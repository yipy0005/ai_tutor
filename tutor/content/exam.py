"""Board-style metadata for board-neutral GCSE practice.

The curriculum and skill ids stay board-neutral. A selected board profile only
changes the exam-facing snapshot attached to a question: paper, calculator
status, command wording and response format. It never changes tier
eligibility or the underlying skill identity.
"""

from __future__ import annotations

import random

GCSE_BOARD_OPTIONS = {
    "generic": "Board-neutral practice",
    "aqa": "AQA-style practice",
    "edexcel": "Pearson Edexcel-style practice",
    "ocr": "OCR-style practice",
    "wjec": "WJEC-style practice",
}

GCSE_BOARD_PROFILES = {
    "generic": {
        "papers": (("practice", "Mixed practice", None),),
        "commands": ("Calculate", "Work out", "Explain"),
        "format": "mixed-practice",
    },
    "aqa": {
        "papers": (
            ("1", "Paper 1 · non-calculator", False),
            ("2", "Paper 2 · calculator", True),
            ("3", "Paper 3 · calculator", True),
        ),
        "commands": ("Calculate", "Work out", "Explain", "Show that"),
        "format": "structured-short-answer",
    },
    "edexcel": {
        "papers": (
            ("1", "Paper 1 · non-calculator", False),
            ("2", "Paper 2 · calculator", True),
            ("3", "Paper 3 · calculator", True),
        ),
        "commands": ("Calculate", "Work out", "Give", "Explain"),
        "format": "structured-short-answer",
    },
    "ocr": {
        "papers": (
            ("1", "Paper 1 · non-calculator", False),
            ("2", "Paper 2 · calculator", True),
            ("3", "Paper 3 · calculator", True),
        ),
        "commands": ("Calculate", "Determine", "Work out", "Show that"),
        "format": "structured-short-answer",
    },
    "wjec": {
        "papers": (
            ("1", "Paper 1 · non-calculator", False),
            ("2", "Paper 2 · calculator", True),
            ("3", "Paper 3 · calculator", True),
        ),
        "commands": ("Calculate", "Work out", "State", "Explain"),
        "format": "structured-short-answer",
    },
}


def normalise_board(board: str | None) -> str:
    return board if board in GCSE_BOARD_OPTIONS else "generic"


def apply_exam_style(
    question: dict,
    *,
    board: str | None,
    tier: str | None,
    topic: str,
    rng: random.Random,
    level: int = 1,
    subject: str = "gcse_maths",
) -> dict:
    """Attach a safe exam snapshot and adapt board-style response format."""
    board = normalise_board(board)
    profile = GCSE_BOARD_PROFILES[board]
    if subject == "gcse_physics" and board != "generic":
        # Physics exam papers permit calculators; the board profiles remain
        # presentation styles rather than separate Physics syllabuses.
        papers = (
            ("1", "Paper 1 · calculator", True),
            ("2", "Paper 2 · calculator", True),
        )
    else:
        papers = profile["papers"]
    paper, paper_label, calculator = rng.choice(papers)
    command = rng.choice(profile["commands"])
    marks = max(1, min(4, 1 + int(level or 0)))
    objective = "AO1" if level <= 1 else "AO2"

    question["exam"] = {
        "board": board,
        "board_label": GCSE_BOARD_OPTIONS[board],
        "paper": paper,
        "paper_label": paper_label,
        "calculator": calculator,
        "marks": marks,
        "command_word": command,
        "assessment_objective": objective,
        "format": profile["format"],
        "topic": topic,
    }

    # GCSE papers are written-response assessments rather than a bank of
    # multiple-choice prompts.  Keep board-neutral mode compatible with the
    # existing starter experience; selecting a board gives typed short answers.
    if board != "generic" and question.get("kind") == "choice":
        question["kind"] = "text"
        question.pop("choices", None)
        question["keypad"] = "text"

    # Keep the mark scheme in the server-only solution after split_question.
    question["mark_scheme"] = [{"mark": marks, "accept": [str(question.get("answer", ""))]}]
    return question
