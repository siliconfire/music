import sys
from pathlib import Path

# ensure the backend folder is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from content_checker import content_checker, reload_blacklists

reload_blacklists()

tests = [
    ("this is clean text", True),
    ("contains badword here", False),
    ("AnOtHeR forbidden PHRASE in text", False),
    ("partial badwo", True),
]

all_ok = True
for txt, expected in tests:
    got = content_checker(txt)
    print(f"{txt!r} -> {got} (expected {expected})")
    if got != expected:
        all_ok = False

print('\nALL OK' if all_ok else '\nSOME FAILED')

