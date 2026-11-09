# Battle of the Books practice games

Quiz games for practicing Battle of the Books questions, one per school level.
Each game is a single HTML file that runs in any browser.

| Level | Folder | Status |
| --- | --- | --- |
| Elementary School Battle of the Books | `elementary/` | Built from `elementary/data/NEW_BOB_GEM.xlsx` |
| Middle School Battle of the Books | `middle-school/` | Waiting for a spreadsheet |
| High School Battle of the Books | `high-school/` | Waiting for a spreadsheet |

`index.html` at the repository root is a landing page that links to every built game.

## Updating a question set (drag and drop)

1. On GitHub, open the level's `data/` folder, for example `elementary/data/`.
2. Use **Add file > Upload files** and drop in the new spreadsheet. Delete the old
   spreadsheet in the same step if you like; if two are present the most recently
   committed one wins.
3. Commit. The **Build Battle of the Books games** workflow in GitHub Actions runs,
   rebuilds that level's `index.html` and `questions.json`, and commits them. This
   takes about a minute. The Actions tab shows the run and reports any skipped rows.

The spreadsheet's first sheet needs a header in row 1 and then, per row:
column A the question, column B the title answer, column C the author answer.

## Starting the middle school or high school game

Drop that level's spreadsheet into `middle-school/data/` or `high-school/data/`.
The workflow builds the game and the landing page starts linking to it. To change
a game's displayed name, edit the `name` in that level's `config.json`. To add a
fourth level, create a new folder with a `config.json` and a `data/` folder.

## How the game works

- **Modes**
  - **Solo**: one player answers the title and the author for each question.
  - **Team**: two to four named teams alternate questions; a scoreboard tracks points.
  - **Flash cards**: one card per book with the title on the front and the author on
    the back. Click to flip, step through the shuffled deck, no points. Students can
    also put the author on the front to practice the other direction.
- **Round length** (solo and team): 5, 10, 20, 25 or 50 questions, chosen before each round.
- **Answer style** (solo and team): multiple choice (four titles, four authors) or
  type it in. Typed titles accept small spelling slips and ignore subtitles;
  typed authors accept the full name or the last name.
- **Scoring**: 2 points per question, 1 for the correct title and 1 for the author.
- **Feedback bursts**: after every answer a comic-book starburst pops up and shakes
  with a message drawn at random for the outcome: both right, one of two right, or
  wrong / out of time. The three messages per outcome are listed near the top of the
  script in `template.html` and are easy to change.
- **30-second clock** (solo and team): a countdown ring shows the seconds left for each
  question, turning red for the last ten. When it hits zero the question is scored
  zero, the answers are shown, and play moves on.
- **Sound**: a looping quiz-show jingle plays on the landing page and on each game's
  setup screen until a round starts, and a tick-tock plays while a question's clock
  runs. All audio is generated in the browser, so there are no sound files. Browsers
  start sound only after the first click or key press. A Sound on/off button sits in
  the header of every page.
- **Read-aloud**: switch it on before starting and hovering over the question, a
  title or author option, or a flash card reads it aloud using the browser's built-in
  speech. Keyboard focus reads too. It is off each time the page is opened.
- **Randomness**: every round reloads the full question set and shuffles it with the
  browser's cryptographic random source. Past orderings are remembered in the
  browser so the same sequence is never served twice on that device.
- **Results**: total score, title vs. author accuracy, team standings, and a review
  list of every question that was not fully correct.

Keyboard: Enter checks or advances; in flash-card mode Space flips the card and
the arrow keys move between cards.

## Building by hand

```bash
python3 build.py              # all levels
python3 build.py elementary   # one level
```

Requires Python 3 with `openpyxl` (`pip install openpyxl`). The game itself lives
in `template.html`; each level's `index.html` is generated from it, so edit the
template, not the generated files.

## Hosting with GitHub Pages

In the repository settings choose **Pages**, set the source to **Deploy from a
branch**, pick `main` and the root folder, and save. A few minutes later the
landing page is live at `https://<account>.github.io/Battle-of-the-Books/` and
each game at `.../Battle-of-the-Books/elementary/` and so on. Pages republishes
automatically after every rebuild.
