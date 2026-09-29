// KENGURU_FAMILY_DEVICE_V1. Existing participant records are never reset.
var KFAMILY={prefix:'kng_family_child_v1_',activeKey:'kng_family_active_v1',
  freshKey:'kng_family_new_form_v1',busy:false,ready:false,memory:Object.create(null),
  storageWarning:false,messageKey:'',renderQueued:false};
function kfText(kk,ru){return typeof uiLang!=='undefined'&&uiLang==='ru'?ru:kk}
function kfValid(t){return typeof t==='string'&&/^[A-Za-z0-9_-]{10,160}$/.test(t)}
function kfInitialToken(){
  // An explicit empty value means "new child". Do not fall back to another tab.
  try{var active=sessionStorage.getItem(KFAMILY.activeKey);if(active!==null)return kfValid(active)?active:''}catch(e){}
  var prior='';try{prior=localStorage.getItem('kng_token')||''}catch(e){}
  if(!kfValid(prior))prior='';
  try{sessionStorage.setItem(KFAMILY.activeKey,prior)}catch(e){}
  return prior;
}
function kfRecords(){
  var out=Object.assign(Object.create(null),KFAMILY.memory);
  try{
    for(var i=0;i<localStorage.length;i++){
      var key=localStorage.key(i);if(!key||!key.startsWith(KFAMILY.prefix))continue;
      try{var p=JSON.parse(localStorage.getItem(key));
        if(p&&kfValid(p.token)&&key===KFAMILY.prefix+p.token)out[p.token]=p;
      }catch(e){}
    }
  }catch(e){KFAMILY.storageWarning=true}
  return Object.values(out).sort((a,b)=>(b.seen||0)-(a.seen||0));
}
function kfStore(p){
  if(!p||!kfValid(p.token))return false;
  var old=KFAMILY.memory[p.token]||{};
  try{old=JSON.parse(localStorage.getItem(KFAMILY.prefix+p.token)||'null')||old}catch(e){}
  var item={token:p.token,full_name:typeof p.full_name==='string'?p.full_name.slice(0,120):(old.full_name||''),
    grade:Number.isInteger(p.grade)&&p.grade>=1&&p.grade<=11?p.grade:(old.grade||null),
    done:!!p.submitted_at||!!old.done,seen:Date.now()};
  KFAMILY.memory[p.token]=item;
  try{var raw=JSON.stringify(item);localStorage.setItem(KFAMILY.prefix+p.token,raw);
    if(localStorage.getItem(KFAMILY.prefix+p.token)!==raw)throw Error('Storage not confirmed');
    return true;
  }catch(e){KFAMILY.storageWarning=true;return false}
}
function kfRemember(p){
  kfStore(p);kfQueueRender();
}
function kfRegistered(t,data){
  // Called only after the registration API returns the new independent token.
  try{sessionStorage.setItem(KFAMILY.activeKey,t)}catch(e){KFAMILY.storageWarning=true}
  kfRemember(Object.assign({},data,{token:t}));
}
function kfMissingActive(){
  try{sessionStorage.setItem(KFAMILY.activeKey,'')}catch(e){}
  kfQueueRender();
}
function kfQueueRender(){
  if(!KFAMILY.ready||KFAMILY.renderQueued)return;
  KFAMILY.renderQueued=true;
  queueMicrotask(()=>{KFAMILY.renderQueued=false;kfRender()});
}
function kfMessage(key){KFAMILY.messageKey=key;kfQueueRender()}
function kfMessageText(){
  var key=KFAMILY.messageKey;
  if(key==='checking')return kfText('Қатысушының күйі тексерілуде…','Проверяем состояние участника…');
  if(key==='busy')return kfText('Қазіргі әрекет аяқталғанша күтіңіз.','Дождитесь завершения текущей отправки или загрузки.');
  if(key==='active')return kfText('Алдымен қазіргі тестті аяқтаңыз. Қатысушыны ауыстыру таймерді тоқтатпайды.',
    'Сначала завершите текущий тест. Переключение участника не останавливает таймер.');
  if(key==='network')return kfText('Сервермен байланыс орнамады. Қатысушы ауыстырылған жоқ. Қайта басып көріңіз.',
    'Не удалось проверить состояние на сервере. Участник не переключён. Повторите попытку.');
  if(key==='storage')return kfText('Браузер кіруді сақтауға рұқсат бермейді. Алғашқы қатысушының кіруін жоғалтпау үшін ауыстыру тоқтатылды.',
    'Браузер не разрешает сохранить вход. Переключение отменено, чтобы не потерять доступ к первому участнику.');
  return '';
}
function kfWorkInFlight(){
  var form=document.getElementById('regForm'),b=form&&form.querySelector('button[type="submit"]');
  if(b&&b.disabled)return true;
  if(typeof KTEST!=='undefined'&&(KTEST.loading||KTEST.saving||KTEST.finishing||KTEST.pendingFinish||KTEST.syncing))return true;
  if(typeof KENGURU_ACCESS!=='undefined'&&(KENGURU_ACCESS.marking||KENGURU_ACCESS.checking))return true;
  return false;
}
async function kfReadStatus(t){
  var c=new AbortController(),timer=setTimeout(()=>c.abort(),15000);
  try{
    var r=await fetch('/api/status/'+encodeURIComponent(t),{cache:'no-store',credentials:'same-origin',signal:c.signal});
    if(!r.ok)throw Error('Status unavailable');
    var p=await r.json();if(!p||p.token!==t)throw Error('Participant mismatch');return p;
  }finally{clearTimeout(timer)}
}
async function kfIsReview(t){
  var c=new AbortController(),timer=setTimeout(()=>c.abort(),15000);
  try{
    var r=await fetch('/api/test/state/'+encodeURIComponent(t),{cache:'no-store',credentials:'same-origin',signal:c.signal});
    if(r.status!==200&&r.status!==409)throw Error('State unavailable');
    var p=await r.json();if(r.status===409)p=p.detail;
    if(!p||p.token!==t)throw Error('Participant mismatch');
    return p.status==='review_required'||p.status==='submitted';
  }finally{clearTimeout(timer)}
}
function kfHasDraftForm(){
  var form=document.getElementById('regForm');if(!form)return false;
  return ['full_name','phone','locality','school','supervisor'].some(id=>{
    var x=document.getElementById(id);return !!(x&&x.value.trim());
  });
}
function kfWriteSelection(next){
  var priorSession=sessionStorage.getItem(KFAMILY.activeKey),priorLast=localStorage.getItem('kng_token');
  try{
    sessionStorage.setItem(KFAMILY.activeKey,next);
    if(sessionStorage.getItem(KFAMILY.activeKey)!==next)throw Error('Tab storage unavailable');
    if(next)localStorage.setItem('kng_token',next);else localStorage.removeItem('kng_token');
    if((localStorage.getItem('kng_token')||'')!==next)throw Error('Storage unavailable');
    if(!next)sessionStorage.setItem(KFAMILY.freshKey,'1');
  }catch(e){
    try{if(priorSession===null)sessionStorage.removeItem(KFAMILY.activeKey);else sessionStorage.setItem(KFAMILY.activeKey,priorSession)}catch(ignore){}
    try{if(priorLast===null)localStorage.removeItem('kng_token');else localStorage.setItem('kng_token',priorLast)}catch(ignore){}
    throw e;
  }
}
function kfReload(){window.location.reload()}
async function kfSwitch(next){
  next=next||'';
  if(KFAMILY.busy)return;
  if(next&&!kfRecords().some(p=>p.token===next))return;
  var active=typeof token==='string'?token:'';
  if(next===active)return;
  if(kfWorkInFlight()){kfMessage('busy');return}
  if(!active&&kfHasDraftForm()&&!confirm(kfText('Енгізілген жаңа өтінім әлі жіберілмеген. Сақталған қатысушыға өту керек пе?',
    'Новая заявка ещё не отправлена. Перейти к сохранённому участнику и очистить незаполненную заявку?')))return;
  KFAMILY.busy=true;kfMessage('checking');kfRender();
  var navigating=false;
  try{
    if(active){
      var p=await kfReadStatus(active);
      if(token!==active||kfWorkInFlight()){kfMessage('busy');return}
      if(p.started_at&&!p.submitted_at){
        if(!(await kfIsReview(active))){kfMessage('active');return}
      }
      if(token!==active||kfWorkInFlight()){kfMessage('busy');return}
      if(!kfStore(p)){kfMessage('storage');return}
    }
    try{kfWriteSelection(next)}catch(e){kfMessage('storage');return}
    // No clear(), no participant reset and no reuse of in-memory test objects.
    navigating=true;kfReload();
  }catch(e){kfMessage('network')}
  finally{if(!navigating){KFAMILY.busy=false;kfRender()}}
}
function kfMakeButton(label,handler){
  var b=document.createElement('button');b.type='button';b.className='btn secondary';b.textContent=label;b.onclick=handler;b.disabled=KFAMILY.busy;return b;
}
function kfRender(){
  if(!KFAMILY.ready)return;
  var panel=document.getElementById('familyParticipants');if(!panel)return;
  var records=kfRecords(),active=typeof token==='string'?token:'';
  var selected=records.find(p=>p.token===active);
  var existing=panel.querySelector('details'),expanded=existing?existing.open:false;
  panel.replaceChildren();
  var title=document.createElement('strong');title.textContent=kfText('Осы құрылғыдағы қатысушылар','Участники на этом устройстве');panel.appendChild(title);
  var current=document.createElement('p');current.className='kf-current';
  current.textContent=active?(kfText('Қазір: ','Сейчас: ')+(selected&&selected.full_name?selected.full_name:kfText('қатысушы','участник'))):
    kfText('Жаңа қатысушыны тіркеу. Әр баланың нәтижесі мен дипломы бөлек сақталады.',
      'Регистрация нового участника. У каждого ребёнка отдельные результат и диплом.');panel.appendChild(current);
  if(active){var add=kfMakeButton(kfText('+ Басқа баланы тіркеу','+ Зарегистрировать другого ребёнка'),()=>void kfSwitch(''));
    add.id='familyNewChildBtn';add.className='btn primary full';panel.appendChild(add)}
  if(records.length){
    var details=document.createElement('details');details.open=expanded;
    var summary=document.createElement('summary');summary.textContent=kfText('Сақталған қатысушылар','Сохранённые участники')+' ('+records.length+')';details.appendChild(summary);
    for(var p of records){
      var row=document.createElement('div');row.className='kf-child';
      var label=document.createElement('span');label.textContent=(p.full_name||kfText('Қатысушы','Участник'))+
        (p.grade?' · '+p.grade+kfText(' сынып',' класс'):'');row.appendChild(label);
      var b=kfMakeButton(p.token===active?kfText('Ашық','Открыт'):(p.done?kfText('Нәтиже / диплом','Результат / диплом'):kfText('Кабинетке кіру','Открыть кабинет')),
        ((target)=>()=>void kfSwitch(target))(p.token));
      b.disabled=KFAMILY.busy||p.token===active;row.appendChild(b);details.appendChild(row);
    }
    panel.appendChild(details);
    var note=document.createElement('small');note.textContent=kfText('Бұл тізім тек осы браузерде сақталады. Ортақ құрылғыда кабинетке қолжетімділікті ашық қалдырмаңыз.',
      'Список сохраняется в этом браузере. На общем устройстве не оставляйте доступ к кабинетам.');panel.appendChild(note);
  }
  var message=document.createElement('p');message.id='familyMessage';message.setAttribute('role','status');message.textContent=kfMessageText();message.hidden=!message.textContent;panel.appendChild(message);
  var result=document.getElementById('resultCard');
  if(result){
    var old=result.querySelector('#familyNextChildResultBtn');if(old)old.remove();
    var actions=result.querySelector('.docActions')||result;
    var next=kfMakeButton(kfText('Басқа баланы тіркеу','Зарегистрировать другого ребёнка'),()=>void kfSwitch(''));
    next.id='familyNextChildResultBtn';next.className='btn primary noprint';actions.appendChild(next);
  }
}
function kfInit(){
  if(KFAMILY.ready)return;
  var reg=document.getElementById('regCard');if(!reg)return;
  var panel=document.createElement('section');panel.id='familyParticipants';panel.className='panel noprint';reg.parentElement.insertBefore(panel,reg);
  var style=document.createElement('style');style.textContent='#familyParticipants{margin-bottom:16px}#familyParticipants strong{display:block;font-size:18px}#familyParticipants .kf-current{line-height:1.5;margin:10px 0}#familyParticipants details{margin:14px 0}#familyParticipants summary{cursor:pointer;font-weight:bold}#familyParticipants .kf-child{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:10px 0;padding:10px 0;border-bottom:1px solid currentColor}#familyParticipants .kf-child span{overflow-wrap:anywhere;flex:1;min-width:120px}#familyParticipants small{display:block;line-height:1.4}#familyParticipants button{white-space:normal;max-width:100%}';document.head.appendChild(style);
  try{
    if(sessionStorage.getItem(KFAMILY.freshKey)==='1'){
      var form=document.getElementById('regForm');if(form)form.reset();
      for(var id of ['full_name','phone','locality','school','supervisor']){var e=document.getElementById(id);if(e)e.value=''}
      var consent=document.getElementById('consent');if(consent)consent.checked=false;
      sessionStorage.removeItem(KFAMILY.freshKey);
    }
  }catch(e){}
  KFAMILY.ready=true;
  if(typeof token==='string'&&kfValid(token))kfStore({token:token});
  kfRender();
  new MutationObserver(()=>kfQueueRender()).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
}
// Block a conflicting start/payment while the switch is checking the server.
document.addEventListener('click',function(e){
  if(KFAMILY.busy&&e.target.closest&&e.target.closest('#autoStartTestBtn,#paidBtn,#autoAccessMarkBtn,#finishBtn')){
    e.preventDefault();e.stopImmediatePropagation();
  }
},true);
document.addEventListener('submit',function(e){if(KFAMILY.busy&&e.target.id==='regForm'){e.preventDefault();e.stopImmediatePropagation()}},true);
window.addEventListener('storage',e=>{if(e.key&&e.key.startsWith(KFAMILY.prefix))kfQueueRender()});
window.addEventListener('pageshow',e=>{
  if(e.persisted){KFAMILY.busy=false;kfMessage('');
    var active=typeof token==='string'?token:'';try{sessionStorage.setItem(KFAMILY.activeKey,active)}catch(ignore){}
  }
});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',kfInit,{once:true});else queueMicrotask(kfInit);
