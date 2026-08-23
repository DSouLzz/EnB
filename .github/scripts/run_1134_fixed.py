from pathlib import Path

p = Path('.github/scripts/build_1134.py')
src = p.read_text(encoding='utf-8')

# build_1134.py accidentally embedded a literal backslash-n before
# `def map_panel_is_open`, which makes the generated tray source invalid.
bad = "mh=r'''\\\\ndef map_panel_is_open(win):"
good = "mh=r'''\ndef map_panel_is_open(win):"
if bad in src:
    src = src.replace(bad, good, 1)
else:
    # Also support the one-backslash representation if GitHub normalized it.
    bad2 = "mh=r'''\\ndef map_panel_is_open(win):"
    if bad2 in src:
        src = src.replace(bad2, good, 1)

code = compile(src, str(p), 'exec')
exec(code, {'__name__': '__main__', '__file__': str(p)})
