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


def build_level(level_dir, template):
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
            .replace("{{BUILD_DATE}}", dt.date.today().isoformat()))
    (level_dir / "index.html").write_text(page, encoding="utf-8")
    (level_dir / "questions.json").write_text(json.dumps(questions, ensure_ascii=False, indent=1), encoding="utf-8")

    books = {(x["title"], x["author"]) for x in questions}
    print(f"  Embedded {len(questions)} questions covering {len(books)} books from {xlsx.name}.")
    if skipped:
        print(f"  Skipped {len(skipped)} incomplete row(s): {', '.join(map(str, skipped))}")
    return {"slug": level_dir.name, "name": name, "questions": len(questions), "books": len(books), "source": xlsx.name}


LANDING = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Battle of the Books Practice</title>
<style>
:root { --bg: #ffd60a; --card: #fffbe8; --fg: #0b0b0b; --muted: #4d4733; --line: #d9c45a; --accent: #0b0b0b; --accent-fg: #ffd60a; }
@media (prefers-color-scheme: dark) { :root { --bg: #0b0b0b; --card: #1b1a14; --fg: #fff6cc; --muted: #c2b88c; --line: #3d3920; --accent: #ffd60a; --accent-fg: #0b0b0b; color-scheme: dark; } }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: var(--bg); color: var(--fg); font: 17px/1.5 "Nunito", "Segoe UI", system-ui, sans-serif; padding: 40px max(16px, 4vw); }
main { max-width: 720px; margin: 0 auto; display: grid; gap: 24px; }
h1 { margin: 0; font-size: 2rem; line-height: 1.15; }
p { margin: 0; color: var(--muted); }
.levels { display: grid; gap: 14px; }
a.level { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; padding: 20px 22px; border-radius: 16px; background: var(--card); color: var(--fg); text-decoration: none; border: 2px solid var(--line); }
a.level:hover, a.level:focus-visible { border-color: var(--accent); }
a.level strong { font-size: 1.2rem; }
a.level span { color: var(--muted); font-size: 0.95rem; }
.play { padding: 10px 18px; border-radius: 10px; background: var(--accent); color: var(--accent-fg); font-weight: 800; }
.soon { opacity: 0.6; }
</style>
</head>
<body>
<main>
  <div>
    <h1>Battle of the Books Practice</h1>
    <p>Pick your school to start practicing.</p>
  </div>
  <div class="levels">
__LEVELS__
  </div>
  <p>Each game draws its questions at random from that school's current question spreadsheet.</p>
</main>
</body>
</html>
"""


def build_landing(built, pending):
    rows = []
    for lv in built:
        rows.append(
            f'    <a class="level" href="{lv["slug"]}/">'
            f'<div><strong>{html.escape(lv["name"])}</strong><br><span>{lv["questions"]:,} questions, {lv["books"]} books</span></div>'
            f'<span class="play">Play</span></a>'
        )
    for lv in pending:
        rows.append(
            f'    <div class="level soon"><div><strong>{html.escape(lv)}</strong><br><span>Coming soon: no question spreadsheet yet</span></div></div>'
        )
    (HERE / "index.html").write_text(LANDING.replace("__LEVELS__", "\n".join(rows)), encoding="utf-8")


def main():
    template = TEMPLATE.read_text(encoding="utf-8")
    only = set(sys.argv[1:])
    levels = sorted(p.parent for p in HERE.glob("*/config.json"))
    if only:
        levels = [lv for lv in levels if lv.name in only]
        if not levels:
            sys.exit(f"No level folder matches {', '.join(sorted(only))}")
    built, pending = [], []
    for level_dir in levels:
        result = build_level(level_dir, template)
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
