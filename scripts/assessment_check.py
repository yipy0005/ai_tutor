"""Focused checks for rich local assessments and GCSE board metadata.

    pixi run assessment-check

This uses a temporary SQLite database and never touches a family's real data.
It deliberately tests the contracts that are easy to regress when manual
responses are added beside the legacy scalar answer flow.
"""

from __future__ import annotations

import base64
import json
import os
import random
import subprocess
import tempfile
from pathlib import Path

from werkzeug.datastructures import MultiDict

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, condition: bool, detail: object = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  ✓ {label}")
    else:
        print(f"  ✗ {label} {detail}")
        FAILURES.append(f"{label} {detail}".strip())


def expect_value_error(label: str, callback, phrase: str) -> None:
    try:
        callback()
    except ValueError as exc:
        check(label, phrase.lower() in str(exc).lower(), str(exc))
    else:
        check(label, False, "did not reject the invalid response")


def renderer_check() -> tuple[bool, object]:
    """Render every GCSE diagram type in a tiny offline Node VM."""
    payloads = {
        "triangle": {
            "type": "triangle",
            "mode": "right",
            "labels": {"base": "3 cm", "height": "4 cm", "hypotenuse": "?"},
        },
        "coordinate_grid": {
            "type": "coordinate_grid",
            "x_min": -4,
            "x_max": 4,
            "y_min": -4,
            "y_max": 4,
            "grid_step": 1,
            "points": [{"x": 2, "y": 3, "label": "P"}],
            "lines": [{"gradient": 2, "intercept": 1}],
        },
        "scatter_plot": {
            "type": "scatter_plot",
            "x_min": 0,
            "x_max": 5,
            "y_min": 0,
            "y_max": 5,
            "points": [[1, 1], [2, 2], [3, 4]],
        },
        "histogram": {
            "type": "histogram",
            "bins": [
                {"start": 0, "end": 10, "density": 2},
                {"start": 10, "end": 20, "density": 4},
            ],
        },
        "box_plot": {
            "type": "box_plot",
            "min": 1,
            "q1": 2,
            "median": 3,
            "q3": 4,
            "max": 5,
            "axis_min": 0,
            "axis_max": 6,
        },
    }
    node_script = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const window = { console: { warn: () => {} } };
vm.runInNewContext(source, { window, console: window.console });
const payloads = JSON.parse(process.argv[2]);
const results = Object.keys(payloads).map((type) => {
  const markup = window.Visuals.render(payloads[type]);
  return typeof markup === "string" && markup.includes("<svg") &&
    markup.includes('role="img"') && markup.includes("aria-label=");
});
const interactive = window.Visuals.renderInteractive(payloads.coordinate_grid);
const interactiveOk = typeof interactive === "string" &&
  interactive.includes('data-interactive-grid="true"') &&
  interactive.includes('tabindex="0"') &&
  interactive.includes('aria-describedby="interactive-instructions"') &&
  interactive.includes('role="img"') && interactive.includes("aria-label=");
process.stdout.write(JSON.stringify({static: results, interactive: interactiveOk}));
"""
    visuals_path = Path(__file__).resolve().parents[1] / "tutor/static/js/visuals.js"
    try:
        result = subprocess.run(
            ["node", "-e", node_script, str(visuals_path), json.dumps(payloads)],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return False, str(exc)
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    try:
        results = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, result.stdout.strip()
    return all(results.get("static", [])) and results.get("interactive") is True, results


def main() -> int:
    tmp = tempfile.TemporaryDirectory(prefix="tutor-assessment-")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp.name}/assessment.sqlite3"
    os.environ["SECRET_KEY"] = "assessment-check-secret-key"

    from tutor import create_app, db
    from tutor.content import (
        ALL_CONTENT_SKILLS,
        check_answer,
        draw_question,
        gcse_skills_for,
        split_question,
    )
    from tutor.models import DailyActivity, SkillProgress
    from tutor.services import assessments, maintenance, pathways, profiles, quests

    manual_ids = (
        "e1.write.composition",
        "e1.write.handwriting",
        "e1.speak.oracy",
        "s1.investigate.practical-evidence",
    )

    print("\nContent response contracts")
    manual_questions = {
        skill_id: draw_question(skill_id, random.Random(index + 1))
        for index, skill_id in enumerate(manual_ids)
    }
    for skill_id, question in manual_questions.items():
        check(
            f"{skill_id} has a valid manual rubric",
            not assessments.validate_question(question),
            assessments.validate_question(question),
        )
        payload, solution = split_question(question)
        check(
            f"{skill_id} keeps rubric out of learner payload",
            "assessment" not in payload and "criteria" not in str(payload),
            payload,
        )
        check(
            f"{skill_id} keeps rubric in private solution",
            isinstance(solution.get("assessment", {}).get("criteria"), list),
            solution,
        )

    composition = manual_questions["e1.write.composition"]
    composition_spec = composition["response_spec"]
    expect_value_error(
        "free text rejects a response below its minimum",
        lambda: assessments.validate_response(
            "free_text", {"text": "too short"}, composition_spec
        ),
        "more",
    )
    bounded_text = assessments.validate_response(
        "free_text", {"text": "x" * 5000}, composition_spec
    )
    check(
        "free text is bounded to its maximum",
        len(bounded_text["text"]) == composition_spec["max_chars"],
        len(bounded_text["text"]),
    )

    handwriting = manual_questions["e1.write.handwriting"]
    handwriting_spec = handwriting["response_spec"]
    expect_value_error(
        "handwriting requires strokes or typed fallback",
        lambda: assessments.validate_response("handwriting", {}, handwriting_spec),
        "draw",
    )
    strokes = assessments.validate_response(
        "handwriting",
        {"strokes": [[[0, 0], [0.5, 0.5], [2, 2]]], "text": ""},
        handwriting_spec,
    )
    check(
        "handwriting keeps bounded in-range points",
        strokes["strokes"] == [[[0.0, 0.0], [0.5, 0.5]]],
        strokes,
    )
    fallback = assessments.validate_response(
        "handwriting", {"text": "typed fallback"}, handwriting_spec
    )
    check("handwriting accepts typed fallback", fallback["text"] == "typed fallback")

    audio = manual_questions["e1.speak.oracy"]
    audio_spec = audio["response_spec"]
    audio_data = (
        "data:audio/webm;codecs=opus;base64,"
        + base64.b64encode(b"local audio").decode("ascii")
    )
    saved_audio = assessments.validate_response(
        "audio", {"audio": audio_data, "duration_ms": 1200}, audio_spec
    )
    check(
        "audio accepts browser codec MIME parameters",
        saved_audio["audio"] == audio_data and saved_audio["duration_ms"] == 1200,
    )
    typed_audio = assessments.validate_response(
        "audio", {"transcript": "I would explain my idea clearly."}, audio_spec
    )
    check("audio accepts typed offline fallback", typed_audio["audio"] is None)
    expect_value_error(
        "audio rejects an unsupported MIME type",
        lambda: assessments.validate_response(
            "audio",
            {"audio": audio_data.replace("audio/webm", "audio/flac"), "duration_ms": 1000},
            audio_spec,
        ),
        "supported",
    )
    expect_value_error(
        "audio rejects a recording over its duration bound",
        lambda: assessments.validate_response(
            "audio", {"audio": audio_data, "duration_ms": 999999}, audio_spec
        ),
        "too long",
    )
    expect_value_error(
        "audio rejects a recording over its byte bound",
        lambda: assessments.validate_response(
            "audio",
            {"audio": audio_data, "duration_ms": 1000},
            {**audio_spec, "max_bytes": 2},
        ),
        "too large",
    )

    evidence = manual_questions["s1.investigate.practical-evidence"]
    evidence_spec = evidence["response_spec"]
    empty_fields = {field["id"]: "" for field in evidence_spec["fields"]}
    expect_value_error(
        "evidence requires every required field",
        lambda: assessments.validate_response(
            "evidence", {"fields": empty_fields}, evidence_spec
        ),
        "complete",
    )
    evidence_fields = {field["id"]: "Recorded evidence" for field in evidence_spec["fields"]}
    saved_evidence = assessments.validate_response(
        "evidence", {"fields": evidence_fields}, evidence_spec
    )
    check(
        "evidence stores the declared fields only",
        set(saved_evidence["fields"]) == set(evidence_fields),
        saved_evidence,
    )

    criteria = composition["assessment"]["criteria"]
    maximum_scores = {criterion["id"]: criterion["max"] for criterion in criteria}
    review = assessments.review_response(
        {"assessment": composition["assessment"]}, maximum_scores, "Great detail."
    )
    check(
        "rubric scoring calculates full marks and pass",
        review["score"] == review["max_score"] and review["passed"],
        review,
    )
    failed_review = assessments.review_response(
        {"assessment": composition["assessment"]}, dict.fromkeys(maximum_scores, 0)
    )
    check("rubric scoring can fail below the pass ratio", not failed_review["passed"])

    print("\nInteractive diagram contracts")
    interactive_questions = {
        "coordinate_points": draw_question(
            "gcse.maths.algebra.coordinates", random.Random(21), tier="foundation"
        ),
        "transformation_polygon": draw_question(
            "gcse.maths.geometry.transformations", random.Random(22), tier="foundation"
        ),
    }
    for kind, question in interactive_questions.items():
        problems = assessments.validate_question(question)
        check(f"{kind} has a valid response contract", not problems, problems)
        payload, solution = split_question(question)
        check(
            f"{kind} exposes controls but keeps its target private",
            "response_spec" in payload
            and "response_answer" not in payload
            and "answer" not in payload
            and isinstance(solution.get("response_answer"), dict),
            (payload, solution),
        )

    coordinate_question = interactive_questions["coordinate_points"]
    coordinate_spec = coordinate_question["response_spec"]
    coordinate_visual = coordinate_question["visual"]
    normalised_point = assessments.validate_response(
        "coordinate_points",
        {"type": "coordinate_points", "points": [[2.0000001, 3]]},
        coordinate_spec,
        coordinate_visual,
    )
    check(
        "interactive points are normalized to bounded grid values",
        normalised_point == {"type": "coordinate_points", "points": [[2.0, 3.0]]},
        normalised_point,
    )
    expect_value_error(
        "interactive responses reject the wrong type",
        lambda: assessments.validate_response(
            "coordinate_points",
            {"type": "transformation_polygon", "points": [[2, 3]]},
            coordinate_spec,
            coordinate_visual,
        ),
        "valid response",
    )
    expect_value_error(
        "interactive responses reject extra fields",
        lambda: assessments.validate_response(
            "coordinate_points",
            {"type": "coordinate_points", "points": [[2, 3]], "extra": True},
            coordinate_spec,
            coordinate_visual,
        ),
        "valid response",
    )
    expect_value_error(
        "interactive responses reject unsnapped points",
        lambda: assessments.validate_response(
            "coordinate_points",
            {"type": "coordinate_points", "points": [[2.5, 3]]},
            coordinate_spec,
            coordinate_visual,
        ),
        "grid intersection",
    )
    expect_value_error(
        "interactive responses reject points outside the grid",
        lambda: assessments.validate_response(
            "coordinate_points",
            {"type": "coordinate_points", "points": [[9, 3]]},
            coordinate_spec,
            coordinate_visual,
        ),
        "inside",
    )

    polygon_question = interactive_questions["transformation_polygon"]
    polygon_spec = polygon_question["response_spec"]
    polygon_visual = polygon_question["visual"]
    expect_value_error(
        "polygon responses reject the wrong vertex count",
        lambda: assessments.validate_response(
            "transformation_polygon",
            {"type": "transformation_polygon", "points": [[1, -1], [3, -1]]},
            polygon_spec,
            polygon_visual,
        ),
        "three",
    )
    expect_value_error(
        "polygon responses reject duplicate vertices",
        lambda: assessments.validate_response(
            "transformation_polygon",
            {
                "type": "transformation_polygon",
                "points": [[1, -1], [1, -1], [2, -3]],
            },
            polygon_spec,
            polygon_visual,
        ),
        "different",
    )
    broken_target = dict(coordinate_question)
    broken_target["response_answer"] = {
        "type": "coordinate_points",
        "points": [[2.5, 3]],
    }
    check(
        "interactive question validation rejects an unsnapped private target",
        bool(assessments.validate_question(broken_target)),
    )
    polygon_solution = split_question(polygon_question)[1]
    target_points = polygon_solution["response_answer"]["points"]
    rotated_points = target_points[1:] + target_points[:1]
    reversed_points = list(reversed(target_points))
    check(
        "polygon marking accepts cyclic vertex order",
        check_answer(
            {"type": "transformation_polygon", "points": rotated_points},
            polygon_solution,
            "transformation_polygon",
        ),
    )
    check(
        "polygon marking accepts reversed cyclic order",
        check_answer(
            {"type": "transformation_polygon", "points": reversed_points},
            polygon_solution,
            "transformation_polygon",
        ),
    )

    print("\nGREAT question variants")
    variant_failures: list[str] = []
    generic_markers = (
        "g — given:",
        "r — required:",
        "given: the useful facts",
        "required: fill in the missing",
    )
    manual_kinds = {"free_text", "handwriting", "audio", "evidence"}
    interactive_kinds = {"coordinate_points", "transformation_polygon"}
    for index, skill in enumerate(ALL_CONTENT_SKILLS):
        tier = skill.tiers[0] if skill.is_gcse else None
        for level in range(3):
            try:
                question = draw_question(
                    skill.id,
                    random.Random(index * 17 + level + 1),
                    level=level,
                    tier=tier,
                )
            except Exception as exc:  # noqa: BLE001
                variant_failures.append(f"{skill.id} level {level}: {exc}")
                continue
            expected_visibility = {
                "level": level,
                "given": "explicit" if level < 2 else "implicit",
                "required": "explicit" if level == 0 else "implicit",
            }
            if question.get("great_visibility") != expected_visibility:
                variant_failures.append(
                    f"{skill.id} level {level}: {question.get('great_visibility')}"
                )
            prompt = str(question.get("prompt", ""))
            prompt_lower = prompt.casefold()
            if any(marker in prompt_lower for marker in generic_markers):
                variant_failures.append(
                    f"{skill.id} level {level}: generic framework text remains"
                )
            if "great_variants" in question:
                variant_failures.append(
                    f"{skill.id} level {level}: authored variants leaked from draw"
                )
            payload, solution = split_question(question)
            if any(key in payload for key in ("answer", "accept", "great_variants")):
                variant_failures.append(
                    f"{skill.id} level {level}: private answer data leaked"
                )
            kind = question.get("kind", "choice")
            if kind not in manual_kinds | interactive_kinds and not check_answer(
                solution.get("answer"), solution, kind
            ):
                variant_failures.append(
                    f"{skill.id} level {level}: answer no longer marks correctly"
                )
    check(
        f"all {len(ALL_CONTENT_SKILLS)} syllabus skills expose three natural G/R variants",
        not variant_failures,
        variant_failures[:8],
    )

    natural_examples = {
        "gcse.maths.geometry.pythagoras": ("hypotenuse", "side"),
        "gcse.maths.algebra.linear-equations": ("solve", "x"),
        "gcse.maths.statistics.averages": ("mean", "median", "range"),
        "gcse.maths.statistics.probability": ("probability", "p("),
        "gcse.maths.graphs.linear": ("y =", "y-intercept", "line"),
    }
    natural_failures: list[str] = []
    for index, (skill_id, terms) in enumerate(natural_examples.items()):
        for level in range(3):
            question = draw_question(
                skill_id,
                random.Random(700 + index * 11 + level),
                level=level,
                tier="foundation",
            )
            prompt_lower = str(question.get("prompt", "")).casefold()
            if not any(term.casefold() in prompt_lower for term in terms):
                natural_failures.append(f"{skill_id} level {level}: {question.get('prompt')}")
            if any(marker in prompt_lower for marker in generic_markers):
                natural_failures.append(f"{skill_id} level {level}: framework marker")
    check(
        "representative GCSE prompts retain natural subject context",
        not natural_failures,
        natural_failures,
    )

    print("\nGCSE visual contracts")
    shared_visuals = [
        ("gcse.maths.algebra.coordinates", "coordinate_grid"),
        ("gcse.maths.algebra.linear-graphs", "coordinate_grid"),
        ("gcse.maths.geometry.transformations", "coordinate_grid"),
        ("gcse.maths.statistics.scatter", "scatter_plot"),
    ]
    higher_visuals = [
        ("gcse.maths.statistics.histograms", "histogram"),
        ("gcse.maths.statistics.cumulative-frequency", "coordinate_grid"),
        ("gcse.maths.statistics.box-plots", "box_plot"),
    ]
    for index, (skill_id, expected_type) in enumerate(shared_visuals):
        for tier in ("foundation", "higher"):
            question = draw_question(skill_id, random.Random(index + len(tier)), tier=tier)
            payload, solution = split_question(question)
            visual = payload.get("visual")
            check(
                f"{skill_id} keeps its {tier} diagram",
                isinstance(visual, dict) and visual.get("type") == expected_type,
                visual,
            )
            visual_blob = json.dumps(visual, ensure_ascii=False).lower()
            check(
                f"{skill_id} public diagram has no private answer data",
                payload.get("visual") == question.get("visual")
                and "visual" not in solution
                and all(key not in visual_blob for key in ("answer", "mark_scheme", "accept", "explain")),
                (payload, solution),
            )
    for index, (skill_id, expected_type) in enumerate(higher_visuals):
        question = draw_question(skill_id, random.Random(index + 50), tier="higher")
        check(
            f"{skill_id} keeps its Higher-only diagram",
            question.get("visual", {}).get("type") == expected_type,
            question.get("visual"),
        )
        blocked = False
        try:
            draw_question(skill_id, random.Random(index + 70), tier="foundation")
        except PermissionError:
            blocked = True
        check("Foundation cannot draw a Higher-only visual skill", blocked, skill_id)
    renderer_ok, renderer_detail = renderer_check()
    check("all GCSE diagram types render as accessible SVG", renderer_ok, renderer_detail)

    app = create_app()
    app.config.update(TESTING=True)

    with app.app_context():
        db.create_all()
        primary = profiles.create_child("Primary", year_group=6)
        gcse = profiles.create_child("GCSE", year_group=6, gcse_tier="higher")
        foundation = profiles.create_child("Foundation", year_group=6, gcse_tier="foundation")
        db.session.commit()

        print("\nInteractive quest flow")
        interactive_quest = quests.start_quest(
            gcse,
            subject="gcse_maths",
            mode="skill",
            count=4,
            skill_id="gcse.maths.algebra.coordinates",
            rng=random.Random(31),
        )
        interactive_row = interactive_quest.questions[0]
        interactive_public = quests.quest_payload(interactive_quest, gcse)["questions"][0]
        check(
            "interactive quest payload keeps target coordinates private",
            interactive_public.get("kind") == "coordinate_points"
            and "response_spec" in interactive_public
            and "response_answer" not in interactive_public
            and "answer" not in interactive_public,
            interactive_public,
        )
        malformed = quests.submit_answer(
            gcse,
            interactive_quest,
            interactive_row.id,
            response={"type": "coordinate_points", "points": [[2.5, 3]]},
            seconds=9,
        )
        check(
            "malformed interactive responses are rejected",
            "error" in malformed,
            malformed,
        )
        check(
            "malformed interactive responses roll back attempt state",
            interactive_row.tries == 0
            and interactive_row.seconds == 0
            and interactive_row.response_status == "unanswered"
            and interactive_row.response_json is None
            and interactive_quest.answered_count == 0,
            interactive_row,
        )
        wrong_interactive = quests.submit_answer(
            gcse,
            interactive_quest,
            interactive_row.id,
            response={"type": "coordinate_points", "points": [[2, 2]]},
            seconds=4,
        )
        check(
            "wrong interactive answers use the normal second chance",
            wrong_interactive.get("status") == "retry"
            and interactive_row.tries == 1
            and interactive_quest.answered_count == 0,
            wrong_interactive,
        )
        target_response = (interactive_row.solution or {}).get("response_answer")
        correct_interactive = quests.submit_answer(
            gcse,
            interactive_quest,
            interactive_row.id,
            response=target_response,
            seconds=3,
        )
        check(
            "correct interactive answers are automatically scored",
            correct_interactive.get("status") == "correct"
            and interactive_row.is_correct is True
            and interactive_row.response_status == "scored"
            and interactive_quest.answered_count == 1
            and interactive_quest.correct_count == 1,
            correct_interactive,
        )
        interactive_progress = db.session.execute(
            db.select(SkillProgress).where(
                SkillProgress.child_id == gcse.id,
                SkillProgress.skill_id == interactive_row.skill_id,
            )
        ).scalar_one()
        check(
            "interactive responses persist normalized JSON and mastery",
            interactive_row.response_json
            == {"type": "coordinate_points", "points": [[2.0, 3.0]]}
            and interactive_row.given_answer == "(2, 3)"
            and interactive_progress.attempts == 1
            and interactive_progress.correct == 1
            and interactive_progress.mastery > 0,
            (interactive_row.response_json, interactive_progress.mastery),
        )

        print("\nPrimary learner response flow")
        composition_quest = quests.start_quest(
            primary,
            subject="english",
            mode="skill",
            count=4,
            skill_id="e1.write.composition",
            rng=random.Random(4),
        )
        composition_row = composition_quest.questions[0]
        public = quests.quest_payload(composition_quest, primary)["questions"][0]
        public_text = str(public)
        check(
            "learner payload exposes response controls but not review data",
            "response_spec" in public
            and "assessment" not in public
            and "criteria" not in public_text
            and "mark_scheme" not in public_text
            and "answer" not in public,
            public,
        )
        short = quests.submit_answer(
            primary,
            composition_quest,
            composition_row.id,
            response={"text": "too short"},
            seconds=2,
        )
        check("short composition is rejected server-side", "error" in short, short)
        check(
            "rejected composition does not become answered",
            not composition_row.is_answered and composition_row.tries == 0,
            composition_row.response_status,
        )

        saved = quests.submit_answer(
            primary,
            composition_quest,
            composition_row.id,
            response={"text": "This is a long enough composition with clear ideas."},
            seconds=7,
        )
        check(
            "composition is saved as pending review",
            saved.get("status") == "submitted"
            and composition_row.is_pending
            and composition_quest.answered_count == 1,
            saved,
        )
        check(
            "pending composition creates no mastery row",
            db.session.execute(
                db.select(SkillProgress).where(
                    SkillProgress.child_id == primary.id,
                    SkillProgress.skill_id == composition_row.skill_id,
                )
            ).scalar_one_or_none()
            is None,
        )
        composition_summary = quests.finish_quest(
            primary, composition_quest, rng=random.Random(5)
        )
        check(
            "finished quest summary labels pending response",
            composition_summary["pending"] == 1
            and composition_summary["answered"] == 1
            and composition_summary["correct"] == 0,
            composition_summary,
        )

        review_scores = {
            criterion["id"]: criterion["max"]
            for criterion in (composition_row.solution or {}).get("assessment", {}).get("criteria", [])
        }
        review_result = quests.record_assessment_review(
            primary,
            composition_quest.id,
            composition_row.id,
            review_scores,
            "Clear ideas and a strong ending.",
        )
        check(
            "parent review applies once and marks the response",
            review_result.get("ok")
            and composition_row.response_status == "reviewed"
            and composition_row.is_correct is True
            and composition_row.score == composition_row.max_score,
            review_result,
        )
        progress_after_review = db.session.execute(
            db.select(SkillProgress).where(
                SkillProgress.child_id == primary.id,
                SkillProgress.skill_id == composition_row.skill_id,
            )
        ).scalar_one()
        attempts_after_review = progress_after_review.attempts
        repeated_review = quests.record_assessment_review(
            primary,
            composition_quest.id,
            composition_row.id,
            review_scores,
        )
        check("repeated parent review is rejected", "error" in repeated_review, repeated_review)
        db.session.refresh(progress_after_review)
        check(
            "repeated review does not double-count mastery",
            progress_after_review.attempts == attempts_after_review,
            progress_after_review.attempts,
        )

        handwriting_quest = quests.start_quest(
            primary,
            subject="english",
            mode="skill",
            count=4,
            skill_id="e1.write.handwriting",
            rng=random.Random(6),
        )
        handwriting_row = handwriting_quest.questions[0]
        pending_result = quests.submit_answer(
            primary,
            handwriting_quest,
            handwriting_row.id,
            response={"text": "Typed handwriting fallback"},
            seconds=5,
        )
        quests.finish_quest(primary, handwriting_quest, rng=random.Random(7))
        check("handwriting fallback is stored as pending", pending_result.get("pending") is True)

        before_rebuild = maintenance.stored_summary(primary)
        rebuild = maintenance.rebuild_derived(primary)
        after_rebuild = maintenance.stored_summary(primary)
        subject_rows = {row["id"]: row for row in maintenance.subject_summary(primary)}
        progress_ids = {
            row.skill_id
            for row in db.session.execute(
                db.select(SkillProgress).where(SkillProgress.child_id == primary.id)
            ).scalars()
        }
        check(
            "rebuild retains pending answers as answered activity",
            rebuild["answers"] == 2
            and after_rebuild["questions"] == before_rebuild["questions"] == 2
            and subject_rows["english"]["questions"] == 2,
            (rebuild, before_rebuild, after_rebuild, subject_rows),
        )
        check(
            "rebuild excludes pending responses from mastery",
            "e1.write.handwriting" not in progress_ids
            and "e1.write.composition" in progress_ids,
            progress_ids,
        )
        activity = db.session.execute(
            db.select(DailyActivity).where(DailyActivity.child_id == primary.id)
        ).scalars().all()
        check(
            "rebuild preserves pending question activity without false correctness",
            sum(row.questions for row in activity) == 2
            and sum(row.correct for row in activity) == 1,
            [(row.questions, row.correct) for row in activity],
        )

        print("\nGCSE board and pathway contracts")
        warnings = profiles.apply_settings(
            gcse.settings,
            MultiDict([("gcse_tier", "higher"), ("gcse_board", "aqa")]),
        )
        db.session.commit()
        check("GCSE board setting saves without a settings error", gcse.settings.gcse_board == "aqa", warnings)
        higher_ids = {skill.id for skill in gcse_skills_for("higher")}
        foundation_ids = {skill.id for skill in gcse_skills_for("foundation")}
        higher_only = higher_ids - foundation_ids
        check("Foundation has a strict subset of Higher skills", bool(higher_only))
        check(
            "Primary active skills never include GCSE skills",
            all(not skill.is_gcse for skill in pathways.active_skills(primary.settings)),
        )
        check(
            "Foundation authorization excludes Higher-only skills",
            not (pathways.active_skill_ids(foundation.settings) & higher_only),
        )
        try:
            quests.subject_for_path(gcse, "english")
        except ValueError:
            check("GCSE learner cannot request a Primary subject", True)
        else:
            check("GCSE learner cannot request a Primary subject", False)

        board_questions = [
            draw_question(
                skill.id,
                random.Random(index + 20),
                tier="higher",
                board="aqa",
            )
            for index, skill in enumerate(gcse_skills_for("higher"))
        ]
        check(
            "board snapshots carry exam context",
            all(
                question.get("exam", {}).get("board") == "aqa"
                and question["exam"].get("paper_label")
                and question["exam"].get("marks")
                and question["exam"].get("command_word")
                and question["exam"].get("assessment_objective")
                for question in board_questions
            ),
        )
        check(
            "non-generic board style offers typed short-answer questions",
            any(question.get("kind") == "text" for question in board_questions),
        )
        board_payload, board_solution = split_question(board_questions[0])
        check(
            "GCSE mark scheme stays server-side",
            "mark_scheme" not in board_payload and "mark_scheme" in board_solution,
            board_solution,
        )

        board_quest = quests.start_quest(
            gcse,
            subject="gcse_maths",
            mode="mixed",
            count=4,
            rng=random.Random(30),
        )
        board_payload = quests.quest_payload(board_quest, gcse)
        check(
            "selected board is snapshotted into the quest",
            board_payload["exam_board"] == "aqa"
            and all(q.get("exam", {}).get("board") == "aqa" for q in board_payload["questions"]),
            board_payload,
        )
        check(
            "board selection does not widen tier authorization",
            {skill.id for skill in pathways.active_skills(gcse.settings)} == higher_ids,
        )
        gcse.settings.gcse_board = "generic"
        db.session.commit()
        check(
            "changing board leaves the authorized skill ids unchanged",
            {skill.id for skill in pathways.active_skills(gcse.settings)} == higher_ids,
        )

    print(f"\nAssessment checks: {CHECKS} run, {len(FAILURES)} failed")
    if FAILURES:
        for failure in FAILURES:
            print(f"  - {failure}")
    tmp.cleanup()
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
