"""Self-reported payment unlock, explicitly authorized by the organizer.

A separate durable ledger keeps access distinct from payment verification.
No existing participant/result/document rows are migrated or marked paid.
The existing paid-participant test and submit handlers remain authoritative.
"""
import math
import re
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import JSONResponse

DELAY_MS = 10_000
VERSION = "self-report-10s-v1"
TABLE = "kenguru_auto_access"


def now_ms():
    return time.time_ns() // 1_000_000


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat() if ms is not None else None


def ensure_schema(m):
    with m.db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS kenguru_auto_access (
            token TEXT PRIMARY KEY REFERENCES participants(token) ON DELETE CASCADE,
            requested_at_ms BIGINT NOT NULL,
            granted_at_ms BIGINT,
            source TEXT NOT NULL DEFAULT 'self_reported_10s'
        )""")


def participant(c, token, lock=False, postgres=False):
    sql = "SELECT * FROM participants WHERE token=?"
    if lock and postgres:
        sql += " FOR UPDATE"
    row = c.execute(sql, (token,)).fetchone()
    if not row:
        raise HTTPException(404, "Participant not found")
    return dict(row)


def fields(p, record, clock):
    """A persisted grant stays valid even if the server clock moves backwards."""
    r = dict(record) if record else {}
    requested = r.get("requested_at_ms")
    due = requested + DELAY_MS if requested is not None else None
    granted = r.get("granted_at_ms")
    if granted is None and due is not None and clock >= due:
        granted = due
    verified = p.get("payment_status") == "paid"
    automatic = granted is not None
    remaining = max(0, due - clock) if due is not None and not automatic and not verified else 0
    return {
        "test_access": verified or automatic,
        "access_source": "payment_confirmed" if verified else ("self_reported_10s" if automatic else None),
        "payment_verified": verified,
        "auto_access_requested_at": iso(requested),
        "auto_access_due_at": iso(due),
        "auto_access_granted_at": iso(granted),
        "auto_access_requested_at_ms": requested,
        "auto_access_due_at_ms": due,
        "auto_access_granted_at_ms": granted,
        "auto_access_pending": bool(requested is not None and not automatic and not verified),
        "auto_access_remaining_ms": remaining,
        "auto_access_seconds_remaining": math.ceil(remaining / 1000),
        "server_now_ms": clock,
        "access_policy_version": VERSION,
    }


def state(c, p, clock, persist=True):
    r = c.execute("SELECT * FROM kenguru_auto_access WHERE token=?", (p["token"],)).fetchone()
    result = fields(p, r, clock)
    # Do not change anything on historical verified/submitted participants.
    if (persist and r and not p.get("submitted_at") and p.get("payment_status") != "paid"
            and r["granted_at_ms"] is None and result["auto_access_granted_at_ms"] is not None):
        c.execute("""UPDATE kenguru_auto_access SET granted_at_ms=requested_at_ms+?
                     WHERE token=? AND granted_at_ms IS NULL AND requested_at_ms<=?""",
                  (DELAY_MS, p["token"], clock - DELAY_MS))
    return result


def status_payload(m, token, mark=False):
    postgres = getattr(m.sqlite3, "__name__", "") == "pgcompat"
    with m.db() as c:
        if mark and not postgres:
            c.execute("BEGIN IMMEDIATE")
        p = participant(c, token, lock=mark, postgres=postgres)
        clock = now_ms()
        if mark and not p.get("submitted_at") and p["payment_status"] != "paid":
            # A repeat click can never replace the first server timestamp.
            # INSERT ... SELECT also protects a concurrent administrator approval.
            c.execute("""INSERT INTO kenguru_auto_access(token,requested_at_ms)
                         SELECT token,? FROM participants
                         WHERE token=? AND payment_status<>'paid' AND submitted_at IS NULL
                         ON CONFLICT(token) DO NOTHING""", (clock, token))
            c.execute("""UPDATE participants SET payment_status='pending'
                         WHERE token=? AND payment_status='unpaid' AND submitted_at IS NULL""", (token,))
            p = participant(c, token)
        p.update(state(c, p, now_ms()))
        p.pop("question_ids", None)
        return p


def decorate_rows(m, rows):
    if not rows:
        return rows
    tokens = [p["token"] for p in rows]
    with m.db() as c:
        records = c.execute("SELECT * FROM kenguru_auto_access WHERE token IN (" +
                            ",".join("?" for _ in tokens) + ")", tuple(tokens)).fetchall()
    records = {r["token"]: r for r in records}
    clock = now_ms()
    return [dict(p, **fields(p, records.get(p["token"]), clock)) for p in rows]


def automatic_test(m, token):
    """Same question bank, order, language and timer as the existing test route."""
    postgres = getattr(m.sqlite3, "__name__", "") == "pgcompat"
    with m.db() as c:
        if not postgres:
            c.execute("BEGIN IMMEDIATE")
        p = participant(c, token, lock=True, postgres=postgres)
        if p.get("submitted_at"):
            raise HTTPException(409, "Attempt already used")
        if not state(c, p, now_ms())["test_access"]:
            raise HTTPException(403, "Test access is not available yet")
        qids = p.get("question_ids")
        if not qids:
            ids = [q["id"] for q in m.BANK[p["grade"]]]
            m.random.Random(token).shuffle(ids)
            qids = ",".join(ids)
            started_at = datetime.now(timezone.utc).isoformat()
            c.execute("UPDATE participants SET question_ids=?,started_at=? WHERE token=?",
                      (qids, started_at, token))
            p["started_at"] = started_at
        ids = qids.split(",")
    bank = {q["id"]: q for q in m.BANK[p["grade"]]}
    lang = p["lang"]
    questions = [{"id": bank[i]["id"], "text": bank[i][lang],
                  "options": m.localized_options(bank[i], lang), "points": bank[i]["points"]} for i in ids]
    started = datetime.fromisoformat(p["started_at"])
    elapsed = max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
    return {"questions": questions, "minutes": 30, "seconds_left": max(0, m.TEST_SECONDS - elapsed),
            "full_name": p["full_name"], "grade": p["grade"], "lang": lang}


def automatic_submit(m, submission):
    """Do not turn an unverified payment into a paid payment to submit a test."""
    postgres = getattr(m.sqlite3, "__name__", "") == "pgcompat"
    with m.db() as c:
        if not postgres:
            c.execute("BEGIN IMMEDIATE")
        p = participant(c, submission.token, lock=True, postgres=postgres)
        if p.get("submitted_at"):
            raise HTTPException(409, "Attempt already used")
        if not state(c, p, now_ms())["test_access"]:
            raise HTTPException(403, "Test access is not available yet")
        if not p.get("started_at"):
            raise HTTPException(409, "Test was not started")
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(p["started_at"])).total_seconds()
        answers = {} if elapsed > m.TEST_SECONDS + m.GRACE_SECONDS else submission.answers
        bank = {q["id"]: q for q in m.BANK[p["grade"]]}
        qids = (p["question_ids"] or "").split(",")
        score = sum(1 for qid in qids if qid and m.answer_is_correct(bank[qid], answers.get(qid), p["lang"]))
        award = "I орын" if score >= 26 else ("II орын" if score >= 21 else ("III орын" if score >= 16 else "Қатысушы сертификаты"))
        number = f"KENG-2026-{p['id']:06d}"
        c.execute("UPDATE participants SET submitted_at=?,score=?,award=?,diploma_no=? WHERE token=?",
                  (datetime.now(timezone.utc).isoformat(), score, award, number, submission.token))
    return {"score": score, "award": award, "diploma_no": number}


def replace_route(app, path, method, endpoint):
    from fastapi.routing import APIRoute
    matches = [r for r in app.routes if isinstance(r, APIRoute) and r.path == path and method in r.methods]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one route: " + method + " " + path)
    old = matches[0]
    app.router.routes.remove(old)
    app.add_api_route(path, endpoint, methods=[method], name=old.name,
                      response_model=old.response_model, status_code=old.status_code,
                      dependencies=old.dependencies, response_class=old.response_class,
                      include_in_schema=old.include_in_schema)


def install(m, patch_assets=True):
    app = m.app
    if getattr(app.state, "kenguru_auto_access_installed", False):
        return
    ensure_schema(m)
    old_test, old_submit = m.get_test, m.submit

    def mark(x):
        return JSONResponse(dict(status_payload(m, x.token, mark=True), ok=True), headers={"Cache-Control": "no-store"})
    mark.__annotations__ = {"x": m.PaymentMark}

    def status(token: str):
        return JSONResponse(status_payload(m, token), headers={"Cache-Control": "no-store"})

    def get_test(token: str):
        with m.db() as c:
            p = participant(c, token)
        if p["payment_status"] == "paid":
            return old_test(token)
        return automatic_test(m, token)

    def submit(s):
        with m.db() as c:
            p = participant(c, s.token)
        if p["payment_status"] == "paid":
            return old_submit(s)
        return automatic_submit(m, s)
    submit.__annotations__ = {"s": m.SubmitTest}

    replace_route(app, "/api/payment-mark", "POST", mark)
    replace_route(app, "/api/status/{token}", "GET", status)
    replace_route(app, "/api/test/{token}", "GET", get_test)
    replace_route(app, "/api/submit", "POST", submit)

    # Preserve existing admin authentication, filters, pagination and paid totals.
    for path in ("/api/admin/list", "/api/admin/paged"):
        route = next((r for r in app.routes if getattr(r, "path", "") == path), None)
        if route is None:
            continue
        def wrap_admin(original):
            @wraps(original)
            def enhanced(*args, **kwargs):
                data = original(*args, **kwargs)
                if isinstance(data, list):
                    return decorate_rows(m, data)
                if isinstance(data, dict) and "items" in data:
                    data = dict(data)
                    data["items"] = decorate_rows(m, data["items"])
                return data
            return enhanced
        replace_route(app, path, "GET", wrap_admin(route.endpoint))
    if patch_assets:
        update_assets(Path(m.BASE) / "static")
    app.openapi_schema = None
    app.state.kenguru_auto_access_installed = True
    print("[KENGURU] SELF-REPORTED 10S ACCESS ACTIVE; PAYMENT STATUS PRESERVED", flush=True)


def update_assets(static):
    path = static / "app.js"
    js = path.read_text(encoding="utf-8")
    if "KENGURU_SELF_REPORT_10S_V1" not in js:
        pattern = r"async function markPaid\(\)\{[\s\S]*?\n\}\n"
        js, n = re.subn(pattern, "async function markPaid(){return kenguruAutoMarkPaid();}\n", js, count=1)
        if n != 1:
            raise RuntimeError("Payment click handler was not found")
        pattern = r"async function checkStatus\(\)\{[\s\S]*?\n\}\nasync function loadTest\(\)\{"
        js, n = re.subn(pattern, "async function checkStatus(){return kenguruAutoCheckStatus();}\nasync function loadTest(){", js, count=1)
        if n != 1:
            raise RuntimeError("Participant status handler was not found")
        start = js.index("function applyLang(){")
        end = js.index("function toggleLang()", start)
        block = js[start:end]
        if "fillSelects()" not in block:
            raise RuntimeError("Language handler changed")
        block = block.replace("function applyLang(){", "function applyLang(){\n  kenguruAutoSetText();", 1)
        block = block.replace("fillSelects()", "fillSelects();kenguruAutoRefreshText()", 1)
        js = js[:start] + block + js[end:]
        prelude = Path(__file__).with_name("kenguru_auto_access.js").read_text(encoding="utf-8")
        path.write_text(prelude + "\n" + js, encoding="utf-8")
    index = static / "index.html"
    html = index.read_text(encoding="utf-8")
    html = re.sub(r'/static/app\.js(?:\?[^"\s<>]*)?', '/static/app.js?v=auto-access-10s-v1', html)
    index.write_text(html, encoding="utf-8")
    admin = static / "admin.html"
    if admin.exists():
        html = admin.read_text(encoding="utf-8")
        if "KENGURU_AUTO_ACCESS_BADGE_V1" not in html:
            pattern = r"function badge\(x\)\{[^\n]*\}"
            replacement = """function badge(x){
  // KENGURU_AUTO_ACCESS_BADGE_V1: an access grant is NOT a verified payment.
  const v=x.payment_status||'unpaid';
  if(v==='paid')return '<span class="pill paid">Төлем расталды / Оплата подтверждена</span>';
  if(x.auto_access_granted_at)return '<span class="pill pending">Авто-рұқсат / Автодопуск</span><br><small>Төлем расталмаған / Оплата не подтверждена</small>';
  if(x.auto_access_requested_at)return '<span class="pill pending">10 с: рұқсат күтілуде / Ожидание допуска</span>';
  return '<span class="pill '+v+'">'+(v==='pending'?'Күтуде / На проверке':'Төленбеген / Не оплачено')+'</span>';
}"""
            html, n = re.subn(pattern, lambda _: replacement, html, count=1)
            if n != 1:
                raise RuntimeError("Admin payment badge was not found")
            admin.write_text(html, encoding="utf-8")


def register_auto_access(app):
    """Install after the existing bootstrap has prepared the actual app and assets."""
    if app.title != "Kenguru Olympiad" or getattr(app.state, "kenguru_auto_access_registered", False):
        return
    app.state.kenguru_auto_access_registered = True

    @app.on_event("startup")
    async def start_auto_access():
        import main
        if main.app is app:
            install(main)
