#!/usr/bin/env python3
"""Offline privacy lint. Reports categories/counts, never matched text."""
import argparse
from collections import Counter
import ipaddress
import json
from pathlib import Path
import re

EMAIL = re.compile(r'(?i)(?<![\w.+-])[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])')
PATTERNS = {
    'credential_assignment': re.compile(r'''(?im)["']?\b(?:api[_ -]?key|access[_ -]?token|password|authorization|cookie|secret)["']?\s*[:=]\s*["']?(?!\[REDACTED\])[^\s"',}]{8,}'''),
    'credential_token': re.compile(r'\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{10,}|AKIA[A-Z0-9]{16})\b'),
    'private_key': re.compile(r'-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----'),
    'government_id': re.compile(r'(?<!\d)(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?!\d)'),
    'phone': re.compile(r'(?<![\w\d])(?:\+\d{1,3}[ .-])?(?:\(\d{3}\)[ .-]?|\d{3}[ .-])\d{3}[ .-]\d{4}(?!\d)'),
    'home_path': re.compile(r'(?:/(?:Users|home)/[^\s/"\\]+|[A-Za-z]:\\Users\\[^\s\\"]+)'),
}
CARD = re.compile(r'(?<![\w\d.])(?:\d[ -]?){12,18}\d(?![\w\d.])')
IP = re.compile(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])')


def luhn(value):
    digits = [int(c) for c in value if c.isdigit()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) < 2:
        return False
    return sum(d if i % 2 == 0 else (d * 2 - 9 if d > 4 else d * 2)
               for i, d in enumerate(reversed(digits))) % 10 == 0


def findings(text, *, public=False, known=()):
    """Public text is strict; repository prose permits reserved example emails."""
    result = Counter()
    for match in EMAIL.finditer(text):
        domain = match.group(1).lower()
        if public or not (domain in {'example.com', 'example.org', 'example.net'} or domain.endswith(('.example', '.invalid', '.test'))):
            result['email'] += 1
    for label, pattern in PATTERNS.items():
        if public or label in {'phone', 'government_id'}:
            result[label] += len(pattern.findall(text))
    result['payment_card'] += sum(luhn(m.group()) for m in CARD.finditer(text))
    if public:
        for match in IP.finditer(text):
            try:
                ipaddress.ip_address(match.group())
            except ValueError:
                continue
            result['ip_address'] += 1
        # Source/docs contain intentional syntax examples; public trace fields do not.
        for value in set(known):
            if value and len(value) >= 3 and value.casefold() in text.casefold():
                result['known_private_value'] += 1
    return +result


def scan_blob(data, *, public=False, known=()):
    text = data.decode('utf-8')  # Unexpected binary public inputs fail closed.
    if public:
        # Decode JSON escapes before scanning string values. Numeric telemetry/hashes
        # are not interpreted as phone/card numbers; content strings still are.
        parsed = json.loads(text)
        strings = []
        def visit(item):
            if isinstance(item, str):
                strings.append(item)
            elif isinstance(item, dict):
                for key, value in item.items():
                    strings.append(key)
                    visit(value)
            elif isinstance(item, list):
                for value in item:
                    visit(value)
        visit(parsed)
        return sum((findings(s, public=True, known=known) for s in strings), Counter())
    return findings(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, action='append', default=[])
    args = parser.parse_args()
    totals = Counter()
    count = 0
    try:
        from security_guard import ROOT, private_values
        import os
        known, _ = private_values(ROOT, dict(os.environ))
        for root in args.path or [ROOT / 'dashboard/data']:
            if not root.exists() or root.is_symlink():
                raise ValueError('Invalid input')
            paths = sorted(root.rglob('*')) if root.is_dir() else [root]
            for path in paths:
                if path.is_symlink():
                    raise ValueError('Symlink input')
                if not path.is_file() or path.suffix.lower() not in {'.json', '.jsonl', '.txt', '.log', '.md', '.csv'}:
                    continue
                data = path.read_bytes()
                if len(data) > 64 * 1024 * 1024:
                    raise ValueError('Input too large')
                text = data.decode('utf-8')
                # Standalone audit of raw logs is strict too; originals are never edited.
                if path.suffix == '.json':
                    totals.update(scan_blob(data, public=True, known=known))
                elif path.suffix == '.jsonl':
                    for line in text.splitlines():
                        if line.strip():
                            totals.update(scan_blob(line.encode(), public=True, known=known))
                else:
                    totals.update(findings(text, public=True, known=known))
                count += 1
        print(f'Privacy scan: {count} files; category counts: {dict(sorted(totals.items()))}. No matched values printed.')
        return int(bool(totals))
    except Exception as exc:
        print(f'Privacy scan blocked ({type(exc).__name__}); no matched values printed.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
