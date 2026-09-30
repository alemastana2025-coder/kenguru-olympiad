"""Force every KENGURU payment surface to one Kaspi Pay URL."""
from pathlib import Path
import re
import qrcode

NEW_PAY_URL = "https://pay.kaspi.kz/pay/cmigicov"
OLD_PATTERN = r"https://pay\.kaspi\.kz/pay/[A-Za-z0-9_-]+"

def register_kaspi_complete(app):
    if getattr(app.state, "kenguru_kaspi_complete_registered", False):
        return
    app.state.kenguru_kaspi_complete_registered = True

    import main
    main.PAY_URL = NEW_PAY_URL

    @app.on_event("startup")
    async def _force_payment_assets():
        import main
        main.PAY_URL = NEW_PAY_URL
        base = Path(main.BASE)
        static = base / "static"

        # The visible payment button must use the same URL.
        for path in (base / "index.html", static / "index.html"):
            if path.exists():
                text = path.read_text(encoding="utf-8")
                text = re.sub(OLD_PATTERN, NEW_PAY_URL, text)
                path.write_text(text, encoding="utf-8")

        # Regenerate QR from the exact same URL; no old QR remains.
        static.mkdir(exist_ok=True)
        qr = qrcode.QRCode(version=None, box_size=10, border=4)
        qr.add_data(NEW_PAY_URL)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(static / "kaspi_qr.png")
        root_qr = base / "kaspi_qr.png"
        try:
            img.save(root_qr)
        except Exception:
            pass

        print("[KENGURU] KASPI COMPLETE ACTIVE: API+BUTTON+QR => cmigicov", flush=True)
