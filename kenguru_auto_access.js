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
