# -*- coding: utf-8 -*-
"""ApiPay integration for KENGURU payment automation."""
import os, json, hmac, hashlib
from decimal import Decimal, InvalidOperation
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from fastapi import HTTPException, Request

APIPAY_BASE = "https://api.apipay.kz/api/v1"

def _main():
    import main
    return main

def _ensure_tables(m):
    with m.db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS apipay_events(
            event_key TEXT PRIMARY KEY,event_type TEXT NOT NULL,invoice_id TEXT,status TEXT,created_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS apipay_invoices(
            token TEXT PRIMARY KEY,invoice_id TEXT NOT NULL,status TEXT NOT NULL,amount TEXT,updated_at TEXT NOT NULL)""")

def _api_post(path, payload):
    api_key = os.getenv("APIPAY_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "ApiPay API key is not configured")
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(APIPAY_BASE + path, data=raw,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"}, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try: detail = json.loads(body)
        except Exception: detail = {"message": body or str(e)}
        raise HTTPException(e.code, detail)
    except URLError:
        raise HTTPException(502, "ApiPay is temporarily unavailable")

def register_apipay(app):
    if getattr(app.state, "_kenguru_apipay", False): return
    app.state._kenguru_apipay = True
    m = _main(); _ensure_tables(m)

    @app.post("/api/apipay/create/{token}")
    def apipay_create(token: str):
        m = _main()
        with m.db() as c: row = c.execute("SELECT * FROM participants WHERE token=?", (token,)).fetchone()
        if not row: raise HTTPException(404, "Participant not found")
        if row["payment_status"] == "paid": return {"ok": True, "paid": True}
        participant = dict(row); full_name = str(participant.get("full_name") or "").strip()
        payload = {"amount": m.PRICE,"description": ("KENGURU-2026 " + full_name)[:100],
            "internal_comment": ("KENGURU participant: " + full_name)[:255],
            "external_order_id": token,"external_order_id_idempotency": ("kenguru-2026-" + token)[:191]}
        data = _api_post("/invoices/qr", payload); invoice_id = str(data.get("id") or "")
        if not invoice_id: raise HTTPException(502, "ApiPay did not return invoice id")
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with m.db() as c:
            c.execute("""INSERT INTO apipay_invoices(token,invoice_id,status,amount,updated_at) VALUES(?,?,?,?,?)
                ON CONFLICT(token) DO UPDATE SET invoice_id=excluded.invoice_id,status=excluded.status,
                amount=excluded.amount,updated_at=excluded.updated_at""",
                (token, invoice_id, str(data.get("status") or "pending"), str(data.get("amount") or m.PRICE), now))
        return {"ok":True,"paid":False,"invoice_id":invoice_id,"status":data.get("status"),
            "qr_token_url":data.get("qr_token_url"),"qr_image_url":data.get("qr_image_url"),"qr_expires_at":data.get("qr_expires_at")}

    @app.post("/api/apipay/webhook")
    async def apipay_webhook(req: Request):
        m = _main(); raw = await req.body()
        try: body = json.loads(raw.decode("utf-8"))
        except Exception: raise HTTPException(400, "Invalid JSON")
        event = str(body.get("event") or ""); secret = os.getenv("APIPAY_WEBHOOK_SECRET", "").strip()
        if not secret:
            if event == "webhook.test": return {"ok":True,"event":event,"setup":True}
            raise HTTPException(503, "ApiPay webhook secret is not configured")
        received = (req.headers.get("X-Webhook-Signature") or "").strip()
        expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        if not received or not hmac.compare_digest(received, expected): raise HTTPException(401, "Invalid webhook signature")
        if event == "webhook.test": return {"ok":True,"event":event}
        if event != "invoice.status_changed": return {"ok":True,"ignored":event}
        inv = body.get("invoice") or {}; invoice_id=str(inv.get("id") or ""); status=str(inv.get("status") or "")
        token=str(inv.get("external_order_id") or ""); event_key=f"{invoice_id}:{status}"
        from datetime import datetime, timezone
        now=datetime.now(timezone.utc).isoformat(); _ensure_tables(m)
        with m.db() as c:
            seen=c.execute("SELECT event_key FROM apipay_events WHERE event_key=?",(event_key,)).fetchone()
            if seen: return {"ok":True,"duplicate":True}
            c.execute("INSERT INTO apipay_events(event_key,event_type,invoice_id,status,created_at) VALUES(?,?,?,?,?)",
                (event_key,event,invoice_id,status,now))
        if not token: return {"ok":True,"ignored":"no_external_order_id"}
        with m.db() as c: participant=c.execute("SELECT token,payment_status FROM participants WHERE token=?",(token,)).fetchone()
        if not participant: return {"ok":True,"ignored":"unknown_participant"}
        if status == "paid":
            try: amount=Decimal(str(inv.get("amount"))); expected_amount=Decimal(str(m.PRICE))
            except (InvalidOperation,TypeError): return {"ok":True,"ignored":"bad_amount"}
            if amount != expected_amount: return {"ok":True,"ignored":"wrong_amount"}
            with m.db() as c:
                c.execute("UPDATE participants SET payment_status='paid' WHERE token=?",(token,))
                c.execute("UPDATE apipay_invoices SET status='paid',amount=?,updated_at=? WHERE token=?",(str(amount),now,token))
            print(f"[KENGURU] ApiPay paid: {token} invoice={invoice_id}",flush=True)
        else:
            with m.db() as c: c.execute("UPDATE apipay_invoices SET status=?,updated_at=? WHERE token=?",(status,now,token))
        return {"ok":True,"status":status}
