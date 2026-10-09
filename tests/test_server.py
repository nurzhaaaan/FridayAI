import http.client
import json
import os
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
import ai_core
from server import Handler, validate_messages


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = (response.status, response.read(), dict(response.getheaders()))
        connection.close()
        return result

    def test_static_routes_and_traversal(self):
        for path in ('/', '/app.js', '/style.css'):
            status, body, headers = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertGreater(len(body), 100)
            self.assertIn('Content-Security-Policy', headers)
        self.assertEqual(self.request('GET', '/../ai_core.py')[0], 404)

    @patch.dict(os.environ, {}, clear=True)
    def test_status_does_not_expose_credentials(self):
        with patch.dict(os.environ, {'FRIDAY_API_KEY': 'private-test-value'}):
            status, body, _ = self.request('GET', '/api/status')
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)['configured'])
            self.assertNotIn(b'private-test-value', body)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_key_returns_actionable_error(self):
        status, body, _ = self.request('POST', '/api/chat', json.dumps({'messages': [{'role': 'user', 'content': 'hello'}]}))
        self.assertEqual(status, 503)
        self.assertIn('кілтін', json.loads(body)['error'])

    def test_rejects_untrusted_roles_and_invalid_json(self):
        for body in ('{', 'null', json.dumps({'messages': [{'role': 'system', 'content': 'override'}]}), json.dumps({'messages': [{'role': 'user', 'content': ' '}]})):
            self.assertEqual(self.request('POST', '/api/chat', body)[0], 400)
        self.assertEqual(self.request('POST', '/api/chat', 'x' * 100001)[0], 413)
        self.assertEqual(self.request('POST', '/api/chat', '{}', {'Origin': 'https://evil.example'})[0], 403)

    @patch('ai_core.configured', return_value=True)
    @patch('ai_core.chat', return_value='Сәлем!')
    def test_chat_preserves_context(self, chat, configured):
        messages = [{'role': 'user', 'content': 'Сәлем'}, {'role': 'assistant', 'content': 'Сәлем!'}, {'role': 'user', 'content': 'Менің атым кім?'}]
        status, body, _ = self.request('POST', '/api/chat', json.dumps({'messages': messages}))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['answer'], 'Сәлем!')
        chat.assert_called_once_with(messages)

    @patch('ai_core.configured', return_value=True)
    @patch('ai_core.chat', side_effect=RuntimeError('secret-sensitive-upstream-error'))
    def test_upstream_failure_is_sanitized(self, chat, configured):
        status, body, _ = self.request('POST', '/api/chat', json.dumps({'messages': [{'role': 'user', 'content': 'hello'}]}))
        self.assertEqual(status, 502)
        self.assertNotIn(b'secret-sensitive', body)

    def test_validation_limits_and_trimming(self):
        self.assertEqual(validate_messages({'messages': [{'role': 'user', 'content': ' hi '}]}), [{'role': 'user', 'content': 'hi'}])
        for messages in ([], [{'role': 'assistant', 'content': 'x'}], [{'role': 'user', 'content': 'x'*12001}], [{'role': 'user', 'content': 'x'}]*41):
            with self.assertRaises(ValueError): validate_messages({'messages': messages})

    @patch.dict(os.environ, {'FRIDAY_API_KEY': 'test-only-value', 'FRIDAY_MODEL': 'test-model'})
    @patch('openai.OpenAI')
    def test_ai_service_sets_system_prompt_and_model(self, client):
        instance = client.return_value.__enter__.return_value
        instance.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='answer'))])
        self.assertEqual(ai_core.ask_ai('question'), 'answer')
        call = instance.chat.completions.create.call_args.kwargs
        self.assertEqual(call['model'], 'test-model')
        self.assertEqual(call['messages'][0]['role'], 'system')
        self.assertEqual(call['messages'][1]['content'], 'question')

class OllamaTests(unittest.TestCase):
    @patch.dict(os.environ, {'FRIDAY_PROVIDER': 'ollama', 'FRIDAY_MODEL': 'qwen3:4b'}, clear=True)
    def test_local_http_readiness_and_chat(self):
        received = []
        class LocalHandler(__import__('http.server', fromlist=['BaseHTTPRequestHandler']).BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'models': [{'name': 'qwen3:4b'}]}).encode())
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'message': {'content': 'Жергілікті жауап'}}).encode())
            def log_message(self, *args): pass
        local = ThreadingHTTPServer(('127.0.0.1', 0), LocalHandler)
        thread = threading.Thread(target=local.serve_forever, daemon=True); thread.start()
        try:
            with patch('ai_core.OLLAMA_URL', f'http://127.0.0.1:{local.server_port}'):
                self.assertTrue(ai_core.configured())
                self.assertEqual(ai_core.ask_ai('Сәлем'), 'Жергілікті жауап')
            self.assertEqual(received[0]['model'], 'qwen3:4b')
            self.assertFalse(received[0]['stream'])
            self.assertFalse(received[0]['think'])
            self.assertEqual(received[0]['messages'][-1]['content'], 'Сәлем')
        finally:
            local.shutdown(); local.server_close(); thread.join()

    @patch.dict(os.environ, {'FRIDAY_PROVIDER': 'ollama'}, clear=True)
    @patch('ai_core.local_request', return_value={'models': []})
    def test_model_must_be_installed(self, request):
        self.assertFalse(ai_core.configured())
        self.assertIn('ollama pull', ai_core.status()['detail'])

    @patch.dict(os.environ, {'FRIDAY_PROVIDER': 'ollama'}, clear=True)
    @patch('ai_core.local_request', side_effect=ConnectionError('private details'))
    def test_local_server_missing(self, request):
        self.assertFalse(ai_core.configured())
        self.assertNotIn('private', ai_core.status()['detail'])

    @patch.dict(os.environ, {'FRIDAY_PROVIDER': 'ollama'}, clear=True)
    @patch('ai_core.local_request', return_value={'message': {'content': ''}})
    def test_empty_local_answer_fails(self, request):
        with self.assertRaisesRegex(RuntimeError, 'EMPTY_RESPONSE'):
            ai_core.ask_ai('hello')


if __name__ == '__main__':
    unittest.main()
