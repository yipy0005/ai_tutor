"""Declarative full-content expansion for England primary and GCSE Maths.

Scope is deliberately explicit:

* England National Curriculum Years 1–6 for the app's existing Primary
  subjects: Maths, English and Science.
* Board-neutral England GCSE Mathematics subject content for Foundation and
  Higher pathways.

The source documents are published by the Department for Education:

* https://www.gov.uk/government/publications/national-curriculum-in-england-mathematics-programmes-of-study
* https://www.gov.uk/government/publications/national-curriculum-in-england-english-programmes-of-study
* https://www.gov.uk/government/publications/national-curriculum-in-england-science-programmes-of-study
* https://www.gov.uk/government/publications/gcse-mathematics-subject-content-and-assessment-objectives

This module keeps the coverage catalogue separate from the original starter
catalogue. Existing IDs are never renamed: progress and quest history use
those IDs as durable database keys. The question factories below are compact,
seeded and intentionally conservative; they provide a sound playable question
for each objective while the catalogue remains easy to audit and extend.
"""

from __future__ import annotations

import random
import re
from copy import deepcopy

from .curriculum import Skill, _g
from .generators import generator, mc


def _generator_name(skill_id: str) -> str:
    return "coverage_" + re.sub(r"[^a-z0-9]+", "_", skill_id.lower()).strip("_")


def _fact(
    sid: str,
    name: str,
    subject: str,
    topic: str,
    year: int,
    nc_ref: str,
    prompt: str,
    answer: str,
    distractors: tuple[str, str, str],
    hint: str = "",
) -> Skill:
    """Create a generated fact skill with a stable, auditable question."""
    generator_name = _generator_name(sid)

    def question(rng: random.Random, level: int = 1) -> dict:
        return mc(
            prompt,
            answer,
            list(distractors),
            rng,
            hint=hint,
            explain=f"The correct answer is {answer}.",
        )

    question.__name__ = generator_name
    generator(generator_name)(question)
    return _g(sid, name, subject, topic, year, generator_name, nc_ref)


def _gcse_fact(
    sid: str,
    name: str,
    topic: str,
    tiers: tuple[str, ...],
    nc_ref: str,
    prompt: str,
    answer: str,
    distractors: tuple[str, str, str],
    hint: str = "",
    visual: dict | None = None,
    interactive: dict | None = None,
) -> Skill:
    """Create a generated GCSE skill with explicit tier eligibility."""
    generator_name = _generator_name(sid)

    def question(rng: random.Random, level: int = 1) -> dict:
        if interactive:
            question = deepcopy(interactive)
            question.setdefault("hint", hint)
            question.setdefault("explain", f"The correct answer is {answer}.")
            question.setdefault("answer", answer)
            return question
        return mc(
            prompt,
            answer,
            list(distractors),
            rng,
            hint=hint,
            explain=f"The correct answer is {answer}.",
            visual=visual,
        )

    question.__name__ = generator_name
    generator(generator_name)(question)
    return Skill(
        sid,
        name,
        "gcse_maths",
        topic,
        0,
        "generated",
        generator_name,
        nc_ref,
        (),
        "gcse_maths",
        tiers,
    )


# ---------------------------------------------------------------------------
# Primary Maths: additional objectives completing the Years 1–6 map.
# ---------------------------------------------------------------------------

PRIMARY_MATHS_EXTRA: list[Skill] = [
    # Year 1
    _fact("m1.num.read-write-100", "Read and write numbers to 100", "maths", "Number & place value", 1, "Read and write numbers from 1 to 100", "Which number is written as forty-seven?", "47", ("74", "407", "40")),
    _fact("m1.num.order", "Order numbers to 100", "maths", "Number & place value", 1, "Identify one more and one less and order numbers", "Which list is in ascending order?", "12, 25, 38, 51", ("51, 38, 25, 12", "12, 38, 25, 51", "25, 12, 51, 38")),
    _fact("m1.calc.part-whole", "Part-whole models", "maths", "Addition & subtraction", 1, "Represent and use number bonds within 20", "7 and 5 make the whole. What is the whole?", "12", ("2", "13", "35")),
    _fact("m1.mult.group-share", "Grouping and sharing", "maths", "Multiplication & division", 1, "Solve one-step multiplication and division problems using grouping and sharing", "12 counters shared equally between 3 groups gives how many in each group?", "4", ("3", "9", "15")),
    _fact("m1.meas.standard-units", "Standard measuring units", "maths", "Measurement", 1, "Measure using standard units", "Which unit is best for the length of a pencil?", "centimetres", ("kilometres", "litres", "kilograms")),
    _fact("m1.meas.days-months", "Days and months", "maths", "Measurement", 1, "Sequence events and use days, weeks and months", "How many days are there in one week?", "7", ("5", "10", "12")),
    _fact("m1.geo.position-turns", "Position and turns", "maths", "Geometry", 1, "Describe position, direction and movement, including half, quarter and three-quarter turns", "A quarter turn clockwise from facing up points which way?", "right", ("left", "up", "down")),
    _fact("m1.patterns.repeating", "Repeating patterns", "maths", "Number & place value", 1, "Recognise and continue simple numerical patterns", "What comes next: 2, 4, 6, 8, ...?", "10", ("9", "11", "12")),
    # Year 2
    _fact("m2.num.count-1000", "Count to 1000", "maths", "Number & place value", 2, "Count in multiples and read numbers up to 1000", "What comes next: 997, 998, 999, ...?", "1000", ("990", "1001", "1099")),
    _fact("m2.num.read-write-1000", "Read and write numbers to 1000", "maths", "Number & place value", 2, "Read and write numbers to at least 1000 in numerals and words", "Which number is six hundred and eight?", "608", ("680", "68", "6008")),
    _fact("m2.calc.add-three-one", "Add a one-digit number to a two-digit number", "maths", "Addition & subtraction", 2, "Add and subtract numbers using concrete objects, pictorial representations and mental methods", "36 + 7 = ?", "43", ("39", "42", "53")),
    _fact("m2.calc.sub-three-one", "Subtract a one-digit number from a two-digit number", "maths", "Addition & subtraction", 2, "Subtract a one-digit number from a two-digit number", "42 − 8 = ?", "34", ("36", "40", "50")),
    _fact("m2.mult.correspondence", "Correspondence problems", "maths", "Multiplication & division", 2, "Solve problems involving multiplication, division and correspondence", "There are 3 hats and 4 scarves. How many different hat-and-scarf outfits can be made?", "12", ("7", "9", "16")),
    _fact("m2.frac.whole", "Fractions of lengths and shapes", "maths", "Fractions", 2, "Recognise, find, name and write fractions of lengths, shapes and quantities", "What fraction of 8 equal parts is 3 parts?", "3/8", ("3/5", "5/8", "1/3")),
    _fact("m2.meas.temperature", "Temperature", "maths", "Measurement", 2, "Use temperature in practical problems", "Which temperature is colder?", "−2°C", ("2°C", "20°C", "12°C")),
    _fact("m2.meas.durations", "Durations and intervals", "maths", "Measurement", 2, "Compare and sequence intervals of time", "A lesson starts at 10:15 and ends at 10:45. How long is it?", "30 minutes", ("15 minutes", "35 minutes", "45 minutes")),
    _fact("m2.meas.dates", "Dates and calendars", "maths", "Measurement", 2, "Know the number of minutes in an hour and hours in a day; use calendars", "Which month comes after September?", "October", ("August", "November", "December")),
    _fact("m2.geo.position-turns", "Position and direction", "maths", "Geometry", 2, "Use mathematical vocabulary to describe position, direction and movement", "A half turn is how many degrees?", "180°", ("90°", "45°", "360°")),
    _fact("m2.geo.right-angles", "Right angles", "maths", "Geometry", 2, "Identify and describe the properties of 2-D shapes including right angles", "Which object has a right angle?", "the corner of a book", ("a curved plate", "a circle", "a sphere")),
    _fact("m2.stats.bar-charts", "Block diagrams and bar charts", "maths", "Statistics", 2, "Interpret and construct simple block diagrams and simple tables", "A bar reaching 6 on the scale represents how many?", "6", ("3", "5", "12")),
    # Year 3
    _fact("m3.calc.add-sub-problems", "Two-step addition and subtraction problems", "maths", "Addition & subtraction", 3, "Solve problems, including two-step problems, using addition and subtraction", "A class has 28 books, buys 15 more, then gives away 9. How many remain?", "34", ("24", "43", "52")),
    _fact("m3.mult.problem-solving", "Multiplication and division problems", "maths", "Multiplication & division", 3, "Solve problems involving multiplication and division, including scaling and correspondence", "6 bags contain 8 apples each. How many apples are there?", "48", ("14", "42", "56")),
    _fact("m3.frac.unit-nonunit", "Unit and non-unit fractions", "maths", "Fractions", 3, "Recognise and use fractions as numbers and find fractions of amounts", "Which is a non-unit fraction?", "3/5", ("1/4", "1/7", "1/10")),
    _fact("m3.meas.estimate", "Estimate measures", "maths", "Measurement", 3, "Estimate, measure and compare lengths, mass, volume and capacity", "Which is a sensible estimate for the height of a classroom door?", "2 metres", ("2 centimetres", "20 metres", "200 metres")),
    _fact("m3.meas.area", "Area by counting squares", "maths", "Measurement", 3, "Measure the perimeter of simple 2-D shapes and find areas by counting squares", "A rectangle covers 4 rows of 6 squares. What is its area?", "24 square units", ("10 square units", "20 square units", "28 square units")),
    _fact("m3.geo.classify", "Classify shapes", "maths", "Geometry", 3, "Draw and identify 2-D shapes and make 3-D shapes", "Which shape is a quadrilateral?", "a rectangle", ("a triangle", "a pentagon", "a circle")),
    _fact("m3.stats.interpret", "Interpret tables and charts", "maths", "Statistics", 3, "Interpret and present data using tables, bar charts, pictograms and graphs", "A table shows 12 children chose red and 8 chose blue. How many chose red or blue?", "20", ("4", "12", "96")),
    _fact("m3.meas.temperature", "Temperature changes", "maths", "Measurement", 3, "Solve problems involving temperature and measures", "The temperature rises from 4°C to 11°C. What is the increase?", "7°C", ("5°C", "15°C", "44°C")),
    # Year 4
    _fact("m4.num.count-multiples", "Count in larger multiples", "maths", "Number & place value", 4, "Count in multiples of 6, 7, 9, 25 and 1000", "What comes next when counting in 25s: 75, 100, 125, ...?", "150", ("135", "140", "175")),
    _fact("m4.num.round", "Round to 10, 100 and 1000", "maths", "Number & place value", 4, "Round any number to the nearest 10, 100 or 1000", "Round 3,650 to the nearest 100.", "3,700", ("3,600", "3,000", "4,000")),
    _fact("m4.num.roman", "Roman numerals to 100", "maths", "Number & place value", 4, "Read Roman numerals to 100 and understand that the system changed over time", "What is XL in Roman numerals?", "40", ("60", "15", "90")),
    _fact("m4.num.negative", "Negative numbers", "maths", "Number & place value", 4, "Count backwards through zero to include negative numbers", "What is 3 less than −2?", "−5", ("−1", "1", "5")),
    _fact("m4.calc.mental", "Mental addition and subtraction", "maths", "Addition & subtraction", 4, "Add and subtract mentally with increasingly large numbers", "What is 4,000 − 700?", "3,300", ("3,700", "4,700", "3,930")),
    _fact("m4.calc.mult-1digit", "Multiply two and three digits by one digit", "maths", "Multiplication & division", 4, "Multiply two- and three-digit numbers by a one-digit number using a formal written layout", "24 × 6 = ?", "144", ("120", "124", "164")),
    _fact("m4.calc.div-1digit", "Divide up to three digits by one digit", "maths", "Multiplication & division", 4, "Divide up to three-digit numbers by a one-digit number", "156 ÷ 3 = ?", "52", ("48", "51", "53")),
    _fact("m4.calc.times-11-12", "Eleven and twelve times tables", "maths", "Multiplication & division", 4, "Recall multiplication and division facts for times tables up to 12", "What is 12 × 8?", "96", ("88", "92", "108")),
    _fact("m4.calc.scale", "Scaling and correspondence", "maths", "Multiplication & division", 4, "Solve problems involving multiplication and division, including scaling", "A recipe for 4 people uses 200 g of flour. How much for 8 people?", "400 g", ("250 g", "300 g", "800 g")),
    _fact("m4.frac.equivalence", "Equivalent fractions", "maths", "Fractions", 4, "Recognise and show families of common equivalent fractions", "Which fraction is equivalent to 3/4?", "6/8", ("3/8", "4/6", "9/16")),
    _fact("m4.frac.hundredths", "Hundredths", "maths", "Fractions", 4, "Count up and down in hundredths", "How many hundredths make one whole?", "100", ("10", "50", "1000")),
    _fact("m4.frac.add-sub", "Add and subtract fractions with the same denominator", "maths", "Fractions", 4, "Add and subtract fractions with the same denominator", "2/7 + 3/7 = ?", "5/7", ("5/14", "6/7", "1/7")),
    _fact("m4.decimals.place", "Tenths and hundredths", "maths", "Fractions", 4, "Recognise decimal equivalents and identify the value of digits", "What is the value of the 7 in 2.74?", "0.7", ("7", "0.07", "70")),
    _fact("m4.decimals.round-compare", "Round and compare decimals", "maths", "Fractions", 4, "Round decimals with one decimal place and compare decimals to two places", "Which is greater?", "0.68", ("0.608", "0.6080", "0.086")),
    _fact("m4.meas.convert", "Convert units", "maths", "Measurement", 4, "Convert between different units of measure", "How many centimetres are in 2 metres?", "200", ("20", "102", "2000")),
    _fact("m4.meas.area", "Area and perimeter", "maths", "Measurement", 4, "Find the area of rectilinear shapes and calculate perimeter", "A rectangle is 7 cm by 4 cm. What is its area?", "28 cm²", ("22 cm²", "11 cm²", "28 cm")),
    _fact("m4.geo.classify", "Classify triangles and quadrilaterals", "maths", "Geometry", 4, "Compare and classify geometric shapes based on their properties and sizes", "A triangle with three equal sides is called what?", "equilateral", ("isosceles", "scalene", "right-angled")),
    _fact("m4.geo.angles", "Acute and obtuse angles", "maths", "Geometry", 4, "Identify acute and obtuse angles and compare angles", "An angle of 120° is what type?", "obtuse", ("acute", "right", "reflex")),
    _fact("m4.geo.symmetry", "Symmetry in shapes", "maths", "Geometry", 4, "Identify lines of symmetry in 2-D shapes", "How many lines of symmetry does a square have?", "4", ("1", "2", "8")),
    _fact("m4.geo.coordinates", "Coordinates in the first quadrant", "maths", "Geometry", 4, "Describe positions on a 2-D grid as coordinates in the first quadrant", "What is the coordinate of a point 3 across and 5 up?", "(3, 5)", ("(5, 3)", "(3, 2)", "(8, 0)")),
    _fact("m4.geo.translation", "Translations on grids", "maths", "Geometry", 4, "Describe translations on a grid", "Moving (2, 4) three squares right gives which point?", "(5, 4)", ("(2, 7)", "(5, 7)", "(−1, 4)")),
    _fact("m4.stats.line-graphs", "Line graphs", "maths", "Statistics", 4, "Interpret and present discrete and continuous data using appropriate graphical methods", "Which graph is best for showing temperature changes during a day?", "a line graph", ("a pie chart", "a tally chart", "a Venn diagram")),
    # Year 5
    _fact("m5.num.powers-ten", "Powers of ten", "maths", "Number & place value", 5, "Identify powers of 10 and the effect of multiplying by them", "What is 37 × 100?", "3700", ("370", "37000", "3.7")),
    _fact("m5.num.round-negative", "Round and order negative numbers", "maths", "Number & place value", 5, "Interpret negative numbers in context and round numbers", "Which is the smallest number?", "−8", ("−3", "0", "5")),
    _fact("m5.num.roman", "Roman numerals to 1000", "maths", "Number & place value", 5, "Read Roman numerals to 1000 and recognise years written in Roman numerals", "What number is D in Roman numerals?", "500", ("50", "100", "1000")),
    _fact("m5.num.factors-multiples", "Factors and multiples", "maths", "Number & place value", 5, "Identify multiples, factors, common factors and common multiples", "Which is a factor of 36?", "9", ("5", "7", "10")),
    _fact("m5.num.prime-square-cube", "Primes, squares and cubes", "maths", "Number & place value", 5, "Know and use prime numbers, square numbers and cube numbers", "Which number is a square number?", "49", ("45", "50", "63")),
    _fact("m5.calc.mental", "Mental calculation strategies", "maths", "Addition & subtraction", 5, "Add, subtract, multiply and divide mentally with increasingly large numbers", "What is 2,500 + 399?", "2,899", ("2,799", "2,999", "2,509")),
    _fact("m5.calc.add-sub", "Large written addition and subtraction", "maths", "Addition & subtraction", 5, "Add and subtract whole numbers with more than four digits", "45,678 + 12,345 = ?", "58,023", ("57,923", "58,123", "56,013")),
    _fact("m5.calc.divide", "Divide up to four digits by one digit", "maths", "Multiplication & division", 5, "Divide up to four digits by one-digit numbers and interpret remainders", "1,248 ÷ 6 = ?", "208", ("202", "214", "248")),
    _fact("m5.calc.order", "Order of operations", "maths", "Addition & subtraction", 5, "Use the four operations to solve problems and understand the equals sign", "Using multiplication before addition, 3 + 4 × 2 = ?", "11", ("14", "10", "9")),
    _fact("m5.frac.mixed-improper", "Mixed numbers and improper fractions", "maths", "Fractions", 5, "Identify, name and write equivalent mixed numbers and improper fractions", "Which mixed number equals 7/3?", "2 1/3", ("1 2/3", "3 1/2", "2 2/3")),
    _fact("m5.frac.add-sub", "Fractions with related denominators", "maths", "Fractions", 5, "Add and subtract fractions with the same or related denominators", "1/2 + 1/4 = ?", "3/4", ("2/6", "1/6", "1/8")),
    _fact("m5.frac.multiply-whole", "Multiply a proper fraction by a whole number", "maths", "Fractions", 5, "Multiply proper fractions and mixed numbers by whole numbers", "3 × 2/5 = ?", "6/5", ("5/6", "2/15", "3/5")),
    _fact("m5.decimal.thousandths", "Thousandths", "maths", "Fractions", 5, "Read, write, order and compare numbers with up to three decimal places", "What is the value of the 6 in 0.426?", "0.006", ("0.06", "0.6", "6")),
    _fact("m5.decimal.operations", "Decimal operations", "maths", "Fractions", 5, "Round and solve problems involving decimals and measures", "0.7 + 0.35 = ?", "1.05", ("0.42", "0.75", "1.35")),
    _fact("m5.percentages", "Percentages", "maths", "Fractions", 5, "Recognise the per cent symbol and understand percentages as fractions", "What is 25% as a fraction in its simplest form?", "1/4", ("1/5", "2/5", "3/4")),
    _fact("m5.measure.convert", "Convert metric units", "maths", "Measurement", 5, "Convert between metric units and use equivalences", "How many millimetres are in 3 centimetres?", "30", ("3", "13", "300")),
    _fact("m5.measure.area-volume", "Area and volume", "maths", "Measurement", 5, "Calculate and estimate area and volume", "A cuboid is 2 cm by 3 cm by 4 cm. What is its volume?", "24 cm³", ("9 cm³", "12 cm³", "48 cm³")),
    _fact("m5.geometry.angles", "Estimate and calculate angles", "maths", "Geometry", 5, "Estimate and compare acute, obtuse and reflex angles", "Angles on a straight line add to what?", "180°", ("90°", "270°", "360°")),
    _fact("m5.geometry.polygons", "Regular and irregular polygons", "maths", "Geometry", 5, "Use properties of rectangles and regular and irregular polygons", "How many sides does a regular hexagon have?", "6", ("5", "7", "8")),
    _fact("m5.geometry.coordinates", "Coordinates in four quadrants", "maths", "Geometry", 5, "Identify and describe positions on the full coordinate grid", "Which coordinate lies in quadrant II?", "(−2, 3)", ("(2, 3)", "(−2, −3)", "(2, −3)")),
    _fact("m5.geometry.reflection", "Reflection", "maths", "Geometry", 5, "Reflect shapes in lines parallel to the axes", "Reflecting (3, 2) in the x-axis gives what?", "(3, −2)", ("(−3, 2)", "(−3, −2)", "(2, 3)")),
    _fact("m5.geometry.translation", "Translation", "maths", "Geometry", 5, "Translate shapes and describe the movement", "Moving (1, 2) by vector (3, −1) gives what?", "(4, 1)", ("(−2, 3)", "(3, 2)", "(4, 3)")),
    _fact("m5.stats.line-graphs", "Read line graphs", "maths", "Statistics", 5, "Complete, read and interpret information in tables and line graphs", "A line graph rises from 12 to 18. What is the increase?", "6", ("5", "12", "30")),
    _fact("m5.ratio.scale", "Scaling and ratio", "maths", "Ratio & proportion", 5, "Solve problems involving scaling by simple fractions and ratio", "A map scale is 1 cm to 5 km. How far is 4 cm?", "20 km", ("9 km", "15 km", "25 km")),
    # Year 6
    _fact("m6.num.large-numbers", "Numbers to ten million", "maths", "Number & place value", 6, "Read, write, order and compare numbers up to ten million", "Which number is greatest?", "7,050,000", ("7,005,000", "6,999,999", "7,000,500")),
    _fact("m6.num.factors-primes", "Common factors and primes", "maths", "Number & place value", 6, "Use common factors, common multiples and prime numbers", "What is the highest common factor of 18 and 24?", "6", ("3", "9", "12")),
    _fact("m6.num.order-operations", "Order of operations", "maths", "Number & place value", 6, "Use knowledge of the order of operations to carry out calculations", "What is 18 − 3 × 4?", "6", ("60", "12", "15")),
    _fact("m6.calc.mental", "Mental calculation", "maths", "Addition & subtraction", 6, "Solve addition, subtraction, multiplication and division problems mentally", "What is 99 × 5?", "495", ("490", "500", "594")),
    _fact("m6.calc.long-multiply", "Long multiplication", "maths", "Multiplication & division", 6, "Multiply multi-digit numbers up to four digits by two digits", "236 × 14 = ?", "3304", ("3204", "3404", "3300")),
    _fact("m6.calc.long-divide", "Long division", "maths", "Multiplication & division", 6, "Divide numbers up to four digits by two digits using formal methods", "1,872 ÷ 24 = ?", "78", ("68", "72", "82")),
    _fact("m6.calc.remainders", "Interpret remainders", "maths", "Multiplication & division", 6, "Interpret remainders according to the context", "17 children travel in cars holding 4. How many cars are needed?", "5", ("4", "4.25", "17")),
    _fact("m6.frac.simplify", "Simplify fractions", "maths", "Fractions", 6, "Use common factors to simplify fractions", "What is 18/24 in its simplest form?", "3/4", ("2/3", "6/8", "9/12")),
    _fact("m6.frac.add-sub", "Add and subtract fractions", "maths", "Fractions", 6, "Add and subtract fractions with different denominators", "1/3 + 1/6 = ?", "1/2", ("2/9", "1/9", "2/6")),
    _fact("m6.frac.multiply", "Multiply fractions", "maths", "Fractions", 6, "Multiply simple pairs of proper fractions", "1/2 × 3/4 = ?", "3/8", ("4/6", "1/4", "3/6")),
    _fact("m6.frac.divide", "Divide fractions by whole numbers", "maths", "Fractions", 6, "Divide proper fractions by whole numbers", "3/4 ÷ 3 = ?", "1/4", ("1/2", "3/12", "9/4")),
    _fact("m6.decimal.operations", "Decimal multiplication and division", "maths", "Fractions", 6, "Multiply and divide numbers by 10, 100 and 1000 and calculate with decimals", "4.8 × 10 = ?", "48", ("4.08", "480", "0.48")),
    _fact("m6.decimal.divide-powers", "Decimal place value", "maths", "Fractions", 6, "Identify the value of each digit and divide by powers of 10", "6.25 ÷ 100 = ?", "0.0625", ("0.625", "62.5", "625")),
    _fact("m6.percentages", "Percentages of amounts", "maths", "Fractions", 6, "Solve problems involving percentages of amounts", "What is 35% of 200?", "70", ("35", "65", "85")),
    _fact("m6.ratio.scale", "Scale drawings and ratio", "maths", "Ratio & proportion", 6, "Solve problems involving scale factors and ratio", "A shape is enlarged by scale factor 3. A side of 4 cm becomes what?", "12 cm", ("7 cm", "9 cm", "16 cm")),
    _fact("m6.ratio.proportion", "Proportion and unequal sharing", "maths", "Ratio & proportion", 6, "Solve problems involving unequal sharing and grouping using ratio", "Share £40 in the ratio 3:2. What is the larger share?", "£24", ("£16", "£20", "£30")),
    _fact("m6.algebra.formulae", "Formulae", "maths", "Algebra", 6, "Use simple formulae", "If d = 3t and t = 4, what is d?", "12", ("7", "1", "64")),
    _fact("m6.algebra.equations", "Two-step equations", "maths", "Algebra", 6, "Find pairs of numbers that satisfy an equation and solve simple equations", "Solve 2x + 3 = 11.", "4", ("3", "5", "7")),
    _fact("m6.algebra.sequences", "Sequences and rules", "maths", "Algebra", 6, "Generate and describe linear number sequences", "What is the next term in 4, 7, 10, 13, ...?", "16", ("15", "17", "20")),
    _fact("m6.measure.convert", "Convert measures", "maths", "Measurement", 6, "Use, read, write and convert between standard units", "How many kilometres are 3,500 metres?", "3.5 km", ("35 km", "0.35 km", "350 km")),
    _fact("m6.measure.area-triangle", "Area of triangles and parallelograms", "maths", "Measurement", 6, "Recognise when it is possible to use formulae for area of shapes", "A triangle has base 8 cm and height 5 cm. What is its area?", "20 cm²", ("40 cm²", "13 cm²", "26 cm²")),
    _fact("m6.measure.volume", "Volume of cubes and cuboids", "maths", "Measurement", 6, "Calculate, estimate and compare volume of cubes and cuboids", "A cuboid measures 2 cm × 5 cm × 6 cm. What is its volume?", "60 cm³", ("26 cm³", "30 cm³", "120 cm³")),
    _fact("m6.geometry.angles", "Angles in polygons", "maths", "Geometry", 6, "Recognise angles where they meet at a point, on a straight line and in polygons", "What is the sum of the interior angles of a triangle?", "180°", ("90°", "270°", "360°")),
    _fact("m6.geometry.coordinates", "Coordinates in all four quadrants", "maths", "Geometry", 6, "Describe positions on the full coordinate grid", "Which point is in quadrant IV?", "(4, −2)", ("(−4, 2)", "(−4, −2)", "(4, 2)")),
    _fact("m6.geometry.transformations", "Transformations", "maths", "Geometry", 6, "Describe translations and reflections in coordinate grids", "A reflection in the y-axis maps (3, −1) to what?", "(−3, −1)", ("(3, 1)", "(−3, 1)", "(1, −3)")),
    _fact("m6.stats.pie-charts", "Pie charts", "maths", "Statistics", 6, "Interpret and construct pie charts and line graphs", "A quarter of a pie chart represents what angle?", "90°", ("45°", "120°", "180°")),
    _fact("m6.stats.mean", "Mean average", "maths", "Statistics", 6, "Calculate and interpret the mean as an average", "What is the mean of 4, 6 and 8?", "6", ("5", "7", "18")),
]


# ---------------------------------------------------------------------------
# Primary English: grammar, spelling, reading and writing knowledge.
# ---------------------------------------------------------------------------

PRIMARY_ENGLISH_EXTRA: list[Skill] = [
    # Year 1
    _fact("e1.phon.split-digraphs", "Split digraphs", "english", "Phonics", 1, "Apply phonic knowledge to decode words with split digraphs", "Which word contains a split digraph?", "make", ("mat", "milk", "step")),
    _fact("e1.phon.vowel-digraphs", "Vowel digraphs", "english", "Phonics", 1, "Read words containing common vowel digraphs and trigraphs", "Which word contains the /ee/ sound?", "sheep", ("ship", "shop", "shape")),
    _fact("e1.spell.days", "Days of the week", "english", "Spelling", 1, "Spell the days of the week", "Which spelling is correct?", "Wednesday", ("Wensday", "Wednsday", "Wendesday")),
    _fact("e1.spell.common-exceptions", "Year 1 common exception words", "english", "Spelling", 1, "Spell common exception words", "Which word completes: The ___ is shining?", "sun", ("son", "sunn", "sone")),
    _fact("e1.gram.word-spaces", "Word separation", "english", "Grammar", 1, "Leave spaces between words", "Which sentence has spaces in the right places?", "The cat sat.", ("Thecatsat.", "The cat sat", "Thecats at.")),
    _fact("e1.gram.sentence", "What makes a sentence", "english", "Grammar", 1, "Recognise a sentence and use basic sentence structure", "Which is a complete sentence?", "Birds can fly.", ("Birds can", "Flying quickly", "Because it rained")),
    _fact("e1.gram.capital-proper", "Capital letters for names", "english", "Punctuation", 1, "Use capital letters for names, places, days and the personal pronoun I", "Which is written correctly?", "Sam lives in London.", ("sam lives in london.", "Sam lives in london.", "sam lives in London.")),
    _fact("e1.read.sequence", "Sequence events", "english", "Reading", 1, "Sequence sentences and events in a story", "What usually comes first when planting a seed?", "put soil in the pot", ("eat the fruit", "watch it grow", "water the leaves")),
    _fact("e1.read.vocab", "Word meaning in context", "english", "Reading", 1, "Discuss word meanings and link them to words with similar meanings", "Which word means nearly the same as little?", "small", ("loud", "quick", "round")),
    # Year 2
    _fact("e2.phon.alternative-graphemes", "Alternative spellings", "english", "Phonics", 2, "Read accurately by blending sounds in unfamiliar words", "Which word has the /k/ sound spelt ch?", "school", ("chair", "chop", "chase")),
    _fact("e2.spell.common-exceptions", "Year 2 common exception words", "english", "Spelling", 2, "Spell common exception words", "Which spelling is correct?", "beautiful", ("beautifull", "beutiful", "beautifal")),
    _fact("e2.spell.suffix-er-est", "Comparative and superlative suffixes", "english", "Spelling", 2, "Spell words with suffixes -er and -est", "What is the superlative form of tall?", "tallest", ("taller", "tallestest", "tallly")),
    _fact("e2.spell.suffix-ly", "The -ly suffix", "english", "Spelling", 2, "Spell words with suffixes -ful, -less and -ly", "Which word is formed by adding -ly to quick?", "quickly", ("quickful", "quickless", "quickery")),
    _fact("e2.gram.progressive", "Progressive tense", "english", "Grammar", 2, "Use the progressive form of verbs in the past and present", "Which sentence uses the present progressive?", "She is running.", ("She ran.", "She runs.", "She will run.")),
    _fact("e2.gram.subordination", "Subordinating conjunctions", "english", "Grammar", 2, "Use subordination with when, if, that and because", "Which word completes: I stayed inside ___ it rained?", "because", ("and", "or", "but")),
    _fact("e2.gram.commas", "Commas in lists", "english", "Punctuation", 2, "Use commas to separate items in a list", "Which sentence is punctuated correctly?", "I packed socks, shoes and a coat.", ("I packed socks shoes and a coat.", "I packed socks, shoes, and, a coat.", "I packed socks shoes, and a coat.")),
    _fact("e2.gram.apostrophe-plural", "Apostrophes for possession", "english", "Punctuation", 2, "Use apostrophes to show possession", "Which phrase shows the bag belongs to one girl?", "the girl's bag", ("the girls bag", "the girls' bag", "the girl bag")),
    _fact("e2.read.retrieve", "Retrieve information", "english", "Reading", 2, "Answer questions and make inferences from what is read", "A text says the dog slept under the table. Where did the dog sleep?", "under the table", ("on the chair", "outside", "in the basket")),
    _fact("e2.read.predict", "Predict from details", "english", "Reading", 2, "Predict what might happen from details stated and implied", "If dark clouds gather and thunder starts, what might happen next?", "it may rain", ("the sun will get brighter", "the ground will freeze", "the leaves will turn blue")),
    # Year 3
    _fact("e3.spell.prefix-in", "The in- prefix", "english", "Spelling", 3, "Use prefixes including in-, il-, im- and ir-", "What is the opposite of possible?", "impossible", ("unpossible", "dispossible", "inpossible")),
    _fact("e3.spell.suffix-ness", "Suffixes and word classes", "english", "Spelling", 3, "Form nouns using suffixes such as -ness and -ment", "Which noun is formed from kind?", "kindness", ("kindly", "kinder", "kindful")),
    _fact("e3.gram.determiners", "Determiners", "english", "Grammar", 3, "Use a, an and the and other determiners", "Which determiner completes: ___ apple was on the table?", "an", ("a", "some", "these")),
    _fact("e3.gram.past-perfect", "Present perfect", "english", "Grammar", 3, "Use the present perfect form of verbs", "Which sentence uses the present perfect?", "She has finished.", ("She finished.", "She is finishing.", "She will finish.")),
    _fact("e3.gram.paragraphs", "Paragraphs", "english", "Grammar", 3, "Use paragraphs to organise ideas around a theme", "What should a new paragraph usually begin?", "a new idea or stage", ("a random word", "the same sentence again", "a question every time")),
    _fact("e3.punct.commas", "Commas after fronted phrases", "english", "Punctuation", 3, "Use commas after fronted adverbials", "Which sentence uses a comma correctly?", "After lunch, we played outside.", ("After, lunch we played outside.", "After lunch we, played outside.", "After lunch we played, outside.")),
    _fact("e3.read.vocab", "Dictionary and vocabulary", "english", "Reading", 3, "Use dictionaries to check meanings and explore word families", "Which resource is best for finding a word's definition?", "a dictionary", ("a calendar", "a map", "a ruler")),
    _fact("e3.read.summarise", "Summarise a paragraph", "english", "Reading", 3, "Identify the main ideas drawn from more than one paragraph", "A good summary should include what?", "the main points", ("every single word", "only the title", "unrelated details")),
    _fact("e3.write.plan", "Plan writing", "english", "Writing", 3, "Plan writing by discussing and recording ideas", "What is useful before writing a story?", "a plan of the main events", ("a random ending", "a dictionary only", "a list of punctuation marks")),
    # Year 4
    _fact("e4.spell.prefixes", "Prefixes in-, il-, im- and ir-", "english", "Spelling", 4, "Spell words with common prefixes", "Which spelling is correct?", "irregular", ("inregular", "ilregular", "irrregular")),
    _fact("e4.spell.suffixes", "Suffixes -ous and -ion", "english", "Spelling", 4, "Use suffixes including -ation, -ous, -tion, -sion and -ssion", "Which word ends with -ous?", "dangerous", ("dangerion", "dangerment", "dangerful")),
    _fact("e4.spell.homophones", "Year 3 and 4 homophones", "english", "Spelling", 4, "Distinguish between homophones and near-homophones", "Which word completes: We walked ___ the gate?", "through", ("threw", "threwgh", "thruu")),
    _fact("e4.spell.word-list", "Statutory word list", "english", "Spelling", 4, "Spell words from the statutory Year 3 and 4 list", "Which spelling is correct?", "separate", ("seperate", "seperrate", "seprate")),
    _fact("e4.gram.noun-phrases", "Expanded noun phrases", "english", "Grammar", 4, "Use expanded noun phrases to add detail", "Which is an expanded noun phrase?", "the ancient, crumbling castle", ("castle", "ran quickly", "under the bridge")),
    _fact("e4.gram.standard-english", "Standard English", "english", "Grammar", 4, "Use standard English forms for verbs and pronouns", "Which sentence uses standard English?", "We were ready.", ("We was ready.", "We be ready.", "Us were ready.")),
    _fact("e4.gram.conjunctions", "Conjunctions and adverbs", "english", "Grammar", 4, "Use conjunctions, adverbs and prepositions to express time, place and cause", "Which word shows cause?", "because", ("next", "under", "quietly")),
    _fact("e4.gram.direct-speech", "Direct speech", "english", "Grammar", 4, "Use inverted commas and other punctuation for direct speech", "Which punctuation marks enclose spoken words?", "inverted commas", ("brackets", "hyphens", "apostrophes")),
    _fact("e4.punct.inverted-commas", "Inverted commas", "english", "Punctuation", 4, "Use and punctuate direct speech", "Which sentence is punctuated correctly?", """"Stop," said Mia.""", ("""Stop, said Mia.""", """Stop said Mia.""", """Stop" said Mia.""")),
    _fact("e4.punct.apostrophes", "Apostrophes in contractions", "english", "Punctuation", 4, "Use apostrophes to mark omitted letters", "Which contraction means do not?", "don't", ("dont", "do'nt", "doesn't")),
    _fact("e4.read.retrieve", "Retrieve and record", "english", "Reading", 4, "Retrieve and record information from non-fiction", "Where would you look for the meaning of a technical word?", "a glossary", ("a contents page", "an index only", "a poem")),
    _fact("e4.read.infer", "Inference and evidence", "english", "Reading", 4, "Draw inferences and justify them with evidence", "If a character's hands are shaking, what might they feel?", "nervous", ("sleepy", "hungry", "proud")),
    _fact("e4.read.vocab", "Vocabulary in context", "english", "Reading", 4, "Check that the text makes sense and explore word meanings", "In 'a swift runner', what does swift mean?", "quick", ("silent", "heavy", "careful")),
    _fact("e4.read.summarise", "Summarise a text", "english", "Reading", 4, "Summarise the main ideas drawn from more than one paragraph", "What should a summary leave out?", "minor repeated details", ("the main idea", "the key event", "the conclusion")),
    # Year 5
    _fact("e5.spell.prefixes", "Prefixes over-, re- and de-", "english", "Spelling", 5, "Use prefixes to change the meaning of words", "What does reheat mean?", "heat again", ("heat less", "heat under", "heat badly")),
    _fact("e5.spell.suffixes", "Suffixes -able and -ible", "english", "Spelling", 5, "Use word endings including -able, -ible, -ant, -ent, -ance and -ence", "Which spelling is correct?", "possible", ("possable", "possibel", "posible")),
    _fact("e5.spell.homophones", "Year 5 and 6 homophones", "english", "Spelling", 5, "Distinguish commonly confused words", "Which word completes: The dog wagged ___ tail?", "its", ("it's", "its'", "it")),
    _fact("e5.spell.word-list", "Upper-key-stage word list", "english", "Spelling", 5, "Spell words from the statutory Year 5 and 6 list", "Which spelling is correct?", "accommodate", ("accomodate", "acommodate", "accommadate")),
    _fact("e5.gram.modal", "Modal verbs", "english", "Grammar", 5, "Use modal verbs or adverbs to indicate degrees of possibility", "Which word shows possibility?", "might", ("ran", "under", "shouted")),
    _fact("e5.gram.perfect", "Perfect form", "english", "Grammar", 5, "Use the perfect form of verbs to mark relationships of time and cause", "Which sentence uses the past perfect?", "She had left.", ("She leaves.", "She is leaving.", "She will leave.")),
    _fact("e5.gram.cohesion", "Cohesion", "english", "Grammar", 5, "Use devices to build cohesion within and across paragraphs", "Which word can link two events in time?", "afterwards", ("because", "under", "blue")),
    _fact("e5.gram.formal", "Formal and informal language", "english", "Grammar", 5, "Use formal and informal structures appropriately", "Which is most suitable for a formal letter?", "I am writing to request information.", ("Hey, tell me this.", "Gimme the details.", "What's up with it?")),
    _fact("e5.punct.colons", "Colons and semicolons", "english", "Punctuation", 5, "Use colons, semicolons and dashes to mark boundaries", "Which mark can introduce a list after a complete clause?", "a colon", ("a question mark", "an apostrophe", "a full stop only")),
    _fact("e5.punct.hyphens", "Hyphens", "english", "Punctuation", 5, "Use hyphens to avoid ambiguity", "Which compound adjective is correctly written?", "well-known", ("wellknown", "well knowned", "well--known")),
    _fact("e5.read.infer", "Inference from evidence", "english", "Reading", 5, "Draw inferences and justify them with evidence", "A character hides a letter in a drawer. What can a reader infer?", "the letter is private", ("the letter is enormous", "the drawer is empty", "the character is swimming")),
    _fact("e5.read.summary", "Summarise across paragraphs", "english", "Reading", 5, "Summarise the main ideas drawn from more than one paragraph", "A summary should be written in what form?", "concise main points", ("every example", "only questions", "random quotations")),
    _fact("e5.write.paragraphs", "Organise writing", "english", "Writing", 5, "Identify how paragraphs develop themes and ideas", "What helps a paragraph stay coherent?", "sentences linked to one main idea", ("unrelated facts", "a new topic each sentence", "only questions")),
    # Year 6
    _fact("e6.spell.prefixes", "Prefixes and roots", "english", "Spelling", 6, "Use knowledge of morphology and etymology to spell unfamiliar words", "What does the prefix anti- mean?", "against", ("before", "again", "under")),
    _fact("e6.spell.suffixes", "Word endings", "english", "Spelling", 6, "Apply spelling rules for word endings and suffixes", "Which spelling is correct?", "guarantee", ("garantee", "guarentee", "guarenty")),
    _fact("e6.spell.word-list", "Statutory Year 5 and 6 words", "english", "Spelling", 6, "Spell words from the statutory Year 5 and 6 list", "Which spelling is correct?", "conscience", ("concience", "conscince", "consience")),
    _fact("e6.gram.subjunctive", "Subjunctive forms", "english", "Grammar", 6, "Recognise vocabulary and structures appropriate for formal writing, including the subjunctive", "Which sentence uses a subjunctive form?", "If I were you, I would wait.", ("If I was you, I wait.", "I am waiting.", "I waited yesterday.")),
    _fact("e6.gram.perfect", "Perfect forms", "english", "Grammar", 6, "Use the perfect form to mark relationships of time and cause", "Which phrase uses the present perfect?", "has finished", ("finished", "is finishing", "will finish")),
    _fact("e6.gram.modal", "Modal possibility", "english", "Grammar", 6, "Use modal verbs and adverbs to indicate degrees of possibility", "Which sentence expresses certainty?", "It will happen.", ("It might happen.", "It could happen.", "It may happen.")),
    _fact("e6.gram.relative", "Relative clauses", "english", "Grammar", 6, "Use relative clauses with who, which, where, when, whose and that", "Which word begins a relative clause in 'the book which I borrowed'?", "which", ("because", "although", "until")),
    _fact("e6.gram.cohesion", "Cohesion across paragraphs", "english", "Grammar", 6, "Use a range of cohesive devices across paragraphs", "Which device can refer back to an earlier noun?", "a pronoun", ("a question mark", "a heading only", "a comma splice")),
    _fact("e6.punct.hyphens", "Hyphens and ambiguity", "english", "Punctuation", 6, "Use hyphens to avoid ambiguity", "Which phrase clearly describes a child who is ten years old?", "a ten-year-old child", ("a ten year old child", "a ten-years-old child", "a tenyearold child")),
    _fact("e6.punct.bullets", "Bullet-point punctuation", "english", "Punctuation", 6, "Use a colon to introduce a list and punctuate bullet points consistently", "What should bullet points in one list have?", "consistent punctuation", ("a different tense each", "random capitals", "no relationship")),
    _fact("e6.read.vocab", "Figurative language", "english", "Reading", 6, "Discuss and evaluate how authors use language, including figurative language", "What does 'the wind whispered' use?", "personification", ("a simile", "a heading", "a fact")),
    _fact("e6.read.compare", "Compare texts", "english", "Reading", 6, "Compare characters, themes and conventions across books", "When comparing two texts, what should you use?", "evidence from both", ("the cover only", "one word", "your guess alone")),
    _fact("e6.read.summarise", "Critical summary", "english", "Reading", 6, "Summarise ideas from more than one paragraph and identify key details", "What makes a summary effective?", "accurate concise key points", ("every minor detail", "only personal opinions", "a list of titles")),
    _fact("e6.write.edit", "Edit and improve writing", "english", "Writing", 6, "Evaluate and edit writing for grammar, vocabulary and punctuation", "What should you do when editing a paragraph?", "check it against the intended meaning", ("remove every adjective", "change every noun", "ignore punctuation")),
]


# ---------------------------------------------------------------------------
# Primary Science: full statutory knowledge strands and working scientifically.
# ---------------------------------------------------------------------------

PRIMARY_SCIENCE_EXTRA: list[Skill] = [
    # Year 1
    _fact("s1.plants.common", "Common plants", "science", "Plants", 1, "Identify and name a variety of common wild and garden plants", "Which is a plant?", "a daffodil", ("a fox", "a stone", "a cloud")),
    _fact("s1.animals.habitats", "Animals and habitats", "science", "Animals including humans", 1, "Identify and name common animals in their habitats", "Which animal is most likely to live in a pond?", "a frog", ("a camel", "a penguin", "a squirrel")),
    _fact("s1.season.weather", "Seasonal weather", "science", "Seasonal changes", 1, "Observe changes across the four seasons and describe weather", "Which weather is common in winter?", "cold", ("always hot", "no clouds ever", "sunlight all night")),
    _fact("s1.mat.object", "Objects and materials", "science", "Everyday materials", 1, "Distinguish an object from the material it is made from", "A window is an object made from which material?", "glass", ("window", "square", "clear")),
    # Year 2
    _fact("s2.plants.seed", "Seeds and bulbs", "science", "Plants", 2, "Observe and describe how seeds and bulbs grow into mature plants", "What does a seed need to start growing?", "water", ("a television", "plastic", "darkness only")),
    _fact("s2.plants.light", "Plants and light", "science", "Plants", 2, "Find out how plants need water, light and a suitable temperature", "Which condition is important for most green plants?", "light", ("petrol", "salt only", "complete darkness")),
    _fact("s2.animals.life-cycle", "Animal life cycles", "science", "Animals including humans", 2, "Notice that animals have offspring which grow into adults", "What does a chick grow into?", "an adult chicken", ("a tadpole", "a seed", "a caterpillar")),
    _fact("s2.mat.material-properties", "Material suitability", "science", "Uses of everyday materials", 2, "Compare the suitability of materials for particular uses", "Which material is best for a waterproof coat?", "plastic", ("paper", "cotton wool", "chalk")),
    _fact("s2.living.microhabitats", "Microhabitats", "science", "Living things & habitats", 2, "Identify and describe microhabitats", "Where might woodlice find a damp microhabitat?", "under a log", ("on a dry roof", "inside a freezer", "on a hot radiator")),
    # Year 3
    _fact("s3.plants.water", "Water transport in plants", "science", "Plants", 3, "Investigate the way water is transported within plants", "Which part carries water up a flowering plant?", "the stem", ("the flower only", "the seed coat", "the fruit skin")),
    _fact("s3.animals.diet", "Nutrition and diet", "science", "Animals including humans", 3, "Identify that animals need the right types and amount of nutrition", "Which nutrient helps build and repair the body?", "protein", ("water only", "fibre only", "salt")),
    _fact("s3.rocks.soil-composition", "Soil components", "science", "Rocks", 3, "Recognise that soils are made from rocks and organic matter", "Which is an organic part of soil?", "decayed leaves", ("glass", "plastic", "metal")),
    _fact("s3.light.transmission", "Light through materials", "science", "Light", 3, "Recognise that light travels from sources and can pass through some materials", "Which material is transparent?", "clear glass", ("thick wood", "cardboard", "brick")),
    _fact("s3.forces.friction", "Friction", "science", "Forces & magnets", 3, "Compare how things move on different surfaces", "Which surface usually creates more friction?", "rough sandpaper", ("smooth ice", "polished glass", "oiled metal")),
    _fact("s3.investigate.fair-test", "Fair tests", "science", "Working scientifically", 3, "Ask relevant questions and use evidence to answer them", "In a fair test, what should be changed?", "one variable", ("everything", "nothing measured", "the answer")),
    # Year 4
    _fact("s4.living.classification", "Classify living things", "science", "Living things & habitats", 4, "Recognise that living things can be grouped in a variety of ways", "Which is a useful way to classify animals?", "whether they have a backbone", ("their favourite colour", "their name length", "their cage size")),
    _fact("s4.living.keys", "Classification keys", "science", "Living things & habitats", 4, "Use classification keys to help identify living things", "A classification key should use questions with what kind of answers?", "yes or no", ("long stories", "opinions only", "random guesses")),
    _fact("s4.living.environment", "Changes to environments", "science", "Living things & habitats", 4, "Recognise that environments can change and this can sometimes pose dangers", "Which change could harm a pond habitat?", "pollution", ("clean water", "more native plants", "careful observation")),
    _fact("s4.animals.teeth", "Teeth and functions", "science", "Animals including humans", 4, "Identify the different types of teeth in humans and their simple functions", "Which teeth are used for cutting food?", "incisors", ("molars", "canines", "wisdom teeth only")),
    _fact("s4.sound.vibrations", "Sound and vibrations", "science", "Sound", 4, "Identify how sounds are made, associating them with vibrating objects", "What makes a guitar string produce sound?", "it vibrates", ("it freezes", "it becomes magnetic", "it loses mass")),
    _fact("s4.sound.pitch", "Pitch and volume", "science", "Sound", 4, "Recognise that sounds get fainter as distance from the source increases", "What happens to a sound as you move farther from its source?", "it becomes quieter", ("it becomes heavier", "it changes into light", "it stops vibrating instantly")),
    _fact("s4.electricity.conductors", "Electrical conductors", "science", "Electricity", 4, "Identify common conductors and insulators", "Which material is a good electrical conductor?", "copper", ("rubber", "plastic", "dry wood")),
    _fact("s4.electricity.symbols", "Circuit diagrams", "science", "Electricity", 4, "Construct and represent simple series circuits", "Which symbol represents a cell in a circuit diagram?", "two unequal parallel lines", ("a triangle", "a spiral", "a single circle only")),
    _fact("s4.states.water-cycle", "The water cycle", "science", "States of matter", 4, "Identify the part played by evaporation and condensation in the water cycle", "What is liquid water changing into water vapour called?", "evaporation", ("condensation", "freezing", "melting")),
    _fact("s4.states.temperature", "Temperature and state changes", "science", "States of matter", 4, "Observe that some materials change state when heated or cooled", "What happens to ice when it is heated?", "it melts", ("it freezes", "it becomes a gas immediately", "it becomes heavier")),
    _fact("s4.habitats.changes", "Habitat change", "science", "Living things & habitats", 4, "Use a local habitat to study how living things depend on each other", "Why can removing plants affect animals?", "plants provide food or shelter", ("plants make all animals magnetic", "animals need no habitat", "rocks reproduce")),
    # Year 5
    _fact("s5.living.life-cycles", "Life cycles", "science", "Living things & habitats", 5, "Describe the differences in the life cycles of mammals, amphibians and insects", "Which animal has a tadpole stage?", "an amphibian", ("a mammal", "a bird", "a reptile only")),
    _fact("s5.living.reproduction", "Plant reproduction", "science", "Living things & habitats", 5, "Describe the life process of reproduction in some plants and animals", "Which part of a flowering plant produces pollen?", "the anther", ("the root hair", "the sepal only", "the stem base")),
    _fact("s5.animals.growth", "Growth and development", "science", "Animals including humans", 5, "Describe the changes as humans develop to old age", "Which is a stage of human development?", "adolescence", ("germination", "metamorphosis only", "pollination")),
    _fact("s5.animals.human-development", "Human development", "science", "Animals including humans", 5, "Describe the changes humans experience from birth to old age", "Which change commonly happens during puberty?", "the body becomes sexually mature", ("bones disappear", "breathing stops", "all teeth become seeds")),
    _fact("s5.materials.mixture", "Mixtures", "science", "Properties & changes of materials", 5, "Compare and group everyday materials based on their properties", "Which is a mixture?", "sand and water", ("pure gold", "a single iron nail", "distilled water")),
    _fact("s5.materials.dissolving", "Dissolving", "science", "Properties & changes of materials", 5, "Know that some materials dissolve to form a solution", "When sugar dissolves in water, what is formed?", "a solution", ("a new metal", "a gas only", "a magnet")),
    _fact("s5.materials.separation", "Separating materials", "science", "Properties & changes of materials", 5, "Use knowledge of solids, liquids and gases to decide how mixtures might be separated", "How can sand be separated from water?", "filtration", ("freezing only", "magnetism only", "evaporation of the sand")),
    _fact("s5.forces.air-resistance", "Air resistance", "science", "Forces", 5, "Identify the effects of air resistance, water resistance and friction", "What causes a parachute to slow a falling person?", "air resistance", ("magnetism", "light", "evaporation")),
    _fact("s5.forces.water-resistance", "Water resistance", "science", "Forces", 5, "Explain how water resistance affects moving objects", "Which shape usually moves through water most easily?", "streamlined", ("flat and wide", "rough and jagged", "open like a net")),
    _fact("s5.forces.mechanisms", "Levers, pulleys and gears", "science", "Forces", 5, "Recognise that some mechanisms allow a smaller force to have a greater effect", "Which mechanism can make lifting a load easier?", "a pulley", ("a shadow", "a thermometer", "a beaker")),
    _fact("s5.space.moon", "The Moon", "science", "Earth and space", 5, "Describe the movement of the Moon relative to the Earth", "The Moon is what relative to Earth?", "a natural satellite", ("a star", "a planet with its own light", "a comet tail")),
    _fact("s5.space.day-night", "Day and night", "science", "Earth and space", 5, "Use the idea of the Earth's rotation to explain day and night", "What causes day and night?", "Earth rotating", ("the Moon changing size", "clouds moving", "the Sun orbiting Earth each day")),
    _fact("s5.investigate.variables", "Variables in investigations", "science", "Working scientifically", 5, "Plan different types of scientific enquiries and take measurements", "The variable deliberately changed in a test is the what?", "independent variable", ("dependent variable", "control result", "conclusion")),
    # Year 6
    _fact("s6.animals.circulatory", "The circulatory system", "science", "Animals including humans", 6, "Identify and name the main parts of the human circulatory system", "Which organ pumps blood around the body?", "the heart", ("the lungs", "the stomach", "the brain only")),
    _fact("s6.animals.heart-blood", "Blood and vessels", "science", "Animals including humans", 6, "Recognise the impact of diet, exercise, drugs and lifestyle on the body", "Which blood vessel carries blood away from the heart?", "an artery", ("a vein", "an air sac", "a tendon")),
    _fact("s6.animals.health", "Healthy lifestyles", "science", "Animals including humans", 6, "Describe how nutrients and water are transported in animals", "Which habit supports a healthy body?", "regular exercise", ("never sleeping", "only eating sugar", "avoiding water")),
    _fact("s6.light.travel", "Light travels", "science", "Light", 6, "Recognise that light appears to travel in straight lines", "How does light usually travel from a source?", "in straight lines", ("in circles only", "through solid walls", "backwards from objects")),
    _fact("s6.light.shadows", "Shadows and light", "science", "Light", 6, "Use the idea that light travels in straight lines to explain shadows", "A shadow forms when an object does what?", "blocks light", ("creates sound", "adds water", "becomes transparent")),
    _fact("s6.electricity.circuits", "Series circuits", "science", "Electricity", 6, "Associate the brightness of lamps with the number and voltage of cells", "Adding another cell in series usually makes a lamp what?", "brighter", ("colder", "magnetic only", "invisible")),
    _fact("s6.electricity.symbols", "Circuit components", "science", "Electricity", 6, "Compare and give reasons for variations in how components function", "Which component opens and closes a circuit?", "a switch", ("a wire only", "a bulb filament only", "a cell case")),
    _fact("s6.living.microorganisms", "Microorganisms", "science", "Living things & habitats", 6, "Recognise that living things can be classified into broad groups", "Which is a microorganism?", "a bacterium", ("a giraffe", "an oak tree", "a mountain")),
    _fact("s6.evolution.variation", "Variation and inheritance", "science", "Evolution & inheritance", 6, "Recognise that offspring vary and are not identical to their parents", "What is variation?", "differences between individuals", ("all individuals being identical", "a type of rock", "a change of season")),
    _fact("s6.investigate.conclusions", "Scientific conclusions", "science", "Working scientifically", 6, "Use test results to make predictions and identify further questions", "A conclusion should be based on what?", "evidence from the results", ("a guess only", "the title", "the equipment colour")),
]


# ---------------------------------------------------------------------------
# GCSE Maths: common DfE content plus Higher extension.
# ---------------------------------------------------------------------------

GCSE_MATHS_EXTRA: list[Skill] = [
    # Shared Foundation/Higher content: Number
    _gcse_fact("gcse.maths.number.integers", "Integers and directed number", "Number", ("foundation", "higher"), "Use the four operations with integers, including negative numbers", "−7 + 12 = ?", "5", ("−19", "−5", "19")),
    _gcse_fact("gcse.maths.number.factors-multiples", "Factors and multiples", "Number", ("foundation", "higher"), "Use factors, multiples, common factors and common multiples", "What is the highest common factor of 18 and 30?", "6", ("3", "9", "12")),
    _gcse_fact("gcse.maths.number.primes-powers", "Primes and powers", "Number", ("foundation", "higher"), "Use prime factors, square numbers, cubes and roots", "Which number is prime?", "29", ("21", "27", "39")),
    _gcse_fact("gcse.maths.number.fractions", "Fractions", "Number", ("foundation", "higher"), "Use fractions in calculations and interpret fractions as operators", "3/4 + 1/8 = ?", "7/8", ("4/12", "1/2", "5/8")),
    _gcse_fact("gcse.maths.number.decimals", "Decimals", "Number", ("foundation", "higher"), "Use decimal notation and calculate with decimals", "0.35 × 10 = ?", "3.5", ("0.035", "35", "0.305")),
    _gcse_fact("gcse.maths.number.percentages", "Percentage calculations", "Number", ("foundation", "higher"), "Interpret percentages and calculate percentage changes", "15% of 80 = ?", "12", ("8", "15", "20")),
    _gcse_fact("gcse.maths.number.approximation", "Approximation and estimation", "Number", ("foundation", "higher"), "Use approximation and estimation to check calculations", "49.7 × 2.1 is approximately what?", "100", ("50", "75", "150")),
    _gcse_fact("gcse.maths.number.bounds", "Limits of accuracy", "Number", ("foundation", "higher"), "Use upper and lower bounds for rounded measurements", "A length is 7.4 cm rounded to 1 decimal place. Which interval is correct?", "7.35 ≤ x < 7.45", ("7.4 ≤ x < 7.5", "7.3 ≤ x < 7.4", "7.35 < x ≤ 7.45")),
    _gcse_fact("gcse.maths.number.indices", "Index laws", "Number", ("foundation", "higher"), "Use index notation and the laws of indices", "2³ × 2² = ?", "32", ("16", "64", "10")),
    _gcse_fact("gcse.maths.number.standard-form-basic", "Standard form", "Number", ("foundation", "higher"), "Use standard form for very large and very small numbers", "3.6 × 10⁴ equals what?", "36,000", ("3,600", "360,000", "0.00036")),
    _gcse_fact("gcse.maths.number.calculator", "Calculator methods", "Number", ("foundation", "higher"), "Use calculators effectively and interpret calculator displays", "Which is the best first estimate for 198 ÷ 4?", "50", ("5", "20", "500")),
    _gcse_fact("gcse.maths.number.money", "Money and financial maths", "Number", ("foundation", "higher"), "Apply number skills to money and financial contexts", "A £60 item is reduced by 25%. What is the sale price?", "£45", ("£35", "£40", "£ fifty")),
    # Ratio, proportion and rates
    _gcse_fact("gcse.maths.ratio.notation", "Ratio notation", "Ratio & proportion", ("foundation", "higher"), "Use ratio notation and simplify ratios", "Simplify 18:24.", "3:4", ("2:3", "4:3", "6:8")),
    _gcse_fact("gcse.maths.ratio.scale", "Scale factors", "Ratio & proportion", ("foundation", "higher"), "Solve scale and enlargement problems using ratios", "A map scale is 1:50,000. What real distance is 2 cm?", "1 km", ("100 m", "2.5 km", "25 km")),
    _gcse_fact("gcse.maths.ratio.direct", "Direct proportion", "Ratio & proportion", ("foundation", "higher"), "Solve direct proportion problems", "Five pens cost £3. How much do eight pens cost at the same rate?", "£4.80", ("£3.60", "£4.20", "£5.00")),
    _gcse_fact("gcse.maths.ratio.unit-rates", "Unit rates", "Ratio & proportion", ("foundation", "higher"), "Use unit rates and compare value", "A car travels 180 km in 3 hours. What is its average speed?", "60 km/h", ("30 km/h", "90 km/h", "540 km/h")),
    _gcse_fact("gcse.maths.ratio.compound-measures", "Compound measures", "Ratio & proportion", ("foundation", "higher"), "Use speed, density and pressure as compound measures", "Density is calculated by which expression?", "mass ÷ volume", ("volume ÷ mass", "mass × volume", "mass + volume")),
    _gcse_fact("gcse.maths.ratio.percent-change", "Percentage change", "Ratio & proportion", ("foundation", "higher"), "Calculate percentage increase and decrease", "A price rises from £50 to £60. What is the percentage increase?", "20%", ("10%", "16.7%", "25%")),
    _gcse_fact("gcse.maths.ratio.reverse-percent", "Reverse percentages", "Ratio & proportion", ("foundation", "higher"), "Solve reverse percentage problems", "After a 20% increase, a value is 72. What was it originally?", "60", ("52", "57.6", "86.4")),
    _gcse_fact("gcse.maths.ratio.growth-decay", "Growth and decay", "Ratio & proportion", ("foundation", "higher"), "Use repeated percentage change in growth and decay contexts", "A population of 1000 grows by 10%. What is the new population?", "1100", ("1010", "1090", "1110")),
    # Algebra
    _gcse_fact("gcse.maths.algebra.substitution", "Substitution", "Algebra", ("foundation", "higher"), "Use algebraic notation and substitute values into expressions", "If x = 4, what is 3x + 2?", "14", ("10", "12", "18")),
    _gcse_fact("gcse.maths.algebra.simplify", "Simplify expressions", "Algebra", ("foundation", "higher"), "Simplify and manipulate algebraic expressions", "3x + 2x − 4 simplifies to what?", "5x − 4", ("5x + 4", "6x − 4", "x − 4")),
    _gcse_fact("gcse.maths.algebra.expand", "Expand brackets", "Algebra", ("foundation", "higher"), "Expand products of algebraic expressions", "3(x + 4) = ?", "3x + 12", ("3x + 4", "x + 12", "7x")),
    _gcse_fact("gcse.maths.algebra.factorise-linear", "Factorise linear expressions", "Algebra", ("foundation", "higher"), "Factorise simple algebraic expressions", "6x + 9 factorises to what?", "3(2x + 3)", ("6(x + 9)", "3(2x + 9)", "9(6x + 1)")),
    _gcse_fact("gcse.maths.algebra.indices", "Algebraic indices", "Algebra", ("foundation", "higher"), "Use index laws with algebraic terms", "x³ × x² = ?", "x⁵", ("x⁶", "2x⁵", "x")),
    _gcse_fact("gcse.maths.algebra.inequalities", "Linear inequalities", "Algebra", ("foundation", "higher"), "Solve linear inequalities", "2x < 10 means what?", "x < 5", ("x > 5", "x < 20", "x > 20")),
    _gcse_fact("gcse.maths.algebra.rearrange", "Rearrange formulae", "Algebra", ("foundation", "higher"), "Rearrange formulae to change the subject", "From y = 3x + 2, what is x?", "(y − 2)/3", ("3y + 2", "(y + 2)/3", "y/3 + 2")),
    _gcse_fact("gcse.maths.algebra.nth-term", "Nth term of a sequence", "Algebra", ("foundation", "higher"), "Recognise and use sequences and find their nth terms", "What is the nth term of 5, 8, 11, 14, ...?", "3n + 2", ("3n + 5", "5n + 3", "n + 3")),
    _gcse_fact(
        "gcse.maths.algebra.coordinates", "Coordinates and gradients", "Algebra", ("foundation", "higher"),
        "Use coordinates in all four quadrants and understand gradient", "Plot point P (2, 3) on the coordinate grid.", "(2, 3)", ("(−2, 3)", "(2, −3)", "(3, 2)"),
        interactive={
            "kind": "coordinate_points",
            "prompt": "Plot point P (2, 3) on the coordinate grid.",
            "answer": "(2, 3)",
            "hint": "Move along the x-axis first, then move up the y-axis.",
            "explain": "Point P is at x = 2 and y = 3.",
            "response_spec": {
                "mode": "point", "min_points": 1, "max_points": 1, "snap": 1, "order": "exact",
                "label": "Plot point P", "helper": "Tap a grid intersection, or enter the x and y coordinates below."
            },
            "response_answer": {"type": "coordinate_points", "points": [[2, 3]]},
            "visual": {
                "type": "coordinate_grid", "x_min": -4, "x_max": 4, "y_min": -5, "y_max": 5, "grid_step": 1,
                "aria_label": "an empty coordinate grid for plotting point P"
            }
        },
    ),
    _gcse_fact(
        "gcse.maths.algebra.linear-graphs", "Linear graphs", "Algebra", ("foundation", "higher"),
        "Interpret and use linear graphs", "Which equation has gradient 3 and y-intercept 2?", "y = 3x + 2", ("y = 2x + 3", "y = x + 5", "y = −3x + 2"),
        visual={
            "type": "coordinate_grid", "x_min": -3, "x_max": 4, "y_min": -5, "y_max": 15, "grid_step": 1,
            "lines": [{"gradient": 3, "intercept": 2, "color": "ocean"}],
            "aria_label": "a coordinate grid showing a straight line"
        },
    ),
    # Geometry and measures
    _gcse_fact("gcse.maths.geometry.angle-facts", "Angle facts", "Geometry & measures", ("foundation", "higher"), "Apply angle facts at a point, on a line and in triangles", "Angles in a triangle add to what?", "180°", ("90°", "270°", "360°")),
    _gcse_fact("gcse.maths.geometry.constructions", "Constructions", "Geometry & measures", ("foundation", "higher"), "Use ruler and compass constructions", "Which construction gives points equidistant from two points?", "the perpendicular bisector", ("a tangent", "a diameter", "a sector")),
    _gcse_fact(
        "gcse.maths.geometry.transformations", "Transformations", "Geometry & measures", ("foundation", "higher"),
        "Describe and apply reflections, rotations, translations and enlargements", "Reflect triangle ABC in the x-axis and plot A′B′C′.", "reflected triangle A′B′C′", ("the original triangle ABC", "a translation only", "a rotation only"),
        interactive={
            "kind": "transformation_polygon",
            "prompt": "Triangle ABC has vertices (1, 1), (3, 1), and (2, 3). Reflect triangle ABC in the x-axis and plot A′B′C′.",
            "answer": "reflected triangle A′B′C′",
            "hint": "The x-coordinate stays the same. Each y-coordinate changes sign.",
            "explain": "Reflecting in the x-axis changes (x, y) to (x, −y).",
            "response_spec": {
                "mode": "polygon", "min_points": 3, "max_points": 3, "snap": 1, "order": "cyclic",
                "label": "Plot the reflected triangle", "helper": "Tap the three reflected vertices in order, or enter them below."
            },
            "response_answer": {
                "type": "transformation_polygon", "points": [[1, -1], [3, -1], [2, -3]]
            },
            "visual": {
                "type": "coordinate_grid", "x_min": -4, "x_max": 4, "y_min": -4, "y_max": 4, "grid_step": 1,
                "polygons": [{"points": [[1, 1], [3, 1], [2, 3]], "style": "dashed", "color": "ocean", "label": "ABC"}],
                "aria_label": "a coordinate grid showing triangle ABC above the x-axis"
            }
        },
    ),
    _gcse_fact("gcse.maths.geometry.congruence", "Congruence", "Geometry & measures", ("foundation", "higher"), "Understand congruence and properties of congruent shapes", "Congruent shapes have what?", "the same shape and size", ("the same area only", "the same perimeter only", "parallel sides only")),
    _gcse_fact("gcse.maths.geometry.similarity", "Similarity", "Geometry & measures", ("foundation", "higher"), "Use similarity and scale factors", "Similar shapes have corresponding lengths in what relationship?", "the same scale factor", ("the same angle sum only", "opposite signs", "no relationship")),
    _gcse_fact("gcse.maths.geometry.area-perimeter", "Perimeter and area", "Geometry & measures", ("foundation", "higher"), "Calculate perimeter and area of common 2-D shapes", "A rectangle is 8 cm by 5 cm. What is its area?", "40 cm²", ("26 cm²", "13 cm²", "80 cm²")),
    _gcse_fact("gcse.maths.geometry.surface-volume", "Surface area and volume", "Geometry & measures", ("foundation", "higher"), "Calculate surface area and volume of prisms and cuboids", "A cuboid is 3 cm × 4 cm × 5 cm. What is its volume?", "60 cm³", ("12 cm³", "47 cm³", "120 cm³")),
    _gcse_fact("gcse.maths.geometry.circles", "Circles", "Geometry & measures", ("foundation", "higher"), "Use circumference and area formulae for circles", "The circumference of a circle is calculated using which expression?", "2πr", ("πr²", "πd²", "r² + π")),
    _gcse_fact("gcse.maths.geometry.bearings", "Bearings", "Geometry & measures", ("foundation", "higher"), "Use three-figure bearings", "What is the bearing of east?", "090°", ("000°", "045°", "180°")),
    _gcse_fact("gcse.maths.geometry.loci", "Loci", "Geometry & measures", ("foundation", "higher"), "Use loci and regions in two dimensions", "The locus of points equidistant from two points is what?", "a perpendicular bisector", ("a circle only", "a parallel line", "a tangent")),
    # Probability and statistics
    _gcse_fact("gcse.maths.probability.scale", "Probability scale", "Probability", ("foundation", "higher"), "Use the probability scale from 0 to 1", "What is the probability of an impossible event?", "0", ("1", "0.5", "−1")),
    _gcse_fact("gcse.maths.probability.relative-frequency", "Relative frequency", "Probability", ("foundation", "higher"), "Use relative frequency to estimate probability", "18 successes in 60 trials gives a relative frequency of what?", "0.3", ("0.03", "0.6", "3")),
    _gcse_fact("gcse.maths.probability.exclusive", "Mutually exclusive events", "Probability", ("foundation", "higher"), "Use the addition rule for mutually exclusive events", "For mutually exclusive A and B, P(A or B) equals what?", "P(A) + P(B)", ("P(A) × P(B)", "P(A) − P(B)", "P(A)/P(B)")),
    _gcse_fact("gcse.maths.probability.independent", "Independent events", "Probability", ("foundation", "higher"), "Understand independent events", "Which pair is independent?", "tossing a coin and rolling a die", ("rain and wet roads", "age and height", "temperature and season")),
    _gcse_fact("gcse.maths.statistics.sampling", "Sampling", "Statistics", ("foundation", "higher"), "Interpret and construct samples and understand sampling methods", "Which sample is least likely to be biased?", "a random sample of the whole group", ("only close friends", "the first three people", "one chosen club")),
    _gcse_fact("gcse.maths.statistics.tables", "Tables and charts", "Statistics", ("foundation", "higher"), "Interpret and construct tables and statistical diagrams", "Which chart is best for comparing categories?", "a bar chart", ("a number line", "a compass", "a construction")),
    _gcse_fact("gcse.maths.statistics.averages-spread", "Averages and spread", "Statistics", ("foundation", "higher"), "Calculate and interpret averages and range", "What is the mean of 4, 6 and 8?", "6", ("5", "7", "18")),
    _gcse_fact(
        "gcse.maths.statistics.scatter", "Scatter graphs", "Statistics", ("foundation", "higher"),
        "Interpret scatter diagrams and correlation", "Points rising from left to right show what correlation?", "positive correlation", ("negative correlation", "no correlation", "perfect zero"),
        visual={
            "type": "scatter_plot", "x_min": 0, "x_max": 8, "y_min": 0, "y_max": 10,
            "points": [[1, 2], [2, 3], [3, 4], [4, 5], [5, 7], [6, 7], [7, 9]],
            "x_label": "x", "y_label": "y", "aria_label": "a scatter plot with points rising from left to right"
        },
    ),
    # Higher-only extension
    _gcse_fact("gcse.maths.number.surds", "Surds", "Number", ("higher",), "Use surd notation and simplify surds", "√50 simplifies to what?", "5√2", ("25√2", "10√5", "√25")),
    _gcse_fact("gcse.maths.number.recurring-decimals", "Recurring decimals", "Number", ("higher",), "Convert recurring decimals to fractions", "0.333... is equal to which fraction?", "1/3", ("1/4", "3/10", "1/9")),
    _gcse_fact("gcse.maths.number.fractional-indices", "Fractional indices", "Number", ("higher",), "Use fractional and negative indices", "16^(1/2) equals what?", "4", ("8", "2", "32")),
    _gcse_fact("gcse.maths.algebra.fractions", "Algebraic fractions", "Algebra", ("higher",), "Simplify and manipulate algebraic fractions", "1/x + 1/x = ?", "2/x", ("1/x²", "2x", "x/2")),
    _gcse_fact("gcse.maths.algebra.quadratic-solutions", "Solve quadratic equations", "Algebra", ("higher",), "Solve quadratic equations by factorising", "The solutions of x² − 5x + 6 = 0 are what?", "2 and 3", ("1 and 6", "−2 and −3", "3 and 5")),
    _gcse_fact("gcse.maths.algebra.completing-square", "Completing the square", "Algebra", ("higher",), "Complete the square for quadratic expressions", "x² + 6x + 9 can be written as what?", "(x + 3)²", ("(x + 6)²", "(x + 9)²", "(x − 3)²")),
    _gcse_fact("gcse.maths.algebra.functions", "Functions", "Algebra", ("higher",), "Use function notation", "If f(x) = 2x + 1, what is f(3)?", "7", ("6", "5", "9")),
    _gcse_fact("gcse.maths.algebra.iteration", "Iteration", "Algebra", ("higher",), "Use iteration to solve numerical problems", "Iteration is best described as what?", "repeating a rule to approach a solution", ("drawing a shape", "rounding once only", "measuring an angle")),
    _gcse_fact("gcse.maths.algebra.proof", "Algebraic proof", "Algebra", ("higher",), "Use algebra to construct and present mathematical proofs", "Which expression is always even for integer n?", "2n", ("n + 1", "n²", "3n")),
    _gcse_fact("gcse.maths.geometry.circle-theorems", "Circle theorems", "Geometry & measures", ("higher",), "Apply circle theorems", "The angle in a semicircle is what?", "90°", ("45°", "180°", "360°")),
    _gcse_fact("gcse.maths.geometry.sine-rule", "Sine rule", "Geometry & measures", ("higher",), "Use the sine rule in non-right-angled triangles", "The sine rule links sides with which opposite quantities?", "their angles", ("their areas only", "their perimeters", "their radii")),
    _gcse_fact("gcse.maths.geometry.cosine-rule", "Cosine rule", "Geometry & measures", ("higher",), "Use the cosine rule", "The cosine rule can find a side when two sides and what are known?", "the included angle", ("the perimeter", "the radius", "the area only")),
    _gcse_fact("gcse.maths.geometry.exact-trig", "Exact trigonometric values", "Geometry & measures", ("higher",), "Use exact values for common trigonometric ratios", "What is sin 30°?", "1/2", ("√2/2", "√3/2", "1")),
    _gcse_fact("gcse.maths.geometry.vectors", "Vectors", "Geometry & measures", ("higher",), "Use vector notation and vector geometry", "A vector describes what?", "a magnitude and a direction", ("an angle only", "an area only", "a probability")),
    _gcse_fact("gcse.maths.geometry.3d-trigonometry", "Three-dimensional geometry", "Geometry & measures", ("higher",), "Apply Pythagoras and trigonometry in three dimensions", "A diagonal through a cuboid is a what type of length?", "a 3-D distance", ("a perimeter only", "a circle radius only", "a probability")),
    _gcse_fact("gcse.maths.probability.tree", "Probability tree diagrams", "Probability", ("higher",), "Use tree diagrams to represent independent and dependent events", "For two independent events, probabilities along a tree branch are combined how?", "by multiplication", ("by addition only", "by subtraction only", "by division only")),
    _gcse_fact("gcse.maths.probability.conditional", "Conditional probability", "Probability", ("higher",), "Use conditional probability in appropriate contexts", "Conditional probability means probability given what?", "that another event has occurred", ("that nothing happened", "the mean", "a scale drawing")),
    _gcse_fact(
        "gcse.maths.statistics.histograms", "Histograms", "Statistics", ("higher",),
        "Interpret histograms with unequal class intervals", "In a histogram, frequency is represented by what?", "frequency density × class width", ("class midpoint only", "frequency ÷ width", "the bar colour"),
        visual={
            "type": "histogram",
            "bins": [
                {"start": 0, "end": 10, "density": 2},
                {"start": 10, "end": 20, "density": 5},
                {"start": 20, "end": 40, "density": 3},
                {"start": 40, "end": 60, "density": 1.5},
            ],
            "x_label": "class interval", "y_label": "frequency density",
            "aria_label": "a histogram with unequal class intervals"
        },
    ),
    _gcse_fact(
        "gcse.maths.statistics.cumulative-frequency", "Cumulative frequency", "Statistics", ("higher",),
        "Interpret cumulative frequency diagrams", "A cumulative frequency graph can estimate which value?", "a median", ("a gradient only", "a bearing", "a vector"),
        visual={
            "type": "coordinate_grid", "x_min": 0, "x_max": 60, "y_min": 0, "y_max": 40, "grid_step": 10,
            "lines": [{"points": [[0, 0], [10, 4], [20, 9], [30, 17], [40, 27], [50, 34], [60, 38]], "color": "grape"}],
            "x_label": "value", "y_label": "cumulative frequency",
            "aria_label": "a cumulative frequency graph"
        },
    ),
    _gcse_fact(
        "gcse.maths.statistics.box-plots", "Box plots", "Statistics", ("higher",),
        "Interpret box plots and interquartile range", "The interquartile range is calculated how?", "upper quartile − lower quartile", ("maximum − minimum only", "mean ÷ median", "lower quartile − upper quartile"),
        visual={
            "type": "box_plot", "min": 2, "q1": 5, "median": 8, "q3": 11, "max": 15,
            "axis_min": 0, "axis_max": 16, "label": "data set", "aria_label": "a box plot labelled with five summary values"
        },
    ),
    _gcse_fact("gcse.maths.statistics.venn", "Venn diagrams", "Statistics", ("higher",), "Use set notation and Venn diagrams for probability", "The intersection of sets A and B contains items in what?", "A and B", ("A or B only", "neither set", "A but not B")),
]
