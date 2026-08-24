from pathlib import Path
import zipfile,tempfile,shutil,json,hashlib,py_compile,re
R=Path.cwd(); Z=R/'release'/'EnB Droplist.zip'; M=R/'release'/'version.json'; V='1.1.39'

def main():
    w=Path(tempfile.mkdtemp(prefix='enb139_'))
    try:
        with zipfile.ZipFile(Z) as z:
            if z.testzip(): raise SystemExit('base ZIP corrupt')
            src=w/'src'; src.mkdir(); z.extractall(src)
        p=next(src.rglob('enb_drop_logger_tray.py')); a=p.parent
        s=p.read_text(encoding='utf-8').replace('1.1.38',V)

        # OCR Status/Test has already confirmed the map title. Do not feed that
        # confirmation back through the normal multi-read stabilizer: commit it
        # directly to the same state consumed by the F8 overlay.
        status=s.index('def _show_ocr_status_impl():') if 'def _show_ocr_status_impl():' in s else s.index('def show_ocr_status(*_):')
        end=s.index('\ndef load_overlay_position',status)
        block=s[status:end]
        old='''        if zone and plausible_zone_title(zone):\n            update_zone(zone)\n\n        hover_item, hover_raw = read_hover_item(win)\n'''
        new='''        if zone and plausible_zone_title(zone):\n            # This zone came from the confirmed map-title probe, so publish it\n            # immediately instead of requiring another stable-read cycle.\n            global current_zone, zone_candidate, zone_candidate_count\n            current_zone = zone\n            zone_candidate = zone\n            zone_candidate_count = max(int(globals().get("ZONE_STABLE_READS", 1)), 1)\n            try:\n                live_overlay["zone"] = zone\n            except Exception:\n                pass\n\n        hover_item, hover_raw = read_hover_item(win)\n'''
        if old in block:
            block=block.replace(old,new,1)
        elif 'update_zone(zone)' in block:
            block=block.replace('            update_zone(zone)\n',new.split('        hover_item')[0][8:],1)
        else:
            raise SystemExit('1.1.38 zone-sync anchor missing')
        s=s[:status]+block+s[end:]

        p.write_text(s,encoding='utf-8')
        c=a/'config.json'; d=json.loads(c.read_text(encoding='utf-8')); d.setdefault('behavior',{}).update({'ocr_status_confirmed_zone_direct_overlay_sync':True}); c.write_text(json.dumps(d,indent=2),encoding='utf-8')
        q=a/'app_version.json'
        if q.exists(): d=json.loads(q.read_text(encoding='utf-8')); d['version']=V; q.write_text(json.dumps(d,indent=2),encoding='utf-8')
        q=a/'auto_updater.py'
        if q.exists(): q.write_text(q.read_text(encoding='utf-8').replace('CURRENT_VERSION = "1.1.38"',f'CURRENT_VERSION = "{V}"'),encoding='utf-8')
        for x in a.rglob('*.py'):
            if '__pycache__' not in x.parts: py_compile.compile(str(x),doraise=True)
        nz=w/'EnB Droplist.zip'
        with zipfile.ZipFile(nz,'w',zipfile.ZIP_DEFLATED) as z:
            for x in src.rglob('*'):
                if x.is_file() and '__pycache__' not in x.parts: z.write(x,x.relative_to(src))
        with zipfile.ZipFile(nz) as z:
            if z.testzip(): raise SystemExit('output ZIP corrupt')
            tray=next(n for n in z.namelist() if n.endswith('enb_drop_logger_tray.py')); source=z.read(tray).decode('utf-8')
            for required in ('is_level_only_target_name','current_zone = zone','live_overlay["zone"] = zone','ZONE SOURCE:'):
                if required not in source: raise SystemExit('missing '+required)
        if nz.stat().st_size<40000: raise SystemExit('output ZIP unexpectedly small')
        shutil.copy2(nz,Z); sha=hashlib.sha256(Z.read_bytes()).hexdigest()
        M.write_text(json.dumps({'name':'EnB Droplist','version':V,'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip','sha256':sha,'release_date':'2026-08-24','release_notes':'Confirmed map zone from OCR Status/Test is now published directly to the F8 overlay, avoiding the extra stable-read cycle. Keeps the 1.1.38 enemy Level/name OCR fixes.'},indent=2)+'\n',encoding='utf-8')
        print('built',V,Z.stat().st_size,sha)
    finally: shutil.rmtree(w,ignore_errors=True)

if __name__=='__main__': main()
