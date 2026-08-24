from pathlib import Path
import zipfile, tempfile, shutil, json, hashlib, py_compile, re

ROOT = Path.cwd()
ZIP = ROOT / "release" / "EnB Droplist.zip"
MANIFEST = ROOT / "release" / "version.json"
VERSION = "1.1.37"

def valid_current():
    try:
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if m.get("version") != VERSION or ZIP.stat().st_size < 40000:
            return False
        with zipfile.ZipFile(ZIP) as z:
            if z.testzip():
                return False
            names = z.namelist()
            tray_name = next(n for n in names if n.endswith("enb_drop_logger_tray.py"))
            source = z.read(tray_name).decode("utf-8")
            return "ZONE SOURCE:" in source and "looks_like_navigation_object_name" in source
    except Exception:
        return False

def replace_once(s, old, new, label):
    if old not in s:
        raise SystemExit(f"{label} anchor missing")
    return s.replace(old, new, 1)

def main():
    if valid_current():
        print("1.1.37 already valid")
        return

    tmp = Path(tempfile.mkdtemp(prefix="enb137_"))
    try:
        with zipfile.ZipFile(ZIP) as z:
            if z.testzip():
                raise SystemExit("base ZIP corrupt")
            src = tmp / "src"
            src.mkdir()
            z.extractall(src)

        tray = next(src.rglob("enb_drop_logger_tray.py"))
        app = tray.parent
        s = tray.read_text(encoding="utf-8").replace("1.1.36", VERSION)

        if "def looks_like_navigation_object_name" not in s:
            helper = '''def looks_like_navigation_object_name(name):
    """Reject gates/navpoints accidentally read as target names."""
    x = norm(name)
    if not x:
        return False
    words = re.findall(r"[A-Za-z0-9']+", x)
    if len(words) >= 2:
        if title_similarity(words[0], "Sector") >= 0.62 and title_similarity(words[1], "Gate") >= 0.52:
            return True
    if re.search(r"\\b(?:Nav|Navigation)\\b", x, re.I):
        return True
    return False


'''
            marker = "def target_title_from_window(win):"
            if marker not in s:
                raise SystemExit("target_title_from_window anchor missing")
            s = s.replace(marker, helper + marker, 1)

        old = '''        if re.search(
            r"\\b(?:Dist|Distance|Hull|Shield|Structure|Quality|Chat|Group|"
            r"Options|Help|Emote|Credits?|Dest|Sector Gate)\\b",
            x, re.I
        ):
            return ""
        return x
'''
        new = '''        if re.search(
            r"\\b(?:Dist|Distance|Hull|Shield|Structure|Quality|Chat|Group|"
            r"Options|Help|Emote|Credits?|Dest)\\b",
            x, re.I
        ):
            return ""
        if looks_like_navigation_object_name(x):
            return ""
        return x
'''
        if old in s:
            s = s.replace(old, new, 1)
        elif "if looks_like_navigation_object_name(x):" not in s:
            raise SystemExit("target clean_name anchor missing")

        old = '''        if 3 <= len(name) <= 80:
            return name, "", "DEST:\\n" + combined
'''
        new = '''        if 3 <= len(name) <= 80 and not looks_like_navigation_object_name(name):
            return name, "", "DEST:\\n" + combined
'''
        if old in s:
            s = s.replace(old, new, 1)
        elif "not looks_like_navigation_object_name(name)" not in s:
            raise SystemExit("Dest fallback anchor missing")

        old = '''        if candidate and 3 <= len(candidate) <= 80:
            return candidate, cl, "DEST:\\n" + combined + "\\nRETICLE:\\n" + raw_reticle
'''
        new = '''        if candidate and 3 <= len(candidate) <= 80 and not looks_like_navigation_object_name(candidate):
            return candidate, cl, "DEST:\\n" + combined + "\\nRETICLE:\\n" + raw_reticle
'''
        if old in s:
            s = s.replace(old, new, 1)
        elif "not looks_like_navigation_object_name(candidate)" not in s:
            raise SystemExit("reticle fallback anchor missing")

        if 'f"ZONE SOURCE: {zone_source}\\n"' not in s:
            old = '''        if current_zone:
            zone = current_zone
        elif fallback_zone and plausible_zone_title(fallback_zone):
            zone = fallback_zone
        elif raw_zone and plausible_zone_title(raw_zone):
            zone = raw_zone
        else:
            zone = ""

        hover_item, hover_raw = read_hover_item(win)
'''
            new = '''        if current_zone:
            zone = current_zone
        elif fallback_zone and plausible_zone_title(fallback_zone):
            zone = fallback_zone
        elif raw_zone and plausible_zone_title(raw_zone):
            zone = raw_zone
        else:
            zone = ""

        zone_source = "none"
        if zone:
            if fallback_zone and plausible_zone_title(fallback_zone) and title_similarity(zone, fallback_zone) >= 0.78:
                zone_source = "map title strip"
            elif probe_zone and probe_support >= 3 and plausible_zone_title(probe_zone) and title_similarity(zone, probe_zone) >= 0.78:
                zone_source = f"map title probe ({probe_support} reads)"
            elif raw_zone and plausible_zone_title(raw_zone) and title_similarity(zone, raw_zone) >= 0.78:
                zone_source = "calibrated zone area"
            elif current_zone:
                zone_source = "previous confirmed zone"

        hover_item, hover_raw = read_hover_item(win)
'''
            s = replace_once(s, old, new, "zone source")

            old = '''            f"MAP TITLE PROBE: {probe_zone or '<none>'} (support {probe_support})\\n"
            f"CONFIRMED ZONE: {zone or '<none>'}\\n\\n"
'''
            new = '''            f"MAP TITLE PROBE: {probe_zone or '<none>'} (support {probe_support})\\n"
            f"ZONE SOURCE: {zone_source}\\n"
            f"CONFIRMED ZONE: {zone or '<none>'}\\n\\n"
'''
            s = replace_once(s, old, new, "status zone source")

        tray.write_text(s, encoding="utf-8")

        cfg = app / "config.json"
        d = json.loads(cfg.read_text(encoding="utf-8"))
        d.setdefault("behavior", {})["reject_navigation_target_names"] = True
        cfg.write_text(json.dumps(d, indent=2), encoding="utf-8")

        av = app / "app_version.json"
        if av.exists():
            d = json.loads(av.read_text(encoding="utf-8"))
            d["version"] = VERSION
            av.write_text(json.dumps(d, indent=2), encoding="utf-8")

        au = app / "auto_updater.py"
        if au.exists():
            t = au.read_text(encoding="utf-8")
            t = t.replace('CURRENT_VERSION = "1.1.36"', f'CURRENT_VERSION = "{VERSION}"')
            au.write_text(t, encoding="utf-8")

        for p in app.rglob("*.py"):
            if "__pycache__" not in p.parts:
                py_compile.compile(str(p), doraise=True)

        newzip = tmp / "EnB Droplist.zip"
        with zipfile.ZipFile(newzip, "w", zipfile.ZIP_DEFLATED) as z:
            for p in src.rglob("*"):
                if p.is_file() and "__pycache__" not in p.parts:
                    z.write(p, p.relative_to(src))

        with zipfile.ZipFile(newzip) as z:
            if z.testzip():
                raise SystemExit("output ZIP corrupt")

        if newzip.stat().st_size < 40000:
            raise SystemExit(f"output ZIP unexpectedly small: {newzip.stat().st_size}")

        shutil.copy2(newzip, ZIP)
        sha = hashlib.sha256(ZIP.read_bytes()).hexdigest()
        MANIFEST.write_text(json.dumps({
            "name": "EnB Droplist",
            "version": VERSION,
            "download_url": "https://soulbound.se/EnB/Download/EnB%20Droplist.zip",
            "sha256": sha,
            "release_date": "2026-08-24",
            "release_notes": "Target OCR rejects fuzzy Sector Gate/navigation-object names. OCR Status/Test shows ZONE SOURCE while preserving the working confirmed-zone logic."
        }, indent=2) + "\n", encoding="utf-8")
        print("built", VERSION, ZIP.stat().st_size, sha)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
