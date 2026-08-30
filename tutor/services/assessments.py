"""Validation and scoring for open-ended local assessments."""

from __future__ import annotations

import base64
import binascii
import math
import re
from datetime import datetime

MANUAL_KINDS = frozenset({"free_text", "handwriting", "audio", "evidence"})
INTERACTIVE_KINDS = frozenset({"coordinate_points", "transformation_polygon"})
_AUDIO_RE = re.compile(
    r"^data:(audio/(?:webm|mp4|ogg|wav))(?:;[A-Za-z0-9!#$&^_.+\-]+(?:=[A-Za-z0-9!#$&^_.+/\-]*)?)*;base64,([A-Za-z0-9+/=\s]+)$",
    re.IGNORECASE,
)


def is_manual(kind: str | None) -> bool:
    return kind in MANUAL_KINDS


def is_interactive(kind: str | None) -> bool:
    return kind in INTERACTIVE_KINDS


def validate_question(question: dict) -> list[str]:
    """Validate a content question's public response spec and private rubric."""
    kind = question.get("kind")
    if kind in INTERACTIVE_KINDS:
        problems: list[str] = []
        spec = question.get("response_spec")
        if not isinstance(spec, dict):
            return ["interactive question is missing response_spec"]
        if not isinstance(question.get("response_answer"), dict):
            problems.append("interactive question is missing private response_answer")
        try:
            validate_response(
                kind,
                question.get("response_answer"),
                spec,
                question.get("visual"),
            )
        except ValueError as exc:
            problems.append(str(exc))
        return problems
    if kind not in MANUAL_KINDS:
        return []
    problems: list[str] = []
    spec = question.get("response_spec")
    assessment = question.get("assessment")
    if not isinstance(spec, dict):
        return ["manual question is missing response_spec"]
    if not isinstance(assessment, dict):
        return ["manual question is missing assessment rubric"]
    if spec.get("mode") not in {"textarea", "strokes", "audio", "evidence"}:
        problems.append("manual question has unsupported response mode")
    if kind == "free_text" and spec.get("mode") != "textarea":
        problems.append("free_text must use textarea mode")
    if kind == "handwriting" and spec.get("mode") != "strokes":
        problems.append("handwriting must use strokes mode")
    if kind == "audio" and spec.get("mode") != "audio":
        problems.append("audio must use audio mode")
    if kind == "evidence" and spec.get("mode") != "evidence":
        problems.append("evidence must use evidence mode")

    criteria = assessment.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        problems.append("manual question needs at least one rubric criterion")
    else:
        ids: set[str] = set()
        for criterion in criteria:
            if not isinstance(criterion, dict):
                problems.append("rubric criterion is not an object")
                continue
            key = str(criterion.get("id", ""))
            if not key or key in ids or not re.fullmatch(r"[a-z][a-z0-9_-]{1,30}", key):
                problems.append(f"invalid or duplicate rubric criterion id {key!r}")
            ids.add(key)
            try:
                maximum = int(criterion.get("max", 0))
            except (TypeError, ValueError):
                maximum = 0
            if maximum < 1 or maximum > 5:
                problems.append(f"rubric criterion {key!r} has invalid maximum")
            if not criterion.get("label") or not criterion.get("description"):
                problems.append(f"rubric criterion {key!r} needs label and description")

    if kind == "evidence":
        fields = spec.get("fields")
        if not isinstance(fields, list) or not fields:
            problems.append("evidence response needs fields")
        else:
            field_ids: set[str] = set()
            for field in fields:
                if not isinstance(field, dict):
                    problems.append("evidence field is not an object")
                    continue
                field_id = str(field.get("id", ""))
                if not field_id or field_id in field_ids or not re.fullmatch(r"[a-z][a-z0-9_-]{1,30}", field_id):
                    problems.append(f"invalid or duplicate evidence field id {field_id!r}")
                field_ids.add(field_id)
                if not field.get("label") or not field.get("prompt"):
                    problems.append(f"evidence field {field_id!r} needs label and prompt")
                maximum = field.get("max_chars", 0)
                if not isinstance(maximum, int) or not 1 <= maximum <= 4000:
                    problems.append(f"evidence field {field_id!r} has invalid max_chars")
    if kind == "audio":
        mimes = spec.get("mime_types")
        if not isinstance(mimes, list) or not mimes or any(not str(m).startswith("audio/") for m in mimes):
            problems.append("audio response needs allowed audio MIME types")
        if not isinstance(spec.get("max_seconds"), int) or not 1 <= spec["max_seconds"] <= 180:
            problems.append("audio response has invalid max_seconds")
    return problems


def _text(value, maximum: int) -> str:
    return str(value or "").replace("\x00", "").strip()[:maximum]


def _interactive_bounds(visual: dict | None) -> tuple[float, float, float, float]:
    if not isinstance(visual, dict) or visual.get("type") != "coordinate_grid":
        raise ValueError("This interactive question has no coordinate grid.")
    values = []
    for key in ("x_min", "x_max", "y_min", "y_max"):
        value = visual.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError("This interactive question has invalid coordinate bounds.")
        values.append(float(value))
    xmin, xmax, ymin, ymax = values
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("This interactive question has invalid coordinate bounds.")
    return xmin, xmax, ymin, ymax


def _interactive_response(kind: str, response, spec: dict, visual: dict | None) -> dict:
    if not isinstance(response, dict):
        raise ValueError("Place the points on the grid before submitting.")
    if set(response) != {"type", "points"} or response.get("type") != kind:
        raise ValueError("That drawing was not a valid response for this question.")
    points = response.get("points")
    if not isinstance(points, list):
        raise ValueError("Place the points on the grid before submitting.")

    hard_min, hard_max = (1, 1) if kind == "coordinate_points" else (3, 3)
    minimum = spec.get("min_points")
    maximum = spec.get("max_points")
    if (
        not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or not isinstance(maximum, int)
        or isinstance(maximum, bool)
        or (minimum, maximum) != (hard_min, hard_max)
        or maximum > 12
    ):
        raise ValueError("This interactive response has invalid point limits.")
    if not hard_min <= len(points) <= hard_max:
        raise ValueError(
            "Place one point on the grid." if kind == "coordinate_points"
            else "Plot all three vertices before submitting."
        )

    snap = spec.get("snap")
    if isinstance(snap, bool) or not isinstance(snap, (int, float)) or not math.isfinite(float(snap)) or float(snap) <= 0:
        raise ValueError("This interactive response has an invalid grid step.")
    snap = float(snap)
    xmin, xmax, ymin, ymax = _interactive_bounds(visual)
    grid_step = visual.get("grid_step") if isinstance(visual, dict) else None
    if (
        isinstance(grid_step, bool)
        or not isinstance(grid_step, (int, float))
        or not math.isfinite(float(grid_step))
        or abs(snap - float(grid_step)) > 1e-6
    ):
        raise ValueError("This interactive response does not match the question grid.")

    clean_points: list[list[float]] = []
    seen: set[tuple[float, float]] = set()
    for point in points:
        if (
            not isinstance(point, list)
            or len(point) != 2
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in point
            )
        ):
            raise ValueError("Each plotted point needs an x and y coordinate.")
        x, y = float(point[0]), float(point[1])
        if not xmin <= x <= xmax or not ymin <= y <= ymax:
            raise ValueError("Keep every point inside the coordinate grid.")
        for value in (x, y):
            if abs(value / snap - round(value / snap)) > 1e-6:
                raise ValueError("Place every point on a grid intersection.")
        clean = [round(round(x / snap) * snap, 4), round(round(y / snap) * snap, 4)]
        clean = [0.0 if abs(value) < 0.00005 else value for value in clean]
        key = (clean[0], clean[1])
        if kind == "transformation_polygon" and key in seen:
            raise ValueError("Each vertex must be at a different grid point.")
        seen.add(key)
        clean_points.append(clean)
    return {"type": kind, "points": clean_points}


def _audio_data_url(value: str, allowed: list[str], max_bytes: int) -> str:
    if not isinstance(value, str):
        raise ValueError("The recording was not valid audio data.")
    match = _AUDIO_RE.fullmatch(value.strip())
    allowed_mimes = {
        str(mime).split(";", 1)[0].strip().lower()
        for mime in allowed
    }
    if not match or match.group(1).lower() not in allowed_mimes:
        raise ValueError("Use a supported local audio recording, or type your answer instead.")
    try:
        raw = base64.b64decode(re.sub(r"\s+", "", match.group(2)), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("The recording could not be read. Please try again.") from exc
    if not raw or len(raw) > max_bytes:
        raise ValueError("That recording is too large. Keep it short or type your answer instead.")
    return value.strip()


def validate_response(
    kind: str,
    response,
    spec: dict,
    visual: dict | None = None,
) -> dict:
    """Return a bounded response safe to persist, or raise ValueError."""
    if kind in INTERACTIVE_KINDS:
        return _interactive_response(kind, response, spec, visual)
    if not isinstance(response, dict):
        if kind == "free_text" and isinstance(response, str):
            response = {"text": response}
        else:
            raise ValueError("Please complete the response before submitting it.")

    if kind == "free_text":
        text = _text(response.get("text"), int(spec.get("max_chars", 2400)))
        if len(text) < int(spec.get("min_chars", 1)):
            raise ValueError("Write a little more so a grown-up can review your ideas.")
        return {"type": "text", "text": text}

    if kind == "handwriting":
        strokes = response.get("strokes") or []
        clean_strokes: list[list[list[float]]] = []
        points = 0
        if isinstance(strokes, list):
            for stroke in strokes:
                if not isinstance(stroke, list) or not stroke:
                    continue
                clean: list[list[float]] = []
                for point in stroke:
                    if not isinstance(point, (list, tuple)) or len(point) != 2:
                        continue
                    try:
                        x, y = float(point[0]), float(point[1])
                    except (TypeError, ValueError):
                        continue
                    if 0 <= x <= 1 and 0 <= y <= 1:
                        clean.append([round(x, 4), round(y, 4)])
                if clean:
                    clean_strokes.append(clean)
                    points += len(clean)
        typed = _text(response.get("text"), int(spec.get("fallback_max_chars", 500)))
        if points == 0 and not typed:
            raise ValueError("Draw your sentence, or use the typed fallback.")
        if points > int(spec.get("max_points", 9000)):
            raise ValueError("That handwriting response is too long. Please try again.")
        return {"type": "handwriting", "strokes": clean_strokes, "text": typed}

    if kind == "audio":
        transcript = _text(response.get("transcript"), int(spec.get("transcript_max_chars", 1200)))
        audio = response.get("audio")
        if audio:
            audio = _audio_data_url(audio, [str(m) for m in spec.get("mime_types", [])], int(spec.get("max_bytes", 1800000)))
        if not audio and not transcript:
            raise ValueError("Record your answer, or type what you would say instead.")
        try:
            duration = int(response.get("duration_ms") or 0)
        except (TypeError, ValueError):
            duration = 0
        maximum_duration = int(spec.get("max_seconds", 75)) * 1000
        if duration < 0 or duration > maximum_duration:
            raise ValueError("That recording is too long. Keep it short or type your answer instead.")
        if audio and duration == 0:
            raise ValueError("The recording duration was missing. Please record it again.")
        return {"type": "audio", "audio": audio, "transcript": transcript, "duration_ms": duration}

    if kind == "evidence":
        fields = {}
        raw_fields = response.get("fields")
        if not isinstance(raw_fields, dict):
            raise ValueError("Complete the investigation record before submitting it.")
        for field in spec.get("fields", []):
            field_id = str(field["id"])
            value = _text(raw_fields.get(field_id), int(field.get("max_chars", 800)))
            if field.get("required") and not value:
                raise ValueError(f"Complete the {field.get('label', field_id).lower()} field first.")
            fields[field_id] = value
        return {"type": "evidence", "fields": fields}

    raise ValueError("That response type is not supported.")


def review_response(solution: dict, scores: dict, feedback: str = "") -> dict:
    assessment = solution.get("assessment") or {}
    criteria = assessment.get("criteria") or []
    clean_scores: dict[str, int] = {}
    total = 0
    maximum = 0
    reviewed_criteria = []
    for criterion in criteria:
        key = str(criterion.get("id"))
        try:
            value = int(scores.get(key))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Choose a score for {criterion.get('label', key)}.") from exc
        limit = int(criterion.get("max", 0))
        if value < 0 or value > limit:
            raise ValueError(f"The score for {criterion.get('label', key)} is out of range.")
        clean_scores[key] = value
        total += value
        maximum += limit
        reviewed_criteria.append({**criterion, "score": value})
    if not maximum:
        raise ValueError("This assessment has no scoreable criteria.")
    ratio = float(assessment.get("pass_ratio", 0.6))
    passed = total / maximum >= ratio
    return {
        "version": assessment.get("version", 1),
        "criteria": reviewed_criteria,
        "scores": clean_scores,
        "score": total,
        "max_score": maximum,
        "passed": passed,
        "feedback": _text(feedback, 1200),
        "reviewed_at": datetime.now().isoformat(timespec="seconds"),
    }
