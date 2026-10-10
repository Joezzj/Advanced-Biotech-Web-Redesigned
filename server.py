"""Static preview and optional SMTP contact bridge. Python 3.10+; stdlib only.

Run: python server.py
Configure SMTP in .env outside docs/ to enable direct delivery.
For public service, run behind an HTTPS reverse proxy with traffic controls.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import smtplib
import ssl
import threading
import time
from collections import defaultdict, deque
from email.message import EmailMessage
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / 'docs'
MAX_BODY = 32_768
ALLOWED_SUFFIXES = {
    '.html', '.css', '.js', '.webp', '.png', '.jpg', '.jpeg',
    '.svg', '.ico', '.txt', '.xml', '.woff', '.woff2',
}
FIELD_LIMITS = {
    'name': 100,
    'email': 254,
    'company': 150,
    'interest': 100,
    'product': 200,
    'message': 5000,
    'website': 200,
}
EMAIL_PATTERN = re.compile(
    r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@'
    r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}'
)
LOG = logging.getLogger('advancedbiotech')


def load_env(path: Path = ROOT / '.env') -> None:
    """Load simple KEY=value entries without executing or expanding their contents."""
    if not path.is_file():
        return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if re.fullmatch(r'[A-Z][A-Z0-9_]*', key):
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


def valid_email(value: str) -> bool:
    if not isinstance(value, str) or len(value) > 254:
        return False
    return EMAIL_PATTERN.fullmatch(value) is not None


class Settings:
    def __init__(self):
        self.host = os.environ.get('HOST', '127.0.0.1')
        self.port = int(os.environ.get('PORT', '8000'))
        self.smtp_host = os.environ.get('SMTP_HOST', '').strip()
        self.smtp_mode = os.environ.get('SMTP_SECURITY', 'ssl').lower()
        default_smtp_port = '465' if self.smtp_mode == 'ssl' else '587'
        self.smtp_port = int(os.environ.get('SMTP_PORT', default_smtp_port))
        self.smtp_user = os.environ.get('SMTP_USER', '').strip()
        self.smtp_password = os.environ.get('SMTP_PASSWORD', '')
        self.mail_from = os.environ.get('MAIL_FROM', self.smtp_user).strip()
        self.mail_to = os.environ.get('MAIL_TO', 'info@advancedbiotech.co.nz').strip()
        origins = os.environ.get('ALLOWED_ORIGINS', '').split(',')
        self.allowed_origins = {
            origin.strip().rstrip('/') for origin in origins if origin.strip()
        }
        self.rate_window = 600
        self.rate_max = 5
        self.smtp_timeout = 12

    @property
    def mail_ready(self) -> bool:
        return bool(
            self.smtp_host
            and self.smtp_user
            and self.smtp_password
            and valid_email(self.mail_from)
            and valid_email(self.mail_to)
            and self.smtp_mode in {'ssl', 'starttls'}
        )


def validate_payload(data):
    if not isinstance(data, dict):
        raise ValueError('The request must contain a JSON object.')
    result = {}
    for key, limit in FIELD_LIMITS.items():
        value = data.get(key, '')
        if not isinstance(value, str):
            raise ValueError('Each field must be text.')
        value = value.strip()
        if len(value) > limit or '\x00' in value:
            raise ValueError('A field exceeds the permitted length or contains an invalid character.')
        if key != 'message' and ('\n' in value or '\r' in value):
            raise ValueError('Single-line fields cannot contain line breaks.')
        result[key] = value
    if result['website']:
        raise ValueError('Please leave the extra field empty.')
    if (
        not result['name']
        or not valid_email(result['email'])
        or len(result['message']) < 10
    ):
        raise ValueError('A name, valid email and a message of at least 10 characters are required.')
    return result


def send_mail(data, settings):
    """Return only after SMTP accepts all recipients. No credentials in messages/logs."""
    msg = EmailMessage()
    msg['From'] = settings.mail_from
    msg['To'] = settings.mail_to
    msg['Reply-To'] = data['email']
    subject = data['product'] or data['interest'] or 'General enquiry'
    msg['Subject'] = f'Website enquiry: {subject}'
    msg.set_content(
        f"Name: {data['name']}\nEmail: {data['email']}\nCompany: {data['company'] or 'Not specified'}\n"
        f"Interest: {data['interest'] or 'General enquiry'}\n"
        f"Product / application: {data['product'] or 'Not specified'}\n\n"
        f"Message:\n{data['message']}\n"
    )
    context = ssl.create_default_context()
    if settings.smtp_mode == 'ssl':
        client = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port,
            timeout=settings.smtp_timeout, context=context,
        )
    else:
        client = smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout,
        )
    with client as smtp:
        if settings.smtp_mode == 'starttls':
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(settings.smtp_user, settings.smtp_password)
        refused = smtp.send_message(msg)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


class ContactServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, settings):
        super().__init__(address, Handler)
        self.settings = settings
        self.attempts = defaultdict(deque)
        self.rate_lock = threading.Lock()

    def check_rate(self, client_ip):
        now = time.monotonic()
        with self.rate_lock:
            # Expire idle entries to keep the store bounded over time.
            expired = [
                ip for ip, times in self.attempts.items()
                if not times or times[-1] <= now - self.settings.rate_window
            ]
            for ip in expired:
                del self.attempts[ip]
            bucket = self.attempts[client_ip]
            while bucket and bucket[0] <= now - self.settings.rate_window:
                bucket.popleft()
            if len(bucket) >= self.settings.rate_max:
                return False
            bucket.append(now)
            return True


class Handler(SimpleHTTPRequestHandler):
    server_version = 'AdvancedBiotech'
    sys_version = ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def log_message(self, fmt, *args):
        # Do not log form payloads, email addresses, tokens or full request URLs.
        if len(args) >= 2:
            LOG.info('%s %s', self.command, args[1])

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        super().end_headers()

    def allowed_origin(self):
        origin = self.headers.get('Origin', '').rstrip('/')
        if not origin:
            return True
        host = self.headers.get('Host', '')
        same_host = {f'http://{host}', f'https://{host}'}
        return origin in same_host or origin in self.server.settings.allowed_origins

    def cors_headers(self):
        origin = self.headers.get('Origin', '').rstrip('/')
        if origin and origin in self.server.settings.allowed_origins:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')

    def json_response(self, status, data):
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        if status == 429:
            self.send_header('Retry-After', str(self.server.settings.rate_window))
        self.cors_headers()
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(payload)

    def send_head(self):
        path = unquote(urlsplit(self.path).path)
        if path == '/site-config.js':
            endpoint = '/api/contact' if self.server.settings.mail_ready else ''
            config = {'contactEndpoint': endpoint, 'requestTimeoutMs': 20000}
            content = (
                f'window.AB_CONFIG = Object.freeze({json.dumps(config)});\n'
            ).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            return io.BytesIO(content)
        if path == '/api/contact/status':
            self.json_response(200, {'configured': self.server.settings.mail_ready})
            return None
        parts = Path(path).parts
        candidate = (PUBLIC / path.lstrip('/')).resolve()
        if path == '/':
            candidate = PUBLIC / 'index.html'
        if (
            not candidate.is_relative_to(PUBLIC.resolve())
            or any(part.startswith('.') for part in parts)
            or candidate.suffix.lower() not in ALLOWED_SUFFIXES
            or not candidate.is_file()
        ):
            self.send_error(404, 'Not found')
            return None
        return super().send_head()

    def do_OPTIONS(self):
        if urlsplit(self.path).path not in {'/api/contact', '/send_mail'}:
            self.json_response(404, {'success': False, 'error': 'Not found.'})
            return
        if not self.allowed_origin():
            self.json_response(403, {'success': False, 'error': 'Origin not allowed.'})
            return
        self.send_response(204)
        self.cors_headers()
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Accept')
        self.send_header('Access-Control-Max-Age', '600')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self):
        if urlsplit(self.path).path not in {'/api/contact', '/send_mail'}:
            self.json_response(404, {'success': False, 'error': 'Not found.'})
            return
        if not self.allowed_origin():
            self.json_response(403, {'success': False, 'error': 'Origin not allowed.'})
            return
        if not self.server.check_rate(self.client_address[0]):
            self.json_response(429, {'success': False, 'error': 'Too many requests. Please try later.'})
            return
        if self.headers.get_content_type() != 'application/json':
            self.json_response(415, {'success': False, 'error': 'Use application/json.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0
        if length > MAX_BODY:
            self.json_response(413, {'success': False, 'error': 'Request too large.'})
            return
        if length <= 0:
            self.json_response(400, {'success': False, 'error': 'Request body required.'})
            return
        try:
            payload = self.rfile.read(length)
            if len(payload) != length:
                raise ValueError('Incomplete request.')
            data = validate_payload(json.loads(payload.decode('utf-8')))
        except (ValueError, UnicodeError):
            self.json_response(400, {
                'success': False,
                'error': 'Please check the name, email, message and field lengths.',
            })
            return
        if not self.server.settings.mail_ready:
            self.json_response(503, {
                'success': False,
                'error': 'Direct mail is not configured. Please use the email draft option.',
            })
            return
        try:
            send_mail(data, self.server.settings)
        except (smtplib.SMTPException, OSError, ValueError):
            LOG.warning('Mail delivery failed; check server-side SMTP configuration.')
            self.json_response(502, {
                'success': False,
                'error': 'Mail delivery was not confirmed. Please contact us by email.',
            })
            return
        self.json_response(200, {'success': True})


def main():
    load_env()
    settings = Settings()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    server = ContactServer((settings.host, settings.port), settings)
    print(f'Advanced Biotech: http://{settings.host}:{server.server_port}', flush=True)
    contact_mode = (
        'direct SMTP delivery enabled.' if settings.mail_ready
        else 'email-draft mode (no SMTP credentials configured).'
    )
    print(f'Contact: {contact_mode}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
