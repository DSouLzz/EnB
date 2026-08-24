from pathlib import Path
import zipfile,tempfile,shutil,json,hashlib,py_compile,re
R=Path.cwd(); Z=R/'release'/'EnB Droplist.zip'; M=R/'release'/'version.json'; V='1.1.35'
try:
    if json.loads(M.read_text(encoding='utf-8')).get('version')==V: raise SystemExit(0)
except Exception: pass
w=Path(tempfile.mkdtemp(prefix='enb135_'))
try:
    with zipfile.ZipFile(Z) as z:
        if z.testzip(): raise SystemExit('bad input zip')
        z.extractall(w)
    p=next(w.rglob('enb_drop_logger_tray.py')); a=p.parent
    s=p.read_text(encoding='utf-8').replace('1.1.34',V)

    # Same-Tk-thread diagnostic queue + cached EnB window.
    anchor='overlay_stop_requested = threading.Event()\n'
    if anchor not in s: raise SystemExit('overlay event anchor missing')
    s=s.replace(anchor,anchor+'\n# 1.1.35 resilient OCR/UI state\noverlay_dialog_requests=[]\noverlay_dialog_lock=threading.Lock()\n_last_enb_window=None\n_last_enb_window_seen=0.0\n',1)

    # Robust window lookup: retry and reuse last valid client.
    st=s.index('def find_window():'); en=s.index('\ndef grab(',st)
    nf='''def _window_usable(win):\n    if win is None:return False\n    try:\n        needle=cfg["window_title_contains"].lower()\n        return needle in (win.title or "").lower() and int(win.width)>0 and int(win.height)>0\n    except Exception:return False\n\ndef find_window(retries=3,delay=0.10):\n    global _last_enb_window,_last_enb_window_seen\n    if _window_usable(_last_enb_window):return _last_enb_window\n    needle=cfg["window_title_contains"].lower()\n    for attempt in range(max(1,int(retries))):\n        try:\n            wins=[w for w in gw.getAllWindows() if needle in (w.title or "").lower() and int(w.width)>0 and int(w.height)>0]\n            if wins:\n                wins.sort(key=lambda w:int(w.width)*int(w.height),reverse=True)\n                _last_enb_window=wins[0];_last_enb_window_seen=time.time();return _last_enb_window\n        except Exception as e:log(f"Window lookup attempt {attempt+1} failed: {e!r}")\n        if attempt+1<max(1,int(retries)):time.sleep(float(delay))\n    if _window_usable(_last_enb_window):return _last_enb_window\n    return None\n\ndef queue_overlay_dialog(title,text):\n    with overlay_dialog_lock:overlay_dialog_requests.append((str(title),str(text)))\n\n'''
    s=s[:st]+nf+s[en:]

    # Map detection from either Dest footer OR independent repeated map-title OCR.
    st=s.index('def map_panel_is_open(win):'); en=s.index('\ndef map_title_from_window',st)
    nm='''def _clean_map_probe(raw):\n    x=normalize_zone_candidate(clean_title_line(raw))\n    return x if x and plausible_zone_title(x) else ""\n\ndef map_title_probe(win):\n    readings=[]\n    for reg in ((0.235,0.205,0.420,0.305),(0.255,0.235,0.390,0.320)):\n        for psm in (7,11):\n            try:\n                raw=client_sparse_ocr(win,*reg,psm);cand=_clean_map_probe(raw);readings.append((cand,raw,psm,reg))\n            except Exception as e:readings.append(("",f"<probe error {e!r}>",psm,reg))\n    valid=[x[0] for x in readings if x[0]]\n    if not valid:return "",0,"\\n".join(x[1] for x in readings)\n    best="";support=0\n    for cand in valid:\n        n=sum(1 for other in valid if title_similarity(cand,other)>=0.80)\n        if n>support:best,support=cand,n\n    dbg="\\n".join(f"{r} [psm{psm} {reg}] -> {c!r}" for c,r,psm,reg in readings)\n    return best,support,dbg\n\ndef map_panel_is_open(win):\n    try:\n        raw1=client_sparse_ocr(win,0.135,0.745,0.615,0.845,7);raw2=client_sparse_ocr(win,0.135,0.745,0.615,0.845,11)\n        dest_ok=bool(re.search(r"\\bDest\\s*:",norm(raw1+" "+raw2),re.I))\n        title,support,probe_raw=map_title_probe(win);title_ok=bool(title and support>=2)\n        return (dest_ok or title_ok),f"DEST_OK={dest_ok} TITLE_OK={title_ok} TITLE={title!r} SUPPORT={support}\\n"+raw1+"\\n"+raw2+"\\n"+probe_raw\n    except Exception as e:return False,f"<map-open OCR error: {e!r}>"\n\n'''
    s=s[:st]+nm+s[en:]

    # Replace only the zone section in tick; leave kill/Level logic untouched.
    ts=s.index('def tick():')
    zcall=s.index('map_panel_is_open(win)',ts)
    zs=s.rfind('\n',ts,zcall)+1
    ze=s.index('    last_ocr_texts = dict(texts)',zcall)
    nz='''    map_open,map_open_raw=map_panel_is_open(win)\n    probe_title,probe_support,probe_raw=map_title_probe(win)\n    texts["map_open"]="YES" if map_open else "NO";texts["map_open_raw"]=map_open_raw;texts["map_probe_raw"]=probe_raw\n    if map_open or map_zone_capture_active() or probe_support>=2:\n        map_title,map_raw=map_title_from_window(win);texts["zone_title_raw"]=map_raw\n        chosen_zone=map_title if map_title and plausible_zone_title(map_title) else probe_title\n        if chosen_zone and plausible_zone_title(chosen_zone):\n            update_zone(chosen_zone);log(f"MAP LIVE SAMPLE open={map_open} probe={probe_title!r}/{probe_support} title={map_title!r} chosen={chosen_zone!r} candidate={candidate_zone!r} reads={candidate_zone_reads} current={current_zone!r}")\n        else:texts["zone"]="<map title not visible>"\n    else:\n        texts["zone_title_raw"]="<map panel closed>";texts["zone"]="<locked to last confirmed zone>"\n    if current_zone:live_overlay["zone"]=current_zone\n\n'''
    s=s[:zs]+nz+s[ze:]

    # OCR Status/Test retries window discovery and never creates Tk from hotkey thread.
    fs=s.index('def show_ocr_status');fe=s.index('\ndef toggle_pause',fs);b=s[fs:fe]
    b=b.replace('        win = find_window()\n','        win = find_window(retries=6, delay=0.15)\n',1)
    b=b.replace('            message_box("EnB Droplist OCR Status", "Earth & Beyond window was not found.")\n','            queue_overlay_dialog("EnB Droplist OCR Status", "Earth & Beyond window was not found after several retries.\\n\\nThe live F8 overlay is still running; bring EnB to the foreground and try again.")\n',1)
    b=b.replace('message_box("EnB Droplist OCR Status / Test", text)','queue_overlay_dialog("EnB Droplist OCR Status / Test", text)',1)
    b=b.replace('message_box("OCR Status failed", f"{type(e).__name__}: {e}")','queue_overlay_dialog("OCR Status failed", f"{type(e).__name__}: {e}")',1)
    if 'map_open,map_open_raw=map_panel_is_open(win)' not in b and 'map_open, map_open_raw = map_panel_is_open(win)' not in b: raise SystemExit('status map-open marker missing')
    # Add probe as fallback to existing F8 zone refresh block.
    marker='        map_open, map_open_raw = map_panel_is_open(win)\n'
    if marker in b:b=b.replace(marker,marker+'        probe_zone, probe_support, probe_raw = map_title_probe(win)\n',1)
    else:
        marker='        map_open,map_open_raw=map_panel_is_open(win)\n';b=b.replace(marker,marker+'        probe_zone,probe_support,probe_raw=map_title_probe(win)\n',1)
    b=b.replace('if map_open and fallback_zone and plausible_zone_title(fallback_zone):','if (map_open or probe_support >= 2) and ((fallback_zone and plausible_zone_title(fallback_zone)) or probe_zone):',1)
    b=b.replace('update_zone(fallback_zone)','update_zone(fallback_zone if fallback_zone and plausible_zone_title(fallback_zone) else probe_zone)',1)
    s=s[:fs]+b+s[fe:]

    # Make OCR status dialogs on the overlay Tk thread so F8 cannot be killed by Tk cross-thread calls.
    op=s.index('def overlay_thread():');poll=s.index('        def poll():',op)
    dialog='''        def show_overlay_dialog(title,text):\n            dlg=tk.Toplevel(root);dlg.title(title);dlg.attributes("-topmost",True)\n            try:dlg.attributes("-alpha",float(cfg.get("ui",{}).get("dialog_opacity",0.82)))\n            except Exception:dlg.attributes("-alpha",0.82)\n            body=tk.Frame(dlg,padx=12,pady=10);body.pack(fill="both",expand=True)\n            txt=tk.Text(body,wrap="word",width=78,height=30,font=("Segoe UI",9),relief="flat");sb=tk.Scrollbar(body,command=txt.yview);txt.configure(yscrollcommand=sb.set);txt.insert("1.0",text);txt.configure(state="disabled");txt.pack(side="left",fill="both",expand=True);sb.pack(side="right",fill="y")\n            buttons=tk.Frame(dlg,padx=12,pady=(0,10));buttons.pack(fill="x");tk.Button(buttons,text="OK",width=10,command=dlg.destroy).pack(side="right")\n            dlg.geometry("650x600");dlg.update_idletasks();sw,sh=dlg.winfo_screenwidth(),dlg.winfo_screenheight();ww,hh=dlg.winfo_width(),dlg.winfo_height();dlg.geometry(f"+{max(0,(sw-ww)//2)}+{max(0,(sh-hh)//2)}");dlg.deiconify();dlg.focus_force()\n\n'''
    s=s[:poll]+dialog+s[poll:]
    needle='            zone_var.set(f"Zone: {live_overlay.get(\'zone\') or \'Unknown / not read\'}")\n'
    if needle not in s:raise SystemExit('overlay zone var marker missing')
    consume='''            requests=[]\n            with overlay_dialog_lock:\n                if overlay_dialog_requests:requests[:]=overlay_dialog_requests[:];overlay_dialog_requests.clear()\n            for title,text in requests:show_overlay_dialog(title,text)\n\n'''
    s=s.replace(needle,consume+needle,1)

    p.write_text(s,encoding='utf-8')
    c=a/'config.json';d=json.loads(c.read_text(encoding='utf-8'));d.setdefault('behavior',{}).update({'map_title_probe_min_support':2,'window_lookup_retries':6});c.write_text(json.dumps(d,indent=2),encoding='utf-8')
    q=a/'app_version.json'
    if q.exists():d=json.loads(q.read_text(encoding='utf-8'));d['version']=V;q.write_text(json.dumps(d,indent=2),encoding='utf-8')
    q=a/'auto_updater.py'
    if q.exists():q.write_text(q.read_text(encoding='utf-8').replace('CURRENT_VERSION = "1.1.34"',f'CURRENT_VERSION = "{V}"'),encoding='utf-8')
    for x in a.rglob('*.py'):
        if '__pycache__' not in x.parts:py_compile.compile(str(x),doraise=True)
    nz=R/'release'/'EnB Droplist.zip.new'
    with zipfile.ZipFile(nz,'w',zipfile.ZIP_DEFLATED) as z:
        for x in w.rglob('*'):
            if x.is_file() and '__pycache__' not in x.parts:z.write(x,x.relative_to(w))
    with zipfile.ZipFile(nz) as z:
        if z.testzip():raise SystemExit('bad output zip')
    nz.replace(Z);sha=hashlib.sha256(Z.read_bytes()).hexdigest()
    M.write_text(json.dumps({'name':'EnB Droplist','version':V,'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip','sha256':sha,'release_date':'2026-08-24','release_notes':'F8/OCR Status uses resilient EnB-window reconnection and same-thread Tk diagnostics. Zone detection accepts the map Dest footer or repeated agreement from a dedicated map-title probe, so valid map zones no longer remain Unknown when Dest OCR is missed.'},indent=2)+'\n',encoding='utf-8')
    print(V,sha,Z.stat().st_size)
finally:
    shutil.rmtree(w,ignore_errors=True)
