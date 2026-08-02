"""The curriculum map: subjects -> topics -> skills for Years 1, 2 and 3.

Aligned to the English National Curriculum (Key Stage 1 for Years 1-2 and
lower Key Stage 2 for Year 3). Skill ids are stable strings; progress in the
database is keyed on them, so renaming an id resets that skill's history.

Maths skills are ``generated`` (a Python function invents a fresh question each
time, so practice never runs out). English and Science skills are ``bank``
skills backed by hand-written questions in ``content/banks/*.json``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache

# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Subject:
    id: str
    name: str
    emoji: str
    colour: str
    blurb: str


SUBJECTS: dict[str, Subject] = {
    "maths": Subject(
        "maths", "Maths", "🔢", "berry", "Numbers, shapes, money and time"
    ),
    "english": Subject(
        "english", "English", "📖", "ocean", "Spelling, grammar and reading"
    ),
    "science": Subject(
        "science", "Science", "🔬", "leaf", "Plants, animals, rocks and light"
    ),
}

SUBJECT_ORDER = ["maths", "english", "science"]

YEAR_LABELS = {1: "Year 1", 2: "Year 2", 3: "Year 3"}
YEAR_BLURBS = {
    1: "Revision — things you learned in Year 1",
    2: "Revision — things you learned in Year 2",
    3: "Getting ahead — brand new Year 3 work",
}


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    subject: str
    topic: str
    year: int
    source: str  # "generated" | "bank"
    generator: str | None = None
    nc_ref: str = ""  # what the National Curriculum calls it (for parents)
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def subject_obj(self) -> Subject:
        return SUBJECTS[self.subject]

    @property
    def year_label(self) -> str:
        return YEAR_LABELS.get(self.year, f"Year {self.year}")


def _g(
    sid: str, name: str, subject: str, topic: str, year: int, gen: str, nc: str = ""
) -> Skill:
    return Skill(sid, name, subject, topic, year, "generated", gen, nc)


def _b(sid: str, name: str, subject: str, topic: str, year: int, nc: str = "") -> Skill:
    return Skill(sid, name, subject, topic, year, "bank", None, nc)


# ---------------------------------------------------------------------------
# Maths — every skill is procedurally generated
# ---------------------------------------------------------------------------

MATHS_SKILLS: list[Skill] = [
    # ---- Year 1 ----------------------------------------------------------
    _g("m1.num.count-sequence", "Counting sequences", "maths", "Number & place value", 1,
       "count_sequence", "Count to and across 100, forwards and backwards"),
    _g("m1.num.one-more-less", "One more, one less", "maths", "Number & place value", 1,
       "one_more_less", "Given a number, identify one more and one less"),
    _g("m1.num.compare", "Bigger or smaller?", "maths", "Number & place value", 1,
       "compare_20", "Use language of equal to, more than, less than"),
    _g("m1.num.count-steps", "Count in 2s, 5s and 10s", "maths", "Number & place value", 1,
       "count_steps_1", "Count in multiples of twos, fives and tens"),
    _g("m1.calc.bonds-10", "Number bonds to 10", "maths", "Addition & subtraction", 1,
       "bonds_10", "Represent and use number bonds within 20"),
    _g("m1.calc.bonds-20", "Number bonds to 20", "maths", "Addition & subtraction", 1,
       "bonds_20", "Represent and use number bonds within 20"),
    _g("m1.calc.add-within-20", "Adding to 20", "maths", "Addition & subtraction", 1,
       "add_within_20", "Add one-digit and two-digit numbers to 20"),
    _g("m1.calc.sub-within-20", "Taking away to 20", "maths", "Addition & subtraction", 1,
       "sub_within_20", "Subtract one-digit and two-digit numbers within 20"),
    _g("m1.calc.doubles", "Doubles", "maths", "Addition & subtraction", 1,
       "doubles", "Recall and use doubles of all numbers to 10"),
    _g("m1.calc.word-problems", "Story problems", "maths", "Addition & subtraction", 1,
       "word_problem_1", "Solve one-step problems using concrete objects"),
    _g("m1.frac.half-quarter", "Halves and quarters", "maths", "Fractions", 1,
       "half_quarter", "Recognise, find and name a half and a quarter"),
    _g("m1.meas.coins", "Coins", "maths", "Measurement", 1,
       "coins_recognise", "Recognise and know the value of coins and notes"),
    _g("m1.meas.time-oclock", "O'clock and half past", "maths", "Measurement", 1,
       "time_oclock", "Tell the time to the hour and half past the hour"),
    _g("m1.meas.compare", "Longer, heavier, fuller", "maths", "Measurement", 1,
       "compare_measures", "Compare, describe and solve practical problems for measures"),
    _g("m1.geo.2d-shapes", "Flat shapes", "maths", "Geometry", 1,
       "shapes_2d_name", "Recognise and name common 2-D shapes"),
    _g("m1.geo.3d-shapes", "Solid shapes", "maths", "Geometry", 1,
       "shapes_3d_name", "Recognise and name common 3-D shapes"),

    # ---- Year 2 ----------------------------------------------------------
    _g("m2.pv.tens-ones", "Tens and ones", "maths", "Number & place value", 2,
       "place_value_2", "Recognise the place value of each digit in a two-digit number"),
    _g("m2.pv.compare-order", "Compare and order to 100", "maths", "Number & place value", 2,
       "compare_100", "Compare and order numbers from 0 up to 100; use <, > and ="),
    _g("m2.pv.count-steps", "Count in 2s, 3s, 5s and 10s", "maths", "Number & place value", 2,
       "count_steps_2", "Count in steps of 2, 3 and 5 from 0, and in tens"),
    _g("m2.calc.add-2digit", "Adding two-digit numbers", "maths", "Addition & subtraction", 2,
       "add_2digit", "Add two two-digit numbers"),
    _g("m2.calc.sub-2digit", "Subtracting two-digit numbers", "maths", "Addition & subtraction", 2,
       "sub_2digit", "Subtract two two-digit numbers"),
    _g("m2.calc.facts-20", "Quick facts to 20", "maths", "Addition & subtraction", 2,
       "facts_20", "Recall and use addition and subtraction facts to 20 fluently"),
    _g("m2.calc.missing-number", "Missing numbers", "maths", "Addition & subtraction", 2,
       "missing_number_2", "Recognise and use the inverse relationship"),
    _g("m2.calc.odd-even", "Odd and even", "maths", "Number & place value", 2,
       "odd_even", "Recognise odd and even numbers"),
    _g("m2.mult.times-2-5-10", "2, 5 and 10 times tables", "maths", "Multiplication & division", 2,
       "times_2_5_10", "Recall multiplication facts for the 2, 5 and 10 times tables"),
    _g("m2.mult.divide-2-5-10", "Dividing by 2, 5 and 10", "maths", "Multiplication & division", 2,
       "divide_2_5_10", "Recall and use division facts for the 2, 5 and 10 tables"),
    _g("m2.mult.arrays", "Groups and arrays", "maths", "Multiplication & division", 2,
       "arrays", "Solve problems involving multiplication and division using arrays"),
    _g("m2.frac.unit-fractions", "Fractions of amounts", "maths", "Fractions", 2,
       "fraction_of_amount_2", "Recognise and find 1/3, 1/4, 2/4 and 3/4 of a set of objects"),
    _g("m2.frac.equivalence", "Same fractions", "maths", "Fractions", 2,
       "fraction_equiv_2", "Recognise the equivalence of 2/4 and 1/2"),
    _g("m2.meas.money", "Pounds and pence", "maths", "Measurement", 2,
       "money_2", "Find different combinations of coins; solve problems with money"),
    _g("m2.meas.change", "Giving change", "maths", "Measurement", 2,
       "change_2", "Solve simple problems involving giving change"),
    _g("m2.meas.time-5min", "Time to 5 minutes", "maths", "Measurement", 2,
       "time_5min", "Tell and write the time to five minutes"),
    _g("m2.meas.units", "Choosing units", "maths", "Measurement", 2,
       "choose_units", "Choose and use appropriate standard units to estimate and measure"),
    _g("m2.geo.properties", "Shape properties", "maths", "Geometry", 2,
       "shape_properties_2", "Identify and describe the properties of 2-D and 3-D shapes"),
    _g("m2.geo.symmetry", "Lines of symmetry", "maths", "Geometry", 2,
       "symmetry_2", "Identify a line of symmetry in a 2-D shape"),
    _g("m2.stats.tally-pictogram", "Tally charts and pictograms", "maths", "Statistics", 2,
       "tally_pictogram", "Interpret and construct simple pictograms and tally charts"),

    # ---- Year 3 ----------------------------------------------------------
    _g("m3.pv.hundreds", "Hundreds, tens and ones", "maths", "Number & place value", 3,
       "place_value_3", "Recognise the place value of each digit in a three-digit number"),
    _g("m3.pv.compare-order", "Compare and order to 1000", "maths", "Number & place value", 3,
       "compare_1000", "Compare and order numbers up to 1000"),
    _g("m3.pv.count-steps", "Count in 4s, 8s, 50s and 100s", "maths", "Number & place value", 3,
       "count_steps_3", "Count from 0 in multiples of 4, 8, 50 and 100"),
    _g("m3.pv.round", "Rounding", "maths", "Number & place value", 3,
       "round_3", "Round numbers to the nearest 10 and 100"),
    _g("m3.calc.mental-add-sub", "Adding in your head", "maths", "Addition & subtraction", 3,
       "mental_add_sub_3", "Add and subtract mentally: 3-digit and ones, tens or hundreds"),
    _g("m3.calc.add-3digit", "Column addition", "maths", "Addition & subtraction", 3,
       "add_3digit", "Add numbers with up to three digits using formal written methods"),
    _g("m3.calc.sub-3digit", "Column subtraction", "maths", "Addition & subtraction", 3,
       "sub_3digit", "Subtract numbers with up to three digits using formal written methods"),
    _g("m3.calc.missing-number", "Missing numbers", "maths", "Addition & subtraction", 3,
       "missing_number_3", "Solve problems including missing number problems"),
    _g("m3.calc.estimate-check", "Estimate and check", "maths", "Addition & subtraction", 3,
       "estimate_3", "Estimate the answer to a calculation and use inverse operations to check"),
    _g("m3.mult.times-3", "3 times table", "maths", "Multiplication & division", 3,
       "times_3", "Recall and use multiplication facts for the 3 times table"),
    _g("m3.mult.times-4", "4 times table", "maths", "Multiplication & division", 3,
       "times_4", "Recall and use multiplication facts for the 4 times table"),
    _g("m3.mult.times-8", "8 times table", "maths", "Multiplication & division", 3,
       "times_8", "Recall and use multiplication facts for the 8 times table"),
    _g("m3.mult.divide-3-4-8", "Dividing by 3, 4 and 8", "maths", "Multiplication & division", 3,
       "divide_3_4_8", "Recall and use division facts for the 3, 4 and 8 times tables"),
    _g("m3.mult.two-digit", "Two-digit times one-digit", "maths", "Multiplication & division", 3,
       "mult_2digit_1digit", "Write and calculate 2-digit x 1-digit using mental and written methods"),
    _g("m3.mult.remainders", "Sharing with leftovers", "maths", "Multiplication & division", 3,
       "divide_remainder_3", "Solve division problems including those with remainders"),
    _g("m3.mult.scaling", "Scaling problems", "maths", "Multiplication & division", 3,
       "scaling_3", "Solve problems including correspondence and scaling"),
    _g("m3.frac.tenths", "Tenths", "maths", "Fractions", 3,
       "tenths_3", "Count up and down in tenths; recognise tenths from dividing by 10"),
    _g("m3.frac.of-amount", "Fractions of amounts", "maths", "Fractions", 3,
       "fraction_of_amount_3", "Recognise and find fractions of a set of objects"),
    _g("m3.frac.equivalent", "Equivalent fractions", "maths", "Fractions", 3,
       "fraction_equiv_3", "Recognise and show, using diagrams, equivalent fractions"),
    _g("m3.frac.add-sub", "Adding and subtracting fractions", "maths", "Fractions", 3,
       "fraction_add_sub_3", "Add and subtract fractions with the same denominator within one whole"),
    _g("m3.frac.compare", "Comparing fractions", "maths", "Fractions", 3,
       "fraction_compare_3", "Compare and order unit fractions and fractions with the same denominator"),
    _g("m3.meas.length", "Millimetres, centimetres, metres", "maths", "Measurement", 3,
       "length_units_3", "Measure, compare, add and subtract lengths (m/cm/mm)"),
    _g("m3.meas.mass-capacity", "Grams, kilograms, millilitres", "maths", "Measurement", 3,
       "mass_capacity_3", "Measure, compare, add and subtract mass (kg/g) and volume (l/ml)"),
    _g("m3.meas.money", "Money problems", "maths", "Measurement", 3,
       "money_3", "Add and subtract amounts of money to give change, using £ and p"),
    _g("m3.meas.perimeter", "Perimeter", "maths", "Measurement", 3,
       "perimeter_3", "Measure the perimeter of simple 2-D shapes"),
    _g("m3.meas.time-minute", "Time to the minute", "maths", "Measurement", 3,
       "time_minute_3", "Tell and write the time from an analogue clock to the nearest minute"),
    _g("m3.meas.time-units", "Time facts", "maths", "Measurement", 3,
       "time_units_3", "Know the number of seconds in a minute and days in each month and year"),
    _g("m3.meas.time-duration", "How long?", "maths", "Measurement", 3,
       "time_duration_3", "Compare durations of events; find start and end times"),
    _g("m3.meas.roman", "Roman numerals", "maths", "Measurement", 3,
       "roman_3", "Tell the time using Roman numerals from I to XII"),
    _g("m3.geo.angles", "Right angles and turns", "maths", "Geometry", 3,
       "angles_3", "Identify right angles; identify angles greater or less than a right angle"),
    _g("m3.geo.lines", "Parallel and perpendicular", "maths", "Geometry", 3,
       "lines_3", "Identify horizontal, vertical, perpendicular and parallel lines"),
    _g("m3.geo.shapes", "Naming shapes", "maths", "Geometry", 3,
       "shapes_3", "Draw 2-D shapes and make 3-D shapes; recognise them in different orientations"),
    _g("m3.stats.bar-chart", "Bar charts and tables", "maths", "Statistics", 3,
       "bar_chart_3", "Interpret and present data using bar charts, pictograms and tables"),
]


# ---------------------------------------------------------------------------
# English — question banks
# ---------------------------------------------------------------------------

ENGLISH_SKILLS: list[Skill] = [
    # ---- Year 1 ----------------------------------------------------------
    _b("e1.spell.plurals", "Adding -s and -es", "english", "Spelling", 1,
       "Words ending -s or -es as plural marker"),
    _b("e1.spell.prefix-un", "The un- prefix", "english", "Spelling", 1,
       "Using the prefix un-"),
    _b("e1.spell.suffix-ing-ed", "Adding -ing and -ed", "english", "Spelling", 1,
       "Suffixes -ing, -ed where no change is needed to the root word"),
    _b("e1.spell.suffix-er-est", "Adding -er and -est", "english", "Spelling", 1,
       "Suffixes -er and -est"),
    _b("e1.spell.tricky-words", "Tricky words", "english", "Spelling", 1,
       "Common exception words for Year 1"),
    _b("e1.phon.digraphs", "Two letters, one sound", "english", "Phonics", 1,
       "Words containing taught GPCs including digraphs and trigraphs"),
    _b("e1.punct.capitals-stops", "Capital letters and full stops", "english", "Punctuation", 1,
       "Beginning to punctuate sentences using a capital letter and a full stop"),
    _b("e1.punct.question-exclaim", "? and !", "english", "Punctuation", 1,
       "Using a question mark or exclamation mark"),
    _b("e1.gram.joining", "Joining words with and", "english", "Grammar", 1,
       "Joining words and joining clauses using and"),
    _b("e1.read.comprehension", "Reading detective", "english", "Reading", 1,
       "Drawing on what they already know to understand texts"),

    # ---- Year 2 ----------------------------------------------------------
    _b("e2.spell.contractions", "Contractions", "english", "Spelling", 2,
       "Contracted forms: apostrophes for omission"),
    _b("e2.spell.dge-ge", "The dge and ge sound", "english", "Spelling", 2,
       "The /dʒ/ sound spelt as ge and dge, and sometimes g"),
    _b("e2.spell.kn-gn-wr", "Silent letters: kn, gn, wr", "english", "Spelling", 2,
       "The /n/ sound spelt kn and gn, the /r/ sound spelt wr"),
    _b("e2.spell.le-el-al-il", "Endings -le, -el, -al, -il", "english", "Spelling", 2,
       "The /l/ or /əl/ sound spelt -le, -el, -al and -il"),
    _b("e2.spell.y-sound", "When y sounds like i", "english", "Spelling", 2,
       "The /aɪ/ sound spelt y at the end of words"),
    _b("e2.spell.suffixes", "Endings -ment, -ness, -ful, -less", "english", "Spelling", 2,
       "Suffixes -ment, -ness, -ful, -less and -ly"),
    _b("e2.spell.homophones", "Words that sound the same", "english", "Spelling", 2,
       "Homophones and near-homophones"),
    _b("e2.spell.apostrophe-own", "Apostrophes for owning", "english", "Spelling", 2,
       "Possessive apostrophe with singular nouns"),
    _b("e2.spell.tricky-words", "Tricky words", "english", "Spelling", 2,
       "Common exception words for Year 2"),
    _b("e2.gram.word-classes", "Nouns, verbs and adjectives", "english", "Grammar", 2,
       "Learning how to use nouns, adjectives, verbs and adverbs"),
    _b("e2.gram.conjunctions", "Because, when, if, that", "english", "Grammar", 2,
       "Subordination using when, if, that, because"),
    _b("e2.gram.tense", "Past and present", "english", "Grammar", 2,
       "Correct choice and consistent use of present and past tense"),
    _b("e2.gram.noun-phrases", "Describing with noun phrases", "english", "Grammar", 2,
       "Expanded noun phrases for description and specification"),
    _b("e2.punct.commas-lists", "Commas in lists", "english", "Punctuation", 2,
       "Commas to separate items in a list"),
    _b("e2.punct.sentence-types", "Four kinds of sentence", "english", "Punctuation", 2,
       "Statement, question, command and exclamation"),
    _b("e2.read.comprehension", "Reading detective", "english", "Reading", 2,
       "Making inferences on the basis of what is being said and done"),

    # ---- Year 3 ----------------------------------------------------------
    _b("e3.spell.prefixes", "Prefixes: dis-, mis-, re-, pre-", "english", "Spelling", 3,
       "Prefixes un-, dis-, mis-, in-, re-, sub-, inter-, super-, anti-, auto-"),
    _b("e3.spell.suffix-ly", "Adding -ly", "english", "Spelling", 3,
       "Adding suffixes beginning with vowel letters; the suffix -ly"),
    _b("e3.spell.suffix-ation", "Adding -ation", "english", "Spelling", 3,
       "Adding the suffix -ation to verbs to form nouns"),
    _b("e3.spell.suffix-ous", "Adding -ous", "english", "Spelling", 3,
       "The suffix -ous"),
    _b("e3.spell.ei-eigh-ey", "The /ay/ sound: ei, eigh, ey", "english", "Spelling", 3,
       "Words with the /eɪ/ sound spelt ei, eigh, or ey"),
    _b("e3.spell.ch-sounds", "Tricky ch words", "english", "Spelling", 3,
       "Words with the /ʃ/ sound spelt ch and the /k/ sound spelt ch"),
    _b("e3.spell.homophones", "Homophones", "english", "Spelling", 3,
       "Homophones and near-homophones for Years 3 and 4"),
    _b("e3.spell.word-families", "Word families", "english", "Spelling", 3,
       "Word families based on common words, showing how words are related"),
    _b("e3.spell.word-list", "Year 3 word list", "english", "Spelling", 3,
       "Statutory Year 3 and 4 word list"),
    _b("e3.gram.a-an", "a or an?", "english", "Grammar", 3,
       "Using the forms a or an according to whether the next word begins with a consonant or vowel"),
    _b("e3.gram.conjunctions", "Time and cause words", "english", "Grammar", 3,
       "Expressing time, place and cause using conjunctions, adverbs and prepositions"),
    _b("e3.gram.adverbs", "Adverbs", "english", "Grammar", 3,
       "Using adverbs to express time and cause"),
    _b("e3.gram.prepositions", "Prepositions", "english", "Grammar", 3,
       "Using prepositions to express place and time"),
    _b("e3.gram.present-perfect", "Have and has", "english", "Grammar", 3,
       "Using the present perfect form of verbs instead of the simple past"),
    _b("e3.punct.direct-speech", "Speech marks", "english", "Punctuation", 3,
       "Introduction to inverted commas to punctuate direct speech"),
    _b("e3.punct.apostrophe-plural", "Apostrophes for plurals", "english", "Punctuation", 3,
       "The possessive apostrophe with plural nouns"),
    _b("e3.vocab.meaning", "What does that word mean?", "english", "Vocabulary", 3,
       "Using dictionaries to check the meaning of unfamiliar words"),
    _b("e3.read.comprehension", "Reading detective", "english", "Reading", 3,
       "Retrieve and record information; draw inferences and justify with evidence"),
]


# ---------------------------------------------------------------------------
# Science — question banks
# ---------------------------------------------------------------------------

SCIENCE_SKILLS: list[Skill] = [
    # ---- Year 1 ----------------------------------------------------------
    _b("s1.plants.parts", "Parts of a plant", "science", "Plants", 1,
       "Identify and describe the basic structure of common flowering plants"),
    _b("s1.plants.trees", "Trees through the year", "science", "Plants", 1,
       "Identify and name a variety of common trees, deciduous and evergreen"),
    _b("s1.animals.groups", "Animal groups", "science", "Animals including humans", 1,
       "Identify and name common animals: fish, amphibians, reptiles, birds and mammals"),
    _b("s1.animals.diets", "What animals eat", "science", "Animals including humans", 1,
       "Identify and name animals that are carnivores, herbivores and omnivores"),
    _b("s1.animals.body-senses", "My body and senses", "science", "Animals including humans", 1,
       "Identify, name, draw and label the basic parts of the human body and the five senses"),
    _b("s1.mat.identify", "Naming materials", "science", "Everyday materials", 1,
       "Distinguish between an object and the material from which it is made"),
    _b("s1.mat.properties", "How materials feel", "science", "Everyday materials", 1,
       "Describe the simple physical properties of a variety of everyday materials"),
    _b("s1.seasons.changes", "The four seasons", "science", "Seasonal changes", 1,
       "Observe changes across the four seasons and describe weather"),

    # ---- Year 2 ----------------------------------------------------------
    _b("s2.living.alive", "Alive, dead or never alive", "science", "Living things & habitats", 2,
       "Explore the differences between things that are living, dead, and never been alive"),
    _b("s2.living.habitats", "Homes for animals", "science", "Living things & habitats", 2,
       "Identify that most living things live in habitats to which they are suited"),
    _b("s2.living.food-chains", "Food chains", "science", "Living things & habitats", 2,
       "Describe how animals obtain their food; construct a simple food chain"),
    _b("s2.plants.growing", "What plants need", "science", "Plants", 2,
       "Find out and describe how plants need water, light and a suitable temperature"),
    _b("s2.animals.offspring", "Baby animals", "science", "Animals including humans", 2,
       "Notice that animals, including humans, have offspring which grow into adults"),
    _b("s2.animals.healthy", "Staying healthy", "science", "Animals including humans", 2,
       "Describe the importance of exercise, eating the right amounts and hygiene"),
    _b("s2.mat.uses", "Choosing the right material", "science", "Uses of everyday materials", 2,
       "Identify and compare the suitability of everyday materials for particular uses"),
    _b("s2.mat.changing", "Squashing and bending", "science", "Uses of everyday materials", 2,
       "Find out how the shapes of solid objects can be changed by squashing, bending, twisting"),

    # ---- Year 3 ----------------------------------------------------------
    _b("s3.plants.functions", "What each plant part does", "science", "Plants", 3,
       "Identify and describe the functions of different parts of flowering plants"),
    _b("s3.plants.needs", "What plants need to grow well", "science", "Plants", 3,
       "Explore the requirements of plants for life and growth and how they vary"),
    _b("s3.plants.life-cycle", "Pollination and seeds", "science", "Plants", 3,
       "Explore the part that flowers play in the life cycle of flowering plants"),
    _b("s3.nutrition.food", "Food and nutrition", "science", "Animals including humans", 3,
       "Identify that animals, including humans, need the right types and amount of nutrition"),
    _b("s3.skeleton.bones", "Skeletons", "science", "Animals including humans", 3,
       "Identify that humans and some animals have skeletons for support, protection and movement"),
    _b("s3.skeleton.muscles", "Muscles", "science", "Animals including humans", 3,
       "Identify that humans and some animals have muscles for movement"),
    _b("s3.rocks.types", "Types of rock", "science", "Rocks", 3,
       "Compare and group together different kinds of rocks on the basis of their properties"),
    _b("s3.rocks.fossils", "Fossils", "science", "Rocks", 3,
       "Describe in simple terms how fossils are formed"),
    _b("s3.rocks.soil", "Soil", "science", "Rocks", 3,
       "Recognise that soils are made from rocks and organic matter"),
    _b("s3.light.sources", "Light and dark", "science", "Light", 3,
       "Recognise that they need light in order to see things and that dark is the absence of light"),
    _b("s3.light.reflection", "Reflecting light", "science", "Light", 3,
       "Notice that light is reflected from surfaces"),
    _b("s3.light.shadows", "Shadows", "science", "Light", 3,
       "Recognise that shadows are formed when the light from a light source is blocked"),
    _b("s3.light.sun-safety", "Sun safety", "science", "Light", 3,
       "Recognise that light from the sun can be dangerous and that there are ways to protect eyes"),
    _b("s3.forces.contact", "Pushes, pulls and surfaces", "science", "Forces & magnets", 3,
       "Compare how things move on different surfaces"),
    _b("s3.forces.magnets", "How magnets work", "science", "Forces & magnets", 3,
       "Describe magnets as having two poles; predict whether magnets attract or repel"),
    _b("s3.forces.magnetic-materials", "Magnetic materials", "science", "Forces & magnets", 3,
       "Compare and group together a variety of everyday materials on whether they are attracted to a magnet"),
]


ALL_SKILLS: list[Skill] = MATHS_SKILLS + ENGLISH_SKILLS + SCIENCE_SKILLS
SKILLS_BY_ID: dict[str, Skill] = {s.id: s for s in ALL_SKILLS}


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def get_skill(skill_id: str) -> Skill | None:
    return SKILLS_BY_ID.get(skill_id)


def skill_name(skill_id: str) -> str:
    skill = SKILLS_BY_ID.get(skill_id)
    return skill.name if skill else skill_id


def skills_for(
    subject: str | None = None,
    years: list[int] | tuple[int, ...] | None = None,
    topic: str | None = None,
) -> list[Skill]:
    out = ALL_SKILLS
    if subject:
        out = [s for s in out if s.subject == subject]
    if years:
        wanted = {int(y) for y in years}
        out = [s for s in out if s.year in wanted]
    if topic:
        out = [s for s in out if s.topic == topic]
    return list(out)


@cache
def topics_for(subject: str, year: int) -> list[str]:
    seen: list[str] = []
    for skill in ALL_SKILLS:
        if skill.subject == subject and skill.year == year and skill.topic not in seen:
            seen.append(skill.topic)
    return seen


@cache
def topic_tree(subject: str) -> list[tuple[int, str, tuple[Skill, ...]]]:
    """[(year, topic, skills)] ordered by year then curriculum order."""
    out: list[tuple[int, str, tuple[Skill, ...]]] = []
    for year in (1, 2, 3):
        for topic in topics_for(subject, year):
            group = tuple(
                s
                for s in ALL_SKILLS
                if s.subject == subject and s.year == year and s.topic == topic
            )
            out.append((year, topic, group))
    return out


def subject_counts() -> dict[str, dict[int, int]]:
    """{subject: {year: number of skills}} — used on the parent overview."""
    counts: dict[str, dict[int, int]] = {s: {1: 0, 2: 0, 3: 0} for s in SUBJECTS}
    for skill in ALL_SKILLS:
        counts[skill.subject][skill.year] += 1
    return counts
