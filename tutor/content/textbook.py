"""The Year 3 Maths Guided Trail textbook.

The textbook is deliberately separate from the adaptive quest selector: it
teaches a fixed, parent-readable sequence, while each practice button hands
back to the existing quest engine for fresh generated questions, server-side
marking, XP, mastery and spaced repetition.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from .curriculum import get_skill, skills_for
from .textbook_guides import GUIDES


@dataclass(frozen=True)
class Drill:
    label: str
    count: int
    detail: str
    tone: str
    profile: str


@dataclass(frozen=True)
class Representation:
    label: str
    purpose: str
    alt: str
    visual: dict[str, object]


@dataclass(frozen=True)
class WorkedStep:
    label: str
    text: str


@dataclass(frozen=True)
class GuidedExample:
    problem: str
    prompt: str
    hint: str


@dataclass(frozen=True)
class ErrorExample:
    wrong: str
    prompt: str
    repair: str


@dataclass(frozen=True)
class TransferPair:
    same_structure: str
    same_context: str


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    skill_id: str
    summary: str
    explanation: str
    example: str
    watch_out: str
    activate: str
    representation: Representation
    worked_steps: tuple[WorkedStep, ...]
    guided_example: GuidedExample
    error_example: ErrorExample
    strategy_prompt: str
    transfer: TransferPair
    reflection_prompt: str
    related_skill_ids: tuple[str, ...]
    drills: tuple[Drill, ...] = (
        Drill("Warm up", 6, "One structure · gentle", "leaf", "warm_up"),
        Drill("Build it", 10, "Same idea · new settings", "ocean", "build"),
        Drill("Prove it", 15, "Choose · transfer · check", "berry", "prove"),
    )


@dataclass(frozen=True)
class Unit:
    id: str
    title: str
    blurb: str
    colour: str
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class LessonStage:
    number: int
    slug: str
    title: str
    subtitle: str


LESSON_STAGES: tuple[LessonStage, ...] = (
    LessonStage(1, "remember", "Remember first", "Wake up a useful idea"),
    LessonStage(2, "see", "See the maths", "Connect the picture to the numbers"),
    LessonStage(3, "watch", "Watch the method", "Notice each decision"),
    LessonStage(4, "try", "Try one step", "Finish a partly completed example"),
    LessonStage(5, "spot", "Spot the mistake", "Repair a common mix-up"),
    LessonStage(6, "choose", "Choose a method", "Use the idea in a new situation"),
    LessonStage(7, "think-practise", "Think back and practise", "Say what you noticed, then have a go"),
)


def lesson_stages() -> list[dict[str, object]]:
    """Return learner-safe metadata for the fixed lesson sequence."""
    return [asdict(stage) for stage in LESSON_STAGES]


def _step(
    step_id: str,
    title: str,
    skill_id: str,
    summary: str,
    explanation: str,
    example: str,
    watch_out: str,
) -> Step:
    guide = GUIDES[step_id]
    return Step(
        id=step_id,
        title=title,
        skill_id=skill_id,
        summary=summary,
        explanation=explanation,
        example=example,
        watch_out=watch_out,
        activate=guide["activate"],
        representation=Representation(**guide["representation"]),
        worked_steps=tuple(WorkedStep(**item) for item in guide["worked_steps"]),
        guided_example=GuidedExample(**guide["guided_example"]),
        error_example=ErrorExample(**guide["error_example"]),
        strategy_prompt=guide["strategy_prompt"],
        transfer=TransferPair(**guide["transfer"]),
        reflection_prompt=guide["reflection_prompt"],
        related_skill_ids=tuple(guide["related_skill_ids"]),
    )


# Eight short units keep the route scannable while retaining every Year 3
# Maths objective. The skill ids are the app's durable progress keys.
YEAR3_MATHS_UNITS: tuple[Unit, ...] = (
    Unit(
        "number-detectives",
        "Number Detectives",
        "See what every digit is doing, then use that structure to compare, count and round.",
        "ocean",
        (
            _step(
                "hundreds-tens-ones",
                "Hundreds, tens and ones",
                "m3.pv.hundreds",
                "Build three-digit numbers from the value of each place.",
                "Read a three-digit number from left to right. The first digit counts hundreds, the second counts tens and the last counts ones. Split the number into parts to check its value.",
                "352 = 300 + 50 + 2\nThe 5 is worth 50 because it is in the tens place.",
                "A digit does not always have the same value: its place matters.",
            ),
            _step(
                "compare-order-1000",
                "Compare and order to 1000",
                "m3.pv.compare-order",
                "Use place value to decide which number is greater or smaller.",
                "Compare hundreds first. If they match, compare tens. If those match, compare ones. To order a list, find the smallest number first and keep checking each place.",
                "708 > 680 because 7 hundreds is more than 6 hundreds.\n245, 254, 425 is ascending order.",
                "Do not compare only the last digit; start with the highest place.",
            ),
            _step(
                "count-jumps",
                "Count in 4s, 8s, 50s and 100s",
                "m3.pv.count-steps",
                "Keep a steady jump size in a number sequence.",
                "Say the jump before you begin, then add the same amount each time. Use known facts such as 4 × 6 = 24 to check a count in 4s.",
                "0, 8, 16, 24, 32 ... counts in 8s.\n250, 300, 350, 400 ... counts in 50s.",
                "Keep the jump size visible; accidentally changing it changes the whole sequence.",
            ),
            _step(
                "rounding",
                "Rounding to 10 and 100",
                "m3.pv.round",
                "Make a nearby number that is easier to use.",
                "To round to the nearest 10, look at the ones digit. To round to the nearest 100, look at the tens digit. Five or more rounds up; four or less stays down.",
                "347 → 350 to the nearest 10.\n347 → 300 to the nearest 100.",
                "The digit you inspect is one place to the right of the place you are rounding to.",
            ),
        ),
    ),
    Unit(
        "add-subtract",
        "Add & Subtract",
        "Choose a sensible method, keep place values lined up, and check your answer.",
        "leaf",
        (
            _step(
                "mental-add-sub",
                "Adding in your head",
                "m3.calc.mental-add-sub",
                "Split numbers into hundreds, tens and ones for quick mental steps.",
                "Add or subtract the easy place-value part first. If the answer crosses a ten or hundred, bridge through it in a second step.",
                "238 + 40 = 278\n238 + 7 = 245\n238 + 47 = 238 + 40 + 7 = 285.",
                "Keep track of whether you added tens, ones or hundreds; do not mix their values.",
            ),
            _step(
                "column-addition",
                "Column addition",
                "m3.calc.add-3digit",
                "Line up ones, tens and hundreds before adding from the right.",
                "Write one number below the other with matching place values. Add the ones, carry a ten when needed, then add tens and hundreds.",
                "  247\n+ 136\n────\n  383\n7 + 6 makes 13, so write 3 and carry 1.",
                "A shifted column changes the place value and gives the wrong answer.",
            ),
            _step(
                "column-subtraction",
                "Column subtraction",
                "m3.calc.sub-3digit",
                "Subtract from the right and exchange when the top digit is too small.",
                "Line up place values. Subtract ones first. If the top ones digit is smaller, exchange one ten for ten ones, then continue with tens and hundreds.",
                "  526\n− 187\n────\n  339\nExchange one ten when 6 ones cannot subtract 7; then exchange one hundred when the tens column needs more.",
                "Check which column needs an exchange; do not exchange every column automatically.",
            ),
            _step(
                "missing-add-sub",
                "Missing numbers",
                "m3.calc.missing-number",
                "Use the inverse operation to find a missing part.",
                "Addition and subtraction are inverse operations. Turn a missing addition into a subtraction, or use the fact family to test the missing value.",
                "47 + □ = 82\n82 − 47 = 35\nSo □ = 35.",
                "Put the answer back into the original equation to check it.",
            ),
            _step(
                "estimate-check",
                "Estimate and check",
                "m3.calc.estimate-check",
                "Predict a sensible size, calculate exactly, then use the inverse.",
                "Round the numbers to get an estimate before using the formal method. After calculating, use the inverse operation to see whether the result returns to the starting number.",
                "398 + 204 is about 400 + 200 = 600.\nExact answer: 602.\n602 − 204 = 398.",
                "An estimate is a reasonableness check, not the exact answer.",
            ),
            _step(
                "two-step-add-sub",
                "Two-step problems",
                "m3.calc.add-sub-problems",
                "Solve one step, keep the new total, then solve the next step.",
                "Read the story carefully. Underline what changes first, calculate that step, write the new amount, and use it in the second step. Label the answer with the right unit.",
                "28 books + 15 = 43\n43 books − 9 = 34 books.",
                "Do not combine every number without deciding what happens first.",
            ),
        ),
    ),
    Unit(
        "multiply-share",
        "Multiply & Share",
        "Build tables from patterns, connect multiplication with division, and explain remainders.",
        "sun",
        (
            _step(
                "times-three",
                "The 3 times table",
                "m3.mult.times-3",
                "Count equal groups of three and use the related facts.",
                "Each next fact adds another group of three. Link multiplication and division facts so one known fact gives four useful facts.",
                "3 × 7 = 21\n7 × 3 = 21\n21 ÷ 3 = 7\n21 ÷ 7 = 3.",
                "The order of factors can change, but the answer stays the same.",
            ),
            _step(
                "times-four",
                "The 4 times table",
                "m3.mult.times-4",
                "Double twice to make groups of four.",
                "A group of four is two groups of two. Use doubling twice, skip-counting, or a known 2 times table fact.",
                "4 × 6 = 2 × 6 doubled = 12 doubled = 24.",
                "Do not confuse 4 × 6 with 4 + 6; multiplication means equal groups.",
            ),
            _step(
                "times-eight",
                "The 8 times table",
                "m3.mult.times-8",
                "Double three times to make groups of eight.",
                "An 8 times table fact can be built by doubling a number three times. Notice the pattern in the ones digits as a memory check.",
                "8 × 6 = 48\n6 doubled is 12, then 24, then 48.",
                "Use the factor 8, not a nearby 6 or 7 fact.",
            ),
            _step(
                "divide-3-4-8",
                "Divide by 3, 4 and 8",
                "m3.mult.divide-3-4-8",
                "Use the matching multiplication fact to solve a division fact.",
                "Ask, “How many groups?” or “How many in each group?” Then use the related table. Division undoes multiplication.",
                "32 ÷ 4 = 8 because 4 × 8 = 32.",
                "Read the division sign in order: the first number is being shared or grouped.",
            ),
            _step(
                "two-digit-times-one",
                "Two-digit times one-digit",
                "m3.mult.two-digit",
                "Partition the two-digit number, multiply each part, then combine.",
                "Split tens and ones so each multiplication is familiar. Add the partial products. A written layout keeps the place values safe when the answer is larger.",
                "23 × 4 = (20 × 4) + (3 × 4)\n= 80 + 12 = 92.",
                "The 2 in 23 means 20, not 2, when it is multiplied.",
            ),
            _step(
                "remainders",
                "Sharing with leftovers",
                "m3.mult.remainders",
                "Find full groups first, then name what is left over.",
                "Use the largest multiplication fact that does not go over. The remainder must be smaller than the divisor, because one more full group would be possible otherwise.",
                "17 ÷ 5 = 3 remainder 2\n5 × 3 = 15, with 2 left.",
                "A remainder is not automatically a decimal; read the story to decide what it means.",
            ),
            _step(
                "scaling",
                "Scaling problems",
                "m3.mult.scaling",
                "Find the scale factor, then apply it to the matching amount.",
                "Compare the known groups or lengths. If one is twice as large, double the other amount; if it is three times as large, multiply by three.",
                "3 packs hold 12 apples.\n6 packs are twice as many, so they hold 24 apples.",
                "Scale every matching quantity by the same factor.",
            ),
            _step(
                "multiply-division-problems",
                "Multiplication and division stories",
                "m3.mult.problem-solving",
                "Translate equal groups, sharing or correspondence into an operation.",
                "Draw a quick array or list the groups. Decide whether the story asks for the total, the number of groups, or the amount in each group before calculating.",
                "6 bags × 8 apples = 48 apples.\nThe word “each” signals equal groups.",
                "Do not choose an operation only because a keyword appears; picture the groups first.",
            ),
        ),
    ),
    Unit(
        "fraction-lab",
        "Fraction Lab",
        "Use equal parts, number lines and the denominator to reason about fractions.",
        "grape",
        (
            _step(
                "tenths",
                "Tenths",
                "m3.frac.tenths",
                "One whole split into ten equal parts gives tenths.",
                "The denominator tells how many equal parts make the whole. One tenth is 0.1, so count in tenths by adding 0.1 each time.",
                "0.1, 0.2, 0.3 ... 1.0\n10 tenths = 1 whole.",
                "Tenths are equal parts; ten uneven pieces do not make ten tenths.",
            ),
            _step(
                "fraction-of-amount",
                "Fractions of amounts",
                "m3.frac.of-amount",
                "Divide by the denominator, then multiply by the numerator.",
                "First find one equal part by dividing the whole amount by the denominator. Then take the required number of those parts.",
                "3/4 of 20: 20 ÷ 4 = 5, then 5 × 3 = 15.",
                "Divide first; multiplying by the numerator before sharing can hide the equal parts.",
            ),
            _step(
                "equivalent-fractions",
                "Equivalent fractions",
                "m3.frac.equivalent",
                "Different names can describe the same amount.",
                "Multiply or divide the numerator and denominator by the same non-zero number. A diagram or number line should show that the amount has not changed.",
                "1/2 = 2/4 = 4/8\nThe parts get smaller, but the shaded amount stays half.",
                "Change both numerator and denominator together.",
            ),
            _step(
                "fraction-add-sub",
                "Adding and subtracting fractions",
                "m3.frac.add-sub",
                "When denominators match, combine only the numerators.",
                "The denominator names the size of each part, so it stays the same. Add or subtract the number of equal parts.",
                "2/7 + 3/7 = 5/7\nThe sevenths stay sevenths.",
                "Never add the denominators when the parts already have the same size.",
            ),
            _step(
                "compare-fractions",
                "Comparing fractions",
                "m3.frac.compare",
                "Use the denominator and numerator to compare the size of parts.",
                "With the same denominator, the larger numerator is larger. For unit fractions with numerator 1, more equal parts means each part is smaller.",
                "5/8 > 3/8 because there are more eighths.\n1/4 > 1/8 because quarters are larger parts than eighths.",
                "A larger denominator does not always mean a larger fraction.",
            ),
            _step(
                "unit-nonunit",
                "Unit and non-unit fractions",
                "m3.frac.unit-nonunit",
                "Spot whether the numerator is one or more than one.",
                "A unit fraction has numerator 1: it is one equal part. A non-unit fraction has two or more equal parts named by its numerator.",
                "1/6 is a unit fraction.\n3/6 is a non-unit fraction.",
                "Look at the numerator, the top number, not the denominator.",
            ),
        ),
    ),
    Unit(
        "measure-it",
        "Measure It",
        "Choose sensible units, convert carefully, and connect area, perimeter and temperature to pictures.",
        "leaf",
        (
            _step(
                "length-units",
                "Millimetres, centimetres and metres",
                "m3.meas.length",
                "Choose a length unit and convert between nearby units.",
                "Use 10 millimetres = 1 centimetre and 100 centimetres = 1 metre. Estimate the size first so the answer is sensible.",
                "4 cm = 40 mm\n2 m = 200 cm.",
                "Do not write a conversion number without changing the unit label too.",
            ),
            _step(
                "mass-capacity",
                "Grams, kilograms, millilitres",
                "m3.meas.mass-capacity",
                "Measure mass and capacity with the correct unit family.",
                "Mass uses grams and kilograms; capacity uses millilitres and litres. Use 1000 g = 1 kg and 1000 ml = 1 l, then compare like with like.",
                "2 kg = 2000 g\n750 ml is less than 1 litre.",
                "Kilograms measure mass; litres measure capacity. Do not swap the families.",
            ),
            _step(
                "estimate-measures",
                "Estimate measures",
                "m3.meas.estimate",
                "Choose a close, sensible measure before measuring exactly.",
                "Use familiar benchmarks: a pencil is about 15 cm, a door is about 2 m, and a bottle may hold about 500 ml. Reject choices that are far too big or too small.",
                "A classroom door is about 2 metres high, not 2 centimetres.",
                "Estimate the object itself, not a number that merely looks tidy.",
            ),
            _step(
                "area-counting-squares",
                "Area by counting squares",
                "m3.meas.area",
                "Area tells how much surface is covered.",
                "Count every equal square, or count rows and columns when the arrangement is regular. Write square units because area covers a surface.",
                "4 rows of 6 squares = 4 × 6 = 24 square units.",
                "Perimeter measures around; area measures the space inside.",
            ),
            _step(
                "perimeter",
                "Perimeter",
                "m3.meas.perimeter",
                "Perimeter is the total distance around a shape.",
                "Add every outside side. For a rectangle, opposite sides match, so add length + width + length + width or double the pair.",
                "A 6 cm by 4 cm rectangle has perimeter\n6 + 4 + 6 + 4 = 20 cm.",
                "Use ordinary length units for perimeter, not square units.",
            ),
            _step(
                "temperature-changes",
                "Temperature changes",
                "m3.meas.temperature",
                "Use a number line to find how much warmer or colder.",
                "For a rise, count forward from the starting temperature. For a fall, count backward. The difference is the distance between the two temperatures.",
                "From 4°C to 11°C is a rise of 7°C.\nFrom 3°C to −2°C is a fall of 5°C.",
                "A change can be positive or negative; state whether it is a rise or a fall.",
            ),
        ),
    ),
    Unit(
        "time-money",
        "Time & Money",
        "Read clocks, calculate durations and use pounds and pence in real situations.",
        "sun",
        (
            _step(
                "money-problems",
                "Money problems",
                "m3.meas.money",
                "Keep pounds and pence aligned when adding, subtracting or finding change.",
                "Convert to pence or line up decimal points so each amount uses the same unit. For change, subtract the price from the amount paid and check by adding back.",
                "£5 and 0p − £3 and 75p = £1 and 25p\nCheck: £3 and 75p + £1 and 25p = £5.",
                "£1.2 means £1.20; always show two pence digits when writing money.",
            ),
            _step(
                "time-to-minute",
                "Time to the minute",
                "m3.meas.time-minute",
                "Read the minute hand first, then the hour hand.",
                "Each small mark is one minute. The hour hand sits between numbers after the hour has begun, so use the number it has most recently passed.",
                "Minute hand on 7 = 35 minutes.\nThe hour hand just past 4 means 4:35.",
                "The hour hand does not jump to the next number at :30.",
            ),
            _step(
                "time-facts",
                "Time facts",
                "m3.meas.time-units",
                "Recall the common relationships between seconds, minutes, days and months.",
                "Use 60 seconds = 1 minute, 60 minutes = 1 hour, 24 hours = 1 day and 7 days = 1 week. Remember that months have different lengths.",
                "2 minutes = 120 seconds.\nA leap year has 366 days.",
                "Do not assume every month has the same number of days.",
            ),
            _step(
                "time-duration",
                "How long?",
                "m3.meas.time-duration",
                "Find elapsed time by moving along a timeline.",
                "Count to the next hour, add whole hours, then add remaining minutes. Draw a timeline when the start and end times cross an hour.",
                "09:45 → 10:00 is 15 minutes;\n10:00 → 10:30 is 30 minutes; total 45 minutes.",
                "Duration is the amount of time between two times, not the end time itself.",
            ),
            _step(
                "roman-clock",
                "Roman numerals on a clock",
                "m3.meas.roman",
                "Recognise I to XII when a clock face uses Roman numerals.",
                "Match each Roman numeral to its ordinary number: I=1, V=5, X=10. On a clock, the hour positions continue around the face from I to XII.",
                "VIII is 8, so the hour hand pointing to VIII shows eight o'clock.",
                "Read the clock position as an hour number; do not treat XII as an ordinary zero.",
            ),
        ),
    ),
    Unit(
        "shape-space",
        "Shape & Space",
        "Use turns, line relationships and properties to describe shapes precisely.",
        "berry",
        (
            _step(
                "angles-turns",
                "Right angles and turns",
                "m3.geo.angles",
                "Use a right angle as the 90-degree benchmark.",
                "A quarter turn is 90°, a half turn is 180° and a full turn is 360°. Compare an angle with a square corner to decide whether it is smaller or larger.",
                "Quarter turn = 90°\nHalf turn = 180°\nA 60° angle is less than a right angle.",
                "The direction of a turn and the size of an angle are related but not identical ideas.",
            ),
            _step(
                "parallel-perpendicular",
                "Parallel and perpendicular lines",
                "m3.geo.lines",
                "Describe whether lines stay apart or meet at a right angle.",
                "Parallel lines remain the same distance apart and never meet. Perpendicular lines meet at 90°. A pair can be horizontal, vertical, parallel or perpendicular.",
                "The opposite edges of a rectangle are parallel.\nAdjacent edges are perpendicular.",
                "Lines can be parallel even when they are vertical or slanted; they do not have to be horizontal.",
            ),
            _step(
                "naming-shapes",
                "Naming shapes",
                "m3.geo.shapes",
                "Use sides, vertices and faces to recognise shapes in any orientation.",
                "Count the sides and vertices of 2-D shapes. For 3-D shapes, notice faces, edges and vertices. Turning a shape does not change its name.",
                "A triangle has 3 sides and 3 vertices.\nA cuboid has rectangular faces.",
                "A shape is still the same shape when it is rotated or drawn in a new position.",
            ),
            _step(
                "classify-shapes",
                "Classify shapes",
                "m3.geo.classify",
                "Group shapes by shared properties, not by how they look in one drawing.",
                "A quadrilateral has four sides. Use properties such as equal sides, right angles and parallel sides to explain why a shape belongs in a group.",
                "A rectangle is a quadrilateral because it has four sides.\nA square is also a quadrilateral.",
                "Categories can overlap: a square can belong to more than one shape family.",
            ),
        ),
    ),
    Unit(
        "data-detectives",
        "Data Detectives",
        "Read what a table or chart says, then explain comparisons and totals in words.",
        "grape",
        (
            _step(
                "bar-charts-tables",
                "Bar charts and tables",
                "m3.stats.bar-chart",
                "Use the labels and scale before reading a value.",
                "Read the title, category labels and scale. Check whether one bar step represents one item or several. Tables organise the same information in rows and columns.",
                "If each bar step is 2, a bar reaching 5 steps represents 10.\nAlways read the scale first.",
                "A bar height is not the answer until you have checked the scale.",
            ),
            _step(
                "interpret-charts",
                "Interpret tables and charts",
                "m3.stats.interpret",
                "Answer totals, differences and comparison questions from data.",
                "Translate the question into an operation: total means add, difference means subtract, and “how many more” means compare two values. Explain the result with the data labels.",
                "12 children chose red and 8 chose blue.\nTotal = 12 + 8 = 20 children.",
                "Include the category or unit in the answer so the number has meaning.",
            ),
        ),
    ),
)


def all_steps() -> tuple[Step, ...]:
    """Return the trail in teaching order."""
    return tuple(step for unit in YEAR3_MATHS_UNITS for step in unit.steps)


def validate_textbook() -> list[str]:
    """Return authoring problems for the fixed Year 3 textbook map."""
    problems: list[str] = []
    units = YEAR3_MATHS_UNITS
    steps = all_steps()
    expected = {skill.id for skill in skills_for("maths", [3])}
    mapped = [step.skill_id for step in steps]
    step_skill_ids = {step.id: step.skill_id for step in steps}
    valid_visuals = {
        "angle",
        "array",
        "bar_chart",
        "blocks",
        "clock",
        "coins",
        "column",
        "fraction",
        "fraction_pair",
        "lines",
        "number_line",
        "partition",
        "rect",
        "roman_clock",
        "shape2d",
        "share",
    }
    valid_profiles = {"warm_up", "build", "prove"}

    if len(units) != 8:
        problems.append(f"expected 8 units, found {len(units)}")
    if len(steps) != 41:
        problems.append(f"expected 41 steps, found {len(steps)}")

    seen_steps: set[str] = set()
    for unit in units:
        if not unit.id or not unit.title or not unit.blurb:
            problems.append("every unit needs an id, title and blurb")
        if not unit.steps:
            problems.append(f"unit {unit.id!r} has no steps")
        for step in unit.steps:
            if step.id in seen_steps:
                problems.append(f"duplicate textbook step id {step.id!r}")
            seen_steps.add(step.id)
            for field_name in (
                "title",
                "summary",
                "explanation",
                "example",
                "watch_out",
                "activate",
                "strategy_prompt",
                "reflection_prompt",
            ):
                if not getattr(step, field_name).strip():
                    problems.append(f"step {step.id!r} has empty {field_name}")

            representation = step.representation
            if not representation.label.strip():
                problems.append(f"step {step.id!r} has no representation label")
            if not representation.purpose.strip():
                problems.append(f"step {step.id!r} has no representation purpose")
            if not representation.alt.strip():
                problems.append(f"step {step.id!r} has no representation alt text")
            visual_type = representation.visual.get("type")
            if visual_type not in valid_visuals:
                problems.append(
                    f"step {step.id!r} has unsupported representation visual {visual_type!r}"
                )

            if len(step.worked_steps) < 2:
                problems.append(f"step {step.id!r} needs at least two narrated worked steps")
            for worked in step.worked_steps:
                if not worked.label.strip() or not worked.text.strip():
                    problems.append(f"step {step.id!r} has an incomplete worked step")
            for field_name in ("problem", "prompt", "hint"):
                if not getattr(step.guided_example, field_name).strip():
                    problems.append(f"step {step.id!r} has incomplete guided example {field_name}")
            for field_name in ("wrong", "prompt", "repair"):
                if not getattr(step.error_example, field_name).strip():
                    problems.append(f"step {step.id!r} has incomplete error example {field_name}")
            for field_name in ("same_structure", "same_context"):
                if not getattr(step.transfer, field_name).strip():
                    problems.append(f"step {step.id!r} has incomplete transfer pair {field_name}")

            skill = get_skill(step.skill_id)
            if skill is None:
                problems.append(f"step {step.id!r} references unknown skill {step.skill_id!r}")
            elif skill.subject != "maths" or skill.year != 3:
                problems.append(
                    f"step {step.id!r} references non-Year-3-Maths skill {step.skill_id!r}"
                )
            for related_id in step.related_skill_ids:
                related_skill_id = step_skill_ids.get(related_id, related_id)
                related = get_skill(related_skill_id)
                if related is None:
                    problems.append(
                        f"step {step.id!r} references unknown related skill {related_id!r}"
                    )
                elif related.subject != "maths" or related.year != 3:
                    problems.append(
                        f"step {step.id!r} references non-Year-3-Maths related skill {related_id!r}"
                    )
                if related_skill_id == step.skill_id:
                    problems.append(f"step {step.id!r} relates to itself")

            if len(step.drills) != 3:
                problems.append(f"step {step.id!r} needs three drill levels")
            profiles = set()
            for drill in step.drills:
                profiles.add(drill.profile)
                if drill.profile not in valid_profiles:
                    problems.append(
                        f"step {step.id!r} drill {drill.label!r} has invalid profile {drill.profile!r}"
                    )
                if not 4 <= drill.count <= 15:
                    problems.append(
                        f"step {step.id!r} drill {drill.label!r} must request 4–15 questions"
                    )
            if profiles != valid_profiles:
                problems.append(f"step {step.id!r} needs warm_up, build and prove profiles")

    if len(mapped) != len(set(mapped)):
        problems.append("each Year 3 Maths skill must map to one textbook step")
    missing = sorted(expected - set(mapped))
    extra = sorted(set(mapped) - expected)
    if missing:
        problems.append(f"missing Year 3 Maths skills: {', '.join(missing)}")
    if extra:
        problems.append(f"textbook references non-catalogue skills: {', '.join(extra)}")
    return problems


def _step_status(row, spaced_days: int | None = None) -> tuple[str, str]:
    if row is None or not row.attempts:
        return "new", "Not started"
    if row.attempts >= 4 and row.mastery >= 0.85:
        if spaced_days is None or spaced_days >= 2:
            return "ready", "Ready to mix"
        return "working", "Review once later"
    return "working", "Keep practising"


def trail_view(
    progress: Mapping[str, object],
    spaced_days: Mapping[str, int] | None = None,
) -> dict:
    """Build the Jinja-safe trail view from existing skill progress rows.

    ``spaced_days`` is derived from answered quest questions. When supplied,
    the visible ready state requires successful retrieval on at least two
    different days; the optional argument keeps this pure content helper
    backwards-compatible for callers that only have progress rows.
    """
    steps = all_steps()
    step_skill_ids = {step.id: step.skill_id for step in steps}
    ready_steps = 0
    current_step_id = next(
        (
            step.id
            for step in steps
            if _step_status(
                progress.get(step.skill_id),
                None if spaced_days is None else spaced_days.get(step.skill_id, 0),
            )[0]
            != "ready"
        ),
        steps[-1].id,
    )
    units: list[dict] = []

    for unit in YEAR3_MATHS_UNITS:
        step_views: list[dict] = []
        unit_ready = 0
        for step in unit.steps:
            row = progress.get(step.skill_id)
            review_days = None if spaced_days is None else spaced_days.get(step.skill_id, 0)
            status, status_label = _step_status(row, review_days)
            attempts = int(getattr(row, "attempts", 0) or 0)
            mastery = round(float(getattr(row, "mastery", 0) or 0) * 100)
            accuracy = round(float(getattr(row, "accuracy", 0) or 0) * 100)
            if status == "ready":
                ready_steps += 1
                unit_ready += 1
            step_view = asdict(step)
            step_view["related_skill_ids"] = [
                step_skill_ids.get(related_id, related_id)
                for related_id in step.related_skill_ids
            ]
            step_view.update(
                {
                    "status": status,
                    "status_label": status_label,
                    "attempts": attempts,
                    "mastery": mastery,
                    "accuracy": accuracy,
                    "spaced_review_days": review_days,
                    "is_current": step.id == current_step_id,
                }
            )
            step_views.append(step_view)
        units.append(
            {
                "id": unit.id,
                "title": unit.title,
                "blurb": unit.blurb,
                "colour": unit.colour,
                "steps": step_views,
                "ready_steps": unit_ready,
                "total_steps": len(unit.steps),
                "is_current": any(step["is_current"] for step in step_views),
            }
        )

    total_steps = len(steps)
    return {
        "units": units,
        "total_steps": total_steps,
        "ready_steps": ready_steps,
        "overall_pct": round(ready_steps / total_steps * 100) if total_steps else 0,
        "current_step_id": current_step_id,
        "next_step": next(
            (
                step
                for unit in units
                for step in unit["steps"]
                if step["id"] == current_step_id
            ),
            asdict(steps[-1]),
        ),
    }


__all__ = [
    "Drill",
    "ErrorExample",
    "GuidedExample",
    "LessonStage",
    "Representation",
    "Step",
    "TransferPair",
    "Unit",
    "WorkedStep",
    "YEAR3_MATHS_UNITS",
    "all_steps",
    "lesson_stages",
    "trail_view",
    "validate_textbook",
]
