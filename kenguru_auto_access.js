// KENGURU_SELF_REPORT_10S_START_V2. The server, not the browser, grants access.
var KENGURU_ACCESS = {last:null, deadline:0, timer:null, retry:null, checking:null, marking:false, generation:0, resultKey:''};
function kenguruAutoSetText(){
  Object.assign(T.kk, {
    iPaid:'Төлем жасадым',
    payText:'Kaspi арқылы төлем жасағаннан кейін «Төлем жасадым» батырмасын басыңыз. Тестке рұқсат 10 секундтан кейін ашылады.',
    howText:'Оқушы сыныбы мен тілін таңдайды. «Төлем жасадым» батырмасынан кейін 10 секундта рұқсат ашылады. 30 минуттық тест тек «Тестті бастау» батырмасын басқанда басталады.',
    waitTitle:'Тестке рұқсат',
    waitText:'10 секундтан кейін рұқсат ашылады. Тестті өзіңіз дайын болған кезде «Тестті бастау» батырмасымен бастайсыз.'
  });
  Object.assign(T.ru, {
    iPaid:'Я оплатил(а)',
    payText:'После оплаты через Kaspi нажмите «Я оплатил(а)». Доступ к тесту откроется через 10 секунд.',
    howText:'Ученик выбирает класс и язык. Через 10 секунд после «Я оплатил(а)» открывается доступ. 30 минут начнутся только после нажатия «Начать тестирование».',
    waitTitle:'Доступ к тесту',
    waitText:'Через 10 секунд откроется доступ. Сам тест начнётся только когда вы нажмёте «Начать тестирование».'
  });
}
function kenguruAutoMessage(message){
  const card=['waitCard','payCard','regCard'].map(byId).find(x=>x&&!x.classList.contains('hidden'));
  if(!card)return;
  let el=card.querySelector('[data-access-error]');
  if(!el){el=document.createElement('p');el.dataset.accessError='1';el.setAttribute('role','alert');card.appendChild(el)}
  el.textContent=message;
}
function kenguruAutoClearTimers(){
  clearInterval(KENGURU_ACCESS.timer);clearTimeout(KENGURU_ACCESS.retry);
  KENGURU_ACCESS.timer=null;KENGURU_ACCESS.retry=null;
}
function kenguruAutoWaitButton(show){
  let b=byId('autoAccessMarkBtn');
  if(!b&&show){
    b=document.createElement('button');b.id='autoAccessMarkBtn';b.type='button';b.className='btn primary';
    b.addEventListener('click',()=>markPaid());byId('waitCard').appendChild(b);
  }
  if(b){b.hidden=!show;b.classList.toggle('hidden',!show);b.textContent=uiLang==='kk'?'Төлем жасадым':'Я оплатил(а)';b.disabled=KENGURU_ACCESS.marking}
}

function kenguruAutoStartButton(show){
  let b=byId('autoStartTestBtn');
  if(!b&&show){
    b=document.createElement('button');b.id='autoStartTestBtn';b.type='button';b.className='btn primary';
    b.addEventListener('click',async()=>{
      if(b.disabled)return;
      b.disabled=true;
      showOnly('testCard');
      try{await loadTest()}
      finally{b.disabled=false}
    });
    byId('waitCard').appendChild(b);
  }
  if(b){
    b.hidden=!show;b.classList.toggle('hidden',!show);
    b.textContent=uiLang==='kk'?'Тестті бастау':'Начать тестирование';
  }
}
function kenguruAutoRefreshText(){
  const s=KENGURU_ACCESS.last;
  if(!s||s.token!==token)return;
  if((s.test_access===true||s.payment_status==='paid')&&!s.started_at){
    const el=byId('payStatus');if(el)el.textContent=uiLang==='kk'?'Рұқсат ашылды. Дайын болғанда «Тестті бастау» батырмасын басыңыз.':'Доступ открыт. Когда будете готовы, нажмите «Начать тестирование».';
    kenguruAutoWaitButton(false);kenguruAutoStartButton(true);
  }else if(s.auto_access_pending){
    const seconds=Math.max(0,Math.ceil((KENGURU_ACCESS.deadline-performance.now())/1000));
    const label=seconds>0?(uiLang==='kk'?'Тест '+seconds+' секундтан кейін ашылады':'Тест откроется через '+seconds+' с'):
      (uiLang==='kk'?'Рұқсатты серверден тексеріп жатырмыз…':'Проверяем доступ на сервере…');
    const el=byId('payStatus');if(el&&el.textContent!==label)el.textContent=label;
  }else if(!s.test_access&&!s.submitted_at){
    const el=byId('payStatus');if(el)el.textContent=uiLang==='kk'?'Төлем жасағаннан кейін төмендегі батырманы басыңыз':'После оплаты нажмите кнопку ниже';
    kenguruAutoWaitButton(s.payment_status==='pending');
  }
}
async function kenguruAutoFetch(url,options){
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),15000);
  try{
    const r=await fetch(url,Object.assign({cache:'no-store'},options||{},{signal:controller.signal}));
    if(!r.ok){const e=new Error('HTTP '+r.status);e.status=r.status;throw e}
    return await r.json();
  }finally{clearTimeout(timeout)}
}
async function kenguruAutoApply(s){
  if(s.token!==token)return;
  kenguruAutoClearTimers();
  KENGURU_ACCESS.last=s;
  KENGURU_ACCESS.deadline=performance.now()+Math.max(0,Number(s.auto_access_remaining_ms)||0);
  uiLang=s.lang||uiLang;applyLang();
  document.querySelectorAll('[data-access-error]').forEach(x=>x.textContent='');
  if(s.submitted_at){
    const key=s.token+'|'+s.submitted_at+'|'+s.diploma_no;
    if(KENGURU_ACCESS.resultKey!==key){KENGURU_ACCESS.resultKey=key;showResult(s)}
    return;
  }
  if(s.test_access===true||s.payment_status==='paid'){
    kenguruAutoWaitButton(false);
    if(s.started_at){
      kenguruAutoStartButton(false);
      showOnly('testCard');
      if(!currentTest){
        try{await loadTest()}catch(e){
          if(typeof testLoading!=='undefined')testLoading=false;
          KENGURU_ACCESS.retry=setTimeout(()=>checkStatus(),2500);
        }
      }
    }else{
      showOnly('waitCard');
      kenguruAutoStartButton(true);
      kenguruAutoRefreshText();
    }
    return;
  }
  if(s.auto_access_pending){
    showOnly('waitCard');kenguruAutoWaitButton(false);kenguruAutoStartButton(false);kenguruAutoRefreshText();
    const activeToken=token;
    KENGURU_ACCESS.timer=setInterval(()=>{
      if(token!==activeToken){kenguruAutoClearTimers();return}
      kenguruAutoRefreshText();
      if(performance.now()>=KENGURU_ACCESS.deadline){
        clearInterval(KENGURU_ACCESS.timer);KENGURU_ACCESS.timer=null;
        void checkStatus();
      }
    },200);
  }else{
    kenguruAutoStartButton(false);
    showOnly(s.payment_status==='pending'?'waitCard':'payCard');
    kenguruAutoWaitButton(s.payment_status==='pending');
    kenguruAutoRefreshText();
  }
}
async function kenguruAutoMarkPaid(){
  if(!token||KENGURU_ACCESS.marking)return;
  const activeToken=token;
  KENGURU_ACCESS.marking=true;KENGURU_ACCESS.generation++;
  [byId('paidBtn'),byId('autoAccessMarkBtn')].filter(Boolean).forEach(b=>b.disabled=true);
  try{
    const s=await kenguruAutoFetch('/api/payment-mark',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:activeToken})});
    if(token===activeToken){KENGURU_ACCESS.generation++;await kenguruAutoApply(s);}
  }catch(e){
    kenguruAutoMessage(uiLang==='kk'?'Сервермен байланыс үзілді. Өтінім мәртебесін қайта тексереміз.':'Связь с сервером прервана. Проверяем сохранённый статус заявки.');
    // A timed-out POST may already be committed. A status read cannot restart it.
    if(token===activeToken)void checkStatus();
  }finally{
    KENGURU_ACCESS.marking=false;
    [byId('paidBtn'),byId('autoAccessMarkBtn')].filter(Boolean).forEach(b=>b.disabled=false);
  }
}
async function kenguruAutoCheckStatus(){
  if(!token)return;
  if(KENGURU_ACCESS.checking)return KENGURU_ACCESS.checking;
  const activeToken=token;
  const generation=KENGURU_ACCESS.generation;
  KENGURU_ACCESS.checking=(async()=>{
    try{
      const s=await kenguruAutoFetch('/api/status/'+encodeURIComponent(activeToken));
      if(token===activeToken&&generation===KENGURU_ACCESS.generation)await kenguruAutoApply(s);
    }catch(e){
      if(token!==activeToken||generation!==KENGURU_ACCESS.generation)return;
      if(e.status===404){
        kenguruAutoClearTimers();KENGURU_ACCESS.last=null;token='';
        try{localStorage.removeItem('kng_token')}catch(ignore){}
        showOnly('regCard');
      }else{
        // Never erase the participant token or restart a countdown on 5xx/offline.
        kenguruAutoMessage(uiLang==='kk'?'Байланыс уақытша үзілді. Рұқсат серверде сақталады.':'Связь временно прервана. Доступ сохраняется на сервере.');
        clearTimeout(KENGURU_ACCESS.retry);
        KENGURU_ACCESS.retry=setTimeout(()=>checkStatus(),2500);
      }
    }finally{KENGURU_ACCESS.checking=null}
  })();
  return KENGURU_ACCESS.checking;
}
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='visible'&&typeof token!=='undefined'&&token&&!currentTest)void checkStatus();
});
window.addEventListener('pageshow',e=>{
  if(e.persisted&&typeof token!=='undefined'&&token&&!currentTest)void checkStatus();
});

// KENGURU_REGISTRATION_ERRORS_V1 — no payment, attempt or database changes.
(function () {
  'use strict';
  if (window.KENGURU_REGISTRATION_FIX_VERSION) return;
  window.KENGURU_REGISTRATION_FIX_VERSION = 'field-errors-20260927';
  const limits = {full_name:[3,120],phone:[7,30],region:[2,100],locality:[2,100],school:[2,180],supervisor:[3,120]};
  const labels = {
    ru:{lang:'Язык олимпиады',grade:'Класс',full_name:'ФИО ученика',phone:'Телефон родителя',region:'Область / город',locality:'Населённый пункт',school:'Школа / организация образования',supervisor:'ФИО руководителя',consent:'Согласие на обработку данных'},
    kk:{lang:'Олимпиада тілі',grade:'Сынып',full_name:'Оқушының аты-жөні',phone:'Ата-ананың телефоны',region:'Облыс / қала',locality:'Елді мекен',school:'Мектеп / білім беру ұйымы',supervisor:'Жетекшінің аты-жөні',consent:'Деректерді өңдеуге келісім'}
  };
  let form, busy=false, errors=[], notice='';
  function lang(){return typeof uiLang !== 'undefined' && uiLang==='ru'?'ru':'kk'}
  function el(id){return document.getElementById(id)}
  function count(value){return Array.from(String(value==null?'':value)).length}
  function read(){
    const data={};
    for(const id of Object.keys(limits)) data[id]=(el(id)?.value||'').trim();
    data.lang=el('lang')?.value||'';
    data.grade=Number(el('grade')?.value||0);
    return data;
  }
  function validate(data){
    const out=[];
    if(!['kk','ru'].includes(data.lang))out.push({field:'lang',kind:'choice'});
    if(!Number.isInteger(data.grade)||data.grade<1||data.grade>11)out.push({field:'grade',kind:'choice'});
    for(const [field,[min,max]] of Object.entries(limits)){
      const length=count(data[field]);
      if(length===0)out.push({field,kind:'required'});
      else if(length<min)out.push({field,kind:'short',min,length});
      else if(length>max)out.push({field,kind:'long',max,length});
    }
    if(!el('consent')?.checked)out.push({field:'consent',kind:'required'});
    return out;
  }
  function message(error){
    const ru=lang()==='ru', name=labels[lang()][error.field]|| (ru?'Заявка':'Өтінім');
    if(error.field==='consent')return ru?'Отметьте согласие на обработку данных.':'Деректерді өңдеуге келісімді белгілеңіз.';
    if(error.kind==='short')return ru?`${name}: нужно не менее ${error.min} символов. Введено: ${error.length}.`:`${name}: кемінде ${error.min} таңба қажет. Енгізілгені: ${error.length}.`;
    if(error.kind==='long')return ru?`${name}: максимум ${error.max} символов. Введено: ${error.length}. Текст не обрезан.`:`${name}: ең көбі ${error.max} таңба. Енгізілгені: ${error.length}. Мәтін қысқартылған жоқ.`;
    if(error.kind==='required')return ru?`Заполните поле «${name}».`:`«${name}» жолын толтырыңыз.`;
    if(error.field==='grade')return ru?'Выберите класс от 1 до 11.':'1–11 аралығындағы сыныпты таңдаңыз.';
    if(error.field==='lang')return ru?'Выберите русский или казахский язык.':'Қазақ немесе орыс тілін таңдаңыз.';
    return ru?`Проверьте поле «${name}».`:`«${name}» жолын тексеріңіз.`;
  }
  function noticeText(){
    const ru=lang()==='ru';
    const all={
      validation:ru?'Проверьте выделенные поля. Введённые данные остались в форме.':'Белгіленген жолдарды тексеріңіз. Енгізілген деректер формада сақталды.',
      server:ru?'Сервер временно не смог обработать заявку. Данные не удалены. Обратитесь к организатору, если ошибка повторяется.':'Сервер өтінімді уақытша өңдей алмады. Деректер өшірілген жоқ. Қате қайталанса, ұйымдастырушыға хабарласыңыз.',
      network:ru?'Не удалось получить ответ сервера. Данные остались в форме. Заявка могла сохраниться: перед повторной отправкой уточните это у организатора.':'Серверден жауап алынбады. Деректер формада сақталды. Өтінім сақталуы мүмкін: қайта жіберер алдында ұйымдастырушыдан нақтылаңыз.',
      rate:ru?'Слишком много запросов. Подождите немного перед повторной отправкой.':'Сұраулар тым көп. Қайта жібермес бұрын аздап күтіңіз.',
      unknown:ru?'Сервер отклонил заявку. Проверьте заполнение полей. Данные не удалены; при повторении отправьте организатору скриншот всех полей, кроме телефона.':'Сервер өтінімді қабылдамады. Жолдарды тексеріңіз. Деректер өшірілген жоқ; қате қайталанса, телефоннан басқа жолдардың скриншотын ұйымдастырушыға жіберіңіз.'
    };
    return all[notice]||'';
  }
  function render(focus){
    if(!form)return;
    form.querySelectorAll('[data-registration-error-for]').forEach(x=>x.remove());
    for(const id of Object.keys(labels.kk)){
      const input=el(id);if(!input)continue;
      input.classList.remove('kreg-invalid');input.removeAttribute('aria-invalid');
      const described=(input.getAttribute('aria-describedby')||'').split(/\s+/).filter(x=>x&&x!==id+'-registration-error');
      if(described.length)input.setAttribute('aria-describedby',described.join(' '));else input.removeAttribute('aria-describedby');
    }
    let box=el('registrationMessage');
    if(!box){box=document.createElement('p');box.id='registrationMessage';box.className='wide kreg-message';box.setAttribute('role','alert');form.prepend(box)}
    box.textContent=noticeText();box.hidden=!notice;
    for(const error of errors){
      const input=el(error.field);if(!input)continue;
      input.classList.add('kreg-invalid');input.setAttribute('aria-invalid','true');
      const help=document.createElement('small');help.id=error.field+'-registration-error';help.className='kreg-error';help.dataset.registrationErrorFor=error.field;help.textContent=message(error);
      input.parentElement.appendChild(help);
      input.setAttribute('aria-describedby',((input.getAttribute('aria-describedby')||'')+' '+help.id).trim());
    }
    const button=form.querySelector('button[type="submit"]');
    if(button){button.disabled=busy;button.textContent=busy?(lang()==='ru'?'Сохраняем заявку…':'Өтінім сақталуда…'):(typeof T!=='undefined'?T[lang()].toPay:button.textContent)}
    if(focus){const first=el(errors[0]?.field);(first||box).scrollIntoView({block:'center',behavior:'smooth'});if(first)first.focus({preventScroll:true})}
  }
  function serverErrors(payload,data){
    if(!Array.isArray(payload?.detail))return [];
    const found=[];
    for(const item of payload.detail){
      const field=Array.isArray(item.loc)?item.loc.find(x=>Object.hasOwn(labels.kk,x)):null;
      if(!field||found.some(x=>x.field===field))continue;
      const length=count(data[field]);const ctx=item.ctx||{};
      if(item.type==='string_too_short')found.push({field,kind:'short',min:Number(ctx.min_length)||limits[field]?.[0]||1,length});
      else if(item.type==='string_too_long')found.push({field,kind:'long',max:Number(ctx.max_length)||limits[field]?.[1]||0,length});
      else found.push({field,kind:item.type==='missing'?'required':'choice'});
    }
    return found;
  }
  async function submitRegistration(){
    if(busy)return;
    const data=read();errors=validate(data);notice=errors.length?'validation':'';render(!!errors.length);
    if(errors.length)return;
    busy=true;render(false);
    const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),30000);
    try{
      const response=await fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:controller.signal,cache:'no-store'});
      let payload=null;try{payload=await response.json()}catch(ignore){}
      if(!response.ok){
        errors=serverErrors(payload,data);
        notice=errors.length?'validation':response.status===429?'rate':response.status>=500?'server':'unknown';
        render(true);return;
      }
      if(!payload||typeof payload.token!=='string'||!payload.token){notice='network';render(true);return}
      token=payload.token;
      let persisted=true;try{localStorage.setItem('kng_token',token)}catch(ignore){persisted=false}
      errors=[];notice='';render(false);
      showOnly('payCard'); // Registration is not payment confirmation and never starts a test.
      if(!persisted && typeof kenguruAutoMessage==='function')kenguruAutoMessage(lang()==='ru'?'Заявка сохранена. Браузер не разрешает запомнить вход: пока не закрывайте эту вкладку.':'Өтінім сақталды. Браузер кіруді есте сақтауға рұқсат бермеді: бұл бетті әзірге жаппаңыз.');
    }catch(error){notice='network';render(true)}
    finally{clearTimeout(timeout);busy=false;render(false)}
  }
  function init(){
    form=el('regForm');if(!form)return;
    form.noValidate=true; // Show the server's actual field rules instead of a generic alert.
    const style=document.createElement('style');style.textContent='.kreg-invalid{outline:2px solid #b42318!important;outline-offset:2px}.kreg-error{display:block;color:#b42318;line-height:1.4;margin-top:8px;font-weight:600}.kreg-message{padding:12px;border:1px solid #fda29b;border-radius:10px;background:#fff4f2;color:#912018;line-height:1.5}.kreg-message[hidden]{display:none}';document.head.appendChild(style);
    document.addEventListener('submit',event=>{
      if(event.target!==form)return;
      event.preventDefault();event.stopImmediatePropagation();void submitRegistration();
    },true);
    form.addEventListener('input',event=>{
      if(!errors.some(x=>x.field===event.target.id))return;
      errors=errors.filter(x=>x.field!==event.target.id);if(!errors.length&&notice==='validation')notice='';render(false);
    });
    new MutationObserver(()=>render(false)).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
