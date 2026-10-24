"""A chords-over-lyrics text sheet: sections, lines, and the bars they make.

Placement rules (no melody or rhythm is written in such a sheet, so these are
the tool's whole idea of time; `report` prints what they gave):

- A chord line over a lyric line is `bars_per_line` bars. The first chord is
  on the line's first downbeat (words before it are a pickup). The chords are
  spread over the bars in order, as evenly as they go, earlier bars taking the
  extra ones; inside a bar, evenly over its beats (two chords in 4/4: beats 1
  and 3). Columns are used for one thing: when every chord sits at or after
  the start of the line's last word, the chords go in the last bar and the
  bars before it hold the chord before.
- A chord line with no lyric under it (and chords after a [Section]: header)
  is one bar per chord.
- A lyric line with no chords takes the chords of the same line of the most
  recent earlier section of the same kind ("Verse 4" -> the last "Verse"
  before it). Without one, it is an error, or with `hold` the chord before
  is held through it.
- A section with no lines at all ("[Bridge]") repeats the most recent section
  of its kind; "[Solo to Verse]" repeats the most recent Verse.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .chords import Chord, ChordError, ChordLine, looks_like_chord_line, parse_chord_line

_HEADER_RE = re.compile(r"^\s*\[([^\]]+)\]\s*:?\s*(.*)$")
# "Verse:", "Chorus 2:", "Intro: D A7 D" - a section name without brackets.
_NAMED_HEADER_RE = re.compile(
    r"^\s*((?:intro|verse|chorus|pre-?chorus|bridge|outro|solo|instrumental|interlude|refrain|tag|coda|ending)"
    r"(?:\s*\d+)?)\s*:\s*(.*)$", re.IGNORECASE)
_TITLE_RE = re.compile(r"^\s*title\s*:\s*(.+?)\s*$", re.IGNORECASE)


def _header(line: str) -> re.Match[str] | None:
    return _HEADER_RE.match(line) or _NAMED_HEADER_RE.match(line)
_TO_RE = re.compile(r"^(.*?)\s+(?:to|over|on)\s+(.+)$", re.IGNORECASE)


class SheetError(ValueError):
    pass


@dataclass
class TextLine:
    number: int                 # 1-based line number in the file
    chords: ChordLine | None
    lyric: str | None


@dataclass
class TextSection:
    name: str
    number: int                 # line number of its header (0 for the part before any header)
    lines: list[TextLine] = field(default_factory=list)


@dataclass
class TextSheet:
    title: str
    subtitle: str
    sections: list[TextSection]
    preamble: int = 0           # lines before the song (a web page's header, chord diagrams), skipped


def _kind(name: str) -> str:
    """'Verse 2' -> 'verse'; 'Solo to Verse' -> 'verse' (it is played over one)."""
    m = _TO_RE.match(name)
    if m:
        name = m.group(2)
    return re.sub(r"\s*\d+\s*$", "", name).strip().lower()


def read_sheet(text: str) -> TextSheet:
    raw = text.splitlines()
    # The song starts at the first chord line or section header. What comes
    # before is not lyrics: the title, a web page's header, chord diagrams.
    start = next((k for k, l in enumerate(raw) if _header(l) or looks_like_chord_line(l)), len(raw))
    preamble = [l.strip() for l in raw[:start] if l.strip()]
    title = subtitle = ""
    named = [m.group(1) for m in map(_TITLE_RE.match, preamble) if m]
    if named:
        title = named[0]
    else:
        first = next((l for l in preamble if not re.match(r"^\w+://", l)), "")
        parts = re.split(r"\s+-\s+", first, maxsplit=1)
        title = parts[0]
        subtitle = parts[1] if len(parts) > 1 else ""
    i = start

    sections: list[TextSection] = [TextSection("", 0)]
    previous: Chord | None = None

    def chord_line(s: str, number: int) -> ChordLine:
        nonlocal previous
        try:
            cl = parse_chord_line(s, previous)
        except ChordError as e:
            raise SheetError(f"line {number}: {e}") from e
        if cl.chords:
            previous = cl.chords[-1].chord
        return cl

    while i < len(raw):
        line, number = raw[i].rstrip(), i + 1
        if not line.strip():
            i += 1
            continue
        h = _header(line)
        if h:
            sections.append(TextSection(h.group(1).strip(), number))
            rest = h.group(2)
            if rest.strip():
                if not looks_like_chord_line(rest):
                    raise SheetError(f"line {number}: after [{h.group(1)}] only chords may follow, not {rest.strip()!r}")
                sections[-1].lines.append(TextLine(number, chord_line(rest, number), None))
            i += 1
            continue
        if looks_like_chord_line(line):
            nxt = raw[i + 1].rstrip() if i + 1 < len(raw) else ""
            if nxt.strip() and not _header(nxt) and not looks_like_chord_line(nxt):
                sections[-1].lines.append(TextLine(number, chord_line(line, number), nxt.strip()))
                i += 2
            else:
                sections[-1].lines.append(TextLine(number, chord_line(line, number), None))
                i += 1
            continue
        sections[-1].lines.append(TextLine(number, None, line.strip()))
        i += 1

    if not sections[0].lines:
        sections.pop(0)
    if not any(l.chords for s in sections for l in s.lines):
        raise SheetError("no chord lines: nothing to chart")
    return TextSheet(title, subtitle, sections, len(preamble))


# ── Bars

Beat = Chord | None


@dataclass
class Bar:
    beats: list[Beat]
    lyric: str = ""             # the lyric line that starts in this bar
    section: str = ""           # the section that starts in this bar
    section_end: bool = False


@dataclass
class Line:
    bars: list[list[Beat]]
    lyric: str
    how: str = ""               # "", "copied from Verse 3", "held"


@dataclass
class Section:
    name: str
    lines: list[Line]
    how: str = ""               # "", "repeats Bridge"

    @property
    def has_chords(self) -> bool:
        return any(c for l in self.lines for b in l.bars for c in b)


@dataclass
class Song:
    title: str
    subtitle: str
    beats_per_bar: int
    sections: list[Section]
    notes: list[str] = field(default_factory=list)

    def bars(self) -> list[Bar]:
        out: list[Bar] = []
        for s in self.sections:
            first = True
            for line in s.lines:
                for j, beats in enumerate(line.bars):
                    out.append(Bar(list(beats), line.lyric if j == 0 else "", s.name if first else ""))
                    first = False
            if out:
                out[-1].section_end = True
        return out

    def last_chord(self) -> Chord:
        for b in reversed(self.bars()):
            for c in reversed(b.beats):
                if c:
                    return c
        raise SheetError("no chords")


def _spread(n: int, slots: int) -> list[int]:
    """n items over `slots` places, evenly, starting at 0."""
    return [i * slots // n for i in range(n)]


def _line_bars(tl: TextLine, bars_per_line: int, beats: int) -> list[list[Beat]]:
    assert tl.chords is not None
    chords = tl.chords.chords
    if tl.lyric is None:
        return [[p.chord] + [None] * (beats - 1) for p in chords]
    bars: list[list[Beat]] = [[None] * beats for _ in range(bars_per_line)]
    words = list(re.finditer(r"\S+", tl.lyric))
    last_word = words[-1].start() if words else 0
    if len(chords) <= beats and all(p.column >= last_word for p in chords) and bars_per_line > 1:
        target = [bars_per_line - 1]
    else:
        target = list(range(bars_per_line))
    n = len(chords)
    if n > len(target) * beats:
        raise SheetError(f"line {tl.number}: {n} chords do not fit {len(target)} bar(s) of {beats} beats")
    # Bars get the chords in order, as evenly as they go, earlier bars the extra.
    if n <= len(target):
        counts = [0] * len(target)
        for k in _spread(n, len(target)):
            counts[k] = 1
    else:
        base, extra = divmod(n, len(target))
        counts = [base + (1 if k < extra else 0) for k in range(len(target))]
    it = iter(chords)
    for bar_index, count in zip(target, counts):
        for beat in _spread(count, beats) if count else []:
            bars[bar_index][beat] = next(it).chord
    return bars


def build_song(sheet: TextSheet, bars_per_line: int = 2, beats_per_bar: int = 4, hold: bool = False) -> Song:
    if bars_per_line < 1:
        raise SheetError("bars per line must be at least 1")
    song = Song(sheet.title, sheet.subtitle, beats_per_bar, [])

    def latest(kind: str) -> Section | None:
        for s in reversed(song.sections):
            if _kind(s.name) == kind and s.has_chords:
                return s
        return None

    for ts in sheet.sections:
        where = f"[{ts.name}] (line {ts.number})" if ts.name else "the lines before any [Section]"
        if not ts.lines:
            kind = _kind(ts.name)
            model = latest(kind)
            if model is None:
                raise SheetError(f"{where} has no lines, and there is no {kind!r} section before it to repeat")
            lines = [Line([list(b) for b in l.bars], "", f"from {model.name}") for l in model.lines]
            song.sections.append(Section(ts.name, lines, f"repeats {model.name}"))
            song.notes.append(f"{ts.name}: no lines in the sheet; repeats the chords of {model.name}")
            continue
        lines: list[Line] = []
        for idx, tl in enumerate(ts.lines):
            if tl.chords is not None:
                lines.append(Line(_line_bars(tl, bars_per_line, beats_per_bar), tl.lyric or ""))
                continue
            model = None
            for s in reversed(song.sections):
                if (_kind(s.name) == _kind(ts.name) and idx < len(s.lines)
                        and any(c for b in s.lines[idx].bars for c in b)):
                    model = s
                    break
            if model is not None:
                bars = [list(b) for b in model.lines[idx].bars]
                lines.append(Line(bars, tl.lyric or "", f"from {model.name}"))
            elif hold:
                lines.append(Line([[None] * beats_per_bar for _ in range(bars_per_line)], tl.lyric or "", "held"))
                song.notes.append(f"*** line {tl.number} ({ts.name or 'no section'}): no chords, and no earlier "
                                  f"{_kind(ts.name) or 'section'} has a line {idx + 1} to copy; the chord before is held")
            else:
                raise SheetError(f"line {tl.number} in {where}: a lyric line with no chords, and no earlier "
                                 f"section of the same kind with a line {idx + 1} to copy them from. "
                                 f"Write its chords in the sheet, or pass --hold to hold the chord before.")
        copied = sum(1 for l in lines if l.how.startswith("from"))
        if copied:
            sources = sorted({l.how[5:] for l in lines if l.how.startswith("from")})
            song.notes.append(f"{ts.name or 'no section'}: {copied} line(s) with no chords take those of "
                              f"{', '.join(sources)}")
        song.sections.append(Section(ts.name, lines))

    first = song.bars()[0]
    if first.beats[0] is None:
        raise SheetError("the song's first bar starts with no chord to hold")
    return song


def report(song: Song) -> str:
    """The chart as text: one row per line of the sheet."""
    def bar_text(b: list[Beat]) -> str:
        cs = [c.text() + (f" (or {c.alt})" if c.alt else "") for c in b if c]
        return " ".join(cs) if cs else "%"
    out: list[str] = []
    n = 1
    for s in song.sections:
        out.append(f"[{s.name}]" + (f"  ({s.how})" if s.how else ""))
        for l in s.lines:
            cells = " | ".join(bar_text(b) for b in l.bars)
            tag = f"  <- {l.how}" if l.how and not s.how else ""
            out.append(f"  {n:3d}  | {cells} |{tag}")
            n += len(l.bars)
    return "\n".join(out)
