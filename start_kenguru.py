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


# Inject ApiPay payment UI before the original app.js.
# It intercepts registration/payment clicks so the old fixed Kaspi QR/manual approval
# flow is not used when ApiPay is active.
index_path = STATIC / "index.html"
if index_path.exists():
    html = index_path.read_text(encoding="utf-8")
    apipay_ui = r"""
<script>
(function(){
  let payPoll=null;

  function cacheKey(t){ return 'kng_apipay_'+t; }

  function setPayUi(p,t){
    const card=document.getElementById('payCard');
    if(!card) return;
    const img=card.querySelector('.payBox img');
    const link=card.querySelector('.payBox a');
    const paid=document.getElementById('paidBtn');

    if(p.qr_image_url && img) img.src=p.qr_image_url;
    if(p.qr_token_url && link){
      link.href=p.qr_token_url;
      link.target='_blank';
      link.rel='noopener';
      link.textContent=(typeof uiLang!=='undefined' && uiLang==='ru')
        ? 'Открыть оплату в Kaspi'
        : 'Kaspi арқылы төлеу';
    }
    if(paid){
      paid.textContent=(typeof uiLang!=='undefined' && uiLang==='ru')
        ? 'Проверить оплату'
        : 'Төлемді тексеру';
    }
    try{ localStorage.setItem(cacheKey(t),JSON.stringify(p)); }catch(e){}
  }

  async function pollPayment(t){
    if(!t) return;
    try{
      const r=await fetch('/api/status/'+encodeURIComponent(t),{cache:'no-store'});
      if(!r.ok) return;
      const s=await r.json();
      if(s.payment_status==='paid'){
        if(payPoll){clearInterval(payPoll);payPoll=null;}
        if(typeof token!=='undefined') token=t;
        if(typeof checkStatus==='function') await checkStatus();
      }
    }catch(e){}
  }

  function startPoll(t){
    if(payPoll) clearInterval(payPoll);
    payPoll=setInterval(()=>pollPayment(t),3000);
    pollPayment(t);
  }

  async function createApiPay(t){
    const r=await fetch('/api/apipay/create/'+encodeURIComponent(t),{method:'POST'});
    if(!r.ok){
      let msg='';
      try{msg=await r.text();}catch(e){}
      alert((typeof uiLang!=='undefined' && uiLang==='ru')
        ? 'Не удалось создать счёт ApiPay. '+msg
        : 'ApiPay төлем шотын жасау мүмкін болмады. '+msg);
      return false;
    }
    const p=await r.json();
    if(p.paid){
      await pollPayment(t);
      return true;
    }
    setPayUi(p,t);
    startPoll(t);
    return true;
  }

  const form=document.getElementById('regForm');
  if(form) form.addEventListener('submit',async function(e){
    e.preventDefault();
    e.stopImmediatePropagation();

    const data={
      lang:document.getElementById('lang').value,
      full_name:document.getElementById('full_name').value.trim(),
      phone:document.getElementById('phone').value.trim(),
      region:document.getElementById('region').value,
      locality:document.getElementById('locality').value.trim(),
      school:document.getElementById('school').value.trim(),
      grade:+document.getElementById('grade').value
    };

    const r=await fetch('/api/register',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(data)
    });
    if(!r.ok){
      alert((typeof uiLang!=='undefined' && uiLang==='ru')
        ? 'Не удалось сохранить заявку'
        : 'Өтінімді сақтау мүмкін болмады');
      return;
    }

    const j=await r.json();
    if(typeof token!=='undefined') token=j.token;
    localStorage.setItem('kng_token',j.token);

    if(typeof showOnly==='function') showOnly('payCard');
    await createApiPay(j.token);
  },true);

  const paid=document.getElementById('paidBtn');
  if(paid) paid.addEventListener('click',async function(e){
    e.preventDefault();
    e.stopImmediatePropagation();
    const t=localStorage.getItem('kng_token')||'';
    await pollPayment(t);
  },true);

  window.addEventListener('load',function(){
    const t=localStorage.getItem('kng_token')||'';
    if(!t) return;
    try{
      const saved=JSON.parse(localStorage.getItem(cacheKey(t))||'null');
      if(saved){
        setPayUi(saved,t);
        startPoll(t);
      }
    }catch(e){}
  });
})();
</script>
"""
    needle = '<script src="/static/app.js"></script>'
    if needle in html and 'kng_apipay_' not in html:
        html = html.replace(needle, apipay_ui + "\n" + needle)
        index_path.write_text(html, encoding="utf-8")


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
