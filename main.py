from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path
import sqlite3, secrets, random, os, hashlib, shutil
from datetime import datetime, timezone, timedelta

BASE = Path(__file__).parent
DB = BASE / 'kenguru.sqlite3'
PRICE = 1000
PAY_URL = 'https://pay.kaspi.kz/pay/ylajsf3h'
ADMIN_PASSWORD = os.getenv('KENGURU_ADMIN_PASSWORD', 'change-me-now')
TEST_SECONDS = 30 * 60
GRACE_SECONDS = 45
app = FastAPI(title='Kenguru Olympiad')
STATIC_DIR = BASE / 'static'
STATIC_DIR.mkdir(exist_ok=True)
# Render production currently keeps web assets at repository root and copies the core files
# into /static at start. Copy certificate backgrounds too so the official templates are served.
for _asset in ('diploma_template.png', 'certificate_template.png'):
    _src = BASE / _asset
    _dst = STATIC_DIR / _asset
    if _src.exists():
        shutil.copy2(_src, _dst)
app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS participants(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            lang TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            region TEXT NOT NULL,
            locality TEXT NOT NULL,
            school TEXT NOT NULL,
            grade INTEGER NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'unpaid',
            created_at TEXT NOT NULL,
            started_at TEXT,
            submitted_at TEXT,
            question_ids TEXT,
            score INTEGER,
            award TEXT,
            diploma_no TEXT UNIQUE
        )''')
init_db()

# Original, generated-style question bank. The uploaded Kangaroo example is used only as a style reference.

def ru_question(q:str)->str:
    """Translate the controlled original templates used by make_bank."""
    import re
    rules=[
      (r'Айданың (\d+) қызыл, (\d+) көк фишкасы болды\. Ол (\d+) фишканы берді\. Неше фишка қалды\?', lambda m:f'У Айды было {m[1]} красных и {m[2]} синих фишек. Она отдала {m[3]} фишки. Сколько фишек осталось?'),
      (r'Заңдылықты жалғастыр: (.+), \?', lambda m:f'Продолжи закономерность: {m[1]}, ?'),
      (r'(\d+) қатардың әрқайсысында (\d+) нүктеден бар\. Барлығы неше нүкте\?', lambda m:f'В каждом из {m[1]} рядов по {m[2]} точек. Сколько точек всего?'),
      (r'Қорапта (\d+) текше бар\. (\d+) текше алынды\. Қалған текшелер саны қанша\?', lambda m:f'В коробке {m[1]} кубиков. {m[2]} кубиков забрали. Сколько кубиков осталось?'),
      (r'Сатының төменнен (\d+)-басқышында Дана тұр\. Ол 2 басқыш жоғары көтерілді\. Енді нешінші басқышта\?', lambda m:f'Дана стоит на {m[1]}-й ступеньке снизу. Она поднялась на 2 ступеньки. На какой ступеньке она теперь?'),
      (r'Бір үстелде (\d+) кітап, екінші үстелде (\d+) кітап бар\. Екі үстелде барлығы қанша кітап\?', lambda m:f'На одном столе {m[1]} книг, на другом {m[2]}. Сколько книг на двух столах?'),
      (r'Екі бірдей қапта (\d+)-ден шар бар және үстелде тағы 1 шар жатыр\. Барлығы неше шар\?', lambda m:f'В двух одинаковых пакетах по {m[1]} шариков и ещё 1 шарик на столе. Сколько шариков всего?'),
      (r'Сан сызығында (\d+) санынан оңға қарай 3 қадам жасалды\. Қай санға келеміз\?', lambda m:f'На числовой прямой от числа {m[1]} сделали 3 шага вправо. К какому числу пришли?'),
      (r'Қатарда (\d+) бала тұр\. Соңғы екі бала шығып кетті\. Қатарда неше бала қалды\?', lambda m:f'В ряду стояло {m[1]} детей. Двое последних вышли. Сколько детей осталось?'),
      (r'Арманда (\d+) қарындаш, Мираста (\d+) қарындаш\. Мираста неше қарындаш артық\?', lambda m:f'У Армана {m[1]} карандашей, у Мираса {m[2]}. На сколько карандашей у Мираса больше?'),
      (r'(\d+) қораптың әрқайсысында (\d+) шардан бар\. (\d+) шар жоғалды\. Неше шар қалды\?', lambda m:f'В каждой из {m[1]} коробок по {m[2]} шариков. {m[3]} шарика потерялись. Сколько осталось?'),
      (r'Тізбек: (.+), \?', lambda m:f'Последовательность: {m[1]}, ?'),
      (r'Тік төртбұрыштың периметрі (\d+) см, бір қабырғасы (\d+) см\. Екінші қабырғасы неше см\?', lambda m:f'Периметр прямоугольника {m[1]} см, одна сторона {m[2]} см. Чему равна вторая сторона?'),
      (r'(\d+) оқушы (\d+) тең топқа бөлінді\. Әр топта неше оқушы\?', lambda m:f'{m[1]} учеников разделили на {m[2]} равные группы. Сколько учеников в каждой группе?'),
      (r'Үш бірдей себетте (\d+)-тен алма және үстелде 2 алма бар\. Барлығы неше алма\?', lambda m:f'В трёх одинаковых корзинах по {m[1]} яблок и ещё 2 яблока на столе. Сколько яблок всего?'),
      (r'Сабақ (\d+):(\d+)-де басталды және (\d+) минутқа созылды\. Қай уақытта аяқталды\?', lambda m:f'Урок начался в {m[1]}:{m[2]} и длился {m[3]} минут. Во сколько он закончился?'),
      (r'Тор көзді қағазда ені (\d+) тор, биіктігі (\d+) тор тіктөртбұрыш салынды\. Оның ауданы неше тор\?', lambda m:f'На клетчатой бумаге построен прямоугольник шириной {m[1]} клеток и высотой {m[2]} клеток. Какова его площадь в клетках?'),
      (r'Бірінші қатарда 1, екіншіде 2, \.\.\. (\d+)-қатарда (\d+) жұлдыз бар\. Барлығы неше жұлдыз\?', lambda m:f'В первом ряду 1 звезда, во втором 2, ... в {m[1]}-м ряду {m[2]} звёзд. Сколько звёзд всего?'),
      (r'Автобуста (\d+) адам болды\. (\d+) адам түсті, (\d+) адам мінді\. Енді неше адам\?', lambda m:f'В автобусе было {m[1]} человек. {m[2]} вышли, {m[3]} вошли. Сколько человек стало?'),
      (r'Белгісіз санды 2-ге көбейтіп, 4 қоссақ (\d+) шығады\. Белгісіз сан қанша\?', lambda m:f'Если неизвестное число умножить на 2 и прибавить 4, получится {m[1]}. Найди число.'),
      (r'Өрнектің мәнін тап: (.+)', lambda m:f'Найди значение выражения: {m[1]}'),
      (r'Қораптың өлшемдері (\d+) см, (\d+) см және (\d+) см\. Көлемі неше см³\?', lambda m:f'Размеры коробки {m[1]} см, {m[2]} см и {m[3]} см. Каков объём в см³?'),
      (r'(\d+) санның (\d+)/(\d+) бөлігі неше\?', lambda m:f'Чему равны {m[2]}/{m[3]} от числа {m[1]}?'),
      (r'(.+)= (.+)', lambda m:q),
      (r'(\d+) нүктенің әр жұбы бір кесіндімен қосылды\. Барлығы неше кесінді\?', lambda m:f'Каждая пара из {m[1]} точек соединена отрезком. Сколько отрезков получилось?'),
      (r'(\d+) санының (\d+)% неше\?', lambda m:f'Чему равны {m[2]}% от числа {m[1]}?'),
      (r'Тік төртбұрыштың қабырғалары (\d+) см және (\d+) см\. Периметрін тап\.', lambda m:f'Стороны прямоугольника {m[1]} см и {m[2]} см. Найди периметр.'),
      (r'Арифметикалық тізбек: (.+) Алғашқы 6 мүшесінің қосындысы\?', lambda m:f'Арифметическая последовательность: {m[1]} Найди сумму первых 6 членов.'),
      (r'Көлік (\d+) км/сағ жылдамдықпен (\d+) сағат жүрді\. Қашықтық\?', lambda m:f'Автомобиль ехал {m[2]} ч со скоростью {m[1]} км/ч. Какое расстояние он проехал?'),
      (r'(\d+) қатар мен (\d+) бағаннан тұратын торда негізгі диагональдағы (\d+) ұяшық боялды\. Боялмаған ұяшық саны\?', lambda m:f'В таблице из {m[1]} строк и {m[2]} столбцов закрашены {m[3]} клеток главной диагонали. Сколько клеток не закрашено?'),
      (r'x=(\d+) болса, (.+) өрнегінің мәні\?', lambda m:f'Если x={m[1]}, найди значение выражения {m[2]}.'),
      (r'(\d+)²−(\d+)² мәнін тап\.', lambda m:f'Найди значение {m[1]}²−{m[2]}².'),
      (r'(\d+) команда бір-бірімен бір реттен ойнайды\. Барлығы неше ойын\?', lambda m:f'{m[1]} команд играют друг с другом по одному разу. Сколько всего игр?'),
      (r'Өлшемдері (\d+)×(\d+)×(\d+) болатын тікбұрышты параллелепипедтің көлемі\?', lambda m:f'Каков объём прямоугольного параллелепипеда размером {m[1]}×{m[2]}×{m[3]}?'),
      (r'(\d+) саны (\d+)% арттырылды\. Жаңа мән\?', lambda m:f'Число {m[1]} увеличили на {m[2]}%. Какое новое значение?'),
      (r'Катеттері (\d+) және (\d+) болатын тікбұрышты үшбұрышта гипотенузаның квадраты неге тең\?', lambda m:f'В прямоугольном треугольнике катеты равны {m[1]} и {m[2]}. Чему равен квадрат гипотенузы?'),
      (r'Геометриялық тізбек: (.+) Алғашқы 5 мүшесінің қосындысы\?', lambda m:f'Геометрическая последовательность: {m[1]} Найди сумму первых 5 членов.'),
      (r'(\d+) саны (\d+):(\d+) қатынасында бөлінді\. Кіші бөлік\?', lambda m:f'Число {m[1]} разделили в отношении {m[2]}:{m[3]}. Найди меньшую часть.'),
      (r'(\d+) нүктеден үш нүктені таңдап, үшбұрыш құрудың саны \(ешбір үшеуі бір түзуде емес\)\?', lambda m:f'Сколькими способами можно выбрать 3 точки из {m[1]} и построить треугольник, если никакие три точки не лежат на одной прямой?'),
      (r'(\d+) элементтен 2 элементті ретсіз таңдаудың саны\?', lambda m:f'Сколько способов выбрать 2 элемента из {m[1]} без учёта порядка?'),
      (r'Вектордың координаталары \((\d+); (\d+)\)\. Ұзындығының квадраты\?', lambda m:f'Координаты вектора ({m[1]}; {m[2]}). Чему равен квадрат его длины?'),
      (r'(\d+) саны (\d+)% кеміді\. Нәтиже\?', lambda m:f'Число {m[1]} уменьшили на {m[2]}%. Результат?'),
      (r'Бір әрекет үшін (\d+) әдіс, одан кейінгі тәуелсіз әрекет үшін (\d+) әдіс бар\. Екі әрекетті орындау жолдарының саны\?', lambda m:f'Первое действие можно выполнить {m[1]} способами, а независимое второе — {m[2]} способами. Сколько способов выполнить оба действия?'),
      (r'(\d+) және (\d+) сандарының ең кіші ортақ еселігін тап\.', lambda m:f'Найди наименьшее общее кратное чисел {m[1]} и {m[2]}.'),
      (r'(\d+)-бұрыштың ішкі бұрыштарының қосындысы\?', lambda m:f'Чему равна сумма внутренних углов {m[1]}-угольника?'),
      (r'Қабырғалары (\d+) және (\d+) квадраттардың аудандарының айырмасы\?', lambda m:f'Квадраты имеют стороны {m[1]} и {m[2]}. Чему равна разность их площадей?'),
    ]
    for pat,fn in rules:
        m=re.fullmatch(pat,q)
        if m: return fn(m)
    return q.replace('мәнін тап','найди значение').replace('қосындысы?','сумма?').replace('x-ті тап.','найди x.').replace('x=?','x=?')

def options(correct, distractors):
    vals=[]
    for x in [correct]+distractors:
        if x not in vals: vals.append(x)
    bump=1
    while len(vals)<5:
        if isinstance(correct,(int,float)):
            cand=correct+bump
            while cand in vals:
                bump+=1; cand=correct+bump
        else:
            cand=str(len(vals)+1)
            while cand in vals:
                cand=str(int(cand)+1)
        vals.append(cand); bump+=1
    vals=vals[:5]
    rnd=random.Random(str(correct)+'|'+','.join(map(str,vals)))
    rnd.shuffle(vals)
    return [str(x) for x in vals], str(correct)

def make_bank(grade:int):
    rnd=random.Random(7000+grade)
    bank=[]
    for i in range(1,31):
        level = 3 if i<=10 else (4 if i<=20 else 5)
        t=i%10
        if grade<=2:
            maxn=20+grade*15
            if t==0:
                a=rnd.randint(3,9); b=rnd.randint(2,6); c=rnd.randint(1,5); ans=a+b-c
                q=f'Айданың {a} қызыл, {b} көк фишкасы болды. Ол {c} фишканы берді. Неше фишка қалды?'
                ds=[ans+1,ans-1,a+b,abs(a-b)+c]
            elif t==1:
                a=rnd.randint(2,7); d=rnd.randint(2,5); seq=[a+j*d for j in range(4)]; ans=a+4*d
                q='Заңдылықты жалғастыр: '+', '.join(map(str,seq))+', ?'
                ds=[ans-d,ans+d,ans+1,ans-1]
            elif t==2:
                rows=rnd.randint(2,4); cols=rnd.randint(3,5); ans=rows*cols
                q=f'{rows} қатардың әрқайсысында {cols} нүктеден бар. Барлығы неше нүкте?'
                ds=[ans+rows,ans-cols,rows+cols,ans+1]
            elif t==3:
                a=rnd.randint(8,18); b=rnd.randint(2,a-2); ans=a-b
                q=f'Қорапта {a} текше бар. {b} текше алынды. Қалған текшелер саны қанша?'
                ds=[a+b,b,a-b+1,a-b-1]
            elif t==4:
                n=rnd.randint(3,8); ans=n+2
                q=f'Сатының төменнен {n}-басқышында Дана тұр. Ол 2 басқыш жоғары көтерілді. Енді нешінші басқышта?'
                ds=[n-2,n+1,n+3,2*n]
            elif t==5:
                a=rnd.randint(4,9); b=rnd.randint(2,5); ans=a+b
                q=f'Бір үстелде {a} кітап, екінші үстелде {b} кітап бар. Екі үстелде барлығы қанша кітап?'
                ds=[a-b,a*b,ans+2,ans-1]
            elif t==6:
                x=rnd.randint(2,8); ans=x*2+1
                q=f'Екі бірдей қапта {x}-ден шар бар және үстелде тағы 1 шар жатыр. Барлығы неше шар?'
                ds=[x+1,x*2,ans+1,x*3]
            elif t==7:
                a=rnd.randint(5,12); ans=a+3
                q=f'Сан сызығында {a} санынан оңға қарай 3 қадам жасалды. Қай санға келеміз?'
                ds=[a-3,a+2,a+4,3]
            elif t==8:
                a=rnd.randint(6,15); ans=a-2
                q=f'Қатарда {a} бала тұр. Соңғы екі бала шығып кетті. Қатарда неше бала қалды?'
                ds=[a+2,a-1,a-3,2]
            else:
                a=rnd.randint(2,6); b=rnd.randint(a+1,9); ans=b-a
                q=f'Арманда {a} қарындаш, Мираста {b} қарындаш. Мираста неше қарындаш артық?'
                ds=[a+b,b,a,abs(ans-1)]
        elif grade<=4:
            if t==0:
                a=rnd.randint(3,12); b=rnd.randint(3,9); c=rnd.randint(2,6); ans=a*b-c
                q=f'{a} қораптың әрқайсысында {b} шардан бар. {c} шар жоғалды. Неше шар қалды?'; ds=[a*b+c,(a-c)*b,a+b-c,ans+1]
            elif t==1:
                a=rnd.randint(2,9); d=rnd.randint(3,7); ans=a+5*d
                q=f'Тізбек: {a}, {a+d}, {a+2*d}, {a+3*d}, {a+4*d}, ?'; ds=[ans-d,ans+d,ans+1,ans-1]
            elif t==2:
                p=rnd.choice([24,28,32,36,40]); a=rnd.randint(3,p//2-3); ans=p//2-a
                q=f'Тік төртбұрыштың периметрі {p} см, бір қабырғасы {a} см. Екінші қабырғасы неше см?'; ds=[p-a,p//2+a,ans+2,ans-2]
            elif t==3:
                total=rnd.choice([30,36,42,48]); groups=rnd.choice([3,4,6]); ans=total//groups
                q=f'{total} оқушы {groups} тең топқа бөлінді. Әр топта неше оқушы?'; ds=[groups,total-groups,ans+groups,ans-1]
            elif t==4:
                x=rnd.randint(5,15); ans=3*x+2
                q=f'Үш бірдей себетте {x}-тен алма және үстелде 2 алма бар. Барлығы неше алма?'; ds=[3*x,2*x+3,ans+3,x+5]
            elif t==5:
                h=rnd.randint(1,4); m=rnd.choice([10,15,20,25,30]); add=rnd.choice([25,35,45]); total=h*60+m+add; ans=f'{total//60}:{total%60:02d}'
                q=f'Сабақ {h}:{m:02d}-де басталды және {add} минутқа созылды. Қай уақытта аяқталды?'; ds=[f'{h}:{(m+add)%60:02d}',f'{(total//60)+1}:{total%60:02d}',f'{h+1}:{m:02d}',f'{total//60}:{(total%60+10)%60:02d}']
            elif t==6:
                a=rnd.randint(4,12); b=rnd.randint(3,9); ans=a*b
                q=f'Тор көзді қағазда ені {a} тор, биіктігі {b} тор тіктөртбұрыш салынды. Оның ауданы неше тор?'; ds=[2*(a+b),a+b,ans-a,ans+b]
            elif t==7:
                n=rnd.randint(3,8); ans=n*(n+1)//2
                q=f'Бірінші қатарда 1, екіншіде 2, ... {n}-қатарда {n} жұлдыз бар. Барлығы неше жұлдыз?'; ds=[n*n,ans+n,ans-1,2*n]
            elif t==8:
                a=rnd.randint(15,30); b=rnd.randint(5,12); c=rnd.randint(2,7); ans=a-b+c
                q=f'Автобуста {a} адам болды. {b} адам түсті, {c} адам мінді. Енді неше адам?'; ds=[a-b-c,a+b-c,ans+1,a+c]
            else:
                x=rnd.randint(3,9); ans=2*x+4
                q=f'Белгісіз санды 2-ге көбейтіп, 4 қоссақ {ans} шығады. Белгісіз сан қанша?'; ds=[x+2,x-2,2*x,ans-2]
        elif grade<=6:
            if t==0:
                a=rnd.randint(12,35); b=rnd.randint(3,9); c=rnd.randint(2,8); ans=a+b*c
                q=f'Өрнектің мәнін тап: {a} + {b} × {c}'; ds=[(a+b)*c,a+b+c,ans+c,ans-b]
            elif t==1:
                a=rnd.randint(2,7); b=rnd.randint(2,6); ans=a*b*(a+b)
                q=f'Қораптың өлшемдері {a} см, {b} см және {a+b} см. Көлемі неше см³?'; ds=[2*(a*b+b*(a+b)+a*(a+b)),a*b,ans+a,ans-b]
            elif t==2:
                den=rnd.choice([4,5,8,10]); num=rnd.randint(1,den-1); total=den*rnd.randint(4,10); ans=total*num//den
                q=f'{total} санның {num}/{den} бөлігі неше?'; ds=[total//den,total*(den-num)//den,ans+den,ans-num]
            elif t==3:
                x=rnd.randint(4,15); k=rnd.randint(2,5); b=rnd.randint(3,12); rhs=k*x+b; ans=x
                q=f'{k}x + {b} = {rhs}. x-ті тап.'; ds=[x+1,x-1,rhs-b,k+x]
            elif t==4:
                n=rnd.randint(5,12); ans=n*(n-1)//2
                q=f'{n} нүктенің әр жұбы бір кесіндімен қосылды. Барлығы неше кесінді?'; ds=[n*n,n*(n+1)//2,2*n,ans-n]
            elif t==5:
                a=rnd.randint(40,90); pct=rnd.choice([10,20,25,50]); ans=a*pct//100
                q=f'{a} санының {pct}% неше?'; ds=[a-pct,a*pct,ans+pct,100*ans//a if a else 0]
            elif t==6:
                a=rnd.randint(6,15); b=rnd.randint(4,12); ans=2*(a+b)
                q=f'Тік төртбұрыштың қабырғалары {a} см және {b} см. Периметрін тап.'; ds=[a*b,a+b,2*a+b,ans+2]
            elif t==7:
                a=rnd.randint(2,8); d=rnd.randint(2,7); n=6; ans=n*(2*a+(n-1)*d)//2
                q=f'Арифметикалық тізбек: {a}, {a+d}, {a+2*d}, ... Алғашқы 6 мүшесінің қосындысы?'; ds=[a+5*d,ans-d,ans+d,6*(a+d)]
            elif t==8:
                speed=rnd.choice([40,50,60,70]); time=rnd.randint(2,5); ans=speed*time
                q=f'Көлік {speed} км/сағ жылдамдықпен {time} сағат жүрді. Қашықтық?'; ds=[speed+time,speed*(time-1),ans+speed,ans-time]
            else:
                a=rnd.randint(2,10); ans=a*a-a
                q=f'{a} қатар мен {a} бағаннан тұратын торда негізгі диагональдағы {a} ұяшық боялды. Боялмаған ұяшық саны?'; ds=[a*a,a*a+a,ans-1,2*a]
        elif grade<=8:
            if t==0:
                x=rnd.randint(3,12); ans=x*x-3*x+2
                q=f'x={x} болса, x²−3x+2 өрнегінің мәні?'; ds=[x*x-3*x,x*x+3*x+2,ans+x,ans-2]
            elif t==1:
                a=rnd.randint(3,9); b=rnd.randint(2,8); ans=a*a-b*b
                q=f'{a}²−{b}² мәнін тап.'; ds=[(a-b)**2,(a+b)**2,a*a+b*b,ans+2*b]
            elif t==2:
                n=rnd.randint(5,10); ans=n*(n-1)//2
                q=f'{n} команда бір-бірімен бір реттен ойнайды. Барлығы неше ойын?'; ds=[n*n,n*(n+1)//2,n*(n-1),ans+n]
            elif t==3:
                a=rnd.randint(4,12); b=rnd.randint(3,9); c=rnd.randint(2,7); ans=a*b*c
                q=f'Өлшемдері {a}×{b}×{c} болатын тікбұрышты параллелепипедтің көлемі?'; ds=[2*(a*b+a*c+b*c),a*b+c,ans+a*b,ans-c]
            elif t==4:
                p=rnd.choice([15,20,25,30,40]); x=rnd.randint(80,180); ans=x*(100+p)//100
                q=f'{x} саны {p}% арттырылды. Жаңа мән?'; ds=[x*p//100,x*(100-p)//100,x+p,ans-p]
            elif t==5:
                a=rnd.randint(2,7); b=rnd.randint(3,9); x=rnd.randint(2,8); rhs=a*x+b; ans=x
                q=f'{a}x+{b}={rhs}. x=?'; ds=[x+1,x-1,rhs//a,rhs-b]
            elif t==6:
                a=rnd.randint(5,13); b=rnd.randint(4,10); ans=a*a+b*b
                q=f'Катеттері {a} және {b} болатын тікбұрышты үшбұрышта гипотенузаның квадраты неге тең?'; ds=[(a+b)**2,a*a-b*b,a*b,2*(a+b)]
            elif t==7:
                a=rnd.randint(2,8); r=rnd.randint(2,4); n=5; ans=a*(r**n-1)//(r-1)
                q=f'Геометриялық тізбек: {a}, {a*r}, {a*r*r}, ... Алғашқы 5 мүшесінің қосындысы?'; ds=[a*r**4,ans-a,ans+a,a*5*r]
            elif t==8:
                total=rnd.choice([120,150,180,240]); ratio=rnd.choice([(2,3),(3,5),(4,5)]); s=sum(ratio); ans=total*ratio[0]//s
                q=f'{total} саны {ratio[0]}:{ratio[1]} қатынасында бөлінді. Кіші бөлік?'; ds=[total*ratio[1]//s,total//s,ans+total//s,ratio[0]*ratio[1]]
            else:
                n=rnd.randint(4,9); ans=n*(n-1)*(n-2)//6
                q=f'{n} нүктеден үш нүктені таңдап, үшбұрыш құрудың саны (ешбір үшеуі бір түзуде емес)?'; ds=[n*(n-1)//2,n**3,ans+n,ans-1]
        else:
            if t==0:
                x=rnd.randint(3,10); ans=2*x*x-5*x+3
                q=f'x={x} болса, 2x²−5x+3 мәнін тап.'; ds=[2*x*x-5*x,2*x*x+5*x+3,ans+x,ans-3]
            elif t==1:
                n=rnd.randint(5,10); k=2; ans=n*(n-1)//2
                q=f'{n} элементтен 2 элементті ретсіз таңдаудың саны?'; ds=[n*n,n*(n-1),n+2,ans+n]
            elif t==2:
                a=rnd.randint(2,7); b=rnd.randint(1,5); x=rnd.randint(3,9); rhs=a*x-b; ans=x
                q=f'{a}x−{b}={rhs}. x=?'; ds=[x+1,x-1,rhs//a,rhs+b]
            elif t==3:
                a=rnd.randint(2,6); b=rnd.randint(2,6); ans=a*a+b*b
                q=f'Вектордың координаталары ({a}; {b}). Ұзындығының квадраты?'; ds=[(a+b)**2,a*b,2*(a+b),ans+a]
            elif t==4:
                base=rnd.randint(100,300); pct=rnd.choice([10,20,25]); ans=base*(100-pct)//100
                q=f'{base} саны {pct}% кеміді. Нәтиже?'; ds=[base*pct//100,base*(100+pct)//100,base-pct,ans+pct]
            elif t==5:
                a=rnd.randint(2,6); n=rnd.randint(4,7); ans=(a**n-1)//(a-1)
                q=f'1+{a}+{a}²+...+{a}^{n-1} қосындысы?'; ds=[a**n,ans-1,ans+a,n*a]
            elif t==6:
                m=rnd.randint(2,7); n=rnd.randint(2,7); ans=m*n
                q=f'Бір әрекет үшін {m} әдіс, одан кейінгі тәуелсіз әрекет үшін {n} әдіс бар. Екі әрекетті орындау жолдарының саны?'; ds=[m+n,m**n,n**m,ans+1]
            elif t==7:
                a=rnd.randint(3,9); b=rnd.randint(3,9); ans=a*b//__import__('math').gcd(a,b)
                q=f'{a} және {b} сандарының ең кіші ортақ еселігін тап.'; ds=[a*b,__import__('math').gcd(a,b),a+b,max(a,b)]
            elif t==8:
                n=rnd.randint(5,10); ans=(n-2)*180
                q=f'{n}-бұрыштың ішкі бұрыштарының қосындысы?'; ds=[n*180,(n-1)*180,360,ans-180]
            else:
                a=rnd.randint(2,7); b=rnd.randint(a+2,12); ans=b*b-a*a
                q=f'Қабырғалары {a} және {b} квадраттардың аудандарының айырмасы?'; ds=[(b-a)**2,b-a,a*a+b*b,2*(a+b)]
        ops, correct=options(ans,ds)
        # bilingual original wording: Russian is a concise translated variant created here, not copied from the sample.
        bank.append({'id':f'g{grade}q{i}','grade':grade,'points':level,'kk':q,'ru':ru_question(q),'options':ops,'answer':correct})
    return bank
BANK={g:make_bank(g) for g in range(1,12)}

# A more puzzle-oriented bank for grades 1–2. These are original tasks inspired only by
# the general Kangaroo-style skills visible in the user's sample (patterns, spatial/logical
# reasoning, counting and multi-step arithmetic), not copies of the sample problems.
def make_early_bank(grade:int):
    rnd=random.Random(9100+grade)
    out=[]
    for i in range(1,31):
        level=3 if i<=10 else (4 if i<=20 else 5)
        t=(i-1)%10
        boost=(i-1)//10
        if t==0:
            a=2+grade+boost; b=a+2; c=b+3; ans=c+2
            kk=f'Сандар кезекпен +2, +3 қадамымен өседі: {a}, {b}, {c}, ... Келесі сан қандай?'
            ru=f'Числа растут по очереди на +2, +3: {a}, {b}, {c}, ... Какое число следующее?'
            ds=[c+3,c+1,c+4,b+2]
        elif t==1:
            total=12+grade*3+boost*4; first=3+boost; second=4+grade; ans=total-first-second
            kk=f'Қорапта {total} фишка болды. Айша {first} фишканы, Дамир {second} фишканы алды. Қалғанын екіге бөлмей-ақ сана: қорапта неше фишка қалды?'
            ru=f'В коробке было {total} фишек. Айша взяла {first}, а Дамир — {second}. Сколько фишек осталось в коробке?'
            ds=[total-first,total-second,ans+1,ans-1]
        elif t==2:
            x=3+grade+boost; ans=x+2
            kk=f'Аружан қатарда сол жақтан {x}-орында тұр. Оның дәл алдында 2 бала бар деп емес, ол екі орын алға жылжыды. Енді сол жақтан нешінші орында?'
            ru=f'Аружан стоит {x}-й слева. Она переставилась на два места вперёд. Какой по счёту слева она стала?'
            ans=max(1,x-2); ds=[x+2,x-1,x+1,2]
        elif t==3:
            n=3+grade+boost; ans=n*(n-1)//2
            kk=f'{n} бала бір-бірімен бір реттен қол алысты. Барлығы неше қол алысу болды?'
            ru=f'{n} детей пожали друг другу руки по одному разу. Сколько всего было рукопожатий?'
            ds=[n,n*(n+1)//2,2*n,ans+1]
        elif t==4:
            rows=2+grade; cols=3+boost+grade; removed=grade+boost; ans=rows*cols-removed
            kk=f'Тақтада {rows} қатар, әр қатарда {cols} жұлдыздан бар. {removed} жұлдыз өшірілді. Неше жұлдыз қалды?'
            ru=f'На доске {rows} рядов, в каждом по {cols} звёзд. {removed} звезды стёрли. Сколько звёзд осталось?'
            ds=[rows+cols-removed,rows*cols+removed,ans+rows,ans-1]
        elif t==5:
            start=1+boost; step1=2+grade; step2=1+boost; ans=start+step1+step2+step1
            kk=f'Робот {start} санынан бастады: алдымен +{step1}, кейін +{step2}, қайтадан +{step1} қадам жасайды. Соңында қай санға келеді?'
            ru=f'Робот начал с числа {start}: сначала +{step1}, затем +{step2}, затем снова +{step1}. На каком числе он остановится?'
            ds=[start+step1+step2,ans+step2,ans-step1,step1*2+step2]
        elif t==6:
            a=7+grade+boost; b=a-2; move=2+boost; ans=(a-move)-(b+move)
            # answer can be negative; ask difference after transfer using absolute value
            ans=abs(ans)
            kk=f'Бір табақта {a} алма, екіншісінде {b} алма. Бірінші табақтан екіншісіне {move} алма ауыстырды. Екі табақтағы алма санының айырмасы енді қанша?'
            ru=f'На одной тарелке {a} яблок, на другой {b}. С первой на вторую переложили {move} яблока. Какова теперь разница в числе яблок?'
            ds=[abs(a-b),ans+2,move,ans+1]
        elif t==7:
            n=4+grade+boost; ans=n+1
            kk=f'Баспалдақта {n} басқыш бар. Төменнен жоғары көтерілгенде әр басқышқа бір рет аяқ басып, ең соңында жоғарғы алаңға шығады. Бастапқы еденді санамасақ, неше жаңа деңгейге көтеріледі?'
            ru=f'У лестницы {n} ступеней. Поднимаясь снизу, ребёнок наступает на каждую ступень и затем выходит на верхнюю площадку. Не считая нижний пол, на сколько новых уровней он поднимется?'
            ds=[n,n-1,n+2,2*n]
        elif t==8:
            a=2+grade; b=3+boost; total=2*a+2*b; ans=total
            kk=f'Тіктөртбұрыштың екі ұзын қабырғасының әрқайсысы {a} тор, екі қысқа қабырғасының әрқайсысы {b} тор. Шекарасы бойымен барлығы неше торлық қадам бар?'
            ru=f'У прямоугольника две стороны по {a} клетки и две стороны по {b} клетки. Сколько клеточных шагов составляет вся граница?'
            ds=[a*b,a+b,total-2,total+2]
        else:
            total=10+grade*2+boost*2; red=3+boost; blue=2+grade; ans=total-red-blue
            kk=f'Қапшықта барлығы {total} шар бар. Оның {red}-і қызыл, {blue}-і көк, қалғаны сары. Сары шар нешеу?'
            ru=f'В мешке всего {total} шаров. {red} из них красные, {blue} синие, остальные жёлтые. Сколько жёлтых шаров?'
            ds=[total-red,total-blue,red+blue,ans+2]
        ops,correct=options(ans,ds)
        out.append({'id':f'g{grade}q{i}','grade':grade,'points':level,'kk':kk,'ru':ru,'options':ops,'answer':correct})
    return out

BANK[1]=make_early_bank(1)
BANK[2]=make_early_bank(2)

class Registration(BaseModel):
    lang: str = Field(pattern='^(kk|ru)$')
    full_name: str = Field(min_length=3, max_length=120)
    phone: str = Field(min_length=7, max_length=30)
    region: str = Field(min_length=2, max_length=100)
    locality: str = Field(min_length=2, max_length=100)
    school: str = Field(min_length=2, max_length=180)
    grade: int = Field(ge=1, le=11)

class PaymentMark(BaseModel):
    token: str

class SubmitTest(BaseModel):
    token: str
    answers: dict[str,str]

class AdminAction(BaseModel):
    password: str
    token: str
    action: str

@app.get('/', response_class=HTMLResponse)
def home():
    return (BASE/'static/index.html').read_text(encoding='utf-8')

@app.get('/admin', response_class=HTMLResponse)
def admin_page():
    return (BASE/'static/admin.html').read_text(encoding='utf-8')

@app.post('/api/register')
def register(r: Registration):
    token=secrets.token_urlsafe(18)
    now=datetime.now(timezone.utc).isoformat()
    with db() as c:
        c.execute('INSERT INTO participants(token,lang,full_name,phone,region,locality,school,grade,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                  (token,r.lang,r.full_name.strip(),r.phone.strip(),r.region.strip(),r.locality.strip(),r.school.strip(),r.grade,now))
    return {'token':token,'price':PRICE,'pay_url':PAY_URL}

@app.post('/api/payment-mark')
def payment_mark(x: PaymentMark):
    with db() as c:
        row=c.execute('SELECT * FROM participants WHERE token=?',(x.token,)).fetchone()
        if not row: raise HTTPException(404,'Participant not found')
        if row['payment_status']=='unpaid': c.execute("UPDATE participants SET payment_status='pending' WHERE token=?",(x.token,))
    return {'ok':True}

@app.get('/api/status/{token}')
def status(token:str):
    with db() as c: row=c.execute('SELECT * FROM participants WHERE token=?',(token,)).fetchone()
    if not row: raise HTTPException(404,'Participant not found')
    d=dict(row); d.pop('question_ids',None)
    return d

@app.get('/api/test/{token}')
def get_test(token:str):
    with db() as c:
        row=c.execute('SELECT * FROM participants WHERE token=?',(token,)).fetchone()
        if not row: raise HTTPException(404,'Participant not found')
        if row['payment_status']!='paid': raise HTTPException(403,'Payment not approved')
        if row['submitted_at']: raise HTTPException(409,'Attempt already used')
        qids=row['question_ids']
        if not qids:
            ids=[q['id'] for q in BANK[row['grade']]]
            rnd=random.Random(token); rnd.shuffle(ids)
            qids=','.join(ids)
            c.execute('UPDATE participants SET question_ids=?,started_at=? WHERE token=?',(qids,datetime.now(timezone.utc).isoformat(),token))
        ids=qids.split(',')
    qmap={q['id']:q for q in BANK[row['grade']]}
    lang=row['lang']
    out=[]
    for qid in ids:
        q=qmap[qid]
        out.append({'id':q['id'],'text':q[lang],'options':q['options'],'points':q['points']})
    started = datetime.fromisoformat(row['started_at']) if row['started_at'] else datetime.now(timezone.utc)
    elapsed = max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
    seconds_left = max(0, TEST_SECONDS - elapsed)
    return {'questions':out,'minutes':30,'seconds_left':seconds_left,'full_name':row['full_name'],'grade':row['grade'],'lang':lang}

@app.post('/api/submit')
def submit(s: SubmitTest):
    with db() as c:
        row=c.execute('SELECT * FROM participants WHERE token=?',(s.token,)).fetchone()
        if not row: raise HTTPException(404,'Participant not found')
        if row['submitted_at']: raise HTTPException(409,'Attempt already used')
        if row['payment_status']!='paid': raise HTTPException(403,'Payment not approved')
        if not row['started_at']: raise HTTPException(409,'Test was not started')
        started = datetime.fromisoformat(row['started_at'])
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        if elapsed > TEST_SECONDS + GRACE_SECONDS:
            # Late submission is still finalized, but unanswered/late payload is ignored.
            s.answers = {}
        qmap={q['id']:q for q in BANK[row['grade']]}
        qids=(row['question_ids'] or '').split(',')
        score=sum(1 for qid in qids if qid and s.answers.get(qid)==qmap[qid]['answer'])
        award='I орын' if score>=26 else ('II орын' if score>=21 else ('III орын' if score>=16 else 'Қатысушы сертификаты'))
        diploma=f"KENG-2026-{row['id']:06d}"
        now=datetime.now(timezone.utc).isoformat()
        c.execute('UPDATE participants SET submitted_at=?,score=?,award=?,diploma_no=? WHERE token=?',(now,score,award,diploma,s.token))
    return {'score':score,'award':award,'diploma_no':diploma}

@app.post('/api/admin/action')
def admin_action(a: AdminAction):
    if not secrets.compare_digest(a.password, ADMIN_PASSWORD): raise HTTPException(401,'Wrong password')
    if a.action not in {'approve','reject'}: raise HTTPException(400,'Bad action')
    status='paid' if a.action=='approve' else 'unpaid'
    with db() as c:
        c.execute('UPDATE participants SET payment_status=? WHERE token=?',(status,a.token))
    return {'ok':True}

@app.get('/api/admin/list')
def admin_list(password:str):
    if not secrets.compare_digest(password, ADMIN_PASSWORD): raise HTTPException(401,'Wrong password')
    with db() as c: rows=c.execute('SELECT * FROM participants ORDER BY id DESC LIMIT 500').fetchall()
    return [dict(r) for r in rows]
