import json
import sqlite3
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from backend import playground as p


class PlaygroundTests(unittest.TestCase):
    def test_original_database_result(self):
        with sqlite3.connect(p.DB.as_uri() + '?mode=ro', uri=True) as conn:
            expected = conn.execute("SELECT COUNT(*) FROM Ingresos WHERE FechaIngreso >= '2026-08-01' AND FechaIngreso < '2026-09-01'").fetchone()[0]
        rows, _, _ = p.execute('SELECT SUM(ingresos) AS total FROM consulta_ingresos WHERE fecha >= :start AND fecha < :end', {'start': '2026-08-01', 'end': '2026-09-01'})
        self.assertEqual(rows, [{'total': expected}])

    def test_unsafe_sql_blocked(self):
        for sql in ['DELETE FROM Ingresos', 'SELECT * FROM Paciente',
                    'SELECT * FROM consulta_ingresos; SELECT 1',
                    'SELECT * FROM main.consulta_ingresos',
                    'SELECT (SELECT NombrePaciente FROM Paciente) FROM consulta_ingresos',
                    'WITH x AS (SELECT * FROM consulta_ingresos) SELECT * FROM x',
                    "SELECT load_extension('x') FROM consulta_ingresos",
                    'SELECT randomblob(100000000) FROM consulta_ingresos']:
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                p.execute(sql, {})

    def test_parameter_binding(self):
        rows, _, _ = p.execute('SELECT SUM(ingresos) AS total FROM consulta_ingresos WHERE via = :via', {'via': "x' OR 1=1 --"})
        self.assertIsNone(rows[0]['total'])

    def test_api_sql_visibility_and_real_execution(self):
        plan = p.Plan(status='ok', sql='SELECT SUM(ingresos) AS total FROM consulta_ingresos', message='Ingresos')
        with patch.object(p, 'generate', AsyncMock(return_value=(plan, 'test-model'))):
            with TestClient(p.app) as client:
                response = client.post('/api/query', json={'question': 'total de ingresos'})
                data = response.json()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(data['sql'], plan.sql)
                self.assertTrue(data['executed'])
                self.assertEqual(data['database'], 'hospital.db')
                self.assertEqual(data['rows'][0]['total'], 17781)

    def test_occupancy_not_fabricated_even_if_model_wrong(self):
        plan = p.Plan(status='ok', sql='SELECT SUM(ingresos) AS ocupadas FROM consulta_ingresos', message='Ocupación')
        with patch.object(p, 'generate', AsyncMock(return_value=(plan, 'test-model'))):
            with TestClient(p.app) as client:
                data = client.post('/api/query', json={'question': 'camas UCI ocupadas hoy'}).json()
                self.assertEqual(data['status'], 'insufficient_data')
                self.assertFalse(data['executed'])
                self.assertEqual(data['rows'], [])

    def test_foreign_origin_rejected(self):
        with TestClient(p.app) as client:
            r = client.post('/api/query', json={'question': 'ingresos'}, headers={'Origin': 'https://other.example'})
            self.assertEqual(r.status_code, 403)

    def test_invalid_question(self):
        with TestClient(p.app) as client:
            self.assertEqual(client.post('/api/query', json={'question': ''}).status_code, 422)


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_cloud_transport_and_secret_not_returned(self):
        original = httpx.AsyncClient
        def handler(request):
            self.assertEqual(str(request.url), 'https://provider.example/v1/chat/completions')
            self.assertEqual(request.headers['authorization'], 'Bearer test-secret')
            body = json.loads(request.content)
            self.assertEqual(body['model'], 'any-model')
            self.assertNotIn('temperature', body)
            self.assertNotIn('max_tokens', body)
            self.assertNotIn('response_format', body)
            return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'status': 'ok', 'sql': 'SELECT SUM(ingresos) AS total FROM consulta_ingresos', 'message': 'Total'})}}]})
        with patch.object(p.httpx, 'AsyncClient', side_effect=lambda **kw: original(transport=httpx.MockTransport(handler), **kw)):
            plan, model = await p.generate(p.Question(question='total ingresos', provider='cloud', cloud=p.Connection(base_url='https://provider.example/v1', model='any-model', api_key='test-secret', json_mode=False, temperature=None, max_tokens=None)))
        self.assertEqual(plan.status, 'ok')
        self.assertNotIn('test-secret', plan.model_dump_json())

    async def test_local_payload(self):
        original = httpx.AsyncClient
        def handler(request):
            body = json.loads(request.content)
            self.assertFalse(body['think'])
            self.assertEqual(body['model'], 'qwen3:4b')
            self.assertEqual(body['format'], 'json')
            return httpx.Response(200, json={'message': {'content': '{"status":"clarify","message":"Indica el periodo"}'}})
        with patch.object(p.httpx, 'AsyncClient', side_effect=lambda **kw: original(transport=httpx.MockTransport(handler), **kw)):
            plan, _ = await p.generate(p.Question(question='consulta ambigua'))
        self.assertEqual(plan.status, 'clarify')


if __name__ == '__main__':
    unittest.main()
