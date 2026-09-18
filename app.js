// KENGURU main UI V8 — supervisor details flow from registration to the diploma.
window.__KENGURU_APIPAY_V6__ = true; // disables the old separate ApiPay patch

let uiLang='kk', token=localStorage.getItem('kng_token')||'',
    timerId=null, payPoll=null, left=1800, currentTest=null;

const T={
kk:{
brandSub:'Математика · 1–11 сынып',about:'Конкурс туралы',join:'Қатысу',results:'Марапат',org:'Ұйымдастырушы панелі',
kicker:'1–11 СЫНЫП ОҚУШЫЛАРЫНА АРНАЛҒАН',title2:'МАТЕМАТИКАЛЫҚ ОЙЫН-КОНКУРСЫ',
lead:'Стандартты емес есептер, логикалық пайымдау, заңдылық, геометрия, комбинаторика және кеңістіктік ойлау. Әр сыныпқа жеке тапсырмалар.',
qword:'сұрақ',minword:'минут',gradeword:'сынып',start:'Қатысуға өтінім беру',details:'Толығырақ',fee:'қатысу жарнасы',
s1:'Тіркелу',s2:'Төлем',s3:'Олимпиада',s4:'Диплом',format:'КОНКУРС ФОРМАТЫ',how:'Қалай өтеді?',
howText:'Оқушы өз сыныбын және тілін таңдайды. Төлем расталғаннан кейін 30 минуттық бір мүмкіндік ашылады. Сұрақтар автоматты араластырылады.',
c1t:'Тіркелу',c1p:'Оқушы туралы деректер дипломға дәл осы түрде түседі.',c2t:'1000 ₸ төлем',
c2p:'Тіркелгеннен кейін жеке ApiPay/Kaspi төлем шоты жасалады.',c3t:'30 тапсырма',c3p:'Үш күрделілік блогы.',
c4t:'Нәтиже',c4p:'Жүйе жауаптарды тексеріп, орын мен атаулы дипломды береді.',
d1:'бастапқы күрделі деңгей',d2:'орта күрделі деңгей',d3:'жоғары логикалық деңгей',
awardSmall:'НӘТИЖЕ',awardTitle:'Марапаттау шкаласы',awardText:'Нәтиже дұрыс жауаптар саны бойынша есептеледі. Бір қатысушыға бір мүмкіндік беріледі.',
a1:'I орын',a2:'II орын',a3:'III орын',a4:'Қатысушы сертификаты',regSmall:'ҚАТЫСУ',regTitle:'Қатысушы өтінімі',
regText:'Деректер дипломға автоматты түрде түседі. Аты-жөні мен мектеп атауын мұқият тексеріңіз.',
oneAttempt:'1 мүмкіндік',oneAttemptText:'Тест басталғаннан кейін таймер серверде де есептеледі.',
language:'Олимпиада тілі',grade:'Сынып',name:'Оқушының аты-жөні толық',phone:'Ата-ананың телефон нөмірі',
region:'Облыс / қала',locality:'Елді мекен',school:'Мектеп / білім беру ұйымы',supervisor:'Жетекшінің аты-жөні толық',
consent:'Олимпиадаға қатысу және диплом рәсімдеу үшін дербес деректерді өңдеуге келісемін.',
toPay:'Төлемге өту — 1000 ₸',payTitle:'Қатысу жарнасын төлеңіз — 1000 ₸',
payText:'Жеке QR-код арқылы төлеңіз. Төлем расталған соң тест автоматты түрде ашылады.',
openKaspi:'Kaspi арқылы төлеу',iPaid:'Төлемді тексеру',waitTitle:'Төлем тексерілуде',
waitText:'Төлем расталғаннан кейін тест автоматты түрде ашылады.',refresh:'Жаңарту',
testRule:'Әр сұрақта бір дұрыс жауап бар.',finish:'Тестті аяқтау',yourScore:'Сіздің нәтижеңіз',
printDiploma:'Дипломды сақтау / басып шығару',footText:'1–11 сынып оқушыларына арналған математикалық ойын-конкурс'
},
ru:{
brandSub:'Математика · 1–11 классы',about:'О конкурсе',join:'Участвовать',results:'Награды',org:'Панель организатора',
kicker:'ДЛЯ УЧАЩИХСЯ 1–11 КЛАССОВ',title2:'МАТЕМАТИЧЕСКИЙ ИГРОВОЙ КОНКУРС',
lead:'Нестандартные задачи, логические рассуждения, закономерности, геометрия, комбинаторика и пространственное мышление. Для каждого класса — отдельные задания.',
qword:'вопросов',minword:'минут',gradeword:'классы',start:'Подать заявку',details:'Подробнее',fee:'взнос за участие',
s1:'Регистрация',s2:'Оплата',s3:'Олимпиада',s4:'Диплом',format:'ФОРМАТ КОНКУРСА',how:'Как проходит?',
howText:'Ученик выбирает класс и язык. После подтверждения оплаты открывается одна попытка на 30 минут.',
c1t:'Регистрация',c1p:'Данные ученика в точности переносятся в диплом.',c2t:'Оплата 1000 ₸',
c2p:'После регистрации создаётся индивидуальный счёт ApiPay/Kaspi.',c3t:'30 заданий',c3p:'Три блока сложности.',
c4t:'Результат',c4p:'Система проверяет ответы и выдаёт место и именной диплом.',
d1:'первый сложный уровень',d2:'средний сложный уровень',d3:'высокий логический уровень',
awardSmall:'РЕЗУЛЬТАТ',awardTitle:'Шкала награждения',awardText:'Результат считается по числу правильных ответов. Один участник получает одну попытку.',
a1:'I место',a2:'II место',a3:'III место',a4:'Сертификат участника',regSmall:'УЧАСТИЕ',regTitle:'Заявка участника',
regText:'Данные автоматически попадут в диплом. Внимательно проверьте ФИО и название школы.',
oneAttempt:'1 попытка',oneAttemptText:'После старта таймер учитывается также на сервере.',
language:'Язык олимпиады',grade:'Класс',name:'ФИО ученика полностью',phone:'Телефон родителя',
region:'Область / город',locality:'Населённый пункт',school:'Школа / организация образования',supervisor:'ФИО руководителя полностью',
consent:'Согласен(на) на обработку персональных данных для участия и оформления диплома.',
toPay:'Перейти к оплате — 1000 ₸',payTitle:'Оплатите участие — 1000 ₸',
payText:'Оплатите по индивидуальному QR. После подтверждения оплаты тест откроется автоматически.',
openKaspi:'Оплатить через Kaspi',iPaid:'Проверить оплату',waitTitle:'Оплата проверяется',
waitText:'После подтверждения оплаты тест откроется автоматически.',refresh:'Обновить',
testRule:'В каждом вопросе один правильный ответ.',finish:'Завершить тест',yourScore:'Ваш результат',
printDiploma:'Сохранить / распечатать диплом',footText:'математический игровой конкурс для учащихся 1–11 классов'
}};

const regionsKK=['Астана қ.','Алматы қ.','Шымкент қ.','Абай облысы','Ақмола облысы','Ақтөбе облысы','Алматы облысы','Атырау облысы','Шығыс Қазақстан облысы','Жамбыл облысы','Жетісу облысы','Батыс Қазақстан облысы','Қарағанды облысы','Қостанай облысы','Қызылорда облысы','Маңғыстау облысы','Павлодар облысы','Солтүстік Қазақстан облысы','Түркістан облысы','Ұлытау облысы'];
const regionsRU=['г. Астана','г. Алматы','г. Шымкент','область Абай','Акмолинская область','Актюбинская область','Алматинская область','Атырауская область','Восточно-Казахстанская область','Жамбылская область','область Жетісу','Западно-Казахстанская область','Карагандинская область','Костанайская область','Кызылординская область','Мангистауская область','Павлодарская область','Северо-Казахстанская область','Туркестанская область','область Ұлытау'];

function byId(id){return document.getElementById(id)}
function fillSelects(){
  let oldGrade=byId('grade').value||'1';
  byId('grade').innerHTML='';
  for(let i=1;i<=11;i++){
    let o=document.createElement('option');o.value=i;o.textContent=i+(uiLang==='kk'?' сынып':' класс');byId('grade').appendChild(o)
  }
  byId('grade').value=oldGrade;
  let oldRegion=byId('region').selectedIndex;
  byId('region').innerHTML='';
  (uiLang==='kk'?regionsKK:regionsRU).forEach((x,i)=>{
    let o=document.createElement('option');o.value=regionsKK[i];o.textContent=x;byId('region').appendChild(o)
  });
  if(oldRegion>=0)byId('region').selectedIndex=oldRegion
}
function applyLang(){
  document.documentElement.lang=uiLang;
  document.querySelectorAll('[data-i18n]').forEach(e=>{let k=e.dataset.i18n;if(T[uiLang][k])e.textContent=T[uiLang][k]});
  byId('langBtn').textContent=uiLang==='kk'?'РУС':'ҚАЗ';
  if(byId('lang'))byId('lang').value=uiLang;
  fillSelects()
}
function toggleLang(){uiLang=uiLang==='kk'?'ru':'kk';applyLang()}
function showOnly(id){
  ['regCard','payCard','waitCard','testCard','resultCard'].forEach(x=>byId(x).classList.toggle('hidden',x!==id));
  document.getElementById('reg').scrollIntoView({behavior:'smooth'})
}

function paymentNodes(){
  const card=byId('payCard');
  return {
    card,
    img:card?card.querySelector('.payBox img'):null,
    link:card?card.querySelector('.payBox a'):null,
    btn:byId('paidBtn')
  };
}
function paymentLoading(){
  const p=paymentNodes();
  if(p.img){p.img.removeAttribute('src');p.img.alt='ApiPay QR';p.img.style.minHeight='220px'}
  if(p.link){p.link.removeAttribute('href');p.link.textContent=uiLang==='kk'?'ApiPay шоты жасалуда…':'Создаём счёт ApiPay…'}
  if(p.btn)p.btn.textContent=T[uiLang].iPaid;
}
function showInvoice(x){
  const p=paymentNodes();
  if(p.img && x.qr_image_url){p.img.src=x.qr_image_url;p.img.style.minHeight=''}
  if(p.link){
    if(x.qr_token_url){p.link.href=x.qr_token_url;p.link.target='_blank';p.link.rel='noopener'}
    else p.link.removeAttribute('href');
    p.link.textContent=T[uiLang].openKaspi;
  }
  if(p.btn)p.btn.textContent=T[uiLang].iPaid;
  try{localStorage.setItem('kng_invoice_'+token,JSON.stringify(x))}catch(e){}
}
async function createInvoice(){
  if(!token)return;
  paymentLoading();
  let r;
  try{
    r=await fetch('/api/apipay/create/'+encodeURIComponent(token),{method:'POST',cache:'no-store'});
  }catch(e){
    alert((uiLang==='kk'?'ApiPay қатесі: ':'Ошибка ApiPay: ')+e.message);return
  }
  if(!r.ok){
    let msg=await r.text();
    alert((uiLang==='kk'?'ApiPay қатесі: ':'Ошибка ApiPay: ')+msg);return
  }
  let x=await r.json();
  if(x.paid){await checkStatus();return}
  if(!x.invoice_id){
    alert(uiLang==='kk'?'ApiPay шот нөмірін қайтармады':'ApiPay не вернул номер счёта');return
  }
  showInvoice(x);
  startPaymentPoll();
}
function startPaymentPoll(){
  if(payPoll)clearInterval(payPoll);
  payPoll=setInterval(checkStatus,3000);
  checkStatus()
}

byId('langBtn').addEventListener('click',toggleLang);
byId('lang').addEventListener('change',e=>{uiLang=e.target.value;applyLang()});

byId('regForm').addEventListener('submit',async e=>{
  e.preventDefault();
  let data={
    lang:byId('lang').value,full_name:byId('full_name').value.trim(),phone:byId('phone').value.trim(),
    region:byId('region').value,locality:byId('locality').value.trim(),school:byId('school').value.trim(),
    supervisor:byId('supervisor').value.trim(),
    grade:+byId('grade').value
  };
  let r=await fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  if(!r.ok){alert(uiLang==='kk'?'Өтінімді сақтау мүмкін болмады':'Не удалось сохранить заявку');return}
  let j=await r.json();
  token=j.token;
  localStorage.setItem('kng_token',token);
  showOnly('payCard');
  await createInvoice();
});

byId('paidBtn').addEventListener('click',checkStatus);
byId('refreshBtn').addEventListener('click',checkStatus);
byId('finishBtn').addEventListener('click',()=>{if(confirm(uiLang==='kk'?'Тестті аяқтайсыз ба?':'Завершить тест?'))submitTest()});
byId('printBtn').addEventListener('click',()=>window.print());

async function checkStatus(){
  if(!token)return;
  let r=await fetch('/api/status/'+encodeURIComponent(token),{cache:'no-store'});
  if(!r.ok){localStorage.removeItem('kng_token');token='';return}
  let s=await r.json();
  uiLang=s.lang||uiLang;applyLang();
  if(s.submitted_at){if(payPoll)clearInterval(payPoll);showResult(s);return}
  if(s.payment_status==='paid'){
    if(payPoll)clearInterval(payPoll);
    showOnly('testCard');await loadTest()
  }else{
    showOnly('payCard');
    let cached=null;
    try{cached=JSON.parse(localStorage.getItem('kng_invoice_'+token)||'null')}catch(e){}
    if(cached)showInvoice(cached)
  }
}
async function loadTest(){
  if(currentTest)return;
  let r=await fetch('/api/test/'+encodeURIComponent(token));
  if(!r.ok){alert(await r.text());return}
  currentTest=await r.json();uiLang=currentTest.lang;applyLang();
  byId('who').textContent=currentTest.full_name+' · '+currentTest.grade+(uiLang==='kk'?' сынып':' класс');
  byId('testForm').innerHTML=currentTest.questions.map((q,i)=>`<div class="question"><div class="qmeta">${i+1}/30 · ${q.points} ${uiLang==='kk'?'балл деңгейі':'балла уровень'}</div><h3>${esc(q.text)}</h3><div class="opts">${q.options.map((o,k)=>`<label class="opt"><input type="radio" name="${q.id}" value="${escAttr(o)}"><b>${String.fromCharCode(65+k)})</b> ${esc(o)}</label>`).join('')}</div></div>`).join('');
  byId('testForm').addEventListener('change',updateProgress);
  left=Math.max(0,currentTest.seconds_left||1800);tick();
  timerId=setInterval(()=>{left--;tick();if(left<=0){clearInterval(timerId);submitTest()}},1000)
}
function updateProgress(){
  let n=new Set([...new FormData(byId('testForm')).keys()]).size;
  byId('progressBar').style.width=(n/30*100)+'%'
}
function tick(){byId('timer').textContent=String(Math.floor(left/60)).padStart(2,'0')+':'+String(left%60).padStart(2,'0')}
async function submitTest(){
  if(!currentTest)return;
  clearInterval(timerId);
  let answers={};new FormData(byId('testForm')).forEach((v,k)=>answers[k]=v);
  let r=await fetch('/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,answers})});
  if(!r.ok){alert(await r.text());return}
  let j=await r.json();
  let s=await (await fetch('/api/status/'+encodeURIComponent(token))).json();
  showResult({...s,...j})
}
function showResult(s){
  currentTest=null;clearInterval(timerId);if(payPoll)clearInterval(payPoll);
  showOnly('resultCard');uiLang=s.lang||uiLang;applyLang();
  const isCertificate=(s.award||'').includes('сертификаты');
  const place=(s.award||'').match(/^(I{1,3})/);
  byId('score').textContent=(s.score??0)+'/30';
  byId('award').textContent=localAward(s.award);
  byId('diplomaNo').textContent=s.diploma_no||'';
  byId('dipBg').src=isCertificate?'/static/certificate_template.png':'/static/diploma_template.png';
  byId('diploma').classList.toggle('certificate',isCertificate);
  byId('dipName').textContent=s.full_name||'';
  byId('dipSchool').textContent=s.school||'';
  byId('dipGrade').textContent=s.grade||'';
  byId('dipAward').textContent=place?place[1]:'';
  byId('dipSupervisor').textContent=s.supervisor?'Жетекшісі: '+s.supervisor:'';
  byId('dipNo').textContent='№ '+(s.diploma_no||'');
  byId('printBtn').textContent=isCertificate?(uiLang==='kk'?'Сертификатты сақтау / басып шығару':'Сохранить / распечатать сертификат'):(uiLang==='kk'?'Дипломды сақтау / басып шығару':'Сохранить / распечатать диплом')
}
function localAward(a){
  if(uiLang==='kk')return a||'';
  return {'I орын':'I место','II орын':'II место','III орын':'III место','Қатысушы сертификаты':'Сертификат участника'}[a]||a||''
}
function esc(x){return String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]))}
function escAttr(x){return esc(x)}

applyLang();
if(token){
  checkStatus().then(()=>{
    let cached=null;
    try{cached=JSON.parse(localStorage.getItem('kng_invoice_'+token)||'null')}catch(e){}
    if(cached){showInvoice(cached);startPaymentPoll()}
  })
}
console.log('[KENGURU] MAIN UI V8 + APIPAY ACTIVE');
