"""KENGURU high-load guard.

Reduces database connection churn and browser request storms without changing
participant, payment, answer, score or diploma semantics.
"""
import os
import queue
import re
import threading
from pathlib import Path

VERSION = "load-guard-20260929-v1"
MARKER = "KENGURU_LOAD_GUARD_V1"

_POOL_MAX = int(os.getenv("KENGURU_DB_POOL_MAX", "10"))
_POOL = queue.LifoQueue(maxsize=_POOL_MAX)
_POOL_LOCK = threading.Lock()
_POOL_COUNT = 0
_POOL_INSTALLED = False


def install_db_pool():
    """Reuse a small number of psycopg connections instead of reconnecting per request."""
    global _POOL_INSTALLED
    if _POOL_INSTALLED or not os.getenv("DATABASE_URL"):
        return
    import pgcompat
    import psycopg
    from psycopg.rows import dict_row

    def discard(conn):
        global _POOL_COUNT
        try:
            conn.close()
        except Exception:
            pass
        with _POOL_LOCK:
            _POOL_COUNT = max(0, _POOL_COUNT - 1)

    def release(conn):
        if getattr(conn, "closed", True):
            discard(conn)
            return
        try:
            _POOL.put_nowait(conn)
        except queue.Full:
            discard(conn)

    def acquire():
        global _POOL_COUNT
        try:
            conn = _POOL.get_nowait()
            if not getattr(conn, "closed", True):
                return conn
            discard(conn)
        except queue.Empty:
            pass
        create = False
        with _POOL_LOCK:
            if _POOL_COUNT < _POOL_MAX:
                _POOL_COUNT += 1
                create = True
        if create:
            try:
                return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row,
                                       connect_timeout=8, application_name="kenguru-web")
            except Exception:
                with _POOL_LOCK:
                    _POOL_COUNT = max(0, _POOL_COUNT - 1)
                raise
        # Backpressure is safer than opening unbounded connections during a spike.
        conn = _POOL.get(timeout=20)
        if getattr(conn, "closed", True):
            discard(conn)
            return acquire()
        return conn

    class PooledConnection:
        def __init__(self):
            self._conn = acquire()
            self._released = False
            self.row_factory = pgcompat.Row

        def execute(self, sql, params=()):
            cur = self._conn.cursor()
            cur.execute(pgcompat._sql(sql), params or ())
            return pgcompat.Cursor(cur)

        def commit(self):
            self._conn.commit()

        def rollback(self):
            self._conn.rollback()

        def close(self):
            if self._released:
                return
            self._released = True
            try:
                if not self._conn.closed:
                    self._conn.rollback()  # close() without context never leaks a transaction
            finally:
                release(self._conn)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            if self._released:
                return False
            self._released = True
            try:
                if exc_type:
                    self._conn.rollback()
                else:
                    self._conn.commit()
            except Exception:
                discard(self._conn)
                raise
            else:
                release(self._conn)
            return False

    def pooled_connect(_ignored=None, *args, **kwargs):
        return PooledConnection()

    pgcompat.connect = pooled_connect
    _POOL_INSTALLED = True
    print(f"[KENGURU] DB POOL ACTIVE max={_POOL_MAX}", flush=True)


def patch_assets(base):
    """Batch draft writes and avoid aggressive retry storms on final submission."""
    static = Path(base) / "static"
    app = static / "app.js"
    index = static / "index.html"
    js = app.read_text(encoding="utf-8")
    if MARKER in js:
        return
    if "KENGURU_TEST_SAFETY_V1" not in js or "KENGURU_FAMILY_DEVICE_V1" not in js:
        raise RuntimeError("Load guard requires current test-safety and family patches")

    # Final result may legitimately take longer during a spike; ordinary reads remain bounded.
    pattern = r"var began=performance\.now\(\),control=new AbortController\(\),\s*t=setTimeout\(\(\)=>(?:control|controller)\.abort\(\),20000\);"
    replacement = "var began=performance.now(),control=new AbortController(),limit=path==='/api/submit'?60000:25000,t=setTimeout(()=>control.abort(),limit);"
    js, n = re.subn(pattern, replacement, js, count=1)
    if n != 1:
        raise RuntimeError("Load guard: request timeout anchor changed")

    # Periodic state sync is a safety check, not a 20-second polling requirement.
    old = "KTEST.poll=setInterval(()=>{if(document.visibilityState==='visible')void ktSync()},20000);"
    new = "KTEST.poll=setInterval(()=>{if(document.visibilityState==='visible')void ktSync()},60000);"
    if js.count(old) != 1:
        raise RuntimeError("Load guard: poll anchor changed")
    js = js.replace(old, new, 1)

    # Batch rapid answer changes into at most roughly one draft write per 8 seconds.
    old = "clearTimeout(KTEST.saveTimer);KTEST.saveTimer=setTimeout(()=>void ktSave(),350);"
    new = ("clearTimeout(KTEST.saveTimer);"
           "var since=Date.now()-(KTEST.lastDraftFlush||0),wait=Math.max(1200,8000-since);"
           "KTEST.saveTimer=setTimeout(()=>{KTEST.lastDraftFlush=Date.now();void ktSave()},wait);")
    if js.count(old) != 1:
        raise RuntimeError("Load guard: autosave anchor changed")
    js = js.replace(old, new, 1)

    # Do not hammer POST /submit after an ambiguous timeout. Check the saved result first.
    anchor = "async function ktSubmit(reason){"
    helper = r'''// KENGURU_LOAD_GUARD_V1
async function ktRecoverFinal(reason){
  if(!KTEST.token||KTEST.review||KTEST.complete)return;
  var active=KTEST.token;
  try{
    var s=await ktRequest('/api/status/'+encodeURIComponent(active));
    if(active!==token)return;
    if(s&&s.submitted_at&&Number.isInteger(s.score)&&s.diploma_no){showResult(s);return;}
  }catch(e){}
  if(active===token&&!KTEST.complete&&!KTEST.review)void ktSubmit(reason);
}
'''
    if js.count(anchor) != 1:
        raise RuntimeError("Load guard: submit anchor changed")
    js = js.replace(anchor, helper + anchor, 1)

    old = "ktPersist();ktNotice(ktError(e),()=>ktSubmit(reason));ktScheduleRetry(()=>ktSubmit(reason));"
    new = "ktPersist();ktNotice(ktError(e),()=>ktRecoverFinal(reason));ktScheduleRetry(()=>ktRecoverFinal(reason));"
    if js.count(old) != 1:
        raise RuntimeError("Load guard: submit retry anchor changed")
    js = js.replace(old, new, 1)

    # Slower exponential retry under congestion.
    js = js.replace("retryMs:2000,complete:false", "retryMs:4000,complete:false", 1)
    js = js.replace("KTEST.retryMs=Math.min(KTEST.retryMs*2,15000);", "KTEST.retryMs=Math.min(KTEST.retryMs*2,30000);", 1)
    js = js.replace("KTEST.retryMs=2000;ktSavedNotice();", "KTEST.retryMs=4000;ktSavedNotice();")
    js = js.replace("KTEST.retryMs=2000;", "KTEST.retryMs=4000;")

    app.write_text(js, encoding="utf-8")
    html = index.read_text(encoding="utf-8")
    html, n = re.subn(r'/static/app\.js(?:\?[^"\x27\s<>]*)?', '/static/app.js?v=' + VERSION, html)
    if n != 1:
        raise RuntimeError("Load guard: app script URL changed")
    index.write_text(html, encoding="utf-8")


def register_load_guard(app):
    if app.title != "Kenguru Olympiad" or getattr(app.state, "kenguru_load_guard_registered", False):
        return
    app.state.kenguru_load_guard_registered = True

    @app.on_event("startup")
    async def start_load_guard():
        import main
        if main.app is not app:
            return
        if not getattr(app.state, "kenguru_family_installed", False):
            raise RuntimeError("Load guard must run after family patch")
        patch_assets(main.BASE)
        app.state.kenguru_load_guard_installed = True
        print("[KENGURU] LOAD GUARD ACTIVE: POOLED DB; BATCHED DRAFTS; RESULT RECOVERY", flush=True)
