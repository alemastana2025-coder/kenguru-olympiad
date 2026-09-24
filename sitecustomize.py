"""KENGURU production bootstrap.
1) Swaps sqlite3 for PostgreSQL compatibility when DATABASE_URL exists.
2) Extends every FastAPI app with KENGURU admin routes.
3) Adds organizer-authorized, persistent 10-second self-reported access.
"""
import os, sys

if os.getenv("DATABASE_URL"):
    try:
        import pgcompat
        sys.modules["sqlite3"] = pgcompat
        print("[KENGURU] PostgreSQL persistence enabled")
    except Exception as e:
        print("[KENGURU] PostgreSQL bootstrap error:", repr(e))

try:
    from fastapi import FastAPI
    _orig_init = FastAPI.__init__
    def _kenguru_init(self, *args, **kwargs):
        _orig_init(self, *args, **kwargs)
        try:
            from admin_extra import register_admin_extra
            register_admin_extra(self)
        except Exception as e:
            print("[KENGURU] admin extension error:", repr(e))
        from kenguru_auto_access import register_auto_access
        register_auto_access(self)
    FastAPI.__init__ = _kenguru_init
except Exception as e:
    print("[KENGURU] FastAPI hook error:", repr(e))
