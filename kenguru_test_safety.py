"""Kenguru: explicit start, one server deadline, durable drafts and safe submission.

Installed AFTER auto-access and the content guard. Existing completed records are
read-only. We never change payment_status, reset a start time or regrade history.
Unknown/late unsaved answers go to a review ledger, never silently become {}.
"""
import copy
import hashlib
import json
import math
import re
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

VERSION = "test-safety-20260929-v1"


class StartRequest(BaseModel):
    token: str = Field(min_length=1, max_length=160)


class AnswerRequest(StartRequest):
    answers: dict[str, str | None] = Field(default_factory=dict)
    base_revision: int | None = Field(default=None, ge=0)
    reason: str = Field(default="manual", pattern="^(manual|timeout)$")


class AdminReviewRequest(BaseModel):
    password: str
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


def clock_ms():
    return time.time_ns() // 1_000_000


def stamp(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


def epoch(value):
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return round(d.timestamp() * 1000)


def pack(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fail(code, kk, ru, status=409):
    raise HTTPException(status, {"code": code, "kk": kk, "ru": ru})


@contextmanager
def locked(m, token):
    pg = getattr(m.sqlite3, "__name__", "") == "pgcompat"
    with m.db() as c:
        if not pg:
            c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT * FROM participants WHERE token=?" + (" FOR UPDATE" if pg else ""), (token,)).fetchone()
        if row is None:
            fail("NOT_FOUND", "Қатысушы табылмады.", "Участник не найден.", 404)
        yield c, dict(row)


def schema(m):
    with m.db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS kenguru_test_sessions (
            token TEXT PRIMARY KEY REFERENCES participants(token) ON DELETE CASCADE,
            started_at_ms BIGINT NOT NULL, deadline_at_ms BIGINT NOT NULL,
            lang TEXT NOT NULL, grade INTEGER NOT NULL, question_snapshot TEXT NOT NULL,
            answers_json TEXT NOT NULL DEFAULT '{}', revision INTEGER NOT NULL DEFAULT 0,
            updated_at_ms BIGINT NOT NULL, review_required INTEGER NOT NULL DEFAULT 0,
            review_reason TEXT, policy_version TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS kenguru_test_submission_audit (
            digest TEXT PRIMARY KEY, token TEXT NOT NULL REFERENCES participants(token) ON DELETE CASCADE,
            received_at_ms BIGINT NOT NULL, reason TEXT NOT NULL,
            payload_json TEXT NOT NULL, saved_answers_json TEXT NOT NULL
        )""")


def access(m, c, p, now):
    from kenguru_auto_access import state
    if not state(c, p, now)["test_access"]:
        fail("NO_ACCESS", "Тестке рұқсат әлі ашылмаған.", "Доступ к тесту ещё не открыт.", 403)


def completed(p):
    """Never manufacture a zero from missing/invalid result data."""
    score = p.get("score")
    if not p.get("submitted_at") or type(score) is not int or not 0 <= score <= 30 or not p.get("diploma_no"):
        fail("RESULT_INCOMPLETE", "Нәтиже деректері тексеруді қажет етеді.", "Данные результата требуют проверки.", 503)
    d = {k: v for k, v in p.items() if k != "question_ids"}
    d.update(status="submitted", saved=True, test_safety_version=VERSION)
    return d


def questions_snapshot(m, p, ids):
    bank = {q["id"]: q for q in m.BANK.get(p["grade"], [])}
    if len(ids) != 30 or len(set(ids)) != 30 or any(i not in bank for i in ids):
        fail("QUESTION_SET_MISMATCH", "Тапсырмалар жиынтығын ұйымдастырушы тексеруі керек.", "Организатору нужно проверить набор заданий.")
    result = []
    for qid in ids:
        q = bank[qid]
        opts = q.get("options", [])
        if q.get("answer") not in opts or len(set(opts)) != len(opts) or not q.get(p["lang"]):
            fail("QUESTION_DATA_INVALID", "Тапсырма дерегінде сәйкессіздік бар.", "Обнаружено несоответствие в задании.")
        item = copy.deepcopy(q)
        # Freeze both the original keys and the actual localized display labels.
        item["display_options"] = list(m.localized_options(q, p["lang"]))
        if len(item["display_options"]) != len(opts) or len(set(item["display_options"])) != len(opts):
            fail("OPTION_DATA_INVALID", "Жауап нұсқаларын тексеру қажет.", "Нужно проверить варианты ответов.")
        result.append(item)
    return result


def session(m, c, p, now, start=False):
    row = c.execute("SELECT * FROM kenguru_test_sessions WHERE token=?", (p["token"],)).fetchone()
    if row:
        s = dict(row)
        if (not p.get("started_at") or epoch(p["started_at"]) != s["started_at_ms"]
                or int(p["grade"]) != s["grade"] or p["lang"] != s["lang"]):
            fail("ATTEMPT_CHANGED", "Тест деректері өзгерген. Ұйымдастырушыға хабарласыңыз.", "Данные попытки изменились. Обратитесь к организатору.")
        return s
    if not p.get("started_at"):
        if not start:
            fail("START_REQUIRED", "Бетті жаңартып, дайын болғанда «Тестті бастау» батырмасын басыңыз.", "Обновите страницу и нажмите «Начать тестирование», когда будете готовы.")
        report = getattr(m.app.state, "kenguru_content_guard_report", {})
        guard = report.get(p["grade"], report.get(str(p["grade"]), {}))
        if guard.get("state") == "review_required":
            fail("CONTENT_REVIEW", "Бұл сыныптың тапсырмалары тексерілуде.", "Задания этого класса проходят проверку.", 503)
        ids = [q["id"] for q in m.BANK[p["grade"]]]
        m.random.Random(p["token"]).shuffle(ids)
        snap = questions_snapshot(m, p, ids)
        started = now
        p["started_at"], p["question_ids"] = stamp(started), ",".join(ids)
        c.execute("UPDATE participants SET started_at=?,question_ids=? WHERE token=? AND started_at IS NULL AND submitted_at IS NULL",
                  (p["started_at"], p["question_ids"], p["token"]))
    else:
        # Adopt a running legacy attempt WITHOUT extending/restarting its timer.
        started = epoch(p["started_at"])
        ids = (p.get("question_ids") or "").split(",")
        snap = questions_snapshot(m, p, ids)
    s = dict(token=p["token"], started_at_ms=started,
             deadline_at_ms=started + int(m.TEST_SECONDS) * 1000,
             lang=p["lang"], grade=p["grade"], question_snapshot=pack(snap), answers_json="{}",
             revision=0, updated_at_ms=now, review_required=0, review_reason=None, policy_version=VERSION)
    c.execute("""INSERT INTO kenguru_test_sessions
        (token,started_at_ms,deadline_at_ms,lang,grade,question_snapshot,answers_json,revision,updated_at_ms,policy_version)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", tuple(s[k] for k in ("token", "started_at_ms", "deadline_at_ms", "lang", "grade", "question_snapshot", "answers_json", "revision", "updated_at_ms", "policy_version")))
    return s


def display_answers(s):
    saved = json.loads(s["answers_json"])
    out = {}
    for q in json.loads(s["question_snapshot"]):
        if q["id"] in saved:
            out[q["id"]] = q["display_options"][q["options"].index(saved[q["id"]])]
    return out


def view(s, p, now, include_questions=False):
    d = {"token": p["token"], "status": "review_required" if s["review_required"] else "active",
         "started_at": stamp(s["started_at_ms"]), "started_at_ms": s["started_at_ms"],
         "deadline_at_ms": s["deadline_at_ms"], "server_now_ms": now,
         "remaining_ms": max(0, s["deadline_at_ms"] - now),
         "seconds_left": math.ceil(max(0, s["deadline_at_ms"] - now) / 1000),
         "minutes": 30, "expired": now >= s["deadline_at_ms"],
         "saved_answers": display_answers(s), "revision": s["revision"],
         "full_name": p["full_name"], "grade": s["grade"], "lang": s["lang"],
         "review_reason": s.get("review_reason"), "test_safety_version": VERSION}
    if include_questions:
        d["questions"] = [{"id": q["id"], "text": q[s["lang"]], "points": q["points"],
                           "options": q["display_options"]} for q in json.loads(s["question_snapshot"])]
    return d


def normalize(s, answers):
    if len(answers) > 30:
        fail("INVALID_ANSWERS", "Жауаптар пішімі дұрыс емес.", "Некорректный формат ответов.", 422)
    bank = {q["id"]: q for q in json.loads(s["question_snapshot"])}
    out = {}
    for qid, value in answers.items():
        q = bank.get(qid)
        if not q or (value is not None and (not isinstance(value, str) or len(value) > 1000)):
            fail("INVALID_ANSWER", "Жауап тапсырмаға сәйкес емес.", "Ответ не соответствует заданию.", 422)
        if value is None:
            out[qid] = None
        elif value in q["options"]:
            out[qid] = value
        elif value in q["display_options"]:
            out[qid] = q["options"][q["display_options"].index(value)]
        else:
            fail("INVALID_ANSWER", "Жауап нұсқасы табылмады. Бетті жаңартыңыз.", "Вариант ответа не найден. Обновите страницу.", 422)
    return out


def audit(c, p, s, now, reason, answers):
    payload = pack(answers)
    digest = hashlib.sha256((p["token"] + "|" + reason + "|" + payload).encode()).hexdigest()
    c.execute("""INSERT INTO kenguru_test_submission_audit
        (digest,token,received_at_ms,reason,payload_json,saved_answers_json)
        VALUES(?,?,?,?,?,?) ON CONFLICT(digest) DO NOTHING""",
              (digest, p["token"], now, reason, payload, s["answers_json"]))


def review(c, p, s, now, reason, answers):
    audit(c, p, s, now, reason, answers)
    c.execute("UPDATE kenguru_test_sessions SET review_required=1,review_reason=? WHERE token=?", (reason, p["token"]))
    s.update(review_required=1, review_reason=reason)
    return view(s, p, now)


def merge(c, s, changes, now):
    saved = json.loads(s["answers_json"])
    for qid, val in changes.items():
        if val is None:
            saved.pop(qid, None)
        else:
            saved[qid] = val
    new = pack(saved)
    if new != s["answers_json"]:
        s.update(answers_json=new, revision=s["revision"] + 1, updated_at_ms=now)
        c.execute("UPDATE kenguru_test_sessions SET answers_json=?,revision=?,updated_at_ms=? WHERE token=?",
                  (new, s["revision"], now, s["token"]))


def changed(s, changes):
    saved = json.loads(s["answers_json"])
    return any(saved.get(k) != v for k, v in changes.items())


def read_test(m, token, start=False, include_questions=True):
    with locked(m, token) as (c, p):
        if p.get("submitted_at"):
            return completed(p)
        now = clock_ms()
        access(m, c, p, now)
        s = session(m, c, p, now, start=start)
        return view(s, p, clock_ms(), include_questions)


def write_answers(m, req, finish=False):
    with locked(m, req.token) as (c, p):
        if p.get("submitted_at"):
            # Retry of a completed request returns the same saved result.
            return completed(p)
        now = clock_ms()
        access(m, c, p, now)
        s = session(m, c, p, now)
        delta = normalize(s, req.answers)
        if s["review_required"]:
            audit(c, p, s, now, "review_followup", delta)
            return view(s, p, now)
        if finish and req.reason == "timeout" and now < s["deadline_at_ms"]:
            d = view(s, p, now)
            d.update(status="not_expired", code="NOT_EXPIRED")
            return d
        different = changed(s, delta)
        if now > s["deadline_at_ms"] + int(m.GRACE_SECONDS) * 1000:
            if different:
                return review(c, p, s, now, "late_unsaved_answers", delta)
        elif different:
            if req.base_revision is not None and req.base_revision != s["revision"]:
                d = view(s, p, now)
                d.update(status="revision_conflict", code="REVISION_CONFLICT")
                return d
            merge(c, s, delta, now)
        if not finish:
            return view(s, p, clock_ms())
        saved = json.loads(s["answers_json"])
        if not saved and (req.reason == "timeout" or now > s["deadline_at_ms"] + int(m.GRACE_SECONDS) * 1000):
            return review(c, p, s, now, "expired_without_saved_answers", delta)
        bank = json.loads(s["question_snapshot"])
        score = sum(saved.get(q["id"]) == q["answer"] for q in bank)
        award = "I орын" if score >= 26 else ("II орын" if score >= 21 else ("III орын" if score >= 16 else "Қатысушы сертификаты"))
        number = f"KENG-2026-{p['id']:06d}"
        submitted = stamp(now)
        audit(c, p, s, now, "final_" + req.reason, delta)
        c.execute("UPDATE participants SET submitted_at=?,score=?,award=?,diploma_no=? WHERE token=? AND submitted_at IS NULL",
                  (submitted, score, award, number, p["token"]))
        p.update(submitted_at=submitted, score=score, award=award, diploma_no=number)
        print("[KENGURU] TEST_SAVED " + pack({"participant_id": p["id"], "answered": len(saved), "reason": req.reason, "policy": VERSION}), flush=True)
        return completed(p)


def response(data):
    # Non-success prevents old clients from converting a pending result to 0/30.
    status = 409 if data.get("status") in ("review_required", "revision_conflict", "not_expired") else 200
    body = {"detail": data} if status != 200 else data
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})


def patch_assets(m):
    static = Path(m.BASE) / "static"
    path = static / "app.js"
    js = path.read_text(encoding="utf-8")
    if "KENGURU_TEST_SAFETY_V1" in js:
        return
    pattern = r"async function loadTest\(\)\{[\s\S]*?\n\}\nfunction updateProgress\(\)\{"
    js, n = re.subn(pattern, "async function loadTest(){return ktLoad(false);}\nfunction updateProgress(){", js, count=1)
    if n != 1:
        raise RuntimeError("Safety patch: test loader changed")
    pattern = r"async function submitTest\(\)\{[\s\S]*?\n\}\nfunction showResult\(s\)\{"
    js, n = re.subn(pattern, "async function submitTest(){return ktSubmit('manual');}\nfunction showResult(s){\n  if(!ktAcceptResult(s))return;", js, count=1)
    if n != 1:
        raise RuntimeError("Safety patch: submit handler changed")
    start = js.index("function kenguruAutoStartButton(show){")
    end = js.index("function kenguruAutoRefreshText(){", start)
    block = js[start:end]
    if "try{await loadTest()}" not in block:
        raise RuntimeError("Safety patch: explicit start button changed")
    block = block.replace("try{await loadTest()}", "try{await ktLoad(true)}", 1)
    js = js[:start] + block + js[end:]
    prelude = Path(__file__).with_name("kenguru_test_safety.js").read_text(encoding="utf-8")
    path.write_text(prelude + "\n" + js, encoding="utf-8")
    index = static / "index.html"
    html = index.read_text(encoding="utf-8")
    html = re.sub(r'/static/app\.js(?:\?[^"\x27\s<>]*)?', '/static/app.js?v=' + VERSION, html)
    index.write_text(html, encoding="utf-8")
    # Make review records discoverable from the existing admin page, without writes.
    admin = static / "admin.html"
    if admin.exists():
        html = admin.read_text(encoding="utf-8")
        marker = "KENGURU_TEST_REVIEW_PANEL_V1"
        if marker not in html:
            pos = html.lower().rfind("</body>")
            if pos < 0:
                raise RuntimeError("Safety patch: admin body missing")
            extra = '''<script>// KENGURU_TEST_REVIEW_PANEL_V1
window.addEventListener('DOMContentLoaded',function(){
 const box=document.createElement('section');box.className='panel';box.style.margin='20px';
 const b=document.createElement('button');b.type='button';b.className='btnx blue';b.textContent='Тест қателері / Проверка попыток';
 const out=document.createElement('div');box.append(b,out);document.body.appendChild(box);let page=1;
 async function load(){out.textContent='Жүктелуде / Загрузка…';try{
 const r=await fetch('/api/admin/test-review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.getElementById('pw').value,page:page,page_size:50})});
 if(!r.ok)throw Error('Қате / Ошибка '+r.status);const j=await r.json();out.textContent='Барлығы / Всего: '+j.total;
 j.items.forEach(x=>{const p=document.createElement('p');p.textContent=x.full_name+' · '+x.phone+' · '+x.grade+' · '+x.review_reason+' · № '+x.id;out.appendChild(p)});
 if(page>1){const prev=document.createElement('button');prev.textContent='←';prev.onclick=()=>{page--;load()};out.appendChild(prev)}
 if(page*50<j.total){const next=document.createElement('button');next.textContent='→';next.onclick=()=>{page++;load()};out.appendChild(next)}
 }catch(e){out.textContent=e.message}}b.onclick=()=>{page=1;load()};
});</script>'''
            admin.write_text(html[:pos] + extra + html[pos:], encoding="utf-8")


def install(m, assets=True):
    from kenguru_auto_access import replace_route
    if getattr(m.app.state, "kenguru_test_safety_installed", False):
        return
    # Validate assets before adding any new table or enabling routes.
    if assets:
        patch_assets(m)
    schema(m)
    def resume(token: str):
        return response(read_test(m, token))
    def begin(r: StartRequest):
        return response(read_test(m, r.token, start=True))
    def state(token: str):
        return response(read_test(m, token, include_questions=False))
    def save(r: AnswerRequest):
        if r.base_revision is None:
            fail("REVISION_REQUIRED", "Жауап нұсқасының нөмірі қажет.", "Нужен номер версии ответов.", 422)
        return response(write_answers(m, r))
    def finish(r: AnswerRequest):
        return response(write_answers(m, r, finish=True))
    replace_route(m.app, "/api/test/{token}", "GET", resume)
    replace_route(m.app, "/api/submit", "POST", finish)
    m.app.add_api_route("/api/test/start", begin, methods=["POST"])
    m.app.add_api_route("/api/test/state/{token}", state, methods=["GET"])
    m.app.add_api_route("/api/test/answers", save, methods=["POST"])
    @m.app.post("/api/admin/test-review")
    def admin_review(r: AdminReviewRequest):
        if not secrets.compare_digest(r.password, m.ADMIN_PASSWORD):
            raise HTTPException(401, "Wrong password")
        with m.db() as c:
            n = c.execute("SELECT COUNT(*) AS n FROM kenguru_test_sessions WHERE review_required=1").fetchone()["n"]
            rows = c.execute("""SELECT p.id,p.full_name,p.phone,p.grade,p.payment_status,p.submitted_at,
                s.review_reason,s.started_at_ms,s.deadline_at_ms,s.revision,s.answers_json
                FROM kenguru_test_sessions s JOIN participants p ON p.token=s.token
                WHERE s.review_required=1 ORDER BY s.updated_at_ms DESC LIMIT ? OFFSET ?""",
                             (r.page_size, (r.page - 1) * r.page_size)).fetchall()
        return {"total": n, "page": r.page, "items": [dict(x) for x in rows]}
    m.app.openapi_schema = None
    m.app.state.kenguru_test_safety_installed = True
    print("[KENGURU] TEST SAFETY ACTIVE: SERVER DEADLINE; DURABLE ANSWERS; IDEMPOTENT SUBMIT", flush=True)


def register_test_safety(app):
    if app.title != "Kenguru Olympiad" or getattr(app.state, "kenguru_test_safety_registered", False):
        return
    app.state.kenguru_test_safety_registered = True
    @app.on_event("startup")
    async def start_test_safety():
        import main
        if main.app is app:
            install(main)
