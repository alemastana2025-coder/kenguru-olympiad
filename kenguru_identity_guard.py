"""KENGURU participant identity guard.
Prevents social/in-app browser autofill from silently replacing the child's name
and adds a mandatory pre-registration identity confirmation.
Does not alter existing participant/payment/result records.
"""
import hashlib
import re
from pathlib import Path

VERSION = "identity-guard-20260930-v1"
MARKER = "KENGURU_IDENTITY_GUARD_V1"


def patch_assets(base):
    static = Path(base) / "static"
    index_path = static / "index.html"
    app_path = static / "app.js"
    html = index_path.read_text(encoding="utf-8")
    js = app_path.read_text(encoding="utf-8")
    if MARKER in js:
        return

    # Disable profile-name autofill heuristics on the child field. Keep phone autocomplete.
    old = '<form id="regForm" class="formgrid">'
    new = '<form id="regForm" class="formgrid" autocomplete="off">'
    if html.count(old) != 1:
        raise RuntimeError("Identity guard: registration form anchor changed")
    html = html.replace(old, new, 1)

    old = '<input id="full_name" required autocomplete="name">'
    new = '<input id="full_name" name="kenguru_child_full_name_2026" required autocomplete="off" autocorrect="off" autocapitalize="words" spellcheck="false" data-form-type="other">'
    if html.count(old) != 1:
        raise RuntimeError("Identity guard: child name input anchor changed")
    html = html.replace(old, new, 1)

    # Also make school/locality explicit non-profile fields.
    html = html.replace('<input id="locality" required>', '<input id="locality" name="kenguru_locality" required autocomplete="off">', 1)
    html = html.replace('<input id="school" required>', '<input id="school" name="kenguru_school" required autocomplete="off">', 1)

    # Add a visible warning directly under the child name field.
    old = '<div class="wide"><label data-i18n="name">Оқушының аты-жөні толық</label><input id="full_name" name="kenguru_child_full_name_2026" required autocomplete="off" autocorrect="off" autocapitalize="words" spellcheck="false" data-form-type="other"></div>'
    new = '<div class="wide"><label data-i18n="name">Оқушының аты-жөні толық</label><input id="full_name" name="kenguru_child_full_name_2026" required autocomplete="off" autocorrect="off" autocapitalize="words" spellcheck="false" data-form-type="other"><small id="childNameWarning" style="display:block;margin-top:6px;line-height:1.35;color:#9a5a00;font-weight:700">Instagram/браузер өз аты-жөніңізді автоматты қойса, өшіріп, баланың аты-жөнін жазыңыз.</small></div>'
    if html.count(old) != 1:
        raise RuntimeError("Identity guard: child name wrapper anchor changed")
    html = html.replace(old, new, 1)

    prelude = r'''// KENGURU_IDENTITY_GUARD_V1
(function(){
  var touched=false, confirmedValue='';
  function nameEl(){return document.getElementById('full_name')}
  function lang(){try{return document.getElementById('lang').value==='ru'?'ru':'kk'}catch(e){return 'kk'}}
  function clearSilentAutofill(){
    var el=nameEl(); if(!el||touched||document.activeElement===el)return;
    // Before the parent has interacted with this field, any prefilled profile name is unsafe.
    if(el.value){el.value='';el.dispatchEvent(new Event('input',{bubbles:true}))}
  }
  function init(){
    var el=nameEl(), form=document.getElementById('regForm'); if(!el||!form)return;
    el.setAttribute('autocomplete','off');
    el.setAttribute('name','kenguru_child_full_name_2026');
    el.addEventListener('pointerdown',()=>{touched=true},{passive:true});
    el.addEventListener('keydown',()=>{touched=true});
    el.addEventListener('paste',()=>{touched=true});
    el.addEventListener('focus',()=>{touched=true});
    el.addEventListener('input',()=>{if(document.activeElement===el)touched=true; confirmedValue=''});
    // Instagram/Android WebView can autofill after DOMContentLoaded.
    [0,250,800,1600].forEach(ms=>setTimeout(clearSilentAutofill,ms));

    form.addEventListener('submit',function(e){
      if(e.__kenguruIdentityConfirmed)return;
      var name=(el.value||'').trim(), school=((document.getElementById('school')||{}).value||'').trim();
      if(!name)return;
      if(confirmedValue===name+'|'+school)return;
      e.preventDefault(); e.stopImmediatePropagation();
      var ru=lang()==='ru';
      var msg=ru
        ? 'Проверьте данные для диплома:\n\nФИО РЕБЁНКА: '+name+'\nШКОЛА: '+school+'\n\nИменно эти данные будут указаны в дипломе. Всё верно?'
        : 'Дипломға түсетін мәліметті тексеріңіз:\n\nОҚУШЫНЫҢ АТЫ-ЖӨНІ: '+name+'\nМЕКТЕП: '+school+'\n\nДипломда дәл осы мәліметтер жазылады. Дұрыс па?';
      if(!window.confirm(msg)){el.focus();el.select();return}
      confirmedValue=name+'|'+school;
      // Re-dispatch only after explicit confirmation; existing registration handler receives it.
      var ev=new Event('submit',{bubbles:true,cancelable:true});
      ev.__kenguruIdentityConfirmed=true;
      form.dispatchEvent(ev);
    },true);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
'''
    js = prelude + "\n" + js

    # Cache-bust app.js after all current guards.
    version = VERSION + '-' + hashlib.sha256(js.encode('utf-8')).hexdigest()[:12]
    html, n = re.subn(r'/static/app\.js(?:\?[^"\'\s<>]*)?', '/static/app.js?v=' + version, html)
    if n != 1:
        raise RuntimeError("Identity guard: app script URL changed")

    app_path.write_text(js, encoding="utf-8")
    index_path.write_text(html, encoding="utf-8")


def register_identity_guard(app):
    if app.title != "Kenguru Olympiad" or getattr(app.state, "kenguru_identity_guard_registered", False):
        return
    app.state.kenguru_identity_guard_registered = True

    @app.on_event("startup")
    async def start_identity_guard():
        import main
        if main.app is not app:
            return
        if not getattr(app.state, "kenguru_load_guard_installed", False):
            raise RuntimeError("Identity guard must run after load guard")
        patch_assets(main.BASE)
        app.state.kenguru_identity_guard_installed = True
        print("[KENGURU] IDENTITY GUARD ACTIVE: PROFILE AUTOFILL BLOCKED; NAME CONFIRMATION REQUIRED", flush=True)
