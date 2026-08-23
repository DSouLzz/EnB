from pathlib import Path
import zipfile,tempfile,shutil,json,hashlib,py_compile,re
R=Path.cwd(); Z=R/'release'/'EnB Droplist.zip'; M=R/'release'/'version.json'; V='1.1.34'
try:
    if json.loads(M.read_text(encoding='utf-8')).get('version')==V: raise SystemExit(0)
except Exception: pass
w=Path(tempfile.mkdtemp(prefix='enb134_'))
try:
    with zipfile.ZipFile(Z) as z:
        if z.testzip(): raise SystemExit('bad input zip')
        z.extractall(w)
    p=next(w.rglob('enb_drop_logger_tray.py')); a=p.parent
    s=p.read_text(encoding='utf-8').replace('1.1.33',V)

    old='def target_title_from_window(win):'
    if old not in s: raise SystemExit('target function missing')
    s=s.replace(old,'def _target_title_from_window_old(win):',1)
    pos=s.index('\ndef normalize_zone_candidate')
    wrap=r'''
def target_title_from_window(win):
    name,old_level,old_debug=_target_title_from_window_old(win)
    votes=[]; dbg=[]
    rx=re.compile(r"\b(?:Level|LeveI|Levei|Leve1|Lvl|CL)\s*[:#\-]?\s*([0-9]{1,2})\b",re.I)
    for c in ((0.795,0.735,0.997,0.810),(0.795,0.755,0.997,0.835)):
        try: img=grab(client_region(win,*c))
        except Exception as e: dbg.append(f"LEVEL GRAB {e!r}"); continue
        g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        for th in (60,90,120,150):
            b=cv2.resize(g,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)
            b=cv2.threshold(b,th,255,cv2.THRESH_BINARY)[1]
            for psm in (7,11,13):
                try:
                    raw=pytesseract.image_to_string(b,config=f"--psm {psm}")
                    for m in rx.finditer(raw):
                        n=int(m.group(1))
                        if 0<=n<=99:votes.append(str(n))
                except Exception as e: dbg.append(f"LEVEL OCR {e!r}")
            try:
                raw=pytesseract.image_to_string(b,config="--psm 7 -c tessedit_char_whitelist=0123456789")
                m=re.search(r"([0-9]{1,2})",raw)
                if m:
                    n=int(m.group(1))
                    if 0<=n<=99:votes.append(str(n))
            except Exception as e: dbg.append(f"LEVEL DIGIT {e!r}")
    if not votes:return name,old_level,old_debug+"\nLEVEL STRIP: <none>"
    from collections import Counter
    level,count=Counter(votes).most_common(1)[0]
    return name,level,old_debug+f"\nLEVEL STRIP WINNER: {level} votes={count}"
'''
    s=s[:pos]+wrap+s[pos:]

    mp=s.index('\ndef map_title_from_window(win):')
    mh=r'''
def map_panel_is_open(win):
    try:
        x=client_sparse_ocr(win,0.135,0.745,0.615,0.845,7); y=client_sparse_ocr(win,0.135,0.745,0.615,0.845,11)
        return bool(re.search(r"\bDest\s*:",norm(x+" "+y),re.I)),x+"\n"+y
    except Exception as e:return False,f"<map-open OCR error: {e!r}>"
'''
    s=s[:mp]+mh+s[mp:]

    t=s.index('def tick():'); zs=s.index('    if map_zone_capture_active():',t)
    m1='    if current_zone:\n        live_overlay["zone"] = current_zone\n'; m2='    if current_zone: live_overlay["zone"]=current_zone\n'
    try: ze=s.index(m1,zs)+len(m1)
    except ValueError: ze=s.index(m2,zs)+len(m2)
    nz='''    map_open,map_open_raw=map_panel_is_open(win)\n    texts["map_open"]="YES" if map_open else "NO"; texts["map_open_raw"]=map_open_raw\n    if map_open or map_zone_capture_active():\n        map_title,map_raw=map_title_from_window(win); texts["zone_title_raw"]=map_raw\n        if map_title and plausible_zone_title(map_title): update_zone(map_title); log(f"MAP LIVE SAMPLE open={map_open} title={map_title!r} candidate={candidate_zone!r} reads={candidate_zone_reads} current={current_zone!r}")\n        else:texts["zone"]="<map title not visible>"\n    else:\n        texts["zone_title_raw"]="<map panel closed>"; texts["zone"]="<locked to last confirmed zone>"\n    if current_zone:live_overlay["zone"]=current_zone\n'''
    s=s[:zs]+nz+s[ze:]

    fs=s.index('def show_ocr_status'); fe=s.index('\ndef toggle_pause',fs); b=s[fs:fe]
    needle='        raw_zone = normalize_zone_candidate(parse_zone(raw.get("zone","")))\n        fallback_zone, map_fallback_raw = map_title_from_window(win)\n'
    if needle not in b: raise SystemExit('F8 zone patch missing')
    repl=needle+'        map_open,map_open_raw=map_panel_is_open(win)\n        if map_open and fallback_zone and plausible_zone_title(fallback_zone):\n            for _ in range(max(1,int(cfg["behavior"].get("stable_zone_reads",3)))):update_zone(fallback_zone)\n            if current_zone:live_overlay["zone"]=current_zone\n'
    b=b.replace(needle,repl,1); s=s[:fs]+b+s[fe:]
    p.write_text(s,encoding='utf-8')

    c=a/'config.json'; d=json.loads(c.read_text(encoding='utf-8')); d.setdefault('behavior',{}).update({'zone_update_requires_m_key':False,'map_panel_dest_detection':True,'enemy_requires_level':True}); c.write_text(json.dumps(d,indent=2),encoding='utf-8')
    q=a/'app_version.json'
    if q.exists():d=json.loads(q.read_text(encoding='utf-8'));d['version']=V;q.write_text(json.dumps(d,indent=2),encoding='utf-8')
    q=a/'auto_updater.py'
    if q.exists():q.write_text(q.read_text(encoding='utf-8').replace('CURRENT_VERSION = "1.1.33"',f'CURRENT_VERSION = "{V}"'),encoding='utf-8')
    for x in a.rglob('*.py'):
        if '__pycache__' not in x.parts:py_compile.compile(str(x),doraise=True)
    nz=R/'release'/'EnB Droplist.zip.new'
    with zipfile.ZipFile(nz,'w',zipfile.ZIP_DEFLATED) as z:
        for x in w.rglob('*'):
            if x.is_file() and '__pycache__' not in x.parts:z.write(x,x.relative_to(w))
    with zipfile.ZipFile(nz) as z:
        if z.testzip():raise SystemExit('bad output zip')
    nz.replace(Z); sha=hashlib.sha256(Z.read_bytes()).hexdigest()
    M.write_text(json.dumps({'name':'EnB Droplist','version':V,'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip','sha256':sha,'release_date':'2026-08-23','release_notes':'Dedicated target Level-strip OCR with digit fallback. Zone refresh detects the real open map panel via Dest:, and F8/live zone no longer depends only on the M hotkey.'},indent=2)+'\n',encoding='utf-8')
    print(V,sha,Z.stat().st_size)
finally:shutil.rmtree(w,ignore_errors=True)
