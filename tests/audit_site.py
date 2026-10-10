"""Check links, assets, labels and preserved product and solution content."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import json
import re

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'docs'
CONTENT = ROOT / 'tests/fixtures/content.json'


class AuditParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.links = []
        self.images = []
        self.inputs = []
        self.labels = []
        self.headings = []
        self.text = []
        self.script_sources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag in ('a', 'link') and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag == 'img':
            self.images.append(attrs)
            if attrs.get('src'):
                self.links.append(attrs['src'])
        if tag == 'script' and attrs.get('src'):
            self.links.append(attrs['src'])
            self.script_sources.append(attrs['src'])
        if tag in ('input', 'select', 'textarea'):
            self.inputs.append(attrs)
        if tag == 'label':
            self.labels.append(attrs.get('for'))
        if tag == 'h1':
            self.headings.append(tag)

    def handle_data(self, data):
        self.text.append(data)


def normalized(text):
    return re.sub(r'\s+', ' ', text).strip()


def audit_pages(parsers):
    checks = 0
    for name, page in parsers.items():
        assert len(page.ids) == len(set(page.ids)), f'Duplicate IDs in {name}'
        assert len(page.headings) == 1, f'Expected one H1 in {name}'
        checks += 2
        for link in page.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            target = PUBLIC / (unquote(url.path) or name)
            assert target.exists(), f'Broken link in {name}: {link}'
            if url.fragment:
                assert target.name in parsers, f'Missing page: {link}'
                assert unquote(url.fragment) in parsers[target.name].ids, (
                    f'Missing anchor in {name}: {link}'
                )
            checks += 1
        for image in page.images:
            assert image.get('alt'), f'Missing image alt in {name}'
            assert image.get('width') and image.get('height'), (
                f'Missing image dimensions in {name}'
            )
            checks += 2
        for field in page.inputs:
            assert field.get('id') in page.labels or field.get('aria-label'), (
                f'Unlabelled input in {name}'
            )
            checks += 1
    return checks


def audit_content(parsers):
    content = json.loads(CONTENT.read_text(encoding='utf-8'))
    collections = [
        ('products.html', content['products'], 'paragraphs'),
        ('solutions.html', content['solutions'], 'intro'),
    ]
    checks = 0
    for filename, records, paragraph_key in collections:
        page_text = normalized(' '.join(parsers[filename].text))
        for record in records:
            assert normalized(record['title']) in page_text
            for paragraph in record[paragraph_key]:
                assert normalized(paragraph) in page_text, (
                    f'Content missing in {filename}: {record["title"]}'
                )
                checks += 1
            for application in record.get('uses', []):
                assert normalized(application['body']) in page_text
                checks += 1
    return checks


def audit_styles():
    checks = 0
    for stylesheet in PUBLIC.rglob('*.css'):
        css = stylesheet.read_text(encoding='utf-8')
        assets = re.findall(r'url\([\"\']?([^\)\"\']+)', css)
        for asset in assets:
            if not asset.startswith(('data:', 'http')):
                assert (stylesheet.parent / asset).is_file(), (
                    f'Missing stylesheet asset: {stylesheet.name}: {asset}'
                )
                checks += 1
        assert css.count('{') == css.count('}'), f'Unbalanced CSS: {stylesheet}'
        checks += 1
    return checks


def audit_public_files():
    checks = 0
    legacy_values = ['smtp_config.json', 'smtp_pass', 'advance@', 'localhost:5000']
    for path in PUBLIC.rglob('*'):
        if path.suffix in {'.html', '.js', '.css', '.json', '.py'}:
            text = path.read_text(encoding='utf-8')
            for value in legacy_values:
                assert value not in text, f'Unsafe legacy value in {path}'
                checks += 1
    assert not list(PUBLIC.glob('*.py'))
    assert not list(PUBLIC.glob('*config.json'))
    return checks


def main():
    parsers = {}
    for path in PUBLIC.glob('*.html'):
        parser = AuditParser()
        parser.feed(path.read_text(encoding='utf-8'))
        parsers[path.name] = parser
    checks = (
        audit_pages(parsers)
        + audit_content(parsers)
        + audit_styles()
        + audit_public_files()
    )
    print(json.dumps({'status': 'PASS', 'checks': checks, 'pages': len(parsers)}))


if __name__ == '__main__':
    main()
