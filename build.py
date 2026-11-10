#!/usr/bin/env python3
"""Build every Battle of the Books practice game from its spreadsheet.

Folder layout (one folder per school level):

    battle-of-the-books/
      template.html            the game, with {{GAME_NAME}} and question markers
      build.py                 this script
      <level>/config.json      {"name": "Elementary School Battle of the Books"}
      <level>/data/*.xlsx      that level's question spreadsheet (drop it here)
      <level>/index.html       GENERATED playable game
      <level>/questions.json   GENERATED readable copy of the questions
      index.html               GENERATED landing page linking to each level

Spreadsheet layout: first sheet, header in row 1, then
    Column A: question    Column B: title answer    Column C: author answer
Rows missing any of the three values are skipped and reported.

Usage:
    python3 build.py            # build every level that has a spreadsheet
    python3 build.py elementary # build one level

If a level's data folder holds several .xlsx files, the most recently
committed one (by git history) is used, falling back to file modification time.
"""
import datetime as dt
import html
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:  # pragma: no cover
    sys.exit("openpyxl is required: pip install openpyxl")

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
LIVE_TEMPLATE = HERE / "live-template.html"
LIVE_CONFIG = HERE / "supabase-config.json"
START, END = "/*QUESTIONS_START*/", "/*QUESTIONS_END*/"


def clean(value):
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text).strip()


def load_questions(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    questions, skipped = [], []
    for row_num, row in enumerate(ws.iter_rows(values_only=True), start=1):
        cells = list(row) + [None] * 3
        q, title, author = (clean(c) for c in cells[:3])
        if row_num == 1 and q.lower() == "question":
            continue  # header row
        if not (q or title or author):
            continue  # blank row
        if not (q and title and author):
            skipped.append(row_num)
            continue
        suffix = f" by {author}".lower()  # tidy "Title by Author" typed into the title cell
        if title.lower().endswith(suffix):
            title = title[: -len(suffix)].strip()
        questions.append({"q": q, "title": title, "author": author})
    return questions, skipped


def commit_time(path):
    """Unix time of the last commit touching path, or None when not in git."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", str(path)],
            cwd=HERE, capture_output=True, text=True, check=True,
        ).stdout.strip()
        return int(out) if out else None
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None


def pick_spreadsheet(level_dir):
    files = [p for p in (level_dir / "data").glob("*.xls[xm]") if not p.name.startswith("~$")]
    if not files:
        return None
    if len(files) == 1:
        return files[0]
    files.sort(key=lambda p: (commit_time(p) or 0, p.stat().st_mtime), reverse=True)
    print(f"  Several spreadsheets found; using the most recent: {files[0].name}")
    return files[0]


def live_config():
    """Public Supabase connection details (project URL + anon/publishable key) for the live classroom game."""
    try:
        cfg = json.loads(LIVE_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    out = {"url": str(cfg.get("url", "")).strip().rstrip("/"), "anonKey": str(cfg.get("anonKey", "")).strip()}
    return out


def build_level(level_dir, template, live_template=None):
    config = json.loads((level_dir / "config.json").read_text(encoding="utf-8"))
    name = config.get("name") or level_dir.name.replace("-", " ").title()
    xlsx = pick_spreadsheet(level_dir)
    print(f"{name} ({level_dir.name}/)")
    if xlsx is None:
        print("  No spreadsheet in data/ yet; skipped.")
        return None

    questions, skipped = load_questions(xlsx)
    payload = json.dumps(questions, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    start = template.index(START) + len(START)
    end = template.index(END)
    page = template[:start] + payload + template[end:]
    page = (page
            .replace("{{GAME_NAME}}", html.escape(name))
            .replace("{{SLUG}}", level_dir.name)
            .replace("{{SOURCE_FILE}}", html.escape(xlsx.name))
            .replace("{{BUILD_DATE}}", dt.date.today().isoformat())
            .replace("{{SIDE_BOOKS_CSS}}", side_books_css())
            .replace("{{SIDE_BOOKS_HTML}}", SIDE_BOOKS_HTML)
            .replace("{{JINGLE_JS}}", JINGLE_JS))
    (level_dir / "index.html").write_text(page, encoding="utf-8")
    if live_template is not None:
        base_css = re.search(r"<style>(.*?)\{\{SIDE_BOOKS_CSS\}\}</style>", template, re.S).group(1)
        live = (live_template.replace("{{BASE_CSS}}", base_css)
                .replace("{{LIVE_CONFIG}}", json.dumps(live_config()).replace("</", "<\\/")))
        live = live[:live.index(START) + len(START)] + payload + live[live.index(END):]
        live = (live
                .replace("{{GAME_NAME}}", html.escape(name))
                .replace("{{SLUG}}", level_dir.name)
                .replace("{{SOURCE_FILE}}", html.escape(xlsx.name))
                .replace("{{BUILD_DATE}}", dt.date.today().isoformat())
                .replace("{{SIDE_BOOKS_CSS}}", side_books_css())
                .replace("{{SIDE_BOOKS_HTML}}", SIDE_BOOKS_HTML))
        (level_dir / "live.html").write_text(live, encoding="utf-8")
    (level_dir / "questions.json").write_text(json.dumps(questions, ensure_ascii=False, indent=1), encoding="utf-8")

    books = {(x["title"], x["author"]) for x in questions}
    print(f"  Embedded {len(questions)} questions covering {len(books)} books from {xlsx.name}.")
    if skipped:
        print(f"  Skipped {len(skipped)} incomplete row(s): {', '.join(map(str, skipped))}")
    return {"slug": level_dir.name, "name": name, "questions": len(questions), "books": len(books), "source": xlsx.name}



# ---------- Decorative columns of stacked books down both page margins ----------
# One tile (180 x 440) that repeats vertically; book heights and gaps sum to the tile
# height so the seam between tiles is invisible.
def _side_books_tile():
    books = [  # (x, width, fill, label colour, tilt)
        (18, 150, "#ffd60a", "#0b0b0b", 0), (30, 128, "#0b0b0b", "#ffd60a", 0), (12, 160, "#fff6cc", "#0b0b0b", -2),
        (26, 136, "#ffd60a", "#0b0b0b", 0), (38, 118, "#0b0b0b", "#ffd60a", 0), (16, 150, "#ffd60a", "#0b0b0b", 2),
        (24, 140, "#fff6cc", "#0b0b0b", 0), (34, 124, "#0b0b0b", "#ffd60a", 0), (14, 156, "#ffd60a", "#0b0b0b", 0),
        (28, 132, "#0b0b0b", "#ffd60a", -2), (20, 146, "#fff6cc", "#0b0b0b", 0),
    ]
    h, gap = 34, 6  # 11 books x 40 = 440
    parts = []
    for i, (x, w, fill, label, tilt) in enumerate(books):
        y = i * (h + gap) + gap / 2
        cx, cy = x + w / 2, y + h / 2
        tr = f' transform="rotate({tilt} {cx} {cy})"' if tilt else ""
        parts.append(
            f'<g{tr}><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{fill}" stroke="#fff6cc" stroke-width="4"/>'
            f'<line x1="{x + 16}" y1="{cy}" x2="{x + w * 0.55:.0f}" y2="{cy}" stroke="{label}" stroke-width="5" stroke-linecap="round"/></g>'
        )
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 440" width="180" height="440">' + "".join(parts) + "</svg>"


def side_books_css():
    from urllib.parse import quote
    uri = "data:image/svg+xml," + quote(_side_books_tile(), safe="/:=, ")
    return (
        "/* Stacks of books down both margins; shown only when the window is wide enough to leave margins free */\n"
        ".side-books { display: none; position: fixed; top: 0; bottom: 0; width: 180px; z-index: 0; pointer-events: none;\n"
        f"  background: url(\"{uri}\") center top / 180px 440px repeat-y; opacity: 0.9; }}\n"
        ".side-books.left { left: max(8px, env(safe-area-inset-left, 0px)); }\n"
        ".side-books.right { right: max(8px, env(safe-area-inset-right, 0px)); transform: scaleX(-1); }\n"
        "@media (min-width: 1180px) { .side-books { display: block; } }\n"
    )


SIDE_BOOKS_HTML = '<div class="side-books left" aria-hidden="true"></div>\n<div class="side-books right" aria-hidden="true"></div>'

JINGLE_JS = r'''<script>
// ---------- BobSound: a looping quiz-show jingle made with the Web Audio API (no files to download) ----------
window.BobSound = (function () {
  const AC = window.AudioContext || window.webkitAudioContext;
  const BPM = 138, STEP = 60 / BPM / 2, STEPS = 32;            // eighth notes, 4 bars
  // C major, I - vi - IV - V. Melody and bass as MIDI numbers, 0 = rest.
  const MELODY = [72,76,79,76, 72,76,79,81,  79,0,76,0, 74,76,74,72,  69,72,77,72, 69,72,77,79,  79,0,83,0, 81,79,77,74];
  const BASS   = [48,0,55,0, 48,0,55,0,  45,0,52,0, 45,0,52,0,  41,0,48,0, 41,0,48,0,  43,0,50,0, 43,0,50,0];
  const CHORDS = [[60,64,67],[57,60,64],[57,60,65],[59,62,67]];
  let ctx = null, master = null, timer = null, step = 0, nextTime = 0, playing = false, wanted = false, enabled = true;
  const hz = m => 440 * Math.pow(2, (m - 69) / 12);
  function context() {
    if (!AC) return null;
    if (!ctx) { ctx = new AC(); master = ctx.createGain(); master.gain.value = 0.35; master.connect(ctx.destination); }
    return ctx;
  }
  function tone(midi, t, dur, type, gain) {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type; o.frequency.value = hz(midi);
    g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(gain, t + 0.012); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(master); o.start(t); o.stop(t + dur + 0.03);
  }
  function noise(t, dur, gain, highpass) {
    const len = Math.max(1, Math.floor(ctx.sampleRate * dur)), buf = ctx.createBuffer(1, len, ctx.sampleRate), d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / len);
    const src = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
    src.buffer = buf; f.type = 'highpass'; f.frequency.value = highpass; g.gain.value = gain;
    src.connect(f).connect(g).connect(master); src.start(t);
  }
  function schedule(i, t) {
    const bar = Math.floor(i / 8), beat = i % 8;
    if (MELODY[i]) tone(MELODY[i], t, STEP * 0.9, 'square', 0.11);
    if (BASS[i]) tone(BASS[i], t, STEP * 1.6, 'triangle', 0.4);
    if (beat % 2 === 1) for (const n of CHORDS[bar]) tone(n, t, STEP * 0.45, 'sawtooth', 0.035);
    noise(t, 0.03, beat % 2 ? 0.07 : 0.14, 6000);                 // hi-hat
    if (beat === 2 || beat === 6) noise(t, 0.12, 0.22, 1500);      // snare on 2 and 4
  }
  function pump() { while (nextTime < ctx.currentTime + 0.25) { schedule(step % STEPS, nextTime); step++; nextTime += STEP; } }
  function halt() {
    clearInterval(timer); timer = null; playing = false;
    if (ctx) { master.gain.cancelScheduledValues(ctx.currentTime); master.gain.setTargetAtTime(0.0001, ctx.currentTime, 0.04); }
  }
  function start() {
    wanted = true;
    if (!enabled || playing) return;
    const c = context(); if (!c) return;
    if (c.state !== 'running') { c.resume().then(() => { if (wanted && !playing && c.state === 'running') start(); }).catch(() => {}); return; }
    master.gain.cancelScheduledValues(c.currentTime); master.gain.setValueAtTime(0.35, c.currentTime);
    playing = true; step = 0; nextTime = c.currentTime + 0.05;
    timer = setInterval(pump, 60);
  }
  function stop() { wanted = false; halt(); }
  function setEnabled(on) { enabled = !!on; if (!enabled) halt(); else if (wanted) start(); }
  // Browsers only allow sound after the visitor clicks or presses a key, so retry then.
  for (const ev of ['pointerdown', 'keydown']) document.addEventListener(ev, () => { if (wanted && !playing) start(); }, { passive: true });
  return { context, start, stop, setEnabled, isEnabled: () => enabled, isPlaying: () => playing, master: () => master };
})();
</script>'''

LANDING = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Battle of the Books Practice</title>
<style>
:root { color-scheme: dark; --bg: #0b0b0b; --card: #1b1a14; --fg: #fff6cc; --muted: #c2b88c; --line: #3d3920; --accent: #ffd60a; --accent-fg: #0b0b0b; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: var(--bg); color: var(--fg); font: 17px/1.5 "Nunito", "Segoe UI", system-ui, sans-serif; padding: 40px max(16px, 4vw); }
main { max-width: 720px; margin: 0 auto; display: grid; gap: 24px; }
h1 { margin: 0; font-size: 2rem; line-height: 1.15; }
p { margin: 0; color: var(--muted); }
.disclaimer { font-size: 0.85rem; font-style: italic; }
.levels { display: grid; gap: 14px; }
a.level { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; padding: 20px 22px; border-radius: 16px; background: var(--card); color: var(--fg); text-decoration: none; border: 2px solid var(--line); }
a.level:hover, a.level:focus-visible { border-color: var(--accent); }
a.level strong { font-size: 1.2rem; }
a.level span { color: var(--muted); font-size: 0.95rem; }
a.level .play { padding: 10px 18px; border-radius: 10px; background: var(--accent); color: var(--accent-fg); font-weight: 800; }
.soon { opacity: 0.6; }
.heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.sound { font: inherit; font-weight: 800; font-size: 0.9rem; padding: 8px 14px; border-radius: 999px; border: 1px solid var(--line); background: var(--card); color: var(--fg); cursor: pointer; }
.sound[aria-pressed="false"] { opacity: 0.7; }
main { position: relative; z-index: 1; }
__SIDE_BOOKS_CSS__
/* Mascot on a stack of books, under the closing line */
.hero { position: relative; width: min(520px, 100%); aspect-ratio: 1; margin: 0 auto; }
.hero .books { position: absolute; left: 19%; bottom: 6.5%; width: 61.5%; }
.hero .books svg { display: block; width: 100%; height: auto; }
.hero .mascot { position: absolute; width: 63.5%; left: 23%; top: 2.7%; filter: drop-shadow(0 0 2px #fff6cc) drop-shadow(0 0 1px #fff6cc); }
</style>
</head>
<body>
__SIDE_BOOKS_HTML__
<main>
  <div class="heading">
    <div>
      <h1>Battle of the Books Practice</h1>
      <p>Pick your school to start practicing.</p>
    </div>
    <button class="sound" id="sound-btn" type="button" aria-pressed="true">Sound: On</button>
  </div>
  <div class="levels">
__LEVELS__
  </div>
  <p>Each game draws its questions at random from that school's current question spreadsheet.</p>
  <p class="disclaimer">This program was coded from an idea using Claude Code. The code has not been reviewed by a professional programmer and is intended only to be used for classroom instructional purposes and practicing Battle of the Books question sets.</p>
  <div class="hero" aria-hidden="true">
    <div class="books">
      <svg viewBox="0 0 320 190">
        <g stroke="#fff6cc" stroke-width="5" stroke-linejoin="round">
          <rect x="12" y="150" width="296" height="34" rx="6" fill="#ffd60a"/>
          <rect x="30" y="114" width="262" height="34" rx="6" fill="#0b0b0b"/>
          <g transform="rotate(-4 160 95)"><rect x="26" y="78" width="268" height="34" rx="6" fill="#fff6cc"/></g>
          <rect x="48" y="42" width="228" height="34" rx="6" fill="#ffd60a"/>
          <rect x="70" y="8" width="190" height="32" rx="6" fill="#0b0b0b"/>
        </g>
        <g stroke-linecap="round" stroke-width="6">
          <line x1="40" y1="167" x2="150" y2="167" stroke="#0b0b0b"/>
          <line x1="58" y1="131" x2="150" y2="131" stroke="#ffd60a"/>
          <g transform="rotate(-4 160 95)"><line x1="54" y1="95" x2="140" y2="95" stroke="#0b0b0b"/></g>
          <line x1="76" y1="59" x2="150" y2="59" stroke="#0b0b0b"/>
          <line x1="98" y1="24" x2="160" y2="24" stroke="#ffd60a"/>
        </g>
      </svg>
    </div>
    <img class="mascot" src="assets/mascot.png" alt="">
  </div>
</main>
__JINGLE_JS__
<script>
  // The jingle plays until a level is chosen (leaving the page stops it). Sound starts at the first click or key press.
  BobSound.start();
  const soundBtn = document.getElementById('sound-btn');
  soundBtn.addEventListener('click', () => {
    const on = soundBtn.getAttribute('aria-pressed') !== 'true';
    soundBtn.setAttribute('aria-pressed', String(on));
    soundBtn.textContent = on ? 'Sound: On' : 'Sound: Off';
    BobSound.setEnabled(on);
  });
</script>
</body>
</html>
"""


def build_landing(built, pending):
    rows = []
    for lv in built:
        rows.append(
            f'    <a class="level" href="{lv["slug"]}/index.html">'
            f'<div><strong>{html.escape(lv["name"])}</strong><br><span>{lv["questions"]:,} questions, {lv["books"]} books</span></div>'
            f'<span class="play">Play</span></a>'
        )
    for lv in pending:
        rows.append(
            f'    <div class="level soon"><div><strong>{html.escape(lv)}</strong><br><span>Coming soon: no question spreadsheet yet</span></div></div>'
        )
    page = (LANDING.replace("__LEVELS__", "\n".join(rows))
            .replace("__SIDE_BOOKS_CSS__", side_books_css())
            .replace("__SIDE_BOOKS_HTML__", SIDE_BOOKS_HTML)
            .replace("__JINGLE_JS__", JINGLE_JS))
    (HERE / "index.html").write_text(page, encoding="utf-8")


def main():
    template = TEMPLATE.read_text(encoding="utf-8")
    live_template = LIVE_TEMPLATE.read_text(encoding="utf-8")
    only = set(sys.argv[1:])
    levels = sorted(p.parent for p in HERE.glob("*/config.json"))
    if only:
        levels = [lv for lv in levels if lv.name in only]
        if not levels:
            sys.exit(f"No level folder matches {', '.join(sorted(only))}")
    built, pending = [], []
    for level_dir in levels:
        result = build_level(level_dir, template, live_template)
        if result:
            built.append(result)
        else:
            cfg = json.loads((level_dir / "config.json").read_text(encoding="utf-8"))
            pending.append(cfg.get("name") or level_dir.name)
    if not only:
        build_landing(built, pending)
        print("Landing page written to index.html.")


if __name__ == "__main__":
    main()
