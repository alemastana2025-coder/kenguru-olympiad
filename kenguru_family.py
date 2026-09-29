"""Device participant switcher. No database, payment, scoring or timer writes.

Runs after the existing test-safety bootstrap. Switches use a full page reload
so callbacks, answers and timers from two children cannot share page state.
"""
import hashlib
import re
from pathlib import Path

VERSION = 'family-device-20260929-v1'
MARKER = 'KENGURU_FAMILY_DEVICE_V1'


def replace_once(text, old, new, label):
    if text.count(old) != 1:
        raise RuntimeError('Family patch: unexpected ' + label)
    return text.replace(old, new, 1)


def patch_assets(base):
    static = Path(base) / 'static'
    app_path = static / 'app.js'
    index_path = static / 'index.html'
    js = app_path.read_text(encoding='utf-8')
    if MARKER in js:
        return
    if 'KENGURU_TEST_SAFETY_V1' not in js or 'KENGURU_REGISTRATION_ERRORS_V1' not in js:
        raise RuntimeError('Family patch requires the current timer and registration fixes')
    js = replace_once(js, "token=localStorage.getItem('kng_token')||''",
                      'token=kfInitialToken()', 'initial participant token')
    js = replace_once(js, '      token=payload.token;\n',
                      '      token=payload.token;\n      kfRegistered(payload.token,data);\n',
                      'registration success hook')
    js = replace_once(js, 'async function kenguruAutoApply(s){\n  if(s.token!==token)return;',
                      'async function kenguruAutoApply(s){\n  if(s.token!==token)return;\n  kfRemember(s);',
                      'participant status hook')
    js = replace_once(js, 'function showResult(s){\n  if(!ktAcceptResult(s))return;',
                      'function showResult(s){\n  if(!ktAcceptResult(s))return;\n  kfRemember(s);',
                      'verified result hook')
    # The auto-access module removes only the old browser pointer on 404. Also
    # clear this tab's pointer, without erasing any other participant record.
    js = replace_once(js,
                      "kenguruAutoClearTimers();KENGURU_ACCESS.last=null;token='';",
                      "kenguruAutoClearTimers();KENGURU_ACCESS.last=null;token='';kfMissingActive();",
                      'missing participant hook')
    prelude = Path(__file__).with_name('kenguru_family.js').read_text(encoding='utf-8')
    combined = prelude + '\n' + js
    version = VERSION + '-' + hashlib.sha256(combined.encode('utf-8')).hexdigest()[:12]
    html = index_path.read_text(encoding='utf-8')
    html, n = re.subn(r'/static/app\.js(?:\?[^"\x27\s<>]*)?',
                      '/static/app.js?v=' + version, html)
    if n != 1:
        raise RuntimeError('Family patch: participant script URL changed')
    # Do not write either asset until every patch anchor has been verified.
    app_path.write_text(combined, encoding='utf-8')
    index_path.write_text(html, encoding='utf-8')


def register_family(app):
    if app.title != 'Kenguru Olympiad' or getattr(app.state, 'kenguru_family_registered', False):
        return
    app.state.kenguru_family_registered = True

    @app.on_event('startup')
    async def start_family():
        import main
        if main.app is not app:
            return
        if not getattr(app.state, 'kenguru_test_safety_installed', False):
            raise RuntimeError('Family patch must run after test safety')
        patch_assets(main.BASE)
        app.state.kenguru_family_installed = True
        print('[KENGURU] FAMILY DEVICE ACTIVE: SEPARATE PARTICIPANTS; RESULTS PRESERVED', flush=True)
