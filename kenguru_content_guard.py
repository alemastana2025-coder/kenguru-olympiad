"""Conservative question-content safeguard for Kenguru.

Restore repository wording only when IDs/options/keys/points are unchanged.
Never change historical participant rows, results, diplomas or answer keys.
Incompatible live overrides remain available to already-started attempts; new
attempts in that grade are held for review instead of silently changing scores.
"""
import copy
import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, Request

VERSION = 'content-guard-20260927-v1'
PROTECTED_GRADES = (1, 2, 3, 4)
REFERENCE_GIT_BLOB = '77692e13fd32f38c11bcb849e3409a39aef3e450'


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _signature(question):
    """Order of options and original keys must match, including their types."""
    return _dump([question.get('id'), question.get('points'),
                  question.get('options'), question.get('answer')])


def _question_map(questions, grade):
    if not isinstance(questions, list) or len(questions) != 30:
        return None
    result = {}
    for q in questions:
        if not isinstance(q, dict):
            return None
        qid = q.get('id')
        if not isinstance(qid, str) or qid in result:
            return None
        if not all(isinstance(q.get(lang), str) and q[lang].strip() for lang in ('kk', 'ru')):
            return None
        options = q.get('options')
        if not isinstance(options, list) or len(options) < 2:
            return None
        if any(not isinstance(o, str) or not o for o in options):
            return None
        if len(set(options)) != len(options) or q.get('answer') not in options:
            return None
        if q.get('points') not in (3, 4, 5):
            return None
        result[qid] = q
    expected = {f'g{grade}q{i}' for i in range(1, 31)}
    return result if set(result) == expected else None


def plan_grade(live, reference, grade):
    """Pure planning: no in-place modification and no writes."""
    canonical = _question_map(reference, grade)
    current = _question_map(live, grade)
    if canonical is None:
        raise RuntimeError(f'Reference bank structure invalid for grade {grade}')
    if current is None:
        return None, ['structure']
    incompatible = sorted(qid for qid in canonical
                          if _signature(current[qid]) != _signature(canonical[qid]))
    if incompatible:
        return None, incompatible
    # Preserve live ordering and any additional fields used elsewhere.
    result = copy.deepcopy(live)
    for q in result:
        source = canonical[q['id']]
        q['kk'], q['ru'] = source['kk'], source['ru']
    return result, []


def reference_bank(m):
    path = Path(m.BASE) / 'question_bank_final.py'
    raw = path.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()
    if blob != REFERENCE_GIT_BLOB:
        raise RuntimeError('Reference bank changed: review it before updating the guard checksum')
    from question_bank_final import BANK
    return BANK


def restore_compatible_wording(m, reference):
    plans, report, snapshots = {}, {}, []
    captured_at = datetime.now(timezone.utc).isoformat()
    for grade in PROTECTED_GRADES:
        live = m.BANK.get(grade)
        restored, differences = plan_grade(live, reference.get(grade), grade)
        changed = restored is not None and _dump(restored) != _dump(live)
        report[grade] = {
            'state': 'review_required' if differences else ('wording_restored' if changed else 'matches_reference'),
            'incompatible_question_ids': differences,
        }
        if differences or changed:
            payload = _dump(live)
            digest = hashlib.sha256((str(grade) + ':' + payload).encode('utf-8')).hexdigest()
            snapshots.append((digest, grade, captured_at, VERSION, payload))
        if restored is not None:
            plans[grade] = restored
    # Retain evidence; never delete question_overrides or overwrite participants.
    with m.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS kenguru_question_content_audit(
            digest TEXT PRIMARY KEY, grade INTEGER NOT NULL, captured_at TEXT NOT NULL,
            guard_version TEXT NOT NULL, original_data TEXT NOT NULL)''')
        for snapshot in snapshots:
            c.execute('''INSERT INTO kenguru_question_content_audit
                (digest,grade,captured_at,guard_version,original_data)
                VALUES(?,?,?,?,?) ON CONFLICT(digest) DO NOTHING''', snapshot)
    # Apply only after the audit transaction commits successfully.
    for grade, bank in plans.items():
        m.BANK[grade] = bank
    return report


def _html_notranslate(html):
    def protect(match):
        tag = match.group(0)
        if re.search(r'\btranslate\s*=', tag, re.I):
            tag = re.sub(r'\btranslate\s*=\s*(?:"[^"]*"|\x27[^\x27]*\x27|[^\s>]+)',
                         'translate="no"', tag, flags=re.I)
        else:
            tag = tag[:-1] + ' translate="no">'
        found = re.search(r'\bclass\s*=\s*(["\x27])(.*?)\1', tag, re.I)
        if found:
            classes = found.group(2).split()
            if 'notranslate' not in classes:
                classes.append('notranslate')
            tag = tag[:found.start()] + 'class="' + ' '.join(classes) + '"' + tag[found.end():]
        else:
            tag = tag[:-1] + ' class="notranslate">'
        return tag
    html, n = re.subn(r'<html\b[^>]*>', protect, html, count=1, flags=re.I)
    if n != 1 or not re.search(r'</head\s*>', html, re.I):
        raise RuntimeError('Participant HTML structure not recognized')
    if 'name="google" content="notranslate"' not in html:
        html = re.sub(r'</head\s*>', '<meta name="google" content="notranslate">\n</head>',
                      html, count=1, flags=re.I)
    html = re.sub(r'/static/app\.js(?:\?[^"\x27\s<>]*)?', '/static/app.js?v=' + VERSION, html)
    return html


def protect_assets(m):
    """Standard translation opt-out; native KK/RU language selection still works."""
    index = Path(m.BASE) / 'static' / 'index.html'
    html = _html_notranslate(index.read_text(encoding='utf-8'))
    index.write_text(html, encoding='utf-8')


def install(m):
    app = m.app
    if getattr(app.state, 'kenguru_content_guard_installed', False):
        return
    reference = reference_bank(m)
    report = restore_compatible_wording(m, reference)
    blocked = {g for g, r in report.items() if r['state'] == 'review_required'}
    from kenguru_auto_access import replace_route
    routes = {(getattr(r, 'path', ''), method): r for r in app.routes
              for method in (getattr(r, 'methods', None) or [])}
    # Do not accept new registrations/payments for a grade held for review.
    registration_route = routes.get(('/api/register', 'POST'))
    if registration_route is not None:
        original_registration = registration_route.endpoint
        def checked_registration(r):
            if r.grade in blocked:
                raise HTTPException(503, 'Бұл сыныптың тапсырмалары тексерілуде. Кейінірек тіркеліңіз. / '
                                    'Задания этого класса проходят проверку. Зарегистрируйтесь позже.')
            return original_registration(r)
        checked_registration.__annotations__ = dict(original_registration.__annotations__)
        replace_route(app, '/api/register', 'POST', checked_registration)
    test_route = routes.get(('/api/test/{token}', 'GET'))
    if test_route is None:
        raise RuntimeError('Participant test endpoint not found')
    original_test = test_route.endpoint

    def checked_test(token: str):
        if blocked:
            with m.db() as c:
                p = c.execute('SELECT grade,started_at,submitted_at FROM participants WHERE token=?', (token,)).fetchone()
            if p and p['grade'] in blocked and not p['started_at'] and not p['submitted_at']:
                raise HTTPException(503, 'Тапсырмалар тексерілуде. Кейінірек кіріңіз; қайта төлем жасамаңыз. / '
                                    'Задания проходят проверку. Вернитесь позже; повторная оплата не нужна.')
        return original_test(token)
    replace_route(app, '/api/test/{token}', 'GET', checked_test)

    def authenticate(password):
        if not isinstance(password, str) or not secrets.compare_digest(password, m.ADMIN_PASSWORD):
            raise HTTPException(401, 'Wrong password')

    locked_message = ('1–4 сынып сұрақтары уақытша қорғалған. Өзгерту үшін тексерілген банк нұсқасын жаңартыңыз. / '
                      'Редактирование вопросов 1–4 классов временно закрыто. Изменения требуют проверки новой версии банка.')
    edit = routes.get(('/api/admin/question/{grade}/{qid}', 'PUT'))
    if edit is not None:
        original_edit = edit.endpoint
        async def checked_edit(grade: int, qid: str, request: Request):
            if grade in PROTECTED_GRADES:
                body = await request.json()
                authenticate(body.get('password') if isinstance(body, dict) else None)
                raise HTTPException(409, locked_message)
            return await original_edit(grade, qid, request)
        replace_route(app, '/api/admin/question/{grade}/{qid}', 'PUT', checked_edit)
    reset = routes.get(('/api/admin/questions/{grade}/reset', 'POST'))
    if reset is not None:
        original_reset = reset.endpoint
        def checked_reset(grade: int, password: str):
            if grade in PROTECTED_GRADES:
                authenticate(password)
                raise HTTPException(409, locked_message)
            return original_reset(grade, password)
        replace_route(app, '/api/admin/questions/{grade}/reset', 'POST', checked_reset)

    @app.post('/api/admin/content-audit')
    async def content_audit(request: Request):
        body = await request.json()
        authenticate(body.get('password') if isinstance(body, dict) else None)
        return {'version': VERSION, 'reference_blob': REFERENCE_GIT_BLOB,
                'grades': report, 'new_starts_held_for_review': sorted(blocked)}

    protect_assets(m)
    app.state.kenguru_content_guard_installed = True
    app.state.kenguru_content_guard_report = report
    app.openapi_schema = None
    print('[KENGURU] CONTENT GUARD ACTIVE ' + _dump(report), flush=True)


def register_content_guard(app):
    if app.title != 'Kenguru Olympiad' or getattr(app.state, 'kenguru_content_guard_registered', False):
        return
    app.state.kenguru_content_guard_registered = True
    @app.on_event('startup')
    async def start_content_guard():
        import main
        if main.app is app:
            install(main)
