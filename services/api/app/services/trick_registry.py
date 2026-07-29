"""
Canonical trick registry — single source of truth for trick names, categories,
biomechanical checkpoints, and normalization.

Every trick the pipeline touches flows through here. The TrickPicker on mobile
uses the same canonical names. Stats, progression, and Gemini prompts all
resolve against this registry.

ADDING A TRICK: add an entry to TRICK_REGISTRY. That's it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TrickCategoryId = Literal[
    "fundamentals", "flip", "grind", "slide", "rotation", "manual", "transition"
]


@dataclass(frozen=True)
class BiomechanicalCheckpoint:
    """One thing to watch for on a specific trick — fed into Pro tier Gemini prompt."""

    body_part: str  # e.g. "front foot", "shoulders", "knees", "hips"
    mechanic: str  # what to observe, e.g. "flick angle off nose pocket"
    good_signal: str  # what it looks like when done well
    bad_signal: str  # what it looks like when off


@dataclass(frozen=True)
class TrickEntry:
    """One canonical trick in the registry."""

    name: str  # display name, exact casing — "Kickflip", "50-50"
    category: TrickCategoryId
    rotation: str | None = None  # "front", "back", None
    aliases: tuple[str, ...] = ()  # fuzzy match targets: ("kflip", "kick flip")
    checkpoints: tuple[BiomechanicalCheckpoint, ...] = ()
    difficulty_tier: int = 1  # 1=beginner, 2=intermediate, 3=advanced
    prerequisites: tuple[str, ...] = ()  # canonical names of tricks to learn first


# ---------------------------------------------------------------------------
# REGISTRY
# ---------------------------------------------------------------------------

TRICK_REGISTRY: tuple[TrickEntry, ...] = (
    # === FUNDAMENTALS ===
    TrickEntry(
        name="Ollie",
        category="fundamentals",
        difficulty_tier=1,
        aliases=("olly", "ollie"),
        checkpoints=(
            BiomechanicalCheckpoint(
                body_part="back foot",
                mechanic="tail pop — snap down through ball of foot",
                good_signal="crisp pop with full ankle extension, tail hits ground",
                bad_signal="mushy press instead of snap, no audible pop",
            ),
            BiomechanicalCheckpoint(
                body_part="front foot",
                mechanic="slide up toward nose after pop",
                good_signal="foot drags from mid-board to bolts, levels the board at peak",
                bad_signal="foot stays flat or lifts off board instead of sliding",
            ),
            BiomechanicalCheckpoint(
                body_part="knees",
                mechanic="compression before pop, tuck at peak",
                good_signal="deep bend before pop, knees pull up to chest in air",
                bad_signal="stiff legs, minimal knee tuck, low height",
            ),
            BiomechanicalCheckpoint(
                body_part="shoulders",
                mechanic="stay level and square to board",
                good_signal="shoulders parallel to board throughout, no twist",
                bad_signal="shoulders open or rotate, causing board to drift",
            ),
        ),
    ),
    TrickEntry(
        name="Shuvit",
        category="fundamentals",
        difficulty_tier=1,
        aliases=("shuv", "shuv-it", "shuv it"),
        prerequisites=("Ollie",),
        checkpoints=(
            BiomechanicalCheckpoint(
                body_part="back foot",
                mechanic="scoop backward to rotate board 180 under feet",
                good_signal="heel-side scoop sends board spinning flat, stays under body",
                bad_signal="board rockets out behind or goes vertical",
            ),
            BiomechanicalCheckpoint(
                body_part="front foot",
                mechanic="lift and hover while board rotates",
                good_signal="front foot lifts clean, stays over board path, catches bolts",
                bad_signal="front foot pushes forward or drifts off axis",
            ),
            BiomechanicalCheckpoint(
                body_part="hips",
                mechanic="stay centered over board rotation",
                good_signal="hips stay stacked above board, body doesn't drift",
                bad_signal="hips shift backward, landing behind the board",
            ),
        ),
    ),
    TrickEntry(
        name="Pop shuvit",
        category="fundamentals",
        difficulty_tier=1,
        aliases=("pop shuv", "pop shuv-it", "pop shuvit", "pop shuv it"),
        prerequisites=("Ollie", "Shuvit"),
        checkpoints=(
            BiomechanicalCheckpoint(
                body_part="back foot",
                mechanic="pop + scoop combined — tail hits ground then scoops backward",
                good_signal="board pops off ground and rotates 180 cleanly underneath",
                bad_signal="no pop height, board just slides on ground",
            ),
            BiomechanicalCheckpoint(
                body_part="front foot",
                mechanic="lift to let board rotate, catch at bolts",
                good_signal="foot lifts cleanly above spinning board, comes down on bolts",
                bad_signal="foot interferes with rotation or lands in middle of board",
            ),
            BiomechanicalCheckpoint(
                body_part="shoulders",
                mechanic="stay square to direction of travel",
                good_signal="no upper body rotation — only the board spins",
                bad_signal="shoulders turn with the scoop, body follows board rotation",
            ),
        ),
    ),
    TrickEntry(
        name="Front shuvit",
        category="fundamentals",
        difficulty_tier=1,
        aliases=("front shuv", "front shuv-it", "fs shuv", "frontside shuvit", "frontshuvit"),
        prerequisites=("Shuvit",),
        checkpoints=(
            BiomechanicalCheckpoint(
                body_part="back foot",
                mechanic="toe-side scoop to rotate board 180 frontside",
                good_signal="board spins flat frontside under feet, stays centered",
                bad_signal="board flies out in front or tilts vertical",
            ),
            BiomechanicalCheckpoint(
                body_part="front foot",
                mechanic="lift and guide — stays over board path",
                good_signal="front foot hovers above rotation, catches cleanly",
                bad_signal="foot drifts backward, misses the catch",
            ),
        ),
    ),
    TrickEntry(
        name="Boneless",
        category="fundamentals",
        difficulty_tier=1,
        aliases=("boneless one",),
    ),
    TrickEntry(
        name="No comply",
        category="fundamentals",
        difficulty_tier=1,
        aliases=("no-comply", "nocomply"),
    ),
    TrickEntry(
        name="Powerslide",
        category="fundamentals",
        difficulty_tier=1,
        aliases=("power slide",),
    ),
    TrickEntry(
        name="360 shuvit",
        category="fundamentals",
        difficulty_tier=2,
        aliases=("360 shuv", "3 shuv", "tre shuv"),
        prerequisites=("Pop shuvit",),
    ),
    # === FLIP TRICKS ===
    TrickEntry(
        name="Kickflip",
        category="flip",
        difficulty_tier=2,
        aliases=("kflip", "kick flip", "kick-flip"),
        prerequisites=("Ollie",),
        checkpoints=(
            BiomechanicalCheckpoint(
                body_part="front foot",
                mechanic="flick off heel-side edge of nose pocket",
                good_signal="foot slides up then flicks outward off the corner, clean rotation",
                bad_signal="foot flicks down (rocket flip) or straight out (no rotation)",
            ),
            BiomechanicalCheckpoint(
                body_part="back foot",
                mechanic="pop timing — snap before front foot flick",
                good_signal="pop initiates upward motion, front foot flick comes after board is rising",
                bad_signal="pop and flick happen simultaneously, board doesn't rise first",
            ),
            BiomechanicalCheckpoint(
                body_part="shoulders",
                mechanic="stay parallel to board, slight lean toe-side",
                good_signal="shoulders square, center of gravity stays over board",
                bad_signal="shoulders open up or lean heel-side, landing behind board",
            ),
            BiomechanicalCheckpoint(
                body_part="back foot",
                mechanic="catch — back foot stops rotation by pressing down on grip",
                good_signal="back foot meets board mid-rotation and presses it level",
                bad_signal="board over-rotates or under-rotates, no active catch",
            ),
            BiomechanicalCheckpoint(
                body_part="knees",
                mechanic="tuck at peak to let board flip underneath",
                good_signal="knees pull up, full flip visible before catch",
                bad_signal="legs stay low, board hits feet before completing flip",
            ),
        ),
    ),
    TrickEntry(
        name="Heelflip",
        category="flip",
        difficulty_tier=2,
        aliases=("heel flip", "heel-flip", "hflip"),
        prerequisites=("Ollie",),
        checkpoints=(
            BiomechanicalCheckpoint(
                body_part="front foot",
                mechanic="flick out off toe-side edge of nose with heel",
                good_signal="heel pushes out and forward off the nose corner, clean heelside rotation",
                bad_signal="foot kicks straight out or flicks down, board doesn't flip cleanly",
            ),
            BiomechanicalCheckpoint(
                body_part="back foot",
                mechanic="pop straight down — no scoop",
                good_signal="tail snaps clean, board goes straight up before flick",
                bad_signal="scoop mixed in causes unwanted shuvit rotation",
            ),
            BiomechanicalCheckpoint(
                body_part="shoulders",
                mechanic="stay square or slight lean heel-side",
                good_signal="shoulders stay over board, body follows straight up",
                bad_signal="upper body twists or leans toe-side, drifts away from board",
            ),
            BiomechanicalCheckpoint(
                body_part="front foot",
                mechanic="catch with front foot on bolts after full rotation",
                good_signal="front foot comes down and stops rotation on the grip",
                bad_signal="board over/under-rotates, foot lands mid-board or misses",
            ),
        ),
    ),
    TrickEntry(
        name="Pressureflip",
        category="flip",
        difficulty_tier=2,
        aliases=("pressure flip", "pressure-flip", "p flip"),
        prerequisites=("Ollie", "Shuvit"),
        checkpoints=(
            BiomechanicalCheckpoint(
                body_part="back foot",
                mechanic="pressure between toes and tail to force underside flip + rotation",
                good_signal="board flips inward and rotates simultaneously from foot pressure alone",
                bad_signal="board only shuvits or only flips, not both",
            ),
            BiomechanicalCheckpoint(
                body_part="front foot",
                mechanic="lift cleanly to let board complete the pressure rotation",
                good_signal="front foot rises out of the way, board finishes rotation underneath",
                bad_signal="front foot blocks or interferes with board path",
            ),
            BiomechanicalCheckpoint(
                body_part="hips",
                mechanic="stay centered — pressure flips want to push you backward",
                good_signal="hips stacked above landing zone, weight centered",
                bad_signal="body drifts backward, landing off the board",
            ),
        ),
    ),
    TrickEntry(
        name="Varial kickflip",
        category="flip",
        difficulty_tier=2,
        aliases=("varial kick", "varial kflip", "varial flip"),
        prerequisites=("Kickflip", "Pop shuvit"),
    ),
    TrickEntry(
        name="Varial heelflip",
        category="flip",
        difficulty_tier=2,
        aliases=("varial heel",),
        prerequisites=("Heelflip", "Front shuvit"),
    ),
    TrickEntry(
        name="Hardflip",
        category="flip",
        difficulty_tier=3,
        aliases=("hard flip",),
        prerequisites=("Kickflip", "Pop shuvit"),
    ),
    TrickEntry(
        name="Inward heelflip",
        category="flip",
        difficulty_tier=3,
        aliases=("inward heel",),
        prerequisites=("Heelflip", "Pop shuvit"),
    ),
    TrickEntry(
        name="Tre flip",
        category="flip",
        difficulty_tier=3,
        aliases=("tre", "360 flip", "360 kickflip", "3 flip"),
        prerequisites=("Kickflip", "360 shuvit"),
    ),
    TrickEntry(
        name="Laser flip",
        category="flip",
        difficulty_tier=3,
        aliases=("laser",),
        prerequisites=("Heelflip", "360 shuvit"),
    ),
    TrickEntry(
        name="360 hardflip",
        category="flip",
        difficulty_tier=3,
        prerequisites=("Hardflip", "360 shuvit"),
    ),
    TrickEntry(
        name="Double kickflip",
        category="flip",
        difficulty_tier=3,
        aliases=("double kick", "double kflip"),
        prerequisites=("Kickflip",),
    ),
    TrickEntry(
        name="Double heelflip",
        category="flip",
        difficulty_tier=3,
        aliases=("double heel",),
        prerequisites=("Heelflip",),
    ),
    TrickEntry(
        name="Impossible",
        category="flip",
        difficulty_tier=3,
        aliases=("impossible flip",),
        prerequisites=("Ollie",),
        checkpoints=(
            BiomechanicalCheckpoint(
                body_part="back foot",
                mechanic="wrap — back foot scoops board around ankle in a vertical loop",
                good_signal="board wraps clean around back foot, one full vertical rotation",
                bad_signal="board flies off sideways or only half-wraps",
            ),
        ),
    ),
    TrickEntry(
        name="Dolphin flip",
        category="flip",
        difficulty_tier=3,
        aliases=("forward flip", "murder flip"),
        prerequisites=("Kickflip",),
    ),
    TrickEntry(
        name="Gazelle flip",
        category="flip",
        difficulty_tier=3,
        prerequisites=("Tre flip",),
    ),
    TrickEntry(
        name="Bigflip",
        category="flip",
        difficulty_tier=3,
        aliases=("big flip",),
        prerequisites=("Kickflip",),
    ),
    TrickEntry(
        name="Big heelflip",
        category="flip",
        difficulty_tier=3,
        prerequisites=("Heelflip",),
    ),
    TrickEntry(
        name="Hospital flip",
        category="flip",
        difficulty_tier=2,
        prerequisites=("Kickflip",),
    ),
    TrickEntry(
        name="Late flip",
        category="flip",
        difficulty_tier=3,
        prerequisites=("Ollie", "Kickflip"),
    ),
    # === GRINDS ===
    TrickEntry(
        name="50-50",
        category="grind",
        difficulty_tier=2,
        aliases=("fifty fifty", "5050"),
        prerequisites=("Ollie",),
        checkpoints=(
            BiomechanicalCheckpoint(
                body_part="knees",
                mechanic="bend on approach and lock in on contact",
                good_signal="low center of gravity, both trucks lock onto ledge/rail simultaneously",
                bad_signal="legs stiff on contact, trucks bounce or miss",
            ),
            BiomechanicalCheckpoint(
                body_part="shoulders",
                mechanic="stay parallel to obstacle through grind",
                good_signal="shoulders track along the obstacle, weight centered",
                bad_signal="shoulders twist, pulling body off the grind line",
            ),
        ),
    ),
    TrickEntry(name="5-0", category="grind", difficulty_tier=2, aliases=("five-o", "five o"), prerequisites=("Ollie",)),
    TrickEntry(name="Nosegrind", category="grind", difficulty_tier=2, aliases=("nose grind",), prerequisites=("Ollie",)),
    TrickEntry(name="Crooked grind", category="grind", difficulty_tier=2, aliases=("crook", "crooks"), prerequisites=("Nosegrind",)),
    TrickEntry(name="Smith grind", category="grind", difficulty_tier=2, aliases=("smith",), prerequisites=("50-50",)),
    TrickEntry(name="Feeble grind", category="grind", difficulty_tier=2, aliases=("feeble",), prerequisites=("50-50",)),
    TrickEntry(name="Overcrook", category="grind", difficulty_tier=3, aliases=("over crook",), prerequisites=("Crooked grind",)),
    TrickEntry(name="Willy grind", category="grind", difficulty_tier=2, aliases=("willy",), prerequisites=("Nosegrind",)),
    TrickEntry(name="Salad grind", category="grind", difficulty_tier=2, aliases=("salad",), prerequisites=("5-0",)),
    TrickEntry(name="Hurricane", category="grind", difficulty_tier=3, prerequisites=("Feeble grind",)),
    # === SLIDES ===
    TrickEntry(name="Boardslide", category="slide", difficulty_tier=2, aliases=("board slide", "bs slide"), prerequisites=("Ollie",)),
    TrickEntry(name="Lipslide", category="slide", difficulty_tier=2, aliases=("lip slide",), prerequisites=("Boardslide",)),
    TrickEntry(name="Noseslide", category="slide", difficulty_tier=2, aliases=("nose slide",), prerequisites=("Ollie",)),
    TrickEntry(name="Tailslide", category="slide", difficulty_tier=2, aliases=("tail slide",), prerequisites=("Ollie",)),
    TrickEntry(name="Bluntslide", category="slide", difficulty_tier=3, aliases=("blunt slide",), prerequisites=("Boardslide",)),
    TrickEntry(name="Nosebluntslide", category="slide", difficulty_tier=3, aliases=("noseblunt", "nose blunt slide"), prerequisites=("Noseslide",)),
    TrickEntry(name="Darkslide", category="slide", difficulty_tier=3, aliases=("dark slide",), prerequisites=("Boardslide",)),
    # === ROTATION ===
    TrickEntry(
        name="180",
        category="rotation",
        difficulty_tier=1,
        aliases=("ollie 180", "one eighty", "frontside180", "frontside 180", "fs 180", "backside180", "backside 180", "bs 180"),
        prerequisites=("Ollie",),
        checkpoints=(
            BiomechanicalCheckpoint(
                body_part="shoulders",
                mechanic="wind up before pop, lead the 180 rotation",
                good_signal="shoulders initiate turn just before pop, body follows as a unit",
                bad_signal="shoulders late or counter-rotate, board and body go different directions",
            ),
            BiomechanicalCheckpoint(
                body_part="head",
                mechanic="look in direction of rotation before takeoff",
                good_signal="head turns first, shoulders and hips follow naturally",
                bad_signal="looking straight or away from rotation direction",
            ),
            BiomechanicalCheckpoint(
                body_part="hips",
                mechanic="full 180 rotation — hips must complete the turn",
                good_signal="hips fully rotated at landing, riding away clean fakie/switch",
                bad_signal="hips stop at 90, revert needed to complete",
            ),
        ),
    ),
    TrickEntry(name="360", category="rotation", difficulty_tier=3, aliases=("three sixty", "ollie 360"), prerequisites=("180",)),
    TrickEntry(name="Bigspin", category="rotation", difficulty_tier=2, aliases=("big spin",), prerequisites=("180", "Pop shuvit")),
    TrickEntry(name="Sex change", category="rotation", difficulty_tier=1, aliases=("body varial",), prerequisites=("180",)),
    TrickEntry(name="Heelflip body varial", category="rotation", difficulty_tier=2, prerequisites=("Heelflip", "Sex change")),
    TrickEntry(name="Ghetto bird", category="rotation", difficulty_tier=3, prerequisites=("Kickflip", "180")),
    # === MANUALS ===
    TrickEntry(name="Manual", category="manual", difficulty_tier=1, aliases=("manny",)),
    TrickEntry(name="Nose manual", category="manual", difficulty_tier=2, aliases=("nose manny",), prerequisites=("Manual",)),
    TrickEntry(name="One-footed manual", category="manual", difficulty_tier=2, prerequisites=("Manual",)),
    TrickEntry(name="Manual kickflip out", category="manual", difficulty_tier=3, prerequisites=("Manual", "Kickflip")),
    TrickEntry(name="Manual shuvit out", category="manual", difficulty_tier=2, prerequisites=("Manual", "Shuvit")),
    # === TRANSITION ===
    TrickEntry(name="Rock to fakie", category="transition", difficulty_tier=1, aliases=("rock fakie",)),
    TrickEntry(name="Rock and roll", category="transition", difficulty_tier=1, aliases=("rock n roll",)),
    TrickEntry(name="Axle stall", category="transition", difficulty_tier=1, aliases=("axle",)),
    TrickEntry(name="Disaster", category="transition", difficulty_tier=2, prerequisites=("Ollie",)),
    TrickEntry(name="Blunt to fakie", category="transition", difficulty_tier=2, aliases=("blunt fakie",)),
)


# ---------------------------------------------------------------------------
# LOOKUP INDEXES (built once at import time)
# ---------------------------------------------------------------------------

# name (lowered) → TrickEntry
_BY_NAME: dict[str, TrickEntry] = {e.name.lower(): e for e in TRICK_REGISTRY}

# alias (lowered) → TrickEntry
_BY_ALIAS: dict[str, TrickEntry] = {}
for _e in TRICK_REGISTRY:
    for _a in _e.aliases:
        _BY_ALIAS[_a.lower()] = _e


def resolve_trick(raw_input: str) -> TrickEntry | None:
    """
    Resolve user input to a canonical TrickEntry.
    Checks exact name first, then aliases. Case-insensitive.
    Returns None if no match (custom trick — user typed something not in library).
    """
    clean = raw_input.strip().lower()
    if not clean:
        return None
    # Exact canonical name
    if clean in _BY_NAME:
        return _BY_NAME[clean]
    # Alias match
    if clean in _BY_ALIAS:
        return _BY_ALIAS[clean]
    return None


def normalize_trick_name(raw_input: str) -> str:
    """
    Returns the canonical display name if found, otherwise cleaned lowercase.
    This is the single place trick names get normalized for stats/DB.
    """
    entry = resolve_trick(raw_input)
    if entry:
        return entry.name.lower()  # "kickflip" — lowercase for DB consistency
    return raw_input.strip().lower()


def get_trick_checkpoints(trick_name: str) -> list[BiomechanicalCheckpoint]:
    """Return biomechanical checkpoints for a trick, empty list if none defined."""
    entry = resolve_trick(trick_name)
    if entry and entry.checkpoints:
        return list(entry.checkpoints)
    return []


def get_trick_prerequisites(trick_name: str) -> list[str]:
    """Return prerequisite trick names (canonical), empty list if none."""
    entry = resolve_trick(trick_name)
    if entry and entry.prerequisites:
        return list(entry.prerequisites)
    return []


def get_category_tricks(category: TrickCategoryId) -> list[TrickEntry]:
    """All tricks in a category, ordered by difficulty tier then name."""
    return sorted(
        [e for e in TRICK_REGISTRY if e.category == category],
        key=lambda e: (e.difficulty_tier, e.name.lower()),
    )


def get_all_canonical_names() -> list[str]:
    """Sorted list of all canonical trick names."""
    return sorted(e.name for e in TRICK_REGISTRY)


def format_checkpoints_for_prompt(trick_name: str) -> str:
    """
    Format biomechanical checkpoints as a prompt block for Gemini Pro tier.
    Returns empty string if no checkpoints defined for this trick.
    """
    checkpoints = get_trick_checkpoints(trick_name)
    if not checkpoints:
        return ""

    entry = resolve_trick(trick_name)
    display_name = entry.name if entry else trick_name

    lines = [f"Biomechanical checkpoints for {display_name}:"]
    for i, cp in enumerate(checkpoints, 1):
        lines.append(f"  {i}. [{cp.body_part}] {cp.mechanic}")
        lines.append(f"     Good: {cp.good_signal}")
        lines.append(f"     Off: {cp.bad_signal}")

    lines.append(
        "Use these as observation targets — report what you see against each checkpoint "
        "when visible. Do not fabricate observations for checkpoints you cannot see in the clip."
    )
    return "\n".join(lines)

