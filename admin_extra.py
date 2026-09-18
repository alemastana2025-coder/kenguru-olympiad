import base64, csv, io, json, secrets
from pathlib import Path
from fastapi import HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse

_INSTALLED = False

def _main():
    import main
    return main

def _auth(password: str):
    m = _main()
    if not password or not secrets.compare_digest(password, m.ADMIN_PASSWORD):
        raise HTTPException(401, "Wrong password")
    return m

def _tables(m):
    with m.db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS question_overrides(grade INTEGER PRIMARY KEY,data TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS template_store(kind TEXT PRIMARY KEY,data TEXT NOT NULL)""")

def _load_overrides(m):
    _tables(m)
    with m.db() as c:
        rows=c.execute("SELECT grade,data FROM question_overrides").fetchall()
        temps=c.execute("SELECT kind,data FROM template_store").fetchall()
    for r in rows:
        try:
            grade=int(r['grade']); q=json.loads(r['data'])
            if grade in m.BANK and isinstance(q,list) and q: m.BANK[grade]=q
        except Exception as e: print('[KENGURU] question override load error:',repr(e))
    for r in temps:
        try:
            kind=r['kind']
            if kind not in ('diploma','certificate'): continue
            (Path(m.BASE)/'static'/f'{kind}_template.png').write_bytes(base64.b64decode(r['data']))
        except Exception as e: print('[KENGURU] template load error:',repr(e))

def _save_grade(m,grade):
    payload=json.dumps(m.BANK[grade],ensure_ascii=False)
    with m.db() as c:
        c.execute("""INSERT INTO question_overrides(grade,data) VALUES(?,?) ON CONFLICT(grade) DO UPDATE SET data=excluded.data""",(grade,payload))

def _validate_question(q,qid):
    kk=str(q.get('kk','')).strip(); ru=str(q.get('ru','')).strip()
    options=[str(x).strip() for x in q.get('options',[]) if str(x).strip()]; answer=str(q.get('answer','')).strip()
    try: points=int(q.get('points',3))
    except: points=3
    if not kk or not ru: raise HTTPException(400,'KK/RU question text is required')
    if len(options)<2: raise HTTPException(400,'At least 2 options are required')
    if answer not in options: raise HTTPException(400,'Correct answer must exactly match one option')
    if points not in (3,4,5): raise HTTPException(400,'Points must be 3, 4 or 5')
    return {'id':qid,'kk':kk,'ru':ru,'options':options,'answer':answer,'points':points}

def register_admin_extra(app):
    if getattr(app.state,'_kenguru_admin_extra',False): return
    app.state._kenguru_admin_extra=True

    @app.on_event('startup')
    async def _kenguru_startup():
        try:
            m=_main()
            from question_bank_final import BANK as REVIEWED_BANK
            # Completely replace the old generated bank with the reviewed fixed 330 questions.
            m.BANK={g:[dict(q) for q in qs] for g,qs in REVIEWED_BANK.items()}
            print('[KENGURU] REVIEWED FINAL bank loaded: 11 grades x 30 = 330 questions')

            # One-time migration: old question_overrides were created from the previous bank
            # and would otherwise replace the new V3 questions after every restart.
            _tables(m)
            with m.db() as c:
                c.execute("""CREATE TABLE IF NOT EXISTS app_meta(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )""")
                row=c.execute("SELECT value FROM app_meta WHERE key=?",('question_bank_version',)).fetchone()
                version=(row['value'] if row else None)
                if version!='reviewed-330-v1':
                    c.execute("DELETE FROM question_overrides")
                    c.execute("""INSERT INTO app_meta(key,value) VALUES(?,?)
                                 ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                              ('question_bank_version','reviewed-330-v1'))
                    print('[KENGURU] old question overrides cleared for reviewed 330 bank')

            # Now load only overrides created after V3 became active.
            _load_overrides(m)
            print('[KENGURU] admin data loaded')
        except Exception as e: print('[KENGURU] startup load error:',repr(e))

    @app.get('/api/admin/questions/{grade}')
    def admin_questions(grade:int,password:str):
        m=_auth(password)
        if grade not in m.BANK: raise HTTPException(404,'Grade not found')
        return m.BANK[grade]

    @app.put('/api/admin/question/{grade}/{qid}')
    async def admin_question_update(grade:int,qid:str,request:Request):
        body=await request.json(); m=_auth(str(body.get('password','')))
        if grade not in m.BANK: raise HTTPException(404,'Grade not found')
        bank=m.BANK[grade]; idx=next((i for i,x in enumerate(bank) if str(x.get('id'))==qid),None)
        if idx is None: raise HTTPException(404,'Question not found')
        bank[idx]=_validate_question(body,qid); _save_grade(m,grade)
        return {'ok':True,'question':bank[idx]}

    @app.post('/api/admin/questions/{grade}/reset')
    def admin_questions_reset(grade:int,password:str):
        m=_auth(password)
        with m.db() as c: c.execute('DELETE FROM question_overrides WHERE grade=?',(grade,))
        return {'ok':True,'restart_required':True}

    @app.post('/api/admin/template/{kind}')
    async def admin_template_upload(kind:str,password:str=Form(...),file:UploadFile=File(...)):
        m=_auth(password)
        if kind not in ('diploma','certificate'): raise HTTPException(400,'Bad template kind')
        raw=await file.read()
        if len(raw)>8*1024*1024: raise HTTPException(413,'Template is too large')
        if 'png' not in (file.content_type or '').lower() and not (file.filename or '').lower().endswith('.png'): raise HTTPException(400,'PNG only')
        encoded=base64.b64encode(raw).decode('ascii')
        with m.db() as c: c.execute("""INSERT INTO template_store(kind,data) VALUES(?,?) ON CONFLICT(kind) DO UPDATE SET data=excluded.data""",(kind,encoded))
        (Path(m.BASE)/'static'/f'{kind}_template.png').write_bytes(raw)
        return {'ok':True,'kind':kind,'bytes':len(raw)}

    @app.delete('/api/admin/participant/{token}')
    def admin_participant_delete(token:str,password:str):
        m=_auth(password)
        with m.db() as c: c.execute('DELETE FROM participants WHERE token=?',(token,))
        return {'ok':True}

    @app.get('/api/admin/export.csv')
    def admin_export(password:str):
        m=_auth(password)
        with m.db() as c: rows=c.execute('SELECT * FROM participants ORDER BY id').fetchall()
        sio=io.StringIO(); fields=['id','full_name','grade','phone','region','locality','school','supervisor','payment_status','score','award','diploma_no','created_at','submitted_at']
        w=csv.DictWriter(sio,fieldnames=fields,extrasaction='ignore'); w.writeheader()
        for r in rows: w.writerow(dict(r))
        return StreamingResponse(io.BytesIO(sio.getvalue().encode('utf-8-sig')),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="kenguru_participants.csv"'})
