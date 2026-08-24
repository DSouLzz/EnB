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

        old='''    # 1.1.37: update zone only while the actual map panel is open.\n    map_open,map_open_raw=map_panel_is_open(win)\n    probe_title,probe_support,probe_raw=map_title_probe(win)\n    texts["map_open"]="YES" if map_open else "NO"\n    texts["map_open_raw"]=map_open_raw\n    texts["map_probe_raw"]=probe_raw\n\n    if map_open or map_zone_capture_active() or probe_support>=3:\n        map_title,map_raw=map_title_from_window(win)\n        texts["zone_title_raw"]=map_raw\n        # If full multipass is noisy but the independent title probe agrees, use probe.\n        chosen_zone = map_title if map_title and plausible_zone_title(map_title) else probe_title\n        if chosen_zone and plausible_zone_title(chosen_zone):\n            update_zone(chosen_zone)\n            log(\n                f"MAP LIVE SAMPLE open={map_open} probe={probe_title!r}/{probe_support} "\n                f"title={map_title!r} chosen={chosen_zone!r} "\n                f"candidate={candidate_zone!r} reads={candidate_zone_reads} current={current_zone!r}"\n            )\n        else:\n            texts["zone"]="<map title not visible>"\n    else:\n        texts["zone_title_raw"]="<map panel closed>"\n        texts["zone"]="<locked to last confirmed zone>"\n'''
        new='''    # 1.1.40: map-open OCR is only one signal. Some EnB layouts clearly show\n    # the map title while the Dest/footer detector still says NO. Always sample\n    # the tight title strip and accept it when two independent readers agree.\n    map_open,map_open_raw=map_panel_is_open(win)\n    probe_title,probe_support,probe_raw=map_title_probe(win)\n    map_title,map_raw=map_title_from_window(win)\n    texts["map_open"]="YES" if map_open else "NO"\n    texts["map_open_raw"]=map_open_raw\n    texts["map_probe_raw"]=probe_raw\n    texts["zone_title_raw"]=map_raw\n\n    fallback_ok = bool(map_title and plausible_zone_title(map_title))\n    probe_ok = bool(probe_title and plausible_zone_title(probe_title))\n    readers_agree = bool(\n        fallback_ok and probe_ok\n        and title_similarity(map_title, probe_title) >= 0.72\n    )\n\n    chosen_zone = ""\n    if map_open or map_zone_capture_active():\n        chosen_zone = map_title if fallback_ok else (probe_title if probe_ok else "")\n    elif readers_agree:\n        # This is the important 1.1.40 fallback: e.g. both readers say Earth\n        # even though MAP PANEL OPEN incorrectly reports NO.\n        chosen_zone = map_title\n\n    if chosen_zone and plausible_zone_title(chosen_zone):\n        update_zone(chosen_zone)\n        log(\n            f"MAP LIVE SAMPLE open={map_open} agree={readers_agree} "\n            f"probe={probe_title!r}/{probe_support} title={map_title!r} "\n            f"chosen={chosen_zone!r} candidate={candidate_zone!r} "\n            f"reads={candidate_zone_reads} current={current_zone!r}"\n        )\n    else:\n        texts["zone"]="<waiting for agreeing map title readers>"\n'''
        if old not in s: raise SystemExit('live zone block anchor missing')
        s=s.replace(old,new,1)
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
            for required in ('readers_agree','title_similarity(map_title, probe_title)','update_zone(chosen_zone)','is_level_only_target_name'):
                if required not in source: raise SystemExit('missing '+required)
        if nz.stat().st_size<40000: raise SystemExit('output ZIP unexpectedly small')
        shutil.copy2(nz,Z); sha=hashlib.sha256(Z.read_bytes()).hexdigest()
        M.write_text(json.dumps({'name':'EnB Droplist','version':V,'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip','sha256':sha,'release_date':'2026-08-24','release_notes':'F8 zone detection no longer depends solely on MAP PANEL OPEN. The live scanner now accepts a zone when the tight map-title reader and independent probe agree, fixing cases where Earth/Kailaasa is visible but MAP PANEL OPEN reports NO.'},indent=2)+'\n',encoding='utf-8')
        print('built',V,Z.stat().st_size,sha)
    finally: shutil.rmtree(w,ignore_errors=True)

if __name__=='__main__': main()
