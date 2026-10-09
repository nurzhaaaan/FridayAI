"""Run the local Friday web app with python server.py."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import ai_core

WEB = Path(__file__).resolve().parent / 'web'
SLOTS = threading.BoundedSemaphore(4)


def validate_messages(payload):
    if not isinstance(payload, dict):
        raise ValueError('Invalid payload')
    messages = payload.get('messages')
    if not isinstance(messages, list) or not 1 <= len(messages) <= 40:
        raise ValueError('Invalid messages')
    clean = []
    for message in messages:
        if not isinstance(message, dict) or message.get('role') not in ('user', 'assistant'):
            raise ValueError('Invalid role')
        content = message.get('content')
        if not isinstance(content, str) or not content.strip() or len(content) > 12000:
            raise ValueError('Invalid content')
        clean.append({'role': message['role'], 'content': content.strip()})
    if clean[-1]['role'] != 'user':
        raise ValueError('Last message must be from user')
    return clean


class Handler(BaseHTTPRequestHandler):
    def headers_out(self, mime, length):
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(length))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        self.end_headers()

    def reply(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.headers_out('application/json; charset=utf-8', len(body))
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/status':
            return self.reply(200, ai_core.status())
        files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path not in files:
            return self.reply(404, {'error': 'Табылмады.'})
        filename, mime = files[path]
        body = (WEB / filename).read_bytes()
        self.send_response(200)
        self.headers_out(mime, len(body))
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/chat':
            return self.reply(404, {'error': 'Табылмады.'})
        origin = self.headers.get('Origin')
        host = self.headers.get('Host', '')
        if origin and origin not in ('http://' + host, 'https://' + host):
            return self.reply(403, {'error': 'Origin rejected.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 100000:
                return self.reply(413, {'error': 'Сұрау тым үлкен немесе бос.'})
            messages = validate_messages(json.loads(self.rfile.read(length)))
        except (ValueError, UnicodeError):
            return self.reply(400, {'error': 'Хабарлама форматы қате (шегі: 12 000 таңба, 40 хабарлама).'})
        if not ai_core.configured():
            return self.reply(503, {'error': 'AI қосылмаған. ' + ai_core.status()['detail']})
        if not SLOTS.acquire(blocking=False):
            return self.reply(429, {'error': 'Сервер бос емес. Сәл кейін қайталаңыз.'})
        try:
            self.reply(200, {'answer': ai_core.chat(messages)})
        except Exception as exc:
            print('AI request failed:', type(exc).__name__, flush=True)
            errors = {'AuthenticationError': 'API кілті жарамсыз.', 'RateLimitError': 'API лимиті немесе баланс шектеуі.', 'APITimeoutError': 'Жауап күту уақыты аяқталды.'}
            self.reply(502, {'error': errors.get(type(exc).__name__, 'AI қызметіне қосылу мүмкін болмады. Ollama іске қосылғанын немесе API байланысын тексеріңіз.')})
        finally:
            SLOTS.release()


def main():
    host, port = os.getenv('FRIDAY_HOST', '127.0.0.1'), int(os.getenv('PORT', '8000'))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f'Friday listening on {host}:{port}; AI configured: {ai_core.configured()}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
