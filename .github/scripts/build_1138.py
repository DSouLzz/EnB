from pathlib import Path
import zipfile,tempfile,shutil,json,hashlib,py_compile,re
R=Path.cwd(); Z=R/'release'/'EnB Droplist.zip'; M=R/'release'/'version.json'; V='1.1.38'

def main():
    w=Path(tempfile.mkdtemp(prefix='enb138_'))
    try:
        with zipfile.ZipFile(Z) as z:
            if z.testzip(): raise SystemExit('base ZIP corrupt')
            src=w/'src'; src.mkdir(); z.extractall(src)
        p=next(src.rglob('enb_drop_logger_tray.py')); a=p.parent
        s=p.read_text(encoding='utf-8').replace('1.1.37',V)

        # A Level line is evidence of an enemy, never the mob name itself.
        marker='def target_title_from_window(win):'
        helper='''def is_level_only_target_name(name):\n    x = norm(name)\n    return bool(re.fullmatch(r"(?:Level|Lvl|Lv)\\s*[:.\\-]?\\s*\\d{1,3}", x, re.I))\n\n\n'''
        if 'def is_level_only_target_name' not in s:
            if marker not in s: raise SystemExit('target title anchor missing')
            s=s.replace(marker,helper+marker,1)

        # Reject Level N anywhere the target-title cleaner is about to accept a name.
        nav='''        if looks_like_navigation_object_name(x):\n            return ""\n        return x\n'''
        stricter='''        if is_level_only_target_name(x):\n            return ""\n        if looks_like_navigation_object_name(x):\n            return ""\n        return x\n'''
        if nav in s: s=s.replace(nav,stricter,1)
        elif 'if is_level_only_target_name(x):' not in s: raise SystemExit('target cleaner anchor missing')

        # Also protect DEST/reticle fallbacks from accepting a level-only string.
        s=s.replace('3 <= len(name) <= 80 and not looks_like_navigation_object_name(name)',
                    '3 <= len(name) <= 80 and not is_level_only_target_name(name) and not looks_like_navigation_object_name(name)')
        s=s.replace('3 <= len(candidate) <= 80 and not looks_like_navigation_object_name(candidate)',
                    '3 <= len(candidate) <= 80 and not is_level_only_target_name(candidate) and not looks_like_navigation_object_name(candidate)')

        # OCR Status/Test already knows the confirmed map zone. Feed that result into the
        # same zone state used by the F8 overlay instead of only printing it in diagnostics.
        status=s.index('def _show_ocr_status_impl():') if 'def _show_ocr_status_impl():' in s else s.index('def show_ocr_status(*_):')
        end=s.index('\ndef load_overlay_position',status)
        block=s[status:end]
        anchor='        hover_item, hover_raw = read_hover_item(win)\n'
        sync='''        if zone and plausible_zone_title(zone):\n            update_zone(zone)\n\n        hover_item, hover_raw = read_hover_item(win)\n'''
        if anchor in block and 'update_zone(zone)' not in block:
            block=block.replace(anchor,sync,1); s=s[:status]+block+s[end:]
        elif 'update_zone(zone)' not in block:
            raise SystemExit('OCR status zone-sync anchor missing')

        p.write_text(s,encoding='utf-8')
        c=a/'config.json'; d=json.loads(c.read_text(encoding='utf-8')); d.setdefault('behavior',{}).update({'reject_level_only_target_names':True,'ocr_status_syncs_confirmed_zone':True}); c.write_text(json.dumps(d,indent=2),encoding='utf-8')
        q=a/'app_version.json'
        if q.exists(): d=json.loads(q.read_text(encoding='utf-8')); d['version']=V; q.write_text(json.dumps(d,indent=2),encoding='utf-8')
        q=a/'auto_updater.py'
        if q.exists(): q.write_text(q.read_text(encoding='utf-8').replace('CURRENT_VERSION = "1.1.37"',f'CURRENT_VERSION = "{V}"'),encoding='utf-8')
        for x in a.rglob('*.py'):
            if '__pycache__' not in x.parts: py_compile.compile(str(x),doraise=True)
        nz=w/'EnB Droplist.zip'
        with zipfile.ZipFile(nz,'w',zipfile.ZIP_DEFLATED) as z:
            for x in src.rglob('*'):
                if x.is_file() and '__pycache__' not in x.parts: z.write(x,x.relative_to(src))
        with zipfile.ZipFile(nz) as z:
            if z.testzip(): raise SystemExit('output ZIP corrupt')
            tray=next(n for n in z.namelist() if n.endswith('enb_drop_logger_tray.py')); source=z.read(tray).decode('utf-8')
            for required in ('is_level_only_target_name','update_zone(zone)','ZONE SOURCE:'):
                if required not in source: raise SystemExit('missing '+required)
        if nz.stat().st_size<40000: raise SystemExit('output ZIP unexpectedly small')
        shutil.copy2(nz,Z); sha=hashlib.sha256(Z.read_bytes()).hexdigest()
        M.write_text(json.dumps({'name':'EnB Droplist','version':V,'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip','sha256':sha,'release_date':'2026-08-24','release_notes':'Target OCR never accepts Level/Lvl/Lv plus a number as the mob name. Enemy recognition still requires a level signal, and OCR Status/Test now syncs its confirmed map zone into the F8 overlay.'},indent=2)+'\n',encoding='utf-8')
        print('built',V,Z.stat().st_size,sha)
    finally: shutil.rmtree(w,ignore_errors=True)

if __name__=='__main__': main()
