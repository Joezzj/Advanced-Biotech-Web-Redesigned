"""Mail API regression tests. All outbound SMTP is mocked; no mail is sent."""
import http.client
import json
from pathlib import Path
import smtplib
import sys
import threading
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server

SAMPLE = {
    'name': 'Test Person',
    'email': 'qa@example.com',
    'company': 'Example Lab',
    'interest': 'Samples & testing',
    'product': 'Antibacterial Masterbatch',
    'message': 'Please provide information about material compatibility.',
    'website': '',
}


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = server.Settings()
        cls.settings.rate_max = 1000
        cls.httpd = server.ContactServer(('127.0.0.1', 0), cls.settings)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def setUp(self):
        self.settings.smtp_host = ''
        self.settings.smtp_user = ''
        self.settings.smtp_password = ''
        self.settings.mail_from = ''
        self.settings.mail_to = 'info@advancedbiotech.co.nz'
        self.settings.smtp_mode = 'ssl'
        self.settings.allowed_origins = set()
        self.settings.rate_max = 1000
        self.httpd.attempts.clear()

    def request(self, method='GET', path='/', body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        res = conn.getresponse()
        result = res.status, dict(res.getheaders()), res.read()
        conn.close()
        return result

    def post(self, data, path='/api/contact', headers=None):
        request_headers = {'Content-Type': 'application/json', **(headers or {})}
        return self.request('POST', path, json.dumps(data), request_headers)

    def configured(self):
        self.settings.smtp_host = 'smtp.example.com'
        self.settings.smtp_user = 'sender@example.com'
        self.settings.smtp_password = 'test-only-not-a-real-password'
        self.settings.mail_from = 'sender@example.com'

    def test_all_four_pages_and_asset_are_served(self):
        paths = [
            '/', '/index.html', '/products.html', '/solutions.html', '/contact.html',
            '/assets/images/polymer-hero.webp', '/style.css', '/main.js',
            '/assets/css/home.css', '/assets/css/products.css',
            '/assets/css/solutions.css', '/assets/css/contact.css',
            '/assets/css/responsive.css', '/assets/js/products.js',
            '/assets/js/contact.js', '/assets/fonts/ubuntu-light.woff',
            '/assets/fonts/ubuntu-regular.woff', '/assets/fonts/ubuntu-medium.woff',
            '/assets/fonts/ubuntu-bold.woff',
        ]
        for path in paths:
            with self.subTest(path=path):
                status, headers, content = self.request(path=path)
                self.assertEqual(status, 200)
                self.assertGreater(len(content), 100)
                self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')

    def test_head_has_no_body(self):
        status, headers, content = self.request('HEAD', '/index.html')
        self.assertEqual(status, 200)
        self.assertGreater(int(headers['Content-Length']), 100)
        self.assertEqual(content, b'')

    def test_private_files_and_directories_not_served(self):
        paths = [
            '/.env', '/smtp_config.json', '/main.py', '/server.py', '/assets/',
            '/%2e%2e/server.py', '/../../server.py', '/no-such-file.html',
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.request(path=path)[0], 404)

    def test_unconfigured_frontend_is_draft_mode(self):
        self.assertIn(b'"contactEndpoint": ""', self.request(path='/site-config.js')[2])
        self.assertFalse(json.loads(self.request(path='/api/contact/status')[2])['configured'])

    def test_configured_frontend_uses_relative_endpoint(self):
        self.configured()
        self.assertIn(b'"contactEndpoint": "/api/contact"', self.request(path='/site-config.js')[2])
        self.assertNotIn(self.settings.smtp_password.encode(), self.request(path='/site-config.js')[2])

    def test_missing_smtp_is_honest_503(self):
        status, _, body = self.post(SAMPLE)
        self.assertEqual(status, 503)
        self.assertFalse(json.loads(body)['success'])

    def test_success_requires_smtp_acceptance(self):
        self.configured()
        with patch('server.send_mail') as send:
            status, _, body = self.post(SAMPLE)
            send.assert_called_once()
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)['success'])
            self.assertEqual(send.call_args.args[0]['message'], SAMPLE['message'])

    def test_original_endpoint_remains_compatible(self):
        self.configured()
        with patch('server.send_mail'):
            self.assertEqual(self.post(SAMPLE, '/send_mail')[0], 200)

    def test_smtp_failure_not_reported_as_success(self):
        self.configured()
        with patch('server.send_mail', side_effect=smtplib.SMTPException('private server diagnostic')):
            status, _, body = self.post(SAMPLE)
            self.assertEqual(status, 502)
            self.assertFalse(json.loads(body)['success'])
            self.assertNotIn(b'private server diagnostic', body)

    def test_invalid_email_message_and_header_injection(self):
        invalid_fields = [
            ('name', ' '),
            ('name', 'Joe\r\nBcc: other@example.com'),
            ('email', 'bad@example'),
            ('email', 'a@example.com\r\nBcc: b@example.com'),
            ('message', ' '),
            ('message', 'short'),
            ('message', 'x' * 5001),
            ('name', ['unexpected']),
            ('website', 'spam'),
        ]
        for field, value in invalid_fields:
            with self.subTest(field=field, value=str(value)[:25]):
                self.assertEqual(self.post({**SAMPLE, field: value})[0], 400)

    def test_payload_must_be_object(self):
        for value in [[], None, 'text', 5]:
            self.assertEqual(self.post(value)[0], 400)

    def test_invalid_json_and_invalid_utf8(self):
        for body in ['not json', b'\xff\xff']:
            self.assertEqual(self.request('POST', '/api/contact', body, {'Content-Type': 'application/json'})[0], 400)

    def test_content_type_and_size_limits(self):
        self.assertEqual(self.request('POST', '/api/contact', '{}', {'Content-Type': 'text/plain'})[0], 415)
        status, _, _ = self.request(
            'POST', '/api/contact', 'x' * (server.MAX_BODY + 1),
            {'Content-Type': 'application/json'},
        )
        self.assertEqual(status, 413)

    def test_unknown_api_route(self):
        self.assertEqual(self.post(SAMPLE, '/does-not-exist')[0], 404)

    def test_untrusted_origin_is_rejected(self):
        self.assertEqual(self.post(SAMPLE, headers={'Origin': 'https://untrusted.example'})[0], 403)

    def test_allowed_cors_origin_is_exact(self):
        self.settings.allowed_origins = {'https://frontend.example'}
        status, headers, _ = self.request('OPTIONS', '/api/contact', headers={'Origin': 'https://frontend.example'})
        self.assertEqual(status, 204)
        self.assertEqual(headers['Access-Control-Allow-Origin'], 'https://frontend.example')
        self.assertEqual(self.post(SAMPLE, headers={'Origin': 'https://frontend.example.attacker.test'})[0], 403)

    def test_rate_limit(self):
        self.settings.rate_max = 2
        self.post(SAMPLE)
        self.post(SAMPLE)
        status, headers, body = self.post(SAMPLE)
        self.assertEqual(status, 429)
        self.assertIn('Retry-After', headers)
        self.assertFalse(json.loads(body)['success'])

    def test_send_mail_preserves_reply_to_and_message(self):
        self.configured()
        mock = MagicMock()
        mock.__enter__.return_value = mock
        mock.send_message.return_value = {}
        with patch('server.smtplib.SMTP_SSL', return_value=mock):
            server.send_mail(SAMPLE, self.settings)
        message = mock.send_message.call_args.args[0]
        self.assertEqual(message['Reply-To'], SAMPLE['email'])
        self.assertEqual(message['From'], self.settings.mail_from)
        self.assertIn(SAMPLE['message'], message.get_content())
        self.assertIn(SAMPLE['company'], message.get_content())

    def test_starttls_is_used_before_login(self):
        self.configured()
        self.settings.smtp_mode = 'starttls'
        mock = MagicMock()
        mock.__enter__.return_value = mock
        mock.send_message.return_value = {}
        with patch('server.smtplib.SMTP', return_value=mock):
            server.send_mail(SAMPLE, self.settings)
        calls = [str(c) for c in mock.method_calls]
        tls_index = next(
            index for index, call in enumerate(calls) if call.startswith('call.starttls')
        )
        login_index = next(
            index for index, call in enumerate(calls) if call.startswith('call.login')
        )
        self.assertLess(tls_index, login_index)

    def test_recipient_refusal_raises(self):
        self.configured()
        mock = MagicMock()
        mock.__enter__.return_value = mock
        mock.send_message.return_value = {self.settings.mail_to: (550, b'Refused')}
        with patch('server.smtplib.SMTP_SSL', return_value=mock):
            with self.assertRaises(smtplib.SMTPRecipientsRefused):
                server.send_mail(SAMPLE, self.settings)


if __name__ == '__main__':
    unittest.main(verbosity=2)
