from pathlib import Path
import base64, hashlib, json, zipfile

R=Path.cwd(); OUT=R/'release'/'EnB Droplist.zip'; MAN=R/'release'/'version.json'
EXPECTED='85449e48b84d2ae1c7e97058965eb7dc2b585ab156e622ccb3c0419f7848b8b5'
parts=[]
for i in range(1,6):
    p=R/'release_parts'/f'1136_{i:02d}.b64'
    if not p.exists(): raise SystemExit(f'missing {p}')
    parts.append(''.join(p.read_text(encoding='utf-8').split()))
raw=base64.b64decode(''.join(parts), validate=True)
sha=hashlib.sha256(raw).hexdigest()
if sha != EXPECTED: raise SystemExit(f'SHA mismatch before write: {sha}')
if len(raw) != 50111: raise SystemExit(f'Unexpected size: {len(raw)}')
OUT.write_bytes(raw)
with zipfile.ZipFile(OUT) as z:
    bad=z.testzip()
    if bad: raise SystemExit(f'ZIP integrity failed at {bad}')
MAN.write_text(json.dumps({
  'name':'EnB Droplist','version':'1.1.36',
  'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip',
  'sha256':EXPECTED,'release_date':'2026-08-24',
  'release_notes':'OCR Status/Test runs in a guarded background worker and resets after every run. Zone OCR rejects short/noisy candidates and requires three agreeing map-title probe reads.'
}, indent=2)+'\n', encoding='utf-8')
print('assembled 1.1.36', len(raw), sha)
