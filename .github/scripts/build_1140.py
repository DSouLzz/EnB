from pathlib import Path
import zipfile,tempfile,shutil,json,hashlib,py_compile
R=Path.cwd(); Z=R/'release'/'EnB Droplist.zip'; M=R/'release'/'version.json'; V='1.1.40'

def main():
    w=Path(tempfile.mkdtemp(prefix='enb140_'))
    try:
        with zipfile.ZipFile(Z) as z:
            if z.testzip(): raise SystemExit('base ZIP corrupt')
            src=w/'src'; src.mkdir(); z.extractall(src)
        p=next(src.rglob('enb_drop_logger_tray.py')); a=p.parent
        s=p.read_text(encoding='utf-8').replace('1.1.39',V)

        # Replace the live zone section structurally instead of matching an exact
        # old block. This survives whitespace/comment changes between releases.
        tick=s.index('def tick():')
        zcall=s.index('map_panel_is_open(win)',tick)
        zs=s.rfind('\n',tick,zcall)+1
        ze=s.index('    last_ocr_texts = dict(texts)',zcall)
        new='''    # 1.1.40: MAP PANEL OPEN is only one signal. Always sample the tight\n    # title strip. If the normal title reader and independent probe agree, the\n    # zone is valid even when the Dest/footer detector incorrectly says NO.\n    map_open,map_open_raw=map_panel_is_open(win)\n    probe_title,probe_support,probe_raw=map_title_probe(win)\n    map_title,map_raw=map_title_from_window(win)\n    texts["map_open"]="YES" if map_open else "NO"\n    texts["map_open_raw"]=map_open_raw\n    texts["map_probe_raw"]=probe_raw\n    texts["zone_title_raw"]=map_raw\n\n    fallback_ok=bool(map_title and plausible_zone_title(map_title))\n    probe_ok=bool(probe_title and plausible_zone_title(probe_title))\n    readers_agree=bool(fallback_ok and probe_ok and title_similarity(map_title,probe_title)>=0.72)\n\n    chosen_zone=""\n    if map_open or map_zone_capture_active():\n        chosen_zone=map_title if fallback_ok else (probe_title if probe_ok else "")\n    elif readers_agree:\n        chosen_zone=map_title\n\n    if chosen_zone and plausible_zone_title(chosen_zone):\n        update_zone(chosen_zone)\n        log(f"MAP LIVE SAMPLE open={map_open} agree={readers_agree} probe={probe_title!r}/{probe_support} title={map_title!r} chosen={chosen_zone!r} candidate={candidate_zone!r} reads={candidate_zone_reads} current={current_zone!r}")\n    else:\n        texts["zone"]="<waiting for agreeing map title readers>"\n    if current_zone:\n        live_overlay["zone"]=current_zone\n\n'''
        s=s[:zs]+new+s[ze:]
        p.write_text(s,encoding='utf-8')

        c=a/'config.json'; d=json.loads(c.read_text(encoding='utf-8')); d.setdefault('behavior',{}).update({'zone_accept_two_reader_agreement':True}); c.write_text(json.dumps(d,indent=2),encoding='utf-8')
        q=a/'app_version.json'
        if q.exists(): d=json.loads(q.read_text(encoding='utf-8')); d['version']=V; q.write_text(json.dumps(d,indent=2),encoding='utf-8')
        q=a/'auto_updater.py'
        if q.exists(): q.write_text(q.read_text(encoding='utf-8').replace('CURRENT_VERSION = "1.1.39"',f'CURRENT_VERSION = "{V}"'),encoding='utf-8')
        for x in a.rglob('*.py'):
            if '__pycache__' not in x.parts: py_compile.compile(str(x),doraise=True)
        nz=w/'EnB Droplist.zip'
        with zipfile.ZipFile(nz,'w',zipfile.ZIP_DEFLATED) as z:
            for x in src.rglob('*'):
                if x.is_file() and '__pycache__' not in x.parts: z.write(x,x.relative_to(src))
        with zipfile.ZipFile(nz) as z:
            if z.testzip(): raise SystemExit('output ZIP corrupt')
            tray=next(n for n in z.namelist() if n.endswith('enb_drop_logger_tray.py')); source=z.read(tray).decode('utf-8')
            for required in ('readers_agree','title_similarity(map_title,probe_title)','update_zone(chosen_zone)','live_overlay["zone"]=current_zone','is_level_only_target_name'):
                if required not in source: raise SystemExit('missing '+required)
        if nz.stat().st_size<40000: raise SystemExit('output ZIP unexpectedly small')
        shutil.copy2(nz,Z); sha=hashlib.sha256(Z.read_bytes()).hexdigest()
        M.write_text(json.dumps({'name':'EnB Droplist','version':V,'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip','sha256':sha,'release_date':'2026-08-24','release_notes':'F8 live zone detection samples the map title every tick and accepts it when the normal title reader and independent probe agree, even when MAP PANEL OPEN incorrectly reports NO. Builder now patches the live zone section structurally.'},indent=2)+'\n',encoding='utf-8')
        print('built',V,Z.stat().st_size,sha)
    finally: shutil.rmtree(w,ignore_errors=True)

if __name__=='__main__': main()
