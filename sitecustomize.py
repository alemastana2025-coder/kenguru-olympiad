"""KENGURU production bootstrap — direct Kaspi pre-import fix."""
import os, sys, re
from pathlib import Path

NEW_PAY_URL = "https://pay.kaspi.kz/pay/cmigicov"
BASE = Path(__file__).parent
OLD_PATTERN = r"https://pay\.kaspi\.kz/pay/[A-Za-z0-9_-]+"

# IMPORTANT: patch source BEFORE main.py is imported, so PAY_URL and the HTML
# served by main are already correct when FastAPI starts.
try:
    for _path in (BASE / "main.py", BASE / "index.html"):
        if _path.exists():
            _text = _path.read_text(encoding="utf-8")
            _text = re.sub(OLD_PATTERN, NEW_PAY_URL, _text)
            _path.write_text(_text, encoding="utf-8")
    print("[KENGURU] KASPI PREIMPORT SOURCE PATCH: cmigicov", flush=True)
except Exception as e:
    print("[KENGURU] Kaspi source patch error:", repr(e), flush=True)

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

        @self.on_event("startup")
        async def _kaspi_final_assertion():
            import main, qrcode
            main.PAY_URL = NEW_PAY_URL

            static = Path(main.BASE) / "static"
            static.mkdir(exist_ok=True)

            # Ensure the actually served static HTML has only the new URL.
            served = static / "index.html"
            if served.exists():
                txt = served.read_text(encoding="utf-8")
                txt = re.sub(OLD_PATTERN, NEW_PAY_URL, txt)
                served.write_text(txt, encoding="utf-8")

            # QR encodes exactly the same new URL.
            qr = qrcode.QRCode(version=None, box_size=10, border=4)
            qr.add_data(NEW_PAY_URL)
            qr.make(fit=True)
            qr.make_image(fill_color="black", back_color="white").save(static / "kaspi_qr.png")

            # Fail deployment startup if any served payment surface is still old.
            html = served.read_text(encoding="utf-8") if served.exists() else ""
            if "pp3rueyw" in html or NEW_PAY_URL not in html:
                raise RuntimeError("KASPI PAYMENT ASSERTION FAILED: served HTML is not cmigicov-only")
            if main.PAY_URL != NEW_PAY_URL:
                raise RuntimeError("KASPI PAYMENT ASSERTION FAILED: API PAY_URL mismatch")

            print("[KENGURU] KASPI VERIFIED ACTIVE: API+BUTTON+QR ONLY cmigicov", flush=True)

    FastAPI.__init__ = _kenguru_init
except Exception as e:
    print("[KENGURU] FastAPI hook error:", repr(e))
