from pathlib import Path
import zipfile,tempfile,shutil,json,hashlib,py_compile,re
R=Path.cwd();Z=R/'release'/'EnB Droplist.zip';M=R/'release'/'version.json';V='1.1.36'
try:
    if json.loads(M.read_text(encoding='utf-8')).get('version')==V: raise SystemExit(0)
except Exception: pass
w=Path(tempfile.mkdtemp(prefix='enb136_'))
try:
    with zipfile.ZipFile(Z) as z:
        if z.testzip(): raise SystemExit('bad input zip')
        z.extractall(w)
    p=next(w.rglob('enb_drop_logger_tray.py'));a=p.parent;s=p.read_text(encoding='utf-8').replace('1.1.35',V)

    anchor='overlay_dialog_requests = []\noverlay_dialog_lock = threading.Lock()\n'
    if anchor not in s: raise SystemExit('overlay dialog anchor missing')
    s=s.replace(anchor,anchor+'\n# 1.1.36 OCR Status/Test worker guard.\nocr_status_worker_lock = threading.Lock()\nocr_status_worker_running = False\n',1)

    ps=s.index('def plausible_zone_title(zone):');pe=s.index('\ndef update_zone',ps)
    pv=r'''def plausible_zone_title(zone):
    zone=normalize_zone_candidate(zone)
    if not zone:return False
    zone=re.sub(r"\s+"," ",zone).strip()
    if not (4<=len(zone)<=48):return False
    if len(re.findall(r"[A-Za-z]",zone))<4:return False
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 '\-]{3,47}",zone):return False
    words=zone.split()
    if not (1<=len(words)<=6):return False
    bad={"chat","group","options","help","emote","computer","credits","level","dist","target","structure","quality","defeated","discovered","faction","current","cancelled","combat","corpse","shield","hull","looted"}
    low={re.sub(r"[^a-z]","",x.lower()) for x in words}
    if low & bad:return False
    if len(words)==1:
        x=re.sub(r"[^A-Za-z0-9'-]","",words[0])
        return len(re.findall(r"[A-Za-z]",x))>=4 and x[:1].isupper() and not x.isupper()
    connectors={"of","the","to","and"}
    for i,x in enumerate(words):
        y=re.sub(r"[^A-Za-z0-9'-]","",x)
        if not y:return False
        if y.lower() in connectors and i>0:continue
        if y.isdigit():continue
        if not y[0].isupper():return False
    return True
'''
    s=s[:ps]+pv+s[pe:]
    s=s.replace('title_ok=bool(title and support>=2)','title_ok=bool(title and support>=3)')
    s=s.replace('probe_support>=2','probe_support>=3').replace('probe_support >= 2','probe_support >= 3')

    # GitHub 1.1.35 and the local 1.1.35 package have slightly different formatting.
    # Replace the F8 condition by regex rather than relying on one exact string.
    pattern=r'''        if \(map_open or probe_support >= 3\) and \(\(fallback_zone and plausible_zone_title\(fallback_zone\)\) or probe_zone\):\n(?:            .*\n){1,3}?'''
    m=re.search(pattern,s)
    if m:
        repl='''        if (map_open or probe_support >= 3) and (\n            (fallback_zone and plausible_zone_title(fallback_zone))\n            or (probe_zone and probe_support >= 3 and plausible_zone_title(probe_zone))\n        ):\n            chosen = fallback_zone if fallback_zone and plausible_zone_title(fallback_zone) else probe_zone\n'''
        s=s[:m.start()]+repl+s[m.end():]
    else:
        old='''        if (map_open or probe_support >= 3) and (fallback_zone or probe_zone) and plausible_zone_title(fallback_zone):\n            chosen = fallback_zone if fallback_zone and plausible_zone_title(fallback_zone) else probe_zone\n'''
        if old not in s: raise SystemExit('F8 zone condition missing')
        new='''        if (map_open or probe_support >= 3) and (\n            (fallback_zone and plausible_zone_title(fallback_zone))\n            or (probe_zone and probe_support >= 3 and plausible_zone_title(probe_zone))\n        ):\n            chosen = fallback_zone if fallback_zone and plausible_zone_title(fallback_zone) else probe_zone\n'''
        s=s.replace(old,new,1)

    fs=s.index('def show_ocr_status(*_):');fe=s.index('\ndef load_overlay_position',fs)
    impl=s[fs:fe].replace('def show_ocr_status(*_):','def _show_ocr_status_impl():',1)
    wrap=r'''
def show_ocr_status(*_):
    global ocr_status_worker_running
    with ocr_status_worker_lock:
        if ocr_status_worker_running:
            queue_overlay_dialog("EnB Droplist OCR Status / Test","OCR Status/Test is already running. Wait for the current OCR pass to finish.")
            return
        ocr_status_worker_running=True
    def run():
        global ocr_status_worker_running
        try:
            log("OCR Status worker started.")
            _show_ocr_status_impl()
        except Exception as e:
            log(f"OCR Status worker failed: {type(e).__name__}: {e}")
            queue_overlay_dialog("OCR Status failed",f"{type(e).__name__}: {e}")
        finally:
            with ocr_status_worker_lock:ocr_status_worker_running=False
            log("OCR Status worker finished; next test is enabled.")
    threading.Thread(target=run,name="EnB-OCR-Status",daemon=True).start()
'''
    s=s[:fs]+impl+'\n'+wrap+s[fe:]
    p.write_text(s,encoding='utf-8')

    c=a/'config.json';d=json.loads(c.read_text(encoding='utf-8'));d.setdefault('behavior',{}).update({'map_title_probe_min_support':3,'ocr_status_worker':True});c.write_text(json.dumps(d,indent=2),encoding='utf-8')
    q=a/'app_version.json'
    if q.exists():d=json.loads(q.read_text(encoding='utf-8'));d['version']=V;q.write_text(json.dumps(d,indent=2),encoding='utf-8')
    q=a/'auto_updater.py'
    if q.exists():q.write_text(q.read_text(encoding='utf-8').replace('CURRENT_VERSION = "1.1.35"',f'CURRENT_VERSION = "{V}"'),encoding='utf-8')
    for x in a.rglob('*.py'):
        if '__pycache__' not in x.parts:py_compile.compile(str(x),doraise=True)
    nz=R/'release'/'EnB Droplist.zip.new'
    with zipfile.ZipFile(nz,'w',zipfile.ZIP_DEFLATED) as z:
        for x in w.rglob('*'):
            if x.is_file() and '__pycache__' not in x.parts:z.write(x,x.relative_to(w))
    with zipfile.ZipFile(nz) as z:
        if z.testzip():raise SystemExit('bad output zip')
    nz.replace(Z);sha=hashlib.sha256(Z.read_bytes()).hexdigest()
    M.write_text(json.dumps({'name':'EnB Droplist','version':V,'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip','sha256':sha,'release_date':'2026-08-24','release_notes':'OCR Status/Test now runs in a guarded background worker and resets after every run, so it can be used repeatedly without blocking the tray callback. Zone OCR rejects short/noisy candidates and requires three agreeing map-title probe reads.'},indent=2)+'\n',encoding='utf-8')
    print(V,sha,Z.stat().st_size)
finally:
    shutil.rmtree(w,ignore_errors=True)
