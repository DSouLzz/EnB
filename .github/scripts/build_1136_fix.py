from pathlib import Path
import subprocess,tempfile,shutil,zipfile,json,hashlib,py_compile,re

R=Path.cwd(); Z=R/'release'/'EnB Droplist.zip'; M=R/'release'/'version.json'
V='1.1.36'; BASE='8ab688349d30715d3c009e71a6c068180fdac6ac'

def release_ok():
    try:
        m=json.loads(M.read_text(encoding='utf-8'))
        if m.get('version')!=V:return False
        sha=hashlib.sha256(Z.read_bytes()).hexdigest()
        if sha.lower()!=str(m.get('sha256','')).lower():return False
        if Z.stat().st_size<40000:return False
        with zipfile.ZipFile(Z) as z:
            return z.testzip() is None
    except Exception:return False

def main():
    if release_ok():
        print('release already valid',V); return
    w=Path(tempfile.mkdtemp(prefix='enb136fix_'))
    try:
        base=w/'base.zip'
        base.write_bytes(subprocess.check_output(['git','show',f'{BASE}:release/EnB Droplist.zip']))
        with zipfile.ZipFile(base) as z:
            if z.testzip():raise SystemExit('bad verified 1.1.35 base zip')
            src=w/'src';src.mkdir();z.extractall(src)
        p=next(src.rglob('enb_drop_logger_tray.py')); a=p.parent
        s=p.read_text(encoding='utf-8').replace('1.1.35',V)

        # Structural worker-state insertion. Do NOT depend on exact whitespace
        # around overlay_dialog_requests / overlay_dialog_lock.
        if 'ocr_status_worker_running' not in s:
            marker='_last_enb_window = None'
            pos=s.find(marker)
            if pos<0:raise SystemExit('window cache marker missing')
            guard='''# 1.1.36 OCR Status/Test worker guard.\nocr_status_worker_lock = threading.Lock()\nocr_status_worker_running = False\n\n'''
            s=s[:pos]+guard+s[pos:]

        ps=s.index('def plausible_zone_title(zone):'); pe=s.index('\ndef update_zone',ps)
        strict='''def plausible_zone_title(zone):\n    zone = normalize_zone_candidate(zone)\n    if not zone:\n        return False\n    zone = re.sub(r"\\s+", " ", zone).strip()\n    if not (4 <= len(zone) <= 48):\n        return False\n    if len(re.findall(r"[A-Za-z]", zone)) < 4:\n        return False\n    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 \'\\-]{3,47}", zone):\n        return False\n    words = zone.split()\n    if not (1 <= len(words) <= 6):\n        return False\n    bad = {"chat","group","options","help","emote","computer","credits","level","dist","target","structure","quality","defeated","discovered","faction","current","cancelled","combat","corpse","shield","hull","looted"}\n    low={re.sub(r"[^a-z]","",w.lower()) for w in words}\n    if low & bad:\n        return False\n    if len(words)==1:\n        w=re.sub(r"[^A-Za-z0-9\'-]","",words[0])\n        return len(re.findall(r"[A-Za-z]",w))>=4 and w[:1].isupper() and not w.isupper()\n    connectors={"of","the","to","and"}\n    for i,w in enumerate(words):\n        bare=re.sub(r"[^A-Za-z0-9\'-]","",w)\n        if not bare:return False\n        if bare.lower() in connectors and i>0:continue\n        if bare.isdigit():continue\n        if not bare[0].isupper():return False\n    return True\n'''
        s=s[:ps]+strict+s[pe:]
        s=s.replace('title_ok=bool(title and support>=2)','title_ok=bool(title and support>=3)')
        s=s.replace('probe_support>=2','probe_support>=3').replace('probe_support >= 2','probe_support >= 3')

        # Repair F8 zone condition structurally, regardless of 1.1.35 formatting.
        pat=re.compile(r'(?m)^\s*if \(map_open or probe_support\s*>=\s*[23]\).*?:\n\s*chosen\s*=.*?\n')
        m=pat.search(s)
        if m:
            ind=re.match(r'\s*',m.group(0)).group(0)
            repl=(ind+'if (map_open or probe_support >= 3) and ((fallback_zone and plausible_zone_title(fallback_zone)) or (probe_zone and probe_support >= 3 and plausible_zone_title(probe_zone))):\n'
                  +ind+'    chosen = fallback_zone if fallback_zone and plausible_zone_title(fallback_zone) else probe_zone\n')
            s=s[:m.start()]+repl+s[m.end():]

        # OCR Status/Test: expensive work off tray callback thread, always reset.
        ss=s.index('def show_ocr_status(*_):'); se=s.index('\ndef load_overlay_position',ss)
        impl=s[ss:se].replace('def show_ocr_status(*_):','def _show_ocr_status_impl():',1)
        wrapper='''def show_ocr_status(*_):\n    global ocr_status_worker_running\n    with ocr_status_worker_lock:\n        if ocr_status_worker_running:\n            queue_overlay_dialog("EnB Droplist OCR Status / Test","OCR Status/Test is already running. Wait for the current OCR pass to finish.")\n            return\n        ocr_status_worker_running=True\n    def run():\n        global ocr_status_worker_running\n        try:\n            log("OCR Status worker started.")\n            _show_ocr_status_impl()\n        except Exception as e:\n            log(f"OCR Status worker failed: {type(e).__name__}: {e}")\n            queue_overlay_dialog("OCR Status failed",f"{type(e).__name__}: {e}")\n        finally:\n            with ocr_status_worker_lock:\n                ocr_status_worker_running=False\n            log("OCR Status worker finished; next test is enabled.")\n    threading.Thread(target=run,name="EnB-OCR-Status",daemon=True).start()\n\n'''
        s=s[:ss]+impl+'\n'+wrapper+s[se:]
        p.write_text(s,encoding='utf-8')

        c=a/'config.json'; d=json.loads(c.read_text(encoding='utf-8')); d.setdefault('behavior',{}).update({'map_title_probe_min_support':3,'ocr_status_worker':True}); c.write_text(json.dumps(d,indent=2),encoding='utf-8')
        q=a/'app_version.json'
        if q.exists():
            d=json.loads(q.read_text(encoding='utf-8'));d['version']=V;q.write_text(json.dumps(d,indent=2),encoding='utf-8')
        q=a/'auto_updater.py'
        if q.exists():q.write_text(q.read_text(encoding='utf-8').replace('CURRENT_VERSION = "1.1.35"',f'CURRENT_VERSION = "{V}"'),encoding='utf-8')

        for x in a.rglob('*.py'):
            if '__pycache__' not in x.parts:py_compile.compile(str(x),doraise=True)
        nz=Z.with_suffix('.zip.new')
        with zipfile.ZipFile(nz,'w',zipfile.ZIP_DEFLATED) as z:
            for x in src.rglob('*'):
                if x.is_file() and '__pycache__' not in x.parts:z.write(x,x.relative_to(src))
        with zipfile.ZipFile(nz) as z:
            if z.testzip():raise SystemExit('bad output zip')
        if nz.stat().st_size<40000:raise SystemExit(f'output zip suspiciously small: {nz.stat().st_size}')
        nz.replace(Z); sha=hashlib.sha256(Z.read_bytes()).hexdigest()
        M.write_text(json.dumps({'name':'EnB Droplist','version':V,'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip','sha256':sha,'release_date':'2026-08-24','release_notes':'OCR Status/Test runs in a guarded background worker and resets after every run. Zone OCR rejects short/noisy candidates and requires three agreeing map-title probe reads.'},indent=2)+'\n',encoding='utf-8')
        print('built',V,sha,Z.stat().st_size)
    finally:
        shutil.rmtree(w,ignore_errors=True)

if __name__=='__main__':main()
