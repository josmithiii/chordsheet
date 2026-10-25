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
    # An added degree is measured from a dominant chord (MusicXML), so the 7
    # added to a sus4 is the minor seventh at alter 0: MuseScore 4.7.5 names
    # that A7sus4, and alter -1 "Asus4b7" (checked 2026-10-24). An "alter"
    # degree is measured from the chord's own: 5 at +1 is the sharp fifth.
    "7sus4": ("suspended-fourth", ((7, 0, "add"),)), "7sus": ("suspended-fourth", ((7, 0, "add"),)),
    "9sus4": ("suspended-fourth", ((7, 0, "add"), (9, 0, "add"))),
    "9sus": ("suspended-fourth", ((7, 0, "add"), (9, 0, "add"))),
    "sus4(#5)": ("suspended-fourth", ((5, 1, "alter"),)),
    "sus2(b5)": ("suspended-second", ((5, -1, "alter"),)),
    "7b13": ("dominant", ((13, -1, "add"),)),
    "7#9b13": ("dominant", ((9, 1, "add"), (13, -1, "add"))),
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
    if token in ("or", "|", "/") or _BASS_ONLY_RE.match(token) or _run(token):
        return True
    m = _CHORD_RE.match(token)
    return bool(m) and m.group(2) in QUALITIES


def _run(token: str) -> list[str]:
    """'C-Am-Dm7-G' -> its chords: a run, played in quick succession. A token
    that is one chord ('C-', minor) or has a piece that is not a chord is no run."""
    pieces = token.split("-")
    if len(pieces) < 2 or not all(pieces):
        return []
    for p in pieces:
        m = _CHORD_RE.match(p)
        if not (m and m.group(2) in QUALITIES):
            return []
    return pieces


@dataclass
class Placed:
    """A chord at a character column of its chord line."""
    column: int
    chord: Chord
    bar: int = 0                # with bar lines (| A G | D |): which bar, from 0
    beat: int = -1              # with beat slashes (| E / A / |): which beat of its bar; -1 = none written


@dataclass
class ChordLine:
    chords: list[Placed] = field(default_factory=list)
    barred: bool = False        # written with | bar lines
    slashed: bool = False       # with / beats inside the bars


def parse_chord_line(line: str, previous: Chord | None = None) -> ChordLine:
    """Every token of `line` is a chord, "/X" (the chord before over X), a
    run "C-Am-Dm7-G", "|" (a bar line) or "or" (the next chord is an
    alternative to the one before)."""
    toks = line.split()
    out = ChordLine(barred="|" in toks, slashed="|" in toks and "/" in toks)
    pending_or = False
    bar = 0
    slot = 0                    # beats written so far in this bar (chords and slashes)
    for m in re.finditer(r"\S+", line):
        tok, col = m.group(0), m.start()
        if tok == "|":
            if slot:
                bar += 1
                slot = 0
            continue
        if tok == "/":
            if not out.slashed:
                raise ChordError(f"a beat slash outside bar lines: {line.strip()!r}")
            slot += 1
            continue
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
            chords = [Chord(base.root, base.suffix, b.group(1))]
        elif _run(tok):
            chords = [parse_chord(p) for p in _run(tok)]
        else:
            chords = [parse_chord(tok)]
        if pending_or:
            last = out.chords[-1]
            last.chord = Chord(last.chord.root, last.chord.suffix, last.chord.bass, alt=chords[0].text())
            pending_or = False
            continue
        for k, chord in enumerate(chords):
            out.chords.append(Placed(col + k, chord, bar, slot if out.slashed else -1))
            slot += 1
    if pending_or:
        raise ChordError(f"'or' with no chord after it: {line.strip()!r}")
    return out


_CHORDISH_RE = re.compile(r"^[A-G][#b]?\S*$")


def looks_like_bad_chord_line(line: str) -> bool:
    """A chord line with a chord this reader does not know ("As7", "Eb/",
    "Fdim(III)"): every token starts like a chord and at least half are
    chords. Read as a lyric, it would hide the mistake; it must fail."""
    toks = line.split()
    if not toks or looks_like_chord_line(line):
        return False
    marks = ("or", "|", "/")
    if not all(t in marks or _CHORDISH_RE.match(t) for t in toks):
        return False
    chords = [t for t in toks if t not in marks]
    good = sum(1 for t in chords if is_chord_token(t))
    return good >= 1 and 2 * good >= len(chords)


def looks_like_chord_line(line: str) -> bool:
    toks = line.split()
    return bool(toks) and all(is_chord_token(t) for t in toks) and any(t not in ("or", "|", "/") for t in toks)


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
