"""GREAT diagnostic scoring, evidence capture and summaries.

A final answer and a child's confidence rating are not enough to prove GREAT
ability. This module keeps self-reflection and evidence-based diagnostic data
separate. Diagnostic scores are only added after a parent reviews the child's
stage responses.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime

STAGES = ("G", "R", "E", "A", "T")
STAGE_LABELS = {
    "G": "Given",
    "R": "Required",
    "E": "Equation / Explanation / Link",
    "A": "Act",
    "T": "Test",
}
STAGE_PROMPTS = {
    "G": "What important information did you notice or use?",
    "R": "What exactly were you trying to find?",
    "E": "What idea, rule, or relationship connected the information?",
    "A": "Show or tell the step you used to work it out.",
    "T": "How could you check that your answer makes sense?",
}
SCORE_LABELS = {
    0: "Not independent yet",
    1: "With a prompt or scaffold",
    2: "Independent evidence",
}


def normalise_scores(raw: Mapping[str, object] | None) -> dict[str, int] | None:
    """Validate and return one complete GREAT score map, or ``None``."""
    if not isinstance(raw, Mapping):
        return None

    scores: dict[str, int] = {}
    for stage in STAGES:
        value = raw.get(stage)
        # bool is an int subclass, but True is not a GREAT score.
        if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1, 2):
            return None
        scores[stage] = value
    return scores


def normalise_responses(raw: Mapping[str, object] | None) -> dict[str, str] | None:
    """Validate complete, non-empty evidence responses from the child."""
    if not isinstance(raw, Mapping):
        return None

    responses: dict[str, str] = {}
    for stage in STAGES:
        value = raw.get(stage)
        if not isinstance(value, str):
            return None
        response = value.strip()
        if not response:
            return None
        responses[stage] = response[:500]
    return responses


def assessment_from_solution(solution: Mapping[str, object] | None) -> dict | None:
    """Read a self-reflection assessment from the legacy ``great`` JSON key."""
    if not isinstance(solution, Mapping):
        return None
    stored = solution.get("great")
    if not isinstance(stored, Mapping):
        return None
    scores = normalise_scores(stored.get("scores"))
    if scores is None:
        return None
    return {
        "scores": scores,
        "source": str(stored.get("source") or "child_reflection"),
        "recorded_at": str(stored.get("recorded_at") or ""),
    }


def store_assessment(
    solution: Mapping[str, object] | None,
    scores: Mapping[str, object],
    source: str = "child_reflection",
) -> dict:
    """Return a solution JSON object containing a self-reflection."""
    validated = normalise_scores(scores)
    if validated is None:
        raise ValueError("A complete GREAT reflection needs scores from 0 to 2 for every stage.")

    updated = dict(solution) if isinstance(solution, Mapping) else {}
    updated["great"] = {
        "scores": validated,
        "source": source,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }
    return updated


def _score_details(scores: Mapping[str, object] | None) -> dict | None:
    validated = normalise_scores(scores)
    if validated is None:
        return None

    first_help = next((stage for stage in STAGES if validated[stage] < 2), None)
    return {
        "scores": validated,
        "stages": [
            {"key": stage, "label": STAGE_LABELS[stage], "score": validated[stage]}
            for stage in STAGES
        ],
        "profile": "-".join(str(validated[stage]) for stage in STAGES),
        "total": sum(validated.values()),
        "first_help": (
            {
                "key": first_help,
                "label": STAGE_LABELS[first_help],
                "score": validated[first_help],
            }
            if first_help
            else None
        ),
    }


def summary(assessment: Mapping[str, object] | None) -> dict | None:
    """Turn a self-reflection into parent-facing profile information."""
    if not isinstance(assessment, Mapping):
        return None
    details = _score_details(assessment.get("scores"))
    if details is None:
        return None
    details.update(
        {
            "source": str(assessment.get("source") or "child_reflection"),
            "recorded_at": str(assessment.get("recorded_at") or ""),
        }
    )
    return details


def question_summary(solution: Mapping[str, object] | None) -> dict | None:
    """Return a display-ready self-reflection summary for one question."""
    return summary(assessment_from_solution(solution))


def diagnostic_from_solution(solution: Mapping[str, object] | None) -> dict | None:
    """Read submitted diagnostic evidence and any parent review."""
    if not isinstance(solution, Mapping):
        return None
    stored = solution.get("great_diagnostic")
    if not isinstance(stored, Mapping):
        return None

    raw_responses = stored.get("responses")
    if not isinstance(raw_responses, Mapping):
        return None
    responses = {
        stage: str(raw_responses.get(stage) or "").strip()[:500] for stage in STAGES
    }
    scores = normalise_scores(stored.get("scores"))
    status = "reviewed" if scores is not None else str(stored.get("status") or "submitted")
    return {
        "responses": responses,
        "scores": scores,
        "status": status,
        "source": str(stored.get("source") or "child_evidence"),
        "recorded_at": str(stored.get("recorded_at") or ""),
        "reviewed_at": str(stored.get("reviewed_at") or ""),
    }


def store_diagnostic(
    solution: Mapping[str, object] | None,
    responses: Mapping[str, object],
) -> dict:
    """Store child evidence as submitted, without pretending it is scored."""
    validated = normalise_responses(responses)
    if validated is None:
        raise ValueError("Please answer each GREAT thinking prompt before saving.")

    updated = dict(solution) if isinstance(solution, Mapping) else {}
    updated["great_diagnostic"] = {
        "responses": validated,
        "scores": None,
        "status": "submitted",
        "source": "child_evidence",
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }
    return updated


def review_diagnostic(
    solution: Mapping[str, object] | None,
    scores: Mapping[str, object],
    reviewer: str = "parent",
) -> dict:
    """Add the parent's 0/1/2 judgement to already-submitted evidence."""
    validated = normalise_scores(scores)
    if validated is None:
        raise ValueError("Choose a score from 0 to 2 for every GREAT stage.")

    diagnostic = diagnostic_from_solution(solution)
    if diagnostic is None:
        raise ValueError("There is no GREAT evidence to review for this question.")

    updated = dict(solution) if isinstance(solution, Mapping) else {}
    stored = dict(updated.get("great_diagnostic") or {})
    stored.update(
        {
            "scores": validated,
            "status": "reviewed",
            "reviewer": reviewer,
            "reviewed_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    updated["great_diagnostic"] = stored
    return updated


def diagnostic_summary(solution: Mapping[str, object] | None) -> dict | None:
    """Return evidence, review state and optional scores for parent views."""
    diagnostic = diagnostic_from_solution(solution)
    if diagnostic is None:
        return None

    details = _score_details(diagnostic["scores"])
    stages = []
    for stage in STAGES:
        stages.append(
            {
                "key": stage,
                "label": STAGE_LABELS[stage],
                "prompt": STAGE_PROMPTS[stage],
                "response": diagnostic["responses"].get(stage, ""),
                "score": details["scores"][stage] if details else None,
            }
        )

    return {
        "responses": diagnostic["responses"],
        "status": diagnostic["status"],
        "submitted": True,
        "reviewed": details is not None,
        "source": diagnostic["source"],
        "recorded_at": diagnostic["recorded_at"],
        "reviewed_at": diagnostic["reviewed_at"],
        "stages": stages,
        "scores": details["scores"] if details else None,
        "profile": details["profile"] if details else None,
        "total": details["total"] if details else None,
        "first_help": details["first_help"] if details else None,
    }


def aggregate(assessments: Iterable[Mapping[str, object]]) -> dict:
    """Aggregate assessed questions without treating missing rows as failures."""
    valid = []
    for assessment in assessments:
        scores = normalise_scores(assessment.get("scores"))
        if scores is not None:
            valid.append(scores)

    stage_rows = []
    for stage in STAGES:
        average = round(sum(scores[stage] for scores in valid) / len(valid), 1) if valid else None
        stage_rows.append(
            {
                "key": stage,
                "label": STAGE_LABELS[stage],
                "average": average,
                "pct": round(average / 2 * 100) if average is not None else None,
            }
        )

    first_help = Counter(
        stage for scores in valid if (stage := next((key for key in STAGES if scores[key] < 2), None))
    )
    bottleneck = None
    if first_help:
        key = max(STAGES, key=lambda stage: (first_help[stage], -STAGES.index(stage)))
        bottleneck = {
            "key": key,
            "label": STAGE_LABELS[key],
            "count": first_help[key],
            "pct": round(first_help[key] / len(valid) * 100),
        }

    return {
        "assessed": len(valid),
        "average_total": round(
            sum(sum(scores.values()) for scores in valid) / len(valid), 1
        )
        if valid
        else None,
        "stages": stage_rows,
        "bottleneck": bottleneck,
    }


def aggregate_diagnostics(diagnostics: Iterable[Mapping[str, object]]) -> dict:
    """Aggregate reviewed diagnostics and report evidence awaiting review."""
    submitted = 0
    reviewed = []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, Mapping):
            continue
        submitted += 1
        if normalise_scores(diagnostic.get("scores")) is not None:
            reviewed.append(diagnostic)

    report = aggregate(reviewed)
    report.update(
        {
            "submitted": submitted,
            "reviewed": len(reviewed),
            "needs_review": max(0, submitted - len(reviewed)),
        }
    )
    return report
