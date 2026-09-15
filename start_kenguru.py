# -*- coding: utf-8 -*-
"""
Stable startup for KENGURU on Render.
Keeps PostgreSQL, final 330-question bank, admin tools, document layout fixes,
and ApiPay integration in one place.
"""
import os
import sys
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
STATIC.mkdir(exist_ok=True)

# Copy public assets from repository root to /static on every Render start.
for name in ("index.html", "app.js", "style.css", "logo.jpg", "kaspi_qr.png"):
    src = BASE / name
    if src.exists():
        shutil.copy2(src, STATIC / name)

# Admin page: preserve the browser window.find collision fix.
admin_src = BASE / "admin.html"
if admin_src.exists():
    text = admin_src.read_text(encoding="utf-8")
    text = text.replace(
        "find.value.toLowerCase()",
        "document.getElementById('find').value.toLowerCase()",
    )
    (STATIC / "admin.html").write_text(text, encoding="utf-8")

# Preserve diploma/certificate positioning and Kazakh-capable dynamic fonts.
css_patch = r"""
.diplomaTemplate{container-type:inline-size}.diplomaTemplate .templateDateFix{font-size:2.05cqw;white-space:nowrap;top:16.55%;right:2.5%;font-family:'Segoe UI',Arial,'DejaVu Sans','Noto Sans',sans-serif;font-weight:900;letter-spacing:0}.diplomaTemplate .templateName,.diplomaTemplate .templateSchool,.diplomaTemplate .templateGrade,.diplomaTemplate .templateAward,.diplomaTemplate .templateNo{font-family:'Segoe UI',Arial,'DejaVu Sans','Noto Sans',sans-serif;letter-spacing:0;line-height:1.1}.diplomaTemplate .templateName{font-size:3.0cqw;top:45.7%;font-weight:800}.diplomaTemplate .templateSchool{font-size:1.8cqw;top:52.8%;font-weight:700}.diplomaTemplate .templateGrade{font-size:2.2cqw;font-weight:700}.diplomaTemplate .templateAward{font-size:2.2cqw;font-weight:700}.diplomaTemplate .templateNo{font-size:1.25cqw;font-weight:700}.diplomaTemplate.certificate .templateName{left:20.5%;top:42.9%;width:58%}.diplomaTemplate.certificate .templateSchool{left:20.5%;top:49.8%;width:58%}.diplomaTemplate.certificate .templateGrade{left:29.2%;top:56.9%;width:45%;text-align:left;padding-left:1%}
"""
style_path = STATIC / "style.css"
if style_path.exists():
    with style_path.open("a", encoding="utf-8") as f:
        f.write("\n" + css_patch + "\n")

# Preserve document preview helper.
preview_patch = r"""
if(new URLSearchParams(location.search).get('preview')==='diploma'){token='';showResult({lang:'kk',score:30,award:'I орын',diploma_no:'KENG-2026-PREVIEW',full_name:'ТЕСТ ОҚУШЫ ӘБІЛҚАСЫМҰЛЫ',school:'№93 қазақ мектебі',grade:'5'});}
"""
app_js = STATIC / "app.js"
if app_js.exists():
    with app_js.open("a", encoding="utf-8") as f:
        f.write("\n" + preview_patch + "\n")

# Force PostgreSQL compatibility BEFORE importing main.py.
import pgcompat
sys.modules["sqlite3"] = pgcompat
print("[KENGURU] PostgreSQL persistence enabled", flush=True)

import main

# Always use the reviewed final 330-question bank.
from question_bank_final import BANK as FINAL_BANK
main.BANK = {g: [dict(q) for q in qs] for g, qs in FINAL_BANK.items()}
print("[KENGURU] FINAL 330 ACTIVE", flush=True)

# Admin question editor/templates/export.
from admin_extra import register_admin_extra
if not any(
    getattr(r, "path", "").startswith("/api/admin/questions/")
    for r in main.app.routes
):
    register_admin_extra(main.app)

# ApiPay QR + signed webhook integration.
from apipay_extra import register_apipay
register_apipay(main.app)
print("[KENGURU] APIPAY READY", flush=True)

import uvicorn
uvicorn.run(
    main.app,
    host="0.0.0.0",
    port=int(os.environ["PORT"]),
)
