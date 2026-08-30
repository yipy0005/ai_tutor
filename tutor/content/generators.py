"""Procedural maths question generators.

Every function takes a seeded ``random.Random`` and an optional difficulty
``level`` (0 = gentle, 1 = normal, 2 = challenge) and returns a question dict:

    {
      "kind":    "choice" | "text" | "truefalse",
      "prompt":  "What is 24 + 8?",
      "choices": [...],            # choice questions only
      "answer":  "32",
      "accept":  ["32"],           # extra spellings accepted for text answers
      "hint":    "Add the ones first.",
      "explain": "24 + 8 = 32",
      "visual":  {...},            # optional picture, drawn by static/js/visuals.js
    }

Because questions are invented on demand a child never sees the same worksheet
twice, which matters a lot when the same skill needs revisiting for weeks.
"""

from __future__ import annotations

import random
from collections.abc import Callable

Question = dict
Generator = Callable[..., Question]

GENERATORS: dict[str, Generator] = {}


def generator(name: str) -> Callable[[Generator], Generator]:
    def wrap(fn: Generator) -> Generator:
        GENERATORS[name] = fn
        return fn

    return wrap


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

NAMES = [
    "Amelia", "Noah", "Priya", "Leo", "Zara", "Oscar", "Maya", "Finn",
    "Aisha", "Jack", "Ivy", "Musa", "Ruby", "Theo", "Nia", "Elsie",
]
THINGS = [
    ("stickers", "🌟"), ("apples", "🍎"), ("marbles", "🔵"), ("pencils", "✏️"),
    ("shells", "🐚"), ("conkers", "🌰"), ("cards", "🃏"), ("buttons", "🔘"),
    ("grapes", "🍇"), ("crayons", "🖍️"),
]


def mc(
    prompt: str,
    answer,
    distractors: list,
    rng: random.Random,
    *,
    hint: str = "",
    explain: str = "",
    visual: dict | None = None,
    prompt_sub: str = "",
    n: int = 4,
) -> Question:
    """Build a multiple-choice question with unique, shuffled options."""
    answer = str(answer)
    options = [answer]
    for d in distractors:
        d = str(d)
        if d not in options:
            options.append(d)
        if len(options) >= n:
            break
    # Safety net: if the distractors collapsed into duplicates, top the list up
    # with nearby numbers so a child is never shown a two-option "guess".
    if len(options) < n and answer.lstrip("-").isdigit():
        for cand in near(int(answer), rng, count=n * 3, spread=5):
            if str(cand) not in options:
                options.append(str(cand))
            if len(options) >= n:
                break
    rng.shuffle(options)
    q: Question = {
        "kind": "choice",
        "prompt": prompt,
        "choices": options,
        "answer": answer,
    }
    if hint:
        q["hint"] = hint
    if explain:
        q["explain"] = explain
    if visual:
        q["visual"] = visual
    if prompt_sub:
        q["prompt_sub"] = prompt_sub
    return q


def txt(
    prompt: str,
    answer,
    *,
    accept: list | None = None,
    hint: str = "",
    explain: str = "",
    visual: dict | None = None,
    prompt_sub: str = "",
    keypad: str = "number",
) -> Question:
    """Build a type-the-answer question."""
    q: Question = {
        "kind": "text",
        "prompt": prompt,
        "answer": str(answer),
        "keypad": keypad,
    }
    if accept:
        q["accept"] = [str(a) for a in accept]
    if hint:
        q["hint"] = hint
    if explain:
        q["explain"] = explain
    if visual:
        q["visual"] = visual
    if prompt_sub:
        q["prompt_sub"] = prompt_sub
    return q


def near(value: int, rng: random.Random, count: int = 6, spread: int = 4) -> list[int]:
    """Plausible wrong numeric answers close to ``value`` (never negative)."""
    out: list[int] = []
    offsets = [1, -1, 2, -2, 10, -10, spread, -spread, 3, -3]
    rng.shuffle(offsets)
    for off in offsets:
        cand = value + off
        if cand >= 0 and cand != value and cand not in out:
            out.append(cand)
        if len(out) >= count:
            break
    return out


def money_str(pence: int) -> str:
    """Format pence the way a UK primary school writes it."""
    if pence < 100:
        return f"{pence}p"
    if pence % 100 == 0:
        return f"£{pence // 100}"
    return f"£{pence // 100}.{pence % 100:02d}"


COINS = [1, 2, 5, 10, 20, 50, 100, 200]
COIN_NAMES = {
    1: "1p", 2: "2p", 5: "5p", 10: "10p",
    20: "20p", 50: "50p", 100: "£1", 200: "£2",
}

_MINUTE_WORDS = {5: "five", 10: "ten", 20: "twenty", 25: "twenty-five"}


def time_words(hour: int, minute: int) -> str:
    """Turn a clock time into the words a Year 1-3 child is taught."""
    nxt = hour % 12 + 1
    hour_12 = hour if 1 <= hour <= 12 else (hour % 12 or 12)
    if minute == 0:
        return f"{hour_12} o'clock"
    if minute == 15:
        return f"quarter past {hour_12}"
    if minute == 30:
        return f"half past {hour_12}"
    if minute == 45:
        return f"quarter to {nxt}"
    if minute in _MINUTE_WORDS:
        return f"{_MINUTE_WORDS[minute]} past {hour_12}"
    if (60 - minute) in _MINUTE_WORDS:
        return f"{_MINUTE_WORDS[60 - minute]} to {nxt}"
    if minute < 30:
        return f"{minute} minutes past {hour_12}"
    return f"{60 - minute} minutes to {nxt}"


def clock(hour: int, minute: int) -> dict:
    return {"type": "clock", "hour": hour, "minute": minute}


ROMAN = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI",
    7: "VII", 8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII",
}


# ===========================================================================
# YEAR 1 — Number and place value
# ===========================================================================


@generator("count_sequence")
def count_sequence(rng: random.Random, level: int = 1) -> Question:
    backwards = rng.random() < 0.4
    start = rng.randint(4, 92)
    step = 1
    seq = [start + i * step for i in range(4)]
    if backwards:
        start = rng.randint(8, 98)
        seq = [start - i * step for i in range(4)]
    gap = rng.randint(1, 2)
    answer = seq[gap]
    shown = [("?" if i == gap else str(v)) for i, v in enumerate(seq)]
    direction = "backwards" if backwards else "forwards"
    return txt(
        f"Fill in the missing number: {',  '.join(shown)}",
        answer,
        hint=f"The numbers are counting {direction} in 1s.",
        explain=f"Counting {direction}: {',  '.join(str(v) for v in seq)}",
        prompt_sub=f"Counting {direction}",
    )


@generator("one_more_less")
def one_more_less(rng: random.Random, level: int = 1) -> Question:
    n = rng.randint(10, 99)
    more = rng.random() < 0.5
    answer = n + 1 if more else n - 1
    word = "one more than" if more else "one less than"
    return mc(
        f"What is {word} {n}?",
        answer,
        near(answer, rng),
        rng,
        hint="One more means count on 1. One less means count back 1.",
        explain=f"{word.capitalize()} {n} is {answer}.",
    )


@generator("compare_20")
def compare_20(rng: random.Random, level: int = 1) -> Question:
    nums = rng.sample(range(1, 21), 4)
    want_big = rng.random() < 0.5
    answer = max(nums) if want_big else min(nums)
    word = "biggest" if want_big else "smallest"
    return mc(
        f"Which number is the {word}?",
        answer,
        [n for n in nums if n != answer],
        rng,
        hint="Count along your number line to see which comes last.",
        explain=f"In order: {', '.join(str(n) for n in sorted(nums))}. The {word} is {answer}.",
    )


@generator("count_steps_1")
def count_steps_1(rng: random.Random, level: int = 1) -> Question:
    step = rng.choice([2, 5, 10])
    start = step * rng.randint(1, 5)
    seq = [start + i * step for i in range(5)]
    gap = rng.randint(2, 4)
    answer = seq[gap]
    shown = [("?" if i == gap else str(v)) for i, v in enumerate(seq)]
    return txt(
        f"Count in {step}s. What is the missing number? {',  '.join(shown)}",
        answer,
        hint=f"Keep adding {step} each time.",
        explain=f"Counting in {step}s: {',  '.join(str(v) for v in seq)}",
        visual={"type": "number_line", "start": seq[0], "end": seq[-1], "step": step, "mark": None},
    )


@generator("odd_even")
def odd_even(rng: random.Random, level: int = 1) -> Question:
    want_odd = rng.random() < 0.5
    top = 100 if level else 30
    odds = [n for n in range(1, top) if n % 2 == 1]
    evens = [n for n in range(2, top) if n % 2 == 0]
    matching, other = (odds, evens) if want_odd else (evens, odds)
    answer = rng.choice(matching)
    other = rng.sample(other, 3)
    word = "odd" if want_odd else "even"
    return mc(
        f"Which of these numbers is {word}?",
        answer,
        other,
        rng,
        hint="Even numbers end in 0, 2, 4, 6 or 8. Odd numbers end in 1, 3, 5, 7 or 9.",
        explain=f"{answer} is {word} because it ends in {answer % 10}.",
    )


# ===========================================================================
# YEAR 1 — Addition and subtraction
# ===========================================================================


@generator("bonds_10")
def bonds_10(rng: random.Random, level: int = 1) -> Question:
    a = rng.randint(0, 10)
    answer = 10 - a
    return txt(
        f"{a} + ? = 10",
        answer,
        hint="How many more do you need to reach 10?",
        explain=f"{a} + {answer} = 10",
        visual={"type": "dots", "filled": a, "empty": answer, "per_row": 5},
    )


@generator("bonds_20")
def bonds_20(rng: random.Random, level: int = 1) -> Question:
    a = rng.randint(2, 18)
    answer = 20 - a
    return txt(
        f"{a} + ? = 20",
        answer,
        hint="First get to 10, then carry on to 20.",
        explain=f"{a} + {answer} = 20",
        visual={"type": "dots", "filled": a, "empty": answer, "per_row": 10},
    )


@generator("add_within_20")
def add_within_20(rng: random.Random, level: int = 1) -> Question:
    a = rng.randint(2, 13)
    b = rng.randint(2, 20 - a)
    answer = a + b
    return txt(
        f"{a} + {b} = ?",
        answer,
        hint=f"Start at {max(a, b)} and count on {min(a, b)}.",
        explain=f"{a} + {b} = {answer}",
        visual={"type": "dots", "filled": a, "empty": b, "per_row": 10, "labels": [str(a), str(b)]},
    )


@generator("sub_within_20")
def sub_within_20(rng: random.Random, level: int = 1) -> Question:
    a = rng.randint(6, 20)
    b = rng.randint(1, a - 1)
    answer = a - b
    return txt(
        f"{a} - {b} = ?",
        answer,
        hint=f"Start at {a} and count back {b}.",
        explain=f"{a} - {b} = {answer}",
    )


@generator("doubles")
def doubles(rng: random.Random, level: int = 1) -> Question:
    n = rng.randint(1, 10 if level < 2 else 20)
    if rng.random() < 0.5:
        return txt(
            f"What is double {n}?",
            n * 2,
            hint=f"Double means {n} + {n}.",
            explain=f"Double {n} is {n} + {n} = {n * 2}.",
        )
    return txt(
        f"What is half of {n * 2}?",
        n,
        hint="Halving is the opposite of doubling. Share it into 2 equal groups.",
        explain=f"Half of {n * 2} is {n}, because {n} + {n} = {n * 2}.",
    )


@generator("word_problem_1")
def word_problem_1(rng: random.Random, level: int = 1) -> Question:
    name = rng.choice(NAMES)
    thing, emoji = rng.choice(THINGS)
    if rng.random() < 0.55:
        a, b = rng.randint(3, 12), rng.randint(2, 8)
        return txt(
            f"{name} has {a} {thing}. A friend gives {name} {b} more. "
            f"How many {thing} does {name} have now?",
            a + b,
            hint="'Gives more' means we add.",
            explain=f"{a} + {b} = {a + b} {thing}.",
            prompt_sub=emoji * min(a, 10),
        )
    a = rng.randint(8, 18)
    b = rng.randint(2, a - 2)
    return txt(
        f"{name} has {a} {thing} and gives away {b}. How many {thing} are left?",
        a - b,
        hint="'Gives away' means we take away.",
        explain=f"{a} - {b} = {a - b} {thing}.",
        prompt_sub=emoji * min(a, 10),
    )


# ===========================================================================
# YEAR 1 — Fractions, measurement, geometry
# ===========================================================================


@generator("half_quarter")
def half_quarter(rng: random.Random, level: int = 1) -> Question:
    if rng.random() < 0.5:
        denom = rng.choice([2, 4])
        n = denom * rng.randint(2, 6)
        answer = n // denom
        word = "half" if denom == 2 else "a quarter"
        return txt(
            f"What is {word} of {n}?",
            answer,
            hint=f"Share {n} equally into {denom} groups.",
            explain=f"{n} shared into {denom} equal groups is {answer} in each group.",
            visual={"type": "share", "total": n, "groups": denom},
        )
    denom = rng.choice([2, 4])
    shaded = 1
    return mc(
        "What fraction of the shape is shaded?",
        "a half" if denom == 2 else "a quarter",
        ["a half", "a quarter", "a third", "a whole"],
        rng,
        hint=f"Count the equal parts. There are {denom}.",
        explain=f"1 part out of {denom} equal parts is shaded.",
        visual={"type": "fraction", "num": shaded, "den": denom, "shape": "circle"},
    )


@generator("coins_recognise")
def coins_recognise(rng: random.Random, level: int = 1) -> Question:
    if rng.random() < 0.5:
        coin = rng.choice([1, 2, 5, 10, 20, 50, 100, 200])
        others = [c for c in COINS if c != coin]
        rng.shuffle(others)
        return mc(
            f"Which coin is worth {money_str(coin)}?",
            COIN_NAMES[coin],
            [COIN_NAMES[c] for c in others],
            rng,
            hint="Look at the number written on the coin.",
            explain=f"The {COIN_NAMES[coin]} coin is worth {money_str(coin)}.",
            visual={"type": "coins", "values": [coin]},
        )
    coin = rng.choice([1, 2, 5, 10, 20])
    count = rng.randint(2, 4)
    total = coin * count
    return txt(
        "How much money is here? Write your answer in pence.",
        f"{total}p",
        accept=[str(total), f"{total}p"],
        hint=f"Count in {coin}s.",
        explain=f"{count} lots of {money_str(coin)} is {money_str(total)}.",
        visual={"type": "coins", "values": [coin] * count},
        keypad="money",
    )


@generator("time_oclock")
def time_oclock(rng: random.Random, level: int = 1) -> Question:
    hour = rng.randint(1, 12)
    minute = rng.choice([0, 30])
    answer = time_words(hour, minute)
    others = set()
    while len(others) < 4:
        h2 = rng.randint(1, 12)
        m2 = rng.choice([0, 30])
        w = time_words(h2, m2)
        if w != answer:
            others.add(w)
    return mc(
        "What time does the clock show?",
        answer,
        list(others),
        rng,
        hint="The short hand tells you the hour. The long hand points up at o'clock.",
        explain=f"The clock shows {answer}.",
        visual=clock(hour, minute),
    )


@generator("compare_measures")
def compare_measures(rng: random.Random, level: int = 1) -> Question:
    sets = [
        ("heaviest", ["a feather 🪶", "a brick 🧱", "a leaf 🍃", "a paperclip 📎"], "a brick 🧱"),
        ("lightest", ["a book 📚", "a bicycle 🚲", "a feather 🪶", "a chair 🪑"], "a feather 🪶"),
        ("longest", ["a pencil ✏️", "a bus 🚌", "a shoe 👟", "a spoon 🥄"], "a bus 🚌"),
        ("shortest", ["a train 🚆", "an ant 🐜", "a ladder 🪜", "a river 🏞️"], "an ant 🐜"),
        ("tallest", ["a mouse 🐭", "a giraffe 🦒", "a cat 🐈", "a duck 🦆"], "a giraffe 🦒"),
        ("holds the most", ["a bathtub 🛁", "a teaspoon 🥄", "a mug ☕", "a bottle 🍼"], "a bathtub 🛁"),
        ("holds the least", ["a bucket 🪣", "a teaspoon 🥄", "a kettle 🫖", "a watering can 🚿"], "a teaspoon 🥄"),
        ("coldest", ["an ice lolly 🍦", "a cup of tea ☕", "warm soup 🍲", "a radiator 🔥"], "an ice lolly 🍦"),
    ]
    word, options, answer = rng.choice(sets)
    return mc(
        f"Which one is the {word}?",
        answer,
        [o for o in options if o != answer],
        rng,
        hint="Picture each one in your head and compare them.",
        explain=f"{answer} is the {word} of these.",
    )


SHAPES_2D = {
    "circle": 0, "triangle": 3, "square": 4, "rectangle": 4,
    "pentagon": 5, "hexagon": 6, "octagon": 8,
}
SHAPES_3D = {
    "cube": ("6 square faces, 8 vertices", "🧊"),
    "cuboid": ("6 rectangular faces, 8 vertices", "📦"),
    "sphere": ("1 curved surface, no edges", "⚽"),
    "cylinder": ("2 circular faces and 1 curved surface", "🥫"),
    "cone": ("1 circular face and 1 point", "🍦"),
    "pyramid": ("a square base and 4 triangular faces", "🔺"),
}


@generator("shapes_2d_name")
def shapes_2d_name(rng: random.Random, level: int = 1) -> Question:
    name = rng.choice(list(SHAPES_2D))
    if rng.random() < 0.6:
        return mc(
            "What is this shape called?",
            name,
            [n for n in SHAPES_2D if n != name],
            rng,
            hint="Count the straight sides.",
            explain=(
                f"A {name} has {SHAPES_2D[name]} straight sides."
                if SHAPES_2D[name]
                else "A circle has no straight sides — it is one curved line."
            ),
            visual={"type": "shape2d", "name": name},
        )
    name = rng.choice([n for n in SHAPES_2D if SHAPES_2D[n]])
    sides = SHAPES_2D[name]
    return mc(
        f"How many sides does a {name} have?",
        sides,
        [s for s in [3, 4, 5, 6, 8, 2] if s != sides],
        rng,
        hint="Look at the picture and count around the edge.",
        explain=f"A {name} has {sides} sides.",
        visual={"type": "shape2d", "name": name},
    )


@generator("shapes_3d_name")
def shapes_3d_name(rng: random.Random, level: int = 1) -> Question:
    name = rng.choice(list(SHAPES_3D))
    desc, emoji = SHAPES_3D[name]
    if rng.random() < 0.5:
        return mc(
            f"Which 3-D shape has {desc}?",
            name,
            [n for n in SHAPES_3D if n != name],
            rng,
            hint="Think about a real object with that shape.",
            explain=f"A {name} has {desc}.",
            prompt_sub=emoji,
        )
    return mc(
        f"What 3-D shape is this? {emoji}",
        name,
        [n for n in SHAPES_3D if n != name],
        rng,
        hint=f"It has {desc}.",
        explain=f"This is a {name}: {desc}.",
    )


# ===========================================================================
# YEAR 2
# ===========================================================================


@generator("place_value_2")
def place_value_2(rng: random.Random, level: int = 1) -> Question:
    tens, ones = rng.randint(1, 9), rng.randint(0, 9)
    n = tens * 10 + ones
    roll = rng.random()
    if roll < 0.35:
        which = rng.choice(["tens", "ones"])
        answer = tens if which == "tens" else ones
        return txt(
            f"How many {which} are there in {n}?",
            answer,
            hint="Split the number into tens and ones.",
            explain=f"{n} is {tens} tens and {ones} ones.",
            visual={"type": "blocks", "hundreds": 0, "tens": tens, "ones": ones},
        )
    if roll < 0.7:
        digit = rng.choice(["tens", "ones"])
        d = tens if digit == "tens" else ones
        value = tens * 10 if digit == "tens" else ones
        return mc(
            f"In the number {n}, what is the value of the {digit} digit?",
            value,
            [d, tens, ones, value + 10, value - 10 if value >= 10 else value + 1],
            rng,
            hint="A digit in the tens place is worth that many tens.",
            explain=f"The {digit} digit is {d}, so it is worth {value}.",
            visual={"type": "blocks", "hundreds": 0, "tens": tens, "ones": ones},
        )
    return txt(
        "What number is shown by the blocks?",
        n,
        hint="Each tall block is 10. Each small block is 1.",
        explain=f"{tens} tens and {ones} ones makes {n}.",
        visual={"type": "blocks", "hundreds": 0, "tens": tens, "ones": ones},
    )


@generator("compare_100")
def compare_100(rng: random.Random, level: int = 1) -> Question:
    a, b = rng.sample(range(1, 101), 2)
    if rng.random() < 0.15:
        b = a
    answer = "<" if a < b else (">" if a > b else "=")
    return mc(
        f"Which sign goes in the box?   {a}  ☐  {b}",
        answer,
        ["<", ">", "="],
        rng,
        n=3,
        hint="The crocodile's mouth always opens towards the bigger number.",
        explain=f"{a} {answer} {b}",
    )


@generator("count_steps_2")
def count_steps_2(rng: random.Random, level: int = 1) -> Question:
    step = rng.choice([2, 3, 5, 10])
    start = step * rng.randint(1, 6)
    seq = [start + i * step for i in range(5)]
    gap = rng.randint(2, 4)
    shown = [("?" if i == gap else str(v)) for i, v in enumerate(seq)]
    return txt(
        f"Count in {step}s. What is the missing number? {',  '.join(shown)}",
        seq[gap],
        hint=f"Add {step} to the number before it.",
        explain=f"Counting in {step}s: {',  '.join(str(v) for v in seq)}",
    )


@generator("add_2digit")
def add_2digit(rng: random.Random, level: int = 1) -> Question:
    if level == 0:
        a, b = rng.randint(11, 40), rng.randint(11, 30)
    else:
        a, b = rng.randint(14, 68), rng.randint(14, 31)
    answer = a + b
    carried = (a % 10) + (b % 10) >= 10
    return txt(
        f"{a} + {b} = ?",
        answer,
        hint=(
            "Add the ones. They make more than 10, so carry a ten across."
            if carried
            else "Add the ones, then add the tens."
        ),
        explain=f"{a % 10} + {b % 10} = {a % 10 + b % 10} ones.  {a} + {b} = {answer}",
        visual={"type": "column", "a": a, "b": b, "op": "+"},
    )


@generator("sub_2digit")
def sub_2digit(rng: random.Random, level: int = 1) -> Question:
    a = rng.randint(30, 99)
    b = rng.randint(11, a - 10)
    answer = a - b
    borrowed = (a % 10) < (b % 10)
    return txt(
        f"{a} - {b} = ?",
        answer,
        hint=(
            "There are not enough ones, so exchange one ten for ten ones."
            if borrowed
            else "Take away the ones, then take away the tens."
        ),
        explain=f"{a} - {b} = {answer}",
        visual={"type": "column", "a": a, "b": b, "op": "-"},
    )


@generator("facts_20")
def facts_20(rng: random.Random, level: int = 1) -> Question:
    if rng.random() < 0.5:
        a = rng.randint(3, 17)
        b = rng.randint(1, 20 - a)
        return txt(f"{a} + {b} = ?", a + b, hint="Try to remember it — no counting!",
                   explain=f"{a} + {b} = {a + b}", prompt_sub="Quick facts ⚡")
    a = rng.randint(6, 20)
    b = rng.randint(1, a)
    return txt(f"{a} - {b} = ?", a - b, hint="Use an addition fact you know to help.",
               explain=f"{a} - {b} = {a - b}", prompt_sub="Quick facts ⚡")


@generator("missing_number_2")
def missing_number_2(rng: random.Random, level: int = 1) -> Question:
    a = rng.randint(11, 45)
    answer = rng.randint(6, 40)
    total = a + answer
    if rng.random() < 0.5:
        return txt(
            f"{a} + ? = {total}",
            answer,
            hint=f"Take {a} away from {total} to find the missing number.",
            explain=f"{total} - {a} = {answer}, so {a} + {answer} = {total}.",
        )
    return txt(
        f"? - {a} = {answer}",
        total,
        hint=f"Add {a} and {answer} to find the missing number.",
        explain=f"{answer} + {a} = {total}, so {total} - {a} = {answer}.",
    )


@generator("times_2_5_10")
def times_2_5_10(rng: random.Random, level: int = 1) -> Question:
    table = rng.choice([2, 5, 10])
    other = rng.randint(2, 12)
    answer = table * other
    return txt(
        f"{other} × {table} = ?",
        answer,
        hint=f"Count in {table}s, {other} times.",
        explain=f"{other} × {table} = {answer}",
        prompt_sub=f"{table} times table",
    )


@generator("divide_2_5_10")
def divide_2_5_10(rng: random.Random, level: int = 1) -> Question:
    table = rng.choice([2, 5, 10])
    answer = rng.randint(2, 12)
    total = table * answer
    return txt(
        f"{total} ÷ {table} = ?",
        answer,
        hint=f"How many {table}s fit into {total}?",
        explain=f"{answer} × {table} = {total}, so {total} ÷ {table} = {answer}.",
        prompt_sub=f"Dividing by {table}",
    )


@generator("arrays")
def arrays(rng: random.Random, level: int = 1) -> Question:
    rows, cols = rng.randint(2, 5), rng.randint(2, 6)
    total = rows * cols
    if rng.random() < 0.5:
        return txt(
            "How many dots are there altogether?",
            total,
            hint=f"There are {rows} rows of {cols}. That is {rows} × {cols}.",
            explain=f"{rows} × {cols} = {total}",
            visual={"type": "array", "rows": rows, "cols": cols},
        )
    answer = f"{rows} × {cols}"
    return mc(
        "Which multiplication does this picture show?",
        answer,
        [f"{rows} × {cols + 1}", f"{rows + 1} × {cols}", f"{rows} + {cols}", f"{cols} × {cols}"],
        rng,
        hint="Count the rows first, then how many are in each row.",
        explain=f"{rows} rows of {cols} is {rows} × {cols} = {total}.",
        visual={"type": "array", "rows": rows, "cols": cols},
    )


@generator("fraction_of_amount_2")
def fraction_of_amount_2(rng: random.Random, level: int = 1) -> Question:
    # Year 2 covers 1/2, 1/3, 1/4, 2/4 and 3/4 only.
    num, den = rng.choice([(1, 2), (1, 3), (1, 4), (2, 4), (3, 4)])
    total = den * rng.randint(2, 6)
    answer = total // den * num
    return txt(
        f"What is {num}/{den} of {total}?",
        answer,
        hint=f"Share {total} into {den} equal groups, then take {num} group{'s' if num > 1 else ''}.",
        explain=f"{total} ÷ {den} = {total // den}, and {total // den} × {num} = {answer}.",
        visual={"type": "share", "total": total, "groups": den, "take": num},
    )


@generator("fraction_equiv_2")
def fraction_equiv_2(rng: random.Random, level: int = 1) -> Question:
    pairs = [("2/4", "1/2"), ("1/2", "2/4"), ("2/2", "1 whole"), ("4/4", "1 whole")]
    left, right = rng.choice(pairs)
    return mc(
        f"{left} is the same as...",
        right,
        ["1/2", "2/4", "1/4", "1 whole", "3/4"],
        rng,
        hint="Draw it and shade it in to check.",
        explain=f"{left} and {right} cover exactly the same amount.",
        visual={
            "type": "fraction",
            "num": int(left.split("/")[0]),
            "den": int(left.split("/")[1]),
            "shape": "bar",
        },
    )


@generator("money_2")
def money_2(rng: random.Random, level: int = 1) -> Question:
    coins = rng.choices([1, 2, 5, 10, 20, 50], k=rng.randint(3, 4))
    total = sum(coins)
    return txt(
        "How much money is here altogether?",
        money_str(total),
        accept=[str(total), f"{total}p", money_str(total)],
        hint="Start with the biggest coin and count on.",
        explain=" + ".join(money_str(c) for c in sorted(coins, reverse=True)) + f" = {money_str(total)}",
        visual={"type": "coins", "values": coins},
        keypad="money",
    )


@generator("change_2")
def change_2(rng: random.Random, level: int = 1) -> Question:
    paid = rng.choice([50, 100])
    cost = rng.randrange(5, paid - 4, 5)
    answer = paid - cost
    name = rng.choice(NAMES)
    thing, emoji = rng.choice(THINGS)
    return txt(
        f"{name} buys some {thing} for {money_str(cost)} and pays with {money_str(paid)}. "
        f"How much change should {name} get?",
        money_str(answer),
        accept=[str(answer), f"{answer}p", money_str(answer)],
        hint=f"Count on from {money_str(cost)} up to {money_str(paid)}.",
        explain=f"{money_str(paid)} - {money_str(cost)} = {money_str(answer)}",
        prompt_sub=emoji,
        keypad="money",
    )


@generator("time_5min")
def time_5min(rng: random.Random, level: int = 1) -> Question:
    hour = rng.randint(1, 12)
    minute = rng.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])
    answer = time_words(hour, minute)
    others = set()
    guard = 0
    while len(others) < 4 and guard < 60:
        guard += 1
        h2 = rng.choice([hour, hour % 12 + 1, rng.randint(1, 12)])
        m2 = rng.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])
        w = time_words(h2, m2)
        if w != answer:
            others.add(w)
    return mc(
        "What time does the clock show?",
        answer,
        list(others),
        rng,
        hint="Count round the clock in 5s from the top.",
        explain=f"The clock shows {answer}.",
        visual=clock(hour, minute),
    )


@generator("choose_units")
def choose_units(rng: random.Random, level: int = 1) -> Question:
    items = [
        ("the length of your pencil", "centimetres (cm)"),
        ("the length of the playground", "metres (m)"),
        ("how heavy an apple is", "grams (g)"),
        ("how heavy you are", "kilograms (kg)"),
        ("the water in a teaspoon", "millilitres (ml)"),
        ("the water in a bucket", "litres (l)"),
        ("how tall a door is", "metres (m)"),
        ("how heavy a bag of flour is", "kilograms (kg)"),
        ("the juice in a carton", "millilitres (ml)"),
        ("the width of a stamp", "centimetres (cm)"),
    ]
    thing, answer = rng.choice(items)
    all_units = ["centimetres (cm)", "metres (m)", "grams (g)", "kilograms (kg)",
                 "millilitres (ml)", "litres (l)"]
    return mc(
        f"Which unit would you use to measure {thing}?",
        answer,
        [u for u in all_units if u != answer],
        rng,
        hint="Small things use small units. Big things use big units.",
        explain=f"We measure {thing} in {answer}.",
    )


@generator("shape_properties_2")
def shape_properties_2(rng: random.Random, level: int = 1) -> Question:
    if rng.random() < 0.5:
        name = rng.choice(["triangle", "square", "rectangle", "pentagon", "hexagon", "octagon"])
        sides = SHAPES_2D[name]
        which = rng.choice(["sides", "vertices (corners)"])
        return txt(
            f"How many {which} does a {name} have?",
            sides,
            hint="A 2-D shape has the same number of corners as sides.",
            explain=f"A {name} has {sides} sides and {sides} vertices.",
            visual={"type": "shape2d", "name": name},
        )
    facts = [
        ("cube", "faces", 6), ("cube", "edges", 12), ("cube", "vertices", 8),
        ("cuboid", "faces", 6), ("cuboid", "vertices", 8),
        ("cylinder", "faces", 3), ("cone", "faces", 2),
        ("square-based pyramid", "faces", 5), ("square-based pyramid", "vertices", 5),
    ]
    name, which, answer = rng.choice(facts)
    return mc(
        f"How many {which} does a {name} have?",
        answer,
        [answer + 1, answer - 1, answer + 2, 12, 6, 8],
        rng,
        hint="Picture the shape and count carefully.",
        explain=f"A {name} has {answer} {which}.",
    )


@generator("symmetry_2")
def symmetry_2(rng: random.Random, level: int = 1) -> Question:
    facts = [("square", 4), ("rectangle", 2), ("circle", "lots"), ("equilateral triangle", 3),
             ("regular hexagon", 6), ("regular pentagon", 5)]
    name, answer = rng.choice(facts)
    if answer == "lots":
        return mc(
            "How many lines of symmetry does a circle have?",
            "too many to count",
            ["1", "2", "4", "none"],
            rng,
            hint="Try folding it in different places. Does it always match?",
            explain="A circle can be folded in half through the middle in any direction.",
            visual={"type": "shape2d", "name": "circle"},
        )
    return mc(
        f"How many lines of symmetry does a {name} have?",
        answer,
        [1, 2, 3, 4, 5, 6, 0],
        rng,
        hint="A line of symmetry is a fold line where both halves match exactly.",
        explain=f"A {name} has {answer} lines of symmetry.",
        visual={"type": "shape2d", "name": name.split()[-1]},
    )


@generator("tally_pictogram")
def tally_pictogram(rng: random.Random, level: int = 1) -> Question:
    labels = rng.sample(["Cats", "Dogs", "Rabbits", "Fish", "Birds", "Hamsters"], 4)
    values = [rng.randint(2, 12) for _ in labels]
    use_tally = rng.random() < 0.5
    visual = {
        "type": "tally" if use_tally else "pictogram",
        "labels": labels,
        "values": values,
        "symbol": "⭐",
        "title": "Favourite pets in Class 3",
    }
    roll = rng.random()
    if roll < 0.4:
        idx = rng.randrange(len(labels))
        return txt(
            f"How many children chose {labels[idx]}?",
            values[idx],
            hint="Find the right row and count carefully.",
            explain=f"{labels[idx]} has {values[idx]}.",
            visual=visual,
        )
    if roll < 0.7:
        top = labels[values.index(max(values))]
        return mc(
            "Which was the most popular?",
            top,
            [x for x in labels if x != top],
            rng,
            hint="Look for the longest row.",
            explain=f"{top} has the most with {max(values)}.",
            visual=visual,
        )
    i, j = rng.sample(range(len(labels)), 2)
    if values[i] < values[j]:
        i, j = j, i
    return txt(
        f"How many more children chose {labels[i]} than {labels[j]}?",
        values[i] - values[j],
        hint="Find both numbers, then subtract.",
        explain=f"{values[i]} - {values[j]} = {values[i] - values[j]}",
        visual=visual,
    )


# ===========================================================================
# YEAR 3 — Number and place value
# ===========================================================================


@generator("place_value_3")
def place_value_3(rng: random.Random, level: int = 1) -> Question:
    h, t, o = rng.randint(1, 9), rng.randint(0, 9), rng.randint(0, 9)
    n = h * 100 + t * 10 + o
    roll = rng.random()
    if roll < 0.3:
        return txt(
            "What number is shown?",
            n,
            hint="Count the hundreds, then the tens, then the ones.",
            explain=f"{h} hundreds, {t} tens and {o} ones makes {n}.",
            visual={"type": "blocks", "hundreds": h, "tens": t, "ones": o},
        )
    if roll < 0.65:
        which = rng.choice(["hundreds", "tens", "ones"])
        digit = {"hundreds": h, "tens": t, "ones": o}[which]
        value = {"hundreds": h * 100, "tens": t * 10, "ones": o}[which]
        return mc(
            f"What is the value of the {which} digit in {n}?",
            value,
            [digit, h, t, o, h * 100, t * 10, value + 10],
            rng,
            hint="The place a digit sits in tells you what it is worth.",
            explain=f"The {which} digit is {digit}, so it is worth {value}.",
        )
    return txt(
        f"Write {h} hundreds, {t} tens and {o} ones as a number.",
        n,
        hint="Put the digits in order: hundreds, tens, ones.",
        explain=f"{h} hundreds + {t} tens + {o} ones = {n}",
    )


@generator("compare_1000")
def compare_1000(rng: random.Random, level: int = 1) -> Question:
    if rng.random() < 0.5:
        a, b = rng.sample(range(100, 1001), 2)
        answer = "<" if a < b else ">"
        return mc(
            f"Which sign goes in the box?   {a}  ☐  {b}",
            answer,
            ["<", ">", "="],
            rng,
            n=3,
            hint="Compare the hundreds first. If they match, compare the tens.",
            explain=f"{a} {answer} {b}",
        )
    nums = rng.sample(range(100, 1000), 4)
    want_big = rng.random() < 0.5
    answer = max(nums) if want_big else min(nums)
    return mc(
        f"Which number is the {'largest' if want_big else 'smallest'}?",
        answer,
        [n for n in nums if n != answer],
        rng,
        hint="Start by looking at the hundreds digit.",
        explain=f"In order: {', '.join(str(n) for n in sorted(nums))}.",
    )


@generator("count_steps_3")
def count_steps_3(rng: random.Random, level: int = 1) -> Question:
    step = rng.choice([4, 8, 50, 100])
    start = step * rng.randint(1, 5)
    seq = [start + i * step for i in range(5)]
    gap = rng.randint(2, 4)
    shown = [("?" if i == gap else str(v)) for i, v in enumerate(seq)]
    return txt(
        f"Count in {step}s. What is the missing number? {',  '.join(shown)}",
        seq[gap],
        hint=f"Add {step} each time.",
        explain=f"Counting in {step}s: {',  '.join(str(v) for v in seq)}",
    )


@generator("round_3")
def round_3(rng: random.Random, level: int = 1) -> Question:
    n = rng.randint(112, 989)
    to_hundred = rng.random() < 0.5
    if to_hundred:
        answer = (n + 50) // 100 * 100
        return txt(
            f"Round {n} to the nearest 100.",
            answer,
            hint="Look at the tens digit. 5 or more rounds up.",
            explain=f"The tens digit of {n} is {n // 10 % 10}, so {n} rounds to {answer}.",
        )
    answer = (n + 5) // 10 * 10
    return txt(
        f"Round {n} to the nearest 10.",
        answer,
        hint="Look at the ones digit. 5 or more rounds up.",
        explain=f"The ones digit of {n} is {n % 10}, so {n} rounds to {answer}.",
    )


# ===========================================================================
# YEAR 3 — Addition and subtraction
# ===========================================================================


@generator("mental_add_sub_3")
def mental_add_sub_3(rng: random.Random, level: int = 1) -> Question:
    n = rng.randint(120, 880)
    kind = rng.choice(["ones", "tens", "hundreds"])
    amount = {"ones": rng.randint(2, 9), "tens": rng.choice([10, 20, 30, 40, 50]),
              "hundreds": rng.choice([100, 200, 300])}[kind]
    add = rng.random() < 0.5
    if add:
        answer = n + amount
        return txt(
            f"{n} + {amount} = ?",
            answer,
            hint=f"Only the {kind} change. Do it in your head.",
            explain=f"{n} + {amount} = {answer}",
            prompt_sub="In your head 🧠",
        )
    if amount > n:
        amount = min(amount, n - 10)
    answer = n - amount
    return txt(
        f"{n} - {amount} = ?",
        answer,
        hint=f"Only the {kind} change. Do it in your head.",
        explain=f"{n} - {amount} = {answer}",
        prompt_sub="In your head 🧠",
    )


@generator("add_3digit")
def add_3digit(rng: random.Random, level: int = 1) -> Question:
    a = rng.randint(124, 799)
    b = rng.randint(105, 199) if level == 0 else rng.randint(115, 480)
    answer = a + b
    return txt(
        f"{a} + {b} = ?",
        answer,
        hint="Line up the ones, tens and hundreds. Start with the ones.",
        explain=f"{a} + {b} = {answer}",
        visual={"type": "column", "a": a, "b": b, "op": "+"},
    )


@generator("sub_3digit")
def sub_3digit(rng: random.Random, level: int = 1) -> Question:
    a = rng.randint(320, 989)
    b = rng.randint(105, a - 100)
    answer = a - b
    return txt(
        f"{a} - {b} = ?",
        answer,
        hint="Start with the ones. Exchange a ten if you need more ones.",
        explain=f"{a} - {b} = {answer}",
        visual={"type": "column", "a": a, "b": b, "op": "-"},
    )


@generator("missing_number_3")
def missing_number_3(rng: random.Random, level: int = 1) -> Question:
    a = rng.randint(120, 480)
    answer = rng.randint(50, 400)
    total = a + answer
    if rng.random() < 0.5:
        return txt(
            f"{a} + ? = {total}",
            answer,
            hint=f"Subtract to find it: {total} - {a}.",
            explain=f"{total} - {a} = {answer}",
        )
    return txt(
        f"? - {a} = {answer}",
        total,
        hint="Use the inverse: add the two numbers you can see.",
        explain=f"{answer} + {a} = {total}",
    )


@generator("estimate_3")
def estimate_3(rng: random.Random, level: int = 1) -> Question:
    a, b = rng.randint(105, 495), rng.randint(105, 495)
    ra = (a + 50) // 100 * 100
    rb = (b + 50) // 100 * 100
    answer = ra + rb
    return mc(
        f"Estimate {a} + {b} by rounding each number to the nearest 100.",
        answer,
        [answer + 100, answer - 100, a + b, answer + 200],
        rng,
        hint=f"{a} rounds to {ra}. {b} rounds to {rb}.",
        explain=f"{ra} + {rb} = {answer}, so the answer is about {answer}.",
    )


# ===========================================================================
# YEAR 3 — Multiplication and division
# ===========================================================================


def _times_table(rng: random.Random, table: int) -> Question:
    other = rng.randint(2, 12)
    if rng.random() < 0.75:
        return txt(
            f"{other} × {table} = ?",
            other * table,
            hint=f"Count in {table}s, or use a fact you already know.",
            explain=f"{other} × {table} = {other * table}",
            prompt_sub=f"{table} times table",
        )
    answer = other
    return txt(
        f"? × {table} = {other * table}",
        answer,
        hint=f"How many {table}s make {other * table}?",
        explain=f"{answer} × {table} = {other * table}",
        prompt_sub=f"{table} times table",
    )


@generator("times_3")
def times_3(rng: random.Random, level: int = 1) -> Question:
    return _times_table(rng, 3)


@generator("times_4")
def times_4(rng: random.Random, level: int = 1) -> Question:
    return _times_table(rng, 4)


@generator("times_8")
def times_8(rng: random.Random, level: int = 1) -> Question:
    return _times_table(rng, 8)


@generator("divide_3_4_8")
def divide_3_4_8(rng: random.Random, level: int = 1) -> Question:
    table = rng.choice([3, 4, 8])
    answer = rng.randint(2, 12)
    total = table * answer
    return txt(
        f"{total} ÷ {table} = ?",
        answer,
        hint=f"How many groups of {table} are in {total}?",
        explain=f"{answer} × {table} = {total}, so {total} ÷ {table} = {answer}.",
        prompt_sub=f"Dividing by {table}",
    )


@generator("mult_2digit_1digit")
def mult_2digit_1digit(rng: random.Random, level: int = 1) -> Question:
    a = rng.randint(12, 39)
    b = rng.choice([2, 3, 4, 5, 8])
    answer = a * b
    tens, ones = a // 10 * 10, a % 10
    return txt(
        f"{a} × {b} = ?",
        answer,
        hint=f"Split {a} into {tens} and {ones}, then multiply each part by {b}.",
        explain=f"{tens} × {b} = {tens * b} and {ones} × {b} = {ones * b}. "
                f"{tens * b} + {ones * b} = {answer}",
        visual={"type": "partition", "value": a, "times": b},
    )


@generator("divide_remainder_3")
def divide_remainder_3(rng: random.Random, level: int = 1) -> Question:
    divisor = rng.choice([3, 4, 5, 8])
    quotient = rng.randint(2, 9)
    remainder = rng.randint(1, divisor - 1)
    total = divisor * quotient + remainder
    if rng.random() < 0.5:
        return txt(
            f"{total} ÷ {divisor} = ? remainder ?  →  what is the remainder?",
            remainder,
            hint=f"Find the biggest multiple of {divisor} that fits inside {total}.",
            explain=f"{divisor} × {quotient} = {divisor * quotient}, "
                    f"and {total} - {divisor * quotient} = {remainder} left over.",
        )
    name = rng.choice(NAMES)
    thing, emoji = rng.choice(THINGS)
    return txt(
        f"{name} shares {total} {thing} equally between {divisor} friends. "
        f"How many does each friend get?",
        quotient,
        hint=f"Share them out into {divisor} equal groups.",
        explain=f"{divisor} × {quotient} = {divisor * quotient}, so each friend gets "
                f"{quotient} with {remainder} left over.",
        prompt_sub=emoji,
    )


@generator("scaling_3")
def scaling_3(rng: random.Random, level: int = 1) -> Question:
    base = rng.randint(3, 12)
    factor = rng.choice([2, 3, 4, 5, 8])
    name = rng.choice(NAMES)
    if rng.random() < 0.5:
        return txt(
            f"A red ribbon is {base} cm long. A blue ribbon is {factor} times as long. "
            f"How long is the blue ribbon?",
            base * factor,
            hint=f"'{factor} times as long' means multiply by {factor}.",
            explain=f"{base} × {factor} = {base * factor} cm",
            prompt_sub="Answer in centimetres",
        )
    total = base * factor
    return txt(
        f"{name} has {total} stickers. That is {factor} times as many as Sam. "
        f"How many does Sam have?",
        base,
        hint=f"Work backwards: divide by {factor}.",
        explain=f"{total} ÷ {factor} = {base}",
    )


# ===========================================================================
# YEAR 3 — Fractions
# ===========================================================================


@generator("tenths_3")
def tenths_3(rng: random.Random, level: int = 1) -> Question:
    roll = rng.random()
    if roll < 0.4:
        n = 10 * rng.randint(2, 9)
        return txt(
            f"What is 1/10 of {n}?",
            n // 10,
            hint="Dividing by 10 finds one tenth.",
            explain=f"{n} ÷ 10 = {n // 10}",
        )
    if roll < 0.7:
        start = rng.randint(1, 5)
        seq = [f"{start + i}/10" for i in range(4)]
        gap = rng.randint(1, 2)
        shown = [("?" if i == gap else v) for i, v in enumerate(seq)]
        return txt(
            f"Count in tenths. What is missing? {',  '.join(shown)}",
            seq[gap],
            accept=[seq[gap].replace("/", " / "), str(start + gap)],
            hint="The top number goes up by 1 each time.",
            explain=f"Counting in tenths: {',  '.join(seq)}",
            keypad="fraction",
        )
    num = rng.randint(1, 9)
    return mc(
        f"Which picture shows {num}/10?",
        f"{num} parts shaded out of 10",
        [f"{num} parts shaded out of {num + 2}", "10 parts shaded out of 10",
         f"{10 - num} parts shaded out of 10"],
        rng,
        hint="The bottom number tells you how many equal parts there are.",
        explain=f"{num}/10 means {num} shaded parts out of 10 equal parts.",
        visual={"type": "fraction", "num": num, "den": 10, "shape": "bar"},
    )


@generator("fraction_of_amount_3")
def fraction_of_amount_3(rng: random.Random, level: int = 1) -> Question:
    den = rng.choice([2, 3, 4, 5, 6, 10])
    num = rng.randint(1, den - 1)
    total = den * rng.randint(2, 8)
    answer = total // den * num
    return txt(
        f"What is {num}/{den} of {total}?",
        answer,
        hint=f"Divide {total} by {den}, then multiply by {num}.",
        explain=f"{total} ÷ {den} = {total // den}. {total // den} × {num} = {answer}.",
        visual={"type": "share", "total": total, "groups": den, "take": num},
    )


@generator("fraction_equiv_3")
def fraction_equiv_3(rng: random.Random, level: int = 1) -> Question:
    base_num, base_den = rng.choice([(1, 2), (1, 3), (1, 4), (1, 5), (2, 3), (3, 4), (2, 5)])
    factor = rng.randint(2, 4)
    answer = base_num * factor
    return txt(
        f"Fill in the missing number:   {base_num}/{base_den} = ?/{base_den * factor}",
        answer,
        hint=f"The bottom was multiplied by {factor}, so do the same to the top.",
        explain=f"{base_num} × {factor} = {answer}, so {base_num}/{base_den} "
                f"= {answer}/{base_den * factor}.",
        visual={"type": "fraction_pair", "a": [base_num, base_den],
                "b": [answer, base_den * factor]},
    )


@generator("fraction_add_sub_3")
def fraction_add_sub_3(rng: random.Random, level: int = 1) -> Question:
    den = rng.choice([4, 5, 6, 7, 8, 10])
    if rng.random() < 0.5:
        a = rng.randint(1, den - 2)
        b = rng.randint(1, den - a - 1)
        answer = a + b
        return txt(
            f"{a}/{den} + {b}/{den} = ?",
            f"{answer}/{den}",
            accept=[str(answer), f"{answer}/{den}"],
            hint="The bottom numbers match, so just add the top numbers.",
            explain=f"{a} + {b} = {answer}, so the answer is {answer}/{den}.",
            keypad="fraction",
        )
    a = rng.randint(2, den)
    b = rng.randint(1, a - 1)
    answer = a - b
    return txt(
        f"{a}/{den} - {b}/{den} = ?",
        f"{answer}/{den}",
        accept=[str(answer), f"{answer}/{den}"],
        hint="The bottom numbers match, so just subtract the top numbers.",
        explain=f"{a} - {b} = {answer}, so the answer is {answer}/{den}.",
        keypad="fraction",
    )


@generator("fraction_compare_3")
def fraction_compare_3(rng: random.Random, level: int = 1) -> Question:
    if rng.random() < 0.5:
        d1, d2 = rng.sample([2, 3, 4, 5, 6, 8, 10], 2)
        bigger = f"1/{min(d1, d2)}"
        smaller = f"1/{max(d1, d2)}"
        want_big = rng.random() < 0.5
        answer = bigger if want_big else smaller
        return mc(
            f"Which fraction is {'bigger' if want_big else 'smaller'}: 1/{d1} or 1/{d2}?",
            answer,
            [f"1/{d1}", f"1/{d2}", "they are equal"],
            rng,
            n=3,
            hint="The more pieces you cut a cake into, the smaller each piece is.",
            explain=f"1/{min(d1, d2)} is bigger because the pieces are larger.",
            visual={"type": "fraction_pair", "a": [1, d1], "b": [1, d2]},
        )
    den = rng.choice([5, 6, 7, 8, 10])
    n1, n2 = rng.sample(range(1, den), 2)
    answer = "<" if n1 < n2 else ">"
    return mc(
        f"Which sign goes in the box?   {n1}/{den}  ☐  {n2}/{den}",
        answer,
        ["<", ">", "="],
        rng,
        n=3,
        hint="The bottom numbers are the same, so compare the top numbers.",
        explain=f"{n1}/{den} {answer} {n2}/{den}",
    )


# ===========================================================================
# YEAR 3 — Measurement
# ===========================================================================


@generator("length_units_3")
def length_units_3(rng: random.Random, level: int = 1) -> Question:
    roll = rng.random()
    if roll < 0.3:
        cm = rng.randint(2, 60)
        return txt(
            f"{cm} cm = ? mm",
            cm * 10,
            hint="There are 10 mm in every 1 cm.",
            explain=f"{cm} × 10 = {cm * 10} mm",
        )
    if roll < 0.55:
        m = rng.randint(2, 9)
        extra = rng.choice([0, 20, 45, 50, 75])
        total = m * 100 + extra
        return txt(
            f"{total} cm = ? m and ? cm  →  how many whole metres?",
            m,
            hint="There are 100 cm in 1 m.",
            explain=f"{total} cm = {m} m and {extra} cm.",
        )
    a = rng.randint(20, 90)
    b = rng.randint(10, 80)
    return txt(
        f"A rope is {a} cm long. Another is {b} cm long. What is the total length in cm?",
        a + b,
        hint="Add the two lengths.",
        explain=f"{a} + {b} = {a + b} cm",
    )


@generator("mass_capacity_3")
def mass_capacity_3(rng: random.Random, level: int = 1) -> Question:
    roll = rng.random()
    if roll < 0.3:
        kg = rng.randint(2, 9)
        return txt(
            f"{kg} kg = ? g",
            kg * 1000,
            hint="There are 1000 g in 1 kg.",
            explain=f"{kg} × 1000 = {kg * 1000} g",
        )
    if roll < 0.6:
        litres = rng.randint(1, 5)
        ml = rng.choice([0, 250, 500, 750])
        total = litres * 1000 + ml
        return txt(
            f"{total} ml = ? litres and ? ml  →  how many whole litres?",
            litres,
            hint="There are 1000 ml in 1 litre.",
            explain=f"{total} ml = {litres} litres and {ml} ml.",
        )
    a, b = rng.choice([(250, 400), (350, 500), (450, 250), (600, 150)])
    return txt(
        f"A jug holds {a} ml of juice. You pour in {b} ml more. How many ml now?",
        a + b,
        hint="Add the two amounts.",
        explain=f"{a} + {b} = {a + b} ml",
    )


@generator("money_3")
def money_3(rng: random.Random, level: int = 1) -> Question:
    roll = rng.random()
    if roll < 0.4:
        a = rng.randrange(105, 480, 5)
        b = rng.randrange(105, 480, 5)
        return txt(
            f"{money_str(a)} + {money_str(b)} = ?",
            money_str(a + b),
            accept=[money_str(a + b), str(a + b)],
            hint="Add the pounds, then add the pence.",
            explain=f"{money_str(a)} + {money_str(b)} = {money_str(a + b)}",
            keypad="money",
        )
    paid = rng.choice([500, 1000, 2000])
    cost = rng.randrange(105, paid - 50, 5)
    answer = paid - cost
    name = rng.choice(NAMES)
    return txt(
        f"{name} has {money_str(paid)} and spends {money_str(cost)}. How much is left?",
        money_str(answer),
        accept=[money_str(answer), str(answer)],
        hint=f"Count on from {money_str(cost)} to {money_str(paid)}.",
        explain=f"{money_str(paid)} - {money_str(cost)} = {money_str(answer)}",
        keypad="money",
    )


@generator("perimeter_3")
def perimeter_3(rng: random.Random, level: int = 1) -> Question:
    w, h = rng.randint(2, 12), rng.randint(2, 12)
    if rng.random() < 0.25:
        side = rng.randint(2, 12)
        return txt(
            f"A square has sides of {side} cm. What is its perimeter?",
            side * 4,
            hint="Perimeter is the distance all the way around. A square has 4 equal sides.",
            explain=f"{side} × 4 = {side * 4} cm",
            visual={"type": "rect", "w": side, "h": side, "unit": "cm"},
        )
    return txt(
        "What is the perimeter of this rectangle?",
        2 * (w + h),
        hint="Add up all four sides.",
        explain=f"{w} + {h} + {w} + {h} = {2 * (w + h)} cm",
        visual={"type": "rect", "w": w, "h": h, "unit": "cm"},
        prompt_sub="Answer in centimetres",
    )


@generator("time_minute_3")
def time_minute_3(rng: random.Random, level: int = 1) -> Question:
    hour = rng.randint(1, 12)
    minute = rng.choice([m for m in range(1, 60) if m % 5 != 0] + [5, 10, 20, 25, 35, 40, 50, 55])
    answer = time_words(hour, minute)
    if rng.random() < 0.5:
        digital = f"{hour}:{minute:02d}"
        return txt(
            "Write this time in digital form, like 4:35",
            digital,
            accept=[digital, digital.replace(":", ".")],
            hint="The short hand gives the hour. Count the minutes round from the top.",
            explain=f"The clock shows {answer}, which is {digital}.",
            visual=clock(hour, minute),
            keypad="time",
        )
    others = set()
    guard = 0
    while len(others) < 4 and guard < 80:
        guard += 1
        m2 = rng.randint(1, 59)
        h2 = rng.choice([hour, hour % 12 + 1])
        w = time_words(h2, m2)
        if w != answer:
            others.add(w)
    return mc(
        "What time does the clock show?",
        answer,
        list(others),
        rng,
        hint="Count round the clock in 5s, then count on the extra minutes.",
        explain=f"The clock shows {answer}.",
        visual=clock(hour, minute),
    )


@generator("time_units_3")
def time_units_3(rng: random.Random, level: int = 1) -> Question:
    facts = [
        ("How many seconds are there in a minute?", 60, [30, 24, 100, 12]),
        ("How many minutes are there in an hour?", 60, [30, 24, 100, 12]),
        ("How many hours are there in a day?", 24, [12, 60, 7, 30]),
        ("How many days are there in a week?", 7, [5, 12, 30, 24]),
        ("How many months are there in a year?", 12, [7, 24, 52, 30]),
        ("How many days are there in a normal year?", 365, [366, 360, 300, 52]),
        ("How many days are there in a leap year?", 366, [365, 367, 360, 400]),
        ("How many minutes are there in half an hour?", 30, [15, 45, 60, 20]),
        ("How many days are there in April?", 30, [31, 28, 29, 25]),
        ("How many days are there in December?", 31, [30, 28, 29, 25]),
        ("How many days are there in February in a normal year?", 28, [29, 30, 31, 27]),
        ("How many weeks are there in a year?", 52, [12, 50, 60, 365]),
    ]
    prompt, answer, wrong = rng.choice(facts)
    return mc(
        prompt,
        answer,
        wrong,
        rng,
        hint="Try to remember this one — it is a fact worth knowing by heart.",
        explain=f"{prompt} {answer}.",
    )


@generator("time_duration_3")
def time_duration_3(rng: random.Random, level: int = 1) -> Question:
    hour = rng.randint(1, 10)
    minute = rng.choice([0, 5, 10, 15, 20, 25, 30, 40, 45])
    add = rng.choice([15, 20, 25, 30, 40, 45, 50])
    total = minute + add
    end_hour = hour + total // 60
    end_min = total % 60
    if rng.random() < 0.6:
        return txt(
            f"A film starts at {hour}:{minute:02d} and lasts {add} minutes. "
            f"What time does it finish?",
            f"{end_hour}:{end_min:02d}",
            accept=[f"{end_hour}:{end_min:02d}", f"{end_hour}.{end_min:02d}"],
            hint="Count on the minutes. Remember 60 minutes makes a new hour.",
            explain=f"{hour}:{minute:02d} + {add} minutes = {end_hour}:{end_min:02d}",
            keypad="time",
        )
    return txt(
        f"Playtime starts at {hour}:{minute:02d} and ends at {end_hour}:{end_min:02d}. "
        f"How many minutes long is it?",
        add,
        hint="Count on from the start time to the end time.",
        explain=f"From {hour}:{minute:02d} to {end_hour}:{end_min:02d} is {add} minutes.",
    )


@generator("roman_3")
def roman_3(rng: random.Random, level: int = 1) -> Question:
    n = rng.randint(1, 12)
    if rng.random() < 0.5:
        return mc(
            f"What is {n} in Roman numerals?",
            ROMAN[n],
            [ROMAN[m] for m in rng.sample([x for x in range(1, 13) if x != n], 4)],
            rng,
            hint="I is 1, V is 5, X is 10.",
            explain=f"{n} is written as {ROMAN[n]}.",
        )
    return txt(
        f"What number is the Roman numeral {ROMAN[n]}?",
        n,
        hint="I is 1, V is 5, X is 10. A smaller letter before a bigger one means subtract.",
        explain=f"{ROMAN[n]} is {n}.",
        visual={"type": "roman_clock"},
    )


# ===========================================================================
# YEAR 3 — Geometry and statistics
# ===========================================================================


@generator("angles_3")
def angles_3(rng: random.Random, level: int = 1) -> Question:
    roll = rng.random()
    if roll < 0.4:
        degrees = rng.choice([30, 45, 60, 90, 120, 135, 150])
        if degrees == 90:
            answer = "a right angle"
        elif degrees < 90:
            answer = "less than a right angle"
        else:
            answer = "greater than a right angle"
        return mc(
            "Is this angle a right angle, less than a right angle, or greater?",
            answer,
            ["a right angle", "less than a right angle", "greater than a right angle"],
            rng,
            n=3,
            hint="A right angle looks like the corner of a book.",
            explain=f"This angle is {answer}.",
            visual={"type": "angle", "degrees": degrees},
        )
    if roll < 0.7:
        turns = rng.choice([("a quarter turn", 1), ("a half turn", 2),
                            ("three quarters of a turn", 3), ("a full turn", 4)])
        label, answer = turns
        return mc(
            f"How many right angles are there in {label}?",
            answer,
            [1, 2, 3, 4],
            rng,
            n=4,
            hint="A quarter turn is one right angle.",
            explain=f"{label.capitalize()} is {answer} right angle{'s' if answer > 1 else ''}.",
        )
    shapes = [("square", 4), ("rectangle", 4), ("right-angled triangle", 1)]
    name, answer = rng.choice(shapes)
    return mc(
        f"How many right angles does a {name} have?",
        answer,
        [0, 1, 2, 3, 4],
        rng,
        hint="Check each corner with the corner of a piece of paper.",
        explain=f"A {name} has {answer} right angle{'s' if answer > 1 else ''}.",
    )


@generator("lines_3")
def lines_3(rng: random.Random, level: int = 1) -> Question:
    kind = rng.choice(["horizontal", "vertical", "parallel", "perpendicular"])
    explains = {
        "horizontal": "Horizontal lines go across, like the horizon.",
        "vertical": "Vertical lines go straight up and down.",
        "parallel": "Parallel lines stay the same distance apart and never meet.",
        "perpendicular": "Perpendicular lines cross at a right angle.",
    }
    if rng.random() < 0.5:
        return mc(
            "What kind of lines are shown in the picture?",
            kind,
            ["horizontal", "vertical", "parallel", "perpendicular"],
            rng,
            n=4,
            hint="Look at the direction of the lines and whether they meet.",
            explain=explains[kind],
            visual={"type": "lines", "kind": kind},
        )
    return mc(
        f"Which words describe lines that {explains[kind].split(' ', 2)[2].rstrip('.')}?",
        kind,
        ["horizontal", "vertical", "parallel", "perpendicular"],
        rng,
        n=4,
        hint="Say each word out loud and picture it.",
        explain=explains[kind],
    )


@generator("shapes_3")
def shapes_3(rng: random.Random, level: int = 1) -> Question:
    roll = rng.random()
    if roll < 0.45:
        name = rng.choice(list(SHAPES_2D))
        return mc(
            "What is this shape called?",
            name,
            [n for n in SHAPES_2D if n != name],
            rng,
            hint="Count the sides, even if the shape is turned around.",
            explain=f"This is a {name}.",
            visual={"type": "shape2d", "name": name, "rotate": rng.choice([0, 15, 30, 45])},
        )
    if roll < 0.75:
        quads = ["square", "rectangle", "rhombus", "trapezium", "parallelogram"]
        not_quads = ["triangle", "pentagon", "hexagon", "circle", "octagon"]
        if rng.random() < 0.5:
            answer = rng.choice(quads)
            return mc(
                "Which of these is a quadrilateral?",
                answer,
                rng.sample(not_quads, 3),
                rng,
                hint="A quadrilateral has exactly 4 straight sides.",
                explain=f"A {answer} has 4 sides, so it is a quadrilateral.",
            )
        answer = rng.choice(not_quads)
        return mc(
            "Which of these is NOT a quadrilateral?",
            answer,
            rng.sample(quads, 3),
            rng,
            hint="A quadrilateral has exactly 4 straight sides.",
            explain=f"A {answer} does not have exactly 4 straight sides.",
        )
    facts = [("cube", "edges", 12), ("cuboid", "faces", 6), ("cube", "vertices", 8),
             ("triangular prism", "faces", 5), ("square-based pyramid", "edges", 8)]
    name, which, answer = rng.choice(facts)
    return mc(
        f"How many {which} does a {name} have?",
        answer,
        [answer + 1, answer - 1, answer + 2, answer - 2],
        rng,
        hint="Picture the shape in your head and count slowly.",
        explain=f"A {name} has {answer} {which}.",
    )


@generator("bar_chart_3")
def bar_chart_3(rng: random.Random, level: int = 1) -> Question:
    themes = [
        ("Books read this month", ["Ava", "Ben", "Cara", "Dev"]),
        ("Goals scored", ["Reds", "Blues", "Greens", "Golds"]),
        ("Minutes of reading", ["Mon", "Tue", "Wed", "Thu"]),
        ("Trees planted", ["Oak", "Ash", "Elm", "Pine"]),
    ]
    title, labels = rng.choice(themes)
    scale = rng.choice([1, 2, 5])
    values = [rng.randint(1, 10) * scale for _ in labels]
    while len(set(values)) < 3:
        values = [rng.randint(1, 10) * scale for _ in labels]
    visual = {"type": "bar_chart", "labels": labels, "values": values,
              "title": title, "step": scale}
    roll = rng.random()
    if roll < 0.3:
        idx = rng.randrange(len(labels))
        return txt(
            f"Look at the bar chart. What is the value for {labels[idx]}?",
            values[idx],
            hint="Follow the top of the bar across to the numbers on the side.",
            explain=f"{labels[idx]} is {values[idx]}.",
            visual=visual,
        )
    if roll < 0.55:
        top = labels[values.index(max(values))]
        return mc(
            "Which bar is the tallest?",
            top,
            [x for x in labels if x != top],
            rng,
            hint="Look for the bar that reaches highest.",
            explain=f"{top} is the tallest with {max(values)}.",
            visual=visual,
        )
    if roll < 0.8:
        i, j = rng.sample(range(len(labels)), 2)
        if values[i] < values[j]:
            i, j = j, i
        return txt(
            f"How many more for {labels[i]} than {labels[j]}?",
            values[i] - values[j],
            hint="Read both bars, then subtract.",
            explain=f"{values[i]} - {values[j]} = {values[i] - values[j]}",
            visual=visual,
        )
    return txt(
        "What is the total of all four bars?",
        sum(values),
        hint="Read each bar, then add them all together.",
        explain=" + ".join(str(v) for v in values) + f" = {sum(values)}",
        visual=visual,
    )


# ===========================================================================
# YEARS 4–6 — starter maths coverage
# ===========================================================================


@generator("place_value_10000")
def place_value_10000(rng: random.Random, level: int = 1) -> Question:
    n = rng.randint(1_000, 9_999)
    digits = str(n)
    places = [
        ("thousands", int(digits[-4]) * 1_000),
        ("hundreds", int(digits[-3]) * 100),
        ("tens", int(digits[-2]) * 10),
        ("ones", int(digits[-1])),
    ]
    place, value = rng.choice(places)
    digit = value // {"thousands": 1_000, "hundreds": 100, "tens": 10, "ones": 1}[place]
    return mc(
        f"What is the value of the {place} digit in {n}?",
        value,
        [digit, value + 10, value + 100, n],
        rng,
        hint="The position of a digit tells you its value.",
        explain=f"The {place} digit is {digit}, so it is worth {value}.",
    )


@generator("add_sub_4digit")
def add_sub_4digit(rng: random.Random, level: int = 1) -> Question:
    if rng.random() < 0.5:
        a = rng.randint(1_000, 7_999)
        b = rng.randint(100, 9_999 - a)
        answer = a + b
        op = "+"
    else:
        a = rng.randint(2_000, 9_999)
        b = rng.randint(100, a - 1)
        answer = a - b
        op = "−"
    return txt(
        f"{a} {op} {b} = ?",
        answer,
        hint="Line up the place values carefully.",
        explain=f"{a} {op} {b} = {answer}",
    )


@generator("times_tables_4")
def times_tables_4(rng: random.Random, level: int = 1) -> Question:
    table = rng.choice([6, 7, 9])
    factor = rng.randint(2, 12)
    answer = table * factor
    return mc(
        f"What is {table} × {factor}?",
        answer,
        [answer - table, answer + table, table + factor],
        rng,
        hint=f"Recall your {table} times table.",
        explain=f"{table} × {factor} = {answer}.",
    )


@generator("place_value_million")
def place_value_million(rng: random.Random, level: int = 1) -> Question:
    n = rng.randint(10_000, 999_999)
    digits = str(n).zfill(6)
    places = [
        ("hundred-thousands", int(digits[0]) * 100_000),
        ("ten-thousands", int(digits[1]) * 10_000),
        ("thousands", int(digits[2]) * 1_000),
        ("hundreds", int(digits[3]) * 100),
        ("tens", int(digits[4]) * 10),
        ("ones", int(digits[5])),
    ]
    place, value = rng.choice(places)
    return mc(
        f"What is the value of the {place} digit in {n}?",
        value,
        [value + 10, value + 100, value + 1_000, int(digits[-1])],
        rng,
        hint="Look at the place-value column, not just the digit.",
        explain=f"The {place} digit is worth {value}.",
    )


@generator("multiply_5")
def multiply_5(rng: random.Random, level: int = 1) -> Question:
    a = rng.randint(12, 999)
    b = rng.randint(2, 12)
    answer = a * b
    return txt(
        f"{a} × {b} = ?",
        answer,
        hint="Partition the larger number or use a written method.",
        explain=f"{a} × {b} = {answer}",
    )


@generator("fraction_decimal_5")
def fraction_decimal_5(rng: random.Random, level: int = 1) -> Question:
    pairs = [
        ("1/2", "0.5", ["0.2", "0.25", "0.75"]),
        ("1/4", "0.25", ["0.4", "0.2", "0.75"]),
        ("3/4", "0.75", ["0.3", "0.25", "0.5"]),
        ("1/5", "0.2", ["0.1", "0.5", "0.25"]),
        ("3/5", "0.6", ["0.3", "0.35", "0.75"]),
    ]
    fraction, decimal, distractors = rng.choice(pairs)
    return mc(
        f"Which decimal is equal to {fraction}?",
        decimal,
        distractors,
        rng,
        hint="Convert the fraction into tenths or hundredths.",
        explain=f"{fraction} is equal to {decimal}.",
    )


@generator("negative_numbers_6")
def negative_numbers_6(rng: random.Random, level: int = 1) -> Question:
    start = rng.randint(-15, 15)
    change = rng.randint(-8, 8) or 3
    answer = start + change
    sign = "+" if change >= 0 else "−"
    amount = abs(change)
    return txt(
        f"Start at {start}. Move {amount} {('forward' if change >= 0 else 'back')}. Where do you land?",
        answer,
        hint="Count along the number line, crossing zero if needed.",
        explain=f"{start} {sign} {amount} = {answer}",
    )


@generator("ratio_percent_6")
def ratio_percent_6(rng: random.Random, level: int = 1) -> Question:
    total = rng.choice([40, 60, 80, 100, 120, 200])
    percent = rng.choice([10, 20, 25, 50])
    answer = total * percent // 100
    return txt(
        f"What is {percent}% of {total}?",
        answer,
        hint="Find 10% first, then build the percentage you need.",
        explain=f"{percent}% of {total} = {answer}",
    )


@generator("algebra_6")
def algebra_6(rng: random.Random, level: int = 1) -> Question:
    coefficient = rng.randint(2, 9)
    x = rng.randint(2, 12)
    constant = rng.randint(1, 15)
    total = coefficient * x + constant
    return txt(
        f"Solve: {coefficient}x + {constant} = {total}",
        x,
        hint="Subtract the constant, then divide by the coefficient.",
        explain=f"{total} − {constant} = {coefficient}x, so x = {x}.",
    )


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def make_question(generator_name: str, rng: random.Random, level: int = 1) -> Question:
    """Generate one question, raising a clear error for an unknown generator."""
    fn = GENERATORS.get(generator_name)
    if fn is None:
        raise KeyError(f"No maths generator named {generator_name!r}")
    return fn(rng, level)
