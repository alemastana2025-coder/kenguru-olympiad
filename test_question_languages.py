"""Run with: python -I -m unittest discover -s . -p test_question_languages.py -v

Requires requirements.txt and httpx. All participant records and database writes
are confined to temporary SQLite files, never the production database.
"""
import copy
import importlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from fastapi.testclient import TestClient


class QuestionLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        source = Path(__file__).resolve().parent
        for name in ('main.py', 'admin_extra.py', 'question_bank_final.py', 'question_languages.py',
                     'document_image.py', 'diploma_template.png', 'certificate_template.png'):
            shutil.copy2(source / name, cls.root / name)
        sys.path.insert(0, str(cls.root))
        cls.main = importlib.import_module('main')
        cls.admin = importlib.import_module('admin_extra')
        cls.bank = importlib.import_module('question_bank_final').BANK
        cls.labels = importlib.import_module('question_languages')
        cls.documents = importlib.import_module('document_image')
        cls.admin.register_admin_extra(cls.main.app)

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(cls.root))
        cls.temp.cleanup()

    def setUp(self):
        self.main.DB = self.root / (self._testMethodName + '.sqlite3')
        self.main.init_db()
        self.admin._tables(self.main)
        with self.main.db() as c:
            c.execute('CREATE TABLE app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            c.execute('INSERT INTO app_meta VALUES (?, ?)', ('question_bank_version', 'reviewed-330-v1'))
        self.client = TestClient(self.main.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def participant(self, token, grade=1, lang='ru', payment='paid', started=False, submitted=False):
        now = datetime.now(timezone.utc)
        qids = ','.join(q['id'] for q in reversed(self.bank[grade])) if started else None
        with self.main.db() as c:
            c.execute('''INSERT INTO participants
                (token,lang,full_name,phone,region,locality,school,grade,payment_status,
                 created_at,started_at,question_ids,submitted_at,score,award,diploma_no)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (token, lang, 'LOCAL TEST', '00000000000', 'Test', 'Test', 'Test', grade,
                 payment, now.isoformat(), (now-timedelta(minutes=1)).isoformat() if started else None,
                 qids, now.isoformat() if submitted else None, 27 if submitted else None,
                 'I орын' if submitted else None, 'LOCAL-' + token if submitted else None))

    def test_all_330_questions_have_complete_labels_and_unchanged_keys(self):
        before = copy.deepcopy(self.bank)
        neutral_words = {'А', 'Б', 'В', 'Алия', 'Аян', 'Бекзат', 'Бота', 'Данияр', 'Дина',
                         'ось Ox', 'параллель', 'перпендикуляр'}
        self.assertEqual(sum(map(len, self.bank.values())), 330)
        for questions in self.bank.values():
            for q in questions:
                for lang in ('kk', 'ru'):
                    labels = self.labels.localized_options(q, lang)
                    self.assertEqual(len(labels), len(q['options']))
                    self.assertEqual(len(set(labels)), len(labels), q['id'])
                    for original, label in zip(q['options'], labels):
                        expected = original == q['answer']
                        self.assertEqual(self.labels.answer_is_correct(q, label, lang), expected, (q['id'], lang, label))
                        self.assertEqual(self.labels.answer_is_correct(q, original, lang), expected, (q['id'], lang, original))
                        if lang == 'ru' and re.search('[А-Яа-яӘәҒғҚқҢңӨөҰұҮүІіЁё]', original):
                            self.assertTrue(original in self.labels.RU_OPTIONS or original in neutral_words
                                            or re.fullmatch(r'\d+ см', original), (q['id'], original))
                    self.assertFalse(self.labels.answer_is_correct(q, None, lang))
                    self.assertFalse(self.labels.answer_is_correct(q, 'invalid', lang))
        self.assertEqual(self.bank, before)
        self.assertIn('Ox осі', self.labels.localized_options(self.bank[6][7], 'kk'))

    def test_russian_examples(self):
        self.participant('russian')
        response = self.client.get('/api/test/russian')
        self.assertEqual(response.status_code, 200)
        questions = {q['id']: q for q in response.json()['questions']}
        self.assertEqual(questions['g1q8']['text'], 'Сегодня вторник. Какой день недели будет через 3 дня?')
        self.assertEqual(questions['g1q8']['options'], ['четверг', 'суббота', 'пятница', 'среда', 'воскресенье'])
        self.assertEqual(questions['g1q26']['options'], ['4 и 8', '7 и 7', '5 и 6', '6 и 7', '3 и 9'])
        self.assertNotIn('answer', questions['g1q8'])

    def test_both_languages_score_correctly_for_every_grade(self):
        for grade in range(1, 12):
            for lang in ('kk', 'ru'):
                for legacy in (False, True):
                    token = f'{grade}-{lang}-{legacy}'
                    with self.subTest(token=token):
                        self.participant(token, grade, lang)
                        response = self.client.get('/api/test/' + token)
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.json()['lang'], lang)
                        source = {q['id']: q for q in self.bank[grade]}
                        answers = {}
                        for q in response.json()['questions']:
                            original = source[q['id']]
                            self.assertEqual(q['text'], original[lang])
                            self.assertEqual(q['options'], self.labels.localized_options(original, lang))
                            index = original['options'].index(original['answer'])
                            answers[q['id']] = original['answer'] if legacy else q['options'][index]
                        result = self.client.post('/api/submit', json={'token': token, 'answers': answers})
                        self.assertEqual(result.status_code, 200)
                        self.assertEqual(result.json()['score'], 30)
                        status = self.client.get('/api/status/' + token).json()
                        self.assertEqual(status['score'], 30)
                        self.assertEqual(status['payment_status'], 'paid')

    def test_wrong_and_missing_answers_are_not_awarded_points(self):
        for lang in ('kk', 'ru'):
            self.participant(lang, 1, lang)
            questions = self.client.get('/api/test/' + lang).json()['questions']
            source = {q['id']: q for q in self.bank[1]}
            answers = {}
            for q in questions[:15]:
                original = source[q['id']]
                correct = original['options'].index(original['answer'])
                answers[q['id']] = q['options'][(correct+1) % len(q['options'])]
            result = self.client.post('/api/submit', json={'token': lang, 'answers': answers})
            self.assertEqual(result.json()['score'], 0)

    def test_existing_attempts_payments_and_results_are_preserved(self):
        self.participant('active', started=True)
        self.participant('completed', started=True, submitted=True)
        self.participant('pending', payment='pending')
        self.participant('unpaid', payment='unpaid')
        with self.main.db() as c:
            before = [dict(r) for r in c.execute('SELECT * FROM participants ORDER BY id')]
        response = self.client.get('/api/test/active')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([q['id'] for q in response.json()['questions']], before[0]['question_ids'].split(','))
        self.assertLess(response.json()['seconds_left'], 1800)
        self.assertEqual(self.client.get('/api/test/completed').status_code, 409)
        self.assertEqual(self.client.get('/api/test/pending').status_code, 403)
        self.assertEqual(self.client.get('/api/test/unpaid').status_code, 403)
        with self.main.db() as c:
            after = [dict(r) for r in c.execute('SELECT * FROM participants ORDER BY id')]
        self.assertEqual(before, after)

    def test_admin_can_correct_participant_without_changing_payment_result_or_diploma(self):
        self.participant('correct-me', grade=4, started=True, submitted=True)
        with self.main.db() as c:
            before = dict(c.execute("SELECT * FROM participants WHERE token='correct-me'").fetchone())

        response = self.client.put('/api/admin/participant/correct-me', json={
            'password': self.main.ADMIN_PASSWORD,
            'full_name': 'ӘЛИХАН СЕРІКҰЛЫ',
            'school': '№99 мектеп-гимназиясы',
            'supervisor': 'АХМЕТОВА АЙГҮЛ СЕРІКҚЫЗЫ',
            'grade': 5,
        })
        self.assertEqual(response.status_code, 200, response.text)

        with self.main.db() as c:
            after = dict(c.execute("SELECT * FROM participants WHERE token='correct-me'").fetchone())
        self.assertEqual(after['full_name'], 'ӘЛИХАН СЕРІКҰЛЫ')
        self.assertEqual(after['school'], '№99 мектеп-гимназиясы')
        self.assertEqual(after['supervisor'], 'АХМЕТОВА АЙГҮЛ СЕРІКҚЫЗЫ')
        self.assertEqual(after['grade'], 5)
        for field in ('payment_status', 'score', 'award', 'diploma_no', 'submitted_at', 'question_ids'):
            self.assertEqual(after[field], before[field], field)

    def test_admin_cannot_change_grade_during_active_attempt_but_can_fix_text(self):
        self.participant('active-edit', grade=3, started=True)
        payload = {
            'password': self.main.ADMIN_PASSWORD,
            'full_name': 'ДҰРЫС АТЫ ЖӨНІ',
            'school': 'Дұрыс мектеп',
            'supervisor': 'ДҰРЫС ЖЕТЕКШІ АТЫ',
            'grade': 4,
        }
        blocked = self.client.put('/api/admin/participant/active-edit', json=payload)
        self.assertEqual(blocked.status_code, 409)
        with self.main.db() as c:
            unchanged = dict(c.execute("SELECT * FROM participants WHERE token='active-edit'").fetchone())
        self.assertEqual(unchanged['grade'], 3)
        self.assertEqual(unchanged['full_name'], 'LOCAL TEST')

        payload['grade'] = 3
        corrected = self.client.put('/api/admin/participant/active-edit', json=payload)
        self.assertEqual(corrected.status_code, 200, corrected.text)
        with self.main.db() as c:
            saved = dict(c.execute("SELECT * FROM participants WHERE token='active-edit'").fetchone())
        self.assertEqual(saved['full_name'], 'ДҰРЫС АТЫ ЖӨНІ')
        self.assertEqual(saved['question_ids'], unchanged['question_ids'])

    def test_cached_document_download_does_not_block_payment_approval(self):
        self.participant('document', grade=5, started=True, submitted=True)
        self.participant('approve-me', payment='pending')
        self.documents._DOCUMENT_CACHE.clear()

        opened = self.client.get('/api/document/document')
        downloaded = self.client.get('/api/document/document?download=1')
        self.assertEqual(opened.status_code, 200, opened.text)
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        self.assertEqual(opened.content[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(opened.content, downloaded.content)
        self.assertEqual(len(self.documents._DOCUMENT_CACHE), 1)
        self.assertEqual(opened.headers['content-length'], str(len(opened.content)))

        approved = self.client.post('/api/admin/action', json={
            'password': self.main.ADMIN_PASSWORD,
            'token': 'approve-me',
            'action': 'approve',
        })
        self.assertEqual(approved.status_code, 200, approved.text)
        with self.main.db() as c:
            row = c.execute("SELECT payment_status FROM participants WHERE token='approve-me'").fetchone()
        self.assertEqual(row['payment_status'], 'paid')

    def test_database_question_overrides_keep_translations_after_admin_save(self):
        question = copy.deepcopy(self.bank[1][7])
        question['ru'] += ' Выберите ответ.'
        payload = {**question, 'password': self.main.ADMIN_PASSWORD}
        result = self.client.put('/api/admin/question/1/g1q8', json=payload)
        self.assertEqual(result.status_code, 200)
        with self.main.db() as c:
            stored = c.execute('SELECT data FROM question_overrides WHERE grade=1').fetchone()['data']
        self.main.BANK = copy.deepcopy(self.bank)
        self.admin._load_overrides(self.main)
        self.participant('overridden')
        questions = self.client.get('/api/test/overridden').json()['questions']
        actual = next(q for q in questions if q['id'] == 'g1q8')
        self.assertEqual(actual['text'], question['ru'])
        self.assertEqual(actual['options'][2], 'пятница')
        self.assertEqual(json.loads(stored)[7]['answer'], 'жұма')
        with self.main.db() as c:
            self.assertEqual(c.execute('SELECT data FROM question_overrides WHERE grade=1').fetchone()['data'], stored)


if __name__ == '__main__':
    unittest.main()
