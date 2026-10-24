"""Chord symbols as written in text sheets: parsing, and MusicXML's names for them."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Suffix as written -> MusicXML <kind>, plus any <degree>s as (value, alter, type).
QUALITIES: dict[str, tuple[str, tuple[tuple[int, int, str], ...]]] = {
    "": ("major", ()),
    "m": ("minor", ()), "min": ("minor", ()), "-": ("minor", ()),
    "7": ("dominant", ()),
    "m7": ("minor-seventh", ()), "min7": ("minor-seventh", ()), "-7": ("minor-seventh", ()),
    "maj7": ("major-seventh", ()), "Maj7": ("major-seventh", ()), "M7": ("major-seventh", ()),
    "^7": ("major-seventh", ()), "^": ("major-seventh", ()),
    "6": ("major-sixth", ()), "m6": ("minor-sixth", ()),
    "9": ("dominant-ninth", ()), "maj9": ("major-ninth", ()), "M9": ("major-ninth", ()),
    "m9": ("minor-ninth", ()),
    "11": ("dominant-11th", ()), "13": ("dominant-13th", ()),
    "dim": ("diminished", ()), "o": ("diminished", ()),
    "dim7": ("diminished-seventh", ()), "o7": ("diminished-seventh", ()),
    "m7b5": ("half-diminished", ()), "m7-5": ("half-diminished", ()), "h7": ("half-diminished", ()),
    "aug": ("augmented", ()), "+": ("augmented", ()),
    "sus": ("suspended-fourth", ()), "sus4": ("suspended-fourth", ()),
    "sus2": ("suspended-second", ()),
    "add9": ("major", ((9, 0, "add"),)),
    "5": ("power", ()),
}

_NOTE = r"[A-G][#b]?"
_CHORD_RE = re.compile(rf"^({_NOTE})(.*?)(?:/({_NOTE}))?$")
_BASS_ONLY_RE = re.compile(rf"^/({_NOTE})$")

STEP_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


class ChordError(ValueError):
    pass


@dataclass(frozen=True)
class Chord:
    root: str               # "F#"
    suffix: str             # "m7", as written
    bass: str = ""          # "E", or "" for none
    alt: str = ""           # an alternative the sheet offers ("D or Bm7" -> alt "Bm7")

    @property
    def kind(self) -> str:
        return QUALITIES[self.suffix][0]

    @property
    def degrees(self) -> tuple[tuple[int, int, str], ...]:
        return QUALITIES[self.suffix][1]

    @property
    def minor(self) -> bool:
        return self.kind in ("minor", "minor-seventh", "minor-sixth", "minor-ninth")

    def text(self) -> str:
        return self.root + self.suffix + (f"/{self.bass}" if self.bass else "")


def note_parts(note: str) -> tuple[str, int]:
    """("F#") -> ("F", 1)."""
    return note[0], {"": 0, "#": 1, "b": -1}[note[1:]]


def parse_chord(token: str) -> Chord:
    m = _CHORD_RE.match(token)
    if not m:
        raise ChordError(f"not a chord: {token!r}")
    root, suffix, bass = m.group(1), m.group(2), m.group(3) or ""
    if suffix not in QUALITIES:
        raise ChordError(f"unknown chord quality {suffix!r} in {token!r} "
                         f"(known: {', '.join(repr(q) for q in QUALITIES if q)})")
    return Chord(root, suffix, bass)


def is_chord_token(token: str) -> bool:
    if token == "or" or _BASS_ONLY_RE.match(token):
        return True
    m = _CHORD_RE.match(token)
    return bool(m) and m.group(2) in QUALITIES


@dataclass
class Placed:
    """A chord at a character column of its chord line."""
    column: int
    chord: Chord


@dataclass
class ChordLine:
    chords: list[Placed] = field(default_factory=list)


def parse_chord_line(line: str, previous: Chord | None = None) -> ChordLine:
    """Every token of `line` is a chord, "/X" (the chord before over X) or
    "or" (the next chord is an alternative to the one before)."""
    out = ChordLine()
    pending_or = False
    for m in re.finditer(r"\S+", line):
        tok, col = m.group(0), m.start()
        if tok == "or":
            if not out.chords or pending_or:
                raise ChordError(f"'or' with no chord before it: {line.strip()!r}")
            pending_or = True
            continue
        b = _BASS_ONLY_RE.match(tok)
        if b:
            base = out.chords[-1].chord if out.chords else previous
            if base is None:
                raise ChordError(f"{tok!r} with no chord before it: {line.strip()!r}")
            chord = Chord(base.root, base.suffix, b.group(1))
        else:
            chord = parse_chord(tok)
        if pending_or:
            last = out.chords[-1]
            last.chord = Chord(last.chord.root, last.chord.suffix, last.chord.bass, alt=chord.text())
            pending_or = False
        else:
            out.chords.append(Placed(col, chord))
    if pending_or:
        raise ChordError(f"'or' with no chord after it: {line.strip()!r}")
    return out


def looks_like_chord_line(line: str) -> bool:
    toks = line.split()
    return bool(toks) and all(is_chord_token(t) for t in toks) and any(t != "or" for t in toks)


# ── Keys

MAJOR_FIFTHS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
                "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7}
MINOR_FIFTHS = {"A": 0, "E": 1, "B": 2, "F#": 3, "C#": 4, "G#": 5, "D#": 6, "A#": 7,
                "D": -1, "G": -2, "C": -3, "F": -4, "Bb": -5, "Eb": -6, "Ab": -7}


@dataclass(frozen=True)
class Key:
    tonic: str
    minor: bool

    @property
    def fifths(self) -> int:
        table = MINOR_FIFTHS if self.minor else MAJOR_FIFTHS
        if self.tonic not in table:
            raise ChordError(f"no key signature for {self.tonic} {'minor' if self.minor else 'major'}")
        return table[self.tonic]

    def __str__(self) -> str:
        return f"{self.tonic} {'minor' if self.minor else 'major'}"


def parse_key(text: str) -> Key:
    m = re.fullmatch(rf"\s*({_NOTE})\s*(major|minor|maj|min|m)?\s*", text)
    if not m:
        raise ChordError(f"not a key: {text!r} (e.g. 'A major', 'F# minor', 'Bbm')")
    k = Key(m.group(1), (m.group(2) or "major") in ("minor", "min", "m"))
    k.fifths  # noqa: B018 - refuses a key with no signature
    return k
