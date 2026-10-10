"""Read page markup into the minimal tree used by JavaScript event tests."""
from html.parser import HTMLParser
from pathlib import Path
import json
import sys

VOID_ELEMENTS = {
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
    'link', 'meta', 'param', 'source', 'track', 'wbr',
}


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {'tag': 'document', 'attrs': {}, 'children': []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = {'tag': tag, 'attrs': dict(attrs), 'children': []}
        self.stack[-1]['children'].append(node)
        if tag not in VOID_ELEMENTS:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index]['tag'] == tag:
                self.stack = self.stack[:index]
                return

    def handle_data(self, data):
        self.stack[-1]['children'].append(data)


def main():
    parser = Parser()
    parser.feed(Path(sys.argv[1]).read_text(encoding='utf-8'))
    print(json.dumps(parser.root))


if __name__ == '__main__':
    main()
