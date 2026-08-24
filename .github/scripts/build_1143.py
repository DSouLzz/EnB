from pathlib import Path
import zipfile,tempfile,shutil,json,hashlib,py_compile,re
R=Path.cwd(); Z=R/'release'/'EnB Droplist.zip'; M=R/'release'/'version.json'; V='1.1.43'

def need(cond,msg):
    if not cond: raise SystemExit(msg)

def main():
    w=Path(tempfile.mkdtemp(prefix='enb143_'))
    try:
        with zipfile.ZipFile(Z) as z:
            if z.testzip(): raise SystemExit('base ZIP corrupt')
            src=w/'src'; src.mkdir(); z.extractall(src)
        p=next(src.rglob('enb_drop_logger_tray.py')); a=p.parent
        s=p.read_text(encoding='utf-8').replace('1.1.42',V)

        # --- Persistent confirmed enemy identity ---------------------------------
        anchor='last_combat_target_seen_at = 0.0\n'
        need(anchor in s,'combat identity global anchor missing')
        s=s.replace(anchor,anchor+'''# 1.1.43: keep a trusted enemy identity across OCR misses/death/loot.\nlocked_enemy_target = ""\nlocked_enemy_level = ""\nlocked_enemy_seen_at = 0.0\n''',1)

        helper='''def valid_locked_enemy_name(name):\n    name = norm(name)\n    if not name or len(name) < 4:\n        return False\n    if is_level_only_target_name(name):\n        return False\n    if looks_like_navigation_object_name(name):\n        return False\n    if re.search(r"\\b(?:Gate|Way|Field|Observatory)\\b", name, re.I) and not re.search(r"\\b(?:Bot|Wight|Drone|Basilisk|Menace|Infiniti|Cybertronic)\\b", name, re.I):\n        # Navigation/location OCR often receives a bogus Level from nearby HUD text.\n        return False\n    return bool(re.search(r"[A-Za-z]{3}", name))\n\n\n'''
        ta='def update_target(text, fallback_mob="", fallback_cl=""):'
        need(ta in s,'update_target anchor missing')
        s=s.replace(ta,helper+ta,1)

        # tick() must be able to update the trusted lock.
        tg='    global last_combat_target,last_combat_target_cl,last_combat_target_seen_at\n'
        need(tg in s,'tick combat global anchor missing')
        s=s.replace(tg,tg+'    global locked_enemy_target, locked_enemy_level, locked_enemy_seen_at\n',1)

        # When name+Level is confirmed, lock it. This survives later no-Level OCR.
        lv='''        chosen_mob = card_mob or fallback_mob\n        chosen_cl = card_cl\n'''
        need(lv in s,'level target selection anchor missing')
        s=s.replace(lv,lv+'''\n        if chosen_mob and chosen_cl and valid_locked_enemy_name(chosen_mob):\n            locked_enemy_target = chosen_mob\n            locked_enemy_level = chosen_cl\n            locked_enemy_seen_at = time.time()\n            log(f"ENEMY LOCK confirmed mob={locked_enemy_target!r} level={locked_enemy_level!r}")\n''',1)

        # Death transition uses the trusted target first, not a noisy current frame.
        old='register_live_kill(last_combat_target, last_combat_target_cl)'
        need(old in s,'death register anchor missing')
        s=s.replace(old,'register_live_kill(locked_enemy_target or last_combat_target, locked_enemy_level or last_combat_target_cl)',1)

        # A loot-session opening is definitive post-kill evidence. The previous code
        # required 3 death OCR passes although a full OCR pass can take ~20s, making
        # the 8-second recent-live window impossible in practice.
        loot='''        if not loot_session_active:\n            loot_session_active = True\n            loot_session_logged = False\n            hover_items_seen = [hovered] if hovered else []\n            log("Loot session opened.")\n'''
        need(loot in s,'loot session open anchor missing')
        loot_new='''        if not loot_session_active:\n            loot_session_active = True\n            loot_session_logged = False\n            hover_items_seen = [hovered] if hovered else []\n            if (\n                locked_enemy_target\n                and (now - float(locked_enemy_seen_at or 0.0)) <= 90.0\n                and not kill_counted_for_active_target\n            ):\n                register_live_kill(locked_enemy_target, locked_enemy_level)\n                log(f"LOOT KILL linked to enemy lock mob={locked_enemy_target!r} level={locked_enemy_level!r}")\n            log("Loot session opened.")\n'''
        s=s.replace(loot,loot_new,1)

        # Loot rows also use the trusted lock so corpse/nav OCR cannot rename a kill.
        old='''    recent_combat = (\n        bool(last_combat_target)\n        and (now - float(last_combat_target_seen_at or 0.0)) <= 45.0\n    )\n\n    if recent_combat:\n        mob_value = last_combat_target\n        cl_value = last_combat_target_cl\n'''
        need(old in s,'loot combat identity anchor missing')
        new='''    recent_combat = (\n        bool(locked_enemy_target or last_combat_target)\n        and (now - float(locked_enemy_seen_at or last_combat_target_seen_at or 0.0)) <= 90.0\n    )\n\n    if recent_combat:\n        mob_value = locked_enemy_target or last_combat_target\n        cl_value = locked_enemy_level or last_combat_target_cl\n'''
        s=s.replace(old,new,1)

        # --- Zone: two independent agreeing readers are already confirmation -------
        za='def update_zone(text):'
        need(za in s,'update_zone anchor missing')
        confirm='''def confirm_zone_from_agreeing_readers(zone):\n    """Commit a zone immediately only when independent readers agree."""\n    global candidate_zone, candidate_zone_reads, current_zone\n    zone = normalize_zone_candidate(parse_zone(zone))\n    if not zone or not plausible_zone_title(zone):\n        return False\n    bad = {"captured","security","character information","target","current","discovered","faction"}\n    if zone.lower() in bad:\n        return False\n    candidate_zone = zone\n    candidate_zone_reads = max(int(cfg["behavior"].get("stable_zone_reads",3)), 1)\n    if current_zone != zone:\n        log(f"Zone changed (2-reader confirm): {current_zone!r} -> {zone!r}")\n        current_zone = zone\n        live_overlay["zone"] = zone\n        live_overlay["kills"] = 0\n    return True\n\n\n'''
        s=s.replace(za,confirm+za,1)

        # Current 1.1.40+ live block has readers_agree. If they agree, don't wait for
        # 3 more 20-second OCR cycles; commit directly.
        pat='''    if chosen_zone and plausible_zone_title(chosen_zone):\n        update_zone(chosen_zone)\n'''
        need(pat in s,'chosen zone updater anchor missing')
        rep='''    if chosen_zone and plausible_zone_title(chosen_zone):\n        if readers_agree:\n            confirm_zone_from_agreeing_readers(chosen_zone)\n        else:\n            update_zone(chosen_zone)\n'''
        s=s.replace(pat,rep,1)

        # Tighten common false-positive zone words observed in logger_status.
        for word in ('captured','security','character','information'):
            token='"looted"'
            if token in s and f'"{word}"' not in s:
                s=s.replace(token,token+f',"{word}"',1)

        # --- Known runtime exceptions from logger_status ---------------------------
        s=s.replace('CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")','CFG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")')
        # Tk Frame internal padding only accepts a scalar distance, not (top,bottom).
        s=s.replace('tk.Frame(dlg, bg="#f3f3f3", padx=12, pady=(0, 10))','tk.Frame(dlg, bg="#f3f3f3", padx=12, pady=10)')

        p.write_text(s,encoding='utf-8')
        c=a/'config.json'; d=json.loads(c.read_text(encoding='utf-8'))
        d.setdefault('behavior',{}).update({
            'enemy_identity_lock':True,
            'loot_session_confirms_kill':True,
            'zone_two_reader_direct_confirm':True,
            'locked_enemy_max_age_seconds':90
        })
        c.write_text(json.dumps(d,indent=2),encoding='utf-8')
        q=a/'app_version.json'
        if q.exists(): d=json.loads(q.read_text(encoding='utf-8')); d['version']=V; q.write_text(json.dumps(d,indent=2),encoding='utf-8')
        q=a/'auto_updater.py'
        if q.exists(): q.write_text(q.read_text(encoding='utf-8').replace('CURRENT_VERSION = "1.1.42"',f'CURRENT_VERSION = "{V}"'),encoding='utf-8')

        for x in a.rglob('*.py'):
            if '__pycache__' not in x.parts: py_compile.compile(str(x),doraise=True)

        nz=w/'EnB Droplist.zip'
        with zipfile.ZipFile(nz,'w',zipfile.ZIP_DEFLATED) as z:
            for x in src.rglob('*'):
                if x.is_file() and '__pycache__' not in x.parts: z.write(x,x.relative_to(src))
        with zipfile.ZipFile(nz) as z:
            if z.testzip(): raise SystemExit('output ZIP corrupt')
            tray=next(n for n in z.namelist() if n.endswith('enb_drop_logger_tray.py'))
            source=z.read(tray).decode('utf-8')
            checks=(
                'ENEMY LOCK confirmed',
                'LOOT KILL linked to enemy lock',
                'confirm_zone_from_agreeing_readers',
                'CFG_PATH.write_text',
                'GetAsyncKeyState(vk_f8)',
                'is_level_only_target_name',
            )
            for required in checks:
                if required not in source: raise SystemExit('missing '+required)
            if 'CONFIG.write_text' in source: raise SystemExit('old CONFIG write remains')
            if 'pady=(0, 10)' in source and 'tk.Frame(dlg' in source: raise SystemExit('bad Tk Frame pady remains')
        if nz.stat().st_size<40000: raise SystemExit('output ZIP unexpectedly small')
        shutil.copy2(nz,Z); sha=hashlib.sha256(Z.read_bytes()).hexdigest()
        M.write_text(json.dumps({
            'name':'EnB Droplist','version':V,
            'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip',
            'sha256':sha,'release_date':'2026-08-24',
            'release_notes':'Locks confirmed enemy name+Level through death/loot, registers a kill when the corpse loot session opens, attaches loot to that locked enemy, commits map zones immediately when two independent readers agree, rejects common false zone words, and fixes CONFIG overlay-position plus transparent-dialog Tk errors. Keeps 1.1.42 physical F8 polling.'
        },indent=2)+'\n',encoding='utf-8')
        print('built',V,Z.stat().st_size,sha)
    finally:
        shutil.rmtree(w,ignore_errors=True)

if __name__=='__main__': main()
