"""Scheme-neutral systematic phonics content for the Primary English pathway.

This is deliberately a transparent starter progression rather than a branded
SSP programme.  Schools can use different teaching orders, so the catalogue
keeps stages, graphemes, word examples, and prerequisites explicit while the
learner-facing Coach uses a cumulative default order.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass

from .curriculum import Skill
from .generators import generator, mc, txt


@dataclass(frozen=True)
class PhonicsMeta:
    """Teaching metadata used by the progression-aware phonics scheduler."""

    stage: int
    order: int
    prerequisites: tuple[str, ...] = ()
    grapheme: str = ""


PHONICS_META: dict[str, PhonicsMeta] = {}
PRIMARY_PHONICS_EXTRA: list[Skill] = []


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _gpc_id(grapheme: str) -> str:
    return f"e1.phonics.gpc.{_slug(grapheme)}"


def _skill(
    sid: str,
    name: str,
    year: int,
    stage: int,
    order: int,
    nc_ref: str,
    builder: Callable[[random.Random, int], dict],
    *,
    prerequisites: tuple[str, ...] = (),
    grapheme: str = "",
) -> Skill:
    """Register one generated phonics skill and its progression metadata."""
    generator_name = "phonics_" + _slug(sid).replace("-", "_")

    def question(rng: random.Random, level: int = 1) -> dict:
        return builder(rng, level)

    question.__name__ = generator_name
    generator(generator_name)(question)
    skill = Skill(
        sid,
        name,
        "english",
        f"Phonics · Stage {stage}",
        year,
        "generated",
        generator_name,
        nc_ref,
        ("phonics", f"phonics-stage-{stage}"),
    )
    PHONICS_META[sid] = PhonicsMeta(
        stage=stage,
        order=order,
        prerequisites=prerequisites,
        grapheme=grapheme,
    )
    PRIMARY_PHONICS_EXTRA.append(skill)
    return skill


def _mastery_complete(progress) -> bool:
    """Use a modest threshold before a phonics target unlocks the next stage."""
    return bool(
        progress
        and progress.attempts >= 2
        and progress.mastery >= 0.75
    )


def phonics_candidates(skills: list[Skill], progress: dict[str, object]) -> list[Skill]:
    """Return the lowest incomplete stage whose prerequisites are complete.

    Direct skill practice can still be requested from the curriculum page, but
    the Coach itself does not jump over an unfinished earlier stage.
    """
    phonics = [skill for skill in skills if skill.is_phonics]
    if not phonics:
        return []

    unlocked = [
        skill
        for skill in phonics
        if all(_mastery_complete(progress.get(prerequisite)) for prerequisite in PHONICS_META[skill.id].prerequisites)
    ]
    if not unlocked:
        return [skill for skill in phonics if PHONICS_META[skill.id].stage == 1]

    incomplete = [skill for skill in unlocked if not _mastery_complete(progress.get(skill.id))]
    if not incomplete:
        return sorted(unlocked, key=lambda skill: (PHONICS_META[skill.id].stage, PHONICS_META[skill.id].order))

    stage = min(PHONICS_META[skill.id].stage for skill in incomplete)
    return [skill for skill in unlocked if PHONICS_META[skill.id].stage == stage]


def phonics_stage_summary(progress: dict[str, object]) -> dict[str, object]:
    """Return small UI-safe progression information for learner/parent views."""
    stages: dict[int, list[Skill]] = {}
    for skill in PRIMARY_PHONICS_EXTRA:
        stages.setdefault(PHONICS_META[skill.id].stage, []).append(skill)
    current = 1
    for stage in sorted(stages):
        if all(_mastery_complete(progress.get(skill.id)) for skill in stages[stage]):
            current = stage + 1
            continue
        current = stage
        break
    current = min(current, max(stages, default=1))
    current_skills = stages.get(current, [])
    mastered = sum(_mastery_complete(progress.get(skill.id)) for skill in current_skills)
    return {
        "stage": current,
        "label": f"Stage {current}",
        "skills": len(current_skills),
        "mastered": mastered,
        "total": len(PRIMARY_PHONICS_EXTRA),
    }


def _gpc_question(
    grapheme: str,
    phoneme: str,
    sound_text: str,
    distractors: tuple[str, ...],
    words: tuple[tuple[str, tuple[str, ...]], ...],
    *,
    stage: int,
):
    def builder(rng: random.Random, level: int) -> dict:
        # Recognition comes first; once the target is familiar, the same GPC
        # also gets blended and segmented in order to avoid guessing-only data.
        variant = rng.choice(("gpc", "gpc", "blend", "segment")) if words else "gpc"
        if variant == "blend":
            word, graphemes = rng.choice(words)
            spoken = " · ".join(_SOUND_TEXT.get(item, item) for item in graphemes)
            question = txt(
                "Blend these sounds to make a word.",
                word,
                accept=[word.upper()],
                hint="Say each sound, then push the sounds together.",
                explain=f"{spoken} makes {word}.",
                keypad="text",
            )
            question.update(
                {
                    "phonics_type": "blend",
                    "graphemes": list(graphemes),
                    "sound_text": spoken,
                }
            )
            return question
        if variant == "segment":
            word, graphemes = rng.choice(words)
            segmented = "-".join(graphemes)
            question = txt(
                "Break this word into its sounds.",
                segmented,
                accept=[
                    " ".join(graphemes),
                    " | ".join(graphemes),
                    "/".join(graphemes),
                ],
                hint="Say the word slowly and listen for each sound.",
                explain=f"{word} can be split into {' - '.join(graphemes)}.",
                keypad="text",
            )
            question.update(
                {
                    "phonics_type": "segment",
                    "phonics_word": word,
                    "graphemes": list(graphemes),
                }
            )
            return question

        question = mc(
            f"Which grapheme makes the {phoneme} sound?",
            grapheme,
            list(distractors),
            rng,
            hint="Say the sound, then look for the letter or letters that represent it.",
            explain=f"{grapheme} represents the {phoneme} sound.",
        )
        question.update(
            {
                "phonics_type": "gpc",
                "phoneme": phoneme,
                "sound_text": sound_text,
                "grapheme": grapheme,
                "phonics_stage": stage,
            }
        )
        return question

    return builder


_SOUND_TEXT = {
    "a": "a as in apple",
    "b": "buh",
    "c": "kuh",
    "d": "duh",
    "e": "e as in egg",
    "f": "fff",
    "g": "guh",
    "h": "huh",
    "i": "i as in insect",
    "j": "juh",
    "k": "kuh",
    "l": "lll",
    "m": "mmm",
    "n": "nnn",
    "o": "o as in octopus",
    "p": "puh",
    "r": "rrr",
    "s": "sss",
    "t": "tuh",
    "u": "u as in umbrella",
    "v": "vuh",
    "w": "wuh",
    "x": "ks",
    "y": "yuh",
    "z": "zzz",
    "sh": "shh",
    "ch": "ch",
    "th": "th",
    "ng": "ng",
    "ck": "kuh",
    "ee": "ee",
    "oo": "oo",
    "ai": "ay",
    "oa": "oa",
    "igh": "igh",
    "ar": "ar",
    "or": "or",
    "ur": "ur",
    "ow": "ow",
    "oi": "oy",
    "ear": "ear",
    "air": "air",
    "ure": "ure",
    "er": "er",
    "a_e": "ay",
    "e_e": "ee",
    "i_e": "igh",
    "o_e": "oa",
    "u_e": "yoo",
}


_CORE_GPCS = (
    ("s", "/s/", ("sun", ("s", "u", "n"))),
    ("a", "/a/", ("at", ("a", "t"))),
    ("t", "/t/", ("tap", ("t", "a", "p"))),
    ("p", "/p/", ("pat", ("p", "a", "t"))),
    ("i", "/i/", ("sit", ("s", "i", "t"))),
    ("n", "/n/", ("pin", ("p", "i", "n"))),
    ("m", "/m/", ("mat", ("m", "a", "t"))),
    ("d", "/d/", ("sad", ("s", "a", "d"))),
)

_STAGE1_IDS = (
    "e1.phonics.oral-blending",
    "e1.phonics.oral-segmenting",
)
_CORE_IDS = tuple(_gpc_id(grapheme) for grapheme, _, _ in _CORE_GPCS)


# Stage 1: oral phonemic awareness before printed GPC work.
_ORAL_WORDS = (
    ("sat", ("s", "a", "t")),
    ("mat", ("m", "a", "t")),
    ("pin", ("p", "i", "n")),
    ("tap", ("t", "a", "p")),
    ("sit", ("s", "i", "t")),
)


def _oral_blend(rng: random.Random, level: int) -> dict:
    word, graphemes = rng.choice(_ORAL_WORDS)
    spoken = " · ".join(_SOUND_TEXT.get(item, item) for item in graphemes)
    question = txt(
        "Blend the sounds to make a word.",
        word,
        accept=[word.upper()],
        hint="Say the sounds slowly, then say them faster together.",
        explain=f"{spoken} makes {word}.",
        keypad="text",
    )
    question.update(
        {
            "phonics_type": "blend",
            "graphemes": list(graphemes),
            "sound_text": spoken,
        }
    )
    return question


def _oral_segment(rng: random.Random, level: int) -> dict:
    word, graphemes = rng.choice(_ORAL_WORDS)
    answer = "-".join(graphemes)
    question = txt(
        "Break the word into its sounds.",
        answer,
        accept=[" ".join(graphemes), " | ".join(graphemes), "/".join(graphemes)],
        hint="Stretch the word and count the sounds you hear.",
        explain=f"{word} can be split into {' - '.join(graphemes)}.",
        keypad="text",
    )
    question.update(
        {
            "phonics_type": "segment",
            "phonics_word": word,
            "graphemes": list(graphemes),
        }
    )
    return question


_skill(
    _STAGE1_IDS[0],
    "Oral blending",
    1,
    1,
    1,
    "Blend spoken sounds together to say a word",
    _oral_blend,
)
_skill(
    _STAGE1_IDS[1],
    "Oral segmenting",
    1,
    1,
    2,
    "Say and separate the sounds in simple words",
    _oral_segment,
)


# Stage 2 and 3: core and extending single-letter GPCs.
_GPC_DEFINITIONS = [
    ("s", "/s/", ("c", "f", "z"), (("sun", ("s", "u", "n")),)),
    ("a", "/a/", ("e", "i", "o"), (("at", ("a", "t")),)),
    ("t", "/t/", ("d", "p", "c"), (("tap", ("t", "a", "p")),)),
    ("p", "/p/", ("b", "t", "q"), (("pat", ("p", "a", "t")),)),
    ("i", "/i/", ("e", "a", "y"), (("sit", ("s", "i", "t")),)),
    ("n", "/n/", ("m", "r", "u"), (("pin", ("p", "i", "n")),)),
    ("m", "/m/", ("n", "w", "r"), (("mat", ("m", "a", "t")),)),
    ("d", "/d/", ("b", "t", "g"), (("sad", ("s", "a", "d")),)),
    ("g", "/g/", ("j", "c", "q"), (("gap", ("g", "a", "p")),)),
    ("o", "/o/", ("a", "u", "e"), (("dog", ("d", "o", "g")),)),
    ("c", "/k/", ("k", "s", "t"), (("cat", ("c", "a", "t")),)),
    ("k", "/k/", ("c", "q", "x"), (("kit", ("k", "i", "t")),)),
    ("e", "/e/", ("i", "a", "u"), (("bed", ("b", "e", "d")),)),
    ("u", "/u/", ("o", "a", "e"), (("sun", ("s", "u", "n")),)),
    ("r", "/r/", ("w", "l", "n"), (("run", ("r", "u", "n")),)),
    ("h", "/h/", ("n", "r", "f"), (("hat", ("h", "a", "t")),)),
    ("b", "/b/", ("d", "p", "h"), (("big", ("b", "i", "g")),)),
    ("f", "/f/", ("v", "s", "th"), (("fit", ("f", "i", "t")),)),
    ("l", "/l/", ("r", "i", "j"), (("lip", ("l", "i", "p")),)),
    ("j", "/j/", ("g", "y", "ch"), (("jam", ("j", "a", "m")),)),
    ("v", "/v/", ("f", "w", "b"), (("van", ("v", "a", "n")),)),
    ("w", "/w/", ("v", "u", "r"), (("wet", ("w", "e", "t")),)),
    ("x", "/ks/", ("c", "z", "s"), (("fix", ("f", "i", "x")),)),
    ("y", "/y/", ("j", "i", "w"), (("yes", ("y", "e", "s")),)),
    ("z", "/z/", ("s", "x", "j"), (("zip", ("z", "i", "p")),)),
]

for order, (grapheme, phoneme, distractors, words) in enumerate(_GPC_DEFINITIONS, start=1):
    stage = 2 if grapheme in {item[0] for item in _CORE_GPCS} else 3
    prerequisites = _STAGE1_IDS if stage == 2 else _CORE_IDS
    _skill(
        _gpc_id(grapheme),
        f"The {grapheme} sound",
        1,
        stage,
        10 + order,
        f"Recognise and apply the {grapheme} grapheme for the {phoneme} sound",
        _gpc_question(
            grapheme,
            phoneme,
            _SOUND_TEXT.get(grapheme, grapheme),
            distractors,
            words,
            stage=stage,
        ),
        prerequisites=prerequisites,
        grapheme=grapheme,
    )


# Common consonant digraphs.
_DIGRAPHS = [
    ("sh", "/sh/", ("ch", "s", "th"), (("ship", ("sh", "i", "p")), ("shop", ("sh", "o", "p")))),
    ("ch", "/ch/", ("sh", "t", "j"), (("chip", ("ch", "i", "p")), ("chat", ("ch", "a", "t")))),
    ("th", "/th/", ("f", "t", "sh"), (("thin", ("th", "i", "n")), ("math", ("m", "a", "th")))),
    ("ng", "/ng/", ("n", "g", "nk"), (("sing", ("s", "i", "ng")), ("ring", ("r", "i", "ng")))),
    ("ck", "/k/", ("c", "k", "ch"), (("sick", ("s", "i", "ck")), ("back", ("b", "a", "ck")))),
]

for order, (grapheme, phoneme, distractors, words) in enumerate(_DIGRAPHS, start=1):
    prerequisites = tuple(_gpc_id(letter) for letter in set(grapheme) if letter in {item[0] for item in _GPC_DEFINITIONS})
    _skill(
        f"e1.phonics.digraph.{grapheme}",
        f"The {grapheme} digraph",
        1,
        3,
        100 + order,
        f"Read words containing the {grapheme} digraph",
        _gpc_question(
            grapheme,
            phoneme,
            _SOUND_TEXT[grapheme],
            distractors,
            words,
            stage=3,
        ),
        prerequisites=prerequisites or _CORE_IDS,
        grapheme=grapheme,
    )


# Stage 4: blending beyond simple CVC words, pseudo-words, and decodable text.
_ADJACENT_WORDS = (
    ("stop", ("s", "t", "o", "p")),
    ("frog", ("f", "r", "o", "g")),
    ("clap", ("c", "l", "a", "p")),
    ("swim", ("s", "w", "i", "m")),
    ("hand", ("h", "a", "n", "d")),
    ("milk", ("m", "i", "l", "k")),
)


def _blend_words(words: tuple[tuple[str, tuple[str, ...]], ...], label: str):
    def builder(rng: random.Random, level: int) -> dict:
        word, graphemes = rng.choice(words)
        spoken = " · ".join(_SOUND_TEXT.get(item, item) for item in graphemes)
        question = txt(
            f"Blend the sounds to make a {label}.",
            word,
            accept=[word.upper()],
            hint="Keep every sound in order, then say the word smoothly.",
            explain=f"{spoken} makes {word}.",
            keypad="text",
        )
        question.update(
            {
                "phonics_type": "blend",
                "graphemes": list(graphemes),
                "sound_text": spoken,
                "phonics_label": label.title(),
            }
        )
        return question

    return builder


_ADJACENT_PREREQS = tuple(_gpc_id(item[0]) for item in _GPC_DEFINITIONS)
_skill(
    "e1.phonics.blending.adjacent-consonants",
    "Blend adjacent consonants",
    1,
    4,
    200,
    "Read words with adjacent consonants by blending each sound",
    _blend_words(_ADJACENT_WORDS, "word with adjacent consonants"),
    prerequisites=_ADJACENT_PREREQS,
)

_PSEUDO_WORDS = (
    ("mip", ("m", "i", "p")),
    ("sheb", ("sh", "e", "b")),
    ("zog", ("z", "o", "g")),
    ("nash", ("n", "a", "sh")),
    ("vot", ("v", "o", "t")),
)
_skill(
    "e1.phonics.decoding.pseudo-words",
    "Blend pretend words",
    1,
    4,
    201,
    "Apply phonic knowledge to decode unfamiliar and pseudo-words",
    _blend_words(_PSEUDO_WORDS, "pretend word"),
    prerequisites=("e1.phonics.blending.adjacent-consonants",),
)

_DECODABLE_TEXT = (
    (
        "The cat sat on a mat.",
        "Where did the cat sit?",
        "a mat",
        ("a log", "a hill", "a bed"),
    ),
    (
        "A frog can hop.",
        "What can the frog do?",
        "hop",
        ("swim", "sing", "run"),
    ),
    (
        "The ship is in the shop.",
        "Where is the ship?",
        "in the shop",
        ("on the hill", "in a bin", "at home"),
    ),
)


def _decodable_sentence(rng: random.Random, level: int) -> dict:
    passage, prompt, answer, distractors = rng.choice(_DECODABLE_TEXT)
    question = mc(
        prompt,
        answer,
        list(distractors),
        rng,
        hint="Read the sentence slowly and find the answer in the words.",
        explain=f"The sentence says: {passage}",
    )
    question.update(
        {
            "phonics_type": "decodable",
            "decodable_text": passage,
            "speak_text": passage,
        }
    )
    return question


_skill(
    "e1.phonics.read.decodable-sentences",
    "Read decodable sentences",
    1,
    4,
    202,
    "Read aloud accurately books closely matched to taught phonics",
    _decodable_sentence,
    prerequisites=("e1.phonics.blending.adjacent-consonants",),
)


# Stage 5: common vowel patterns and split digraphs.
_VOWEL_GPCS = [
    ("ee", "/ee/", ("ea", "e", "ie"), (("sheep", ("sh", "ee", "p")), ("green", ("g", "r", "ee", "n")))),
    ("oo", "/oo/", ("ou", "u", "oa"), (("moon", ("m", "oo", "n")), ("book", ("b", "oo", "k")))),
    ("ai", "/ay/", ("ay", "a_e", "eigh"), (("rain", ("r", "ai", "n")), ("mail", ("m", "ai", "l")))),
    ("oa", "/oa/", ("ow", "o_e", "oe"), (("boat", ("b", "oa", "t")), ("goat", ("g", "oa", "t")))),
    ("igh", "/igh/", ("i", "ie", "y"), (("light", ("l", "igh", "t")), ("night", ("n", "igh", "t")))),
    ("ar", "/ar/", ("a", "are", "au"), (("farm", ("f", "ar", "m")), ("star", ("s", "t", "ar")))),
    ("or", "/or/", ("aw", "a", "oor"), (("fork", ("f", "or", "k")), ("storm", ("s", "t", "or", "m")))),
    ("ur", "/ur/", ("er", "ir", "ear"), (("turn", ("t", "ur", "n")), ("burst", ("b", "ur", "s", "t")))),
    ("ow", "/ow/", ("ou", "oa", "ough"), (("cow", ("c", "ow")), ("down", ("d", "ow", "n")))),
    ("oi", "/oy/", ("oy", "ou", "oi_e"), (("coin", ("c", "oi", "n")), ("join", ("j", "oi", "n")))),
    ("ear", "/ear/", ("eer", "ere", "ier"), (("hear", ("h", "ear")), ("near", ("n", "ear")))),
    ("air", "/air/", ("are", "ear", "ere"), (("fair", ("f", "air")), ("hair", ("h", "air")))),
    ("ure", "/ure/", ("our", "oor", "ur"), (("pure", ("p", "ure")), ("cure", ("c", "ure")))),
    ("er", "/er/", ("ur", "ir", "ear"), (("fern", ("f", "er", "n")), ("herd", ("h", "er", "d")))),
]

for order, (grapheme, phoneme, distractors, words) in enumerate(_VOWEL_GPCS, start=1):
    prereqs = ("e1.phonics.blending.adjacent-consonants",)
    _skill(
        f"e2.phonics.gpc.{_slug(grapheme)}",
        f"The {grapheme} spelling",
        2,
        5,
        300 + order,
        f"Read words containing the {grapheme} grapheme or trigraph",
        _gpc_question(
            grapheme,
            phoneme,
            _SOUND_TEXT[grapheme],
            distractors,
            words,
            stage=5,
        ),
        prerequisites=prereqs,
        grapheme=grapheme,
    )

_SPLIT_WORDS = (
    ("make", ("m", "a_e", "k")),
    ("time", ("t", "i_e", "m")),
    ("home", ("h", "o_e", "m")),
    ("cube", ("c", "u_e", "b")),
)
_skill(
    "e2.phonics.split-digraphs",
    "Split digraphs",
    2,
    5,
    320,
    "Apply phonic knowledge to decode words with split digraphs",
    _gpc_question(
        "a_e",
        "/ay/",
        "ay",
        ("ai", "ee", "igh"),
        (("make", ("m", "a_e", "k")),),
        stage=5,
    ),
    prerequisites=("e1.phonics.blending.adjacent-consonants",),
    grapheme="a_e",
)


def _alternative_spellings(rng: random.Random, level: int) -> dict:
    question = mc(
        "Which grapheme can represent the /ay/ sound?",
        "eigh",
        ["ai", "ee", "oa"],
        rng,
        hint="Say each spelling aloud and listen for the /ay/ sound.",
        explain="The spelling eigh can represent the /ay/ sound in words such as eight.",
    )
    question.update(
        {
            "phonics_type": "gpc",
            "phoneme": "/ay/",
            "sound_text": "ay",
            "phonics_stage": 6,
        }
    )
    return question


_skill(
    "e2.phonics.alternative-spellings",
    "Alternative spellings",
    2,
    6,
    400,
    "Read words with alternative spellings for familiar phonemes",
    _alternative_spellings,
    prerequisites=("e2.phonics.split-digraphs",),
)


def _tricky_word(rng: random.Random, level: int) -> dict:
    question = mc(
        "Which word is a common exception word?",
        "said",
        ["sat", "sand", "sip"],
        rng,
        hint="This word has a part that does not follow the usual sound pattern.",
        explain="Said is a common exception word that children learn to read by sight alongside phonics.",
    )
    question.update(
        {
            "phonics_type": "tricky",
            "sound_text": "said",
            "phonics_stage": 6,
        }
    )
    return question


_skill(
    "e2.phonics.common-exception-words",
    "Common exception words",
    2,
    6,
    401,
    "Read common exception words alongside taught phonics",
    _tricky_word,
    prerequisites=("e2.phonics.alternative-spellings",),
)
