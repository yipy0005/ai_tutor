"""Playable open-ended Primary assessment prompts.

These prompts deliberately collect evidence rather than pretending a free-text,
handwriting, spoken or practical response is automatically right or wrong.
The child sees only the response specification; the rubric stays in the server
solution for parent review.
"""

from __future__ import annotations

import random
from copy import deepcopy

from .curriculum import Skill
from .generators import generator


def _generator_name(skill_id: str) -> str:
    return "assessment_" + skill_id.replace(".", "_").replace("-", "_")


def _rubric(*criteria: tuple[str, str, str, int]) -> list[dict]:
    return [
        {"id": key, "label": label, "description": description, "max": maximum}
        for key, label, description, maximum in criteria
    ]


def _assessment(
    sid: str,
    name: str,
    subject: str,
    topic: str,
    year: int,
    nc_ref: str,
    kind: str,
    prompt: str,
    response_spec: dict,
    criteria: list[dict],
    *,
    hint: str = "",
    prompt_sub: str = "",
    tags: tuple[str, ...] = (),
) -> Skill:
    generator_name = _generator_name(sid)

    def question(rng: random.Random, level: int = 1) -> dict:
        del rng, level
        output = {
            "kind": kind,
            "prompt": prompt,
            "response_spec": deepcopy(response_spec),
            "assessment": {
                "version": 1,
                "type": kind,
                "pass_ratio": 0.6,
                "criteria": deepcopy(criteria),
            },
        }
        if hint:
            output["hint"] = hint
        if prompt_sub:
            output["prompt_sub"] = prompt_sub
        return output

    question.__name__ = generator_name
    generator(generator_name)(question)
    return Skill(
        sid,
        name,
        subject,
        topic,
        year,
        "generated",
        generator_name,
        nc_ref,
        tags,
        "primary",
        (),
    )


def _composition(year: int, prompt: str) -> Skill:
    minimum = 20 + year * 10
    return _assessment(
        f"e{year}.write.composition",
        f"Year {year} composition",
        "english",
        "Writing",
        year,
        "Plan, draft, evaluate and edit writing for the intended audience and purpose",
        "free_text",
        prompt,
        {
            "mode": "textarea",
            "label": "Your writing",
            "min_chars": minimum,
            "max_chars": 2400,
            "rows": 5 if year < 4 else 8,
            "spellcheck": True,
            "helper": "Ideas first, then make your sentences clear.",
        },
        _rubric(
            ("ideas", "Ideas and content", "Ideas suit the prompt and audience.", 2),
            ("organisation", "Organisation", "The writing has a clear order or structure.", 2),
            ("language", "Word choices", "Words and sentences create the intended effect.", 2),
            ("accuracy", "Accuracy", "Grammar, spelling and punctuation are checked.", 2),
        ),
        hint="Say your ideas out loud first, then write them in an order that makes sense.",
        tags=("composition", "manual_review"),
    )


def _handwriting(year: int, text: str) -> Skill:
    return _assessment(
        f"e{year}.write.handwriting",
        f"Year {year} handwriting",
        "english",
        "Writing",
        year,
        "Write legibly and present writing appropriately for its purpose",
        "handwriting",
        "Copy this sentence in your neatest handwriting.",
        {
            "mode": "strokes",
            "label": "Handwriting pad",
            "copy_text": text,
            "canvas_label": "Draw your handwriting here",
            "fallback_label": "Or type the sentence if drawing is difficult",
            "max_points": 9000,
            "fallback_max_chars": 500,
        },
        _rubric(
            ("formation", "Letter formation", "Letters are formed clearly and consistently.", 2),
            ("spacing", "Spacing", "Words and letters have helpful spacing.", 2),
            ("baseline", "Line and size", "Writing sits on the line with a readable size.", 2),
            ("presentation", "Presentation", "The copied sentence is complete and legible.", 2),
        ),
        hint="Slow down, leave spaces between words, and keep your letters sitting on the line.",
        tags=("handwriting", "manual_review"),
    )


def _oracy(year: int, prompt: str) -> Skill:
    return _assessment(
        f"e{year}.speak.oracy",
        f"Year {year} speaking",
        "english",
        "Spoken language",
        year,
        "Speak audibly and fluently, adapting spoken language to audience and purpose",
        "audio",
        prompt,
        {
            "mode": "audio",
            "label": "Your spoken answer",
            "max_seconds": 75 if year >= 4 else 45,
            "max_bytes": 1800000,
            "mime_types": ["audio/webm", "audio/mp4", "audio/ogg", "audio/wav"],
            "fallback": "typed",
            "transcript_max_chars": 1200,
            "helper": "You can record your voice, or type what you would say instead.",
        },
        _rubric(
            ("clarity", "Clarity", "The response can be heard or read clearly.", 2),
            ("vocabulary", "Vocabulary", "Words are chosen for the audience and purpose.", 2),
            ("fluency", "Fluency", "Ideas are developed in a steady, understandable way.", 2),
            ("response", "Response", "The answer addresses the speaking prompt.", 2),
        ),
        hint="Plan three points: start with your answer, add a reason or example, then finish clearly.",
        tags=("oracy", "manual_review"),
    )


def _practical(year: int, prompt: str) -> Skill:
    fields = [
        {"id": "question", "label": "Question", "prompt": "What were you investigating?", "required": True, "max_chars": 500},
        {"id": "prediction", "label": "Prediction", "prompt": "What did you think would happen?", "required": True, "max_chars": 700},
        {"id": "method", "label": "Method", "prompt": "What did you do, in order?", "required": True, "max_chars": 1000},
        {"id": "observation", "label": "Observations or data", "prompt": "What did you see or measure?", "required": True, "max_chars": 900},
        {"id": "conclusion", "label": "Conclusion", "prompt": "What does your evidence show?", "required": True, "max_chars": 700},
        {"id": "safety", "label": "Safety", "prompt": "How would you keep the investigation safe?", "required": True, "max_chars": 500},
    ]
    return _assessment(
        f"s{year}.investigate.practical-evidence",
        f"Year {year} practical investigation",
        "science",
        "Working scientifically",
        year,
        "Ask questions, plan enquiries, record evidence, draw conclusions and report findings",
        "evidence",
        prompt,
        {
            "mode": "evidence",
            "label": "Investigation record",
            "fields": fields,
            "helper": "Use observations or measurements as evidence, not just a guess.",
        },
        _rubric(
            ("question", "Question and prediction", "The question and prediction are testable and sensible.", 2),
            ("method", "Method and variables", "The method is ordered and identifies what is changed or kept fair.", 2),
            ("evidence", "Evidence", "Observations or measurements are recorded clearly.", 2),
            ("conclusion", "Conclusion", "The conclusion uses the evidence to answer the question.", 2),
            ("safety", "Safety", "Relevant safety steps are identified.", 2),
        ),
        hint="A fair test changes one thing, measures one result, and keeps other important things the same.",
        tags=("practical", "manual_review"),
    )


PRIMARY_ASSESSMENT_EXTRA: list[Skill] = []

_COMPOSITIONS = {
    1: "Write three sentences about a tiny animal that finds a surprising home.",
    2: "Write a short story about a lost button that becomes useful.",
    3: "Write a diary entry from the point of view of an animal exploring a new place.",
    4: "Write a setting description that makes a woodland sound mysterious.",
    5: "Write an information page explaining how to care for an imaginary creature.",
    6: "Write a persuasive letter asking for a positive change at school.",
}
_HANDWRITING = {
    1: "The bright sun warms the garden.",
    2: "A careful reader notices small details.",
    3: "Good writers choose words with care.",
    4: "Clear handwriting helps every reader.",
    5: "A thoughtful explanation uses precise language.",
    6: "Practice makes communication easier to understand.",
}
_ORACY = {
    1: "Tell a grown-up about your favourite animal and give one reason.",
    2: "Explain how to look after a plant so that it can grow well.",
    3: "Describe a book or story you enjoyed and recommend it to someone.",
    4: "Explain one way people can help a local habitat.",
    5: "Give a short talk about a change you would make to improve your community.",
    6: "Present a balanced argument about whether children should have more outdoor learning.",
}
_PRACTICAL = {
    1: "Plan a simple investigation: which place might help a seed grow best?",
    2: "Plan a fair test to find out which material keeps an ice cube coldest.",
    3: "Plan an investigation comparing how far toy cars travel on different surfaces.",
    4: "Plan an investigation to find out how the length of a vibrating ruler affects sound.",
    5: "Plan a fair test to compare the air resistance of different paper shapes.",
    6: "Plan an investigation into how changing a circuit affects a lamp or buzzer.",
}

for _year in range(1, 7):
    PRIMARY_ASSESSMENT_EXTRA.extend(
        [
            _composition(_year, _COMPOSITIONS[_year]),
            _handwriting(_year, _HANDWRITING[_year]),
            _oracy(_year, _ORACY[_year]),
            _practical(_year, _PRACTICAL[_year]),
        ]
    )
