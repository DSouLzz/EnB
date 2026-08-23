from pathlib import Path
import zipfile,tempfile,shutil,json,hashlib,py_compile,re
R=Path.cwd(); Z=R/'release'/'EnB Droplist.zip'; M=R/'release'/'version.json'; V='1.1.34'
try:
 if json.loads(M.read_text(encoding='utf-8')).get('version')==V: raise SystemExit(0)
except Exception: pass
w=Path(tempfile.mkdtemp())
try:
 with zipfile.ZipFile(Z) as z:
  if z.testzip(): raise SystemExit('bad input zip')
  z.extractall(w)
 p=next(w.rglob('enb_drop_logger_tray.py')); a=p.parent; s=p.read_text(encoding='utf-8').replace('1.1.33',V)
 st=s.index('def target_title_from_window(win):'); en=s.index('\ndef normalize_zone_candidate',st)
 nf=r'''def target_title_from_window(win):
    """Read target name and Level from separate narrow target-card strips."""
    def prep_variants(img):
        if img is None or getattr(img,"size",0)==0:return []
        hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV); gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        mask=cv2.inRange(hsv,(0,0,105),(179,165,255)); masked=cv2.bitwise_and(gray,gray,mask=mask); out=[]
        for base in (gray,mask,masked):
            big=cv2.resize(base,None,fx=4,fy=4,interpolation=cv2.INTER_CUBIC)
            out.extend([big,cv2.threshold(big,70,255,cv2.THRESH_BINARY)[1],cv2.threshold(big,105,255,cv2.THRESH_BINARY)[1],cv2.threshold(big,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]])
        return out
    def clean_name(x):
        x=norm(x); x=re.sub(r"^Corpse\s+of\s+","",x,flags=re.I).strip(); x=re.sub(r"[^A-Za-z0-9 '\-]"," ",x); x=re.sub(r"\s+"," ",x).strip()
        if not (3<=len(x)<=65) or len(re.findall(r"[A-Za-z]",x))<3 or len(x.split())>9:return ""
        if re.search(r"\b(?:Dist|Distance|Hull|Shield|Structure|Quality|Chat|Group|Options|Help|Emote|Credits?|Dest|Sector Gate)\b",x,re.I):return ""
        return x
    name_regions=[(0.795,0.685,0.997,0.755),(0.795,0.705,0.997,0.775)]
    level_regions=[(0.795,0.740,0.997,0.805),(0.795,0.760,0.997,0.830)]
    name_votes=[]; level_votes=[]; debug=[]
    for coords in name_regions:
        try:img=grab(client_region(win,*coords))
        except Exception as e:debug.append(f"NAME GRAB {coords}: {e!r}");continue
        for proc in prep_variants(img):
            for psm in (7,11):
                try:
                    raw=pytesseract.image_to_string(proc,config=f"--psm {psm} -c preserve_interword_spaces=1"); vals=[clean_name(x) for x in raw.splitlines()]; vals=[x for x in vals if x]
                    if vals:name_votes.extend(vals);debug.append(f"NAME psm{psm} {coords[1]:.3f}-{coords[3]:.3f}: "+" | ".join(vals))
                except Exception as e:debug.append(f"NAME OCR error: {e!r}")
    level_re=re.compile(r"\b(?:Level|LeveI|Levei|Leve1|Lvl|CL)\s*[:#\-]?\s*([0-9]{1,2})\b",re.I)
    for coords in level_regions:
        try:img=grab(client_region(win,*coords))
        except Exception as e:debug.append(f"LEVEL GRAB {coords}: {e!r}");continue
        for proc in prep_variants(img):
            for psm in (7,11,13):
                try:
                    raw=pytesseract.image_to_string(proc,config=f"--psm {psm}")
                    if norm(raw):debug.append(f"LEVEL psm{psm} {coords[1]:.3f}-{coords[3]:.3f}: {norm(raw)}")
                    for m in level_re.finditer(raw):
                        n=int(m.group(1))
                        if 0<=n<=99:level_votes.append(str(n))
                except Exception as e:debug.append(f"LEVEL OCR error: {e!r}")
            try:
                rawd=pytesseract.image_to_string(proc,config="--psm 7 -c tessedit_char_whitelist=0123456789"); m=re.search(r"([0-9]{1,2})",rawd)
                if m:
                    n=int(m.group(1))
                    if 0<=n<=99:level_votes.append(str(n));debug.append(f"LEVEL DIGITS {coords[1]:.3f}-{coords[3]:.3f}: {n}")
            except Exception as e:debug.append(f"LEVEL DIGIT OCR error: {e!r}")
    from collections import Counter
    if not level_votes:return "","","TARGET CARD STRIPS (no Level found):\n"+("\n".join(debug) if debug else "<blank>")
    level,level_count=Counter(level_votes).most_common(1)[0]; name=""
    if name_votes:
        counts=Counter(x.lower() for x in name_votes); key,_=counts.most_common(1)[0]; originals=[x for x in name_votes if x.lower()==key]; name=min(originals,key=lambda x:(len(x.split()),len(x)))
    return name,level,"TARGET CARD STRIPS:\n"+("\n".join(debug) if debug else "<blank>")+f"\nLEVEL WINNER: {level} votes={level_count}"+(f"\nNAME WINNER: {name}" if name else "\nNAME WINNER: <fallback needed>")
'''
 s=s[:st]+nf+s[en:]
 mp=s.index('\ndef map_title_from_window(win):')
 mh=r'''\ndef map_panel_is_open(win):
    """Detect the in-game map using its visible Dest: footer."""
    try:
        raw1=client_sparse_ocr(win,0.135,0.745,0.615,0.845,7); raw2=client_sparse_ocr(win,0.135,0.745,0.615,0.845,11); combined=norm(raw1+" "+raw2)
        return bool(re.search(r"\bDest\s*:",combined,re.I)),raw1+"\n"+raw2
    except Exception as e:return False,f"<map-open OCR error: {e!r}>"
'''
 s=s[:mp]+mh+s[mp:]
 zs=s.index('    # 1.1.34: Zone changes are accepted ONLY during the short capture window'); zm='    if current_zone:\n        live_overlay["zone"] = current_zone\n'; ze=s.index(zm,zs)+len(zm)
 nz='''    # 1.1.34: update zone only while the actual map panel is open.\n    map_open,map_open_raw=map_panel_is_open(win); texts["map_open"]="YES" if map_open else "NO"; texts["map_open_raw"]=map_open_raw\n    if map_open or map_zone_capture_active():\n        map_title,map_raw=map_title_from_window(win); texts["zone_title_raw"]=map_raw\n        if map_title and plausible_zone_title(map_title):\n            update_zone(map_title); log(f"MAP LIVE SAMPLE open={map_open} title={map_title!r} candidate={candidate_zone!r} reads={candidate_zone_reads} current={current_zone!r}")\n        else:texts["zone"]="<map title not visible>"\n    else:\n        texts["zone_title_raw"]="<map panel closed>"; texts["zone"]="<locked to last confirmed zone>"\n    if current_zone:live_overlay["zone"]=current_zone\n'''
 s=s[:zs]+nz+s[ze:]
 fs=s.index('def show_ocr_status'); fe=s.index('\ndef toggle_pause',fs); b=s[fs:fe]
 needle='''        raw_zone = normalize_zone_candidate(parse_zone(raw.get("zone","")))\n        fallback_zone, map_fallback_raw = map_title_from_window(win)\n'''
 repl='''        raw_zone = normalize_zone_candidate(parse_zone(raw.get("zone","")))\n        fallback_zone, map_fallback_raw = map_title_from_window(win)\n        map_open, map_open_raw = map_panel_is_open(win)\n        if map_open and fallback_zone and plausible_zone_title(fallback_zone):\n            needed=max(1,int(cfg["behavior"].get("stable_zone_reads",3)))\n            for _ in range(needed):update_zone(fallback_zone)\n            if current_zone:live_overlay["zone"]=current_zone\n'''
 if needle not in b:raise SystemExit('F8 zone patch point missing')
 b=b.replace(needle,repl,1); b=b.replace('f"CONFIRMED ZONE: {zone or \'<none>\'}\\n\\n"','f"MAP PANEL OPEN: {\'YES\' if map_open else \'NO\'}\\n" f"CONFIRMED ZONE: {zone or \'<none>\'}\\n\\n"',1); s=s[:fs]+b+s[fe:]
 p.write_text(s,encoding='utf-8')
 c=a/'config.json'; d=json.loads(c.read_text(encoding='utf-8')); d.setdefault('behavior',{}); d['behavior']['zone_update_requires_m_key']=False; d['behavior']['map_panel_dest_detection']=True; d['behavior']['enemy_requires_level']=True; c.write_text(json.dumps(d,indent=2),encoding='utf-8')
 q=a/'app_version.json';
 if q.exists():d=json.loads(q.read_text(encoding='utf-8'));d['version']=V;q.write_text(json.dumps(d,indent=2),encoding='utf-8')
 q=a/'auto_updater.py';
 if q.exists():q.write_text(q.read_text(encoding='utf-8').replace('CURRENT_VERSION = "1.1.33"',f'CURRENT_VERSION = "{V}"'),encoding='utf-8')
 for x in a.rglob('*.py'):
  if '__pycache__' not in x.parts:py_compile.compile(str(x),doraise=True)
 nz=R/'release'/'EnB Droplist.zip.new'
 with zipfile.ZipFile(nz,'w',zipfile.ZIP_DEFLATED) as z:
  for x in w.rglob('*'):
   if x.is_file() and '__pycache__' not in x.parts:z.write(x,x.relative_to(w))
 with zipfile.ZipFile(nz) as z:
  if z.testzip():raise SystemExit('bad output zip')
 nz.replace(Z); sha=hashlib.sha256(Z.read_bytes()).hexdigest(); M.write_text(json.dumps({'name':'EnB Droplist','version':V,'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip','sha256':sha,'release_date':'2026-08-23','release_notes':'Dedicated target Name/Level OCR strips with digit-only Level fallback. Zone updates detect the real open map panel via the Dest footer, and F8 can safely refresh the live zone while the map is open.'},indent=2)+'\n',encoding='utf-8'); print(V,sha,Z.stat().st_size)
finally:shutil.rmtree(w,ignore_errors=True)
