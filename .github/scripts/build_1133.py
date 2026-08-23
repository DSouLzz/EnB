from pathlib import Path
import zipfile,tempfile,shutil,json,hashlib,py_compile,re
R=Path.cwd(); Z=R/'release'/'EnB Droplist.zip'; M=R/'release'/'version.json'; V='1.1.33'
try:
 if json.loads(M.read_text()).get('version')==V: raise SystemExit(0)
except Exception: pass
w=Path(tempfile.mkdtemp())
try:
 with zipfile.ZipFile(Z) as z:
  if z.testzip(): raise SystemExit('bad input zip')
  z.extractall(w)
 p=next(w.rglob('enb_drop_logger_tray.py')); a=p.parent; s=p.read_text().replace('1.1.32',V)
 s=s.replace('loot_session_logged = False\n','''loot_session_logged = False\ndeath_candidate_reads=0\nkill_counted_for_active_target=False\npending_kill_row=0\npending_kill_ts=""\npending_kill_mob=""\npending_kill_cl=""\n''',1)
 mark='\ndef client_rect_screen(win):'
 h=r'''
def append_kill_only(kill):
 path=(BASE/cfg["excel_file"]).resolve()
 try:
  wb=load_workbook(path); ws=wb["Kills"]; ws.append(kill); row=ws.max_row; rebuild_summary(wb); wb.save(path); wb.close(); log(f"XLSX KILL SAVED row={row} mob={kill[2]!r}"); return row
 except Exception as e: log(f"XLSX KILL FAIL: {e!r}"); return 0

def append_drops_to_existing_kill(row,drops):
 if not drops:return True
 path=(BASE/cfg["excel_file"]).resolve()
 try:
  wb=load_workbook(path); kw=wb["Kills"]; dw=wb["Drops"]
  if dw.cell(2,10).value!="Item Image":dw.cell(2,10).value="Item Image"
  for x in drops:dw.append(x)
  if row and 1<=int(row)<=kw.max_row:kw.cell(int(row),5).value=len(drops)
  rebuild_summary(wb); wb.save(path); wb.close(); log(f"XLSX DROPS ATTACHED kill_row={row} drop_rows={len(drops)}"); return True
 except Exception as e:log(f"XLSX DROP ATTACH FAIL: {e!r}"); return False

def register_live_kill(mob,cl):
 global kill_counted_for_active_target,pending_kill_row,pending_kill_ts,pending_kill_mob,pending_kill_cl
 if kill_counted_for_active_target or not mob:return False
 ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"); zone=current_zone or live_overlay.get("zone") or "Unknown / press M"
 kill_counted_for_active_target=True; live_overlay["zone"]=zone; live_overlay["kills"]=int(live_overlay.get("kills",0))+1
 pending_kill_ts=ts; pending_kill_mob=mob; pending_kill_cl=cl or ""; pending_kill_row=append_kill_only([ts,zone,mob,cl or "",0,"","Live Level-loss death transition; awaiting hovered loot"])
 log(f"LIVE KILL CONFIRMED zone={zone!r} kills={live_overlay['kills']} mob={mob!r} level={cl!r}"); notify("Kill detected",f"{zone} | Kill {live_overlay['kills']} | {mob}"); return True

'''
 if mark not in s:raise SystemExit('helper marker missing')
 s=s.replace(mark,h+mark,1)
 old='''    # Live Zone uses exactly the same multipass/fuzzy OCR as OCR Status/Test.\n    map_title, map_raw = map_title_from_window(win)\n    texts["zone_title_raw"] = map_raw\n\n    if map_title and plausible_zone_title(map_title):\n        update_zone(map_title)\n\n        # update_zone() owns the stable/fuzzy decision. Once it has accepted a\n        # current zone, the overlay mirrors it unconditionally.\n        if current_zone:\n            live_overlay["zone"] = current_zone\n\n        log(\n            f"MAP LIVE SAMPLE title={map_title!r} "\n            f"candidate={candidate_zone!r} reads={candidate_zone_reads} "\n            f"current={current_zone!r} overlay={live_overlay['zone']!r}"\n        )\n    else:\n        texts["zone"] = "<map title not visible>"\n        if current_zone:\n            # Keep the last confirmed zone in F8 until a new stable zone is accepted.\n            live_overlay["zone"] = current_zone\n'''
 new='''    if map_zone_capture_active():\n        map_title,map_raw=map_title_from_window(win); texts["zone_title_raw"]=map_raw\n        if map_title and plausible_zone_title(map_title): update_zone(map_title); log(f"MAP M-WINDOW SAMPLE title={map_title!r} candidate={candidate_zone!r} reads={candidate_zone_reads} current={current_zone!r}")\n    else:\n        texts["zone_title_raw"]="<M capture inactive>"; texts["zone"]="<locked to last confirmed zone>"\n    if current_zone: live_overlay["zone"]=current_zone\n'''
 if old not in s:raise SystemExit('zone block missing')
 s=s.replace(old,new,1)
 s=s.replace('global map_zone_capture_until\n','global map_zone_capture_until, candidate_zone, candidate_zone_reads\n',1)
 s=s.replace('''                map_zone_capture_until = time.time() + 4.0\n                log("M key detected: map-zone OCR window opened for 4 seconds.")\n''','''                candidate_zone=""; candidate_zone_reads=0\n                map_zone_capture_until=time.time()+4.0\n                log("M key detected: map-zone OCR window opened for 4 seconds; zone vote reset.")\n''',1)
 th='''def tick():\n    global candidate_loot_text,candidate_loot_reads,last_logged_loot_hash,last_log_time\n    global last_ocr_texts,last_ocr_items,last_scan_error\n    global loot_session_active, loot_session_last_seen, loot_session_logged\n    global hover_items_seen, hover_item_images\n    global last_combat_target,last_combat_target_cl,last_combat_target_seen_at\n'''
 s=s.replace(th,th+'''    global death_candidate_reads,kill_counted_for_active_target\n    global pending_kill_row,pending_kill_ts,pending_kill_mob,pending_kill_cl\n''',1)
 st=s.find('    # 1.1.33 authoritative mob rule:'); st=st if st>=0 else s.find('    # 1.1.32 authoritative mob rule:'); en=s.find('    # User-hover tooltip is the authoritative item name source.',st)
 if st<0 or en<0:raise SystemExit('target block missing')
 tb=r'''    card_mob,card_cl,card_raw=target_title_from_window(win); texts["combat_card_raw"]=card_raw; level_target=bool(card_cl); texts["level_target"]="YES" if level_target else "NO"
    if level_target:
        death_candidate_reads=0; chosen_mob=card_mob or fallback_mob
        if kill_counted_for_active_target:
            kill_counted_for_active_target=False; pending_kill_row=0; pending_kill_ts=""; pending_kill_mob=""; pending_kill_cl=""; log("NEW LIVE TARGET CYCLE: kill latch reset.")
        if chosen_mob:update_target("",chosen_mob,card_cl); log(f"LEVEL TARGET confirmed mob={chosen_mob!r} level={card_cl!r} blue={combat_metrics['blue_frac']:.3f} red={combat_metrics['red_frac']:.3f}")
    else:
        nowd=time.time(); recent=bool(last_combat_target) and nowd-float(last_combat_target_seen_at or 0)<=8.0; same=bool(recent and fallback_mob and title_similarity(fallback_mob,last_combat_target)>=0.66); evidence=recent and (same or corpse_target or (not fallback_mob and not combat_target))
        if evidence and not kill_counted_for_active_target:
            death_candidate_reads+=1; log(f"DEATH CANDIDATE {death_candidate_reads}/3 last={last_combat_target!r} fallback={fallback_mob!r}")
            if death_candidate_reads>=3:register_live_kill(last_combat_target,last_combat_target_cl); death_candidate_reads=3
        else:death_candidate_reads=0
        if corpse_target and fallback_mob:
            x=re.sub(r"^Corpse\s+of\s+","",fallback_mob,flags=re.I).strip()
            if x:last_combat_target=x; last_combat_target_cl=fallback_cl or last_combat_target_cl
        elif fallback_mob:log(f"NO-LEVEL TARGET ignored: {fallback_mob!r} red={combat_metrics['red_frac']:.3f} blue={combat_metrics['blue_frac']:.3f}")

'''
 s=s[:st]+tb+s[en:]
 ol='''    if append_rows(kill,drops):\n        loot_session_logged = True\n        last_log_time = now\n\n        live_overlay["zone"] = zone_value\n        live_overlay["kills"] = int(live_overlay.get("kills", 0)) + 1\n        live_overlay["last_drop"] = ", ".join(name for name,_ in items[:3])\n\n        log(\n            f"LIVE+XLSX OK hover-tooltip zone={zone_value!r} "\n            f"kills={live_overlay['kills']} mob={mob_value!r} "\n            f"CL={cl_value!r} items={items!r}"\n        )\n        notify(\n            "Loot logged",\n            f"{zone_value} | Kill {live_overlay['kills']} | "\n            f"{live_overlay['last_drop']}"\n        )\n'''
 nl='''    already_counted=kill_counted_for_active_target and bool(pending_kill_mob) and title_similarity(mob_value,pending_kill_mob)>=0.66\n    saved=append_drops_to_existing_kill(pending_kill_row,drops) if already_counted and pending_kill_row else append_rows(kill,drops)\n    if saved:\n        loot_session_logged=True; last_log_time=now; live_overlay["zone"]=zone_value; live_overlay["last_drop"]=", ".join(name for name,_ in items[:3])\n        if not already_counted:live_overlay["kills"]=int(live_overlay.get("kills",0))+1; kill_counted_for_active_target=True\n        log(f"LIVE+XLSX OK hover-tooltip zone={zone_value!r} kills={live_overlay['kills']} mob={mob_value!r} CL={cl_value!r} items={items!r} attached_to_live_kill={already_counted}")\n        notify("Loot logged",f"{zone_value} | Kill {live_overlay['kills']} | {live_overlay['last_drop']}")\n'''
 if ol not in s:raise SystemExit('loot block missing')
 s=s.replace(ol,nl,1); p.write_text(s)
 c=a/'config.json'; d=json.loads(c.read_text()); d.setdefault('behavior',{})['death_no_level_reads']=3; d['behavior']['zone_update_requires_m_key']=True; c.write_text(json.dumps(d,indent=2))
 q=a/'app_version.json';
 if q.exists():d=json.loads(q.read_text());d['version']=V;q.write_text(json.dumps(d,indent=2))
 q=a/'auto_updater.py';
 if q.exists():q.write_text(q.read_text().replace('CURRENT_VERSION = "1.1.32"',f'CURRENT_VERSION = "{V}"'))
 for x in a.rglob('*.py'):
  if '__pycache__' not in x.parts:py_compile.compile(str(x),doraise=True)
 nz=R/'release'/'EnB Droplist.zip.new'
 with zipfile.ZipFile(nz,'w',zipfile.ZIP_DEFLATED) as z:
  for x in w.rglob('*'):
   if x.is_file() and '__pycache__' not in x.parts:z.write(x,x.relative_to(w))
 with zipfile.ZipFile(nz) as z:
  if z.testzip():raise SystemExit('bad output zip')
 nz.replace(Z); sha=hashlib.sha256(Z.read_bytes()).hexdigest(); M.write_text(json.dumps({'name':'EnB Droplist','version':V,'download_url':'https://soulbound.se/EnB/Download/EnB%20Droplist.zip','sha256':sha,'release_date':'2026-08-23','release_notes':'Live kills count on Level-to-no-Level transition; F8 updates at death; XLSX records kill immediately and attaches hovered drops later. Zone changes only during M-key OCR window.'},indent=2)+'\n'); print(V,sha,Z.stat().st_size)
finally:shutil.rmtree(w,ignore_errors=True)
