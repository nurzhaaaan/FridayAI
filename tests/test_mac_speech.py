import http.client
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from http.server import ThreadingHTTPServer
import mac_speech
from server import Handler

AUDIO = b'RIFF' + b'\0' * 44


class MacSpeechTests(unittest.TestCase):
    @patch('mac_speech.available', return_value=True)
    @patch('mac_speech.subprocess.run')
    def test_native_commands_and_temp_cleanup(self, run, available):
        def execute(args, **kwargs):
            if args[-1] == '?':
                return SimpleNamespace(stdout='Milena             ru_RU    # test\nSamantha           en_US    # test\n')
            if args[0] == '/usr/bin/afconvert':
                Path(args[-1]).write_bytes(AUDIO)
            return SimpleNamespace(stdout='')
        run.side_effect=execute
        audio, locale=mac_speech.synthesize('Сәлем; $(echo should-not-run)', 'kk-KZ')
        self.assertEqual(locale,'ru_RU')
        self.assertEqual(audio,AUDIO)
        say_args=run.call_args_list[1].args[0]
        self.assertEqual(say_args[:3], ['/usr/bin/say','-v','Milena'])
        self.assertNotIn('$(echo should-not-run)',say_args)
        self.assertFalse(Path(say_args[4]).exists())
        self.assertNotIn('shell',run.call_args.kwargs)

    @patch('mac_speech.available', return_value=True)
    def test_validation(self, available):
        for text,lang in [('', 'ru-RU'),('x'*12001,'ru-RU'),('hello','bad-language')]:
            with self.assertRaises(ValueError): mac_speech.synthesize(text,lang)

    def test_http_audio_route(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(payload,origin=None):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
            c.request('POST','/api/speech',json.dumps(payload),headers={'Origin':origin} if origin else {})
            r=c.getresponse();result=r.status,r.read(),dict(r.getheaders());c.close();return result
        try:
            with patch('mac_speech.available',return_value=True), patch('mac_speech.synthesize',return_value=(AUDIO,'ru_RU')) as synth:
                status,body,headers=request({'text':'Hello','language':'ru-RU'})
                self.assertEqual(status,200);self.assertEqual(body,AUDIO)
                self.assertEqual(headers['Content-Type'],'audio/wav')
                self.assertEqual(headers['X-Friday-Voice-Language'],'ru_RU')
                self.assertIn("media-src 'self' blob:",headers['Content-Security-Policy'])
                self.assertEqual(request({'text':'','language':'ru-RU'})[0],400)
                self.assertEqual(request({'text':'Hello','language':'ru-RU'},'https://evil.example')[0],403)
                synth.assert_called_once()
            with patch('mac_speech.available',return_value=False):
                self.assertEqual(request({'text':'Hello','language':'ru-RU'})[0],503)
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__ == '__main__': unittest.main()
