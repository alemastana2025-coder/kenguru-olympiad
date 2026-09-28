// KENGURU_TEST_SAFETY_V1: a displayed countdown is not authority to finalize.
var KTEST={token:'',started:0,deadline:0,anchor:0,wall:0,remaining:0,revision:0,
  saved:{},pending:{},conflicts:{},loading:null,saving:null,syncing:null,finishing:null,
  tick:null,poll:null,saveTimer:null,retry:null,pendingFinish:null,frozen:false,review:false,
  skewCheck:false,storageWarning:false,retryMs:2000,complete:false};
function ktText(kk,ru){return uiLang==='ru'?ru:kk}
function ktNotice(message,retry){
  var card=['testCard','waitCard','payCard'].map(byId).find(x=>x&&!x.classList.contains('hidden'));
  if(!card)return;
  var el=card.querySelector('[data-test-safety-notice]');
  if(!el){el=document.createElement('div');el.dataset.testSafetyNotice='1';el.setAttribute('role','status');el.style.cssText='margin:12px 0;line-height:1.5;overflow-wrap:anywhere';card.insertBefore(el,card.firstChild)}
  el.textContent=message;
  if(retry){var b=document.createElement('button');b.type='button';b.className='btn secondary';b.textContent=ktText('Қайта жіберу','Повторить');b.onclick=retry;el.appendChild(document.createElement('br'));el.appendChild(b)}
}
function ktKey(){return 'kng_test_draft_v1_'+KTEST.token}
function ktPersist(){
  if(!KTEST.token||!KTEST.started)return;
  try{localStorage.setItem(ktKey(),JSON.stringify({started:KTEST.started,deadline:KTEST.deadline,
    saved:KTEST.saved,pending:KTEST.pending,conflicts:KTEST.conflicts,revision:KTEST.revision,pendingFinish:KTEST.pendingFinish}))}
  catch(e){KTEST.storageWarning=true}
}
function ktClearTimers(){
  clearInterval(KTEST.tick);clearInterval(KTEST.poll);clearTimeout(KTEST.saveTimer);clearTimeout(KTEST.retry);
  KTEST.tick=null;KTEST.poll=null;KTEST.saveTimer=null;KTEST.retry=null;
  if(typeof timerId!=='undefined')clearInterval(timerId);
}
function ktFreeze(value){
  KTEST.frozen=value;
  document.querySelectorAll('#testForm input').forEach(x=>x.disabled=value);
  var b=byId('finishBtn');if(b)b.disabled=value;
}
function ktClock(d){
  if(!Number.isFinite(d.remaining_ms)||!Number.isFinite(d.server_now_ms)||!Number.isFinite(d.deadline_at_ms))throw Error('Invalid server clock');
  KTEST.deadline=d.deadline_at_ms;KTEST.remaining=Math.max(0,d.remaining_ms-Math.max(0,Number(d._rtt_ms)||0)/2);
  KTEST.anchor=performance.now();KTEST.wall=Date.now();KTEST.skewCheck=false;
}
function ktRemaining(){return Math.max(0,KTEST.remaining-Math.max(0,performance.now()-KTEST.anchor))}
function ktTick(){
  if(!KTEST.started||KTEST.review||!currentTest)return;
  var drift=(Date.now()-KTEST.wall)-(performance.now()-KTEST.anchor);
  if(Math.abs(drift)>2000&&!KTEST.skewCheck){
    KTEST.skewCheck=true;
    ktNotice(ktText('Уақыт сервермен сәйкестендірілуде…','Синхронизируем время с сервером…'));
    void ktSync();
  }
  left=Math.ceil(ktRemaining()/1000);
  var el=byId('timer');if(el)el.textContent=String(Math.floor(left/60)).padStart(2,'0')+':'+String(left%60).padStart(2,'0');
  // Zero on this clock causes only a server check, never an early submit.
  if(left===0&&!KTEST.pendingFinish&&!KTEST.finishing&&!KTEST.syncing){ktFreeze(true);void ktSync()}
}
function ktProgress(){
  var n=new Set(Array.from(document.querySelectorAll('#testForm input:checked')).map(x=>x.name)).size;
  var el=byId('progressBar');if(el)el.style.width=(n/30*100)+'%';
}
async function ktRequest(path,options){
  var began=performance.now(),control=new AbortController(), t=setTimeout(()=>control.abort(),20000);
  try{
    var r=await fetch(path,Object.assign({cache:'no-store',credentials:'same-origin'},options||{},{signal:control.signal}));
    var d;try{d=await r.json()}catch(e){throw Error('Invalid server response')}
    if(!r.ok){
      var detail=d&&d.detail;
      if(detail&&typeof detail==='object'&&['review_required','revision_conflict','not_expired'].includes(detail.status)){detail._rtt_ms=performance.now()-began;return detail;}
      var e=new Error((detail&&typeof detail==='object'?(uiLang==='ru'?detail.ru:detail.kk):detail)||('HTTP '+r.status));
      e.code=detail&&detail.code;e.httpStatus=r.status;throw e;
    }
    if(!d||typeof d!=='object')throw Error('Empty server response');
    d._rtt_ms=performance.now()-began;return d;
  }finally{clearTimeout(t)}
}
function ktPost(path,body){return ktRequest(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}
function ktError(e){return e&&e.httpStatus&&e.message?e.message:ktText('Байланыс үзілді. Жауаптар өшірілген жоқ; қайта жіберіледі.','Связь прервана. Ответы не удалены; отправка будет повторена.')}
function ktScheduleRetry(fn){
  clearTimeout(KTEST.retry);var active=KTEST.token;
  KTEST.retry=setTimeout(()=>{if(token===active&&!KTEST.review)void fn()},KTEST.retryMs);
  KTEST.retryMs=Math.min(KTEST.retryMs*2,15000);
}
function ktSavedNotice(){
  var pending=Object.keys(KTEST.pending).length;
  if(Object.keys(KTEST.conflicts).length){
    ktNotice(ktText('Басқа бетте жауап өзгертілген. Белгіленген сұрақтағы жауабыңызды қайта таңдаңыз.','Ответ изменён в другой вкладке. Повторно выберите ответ в отмеченном вопросе.'));return;
  }
  ktNotice(pending?ktText('Жауаптар жіберілуде…','Отправляем ответы…'):
    ktText('Серверде сақталған жауаптар: ','Ответов сохранено на сервере: ')+Object.keys(KTEST.saved).length+
    (KTEST.storageWarning?ktText('. Браузерде қосымша сақтық көшірме сақталмай тұр.','. Дополнительная копия в браузере недоступна.'):''));
}
function ktSetRadios(){
  var answers=Object.assign({},KTEST.saved,KTEST.pending);
  document.querySelectorAll('#testForm input[type="radio"]').forEach(x=>{
    x.checked=answers[x.name]===x.value;
    var q=x.closest('.question');if(q){q.dataset.answerConflict=KTEST.conflicts[x.name]?'1':'0';q.style.outline=KTEST.conflicts[x.name]?'2px solid currentColor':''}
  });ktProgress();
}
function ktReview(d){
  ktClearTimers();KTEST.review=true;KTEST.pendingFinish=null;ktFreeze(true);ktPersist();
  showOnly('waitCard');kenguruAutoWaitButton(false);kenguruAutoStartButton(false);
  ktReviewLabels();
}
function ktReviewLabels(){
  if(!KTEST.review)return;
  var box=byId('waitCard'),title=box&&box.querySelector('[data-i18n="waitTitle"]'),text=box&&box.querySelector('[data-i18n="waitText"]');
  if(title)title.textContent=ktText('Нәтижені тексеру','Проверка результата');
  if(text)text.textContent=ktText('Ұйымдастырушы сақталған жауаптар мен уақыт деректерін тексере алады.','Организатор может проверить сохранённые ответы и данные времени.');
  var el=byId('payStatus');if(el)el.textContent=ktText('Жауаптар тексеруге сақталды','Ответы сохранены для проверки');
  ktNotice(ktText('Жүйе уақыт не сақтау сәйкессіздігін анықтады. Нөл балл қойылған жоқ. Ұйымдастырушыға тіркелген аты-жөніңізді жіберіңіз; қайта төлем жасамаңыз.',
    'Обнаружено несоответствие времени или сохранения. Нулевой балл не выставлен. Сообщите организатору ФИО участника; повторная оплата не нужна.'));
}
function ktReceive(d,sent){
  if(KTEST.complete)return true;
  if(d.status==='submitted'){showResult(d);return true}
  if(d.token!==KTEST.token)throw Error('Participant mismatch');
  if(d.status==='review_required'){ktReview(d);return true}
  if(!Number.isInteger(d.revision)||!d.saved_answers||typeof d.saved_answers!=='object')throw Error('Invalid saved answers');
  ktClock(d);
  // A stale response can adjust the clock, but cannot roll back the draft.
  if(d.revision<KTEST.revision)return false;
  if(!sent&&d.revision>KTEST.revision){
    for(var q of Object.keys(KTEST.pending)){
      if(d.saved_answers[q]!==KTEST.saved[q]&&d.saved_answers[q]!==KTEST.pending[q]){KTEST.conflicts[q]=KTEST.pending[q];delete KTEST.pending[q];}
    }
  }
  if(sent&&d.status==='revision_conflict'){
    for(var q of Object.keys(sent.changes)){
      if(d.saved_answers[q]!==sent.base[q]&&d.saved_answers[q]!==sent.changes[q]&&KTEST.pending[q]===sent.changes[q]){
        KTEST.conflicts[q]=sent.changes[q];delete KTEST.pending[q];
      }
    }
  }
  KTEST.saved=Object.assign({},d.saved_answers);KTEST.revision=d.revision;
  if(sent&&d.status!=='revision_conflict'){
    for(var q of Object.keys(sent.changes))if(KTEST.pending[q]===sent.changes[q])delete KTEST.pending[q];
  }
  for(var q of Object.keys(KTEST.pending))if(KTEST.pending[q]===KTEST.saved[q])delete KTEST.pending[q];
  ktPersist();ktSetRadios();return false;
}
async function ktLoad(start){
  if(KTEST.loading)return KTEST.loading;
  if(currentTest&&KTEST.token===token)return;
  var active=token;if(!active)return;
  testLoading=true;
  KTEST.loading=(async()=>{
    try{
      var d=await (start?ktPost('/api/test/start',{token:active}):ktRequest('/api/test/'+encodeURIComponent(active)));
      if(active!==token)return;
      if(d.status==='submitted'){showResult(d);return}
      if(d.status==='review_required'){KTEST.token=active;KTEST.started=d.started_at_ms;ktReview(d);return}
      if(d.status!=='active'||!Array.isArray(d.questions)||d.questions.length!==30||!d.saved_answers||!Number.isInteger(d.revision))throw Error('Invalid test response');
      ktClearTimers();KTEST.token=active;KTEST.started=d.started_at_ms;KTEST.review=false;KTEST.complete=false;
      KTEST.saved=Object.assign({},d.saved_answers);KTEST.revision=d.revision;KTEST.pending={};KTEST.conflicts={};KTEST.pendingFinish=null;
      ktClock(d);
      var cached=null;try{cached=JSON.parse(localStorage.getItem(ktKey())||'null')}catch(e){}
      if(cached&&cached.started===KTEST.started&&cached.deadline===KTEST.deadline){
        var qmap=Object.fromEntries(d.questions.map(q=>[q.id,q.options]));
        for(var q of Object.keys(cached.pending||{})){
          var val=cached.pending[q];if(!qmap[q]||!qmap[q].includes(val))continue;
          if(d.saved_answers[q]===val)continue;
          if(d.saved_answers[q]!==((cached.saved||{})[q]))KTEST.conflicts[q]=val;
          else KTEST.pending[q]=val;
        }
        Object.assign(KTEST.conflicts,cached.conflicts||{});
        if(['manual','timeout'].includes(cached.pendingFinish))KTEST.pendingFinish=cached.pendingFinish;
      }
      currentTest=d;uiLang=d.lang;KENGURU_ACCESS.last=Object.assign({},KENGURU_ACCESS.last||{},{token:active,started_at:d.started_at});applyLang();
      showOnly('testCard');
      byId('who').textContent=d.full_name+' · '+d.grade+ktText(' сынып',' класс');
      byId('testForm').innerHTML=d.questions.map((q,i)=>'<div class="question"><div class="qmeta">'+(i+1)+'/30</div><h3>'+esc(q.text)+'</h3><div class="opts">'+q.options.map((o,k)=>'<label class="opt"><input type="radio" name="'+escAttr(q.id)+'" value="'+escAttr(o)+'"><b>'+String.fromCharCode(65+k)+')</b> '+esc(o)+'</label>').join('')+'</div></div>').join('');
      ktSetRadios();ktFreeze(Boolean(KTEST.pendingFinish)||d.expired);ktPersist();ktSavedNotice();
      KTEST.tick=setInterval(ktTick,250);KTEST.poll=setInterval(()=>{if(document.visibilityState==='visible')void ktSync()},20000);ktTick();
      if(KTEST.pendingFinish)setTimeout(()=>void ktSubmit(KTEST.pendingFinish),0);
      else if(d.expired)setTimeout(()=>void ktSubmit('timeout'),0);
      else if(Object.keys(KTEST.pending).length)void ktSave();
    }catch(e){
      if(active!==token)return;
      currentTest=null;showOnly('waitCard');kenguruAutoStartButton(true);
      ktNotice(ktError(e),()=>ktLoad(start));
    }finally{testLoading=false;KTEST.loading=null}
  })();return KTEST.loading;
}
async function ktSave(){
  if(KTEST.saving)return KTEST.saving;
  if(!currentTest||KTEST.review||!Object.keys(KTEST.pending).length)return;
  var active=KTEST.token,sent={changes:Object.assign({},KTEST.pending),base:Object.assign({},KTEST.saved)};
  KTEST.saving=(async()=>{
    try{
      var d=await ktPost('/api/test/answers',{token:active,answers:sent.changes,base_revision:KTEST.revision});
      if(active!==token)return;
      if(ktReceive(d,sent))return;
      KTEST.retryMs=2000;ktSavedNotice();
    }catch(e){if(active===token){ktNotice(ktError(e),()=>ktSave());ktScheduleRetry(()=>KTEST.pendingFinish?ktSubmit(KTEST.pendingFinish):ktSave())}}
    finally{KTEST.saving=null}
  })();return KTEST.saving;
}
async function ktSync(){
  if(KTEST.syncing)return KTEST.syncing;
  if(!currentTest||KTEST.review||KTEST.finishing)return;
  var active=KTEST.token;
  KTEST.syncing=(async()=>{
    try{
      var d=await ktRequest('/api/test/state/'+encodeURIComponent(active));
      if(active!==token)return;
      if(ktReceive(d))return;
      KTEST.retryMs=2000;
      if(d.expired&&!KTEST.pendingFinish)setTimeout(()=>void ktSubmit('timeout'),0);
      else if(!KTEST.pendingFinish){ktFreeze(false);ktSavedNotice();if(Object.keys(KTEST.pending).length)void ktSave()}
    }catch(e){if(active===token){ktNotice(ktError(e),()=>ktSync());ktScheduleRetry(()=>ktSync())}}
    finally{KTEST.syncing=null}
  })();return KTEST.syncing;
}
async function ktSubmit(reason){
  if(KTEST.finishing)return KTEST.finishing;
  if(!currentTest||KTEST.review)return;
  reason=reason||KTEST.pendingFinish||'manual';
  if(Object.keys(KTEST.conflicts).length){ktFreeze(false);ktSavedNotice();return}
  var active=KTEST.token;
  clearTimeout(KTEST.saveTimer);KTEST.saveTimer=null;
  KTEST.pendingFinish=reason;ktFreeze(true);ktPersist();
  KTEST.finishing=(async()=>{
    try{
      if(KTEST.saving)await KTEST.saving;
      if(KTEST.review||!currentTest)return;
      if(Object.keys(KTEST.conflicts).length){KTEST.pendingFinish=null;ktFreeze(false);ktPersist();ktSavedNotice();return}
      ktNotice(ktText('Нәтиже серверге сақталуда. Бетті жаппаңыз.','Сохраняем результат на сервере. Не закрывайте страницу.'));
      var sent={changes:Object.assign({},KTEST.pending),base:Object.assign({},KTEST.saved)};
      var d=await ktPost('/api/submit',{token:active,answers:sent.changes,base_revision:KTEST.revision,reason:reason});
      if(active!==token)return;
      if(d.status==='submitted'){showResult(d);return}
      if(ktReceive(d,sent))return;
      if(d.status==='not_expired'){
        KTEST.pendingFinish=null;ktFreeze(false);ktPersist();ktTick();ktSavedNotice();return;
      }
      if(d.status==='revision_conflict'){
        KTEST.pendingFinish=null;ktFreeze(false);ktPersist();ktSavedNotice();return;
      }
      throw Error('Result was not confirmed');
    }catch(e){
      if(active!==token)return;
      // Keep frozen answers and the pending operation; the endpoint is idempotent.
      ktPersist();ktNotice(ktError(e),()=>ktSubmit(reason));ktScheduleRetry(()=>ktSubmit(reason));
    }finally{KTEST.finishing=null}
  })();return KTEST.finishing;
}
function ktAcceptResult(s){
  if(!token&&new URLSearchParams(location.search).get('preview')==='diploma')return true;
  if(!s||!s.submitted_at||!Number.isInteger(s.score)||s.score<0||s.score>30||!s.diploma_no||(s.token&&s.token!==token)){
    ktNotice(ktText('Нәтиже әлі расталмаған. Нөл балл қойылмайды; қайта тексеріңіз.','Результат ещё не подтверждён. Ноль не выставлен; повторите проверку.'),()=>KTEST.pendingFinish?ktSubmit(KTEST.pendingFinish):ktSync());return false;
  }
  ktClearTimers();KTEST.complete=true;KTEST.pendingFinish=null;KTEST.pending={};KTEST.conflicts={};
  if(KTEST.token===token){try{localStorage.removeItem(ktKey())}catch(e){}}
  KENGURU_ACCESS.resultKey=s.token+'|'+s.submitted_at+'|'+s.diploma_no;
  return true;
}
document.addEventListener('change',function(e){
  var x=e.target;
  if(!x.matches('#testForm input[type="radio"]')||!currentTest)return;
  if(KTEST.frozen||ktRemaining()<=0){ktSetRadios();void ktSync();return}
  KTEST.pending[x.name]=x.value;delete KTEST.conflicts[x.name];ktPersist();ktProgress();ktSavedNotice();
  clearTimeout(KTEST.saveTimer);KTEST.saveTimer=setTimeout(()=>void ktSave(),350);
});
document.addEventListener('submit',function(e){if(e.target.id==='testForm'){e.preventDefault();e.stopImmediatePropagation()}},true);
document.addEventListener('visibilitychange',function(){
  if(!currentTest)return;ktPersist();
  if(document.visibilityState==='visible'){ktTick();if(KTEST.pendingFinish)void ktSubmit(KTEST.pendingFinish);else void ktSync()}
  else if(!KTEST.finishing)void ktSave();
});
window.addEventListener('online',function(){if(currentTest){if(KTEST.pendingFinish)void ktSubmit(KTEST.pendingFinish);else void ktSync()}});
window.addEventListener('pagehide',function(){
  ktPersist();
  if(!currentTest||KTEST.review||!Object.keys(KTEST.pending).length)return;
  // Enqueued is not acknowledged: retain the local copy until a normal response.
  var body=JSON.stringify({token:KTEST.token,answers:KTEST.pending,base_revision:KTEST.revision});
  try{fetch('/api/test/answers',{method:'POST',headers:{'Content-Type':'application/json'},body:body,keepalive:true,cache:'no-store'}).catch(()=>{})}catch(e){}
});
window.addEventListener('pageshow',function(e){if(e.persisted&&currentTest)void ktSync()});

new MutationObserver(()=>ktReviewLabels()).observe(document.documentElement,{attributes:true,attributeFilter:["lang"]});
