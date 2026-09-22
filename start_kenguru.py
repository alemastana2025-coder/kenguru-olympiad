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
.docbar button,.docbar a{border:0;padding:11px 16px;border-radius:9px;font-weight:800;cursor:pointer;background:#087dcc;color:#fff;text-decoration:none}
.docwrap{max-width:1120px;margin:20px auto;padding:0 12px}
@media print{.docbar{display:none!important}.docwrap{margin:0;padding:0;max-width:none}}
</style></head><body>
<div class=\"docbar noprint\"><a href=\"/api/document/${encodeURIComponent(token)}\" target=\"_blank\">Құжатты ашу</a><a href=\"/api/document/${encodeURIComponent(token)}?download=1\" download>PNG жүктеу</a><button id=\"printNow\">Басып шығару</button></div>
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
    const verifyUrl=location.origin+'/verify?no='+encodeURIComponent(x.diploma_no||'');
    d.getElementById('aQr').src='https://quickchart.io/qr?size=150&text='+encodeURIComponent(verifyUrl);
    d.getElementById('printNow').onclick=()=>w.print();
  };
  if(w.document.readyState==='complete')fill();
  else w.addEventListener('load',fill,{once:true});
}
"""
    if "function openDiploma(token)" not in text:
        text = text.replace("async function act(token,action){", admin_diploma_js + "\nasync function act(token,action){")

    (STATIC / "admin.html").write_text(text, encoding="utf-8")

# Scale the admin panel for 10,000+ participants: server-side search and pagination.
admin_live = STATIC / "admin.html"
if admin_live.exists():
    admin_html = admin_live.read_text(encoding="utf-8")
    paged_admin_js = r"""
<script>
const KPAGE={participants:1,payments:1,results:1};
const KSIZE=100;
let KPART=[],KPAY=[],KRES=[],KDEBOUNCE=null;

function kEl(id){return document.getElementById(id)}
function kEnsureUI(){
  if(!kEl('peoplePager')){
    const p=document.createElement('div');p.id='peoplePager';p.className='kpager';
    const box=kEl('peopleRows')?.closest('.panel'); if(box)box.appendChild(p);
  }
  if(!kEl('payFind')){
    const tools=document.createElement('div');tools.className='tools';
    tools.innerHTML='<input class="field" id="payFind" placeholder="Аты-жөні / телефон / мектеп" oninput="kSchedule(\'payments\')"><button class="btnx blue" onclick="kLoadPayments(1)">Жаңарту</button>';
    const tbl=kEl('payRows')?.closest('.tblbox'); if(tbl)tbl.parentNode.insertBefore(tools,tbl);
  }
  if(!kEl('payPager')){
    const p=document.createElement('div');p.id='payPager';p.className='kpager';
    const sec=kEl('payments'); if(sec)sec.appendChild(p);
  }
  if(!kEl('resFind')){
    const tools=document.createElement('div');tools.className='tools';
    tools.innerHTML='<input class="field" id="resFind" placeholder="Аты-жөні / мектеп / KENG №" oninput="kSchedule(\'results\')"><button class="btnx blue" onclick="kLoadResults(1)">Жаңарту</button>';
    const tbl=kEl('resRows')?.closest('.tblbox'); if(tbl)tbl.parentNode.insertBefore(tools,tbl);
  }
  if(!kEl('resPager')){
    const p=document.createElement('div');p.id='resPager';p.className='kpager';
    const sec=kEl('results'); if(sec)sec.appendChild(p);
  }
  if(!kEl('kPagerStyle')){
    const st=document.createElement('style');st.id='kPagerStyle';st.textContent=`
      .kpager{display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap;margin:14px 0 4px;padding:10px;background:#f7fafc;border:1px solid #e2ebf2;border-radius:11px}
      .kpager .kinfo{font-size:13px;color:#647b8e;font-weight:700;padding:0 4px}.kpager button:disabled{opacity:.45;cursor:not-allowed}
    `;document.head.appendChild(st);
  }
}

function kSchedule(kind){
  clearTimeout(KDEBOUNCE);
  KDEBOUNCE=setTimeout(()=>{
    if(kind==='participants')kLoadParticipants(1);
    else if(kind==='payments')kLoadPayments(1);
    else kLoadResults(1);
  },280)
}

async function kFetch(kind,page,q='',grade=''){
  if(!kEl('pw').value)throw new Error('NO_PASSWORD');
  const u=new URL('/api/admin/paged',location.origin);
  u.searchParams.set('password',kEl('pw').value);
  u.searchParams.set('kind',kind);
  u.searchParams.set('page',page);
  u.searchParams.set('page_size',KSIZE);
  if(q)u.searchParams.set('q',q);
  if(grade)u.searchParams.set('grade',grade);
  const r=await fetch(u,{cache:'no-store'});
  if(!r.ok){if(r.status===401)throw new Error('BAD_PASSWORD');throw new Error(await r.text())}
  return await r.json();
}
function kStats(s){
  if(!s)return;
  kEl('nAll').textContent=Number(s.all||0).toLocaleString();
  kEl('nWait').textContent=Number(s.pending||0).toLocaleString();
  kEl('nPaid').textContent=Number(s.paid||0).toLocaleString();
  kEl('nDone').textContent=Number(s.done||0).toLocaleString();
}
function kPager(id,kind,m){
  const el=kEl(id);if(!el)return;
  const total=Number(m.total||0), page=Number(m.page||1), pages=Math.max(1,Number(m.pages||1));
  const start=total?((page-1)*KSIZE+1):0, end=Math.min(page*KSIZE,total);
  const fn=kind==='participants'?'kLoadParticipants':kind==='payments'?'kLoadPayments':'kLoadResults';
  el.innerHTML=`<button class="btnx gray" ${page<=1?'disabled':''} onclick="${fn}(${page-1})">← Алдыңғы</button><span class="kinfo">${start.toLocaleString()}–${end.toLocaleString()} / ${total.toLocaleString()} · ${page}/${pages} бет</span><button class="btnx gray" ${page>=pages?'disabled':''} onclick="${fn}(${page+1})">Келесі →</button>`;
}
function kSyncData(){
  const map=new Map();[...KPART,...KPAY,...KRES].forEach(x=>map.set(x.token,x));DATA=[...map.values()];
}

async function kLoadParticipants(page=KPAGE.participants){
  const q=(kEl('find')?.value||'').trim(), grade=kEl('gfilter')?.value||'';
  const j=await kFetch('participants',page,q,grade);KPAGE.participants=j.page;KPART=j.items||[];kSyncData();kStats(j.stats);
  kEl('peopleRows').innerHTML=KPART.map(x=>`<tr><td>${x.id}</td><td><b>${E(x.full_name)}</b><br><small>${E(x.region)}, ${E(x.locality)}</small></td><td>${x.grade}</td><td>${E(x.phone)}</td><td>${E(x.school)}${x.supervisor?`<br><small>Жетекші: ${E(x.supervisor)}</small>`:''}</td><td>${badge(x)}</td><td>${x.payment_status!=='paid'?`<button class="btnx blue" onclick="act('${x.token}','approve')">✓ Растау</button>`:`<button class="btnx gray" disabled>✓ Расталды</button>`} <button class="btnx gray" onclick="openParticipantEditor('${x.token}')">✎ Түзету</button> <button class="btnx red" onclick="delP('${x.token}')">Өшіру</button></td></tr>`).join('')||'<tr><td colspan="7">Қатысушы жоқ</td></tr>';
  kPager('peoplePager','participants',j)
}
async function kLoadPayments(page=KPAGE.payments){
  const q=(kEl('payFind')?.value||'').trim();
  const j=await kFetch('payments',page,q,'');KPAGE.payments=j.page;KPAY=j.items||[];kSyncData();kStats(j.stats);
  kEl('payRows').innerHTML=KPAY.map(x=>`<tr><td><b>${E(x.full_name)}</b></td><td>${E(x.phone)}</td><td>${x.grade}</td><td>${badge(x)}</td><td>${x.payment_status!=='paid'?`<button class="btnx blue" onclick="act('${x.token}','approve')">Растау</button>`:''} ${x.payment_status==='pending'?`<button class="btnx gray" onclick="act('${x.token}','reject')">Қайтару</button>`:''}</td></tr>`).join('')||'<tr><td colspan="5">Жазба жоқ</td></tr>';
  kPager('payPager','payments',j)
}
async function kLoadResults(page=KPAGE.results){
  const q=(kEl('resFind')?.value||'').trim();
  const j=await kFetch('results',page,q,'');KPAGE.results=j.page;KRES=j.items||[];kSyncData();kStats(j.stats);
  kEl('resRows').innerHTML=KRES.map(x=>`<tr><td><b>${E(x.full_name)}</b><br><small>${E(x.school)}</small></td><td>${x.grade}</td><td><b>${x.score}/30</b></td><td>${E(x.award)}</td><td>${E(x.diploma_no)}</td><td><button class="btnx blue" onclick="openDiploma('${x.token}')">⬇ Диплом / сертификат</button></td></tr>`).join('')||'<tr><td colspan="6">Әзірге нәтиже жоқ</td></tr>';
  kPager('resPager','results',j)
}

window.load=async function(){
  kEnsureUI();
  try{
    await Promise.all([kLoadParticipants(KPAGE.participants),kLoadPayments(KPAGE.payments),kLoadResults(KPAGE.results)]);
    kEl('notice').classList.add('hidden');
  }catch(e){if(e.message==='BAD_PASSWORD'||e.message==='NO_PASSWORD')alert('Пароль қате');else alert('Деректерді жүктеу қатесі: '+e.message)}
};
window.renderPeople=function(){kSchedule('participants')};
window.renderPay=function(){kLoadPayments(KPAGE.payments)};
window.renderRes=function(){kLoadResults(KPAGE.results)};
window.act=async function(token,action){
  const r=await fetch('/api/admin/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:kEl('pw').value,token,action})});
  if(r.ok)await load();else alert('Қате')
};
window.delP=async function(token){
  if(!confirm('Қатысушыны өшіру керек пе?'))return;
  const r=await fetch('/api/admin/participant/'+encodeURIComponent(token)+'?password='+encodeURIComponent(kEl('pw').value),{method:'DELETE'});
  if(r.ok)await load();else alert('Өшіру мүмкін болмады')
};
kEnsureUI();
</script>
"""
    if "const KPAGE={participants:1,payments:1,results:1}" not in admin_html:
        # IMPORTANT: append before the REAL closing body tag, not the </body></html>
        # text that appears inside the diploma window template literal.
        close_pos = admin_html.rfind("</body></html>")
        if close_pos < 0:
            close_pos = admin_html.rfind("</body>")
        if close_pos < 0:
            raise RuntimeError("Admin HTML closing body tag not found")
        admin_html = admin_html[:close_pos] + paged_admin_js + admin_html[close_pos:]
    admin_live.write_text(admin_html, encoding="utf-8")

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
  function diplomaNo(box){
    return String((box.querySelector('.templateNo')||{}).textContent||'').replace(/^№\s*/,'').trim();
  }
  function attachQr(box){
    if(!box)return;
    const no=diplomaNo(box);
    let img=box.querySelector('.templateQr');
    if(!img){
      img=document.createElement('img');
      img.className='templateQr';
      img.alt='QR';
      box.appendChild(img);
    }
    if(no){
      const verifyUrl=location.origin+'/verify?no='+encodeURIComponent(no);
      const next='https://quickchart.io/qr?size=150&text='+encodeURIComponent(verifyUrl);
      if(img.src!==next)img.src=next;
      img.style.display='';
    }else{
      img.style.display='none';
    }
  }
  function scan(){
    document.querySelectorAll('.diplomaTemplate').forEach(attachQr);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',scan,{once:true});
  else scan();
  new MutationObserver(scan).observe(document.documentElement,{childList:true,subtree:true,characterData:true});
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
    '/static/app.js?v=12',
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

# Paginated admin API. Keeps the panel fast even with 10,000+ registrations.
from fastapi import HTTPException as _AdminHTTPException

if not any(getattr(r, "path", "") == "/api/admin/paged" for r in main.app.routes):
    @main.app.get("/api/admin/paged")
    def admin_paged(password: str, kind: str = "participants", q: str = "", grade: int = 0, page: int = 1, page_size: int = 100):
        if not main.secrets.compare_digest(password or "", main.ADMIN_PASSWORD):
            raise _AdminHTTPException(401, "Wrong password")
        kind = (kind or "participants").strip().lower()
        if kind not in {"participants", "payments", "results"}:
            raise _AdminHTTPException(400, "Bad kind")
        page_size = max(25, min(int(page_size or 100), 200))
        page = max(1, int(page or 1))
        q = (q or "").strip().lower()[:160]
        grade = int(grade or 0)

        where = []
        params = []
        if kind == "results":
            where.append("submitted_at IS NOT NULL")
        if grade and 1 <= grade <= 11:
            where.append("grade=?")
            params.append(grade)
        if q:
            where.append("LOWER(COALESCE(full_name,'') || ' ' || COALESCE(phone,'') || ' ' || COALESCE(school,'') || ' ' || COALESCE(supervisor,'') || ' ' || COALESCE(diploma_no,'')) LIKE ?")
            params.append('%' + q + '%')
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        if kind == "payments":
            order_sql = " ORDER BY CASE payment_status WHEN 'pending' THEN 0 WHEN 'unpaid' THEN 1 ELSE 2 END, id DESC"
        elif kind == "results":
            order_sql = " ORDER BY submitted_at DESC, id DESC"
        else:
            order_sql = " ORDER BY id DESC"

        with main.db() as c:
            stat = c.execute("""SELECT COUNT(*) AS n_all,
                COALESCE(SUM(CASE WHEN payment_status='pending' THEN 1 ELSE 0 END),0) AS n_pending,
                COALESCE(SUM(CASE WHEN payment_status='paid' THEN 1 ELSE 0 END),0) AS n_paid,
                COALESCE(SUM(CASE WHEN submitted_at IS NOT NULL THEN 1 ELSE 0 END),0) AS n_done
                FROM participants""").fetchone()
            total_row = c.execute("SELECT COUNT(*) AS n FROM participants" + where_sql, tuple(params)).fetchone()
            total = int(total_row['n'] or 0)
            pages = max(1, (total + page_size - 1) // page_size)
            if page > pages:
                page = pages
            offset = (page - 1) * page_size
            fields = "id,token,lang,full_name,phone,region,locality,school,supervisor,grade,payment_status,created_at,started_at,submitted_at,score,award,diploma_no"
            rows = c.execute(
                "SELECT " + fields + " FROM participants" + where_sql + order_sql + " LIMIT ? OFFSET ?",
                tuple(params + [page_size, offset])
            ).fetchall()
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
            "stats": {
                "all": int(stat['n_all'] or 0),
                "pending": int(stat['n_pending'] or 0),
                "paid": int(stat['n_paid'] or 0),
                "done": int(stat['n_done'] or 0),
            }
        }

# Public diploma/certificate verification page used by QR codes.
from html import escape as html_escape
from fastapi.responses import HTMLResponse

if not any(getattr(r, "path", "") == "/verify" for r in main.app.routes):
    @main.app.get("/verify", response_class=HTMLResponse)
    def verify_document(no: str = ""):
        no = (no or "").strip()
        row = None
        if no:
            with main.db() as c:
                row = c.execute(
                    """SELECT full_name, school, grade, award, diploma_no, submitted_at
                       FROM participants
                       WHERE diploma_no=? AND submitted_at IS NOT NULL
                       LIMIT 1""",
                    (no,)
                ).fetchone()

        if not row:
            return HTMLResponse("""<!doctype html>
<html lang="kk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Құжатты тексеру · KENGURU 2026</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f8fc;font-family:Arial,sans-serif;color:#16324a}
.wrap{max-width:680px;margin:8vh auto;padding:18px}.card{background:#fff;border:1px solid #dbe6ef;border-radius:20px;padding:32px;box-shadow:0 18px 50px rgba(10,55,90,.08)}
.logo{font-size:13px;font-weight:900;color:#087dcc;letter-spacing:.08em}.bad{font-size:58px;margin:18px 0 8px}.muted{color:#6d8294;line-height:1.55}
</style></head><body><div class="wrap"><div class="card"><div class="logo">KENGURU · 2026</div><div class="bad">✕</div>
<h1>Құжат табылмады</h1><p class="muted">QR-кодтағы диплом немесе сертификат нөмірі базаға сәйкес келмейді.</p>
</div></div></body></html>""", status_code=404)

        award = str(row["award"] or "")
        doc_type = "Сертификат" if "сертификаты" in award.lower() else "Диплом"
        full_name = html_escape(str(row["full_name"] or ""))
        school = html_escape(str(row["school"] or ""))
        grade = html_escape(str(row["grade"] or ""))
        award_html = html_escape(award)
        number = html_escape(str(row["diploma_no"] or ""))

        page = f"""<!doctype html>
<html lang="kk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{doc_type} тексерілді · {number}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f8fc;font-family:Arial,sans-serif;color:#15344d}}
.wrap{{max-width:760px;margin:5vh auto;padding:18px}}.card{{background:#fff;border:1px solid #d9e5ee;border-radius:22px;overflow:hidden;box-shadow:0 20px 60px rgba(8,61,99,.10)}}
.head{{padding:28px 30px;background:linear-gradient(135deg,#073762,#0782cf);color:#fff}}.brand{{font-size:13px;font-weight:900;letter-spacing:.08em;opacity:.9}}
.ok{{display:flex;align-items:center;gap:12px;margin-top:15px}}.check{{width:46px;height:46px;border-radius:50%;display:grid;place-items:center;background:#e8fff0;color:#16733a;font-size:28px;font-weight:900}}
.head h1{{font-size:26px;margin:0}}.head p{{margin:5px 0 0;opacity:.86}}
.body{{padding:26px 30px}}.row{{display:grid;grid-template-columns:180px 1fr;gap:16px;padding:15px 0;border-bottom:1px solid #e7eef4}}
.row:last-child{{border-bottom:0}}.label{{color:#718697;font-size:13px;font-weight:700}}.value{{font-weight:800;overflow-wrap:anywhere}}
.number{{color:#087dcc}}.verified{{margin-top:22px;padding:13px 15px;border-radius:12px;background:#eaf8ef;color:#176c34;font-weight:800;text-align:center}}
@media(max-width:600px){{.row{{grid-template-columns:1fr;gap:5px}}.head,.body{{padding:22px}}}}
</style></head><body>
<div class="wrap"><div class="card">
<div class="head"><div class="brand">KENGURU · 2026</div><div class="ok"><div class="check">✓</div><div><h1>Құжат расталды</h1><p>Бұл құжат KENGURU жүйесінің базасында бар.</p></div></div></div>
<div class="body">
<div class="row"><div class="label">Құжат түрі</div><div class="value">{doc_type}</div></div>
<div class="row"><div class="label">Диплом нөмірі</div><div class="value number">{number}</div></div>
<div class="row"><div class="label">Қатысушының аты-жөні</div><div class="value">{full_name}</div></div>
<div class="row"><div class="label">Мектебі</div><div class="value">{school}</div></div>
<div class="row"><div class="label">Сыныбы</div><div class="value">{grade}</div></div>
<div class="row"><div class="label">Алған орны / нәтижесі</div><div class="value">{award_html}</div></div>
<div class="verified">✓ Құжаттың түпнұсқалығы расталды</div>
</div></div></div></body></html>"""
        return HTMLResponse(page)

from question_bank_final import BANK as FINAL_BANK
main.BANK = {g: [dict(q) for q in qs] for g, qs in FINAL_BANK.items()}
print("[KENGURU] FINAL 330 ACTIVE", flush=True)

from admin_extra import register_admin_extra
if not any(getattr(r, "path", "").startswith("/api/admin/questions/") for r in main.app.routes):
    register_admin_extra(main.app)

# ApiPay is deliberately NOT registered.
print("[KENGURU] ADMIN 10K PAGINATION SAFE", flush=True)
print("[KENGURU] MANUAL KASPI PAYMENT ACTIVE", flush=True)

import uvicorn
uvicorn.run(main.app, host="0.0.0.0", port=int(os.environ["PORT"]))
