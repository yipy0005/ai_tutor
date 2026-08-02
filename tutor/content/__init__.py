"""Content layer: turns a skill id into a question, and marks the answer.

Two kinds of skill:

* ``generated`` maths skills call a function in :mod:`generators`, so a child
  never runs out of practice.
* ``bank`` English and Science skills draw from the hand-written JSON files in
  ``content/banks``.

Marking lives here too, so the browser is never trusted with an answer.
"""

from __future__ import annotations

import json
import random
import re
from functools import lru_cache
from pathlib import Path

from . import generators
from .curriculum import (
    ALL_SKILLS,
    SKILLS_BY_ID,
    SUBJECT_ORDER,
    SUBJECTS,
    YEAR_BLURBS,
    YEAR_LABELS,
    Skill,
    Subject,
    get_skill,
    skill_name,
    skills_for,
    subject_counts,
    topic_tree,
    topics_for,
)

__all__ = [
    "ALL_SKILLS",
    "SKILLS_BY_ID",
    "SUBJECTS",
    "SUBJECT_ORDER",
    "YEAR_BLURBS",
    "YEAR_LABELS",
    "Skill",
    "Subject",
    "bank_size",
    "check_answer",
    "draw_question",
    "get_passage",
    "get_skill",
    "skill_name",
    "skills_for",
    "subject_counts",
    "topic_tree",
    "topics_for",
    "validate_content",
]

BANKS_DIR = Path(__file__).parent / "banks"

BANK_FILES = [
    "english_y1.json",
    "english_y2.json",
    "english_y3.json",
    "science_y1.json",
    "science_y2.json",
    "science_y3.json",
]
READING_FILE = "reading.json"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    banks: dict[str, list[dict]] = {}
    passages: dict[str, dict] = {}

    for filename in BANK_FILES:
        path = BANKS_DIR / filename
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for skill_id, items in data.items():
            if skill_id.startswith("_"):
                continue
            banks.setdefault(skill_id, []).extend(items)

    reading_path = BANKS_DIR / READING_FILE
    if reading_path.exists():
        data = json.loads(reading_path.read_text(encoding="utf-8"))
        passages.update(data.get("passages", {}))
        for skill_id, items in data.get("questions", {}).items():
            banks.setdefault(skill_id, []).extend(items)

    return banks, passages


def _banks() -> dict[str, list[dict]]:
    return _load()[0]


def get_passage(passage_id: str) -> dict | None:
    return _load()[1].get(passage_id)


def bank_size(skill_id: str) -> int:
    return len(_banks().get(skill_id, []))


# ---------------------------------------------------------------------------
# Drawing a question
# ---------------------------------------------------------------------------


def draw_question(
    skill_id: str,
    rng: random.Random | None = None,
    level: int = 1,
    avoid: set[str] | None = None,
) -> dict:
    """Return one question for ``skill_id``.

    ``avoid`` holds item keys already used in this quest so a child does not
    see the same bank question twice in one sitting.
    """
    rng = rng or random.Random()
    avoid = avoid or set()
    skill = SKILLS_BY_ID.get(skill_id)
    if skill is None:
        raise KeyError(f"Unknown skill id {skill_id!r}")

    if skill.source == "generated":
        question = generators.make_question(skill.generator or "", rng, level)
        question["item_key"] = f"{skill_id}#gen"
    else:
        items = _banks().get(skill_id, [])
        if not items:
            raise LookupError(f"No bank questions found for skill {skill_id!r}")
        pool = [
            (i, item)
            for i, item in enumerate(items)
            if f"{skill_id}#{i}" not in avoid
        ]
        if not pool:  # everything already used — allow repeats rather than fail
            pool = list(enumerate(items))
        index, item = rng.choice(pool)
        question = dict(item)
        question["item_key"] = f"{skill_id}#{index}"
        if question.get("kind") == "choice":
            choices = list(question.get("choices", []))
            rng.shuffle(choices)
            question["choices"] = choices

    passage_id = question.get("passage")
    if passage_id:
        passage = get_passage(passage_id)
        if passage:
            question["passage_title"] = passage.get("title", "")
            question["passage_text"] = passage.get("text", "")

    question.setdefault("kind", "choice")
    question.setdefault("hint", "")
    question.setdefault("explain", "")
    question["skill_id"] = skill_id
    question["skill_name"] = skill.name
    question["subject"] = skill.subject
    question["year"] = skill.year
    return question


def split_question(question: dict) -> tuple[dict, dict]:
    """Split a drawn question into (payload for the browser, solution)."""
    solution = {
        "answer": str(question.get("answer", "")),
        "accept": [str(a) for a in question.get("accept", [])],
        "explain": question.get("explain", ""),
    }
    payload = {
        k: v
        for k, v in question.items()
        if k not in {"answer", "accept", "explain", "passage"}
    }
    return payload, solution


# ---------------------------------------------------------------------------
# Marking
# ---------------------------------------------------------------------------

_MONEY_RE = re.compile(r"^£?\s*(\d+)(?:[.,](\d{1,2}))?\s*(p|pence|pounds?)?$", re.I)


def _normalise(value: str) -> str:
    text = str(value).strip().lower()
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s*/\s*", "/", text)  # 3 / 7 -> 3/7
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip(".")
    text = text.replace(",", "")
    return text


def _to_pence(value: str) -> int | None:
    """Read a money amount as a whole number of pence, or None."""
    text = str(value).strip().lower().replace(",", "").replace(" ", "")
    if not text:
        return None
    match = _MONEY_RE.match(text)
    if not match:
        return None
    whole, frac, suffix = match.group(1), match.group(2), (match.group(3) or "")
    has_pound = text.startswith("£") or suffix.startswith("pound")
    is_pence = suffix.startswith("p") and not suffix.startswith("pound")

    if has_pound:
        pence = int(whole) * 100 + int((frac or "0").ljust(2, "0"))
    elif is_pence and frac is None:
        pence = int(whole)
    elif frac is not None:
        # A bare "3.50" in a money question means £3.50.
        pence = int(whole) * 100 + int(frac.ljust(2, "0"))
    else:
        pence = int(whole)
    return pence


def _looks_like_money(value: str) -> bool:
    text = str(value).strip().lower()
    return "£" in text or text.endswith("p") or "." in text


def check_answer(given: str, solution: dict, kind: str = "choice") -> bool:
    """Mark one answer. Forgiving about formatting, strict about the maths."""
    if given is None:
        return False
    accepted = [solution.get("answer", "")] + list(solution.get("accept", []))
    accepted = [a for a in accepted if str(a) != ""]
    if not accepted:
        return False

    given_norm = _normalise(given)
    if not given_norm:
        return False

    for candidate in accepted:
        if given_norm == _normalise(candidate):
            return True

    if kind == "choice":
        return False

    # Money: £3.50, 3.50 and 350p all mean the same thing.
    if any(_looks_like_money(a) for a in accepted) or _looks_like_money(given):
        given_pence = _to_pence(given)
        if given_pence is not None:
            for candidate in accepted:
                cand_pence = _to_pence(candidate)
                if cand_pence is not None and cand_pence == given_pence:
                    return True

    # Times: 4:35, 4.35 and 04:35 all mean the same thing.
    given_time = _normalise(given).replace(".", ":").lstrip("0")
    for candidate in accepted:
        cand_time = _normalise(candidate).replace(".", ":").lstrip("0")
        if ":" in cand_time and given_time == cand_time:
            return True

    return False


# ---------------------------------------------------------------------------
# Validation (used by `pixi run content-check`)
# ---------------------------------------------------------------------------


def validate_content(samples: int = 40) -> list[str]:
    """Check every skill can produce sound questions. Returns a list of problems."""
    problems: list[str] = []
    banks = _banks()

    for skill in ALL_SKILLS:
        if skill.source == "generated":
            if skill.generator not in generators.GENERATORS:
                problems.append(f"{skill.id}: missing generator {skill.generator!r}")
                continue
        elif not banks.get(skill.id):
            problems.append(f"{skill.id}: no questions in any bank file")
            continue

        for i in range(samples if skill.source == "generated" else bank_size(skill.id)):
            rng = random.Random(i * 31 + 7)
            try:
                question = draw_question(skill.id, rng, level=i % 3)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{skill.id}: raised {type(exc).__name__}: {exc}")
                break

            prompt = question.get("prompt", "")
            answer = str(question.get("answer", ""))
            if not prompt:
                problems.append(f"{skill.id}: empty prompt")
                break
            if answer == "":
                problems.append(f"{skill.id}: empty answer for {prompt!r}")
                break

            if question.get("kind") == "choice":
                choices = question.get("choices") or []
                if len(choices) < 3:
                    problems.append(f"{skill.id}: only {len(choices)} choices for {prompt!r}")
                    break
                if len(set(choices)) != len(choices):
                    problems.append(f"{skill.id}: duplicate choices for {prompt!r}")
                    break
                if answer not in choices:
                    problems.append(f"{skill.id}: answer not among choices for {prompt!r}")
                    break

            _payload, solution = split_question(question)
            if not check_answer(answer, solution, question.get("kind", "choice")):
                problems.append(f"{skill.id}: own answer fails marking for {prompt!r}")
                break

    for skill_id in banks:
        if skill_id not in SKILLS_BY_ID:
            problems.append(f"bank has questions for unknown skill {skill_id!r}")

    return problems


def content_summary() -> dict:
    banks = _banks()
    generated = [s for s in ALL_SKILLS if s.source == "generated"]
    banked = [s for s in ALL_SKILLS if s.source == "bank"]
    return {
        "skills": len(ALL_SKILLS),
        "generated_skills": len(generated),
        "bank_skills": len(banked),
        "generators": len(generators.GENERATORS),
        "bank_questions": sum(len(v) for v in banks.values()),
        "passages": len(_load()[1]),
    }
