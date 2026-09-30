"""KENGURU Kaspi Pay link override."""
NEW_PAY_URL = "https://pay.kaspi.kz/pay/cmigicov"

def register_kaspi_link(app):
    if getattr(app.state, "kenguru_kaspi_link_registered", False):
        return
    app.state.kenguru_kaspi_link_registered = True
    import main
    main.PAY_URL = NEW_PAY_URL
    print("[KENGURU] KASPI PAY LINK ACTIVE: cmigicov", flush=True)
