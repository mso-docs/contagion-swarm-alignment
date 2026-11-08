"""Small metadata checks; substantive writing still requires the repository skill."""
import argparse
import os
from pathlib import Path
import sys


def validate(title,body=None):
    title=title.strip()
    if not title or len(title)>72 or title.endswith('.'):
        raise ValueError('Use a nonempty subject/title of at most72 characters without a trailing period')
    if body is not None:
        for heading in ['## Summary','## Validation','## Limitations']:
            if heading not in body:raise ValueError('PR body must include Summary, Validation and Limitations sections')
            section=body.split(heading,1)[1].split('\n## ',1)[0].strip()
            if not section:raise ValueError('PR sections must contain substantive text')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind',choices=['commit','pr'],required=True)
    parser.add_argument('file',nargs='?',type=Path)
    args=parser.parse_args()
    try:
        if args.kind=='commit':
            lines=args.file.read_text().splitlines();validate(lines[0] if lines else '')
        else:validate(os.environ.get('PR_TITLE',''),os.environ.get('PR_BODY',''))
    except (ValueError,OSError) as exc:sys.exit(str(exc))
