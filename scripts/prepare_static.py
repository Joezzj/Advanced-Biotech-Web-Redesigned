"""Copy the editable site into a clean dist/ directory for static hosting."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs'
DESTINATION = ROOT / 'dist'


def main():
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    shutil.copytree(SOURCE, DESTINATION)
    print(f'Static files prepared in {DESTINATION}')


if __name__ == '__main__':
    main()
