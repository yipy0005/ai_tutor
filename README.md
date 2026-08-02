# Learning Quest

A small Flask web app for a child in the English school system who is between
Year 2 and Year 3. It does two things at once: keeps Year 1 and Year 2 fresh
through spaced repetition, and introduces the Year 3 curriculum early so
September feels familiar rather than new.

It runs on one computer in your house. There is no account, no cloud, no
tracking and no network access — your child's progress lives in a single SQLite
file in `instance/`.

---

## Getting started

Everything runs through [pixi](https://pixi.sh). You do not need to install
Python, Flask or anything else yourself.

```bash
pixi run setup     # create the database (once)
pixi run serve     # start the app
```

Then open **http://127.0.0.1:5001**. The first screen asks for your child's
name and a parent PIN, and you are away.

`pixi run serve` also prints a second address on your home wi-fi, so a tablet
in the kitchen can use the same app.

> **Port 5001, not 5000.** On macOS the AirPlay Receiver service occupies port
> 5000 and answers with a bare `403`, which is a miserable thing to debug.

### Want to see the parent dashboard with data in it first?

```bash
pixi run seed -- --demo
```

That adds a profile called **Demo** with six weeks of invented practice
history, so the charts, mastery grid and insights all have something to show.
Delete it whenever you like from **Parent → Learners**.

---

## What a child sees

The child's side is built around one assumption: **attention is the scarce
resource, not time.**

* **Quests, not lessons.** A quest is 6 to 8 questions, about three to five
  minutes. Progress dots at the top mean the finish line is visible from the
  first question, which is what makes a short session feel finishable rather
  than open-ended.
* **One thing on screen.** No competing buttons, no side panels. Tap targets are
  at least 56px, the primary action is at least 74px.
* **Pictures, not just words.** Clock faces, place-value blocks, coins, fraction
  bars, bar charts, tally marks, arrays, number lines, angles and shapes are all
  drawn as inline SVG. A seven-year-old reasons far better about a clock face
  than about the phrase "twenty-five to four".
* **Wrong answers are soft.** A gentle low tone rather than a buzzer, one second
  chance, then the answer with an explanation. Nothing is lost by being wrong,
  and effort still earns a little XP.
* **Correct answers keep the pace up.** They advance themselves after a beat.
  Wrong answers wait, so there is time to read why.
* **Read-aloud.** Any question can be read out using the device's own voice.
  Genuinely useful for maths word problems while reading is still developing.
* **A wiggle break** is offered after a while. Offered, never enforced.
* **Rewards are cosmetic.** XP, coins, a day streak, 24 badges, and a shop of
  emoji hats, pets and backgrounds. None of it gates any learning content.

Interruptions are safe: reload or close the tab mid-quest and everything
answered so far is kept, with the progress dots intact when you come back.

---

## What a parent sees

Behind a PIN at **/parent**, in a deliberately calmer and denser design.

**Overview** — minutes today and this week, accuracy, streak, curriculum
coverage and mastery, a per-subject breakdown, a 14-day minutes chart, an
accuracy trend line, a 10-week practice heatmap, and plain-English notes that
say what the numbers imply and what to change.

**Progress** — every skill in the curriculum, grouped exactly as the National
Curriculum groups it, with mastery, accuracy, attempts, when it was last seen
and when spaced repetition will bring it back. Each skill shows the actual
curriculum objective it maps to, so you can line it up against what school says.

**Activity** — day-by-day history, the full quest list, and recent mistakes with
the correct answer and explanation. The fastest way to help is to read two or
three of these together.

**Quest review** — every question exactly as it was asked, what your child
answered, whether a clue was used, how long each one took.

**Learners** — add siblings, rename, reset progress, delete a profile.

**Curriculum** — the full map of all 145 skills and where the questions come
from.

### Settings a parent controls

Suggested defaults are in brackets.

| | |
|---|---|
| Questions per quest | 4–15 *(8)* |
| Daily time limit | 0–240 min, real time on task *(30)* |
| Wiggle break after | 0–40 min *(12)* |
| Daily and weekly quest goals | *(3 per day, 18 per week)* |
| Hours the app is available | *(off — any time)* |
| Subjects | Maths, English, Science *(all on)* |
| Year groups | Year 1, 2, 3 *(all on)* |
| Revision vs getting ahead | Weights per year *(15 / 35 / 50)* |
| Difficulty | Gentle · Adaptive · Challenge *(Adaptive)* |
| Focus skills | Reserved a slot in every quest |
| Clues | On/off *(on)* |
| One second chance | On/off *(on)* |
| Explain the answer | On/off *(on)* |
| Sound effects | On/off *(on)* |
| Animations | On/off *(on)* |
| Read-aloud button | On/off *(on)* |
| Read every question aloud | On/off *(off)* |
| Dyslexia-friendly font | On/off *(off)* |
| Larger text | On/off *(off)* |
| High contrast | On/off *(off)* |
| Show the timer | On/off *(**off** — visible timers make children rush)* |
| Coin shop | On/off *(on)* |
| A note on the home screen | Free text |
| An agreed reward | Free text |
| Parent PIN | 4–8 digits *(1234)* |

Two worth explaining:

* **Revision vs getting ahead** are relative weights, not percentages. For the
  summer before Year 3, roughly `15 / 35 / 50` works well: enough Year 1 and 2
  to stop it fading, with most of the effort on new material.
* **Focus skills** are reserved a place in every quest for that subject, up to a
  quarter of the questions. Tick one when school flags something. Weak skills
  are suggested for you.

---

## How practice is chosen

Three things combine to pick each question:

1. **Spaced repetition.** Every skill sits in a Leitner box with a due date
   (today → 1 → 3 → 7 → 16 → 35 days). Getting it right moves it up a box;
   getting it wrong drops it two. Overdue skills climb to the front fast. This
   is what turns a summer of five-minute sessions into knowledge that is still
   there in September.
2. **Mastery targeting.** Mastery is a moving average weighted towards recent
   answers — five correct in a row reaches "mastered", and one slip knocks it
   back meaningfully. Weak skills come round more often; a skill answered
   correctly four times running is allowed to rest.
3. **Your intent.** The year-mix weights and any focus skills act on top.

Difficulty is per skill, not global: in Adaptive mode a skill your child finds
hard produces easier numbers than one they have nailed.

---

## What it covers

145 skills across Years 1, 2 and 3, mapped to the English National Curriculum
(Key Stage 1 and lower Key Stage 2).

| Subject | Year 1 | Year 2 | Year 3 | Total | Questions |
|---|---|---|---|---|---|
| **Maths** | 16 | 20 | 33 | 69 | Generated — never repeats |
| **English** | 10 | 16 | 18 | 44 | 420 written questions |
| **Science** | 8 | 8 | 16 | 32 | 259 written questions |

**Maths** skills are *procedural*: a Python function invents a fresh question
every time, so practice genuinely never runs out. Place value, the four
operations, all the times tables through Year 3, fractions, money, time, Roman
numerals, measurement and conversion, perimeter, angles, lines, shape
properties, and statistics.

**English** covers phonics and spelling patterns, the Year 1–3 statutory word
lists, punctuation up to inverted commas and plural possessive apostrophes,
grammar from joining words to the present perfect, and reading comprehension
over six original passages.

**Science** covers plants, animals and humans, materials, seasons, habitats and
food chains, nutrition, skeletons and muscles, rocks and fossils and soil, light
and shadows, and forces and magnets.

### Adding your own questions

English and Science questions are plain JSON in
`tutor/content/banks/`, keyed by skill id:

```json
{
  "e3.spell.prefixes": [
    {
      "kind": "choice",
      "prompt": "Which prefix means 'again'?",
      "choices": ["re", "dis", "mis", "pre"],
      "answer": "re",
      "hint": "It means to do it another time.",
      "explain": "re + build = rebuild."
    }
  ]
}
```

Use `"kind": "text"` for a typed answer, plus an optional
`"accept": ["alternative spellings"]`. Then check your work:

```bash
pixi run content-check
```

That validates every question in every bank and 40 samples from every maths
generator: prompts present, no duplicate options, the answer among the choices,
and each question's own answer passing the marker.

---

## Commands

| Command | What it does |
|---|---|
| `pixi run setup` | Create the database. Run once. |
| `pixi run serve` | Start the app for everyday use. |
| `pixi run dev` | Development server with auto-reload. |
| `pixi run seed -- --demo` | Add a Demo profile with six weeks of history. |
| `pixi run add-child --name Emma --year 2` | Add a learner from the terminal. |
| `pixi run content-check` | Validate every question. |
| `pixi run smoke` | End-to-end check of every page and the quest flow. |
| `pixi run reset-db` | Delete everything and start again (asks first). |
| `pixi run -e dev lint` | Lint. |
| `pixi run -e dev fmt` | Format. |

---

## How it is built

```
tutor/
  content/          the curriculum: what to teach and how to ask it
    curriculum.py     145 skills, mapped to National Curriculum objectives
    generators.py     69 maths question generators
    banks/*.json      English and Science questions, and reading passages
    __init__.py       drawing questions, and marking answers
  services/         the thinking
    scheduler.py      which skill next: spaced repetition + mastery + your intent
    quests.py         building and running a quest
    rewards.py        XP, coins, streaks, badges, shop
    stats.py          everything the parent dashboard shows
    profiles.py       learners and the settings form
  blueprints/       routes: kid.py, api.py, parent.py
  static/
    js/visuals.js     19 SVG renderers (clocks, blocks, charts, fractions…)
    js/play.js        the quest player
    js/app.js         sound, read-aloud, confetti
  templates/
instance/           your database. Never committed.
```

Three deliberate choices:

**Content lives in code and JSON, progress lives in the database.** The database
only ever stores progress against skill ids, so you can rewrite a question
without a migration and without losing history.

**Every question a child sees is written to the database** before it is shown —
prompt, options and correct answer. That is why answers are never sent to the
browser before your child has committed to one, and why a parent can read back
the exact wording of anything asked weeks later.

**No build step and no third-party front-end code.** No npm, no bundler, no CDN,
no chart library, no fonts to download, no audio or image files. Sounds are
synthesised with the Web Audio API, speech uses the browser's own voice, charts
are hand-drawn SVG. It works with the wi-fi off.

---

## Verification

```bash
pixi run content-check   # 145 skills, 679 written questions, 69 generators
pixi run smoke           # 96 checks: pages, quest flow, settings, limits, PIN
pixi run -e dev lint
```

`pixi run smoke` runs against a throwaway database, so it never touches real
progress. It covers first-run setup, every page, CSRF rejection, the full quest
flow including the second chance and clues, every quest mode, subject and year
filtering, the shop, settings persistence, focus-skill selection, the PIN gate
and its lockout, adding and deleting learners, quiet hours and the daily time
limit.

The child-facing player and the parent dashboard were additionally driven
through a real browser at phone and laptop widths to confirm tap-target sizes,
the on-screen keypad, the retry path, resuming a reloaded quest, the
celebration overlay, chart rendering and the absence of horizontal overflow.

---

## A note on security

This is built for one family on one home network.

* The parent PIN is stored hashed, and five wrong attempts locks the form for
  five minutes. It is designed to stop a curious seven-year-old, not an
  attacker.
* All form and API requests are CSRF protected.
* Answers are marked on the server. The browser is never told a correct answer
  in advance.
* `pixi run serve` uses Flask's built-in development server, which is fine for a
  household and is **not** hardened for the public internet. Do not port-forward
  it or expose it beyond your home network.
