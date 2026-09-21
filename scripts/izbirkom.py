#!/usr/bin/env python3
"""Сохранение первоисточника для последующего явного адаптера в Vibori v1."""
from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import json

p = ArgumentParser(description='Получить страницу избирательной комиссии')
p.add_argument('--url', required=True); p.add_argument('--out', required=True)
args = p.parse_args(); out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
req = Request(args.url, headers={'User-Agent':'Vibori research importer/1.0 (+https://github.com/)'})
with urlopen(req, timeout=30) as response:
    body = response.read(); out.write_bytes(body)
    meta = {'url': args.url, 'retrieved_at': datetime.now(timezone.utc).isoformat(), 'status': response.status, 'content_type': response.headers.get_content_type(), 'output': str(out)}
out.with_suffix(out.suffix + '.source.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(meta, ensure_ascii=False))
