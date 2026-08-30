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
import math
import random
import re
from functools import lru_cache
from pathlib import Path

from . import generators
from .curriculum import (
    ALL_CONTENT_SKILLS,
    ALL_SKILLS,
    GCSE_MATHS_SKILLS,
    GCSE_TIER_LABELS,
    GCSE_TIERS,
    PATHWAY_BLURBS,
    PATHWAY_LABELS,
    PATHWAY_SUBJECT_ORDER,
    PRIMARY_YEARS,
    SKILLS_BY_ID,
    SUBJECT_ORDER,
    SUBJECTS,
    YEAR_BLURBS,
    YEAR_LABELS,
    Skill,
    Subject,
    gcse_skills_for,
    get_skill,
    skill_name,
    skills_for,
    subject_counts,
    topic_tree,
    topics_for,
)
from .exam import GCSE_BOARD_OPTIONS, GCSE_BOARD_PROFILES, apply_exam_style

__all__ = [
    "ALL_CONTENT_SKILLS",
    "ALL_SKILLS",
    "GCSE_MATHS_SKILLS",
    "GCSE_BOARD_OPTIONS",
    "GCSE_BOARD_PROFILES",
    "GCSE_TIER_LABELS",
    "GCSE_TIERS",
    "PATHWAY_BLURBS",
    "PATHWAY_LABELS",
    "PATHWAY_SUBJECT_ORDER",
    "PRIMARY_YEARS",
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
    "gcse_skills_for",
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
    "english_y4.json",
    "english_y5.json",
    "english_y6.json",
    "science_y1.json",
    "science_y2.json",
    "science_y3.json",
    "science_y4.json",
    "science_y5.json",
    "science_y6.json",
    "gcse_maths.json",
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


_GREAT_VARIANT_LEVELS = {
    0: {"given": "explicit", "required": "explicit"},
    1: {"given": "explicit", "required": "implicit"},
    2: {"given": "implicit", "required": "implicit"},
}
_GREAT_VARIANTS_KEY = "great_variants"
_GREAT_FRAMEWORK_MARKER_RE = re.compile(
    r"(?:\b(?:given|required)\s*:|(?:^|\s)[gr]\s*[—–-]\s*(?:given|required)\s*:)",
    re.IGNORECASE,
)


def _variant_level(level: int) -> int:
    try:
        return max(0, min(2, int(level)))
    except (TypeError, ValueError):
        return 1


def _natural_variant_text(value: object) -> str | None:
    """Return authored wording only when it is usable and not framework text."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or _GREAT_FRAMEWORK_MARKER_RE.search(text):
        return None
    return text


def _apply_authored_variant(question: dict, variant_level: int) -> None:
    """Apply an optional, question-authored natural wording variant.

    The content author owns the context, so this deliberately does not try to
    infer or invent Given/Required wording from an arbitrary prompt. A variant
    may be a prompt string or a mapping with ``prompt`` and optional
    ``prompt_sub``. The authoring field is consumed before the question reaches
    the learner payload.
    """
    variants = question.pop(_GREAT_VARIANTS_KEY, None)
    if not isinstance(variants, dict):
        return

    variant = variants.get(variant_level, variants.get(str(variant_level)))
    prompt_sub: object = None
    if isinstance(variant, dict):
        prompt = variant.get("prompt")
        prompt_sub = variant.get("prompt_sub")
    else:
        prompt = variant

    natural_prompt = _natural_variant_text(prompt)
    if natural_prompt is None:
        return
    question["prompt"] = natural_prompt

    if isinstance(variant, dict) and "prompt_sub" in variant:
        natural_sub = _natural_variant_text(prompt_sub)
        if natural_sub is not None:
            question["prompt_sub"] = natural_sub


def _apply_great_variant(question: dict, level: int) -> dict:
    """Attach G/R visibility metadata without adding generic learner text."""
    variant_level = _variant_level(level)
    question["great_visibility"] = {
        "level": variant_level,
        **_GREAT_VARIANT_LEVELS[variant_level],
    }
    _apply_authored_variant(question, variant_level)
    return question


def draw_question(
    skill_id: str,
    rng: random.Random | None = None,
    level: int = 1,
    avoid: set[str] | None = None,
    tier: str | None = None,
    board: str | None = None,
) -> dict:
    """Return one question for ``skill_id``.

    ``level`` is the three-step GREAT visibility scale: level 0 makes both
    parts explicit in the authored context, level 1 keeps the required step
    less explicit, and level 2 leaves both implicit. Wording is never wrapped
    in framework labels. A question may provide a ``great_variants`` mapping
    for natural, authored prompts; otherwise its existing prompt is retained.
    ``avoid`` holds item keys already used in this quest so a child does not
    see the same bank question twice in one sitting.
    """
    rng = rng or random.Random()
    avoid = avoid or set()
    skill = SKILLS_BY_ID.get(skill_id)
    if skill is None:
        raise KeyError(f"Unknown skill id {skill_id!r}")
    if skill.is_gcse and not skill.eligible_for_tier(tier):
        raise PermissionError(
            f"Skill {skill_id!r} is not available for GCSE tier {tier!r}"
        )

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
    if skill.is_gcse:
        question["year_label"] = skill.year_label
        question["pathway"] = skill.pathway
        question["pathway_label"] = skill.pathway_label
        if tier in GCSE_TIER_LABELS:
            question["tier"] = GCSE_TIER_LABELS[tier]
        apply_exam_style(
            question,
            board=board,
            tier=tier,
            topic=skill.topic,
            rng=rng,
            level=level,
        )
    _apply_great_variant(question, level)
    return question


def split_question(question: dict) -> tuple[dict, dict]:
    """Split a drawn question into safe browser payload and private solution."""
    kind = question.get("kind", "choice")
    solution = {
        "answer": str(question.get("answer", "")),
        "accept": [str(a) for a in question.get("accept", [])],
        "explain": question.get("explain", ""),
        # Optional content-specific evidence guidance stays server-side. The
        # first diagnostic pilot uses the generic parent-review rubric; future
        # question authors can add stage-specific evidence here.
        "great_rubric": question.get(
            "great_rubric", {"version": 1, "mode": "parent_review"}
        ),
        "manual": kind in {"free_text", "handwriting", "audio", "evidence"},
        "interactive": kind in {"coordinate_points", "transformation_polygon"},
    }
    if kind in {"free_text", "handwriting", "audio", "evidence"}:
        solution["assessment"] = question.get("assessment", {})
    if kind in {"coordinate_points", "transformation_polygon"}:
        solution["response_spec"] = question.get("response_spec", {})
        solution["response_answer"] = question.get("response_answer", {})
    if question.get("mark_scheme"):
        solution["mark_scheme"] = question["mark_scheme"]
    payload = {
        k: v
        for k, v in question.items()
        if k not in {
            "answer",
            "accept",
            "explain",
            "passage",
            "great_rubric",
            "assessment",
            "mark_scheme",
            "response_answer",
            "great_variants",
        }
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


def _interactive_point_equal(left: object, right: object) -> bool:
    if not isinstance(left, (list, tuple)) or not isinstance(right, (list, tuple)):
        return False
    if len(left) != 2 or len(right) != 2:
        return False
    if not _finite_number(left[0]) or not _finite_number(left[1]):
        return False
    if not _finite_number(right[0]) or not _finite_number(right[1]):
        return False
    return (
        abs(float(left[0]) - float(right[0])) <= 1e-6
        and abs(float(left[1]) - float(right[1])) <= 1e-6
    )


def _interactive_sequence_equal(left: list, right: list) -> bool:
    return len(left) == len(right) and all(
        _interactive_point_equal(a, b) for a, b in zip(left, right, strict=True)
    )


def _interactive_answer_matches(given: object, solution: dict, kind: str) -> bool:
    if not isinstance(given, dict) or given.get("type") != kind:
        return False
    expected = solution.get("response_answer")
    if not isinstance(expected, dict) or expected.get("type") != kind:
        return False
    points = given.get("points")
    target = expected.get("points")
    if not isinstance(points, list) or not isinstance(target, list):
        return False
    if kind == "coordinate_points":
        return _interactive_sequence_equal(points, target)
    if len(points) != len(target):
        return False
    order = (solution.get("response_spec") or {}).get("order", "exact")
    if order != "cyclic":
        return _interactive_sequence_equal(points, target)
    for offset in range(len(target)):
        rotated = target[offset:] + target[:offset]
        if _interactive_sequence_equal(points, rotated):
            return True
        reversed_target = list(reversed(rotated))
        if _interactive_sequence_equal(points, reversed_target):
            return True
    return False


def check_answer(given: object, solution: dict, kind: str = "choice") -> bool:
    """Mark one answer. Forgiving about formatting, strict about the maths."""
    if kind in _INTERACTIVE_KINDS:
        return _interactive_answer_matches(given, solution, kind)
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

_MANUAL_KINDS = {"free_text", "handwriting", "audio", "evidence"}
_INTERACTIVE_KINDS = {"coordinate_points", "transformation_polygon"}

_VISUAL_TYPES = {
    "dots", "blocks", "clock", "roman_clock", "shape2d", "coins", "fraction",
    "fraction_pair", "bar_chart", "pictogram", "tally", "array", "number_line",
    "rect", "angle", "lines", "triangle", "coordinate_grid", "scatter_plot",
    "histogram", "box_plot", "column", "share", "partition",
}
_VISUAL_PRIVATE_KEYS = {
    "answer", "accept", "explain", "mark_scheme", "assessment", "solution", "correct",
    "target", "expected", "response_answer",
}
_VISUAL_PALETTE = {"ocean", "berry", "leaf", "sun", "grape", "ink"}


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _visual_text(
    value: object,
    key: str,
    problems: list[str],
    maximum: int = 80,
) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        problems.append(f"visual {key} must be a non-empty string of at most {maximum} characters")


def _visual_required_number(
    visual: dict,
    key: str,
    problems: list[str],
) -> float | None:
    value = visual.get(key)
    if not _finite_number(value):
        problems.append(f"visual {key} must be a finite number")
        return None
    return float(value)


def _visual_color(value: object, key: str, problems: list[str]) -> None:
    if value is not None and value not in _VISUAL_PALETTE:
        problems.append(f"visual {key} has unsupported colour {value!r}")


def _visual_point_pair(
    value: object,
    key: str,
    problems: list[str],
    bounds: tuple[float, float, float, float] | None = None,
) -> None:
    if not isinstance(value, list) or len(value) != 2 or not all(_finite_number(v) for v in value):
        problems.append(f"visual {key} must be a pair of finite numbers")
        return
    if bounds:
        xmin, xmax, ymin, ymax = bounds
        if not xmin <= float(value[0]) <= xmax or not ymin <= float(value[1]) <= ymax:
            problems.append(f"visual {key} lies outside the coordinate grid")


def _visual_bounds(
    visual: dict,
    problems: list[str],
    *,
    require_step: bool = True,
) -> tuple[float, float, float, float] | None:
    values = {
        key: _visual_required_number(visual, key, problems)
        for key in ("x_min", "x_max", "y_min", "y_max")
    }
    if any(value is None for value in values.values()):
        return None
    xmin, xmax = values["x_min"], values["x_max"]
    ymin, ymax = values["y_min"], values["y_max"]
    assert xmin is not None and xmax is not None and ymin is not None and ymax is not None
    if xmin >= xmax or ymin >= ymax:
        problems.append("visual coordinate bounds must have increasing limits")
        return None
    if xmax - xmin > 80 or ymax - ymin > 80:
        problems.append("visual coordinate bounds are too wide")
    if require_step:
        step = _visual_required_number(visual, "grid_step", problems)
        if step is not None and (step <= 0 or (xmax - xmin) / step > 40 or (ymax - ymin) / step > 40):
            problems.append("visual grid_step must produce at most 40 grid intervals")
    return xmin, xmax, ymin, ymax


def _visual_problems(question: dict) -> list[str]:
    """Validate visual payloads without allowing private answer data."""
    visual = question.get("visual")
    if visual is None:
        return []
    if not isinstance(visual, dict):
        return ["visual must be an object"]

    problems: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if str(key).lower() in _VISUAL_PRIVATE_KEYS:
                    problems.append(f"visual contains private key {key!r}")
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)
        elif isinstance(value, float) and not math.isfinite(value):
            problems.append("visual contains a non-finite number")

    walk(visual)
    visual_type = visual.get("type")
    if visual_type not in _VISUAL_TYPES:
        problems.append(f"visual has unsupported type {visual_type!r}")
        return problems

    _visual_text(visual.get("aria_label"), "aria_label", problems)

    if visual_type == "triangle":
        mode = visual.get("mode")
        if mode not in {"right", "general"}:
            problems.append("triangle visual mode must be 'right' or 'general'")
        labels = visual.get("labels")
        if not isinstance(labels, dict) or not labels:
            problems.append("triangle visual needs labelled sides or angles")
        else:
            allowed = (
                {"base", "height", "hypotenuse", "angle"}
                if mode == "right"
                else {"base", "left", "right", "top"}
            )
            for key, value in labels.items():
                if key not in allowed:
                    problems.append(f"triangle visual has unsupported label {key!r}")
                if not isinstance(value, str) or not value.strip() or len(value) > 32:
                    problems.append(f"triangle label {key!r} must be a short string")

    elif visual_type == "coordinate_grid":
        bounds = _visual_bounds(visual, problems)
        for key in ("x_label", "y_label"):
            _visual_text(visual.get(key), key, problems, 40)
        points = visual.get("points", [])
        if not isinstance(points, list) or len(points) > 24:
            problems.append("coordinate_grid points must be a list of at most 24")
        elif isinstance(points, list):
            for index, point in enumerate(points):
                if not isinstance(point, dict):
                    problems.append(f"coordinate_grid point {index} must be an object")
                    continue
                x = point.get("x")
                y = point.get("y")
                if not _finite_number(x) or not _finite_number(y):
                    problems.append(f"coordinate_grid point {index} needs finite x and y")
                elif bounds:
                    xmin, xmax, ymin, ymax = bounds
                    if not xmin <= float(x) <= xmax or not ymin <= float(y) <= ymax:
                        problems.append(f"coordinate_grid point {index} lies outside the grid")
                _visual_text(point.get("label"), f"point {index} label", problems, 32)
                _visual_color(point.get("color"), f"point {index} color", problems)

        lines = visual.get("lines", [])
        if not isinstance(lines, list) or len(lines) > 8:
            problems.append("coordinate_grid lines must be a list of at most 8")
        elif isinstance(lines, list):
            for index, line in enumerate(lines):
                if not isinstance(line, dict):
                    problems.append(f"coordinate_grid line {index} must be an object")
                    continue
                has_equation = "gradient" in line or "intercept" in line
                if has_equation:
                    if not _finite_number(line.get("gradient")) or not _finite_number(line.get("intercept")):
                        problems.append(f"coordinate_grid line {index} needs gradient and intercept")
                else:
                    line_points = line.get("points")
                    if not isinstance(line_points, list) or len(line_points) < 2 or len(line_points) > 24:
                        problems.append(f"coordinate_grid line {index} needs at least two points")
                    elif isinstance(line_points, list):
                        for point_index, point in enumerate(line_points):
                            _visual_point_pair(point, f"line {index} point {point_index}", problems)
                _visual_color(line.get("color"), f"line {index} color", problems)

        polygons = visual.get("polygons", [])
        if not isinstance(polygons, list) or len(polygons) > 8:
            problems.append("coordinate_grid polygons must be a list of at most 8")
        elif isinstance(polygons, list):
            for index, polygon in enumerate(polygons):
                if not isinstance(polygon, dict):
                    problems.append(f"coordinate_grid polygon {index} must be an object")
                    continue
                polygon_points = polygon.get("points")
                if not isinstance(polygon_points, list) or not 3 <= len(polygon_points) <= 12:
                    problems.append(f"coordinate_grid polygon {index} needs 3 to 12 points")
                elif isinstance(polygon_points, list):
                    for point_index, point in enumerate(polygon_points):
                        _visual_point_pair(
                            point,
                            f"polygon {index} point {point_index}",
                            problems,
                            bounds,
                        )
                if polygon.get("style") not in {None, "solid", "dashed"}:
                    problems.append(f"coordinate_grid polygon {index} has unsupported style")
                _visual_text(polygon.get("label"), f"polygon {index} label", problems, 32)
                _visual_color(polygon.get("color"), f"polygon {index} color", problems)

    elif visual_type == "scatter_plot":
        bounds = _visual_bounds(visual, problems, require_step=False)
        for key in ("title", "x_label", "y_label"):
            _visual_text(visual.get(key), key, problems, 60 if key == "title" else 40)
        points = visual.get("points")
        if not isinstance(points, list) or len(points) < 2 or len(points) > 100:
            problems.append("scatter_plot needs 2 to 100 points")
        elif isinstance(points, list):
            for index, point in enumerate(points):
                _visual_point_pair(point, f"scatter point {index}", problems, bounds)

    elif visual_type == "histogram":
        for key in ("title", "x_label", "y_label"):
            _visual_text(visual.get(key), key, problems, 60 if key == "title" else 40)
        bins = visual.get("bins")
        if not isinstance(bins, list) or not 1 <= len(bins) <= 20:
            problems.append("histogram needs 1 to 20 bins")
        elif isinstance(bins, list):
            previous_end: float | None = None
            for index, bin_data in enumerate(bins):
                if not isinstance(bin_data, dict):
                    problems.append(f"histogram bin {index} must be an object")
                    continue
                start = _visual_required_number(bin_data, "start", problems)
                end = _visual_required_number(bin_data, "end", problems)
                density = _visual_required_number(bin_data, "density", problems)
                if start is not None and end is not None:
                    if start >= end:
                        problems.append(f"histogram bin {index} has invalid interval")
                    if previous_end is not None and start < previous_end:
                        problems.append("histogram bins must be ordered and non-overlapping")
                    previous_end = end
                if density is not None and density < 0:
                    problems.append(f"histogram bin {index} density cannot be negative")

    elif visual_type == "box_plot":
        for key in ("label",):
            _visual_text(visual.get(key), key, problems, 40)
        values = {
            key: _visual_required_number(visual, key, problems)
            for key in ("min", "q1", "median", "q3", "max")
        }
        ordered = [values[key] for key in ("min", "q1", "median", "q3", "max")]
        if all(value is not None for value in ordered) and ordered != sorted(ordered):
            problems.append("box_plot summary values must be ordered")
        axis_min = visual.get("axis_min", values["min"])
        axis_max = visual.get("axis_max", values["max"])
        if not _finite_number(axis_min) or not _finite_number(axis_max):
            problems.append("box_plot axis bounds must be finite numbers")
        elif axis_min >= axis_max:
            problems.append("box_plot axis bounds must be increasing")
        elif values["min"] is not None and values["max"] is not None and not (
            float(axis_min) <= values["min"] <= values["max"] <= float(axis_max)
        ):
            problems.append("box_plot axis bounds must contain the five summary values")

    return problems


def _interactive_question_problems(question: dict) -> list[str]:
    """Validate an auto-marked point or polygon response contract."""
    kind = question.get("kind")
    if kind not in _INTERACTIVE_KINDS:
        return []
    problems: list[str] = []
    expected_mode = {
        "coordinate_points": "point",
        "transformation_polygon": "polygon",
    }[kind]
    expected_order = "exact" if kind == "coordinate_points" else "cyclic"
    spec = question.get("response_spec")
    expected = question.get("response_answer")
    visual = question.get("visual")
    if not isinstance(spec, dict):
        problems.append("interactive question needs response_spec")
        return problems
    allowed_spec = {"mode", "min_points", "max_points", "snap", "order", "label", "helper"}
    unknown_spec = sorted(set(spec) - allowed_spec)
    problems.extend(f"interactive response has unsupported spec field {key!r}" for key in unknown_spec)
    if spec.get("mode") != expected_mode:
        problems.append(f"{kind} response has wrong mode")
    if spec.get("order") != expected_order:
        problems.append(f"{kind} response has wrong point order policy")
    minimum = spec.get("min_points")
    maximum = spec.get("max_points")
    if (
        not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or not isinstance(maximum, int)
        or isinstance(maximum, bool)
        or not 1 <= minimum <= maximum <= 12
    ):
        problems.append("interactive response point limits must be integers from 1 to 12")
    elif (kind == "coordinate_points" and (minimum, maximum) != (1, 1)) or (
        kind == "transformation_polygon" and (minimum, maximum) != (3, 3)
    ):
        problems.append(f"{kind} response must require its fixed vertex count")
    snap = spec.get("snap")
    if not _finite_number(snap) or float(snap) <= 0:
        problems.append("interactive response snap must be a positive finite number")
        snap_value = None
    else:
        snap_value = float(snap)
    _visual_text(spec.get("label"), "interactive label", problems, 80)
    _visual_text(spec.get("helper"), "interactive helper", problems, 180)

    bounds = None
    if not isinstance(visual, dict) or visual.get("type") != "coordinate_grid":
        problems.append("interactive response needs a coordinate_grid visual")
    else:
        bounds = _visual_bounds(visual, problems)
        if snap_value is not None and _finite_number(visual.get("grid_step")):
            if abs(snap_value - float(visual["grid_step"])) > 1e-6:
                problems.append("interactive response snap must match grid_step")

    if not isinstance(expected, dict):
        problems.append("interactive question needs a private response_answer")
        return problems
    if set(expected) != {"type", "points"}:
        problems.append("interactive response_answer must contain only type and points")
    if expected.get("type") != kind:
        problems.append("interactive response_answer has the wrong type")
    points = expected.get("points")
    if not isinstance(points, list):
        problems.append("interactive response_answer points must be a list")
        return problems
    if isinstance(minimum, int) and isinstance(maximum, int) and not minimum <= len(points) <= maximum:
        problems.append("interactive response_answer has the wrong number of points")
    seen: set[tuple[float, float]] = set()
    for index, point in enumerate(points):
        before = len(problems)
        _visual_point_pair(point, f"interactive target {index}", problems, bounds)
        if len(problems) == before and snap_value is not None:
            if any(abs(float(value) / snap_value - round(float(value) / snap_value)) > 1e-6 for value in point):
                problems.append(f"interactive target {index} is not snapped to the grid")
        if isinstance(point, list) and len(point) == 2 and all(_finite_number(value) for value in point):
            key = (round(float(point[0]), 6), round(float(point[1]), 6))
            if key in seen:
                problems.append("interactive polygon cannot repeat a vertex")
            seen.add(key)
    payload, _solution = split_question(question)
    if "response_answer" in payload:
        problems.append("interactive response_answer leaked into the public payload")
    return problems


def _manual_question_problems(question: dict) -> list[str]:
    """Validate the public response contract without exposing the rubric."""
    kind = question.get("kind")
    if kind not in _MANUAL_KINDS:
        return []
    problems: list[str] = []
    spec = question.get("response_spec")
    assessment = question.get("assessment")
    if not isinstance(spec, dict) or not isinstance(assessment, dict):
        return ["manual question needs response_spec and assessment"]
    expected_mode = {
        "free_text": "textarea",
        "handwriting": "strokes",
        "audio": "audio",
        "evidence": "evidence",
    }[kind]
    if spec.get("mode") != expected_mode:
        problems.append(f"{kind} response has wrong mode")
    criteria = assessment.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        problems.append(f"{kind} response has no rubric criteria")
    else:
        ids: set[str] = set()
        for criterion in criteria:
            if not isinstance(criterion, dict):
                problems.append(f"{kind} response has malformed rubric criterion")
                continue
            key = str(criterion.get("id", ""))
            if not key or key in ids:
                problems.append(f"{kind} response has duplicate rubric id {key!r}")
            ids.add(key)
            maximum = criterion.get("max")
            if not isinstance(maximum, int) or not 1 <= maximum <= 5:
                problems.append(f"{kind} response has invalid rubric maximum")
    if kind == "evidence":
        fields = spec.get("fields")
        if not isinstance(fields, list) or not fields:
            problems.append("evidence response has no fields")
        else:
            field_ids: set[str] = set()
            for field in fields:
                if not isinstance(field, dict):
                    problems.append("evidence response has malformed field")
                    continue
                key = str(field.get("id", ""))
                if not key or key in field_ids:
                    problems.append(f"evidence response has duplicate field id {key!r}")
                field_ids.add(key)
                if not isinstance(field.get("max_chars"), int):
                    problems.append(f"evidence field {key!r} has no max_chars")
    if kind == "audio":
        if not isinstance(spec.get("mime_types"), list) or not spec.get("mime_types"):
            problems.append("audio response has no MIME allow-list")
        if not isinstance(spec.get("max_seconds"), int) or not 1 <= spec["max_seconds"] <= 180:
            problems.append("audio response has invalid duration")
    return problems


def validate_content(samples: int = 40) -> list[str]:
    """Check registry integrity, pathway reachability and question validity."""
    problems: list[str] = []
    banks = _banks()
    passages = _load()[1]

    # A dict lookup hides duplicate IDs, which would strand progress under the
    # wrong skill. Detect duplicates before checking individual sources.
    ids = [skill.id for skill in ALL_CONTENT_SKILLS]
    duplicate_ids = sorted({skill_id for skill_id in ids if ids.count(skill_id) > 1})
    problems.extend(f"duplicate skill id {skill_id!r}" for skill_id in duplicate_ids)

    declared_generators = {
        skill.generator
        for skill in ALL_CONTENT_SKILLS
        if skill.source == "generated" and skill.generator
    }
    orphan_generators = sorted(set(generators.GENERATORS) - declared_generators)
    problems.extend(f"orphan generator {name!r}" for name in orphan_generators)

    for skill in ALL_CONTENT_SKILLS:
        if skill.source not in {"generated", "bank"}:
            problems.append(f"{skill.id}: unsupported source {skill.source!r}")
            continue

        if skill.is_gcse:
            if skill.subject != "gcse_maths" or skill.pathway != "gcse_maths":
                problems.append(f"{skill.id}: invalid GCSE subject/pathway")
            if skill.year != 0:
                problems.append(f"{skill.id}: GCSE skill must use internal year 0")
            if not skill.tiers:
                problems.append(f"{skill.id}: missing GCSE tier eligibility")
            invalid_tiers = set(skill.tiers) - set(GCSE_TIERS)
            problems.extend(
                f"{skill.id}: invalid GCSE tier {tier!r}" for tier in sorted(invalid_tiers)
            )
        else:
            if skill.subject not in SUBJECT_ORDER:
                problems.append(f"{skill.id}: invalid Primary subject {skill.subject!r}")
            if skill.pathway != "primary":
                problems.append(f"{skill.id}: invalid Primary pathway {skill.pathway!r}")
            if skill.year not in PRIMARY_YEARS:
                problems.append(f"{skill.id}: invalid Primary year {skill.year!r}")

        if skill.source == "generated":
            if skill.generator not in generators.GENERATORS:
                problems.append(f"{skill.id}: missing generator {skill.generator!r}")
                continue
        elif not banks.get(skill.id):
            problems.append(f"{skill.id}: no questions in any bank file")
            continue

        tiers = skill.tiers if skill.is_gcse else (None,)
        for tier in tiers:
            draw_count = samples if skill.source == "generated" else bank_size(skill.id)
            for i in range(draw_count):
                rng = random.Random(i * 31 + 7)
                try:
                    question = draw_question(
                        skill.id, rng, level=i % 3, tier=tier
                    )
                except Exception as exc:  # noqa: BLE001
                    problems.append(
                        f"{skill.id} ({tier or 'Primary'}): raised "
                        f"{type(exc).__name__}: {exc}"
                    )
                    break

                prompt = question.get("prompt", "")
                if not prompt:
                    problems.append(f"{skill.id}: empty prompt")
                    break

                visual_problems = _visual_problems(question)
                if visual_problems:
                    problems.extend(f"{skill.id}: {problem}" for problem in visual_problems)
                    break

                interactive_problems = _interactive_question_problems(question)
                if interactive_problems:
                    problems.extend(f"{skill.id}: {problem}" for problem in interactive_problems)
                    break

                manual_problems = _manual_question_problems(question)
                if manual_problems:
                    problems.extend(f"{skill.id}: {problem}" for problem in manual_problems)
                    break
                if question.get("kind") in _MANUAL_KINDS:
                    continue
                if question.get("kind") in _INTERACTIVE_KINDS:
                    _payload, solution = split_question(question)
                    if not check_answer(
                        solution.get("response_answer"), solution, question["kind"]
                    ):
                        problems.append(f"{skill.id}: own interactive answer fails marking for {prompt!r}")
                        break
                    continue

                answer = str(question.get("answer", ""))
                if answer == "":
                    problems.append(f"{skill.id}: empty answer for {prompt!r}")
                    break

                if question.get("kind") == "choice":
                    choices = question.get("choices") or []
                    if len(choices) < 3:
                        problems.append(
                            f"{skill.id}: only {len(choices)} choices for {prompt!r}"
                        )
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

            if skill.source == "bank":
                for item in banks.get(skill.id, []):
                    passage_id = item.get("passage") if isinstance(item, dict) else None
                    if passage_id and passage_id not in passages:
                        problems.append(
                            f"{skill.id}: missing passage reference {passage_id!r}"
                        )

    for skill_id in banks:
        if skill_id not in SKILLS_BY_ID:
            problems.append(f"bank has questions for unknown skill {skill_id!r}")

    for subject in SUBJECT_ORDER:
        for year in PRIMARY_YEARS:
            group = [
                skill
                for skill in ALL_SKILLS
                if skill.subject == subject and skill.year == year
            ]
            if not group:
                problems.append(f"no Primary skills for {subject} Year {year}")

    for tier in GCSE_TIERS:
        if not gcse_skills_for(tier):
            problems.append(f"no GCSE skills for {tier} tier")

    return problems


def content_summary() -> dict:
    banks = _banks()
    primary_generated = [s for s in ALL_SKILLS if s.source == "generated"]
    primary_banked = [s for s in ALL_SKILLS if s.source == "bank"]
    generated = [s for s in ALL_CONTENT_SKILLS if s.source == "generated"]
    banked = [s for s in ALL_CONTENT_SKILLS if s.source == "bank"]
    gcse = [s for s in ALL_CONTENT_SKILLS if s.is_gcse]
    gcse_generated = [s for s in gcse if s.source == "generated"]
    gcse_banked = [s for s in gcse if s.source == "bank"]
    return {
        # ``skills`` remains the Primary count for backwards compatibility.
        "skills": len(ALL_SKILLS),
        "primary_skills": len(ALL_SKILLS),
        "content_skills": len(ALL_CONTENT_SKILLS),
        "generated_skills": len(generated),
        "bank_skills": len(banked),
        "primary_generated_skills": len(primary_generated),
        "primary_bank_skills": len(primary_banked),
        "gcse_skills": len(gcse),
        "gcse_generated_skills": len(gcse_generated),
        "gcse_bank_skills": len(gcse_banked),
        "gcse_foundation_skills": len(gcse_skills_for("foundation")),
        "gcse_higher_skills": len(gcse_skills_for("higher")),
        "generators": len(generators.GENERATORS),
        "bank_questions": sum(len(v) for v in banks.values()),
        "gcse_bank_questions": sum(
            len(banks.get(skill.id, [])) for skill in gcse_banked
        ),
        "passages": len(_load()[1]),
    }
