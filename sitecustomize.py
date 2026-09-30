"""KENGURU production bootstrap."""
import os, sys

if os.getenv("DATABASE_URL"):
    try:
        import pgcompat
        from kenguru_load_guard import install_db_pool
        install_db_pool()
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
        from kenguru_content_guard import register_content_guard
        register_content_guard(self)
        from kenguru_test_safety import register_test_safety
        register_test_safety(self)
        from kenguru_family import register_family
        register_family(self)
        from kenguru_load_guard import register_load_guard
        register_load_guard(self)
        from kenguru_identity_guard import register_identity_guard
        register_identity_guard(self)
        from kenguru_school_wrap import register_school_wrap
        register_school_wrap(self)
        from kenguru_kaspi_complete import register_kaspi_complete
        register_kaspi_complete(self)
    FastAPI.__init__ = _kenguru_init
except Exception as e:
    print("[KENGURU] FastAPI hook error:", repr(e))
