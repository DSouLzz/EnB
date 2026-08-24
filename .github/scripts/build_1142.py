from pathlib import Path
import zipfile,tempfile,shutil,json,hashlib,py_compile
R=Path.cwd(); Z=R/'release'/'EnB Droplist.zip'; M=R/'release'/'version.json'; V='1.1.42'

def main():
    w=Path(tempfile.mkdtemp(prefix='enb142_'))
    try:
        with zipfile.ZipFile(Z) as z:
            if z.testzip(): raise SystemExit('base ZIP corrupt')
            src=w/'src'; src.mkdir(); z.extractall(src)
        p=next(src.rglob('enb_drop_logger_tray.py')); a=p.parent
        s=p.read_text(encoding='utf-8').replace('1.1.41',V)

        # 1.1.42: do not rely on RegisterHotKey. Earth & Beyond can consume
        # function-key input while focused. Poll the physical F8 key state and
        # toggle only on the up->down edge, which works even when the game is active.
        hs=s.index('def hotkey_thread():')
        he=s.index('\ndef cursor_pos()', hs)
        new_hotkey='''def hotkey_thread():\n    try:\n        user32 = ctypes.windll.user32\n        vk_f8 = 0x77\n        was_down = False\n        log("F8 hotkey mode: GetAsyncKeyState edge polling.")\n\n        while running:\n            down = bool(user32.GetAsyncKeyState(vk_f8) & 0x8000)\n            if down and not was_down:\n                overlay_toggle_requested.set()\n                log("F8 overlay toggle requested (physical key edge).")\n            was_down = down\n            time.sleep(0.015)\n    except Exception as e:\n        log(f"Hotkey error: {e!r}")\n\n\n'''
        s=s[:hs]+new_hotkey+s[he+1:]

        p.write_text(s,encoding='utf-8')
        c=a/'config.json'; d=json.loads(c.read_text(encoding='utf-8')); d.setdefault('behavior',{}).update({'f8_hotkey_mode':'GetAsyncKeyState edge polling'}); c.write_text(json.dumps(d,indent=2),encoding='utf-8')
        q=a/'app_version.json'
        if q.exists(): d=json.loads(q.read_text(encoding='utf-8')); d['version']=V; q.write_text(json.dumps(d,indent=2),encoding='utf-8')
        q=a/'auto_updater.py'
        if q.exists(): q.write_text(q.read_text(encoding='utf-8').replace('CURRENT_VERSION = "1.1.41"',f'CURRENT_VERSION = "{V}"'),encoding='utf-8')
        for x in a.rglob('*.py'):
            if '__pycache__' not in x.parts: py_compile.compile(str(x),doraise=True)
        nz=w/'EnB Droplist.zip'
        with zipfile.ZipFile(nz,'w',zipfile.ZIP_DEFLATED) as z:
            for x in src.rglob('*'):
                if x.is_file() and '__pycache__' not in x.parts: z.write(x,x.relative_to(src))
        with zipfile.ZipFile(nz) as z:
            if z.testzip(): raise SystemExit('output ZIP corrupt')
            tray=next(n for n in z.namelist() if n.endswith('enb_drop_logger_tray.py')); source=z.read(tray).decode('utf-8')
            for required in ('GetAsyncKeyState(vk_f8)','physical key edge','overlay_toggle_requested.set()','readers_agree','is_level_only_target_name'):
                if required not in source: raise SystemExit('missing '+required)
            if 'RegisterHotKey(None' in source: raise SystemExit('old RegisterHotKey path still present')
        if nz.stat().st_size<40000: raise SystemExit('output ZIP unexpectedly small')
        shutil.copy2(nz,Z); sha=hashlib.sha256(Z.read_bytes()).hexdigest()
        M.write_text(json.dumps({'name':'EnB Droplist','version':V,'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip','sha256':sha,'release_date':'2026-08-24','release_notes':'F8 no longer uses RegisterHotKey. It now polls the physical F8 key state with GetAsyncKeyState and toggles on the key-down edge, so the overlay can be shown/hidden while Earth & Beyond itself has focus.'},indent=2)+'\n',encoding='utf-8')
        print('built',V,Z.stat().st_size,sha)
    finally: shutil.rmtree(w,ignore_errors=True)

if __name__=='__main__': main()
