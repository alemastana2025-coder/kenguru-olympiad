# -*- coding: utf-8 -*-
import os, sys, shutil, re
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
STATIC.mkdir(exist_ok=True)

# Copy the current site assets. ApiPay UI is intentionally NOT copied/loaded.
for name in ("index.html", "app.js", "style.css", "logo.jpg", "kaspi_qr.png"):
    src = BASE / name
    if src.exists():
        shutil.copy2(src, STATIC / name)

# Keep the admin search fix and add organizer-side diploma/certificate download.
admin_src = BASE / "admin.html"
if admin_src.exists():
    text = admin_src.read_text(encoding="utf-8").replace(
        "find.value.toLowerCase()",
        "document.getElementById('find').value.toLowerCase()"
    )

    # Results table: add a document action column.
    text = text.replace(
        '<th>Оқушы</th><th>Сынып</th><th>Ұпай</th><th>Марапат</th><th>№ KENG</th></tr>',
        '<th>Оқушы</th><th>Сынып</th><th>Ұпай</th><th>Марапат</th><th>№ KENG</th><th>Құжат</th></tr>'
    )

    # Results rows: one-click access to the participant's exact diploma/certificate.
    old_render = """function renderRes(){let a=DATA.filter(x=>x.submitted_at);resRows.innerHTML=a.map(x=>`<tr><td><b>${E(x.full_name)}</b><br><small>${E(x.school)}</small></td><td>${x.grade}</td><td><b>${x.score}/30</b></td><td>${E(x.award)}</td><td>${E(x.diploma_no)}</td></tr>`).join('')||'<tr><td colspan=\"5\">Әзірге нәтиже жоқ</td></tr>'}"""
    new_render = """function renderRes(){let a=DATA.filter(x=>x.submitted_at);resRows.innerHTML=a.map(x=>`<tr><td><b>${E(x.full_name)}</b><br><small>${E(x.school)}</small></td><td>${x.grade}</td><td><b>${x.score}/30</b></td><td>${E(x.award)}</td><td>${E(x.diploma_no)}</td><td><button class=\"btnx blue\" onclick=\"openDiploma('${x.token}')\">⬇ Диплом / сертификат</button></td></tr>`).join('')||'<tr><td colspan=\"6\">Әзірге нәтиже жоқ</td></tr>'}"""
    text = text.replace(old_render, new_render)

    admin_diploma_js = r"""
function openDiploma(token){
  const x=DATA.find(p=>p.token===token);
  if(!x||!x.submitted_at)return alert('Қатысушы тестті әлі аяқтамаған');
  const isCertificate=String(x.award||'').includes('сертификаты');
  const place=String(x.award||'').match(/^(I{1,3})/);
  const w=window.open('','_blank');
  if(!w)return alert('Браузер жаңа терезені бұғаттады');

  w.document.write(`<!doctype html><html lang=\"kk\"><head>
<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>${isCertificate?'Сертификат':'Диплом'} · ${E(x.full_name)}</title>
<link rel=\"stylesheet\" href=\"/static/style.css\">
<style>
body{margin:0;background:#eef4f8;font-family:Arial,sans-serif}
.docbar{position:sticky;top:0;z-index:20;display:flex;justify-content:center;gap:10px;padding:12px;background:#fff;border-bottom:1px solid #dbe6ef}
.docbar button{border:0;padding:11px 16px;border-radius:9px;font-weight:800;cursor:pointer;background:#087dcc;color:#fff}
.docwrap{max-width:1120px;margin:20px auto;padding:0 12px}
@media print{.docbar{display:none!important}.docwrap{margin:0;padding:0;max-width:none}}
</style></head><body>
<div class=\"docbar noprint\"><button id=\"printNow\">⬇ Жүктеу / басып шығару</button></div>
<div class=\"docwrap\">
  <div class=\"diploma diplomaTemplate${isCertificate?' certificate':''}\" id=\"adminDiploma\">
    <img class=\"diplomaBg\" id=\"aBg\" src=\"${isCertificate?'/static/certificate_template.png':'/static/diploma_template.png'}\" alt=\"\">
    <div class=\"templateDateFix\">15–30 ҚЫРКҮЙЕК</div>
    <div class=\"templateField templateName\" id=\"aName\"></div>
    <div class=\"templateField templateSchool\" id=\"aSchool\"></div>
    <div class=\"templateField templateGrade\" id=\"aGrade\"></div>
    <div class=\"templateField templateAward\" id=\"aAward\"></div>
    <div class=\"templateField templateSupervisor\" id=\"aSupervisor\"></div>
    <div class=\"templateField templateNo\" id=\"aNo\"></div>
    <img class=\"templateQr\" id=\"aQr\" alt=\"QR\">
  </div>
</div></body></html>`);
  w.document.close();

  const fill=()=>{
    const d=w.document;
    d.getElementById('aName').textContent=x.full_name||'';
    d.getElementById('aSchool').textContent=x.school||'';
    d.getElementById('aGrade').textContent=x.grade||'';
    d.getElementById('aAward').textContent=place?place[1]:'';
    const sup=d.getElementById('aSupervisor');
    sup.textContent=x.supervisor?'Жетекшісі: '+x.supervisor:'';
    const len=(sup.textContent||'').trim().length;
    sup.style.fontSize=(len>72?.86:len>60?1:len>50?1.15:(isCertificate?1.28:1.32))+'cqw';
    sup.style.whiteSpace='nowrap';
    d.getElementById('aNo').textContent='№ '+(x.diploma_no||'');
    const qrData=['KENGURU 2026','Құжат: '+(isCertificate?'Сертификат':'Диплом'),'№ '+(x.diploma_no||''),'Аты-жөні: '+(x.full_name||''),'Мектеп: '+(x.school||''),'Сыныбы: '+(x.grade||''),'Нәтиже: '+(x.award||'')].join('\n');
    d.getElementById('aQr').src='https://quickchart.io/qr?size=150&text='+encodeURIComponent(qrData);
    d.getElementById('printNow').onclick=()=>w.print();
  };
  if(w.document.readyState==='complete')fill();
  else w.addEventListener('load',fill,{once:true});
}
"""
    if "function openDiploma(token)" not in text:
        text = text.replace("async function act(token,action){", admin_diploma_js + "\nasync function act(token,action){")

    (STATIC / "admin.html").write_text(text, encoding="utf-8")

# Keep the latest diploma/supervisor layout adjustments.
css_patch = r"""
.diplomaTemplate{container-type:inline-size}.diplomaTemplate .templateDateFix{font-size:2.05cqw;white-space:nowrap;top:16.55%;right:2.5%;font-family:'Segoe UI',Arial,'DejaVu Sans','Noto Sans',sans-serif;font-weight:900;letter-spacing:0}.diplomaTemplate .templateName,.diplomaTemplate .templateSchool,.diplomaTemplate .templateGrade,.diplomaTemplate .templateAward,.diplomaTemplate .templateSupervisor,.diplomaTemplate .templateNo{font-family:'Segoe UI',Arial,'DejaVu Sans','Noto Sans',sans-serif;letter-spacing:0;line-height:1.1}.diplomaTemplate .templateName{font-size:3.0cqw;top:45.7%;font-weight:800}.diplomaTemplate .templateSchool{font-size:1.8cqw;top:52.8%;font-weight:700}.diplomaTemplate .templateGrade{font-size:2.2cqw;font-weight:700}.diplomaTemplate .templateAward{font-size:2.2cqw;font-weight:700}.diplomaTemplate .templateSupervisor{left:15%;top:65.0%;width:70%;font-size:1.32cqw;font-weight:700}.diplomaTemplate .templateNo{font-size:1.25cqw;font-weight:700}.diplomaTemplate.certificate .templateName{left:20.5%;top:42.9%;width:58%}.diplomaTemplate.certificate .templateSchool{left:20.5%;top:49.8%;width:58%}.diplomaTemplate.certificate .templateGrade{left:29.2%;top:56.9%;width:45%;text-align:left;padding-left:1%}.diplomaTemplate.certificate .templateSupervisor{left:20%;top:61.2%;width:60%;font-size:1.28cqw}.diplomaTemplate .templateQr{position:absolute;right:4.2%;bottom:6.2%;width:12.4cqw;height:12.4cqw;object-fit:contain;background:#fff;padding:.45cqw;border-radius:.65cqw;box-shadow:0 0 0 .15cqw rgba(0,0,0,.06)}.diplomaTemplate.certificate .templateQr{right:4.6%;bottom:6.6%;width:12.2cqw;height:12.2cqw}
"""
with (STATIC / "style.css").open("a", encoding="utf-8") as f:
    f.write("\n" + css_patch + "\n")

# Keep diploma preview helper.
preview = r"""if(new URLSearchParams(location.search).get('preview')==='diploma'){token='';showResult({lang:'kk',score:30,award:'I орын',diploma_no:'KENG-2026-PREVIEW',full_name:'ТЕСТ ОҚУШЫ ӘБІЛҚАСЫМҰЛЫ',school:'№93 қазақ мектебі',supervisor:'АХМЕТОВА АЙГҮЛ СЕРІКҚЫЗЫ',grade:'5'});}"""
with (STATIC / "app.js").open("a", encoding="utf-8") as f:
    f.write("\n" + preview + "\n")

# Add QR code to participant-facing diploma/certificate in the lower-right corner.
qr_patch = r"""
(function(){
  function buildQrText(box){
    const no=(box.querySelector('.templateNo')||{}).textContent||'';
    const name=(box.querySelector('.templateName')||{}).textContent||'';
    const school=(box.querySelector('.templateSchool')||{}).textContent||'';
    const grade=(box.querySelector('.templateGrade')||{}).textContent||'';
    const award=(box.querySelector('.templateAward')||{}).textContent||'';
    const isCertificate=box.classList.contains('certificate');
    return ['KENGURU 2026','Құжат: '+(isCertificate?'Сертификат':'Диплом'),no,name&&('Аты-жөні: '+name),school&&('Мектеп: '+school),grade&&('Сыныбы: '+grade),award&&('Нәтиже: '+award)].filter(Boolean).join('\n');
  }
  function attachQr(box){
    if(!box || box.querySelector('.templateQr')) return;
    const img=document.createElement('img');
    img.className='templateQr';
    img.alt='QR';
    img.src='https://quickchart.io/qr?size=150&text='+encodeURIComponent(buildQrText(box));
    box.appendChild(img);
  }
  function scan(){
    document.querySelectorAll('.diplomaTemplate').forEach(attachQr);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',scan,{once:true});
  else scan();
  new MutationObserver(scan).observe(document.documentElement,{childList:true,subtree:true});
})();
"""
with (STATIC / "app.js").open("a", encoding="utf-8") as f:
    f.write("\n" + qr_patch + "\n")

# -------------------------------------------------------------------
# IMPORTANT: restore the ORIGINAL manual Kaspi confirmation flow.
# Registration -> fixed Kaspi Pay link/QR -> "Төледім / Я оплатил(а)"
# -> payment_status=pending -> organizer approves in /admin -> test opens.
# No ApiPay API, invoices or webhook are used.
# -------------------------------------------------------------------

# Remove the separate ApiPay browser script and force browsers to refresh app.js.
index_path = STATIC / "index.html"
html = index_path.read_text(encoding="utf-8")
html = re.sub(
    r'\s*<script\s+src="/static/apipay_ui\.js(?:\?v=\d+)?"></script>',
    '',
    html
)
html = re.sub(
    r'/static/app\.js(?:\?v=\d+)?',
    '/static/app.js?v=11',
    html
)
index_path.write_text(html, encoding="utf-8")

app_path = STATIC / "app.js"
js = app_path.read_text(encoding="utf-8")

# Remove ApiPay mode flag.
js = js.replace(
    "window.__KENGURU_APIPAY_V6__ = true; // disables the old separate ApiPay patch\n\n",
    ""
)

# Restore manual-payment wording.
repls = {
    "c2p:'Тіркелгеннен кейін жеке ApiPay/Kaspi төлем шоты жасалады.'":
        "c2p:'Kaspi арқылы төлем жасап, төленгенін белгілеңіз.'",
    "c2p:'После регистрации создаётся индивидуальный счёт ApiPay/Kaspi.'":
        "c2p:'Оплатите через Kaspi и отметьте, что платёж выполнен.'",
    "payText:'Жеке QR-код арқылы төлеңіз. Төлем расталған соң тест автоматты түрде ашылады.'":
        "payText:'QR-кодты сканерлеңіз немесе Kaspi төлем сілтемесін ашыңыз. Содан кейін «Төледім» батырмасын басыңыз.'",
    "payText:'Оплатите по индивидуальному QR-коду. После подтверждения тест откроется автоматически.'":
        "payText:'Отсканируйте QR-код или откройте ссылку Kaspi. После оплаты нажмите «Я оплатил(а)».'",
    "payText:'Оплатите по индивидуальному QR-коду. После подтверждения оплаты тест откроется автоматически.'":
        "payText:'Отсканируйте QR-код или откройте ссылку Kaspi. После оплаты нажмите «Я оплатил(а)».'",
    "iPaid:'Төлемді тексеру'":
        "iPaid:'Төледім'",
    "iPaid:'Проверить оплату'":
        "iPaid:'Я оплатил(а)'",
    "waitText:'Төлем расталғаннан кейін тест автоматты түрде ашылады.'":
        "waitText:'Ұйымдастырушы төлемді растағаннан кейін тест ашылады. Осы бетті кейін қайта ашсаңыз да өтінім сақталады.'",
    "waitText:'После подтверждения оплаты тест откроется автоматически.'":
        "waitText:'После подтверждения организатором тест откроется. Заявка сохранится, даже если вы позже снова откроете страницу.'",
}
for old, new in repls.items():
    js = js.replace(old, new)

# Replace the entire ApiPay invoice block with the old "I paid" marker.
manual_block = r"""async function markPaid(){
  if(!token)return;
  let r=await fetch('/api/payment-mark',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({token})
  });
  if(r.ok){
    showOnly('waitCard');
    await checkStatus()
  }
}

byId('langBtn').addEventListener"""

js, n = re.subn(
    r"function paymentNodes\(\)\{[\s\S]*?\n\}\n\nbyId\('langBtn'\)\.addEventListener",
    manual_block,
    js,
    count=1
)
if n != 1:
    raise RuntimeError("Manual-payment patch failed: ApiPay payment block not found")

# Registration must only show the existing Kaspi Pay link/QR.
js = js.replace(
    "  showOnly('payCard');\n  await createInvoice();",
    "  showOnly('payCard');"
)

# "I paid" sends the application to manual review.
js = js.replace(
    "byId('paidBtn').addEventListener('click',checkStatus);",
    "byId('paidBtn').addEventListener('click',markPaid);"
)

# Restore pending/waiting behavior until organizer approves.
manual_status = r"""async function checkStatus(){
  if(!token)return;
  let r=await fetch('/api/status/'+encodeURIComponent(token),{cache:'no-store'});
  if(!r.ok){
    localStorage.removeItem('kng_token');
    token='';
    return
  }
  let s=await r.json();
  uiLang=s.lang||uiLang;
  applyLang();

  if(s.submitted_at){
    showResult(s);
    return
  }

  if(s.payment_status==='paid'){
    showOnly('testCard');
    await loadTest()
  }else if(s.payment_status==='pending'){
    showOnly('waitCard');
    byId('payStatus').textContent=uiLang==='kk'?'Тексерілуде':'На проверке'
  }else{
    showOnly('payCard')
  }
}
async function loadTest(){"""

js, n = re.subn(
    r"async function checkStatus\(\)\{[\s\S]*?\n\}\nasync function loadTest\(\)\{",
    manual_status,
    js,
    count=1
)
if n != 1:
    raise RuntimeError("Manual-payment patch failed: status block not found")

# On a returning visitor, just restore their participant status.
js, n = re.subn(
    r"applyLang\(\);\nif\(token\)\{[\s\S]*?\n\}\nconsole\.log\('\[KENGURU\] MAIN UI V8 \+ APIPAY ACTIVE'\);",
    "applyLang();\nif(token)checkStatus();\nconsole.log('[KENGURU] MAIN UI V8 + MANUAL KASPI ACTIVE');",
    js,
    count=1
)
if n != 1:
    # Safe fallback for minor console/version differences.
    js = re.sub(
        r"applyLang\(\);\nif\(token\)\{[\s\S]*$",
        "applyLang();\nif(token)checkStatus();\nconsole.log('[KENGURU] MANUAL KASPI ACTIVE');\n",
        js,
        count=1
    )

# There must be no active ApiPay calls left in the browser code.
if "/api/apipay/" in js or "createInvoice(" in js:
    raise RuntimeError("ApiPay is still active in patched app.js")

app_path.write_text(js, encoding="utf-8")

# Persistent PostgreSQL compatibility.
import pgcompat
sys.modules["sqlite3"] = pgcompat
print("[KENGURU] PostgreSQL persistence enabled", flush=True)

import main
from question_bank_final import BANK as FINAL_BANK
main.BANK = {g: [dict(q) for q in qs] for g, qs in FINAL_BANK.items()}
print("[KENGURU] FINAL 330 ACTIVE", flush=True)

from admin_extra import register_admin_extra
if not any(getattr(r, "path", "").startswith("/api/admin/questions/") for r in main.app.routes):
    register_admin_extra(main.app)

# ApiPay is deliberately NOT registered.
print("[KENGURU] MANUAL KASPI PAYMENT ACTIVE", flush=True)

import uvicorn
uvicorn.run(main.app, host="0.0.0.0", port=int(os.environ["PORT"]))
