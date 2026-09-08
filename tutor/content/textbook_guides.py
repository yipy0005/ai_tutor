"""Structured teaching content for the Year 3 Maths Guided Trail.

The map in :mod:`textbook` remains the curriculum spine. This module holds the
small instructional moves that turn each card into a teach-model-guide-diagnose-
transfer sequence. Values are plain dictionaries so the authoring data stays
serialisable and easy to validate.
"""

from __future__ import annotations


def _representation(label: str, purpose: str, alt: str, visual: dict) -> dict:
    return {
        "label": label,
        "purpose": purpose,
        "alt": alt,
        "visual": visual,
    }


def _worked(label: str, text: str) -> dict:
    return {"label": label, "text": text}


def _guided(problem: str, prompt: str, hint: str) -> dict:
    return {"problem": problem, "prompt": prompt, "hint": hint}


def _error(wrong: str, prompt: str, repair: str) -> dict:
    return {"wrong": wrong, "prompt": prompt, "repair": repair}


def _guide(
    *,
    activate: str,
    representation: dict,
    worked: tuple[dict, ...],
    guided: dict,
    error: dict,
    strategy: str,
    same_structure: str,
    same_context: str,
    reflection: str,
    related: tuple[str, ...],
) -> dict:
    return {
        "activate": activate,
        "representation": representation,
        "worked_steps": worked,
        "guided_example": guided,
        "error_example": error,
        "strategy_prompt": strategy,
        "transfer": {
            "same_structure": same_structure,
            "same_context": same_context,
        },
        "reflection_prompt": reflection,
        "related_skill_ids": related,
    }


GUIDES: dict[str, dict] = {
    "hundreds-tens-ones": _guide(
        activate="What is the value of the 5 in 352?",
        representation=_representation(
            "Place-value blocks",
            "The blocks show that a digit's value comes from its place.",
            "Three hundreds, five tens and two ones.",
            {"type": "blocks", "hundreds": 3, "tens": 5, "ones": 2},
        ),
        worked=(
            _worked("Build it", "352 has 3 hundreds, 5 tens and 2 ones."),
            _worked("Connect it", "3 hundreds + 5 tens + 2 ones = 300 + 50 + 2."),
        ),
        guided=_guided(
            "4 hundreds, 7 tens and 3 ones = ___",
            "Write the three digits in place-value order.",
            "Hundreds come first, then tens, then ones.",
        ),
        error=_error(
            "In 407, the 4 is worth 4.",
            "What is the first mistake?",
            "The 4 is in the hundreds place, so it is worth 400.",
        ),
        strategy="Which place should you inspect first when two three-digit numbers are compared?",
        same_structure="A house number, a score and a number of stickers can all be split into hundreds, tens and ones.",
        same_context="In 352 stickers, ask for the tens digit, then ask for the value of the hundreds digit.",
        reflection="How did the blocks help you connect a digit with its value?",
        related=("compare-order-1000",),
    ),
    "compare-order-1000": _guide(
        activate="Which is greater: 6 hundreds or 8 hundreds?",
        representation=_representation(
            "Place-value comparison",
            "Compare the highest place first, then move right only when it matches.",
            "708 and 680 compared by hundreds, tens and ones.",
            {"type": "blocks", "hundreds": 7, "tens": 0, "ones": 8},
        ),
        worked=(
            _worked("Start left", "708 has 7 hundreds; 680 has 6 hundreds."),
            _worked("Decide", "Because 7 hundreds is greater than 6 hundreds, 708 is greater."),
        ),
        guided=_guided(
            "425 ___ 452",
            "Choose <, > or = after comparing each place.",
            "The hundreds match, so compare the tens.",
        ),
        error=_error(
            "245 > 425 because 5 is greater than 5.",
            "Where should the comparison begin?",
            "Start with hundreds. 4 hundreds is greater than 2 hundreds, so 425 is greater.",
        ),
        strategy="What is the first place that is different? That place decides the comparison.",
        same_structure="Compare classroom numbers, prices and scores by checking the highest place first.",
        same_context="With the same four numbers, find the smallest one instead of the largest one.",
        reflection="Did you need to look at every digit? Why or why not?",
        related=("hundreds-tens-ones", "rounding"),
    ),
    "count-jumps": _guide(
        activate="What is the next number after 24 when counting in 8s?",
        representation=_representation(
            "Number-line jumps",
            "Equal jumps keep the step size constant.",
            "Jumps of 8 from 0 to 40.",
            {"type": "number_line", "start": 0, "end": 40, "step": 8, "mark": 24},
        ),
        worked=(
            _worked("Name the jump", "This sequence counts in 8s, so add 8 each time."),
            _worked("Check a landing", "24 + 8 = 32, so the next landing is 32."),
        ),
        guided=_guided(
            "50, 100, ___, 200",
            "Say the jump size before filling the gap.",
            "Each jump is 50.",
        ),
        error=_error(
            "0, 8, 16, 25, 32",
            "Which landing does not fit the jump?",
            "16 + 8 = 24, not 25.",
        ),
        strategy="How can you check the jump between two neighbouring numbers?",
        same_structure="Count in equal jumps when organising seats, points or pages.",
        same_context="Use the same sequence but ask for the number just before the missing landing.",
        reflection="What stayed the same at every jump?",
        related=("rounding", "compare-order-1000"),
    ),
    "rounding": _guide(
        activate="Which is nearer to 350: 347 or 362?",
        representation=_representation(
            "Number line",
            "Rounding chooses the nearest marked multiple.",
            "347 sits between 340 and 350 and is nearer 350.",
            {"type": "number_line", "start": 300, "end": 400, "step": 10, "mark": 350},
        ),
        worked=(
            _worked("Choose the place", "To round to the nearest 10, inspect the ones digit."),
            _worked("Move to the nearest", "347 has 7 ones, so it rounds up to 350."),
        ),
        guided=_guided(
            "562 rounded to the nearest 100 = ___",
            "Inspect the tens digit, then choose the nearer hundred.",
            "The tens digit is 6, so round up.",
        ),
        error=_error(
            "347 rounds to 300 to the nearest 10 because 3 is less than 5.",
            "Which digit should be inspected?",
            "For nearest 10, inspect the ones digit: 7 rounds 340 up to 350.",
        ),
        strategy="Which digit tells you whether to round up? It is one place to the right of the target place.",
        same_structure="Round a distance, a number of people or a price to make a quick estimate.",
        same_context="Round 347 to the nearest 10 and then to the nearest 100; the target place changes.",
        reflection="How did you know which digit to look at?",
        related=("compare-order-1000", "count-jumps"),
    ),
    "mental-add-sub": _guide(
        activate="What is 238 + 40?",
        representation=_representation(
            "Partitioned number line",
            "A place-value jump changes one part of the number at a time.",
            "238 moved forward by 40 and then 7.",
            {"type": "number_line", "start": 230, "end": 290, "step": 10, "mark": 278},
        ),
        worked=(
            _worked("Split the amount", "47 is 40 + 7."),
            _worked("Bridge in parts", "238 + 40 = 278, then 278 + 7 = 285."),
        ),
        guided=_guided(
            "364 + 28 = 364 + 20 + ___",
            "Partition 28 into tens and ones.",
            "28 is 20 + 8.",
        ),
        error=_error(
            "238 + 47 = 275 because 238 + 40 = 278 and 278 − 3 = 275.",
            "What happened to the 7 ones?",
            "After adding 40, add 7, not subtract 3: 278 + 7 = 285.",
        ),
        strategy="Which part is easiest to change first: hundreds, tens or ones?",
        same_structure="Use place-value jumps for scores, distances and amounts of money.",
        same_context="With 238, subtract 47 instead of adding 47; the context stays numerical but the operation changes.",
        reflection="Which partition made the calculation easier?",
        related=("column-addition", "column-subtraction"),
    ),
    "column-addition": _guide(
        activate="What must line up in a column calculation?",
        representation=_representation(
            "Place-value columns",
            "The visual keeps ones with ones, tens with tens and hundreds with hundreds.",
            "247 + 136 arranged by place value.",
            {"type": "column", "a": 247, "b": 136, "op": "+"},
        ),
        worked=(
            _worked("Line it up", "Put ones under ones, tens under tens and hundreds under hundreds."),
            _worked("Regroup", "7 + 6 = 13, so write 3 ones and carry 1 ten."),
            _worked("Finish", "4 + 3 + 1 = 8 tens, then 2 + 1 = 3 hundreds."),
        ),
        guided=_guided(
            "  358\n+ 227\n────\n  ___",
            "Complete the ones column and record any carried ten.",
            "8 + 7 = 15: write 5 and carry 1.",
        ),
        error=_error(
            "  247\n+ 136\n────\n  273",
            "Which place-value step is missing?",
            "The carried ten must be added to the tens: 4 + 3 + 1 = 8.",
        ),
        strategy="Before adding, how will you check that the columns are aligned?",
        same_structure="Add prices, lengths or scores when each quantity is written in the same units.",
        same_context="Use the same numbers to find the difference 383 − 247; the operation changes even though the column layout remains.",
        reflection="Why is the carried 1 worth ten, not one?",
        related=("column-subtraction", "estimate-check"),
    ),
    "column-subtraction": _guide(
        activate="Can 6 ones subtract 7 ones? What could you exchange?",
        representation=_representation(
            "Place-value exchange",
            "An exchange changes one ten into ten ones without changing the total.",
            "526 − 187 with exchanges available in the columns.",
            {"type": "column", "a": 526, "b": 187, "op": "−"},
        ),
        worked=(
            _worked("Check the ones", "6 is smaller than 7, so exchange one ten for ten ones: 16 ones."),
            _worked("Check the tens", "After that exchange, 1 ten is smaller than 8 tens, so exchange one hundred for ten tens."),
            _worked("Subtract", "16 − 7 = 9, 11 − 8 = 3 and 3 − 1 = 2, giving 339."),
        ),
        guided=_guided(
            "  643\n− 278\n────\n  ___",
            "Fill in the two exchanged place values before subtracting.",
            "The 3 ones becomes 13 after one ten is exchanged.",
        ),
        error=_error(
            "  526\n− 187\n────\n  449",
            "Where did the first exchange go wrong?",
            "After exchanging a ten, the tens digit must decrease by 1; after exchanging a hundred, the hundreds digit must decrease by 1.",
        ),
        strategy="Which column needs an exchange? Look at the top digit and the digit below it.",
        same_structure="Subtract prices, lengths or points using the same exchange idea.",
        same_context="Use 526 and 187 in a missing-number problem: 187 + □ = 526.",
        reflection="What does an exchange mean in the place-value blocks?",
        related=("column-addition", "missing-add-sub"),
    ),
    "missing-add-sub": _guide(
        activate="What is the inverse of addition?",
        representation=_representation(
            "Part-whole relationship",
            "The whole stays fixed while the missing part is found by undoing the known part.",
            "47 and 35 combine to make 82.",
            {"type": "number_line", "start": 30, "end": 90, "step": 10, "mark": 80},
        ),
        worked=(
            _worked("Read the whole", "In 47 + □ = 82, the whole is 82."),
            _worked("Undo the known part", "82 − 47 = 35, so the missing part is 35."),
        ),
        guided=_guided(
            "36 + □ = 91",
            "Use subtraction to remove the known part from the whole.",
            "Calculate 91 − 36.",
        ),
        error=_error(
            "47 + □ = 82, so □ = 129 because 47 + 82 = 129.",
            "Which numbers should be combined?",
            "The missing part is the difference between the whole and the known part: 82 − 47 = 35.",
        ),
        strategy="Which number is the whole, and which part is already known?",
        same_structure="Find a missing distance, score or quantity by using the inverse operation.",
        same_context="Turn 47 + □ = 82 into □ + 47 = 82; the unknown stays the same but its position changes.",
        reflection="How did putting the answer back into the original equation help?",
        related=("column-subtraction", "estimate-check"),
    ),
    "estimate-check": _guide(
        activate="About how much is 398 + 204?",
        representation=_representation(
            "Estimate and inverse",
            "Rounding predicts the size; the inverse checks the exact calculation.",
            "398 and 204 rounded to 400 and 200.",
            {"type": "number_line", "start": 300, "end": 700, "step": 100, "mark": 600},
        ),
        worked=(
            _worked("Estimate", "398 + 204 is about 400 + 200 = 600."),
            _worked("Calculate", "The exact answer is 602."),
            _worked("Check", "602 − 204 = 398, so the answer is consistent."),
        ),
        guided=_guided(
            "496 + 203 is about ___",
            "Round each number to the nearest hundred first.",
            "496 rounds to 500 and 203 rounds to 200.",
        ),
        error=_error(
            "398 + 204 = 600 exactly.",
            "Is 600 an estimate or the exact answer?",
            "600 is the estimate; the exact answer is 602.",
        ),
        strategy="Which check is useful here: an estimate, the inverse, or both?",
        same_structure="Estimate and check totals when shopping, counting or measuring.",
        same_context="Use the same numbers but estimate 398 − 204; the operation changes.",
        reflection="What did the estimate tell you before you calculated exactly?",
        related=("missing-add-sub", "two-step-add-sub"),
    ),
    "two-step-add-sub": _guide(
        activate="If 28 books increase by 15, what is the new total?",
        representation=_representation(
            "Two-step number line",
            "Recording the intermediate total prevents the two changes being mixed together.",
            "28 moves forward to 43, then back to 34.",
            {"type": "number_line", "start": 20, "end": 50, "step": 5, "mark": 35},
        ),
        worked=(
            _worked("Find the first change", "28 + 15 = 43 books."),
            _worked("Use the new amount", "43 − 9 = 34 books remain."),
        ),
        guided=_guided(
            "A shelf has 36 books, gets 18 more, then loses 7. How many remain?",
            "Write the intermediate total before the second step.",
            "First find 36 + 18.",
        ),
        error=_error(
            "28 + 15 − 9 = 28 + 6 = 34, but no intermediate amount was recorded.",
            "Why is this method hard to check?",
            "The answer happens to be correct, but recording 43 shows what the second change acts on.",
        ),
        strategy="What changes first in the story?",
        same_structure="Use an intermediate total for shopping, collections and journey distances.",
        same_context="Keep the book story but make both changes additions; the context stays the same while the structure changes.",
        reflection="Why did writing the new total make the problem safer?",
        related=("estimate-check", "mental-add-sub"),
    ),
    "times-three": _guide(
        activate="How many are in 4 groups of 3?",
        representation=_representation(
            "Equal-group array",
            "Rows and columns make the multiplication and its inverse visible.",
            "Three rows of four counters.",
            {"type": "array", "rows": 3, "cols": 4},
        ),
        worked=(
            _worked("Count groups", "3 × 7 means 3 equal groups of 7, or seven jumps of 3."),
            _worked("Link the family", "3 × 7 = 21, 7 × 3 = 21, 21 ÷ 3 = 7 and 21 ÷ 7 = 3."),
        ),
        guided=_guided(
            "3 × 8 = ___",
            "Build it from 3 × 7 or count one more group of three.",
            "21 + 3 = 24.",
        ),
        error=_error(
            "3 × 7 = 10 because 3 + 7 = 10.",
            "What does the multiplication sign mean?",
            "It means equal groups: 3 groups of 7 total 21.",
        ),
        strategy="Are you finding the total, the number of groups, or the amount in each group?",
        same_structure="Use equal groups for fruit, seats or packs, not only counters.",
        same_context="Use 3 × 7 and then 21 ÷ 3 in the same group story; the operation changes.",
        reflection="Which related fact could rescue you if you forget a table fact?",
        related=("divide-3-4-8", "times-four"),
    ),
    "times-four": _guide(
        activate="What is double 6? What is double that answer?",
        representation=_representation(
            "Doubling array",
            "Two doublings build four equal groups.",
            "Four rows of six counters.",
            {"type": "array", "rows": 4, "cols": 6},
        ),
        worked=(
            _worked("Double once", "6 doubled is 12."),
            _worked("Double again", "12 doubled is 24, so 4 × 6 = 24."),
        ),
        guided=_guided(
            "4 × 7 = ___",
            "Double 7, then double your answer.",
            "7 → 14 → 28.",
        ),
        error=_error(
            "4 × 6 = 18 because 3 × 6 = 18.",
            "Which table was used by mistake?",
            "Four groups of six are 24; 18 is three groups of six.",
        ),
        strategy="Which known fact can you double to make a group of four?",
        same_structure="Four equal groups can describe chairs, cards or points.",
        same_context="Keep four groups of six but ask how many are in each group when the total is 24.",
        reflection="Why does doubling twice make four times as many?",
        related=("times-three", "times-eight"),
    ),
    "times-eight": _guide(
        activate="What is 2 × 6? What happens when you double twice more?",
        representation=_representation(
            "Repeated doubling",
            "Three doublings turn a number into eight times as many.",
            "Eight rows of six counters.",
            {"type": "array", "rows": 8, "cols": 3},
        ),
        worked=(
            _worked("Double 1", "6 doubled is 12."),
            _worked("Double 2 and 3", "12 doubled is 24; 24 doubled is 48, so 8 × 6 = 48."),
        ),
        guided=_guided(
            "8 × 7 = ___",
            "Double 7 three times.",
            "7 → 14 → 28 → 56.",
        ),
        error=_error(
            "8 × 6 = 42 because 7 × 6 = 42.",
            "Which table fact was used?",
            "42 is 7 × 6; eight groups of six are 48.",
        ),
        strategy="Can repeated doubling make the eight-times fact easier?",
        same_structure="Use repeated doubling for groups, points and quantities that are eight times as large.",
        same_context="Keep 8 × 6 but ask for 48 ÷ 8; the context stays equal groups while the operation reverses.",
        reflection="How many doublings did you need, and why?",
        related=("times-four", "divide-3-4-8"),
    ),
    "divide-3-4-8": _guide(
        activate="Which multiplication fact helps with 32 ÷ 4?",
        representation=_representation(
            "Equal sharing",
            "Sharing shows division as the inverse of multiplication.",
            "32 counters shared into four equal groups.",
            {"type": "share", "total": 32, "groups": 4},
        ),
        worked=(
            _worked("Name the groups", "32 ÷ 4 asks how many are in each of four equal groups."),
            _worked("Use the fact", "4 × 8 = 32, so 32 ÷ 4 = 8."),
        ),
        guided=_guided(
            "24 ÷ 3 = ___",
            "Think of 3 × ___ = 24.",
            "Three groups of eight make 24.",
        ),
        error=_error(
            "32 ÷ 4 = 36 because 32 + 4 = 36.",
            "Does division join or split groups?",
            "Division splits a total into equal groups; the answer is 8.",
        ),
        strategy="Are you finding the group size or the number of groups?",
        same_structure="Share sweets, counters or objects into equal groups.",
        same_context="Use 32 counters and four groups, then ask how many groups of four can be made.",
        reflection="Which multiplication fact did you use to check the division?",
        related=("times-three", "remainders"),
    ),
    "two-digit-times-one": _guide(
        activate="What is 20 × 4? What is 3 × 4?",
        representation=_representation(
            "Partitioning",
            "Splitting tens and ones keeps both products familiar.",
            "23 split into 20 and 3, each multiplied by 4.",
            {"type": "partition", "value": 23, "times": 4},
        ),
        worked=(
            _worked("Partition", "23 is 20 + 3."),
            _worked("Multiply parts", "20 × 4 = 80 and 3 × 4 = 12."),
            _worked("Combine", "80 + 12 = 92, so 23 × 4 = 92."),
        ),
        guided=_guided(
            "24 × 3 = (20 × 3) + (4 × 3) = ___",
            "Calculate each partial product before combining.",
            "60 + 12 = 72.",
        ),
        error=_error(
            "23 × 4 = 20 + 12 = 32.",
            "What has been left out?",
            "The 20 must be multiplied by 4: 80 + 12 = 92.",
        ),
        strategy="Which place-value parts make familiar multiplication facts?",
        same_structure="Partition lengths, collections or prices before multiplying.",
        same_context="Keep 23 × 4 but ask for a missing factor: □ × 4 = 92.",
        reflection="Why is the 2 in 23 treated as 20?",
        related=("times-four", "scaling"),
    ),
    "remainders": _guide(
        activate="How many full groups of 5 fit into 17?",
        representation=_representation(
            "Sharing with a remainder",
            "Full groups and leftover counters show why the remainder is smaller than the divisor.",
            "17 counters shared into five groups, with two left over.",
            {"type": "share", "total": 17, "groups": 5},
        ),
        worked=(
            _worked("Find full groups", "5 × 3 = 15 is the largest multiple of 5 below 17."),
            _worked("Name the remainder", "17 − 15 = 2, so 17 ÷ 5 = 3 remainder 2."),
        ),
        guided=_guided(
            "23 ÷ 4 = ___ remainder ___",
            "Find the largest multiple of 4 that does not go over 23.",
            "4 × 5 = 20, leaving 3.",
        ),
        error=_error(
            "17 ÷ 5 = 2 remainder 7.",
            "Can a remainder be as large as the divisor?",
            "One more group of 5 would fit into 7, so the correct form is 3 remainder 2.",
        ),
        strategy="What does the story want you to do with the leftover objects?",
        same_structure="Remainders occur when sharing teams, seats or objects that cannot split equally.",
        same_context="Keep 17 objects and 5 groups, but ask how many objects are left after making three full groups.",
        reflection="Why must the remainder be smaller than the divisor?",
        related=("divide-3-4-8", "multiply-division-problems"),
    ),
    "scaling": _guide(
        activate="If 3 packs hold 12 apples, how many apples are in twice as many packs?",
        representation=_representation(
            "Scale-factor number line",
            "The same factor changes both matching quantities.",
            "A quantity doubled from 12 to 24.",
            {"type": "number_line", "start": 0, "end": 24, "step": 6, "mark": 24},
        ),
        worked=(
            _worked("Find the factor", "6 packs is twice 3 packs, so the scale factor is 2."),
            _worked("Apply it", "12 × 2 = 24 apples."),
        ),
        guided=_guided(
            "4 pencils cost 20p. How much do 8 pencils cost?",
            "Decide how the number of pencils changed, then use the same factor on the cost.",
            "8 is twice 4, so double 20p.",
        ),
        error=_error(
            "If 3 packs hold 12 apples, 6 packs hold 15 apples because 6 is 3 more.",
            "Should the amount be added or scaled?",
            "6 is twice 3, so 12 must also be doubled to 24.",
        ),
        strategy="What is the scale factor between the known and new quantities?",
        same_structure="Scale recipes, lengths, prices and collections by the same factor.",
        same_context="Keep the packs story but ask how many packs are needed for 24 apples; division reverses the scale.",
        reflection="Which two quantities had to change together?",
        related=("two-digit-times-one", "multiply-division-problems"),
    ),
    "multiply-division-problems": _guide(
        activate="Does 6 bags of 8 make a total, a group size or a number of groups?",
        representation=_representation(
            "Array and equal groups",
            "An array makes the structure visible before an operation is chosen.",
            "Six rows of eight apples.",
            {"type": "array", "rows": 6, "cols": 8},
        ),
        worked=(
            _worked("Picture the groups", "Six bags with 8 apples in each means six equal groups."),
            _worked("Choose the operation", "Equal groups with the total unknown use multiplication: 6 × 8 = 48."),
        ),
        guided=_guided(
            "48 apples are shared equally into 6 bags. How many in each bag?",
            "Use the same array but read the question in reverse.",
            "Think 6 × ___ = 48.",
        ),
        error=_error(
            "6 bags of 8 apples means 6 + 8 = 14 apples.",
            "What does ‘of 8 each’ tell you?",
            "It describes equal groups, so multiply: 6 × 8 = 48.",
        ),
        strategy="What is unknown: the total, the number of groups, or the group size?",
        same_structure="Use the structure for bags, rows of seats, teams and packs.",
        same_context="Keep six bags and eight apples but ask for the number of bags needed for 48 apples.",
        reflection="What clue in the story helped you choose the operation?",
        related=("scaling", "remainders"),
    ),
    "tenths": _guide(
        activate="How many equal parts make one whole?",
        representation=_representation(
            "Fraction bar",
            "Ten equal sections connect tenths, the numerator and the whole.",
            "Three tenths shaded on a ten-part bar.",
            {"type": "fraction", "num": 3, "den": 10, "shape": "bar"},
        ),
        worked=(
            _worked("Read the denominator", "The denominator 10 means the whole is split into ten equal parts."),
            _worked("Read the numerator", "3/10 means three of those tenths are selected; 10/10 is one whole."),
        ),
        guided=_guided(
            "7/10 means ___ tenths",
            "Use the numerator to name how many tenths.",
            "The top number is 7.",
        ),
        error=_error(
            "3/10 means three parts out of any ten pieces, even if they are unequal.",
            "What must be true about the parts?",
            "The ten parts must be equal for each one to be a tenth.",
        ),
        strategy="Which number tells you the size of each part?",
        same_structure="Tenths describe a shaded bar, a length on a number line or a quantity of a whole.",
        same_context="Keep 3/10 but represent it as 0.3 and as three tenths on a number line.",
        reflection="What does the denominator tell you?",
        related=("equivalent-fractions", "fraction-add-sub"),
    ),
    "fraction-of-amount": _guide(
        activate="What is one quarter of 20?",
        representation=_representation(
            "Sharing into equal parts",
            "Dividing first finds one equal part before taking the numerator's number of parts.",
            "20 shared into four groups, with three groups selected.",
            {"type": "share", "total": 20, "groups": 4, "take": 3},
        ),
        worked=(
            _worked("Find one part", "20 ÷ 4 = 5, so one quarter is 5."),
            _worked("Take the numerator", "Three quarters is 3 × 5 = 15."),
        ),
        guided=_guided(
            "2/5 of 25 = ___",
            "Find one fifth first, then take two of them.",
            "25 ÷ 5 = 5; then 5 × 2.",
        ),
        error=_error(
            "3/4 of 20 = 20 ÷ 3 × 4.",
            "Which number tells you how many equal parts to make?",
            "Divide by the denominator 4 first, then multiply by the numerator 3.",
        ),
        strategy="Which number tells you the part size, and which tells you how many parts to take?",
        same_structure="Find a fraction of sweets, money, distance or a class total.",
        same_context="Keep 3/4 of 20 but ask for the amount left; use the whole and the part together.",
        reflection="Why do we divide before multiplying?",
        related=("fraction-add-sub", "compare-fractions"),
    ),
    "equivalent-fractions": _guide(
        activate="Is 1/2 the same amount as 2/4?",
        representation=_representation(
            "Equivalent fraction bars",
            "The bars show that the number of pieces changes while the shaded amount stays fixed.",
            "One half and two quarters shaded to the same length.",
            {"type": "fraction_pair", "a": [1, 2], "b": [2, 4]},
        ),
        worked=(
            _worked("Change the denominator", "2 × 2 = 4, so split each half into two quarters."),
            _worked("Change the numerator", "The one shaded half becomes two shaded quarters: 1/2 = 2/4."),
        ),
        guided=_guided(
            "2/3 = ?/6",
            "The denominator was multiplied by 2; do the same to the numerator.",
            "2 × 2 = 4.",
        ),
        error=_error(
            "1/2 = 1/4 because the denominator doubled.",
            "What happened to the shaded amount?",
            "When the pieces are halved, two pieces are needed to cover the original half: 1/2 = 2/4.",
        ),
        strategy="What same operation happened to both numerator and denominator?",
        same_structure="Equivalent fractions can describe parts of a cake, a length or a collection.",
        same_context="Keep one half of a bar but rename it as 2/4, 3/6 and 4/8.",
        reflection="How did the picture prove that the amount stayed the same?",
        related=("tenths", "compare-fractions"),
    ),
    "fraction-add-sub": _guide(
        activate="What does the denominator in 2/7 tell you?",
        representation=_representation(
            "Fraction parts",
            "Matching denominators mean the parts are the same size, so only their count changes.",
            "Two sevenths and three sevenths shown as equal parts.",
            {"type": "fraction_pair", "a": [2, 7], "b": [3, 7]},
        ),
        worked=(
            _worked("Keep the part size", "Both fractions are sevenths, so the denominator stays 7."),
            _worked("Combine parts", "2 sevenths + 3 sevenths = 5 sevenths: 2/7 + 3/7 = 5/7."),
        ),
        guided=_guided(
            "4/9 − 2/9 = ___",
            "Subtract the number of ninths, not the size of a ninth.",
            "4 − 2 = 2, so the answer is 2/9.",
        ),
        error=_error(
            "2/7 + 3/7 = 5/14.",
            "Did the size of each part change?",
            "No. The parts are still sevenths, so the answer is 5/7.",
        ),
        strategy="Are the denominators equal? If so, what quantity is changing?",
        same_structure="Add or subtract equal parts of a bar, recipe or distance.",
        same_context="Use sevenths in a sharing story where two parts are collected rather than written as fractions.",
        reflection="Why does the denominator stay the same?",
        related=("compare-fractions", "tenths"),
    ),
    "compare-fractions": _guide(
        activate="Which is larger: one quarter or one eighth?",
        representation=_representation(
            "Fraction comparison bars",
            "Equal-length bars make part size and numerator comparisons visible.",
            "One quarter and one eighth compared on equal bars.",
            {"type": "fraction_pair", "a": [1, 4], "b": [1, 8]},
        ),
        worked=(
            _worked("Same denominator", "With the same denominator, compare numerators: 5/8 is greater than 3/8."),
            _worked("Unit fractions", "For one-part fractions, fewer pieces make each piece larger: 1/4 > 1/8."),
        ),
        guided=_guided(
            "3/6 ___ 5/6",
            "The denominators match, so compare the numerators.",
            "3 is less than 5.",
        ),
        error=_error(
            "1/8 > 1/4 because 8 is greater than 4.",
            "What happens to each piece when the whole is cut into more parts?",
            "More parts make smaller pieces, so 1/8 is less than 1/4.",
        ),
        strategy="Are you comparing the number of equal parts or the size of each part?",
        same_structure="Compare fractions in recipes, lengths, shaded shapes and quantities.",
        same_context="Keep the two bars but compare 3/8 and 5/8 instead of unit fractions.",
        reflection="Which feature of the fractions did you compare first?",
        related=("fraction-add-sub", "unit-nonunit"),
    ),
    "unit-nonunit": _guide(
        activate="Which fraction has a numerator of 1?",
        representation=_representation(
            "Fraction bar",
            "The numerator tells how many equal parts are selected.",
            "One sixth is a unit fraction; three sixths is non-unit.",
            {"type": "fraction", "num": 1, "den": 6, "shape": "bar"},
        ),
        worked=(
            _worked("Look at the top", "A unit fraction has numerator 1: 1/6 is one sixth."),
            _worked("Name the contrast", "3/6 is non-unit because it names three equal sixths."),
        ),
        guided=_guided(
            "Is 1/9 unit or non-unit?",
            "Inspect the numerator only.",
            "The numerator is 1.",
        ),
        error=_error(
            "3/10 is a unit fraction because the denominator is 10.",
            "Which number defines unit fraction?",
            "The numerator must be 1; 3/10 is non-unit.",
        ),
        strategy="Which part of the fraction name tells you whether it is unit?",
        same_structure="Classify fractions in diagrams, measurements and amounts.",
        same_context="Keep 3/6 but ask whether it is equal to a unit fraction; the structure changes from naming to comparing.",
        reflection="Why is the numerator the important clue?",
        related=("compare-fractions", "tenths"),
    ),
    "length-units": _guide(
        activate="How many millimetres are in one centimetre?",
        representation=_representation(
            "Length benchmark",
            "A labelled measure links the unit name to the amount being measured.",
            "A 4 cm length with a centimetre unit label.",
            {"type": "rect", "w": 4, "h": 1, "unit": "cm"},
        ),
        worked=(
            _worked("Choose the relationship", "1 cm = 10 mm."),
            _worked("Convert", "4 cm means four groups of 10 mm: 4 × 10 = 40 mm."),
        ),
        guided=_guided(
            "3 m = ___ cm",
            "Use 100 cm for each metre.",
            "3 × 100 = 300.",
        ),
        error=_error(
            "4 cm = 40, with no unit written.",
            "What is missing from the answer?",
            "The unit must change too: 4 cm = 40 mm.",
        ),
        strategy="Are you converting to a smaller unit or a larger unit?",
        same_structure="Convert lengths of ribbons, routes and objects using the same unit relationship.",
        same_context="Keep 4 cm but ask for millimetres, then ask which is the larger unit.",
        reflection="How did the unit label help you avoid a bare-number answer?",
        related=("mass-capacity", "estimate-measures"),
    ),
    "mass-capacity": _guide(
        activate="Which is heavier: 2 kg or 200 g?",
        representation=_representation(
            "Unit-scale number line",
            "The benchmark 1000 connects grams with kilograms and millilitres with litres.",
            "0 to 1000 grams with the one-kilogram endpoint marked.",
            {"type": "number_line", "start": 0, "end": 1000, "step": 250, "mark": 1000},
        ),
        worked=(
            _worked("Stay in one family", "Mass uses grams and kilograms; capacity uses millilitres and litres."),
            _worked("Convert", "2 kg = 2 × 1000 g = 2000 g."),
        ),
        guided=_guided(
            "3 litres = ___ millilitres",
            "Use 1000 millilitres for each litre.",
            "3 × 1000 = 3000.",
        ),
        error=_error(
            "2 kg = 2000 ml.",
            "Are kilograms a mass or capacity unit?",
            "Kilograms measure mass, so 2 kg = 2000 g.",
        ),
        strategy="Which unit family does the question use: mass or capacity?",
        same_structure="Convert weights and liquid amounts using the matching unit family.",
        same_context="Keep 2 kg but ask whether it is heavier than 750 g; comparison replaces conversion.",
        reflection="Why must you keep mass and capacity units separate?",
        related=("length-units", "estimate-measures"),
    ),
    "estimate-measures": _guide(
        activate="About how tall is a classroom door: 2 cm, 2 m or 20 m?",
        representation=_representation(
            "Familiar benchmark",
            "A benchmark helps reject measures that are far too large or small.",
            "A two-metre rectangle representing a classroom door.",
            {"type": "rect", "w": 2, "h": 1, "unit": "m"},
        ),
        worked=(
            _worked("Picture the object", "A door is taller than a person, so centimetres are too small."),
            _worked("Choose sensibly", "2 metres is a sensible estimate; 20 metres is far too tall."),
        ),
        guided=_guided(
            "Choose a sensible length for a pencil: 15 cm, 15 m or 15 km.",
            "Compare each choice with the size of a pencil.",
            "A pencil fits in a hand, so centimetres fit.",
        ),
        error=_error(
            "A door is about 2 centimetres high.",
            "Which unit makes the estimate unrealistic?",
            "A door is about 2 metres high; 2 centimetres is tiny.",
        ),
        strategy="What familiar object can you use as a benchmark?",
        same_structure="Estimate length, mass and capacity before measuring exactly.",
        same_context="Estimate the door in metres, then estimate its width; the object stays the same but the measure changes.",
        reflection="Which benchmark made your estimate sensible?",
        related=("length-units", "area-counting-squares"),
    ),
    "area-counting-squares": _guide(
        activate="How many squares are in 3 rows of 4?",
        representation=_representation(
            "Square grid",
            "Rows and columns reveal area as covered surface, not distance around.",
            "A 6 by 4 rectangle of equal squares.",
            {"type": "rect", "w": 6, "h": 4, "unit": "square units"},
        ),
        worked=(
            _worked("Count systematically", "There are 4 rows with 6 squares in each row."),
            _worked("Use multiplication", "4 × 6 = 24, so the area is 24 square units."),
        ),
        guided=_guided(
            "A rectangle has 3 rows of 5 squares. Its area is ___ square units.",
            "Count the rows and squares in each row.",
            "3 × 5 = 15.",
        ),
        error=_error(
            "A 4 by 6 rectangle has area 20 because its perimeter is 20.",
            "Which measurement is being found?",
            "Area covers the inside: 4 × 6 = 24 square units. 20 is the perimeter.",
        ),
        strategy="Are you measuring around the edge or covering the inside?",
        same_structure="Find area by counting tiles, floor squares or grid spaces.",
        same_context="Keep a 6 by 4 rectangle but ask for perimeter; the shape stays the same while the structure changes.",
        reflection="Why do area answers use square units?",
        related=("perimeter", "estimate-measures"),
    ),
    "perimeter": _guide(
        activate="What does ‘around the edge’ mean?",
        representation=_representation(
            "Labelled rectangle",
            "Every outside side contributes to the distance around.",
            "A 6 cm by 4 cm rectangle with side lengths shown.",
            {"type": "rect", "w": 6, "h": 4, "unit": "cm"},
        ),
        worked=(
            _worked("List the sides", "The rectangle has 6 cm, 4 cm, 6 cm and 4 cm around its edge."),
            _worked("Add them", "6 + 4 + 6 + 4 = 20 cm."),
        ),
        guided=_guided(
            "A square has sides of 5 cm. Its perimeter is ___ cm.",
            "A square has four equal sides.",
            "5 + 5 + 5 + 5 = 20.",
        ),
        error=_error(
            "A 6 cm by 4 cm rectangle has perimeter 24 cm because 6 × 4 = 24.",
            "What does multiplication find here?",
            "6 × 4 finds the area; perimeter adds the four sides to make 20 cm.",
        ),
        strategy="Which sides are equal, and have you included every outside side?",
        same_structure="Find the distance around a garden, picture frame or playground.",
        same_context="Keep the rectangle but ask how many square units cover it; that is area, not perimeter.",
        reflection="How did the shape's properties reduce the amount you had to add?",
        related=("area-counting-squares", "temperature-changes"),
    ),
    "temperature-changes": _guide(
        activate="From 4°C to 11°C, did the temperature rise or fall?",
        representation=_representation(
            "Temperature number line",
            "The distance between two temperatures gives the size of the change.",
            "A number line from -5 to 15 degrees with 5 degrees marked.",
            {"type": "number_line", "start": -5, "end": 15, "step": 5, "mark": 5},
        ),
        worked=(
            _worked("Face the direction", "From 4 to 11 moves forward, so it is a rise."),
            _worked("Count the distance", "11 − 4 = 7, so the rise is 7°C."),
        ),
        guided=_guided(
            "The temperature falls from 8°C to 3°C by ___°C.",
            "Find the distance between 8 and 3.",
            "8 − 3 = 5.",
        ),
        error=_error(
            "From 3°C to -2°C is a fall of -5°C.",
            "How should a change be described?",
            "It is a fall of 5°C; the word fall already gives the direction.",
        ),
        strategy="Is the change a rise or a fall before you calculate its size?",
        same_structure="Use a number line for temperature, bank balances or height changes.",
        same_context="Keep the same start and end temperatures but ask for the final temperature after a rise.",
        reflection="How did the number line show direction as well as distance?",
        related=("perimeter", "time-duration"),
    ),
    "money-problems": _guide(
        activate="How many pence are in £1?",
        representation=_representation(
            "Pounds and pence",
            "Money amounts stay aligned when both are written with the same units.",
            "£2, £50 and 20p represented as coins.",
            {"type": "coins", "values": [100, 100, 50, 20, 5]},
        ),
        worked=(
            _worked("Align units", "Write £5 as £5 and 0p, or convert both amounts to pence."),
            _worked("Find change", "£5.00 − £3.75 = £1.25; adding £3.75 + £1.25 checks it."),
        ),
        guided=_guided(
            "£4 and 0p − £2 and 65p = £___ and ___p",
            "Count on from the price to the amount paid or subtract in pence.",
            "265p to 400p is 135p: £1 and 35p.",
        ),
        error=_error(
            "£5 − £3.75 = £2.25 because 5 − 3 = 2 and 75 − 0 = 75.",
            "Why does the pence subtraction need care?",
            "£5 is £5.00, so the difference is £1.25, not £2.25.",
        ),
        strategy="Will pounds-and-pence or all-pence notation make this calculation clearer?",
        same_structure="Use the method for shopping, saving and finding change.",
        same_context="Keep the same price but ask whether £3.75 is enough to buy it with £5; comparison replaces change.",
        reflection="How did adding the price and change back check your answer?",
        related=("time-duration", "two-step-add-sub"),
    ),
    "time-to-minute": _guide(
        activate="Which hand tells you the minutes on a clock?",
        representation=_representation(
            "Analogue clock",
            "The minute hand and the hour hand work together to show the exact time.",
            "An analogue clock showing 4:35.",
            {"type": "clock", "hour": 4, "minute": 35},
        ),
        worked=(
            _worked("Read minutes", "The long minute hand points to 7: 7 × 5 = 35 minutes."),
            _worked("Read the hour", "The short hand has passed 4, so the time is 4:35."),
        ),
        guided=_guided(
            "The minute hand points to 9 and the hour hand is just past 2. What time is it?",
            "Count in fives around the clock, then name the hour just passed.",
            "9 × 5 = 45; the time is 2:45.",
        ),
        error=_error(
            "A clock with the hour hand just past 4 shows 5:35.",
            "Which hour has the short hand passed?",
            "It has passed 4, so the hour is 4 until it reaches 5 o'clock.",
        ),
        strategy="Which hand do you read first, and what does each hand measure?",
        same_structure="Read a wall clock, timetable or analogue watch using the same two-hand method.",
        same_context="Keep 4:35 but ask how long until 5:00; the context stays time while the structure changes to duration.",
        reflection="Why does the hour hand sit between numbers?",
        related=("time-duration", "time-facts"),
    ),
    "time-facts": _guide(
        activate="How many minutes are in one hour?",
        representation=_representation(
            "Time-unit number line",
            "Repeated equal intervals connect seconds, minutes, hours and days.",
            "A 0-to-60 minute line with the hour endpoint marked.",
            {"type": "number_line", "start": 0, "end": 60, "step": 10, "mark": 60},
        ),
        worked=(
            _worked("Recall the relationship", "60 seconds = 1 minute and 60 minutes = 1 hour."),
            _worked("Scale it", "2 minutes means two groups of 60 seconds: 120 seconds."),
        ),
        guided=_guided(
            "3 hours = ___ minutes",
            "Use three groups of 60 minutes.",
            "3 × 60 = 180.",
        ),
        error=_error(
            "2 hours = 120 seconds.",
            "Which unit should change?",
            "Hours convert to minutes first: 2 hours = 120 minutes.",
        ),
        strategy="What is the unit you start with, and what unit do you need?",
        same_structure="Convert time for lessons, journeys and schedules.",
        same_context="Keep two hours but ask how many minutes remain after 30 minutes; the structure becomes subtraction.",
        reflection="Which time facts do you want to remember without calculating?",
        related=("time-to-minute", "time-duration"),
    ),
    "time-duration": _guide(
        activate="How many minutes from 09:45 to 10:00?",
        representation=_representation(
            "Elapsed-time line",
            "Moving to the next hour, then adding whole hours and minutes, avoids clock arithmetic errors.",
            "A timeline from 9 to 11 o'clock marked in one-hour steps.",
            {"type": "number_line", "start": 9, "end": 11, "step": 1, "mark": 10},
        ),
        worked=(
            _worked("Reach the hour", "09:45 to 10:00 is 15 minutes."),
            _worked("Add the rest", "10:00 to 10:30 is 30 minutes; 15 + 30 = 45 minutes."),
        ),
        guided=_guided(
            "A lesson runs from 10:35 to 11:20. How long is it?",
            "Count to 11:00, then count from 11:00 to 11:20.",
            "25 minutes + 20 minutes = 45 minutes.",
        ),
        error=_error(
            "09:45 to 10:30 lasts 10:30 − 09:45 = 85 minutes.",
            "What happens when the hour changes?",
            "Use 15 minutes to 10:00, then 30 minutes: total 45 minutes.",
        ),
        strategy="Can you split the journey at a whole hour?",
        same_structure="Find durations for lessons, films, journeys and playtime.",
        same_context="Keep the same start and end times but ask what time the activity finishes after 45 minutes.",
        reflection="Which checkpoint made the elapsed time easier to see?",
        related=("time-to-minute", "money-problems"),
    ),
    "roman-clock": _guide(
        activate="What number does VIII represent?",
        representation=_representation(
            "Roman clock face",
            "The familiar clock positions connect Roman numerals with ordinary numbers.",
            "A clock face labelled I to XII in Roman numerals.",
            {"type": "roman_clock"},
        ),
        worked=(
            _worked("Match symbols", "I is 1, V is 5 and X is 10."),
            _worked("Read the position", "VIII is 8, so the hour hand at VIII shows eight o'clock."),
        ),
        guided=_guided(
            "The hour hand points to XI. What hour is it?",
            "Break XI into X and I.",
            "10 + 1 = 11.",
        ),
        error=_error(
            "XII means zero because it comes after XI.",
            "What does XII represent on the clock?",
            "XII is 12 and marks the top of the clock face.",
        ),
        strategy="Which Roman symbols do you recognise first?",
        same_structure="Read Roman numerals on clocks, book chapters or dates.",
        same_context="Keep the same clock position but ask for the time in words rather than the Roman numeral.",
        reflection="Which Roman numeral was easiest to recognise, and why?",
        related=("time-to-minute", "time-facts"),
    ),
    "angles-turns": _guide(
        activate="What does a quarter turn make?",
        representation=_representation(
            "Angle benchmark",
            "A square corner gives a reliable visual benchmark for 90 degrees.",
            "A 90-degree right angle.",
            {"type": "angle", "degrees": 90},
        ),
        worked=(
            _worked("Connect turns", "A quarter turn is 90°, a half turn is 180° and a full turn is 360°."),
            _worked("Compare", "A 60° angle is less than a right angle because 60 is less than 90."),
        ),
        guided=_guided(
            "Is 120° less than, equal to or greater than a right angle?",
            "Compare 120 with the 90-degree benchmark.",
            "120 is greater than 90.",
        ),
        error=_error(
            "A half turn is 90° because half means divide 180 by 2.",
            "What whole turn is being split?",
            "A full turn is 360°; half of it is 180°.",
        ),
        strategy="Which benchmark turn or corner helps you compare the angle?",
        same_structure="Describe turns in maps, games and movement as well as angles in shapes.",
        same_context="Keep a quarter turn but ask for its degrees, then ask for the direction of the turn.",
        reflection="How are a turn and an angle connected, but not identical?",
        related=("parallel-perpendicular", "classify-shapes"),
    ),
    "parallel-perpendicular": _guide(
        activate="What is special about the corner of a book?",
        representation=_representation(
            "Line relationships",
            "The picture shows lines that stay apart and lines that meet at a right angle.",
            "Parallel lines and perpendicular lines compared.",
            {"type": "lines", "kind": "parallel"},
        ),
        worked=(
            _worked("Parallel", "Parallel lines stay the same distance apart and never meet."),
            _worked("Perpendicular", "Perpendicular lines meet at 90°, like the sides of a rectangle."),
        ),
        guided=_guided(
            "Are the opposite sides of a rectangle parallel or perpendicular?",
            "Imagine extending the sides without changing direction.",
            "Opposite sides stay apart, so they are parallel.",
        ),
        error=_error(
            "Parallel lines must be horizontal.",
            "Can two vertical or slanted lines stay the same distance apart?",
            "Yes. Direction does not matter; never meeting and staying equally spaced is what matters.",
        ),
        strategy="Do the lines meet? If so, do they meet at a right angle?",
        same_structure="Find line relationships in letters, windows, roads and shapes.",
        same_context="Use a rectangle to identify parallel opposite sides and perpendicular adjacent sides.",
        reflection="What test could you use to recognise perpendicular lines?",
        related=("angles-turns", "classify-shapes"),
    ),
    "naming-shapes": _guide(
        activate="How many sides and vertices does a triangle have?",
        representation=_representation(
            "Rotated shape",
            "Turning a shape does not change its properties or name.",
            "A triangle shown in a new orientation.",
            {"type": "shape2d", "name": "triangle", "rotate": 30},
        ),
        worked=(
            _worked("Count properties", "A triangle has 3 straight sides and 3 vertices."),
            _worked("Ignore orientation", "Rotating the triangle changes its position, not its name."),
        ),
        guided=_guided(
            "A shape has 4 sides and 4 vertices. Name one possible shape.",
            "Use the number of sides first, then consider its properties.",
            "Rectangle or square are possible answers.",
        ),
        error=_error(
            "A triangle pointing sideways is no longer a triangle.",
            "What changed when the shape turned?",
            "Only its orientation changed; it still has three sides and three vertices.",
        ),
        strategy="Which properties stay true even when the drawing is rotated?",
        same_structure="Name shapes in diagrams, buildings, packaging and everyday objects.",
        same_context="Keep a four-sided shape but change its properties to distinguish square, rectangle or another quadrilateral.",
        reflection="Which property helped you name the shape most quickly?",
        related=("classify-shapes", "parallel-perpendicular"),
    ),
    "classify-shapes": _guide(
        activate="What makes a shape a quadrilateral?",
        representation=_representation(
            "Shape family",
            "A shape can belong to more than one family when it shares properties.",
            "A square as a quadrilateral with four right angles and equal sides.",
            {"type": "shape2d", "name": "square", "rotate": 25},
        ),
        worked=(
            _worked("Start with a property", "A quadrilateral has exactly four straight sides."),
            _worked("Notice overlap", "A square is a quadrilateral and also has four equal sides and four right angles."),
        ),
        guided=_guided(
            "Why can a square belong to the quadrilateral family?",
            "Count its straight sides.",
            "It has four straight sides.",
        ),
        error=_error(
            "A square cannot be a rectangle because it has equal sides.",
            "Which rectangle properties does a square share?",
            "A square has four right angles, so it fits the rectangle family as well.",
        ),
        strategy="Which property is the question asking you to use?",
        same_structure="Classify tiles, signs and drawn shapes by shared properties.",
        same_context="Keep the square but ask for a different family it belongs to; the shape stays the same while the criterion changes.",
        reflection="Why can one shape belong to several groups?",
        related=("naming-shapes", "angles-turns"),
    ),
    "bar-charts-tables": _guide(
        activate="What should you read before the height of a bar?",
        representation=_representation(
            "Scaled bar chart",
            "The scale tells how much each grid step represents.",
            "A bar chart with a scale of two.",
            {"type": "bar_chart", "labels": ["A", "B", "C", "D"], "values": [4, 8, 6, 10], "step": 2, "title": "Books read"},
        ),
        worked=(
            _worked("Read labels", "Check the title, category labels and vertical scale."),
            _worked("Read a bar", "If each step is 2 and a bar reaches 5 steps, its value is 10."),
        ),
        guided=_guided(
            "A bar reaches 4 steps on a scale of 5. What value does it show?",
            "Multiply the number of steps by the scale value.",
            "4 × 5 = 20.",
        ),
        error=_error(
            "A bar reaching 5 on a scale of 2 represents 5.",
            "What does each step represent?",
            "Each step represents 2, so 5 steps represent 10.",
        ),
        strategy="Have you read the title, labels and scale before calculating?",
        same_structure="Read scaled charts about books, scores, weather or class choices.",
        same_context="Keep the same chart but ask for a total instead of one category; the representation stays while the operation changes.",
        reflection="Why is the scale part of the data, not decoration?",
        related=("interpret-charts",),
    ),
    "interpret-charts": _guide(
        activate="If 12 children chose red and 8 chose blue, what operation finds the total?",
        representation=_representation(
            "Chart and question",
            "The question wording determines whether to add, subtract or compare chart values.",
            "A bar chart with four labelled categories.",
            {"type": "bar_chart", "labels": ["Red", "Blue", "Green", "Gold"], "values": [12, 8, 6, 10], "step": 2, "title": "Class choices"},
        ),
        worked=(
            _worked("Translate the question", "‘Total’ means combine the values, so add 12 + 8."),
            _worked("Give meaning", "20 children chose red or blue; include the category and unit."),
        ),
        guided=_guided(
            "The chart shows 12 red and 8 blue. How many more chose red?",
            "Compare the two values by subtraction.",
            "12 − 8 = 4 children.",
        ),
        error=_error(
            "How many more chose red? 12 + 8 = 20.",
            "Does ‘how many more’ ask for a total?",
            "It asks for the difference: 12 − 8 = 4 children.",
        ),
        strategy="Which word signals the structure: total, difference, or more?",
        same_structure="Interpret data from tables, bar charts, pictograms and class surveys.",
        same_context="Keep the same chart but ask for the total, difference and most popular category.",
        reflection="Which labels or words helped you choose the operation?",
        related=("bar-charts-tables",),
    ),
}


__all__ = ["GUIDES"]
