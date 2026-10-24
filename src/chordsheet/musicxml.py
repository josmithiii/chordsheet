"""A Song as a MusicXML 4.0 lead sheet: slash notation, chord symbols, the
section names, and each lyric line as text under its first bar.

Written to suit MuseNik's readers as well as MuseScore: the chords are
<harmony> elements at their beats (MuseNik's iReal Pro chart reads them,
src/core/IRealChart.cpp), and rehearsal marks are only A to D, the ones
iReal Pro has; the section's own name goes beside the letter as words."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from .chords import Chord, Key, note_parts
from .sheet import Song, _kind

DOCTYPE = ('<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
           '"http://www.musicxml.org/dtds/partwise.dtd">')
LETTERS = "ABCD"


def _sub(parent: ET.Element, tag: str, body: str | None = None, **attrs: str) -> ET.Element:
    e = ET.SubElement(parent, tag, attrs)
    if body is not None:
        e.text = body
    return e


def _harmony(parent: ET.Element, c: Chord) -> None:
    h = _sub(parent, "harmony")
    root = _sub(h, "root")
    step, alter = note_parts(c.root)
    _sub(root, "root-step", step)
    if alter:
        _sub(root, "root-alter", str(alter))
    # No text attribute: MuseScore 4.0 takes it as the whole chord name, root
    # and all ("m" for F#m). MuseScore spells the kind in the score's style.
    _sub(h, "kind", c.kind)
    if c.bass:
        bass = _sub(h, "bass")
        bstep, balter = note_parts(c.bass)
        _sub(bass, "bass-step", bstep)
        if balter:
            _sub(bass, "bass-alter", str(balter))
    for value, alter_, type_ in c.degrees:
        d = _sub(h, "degree")
        _sub(d, "degree-value", str(value))
        _sub(d, "degree-alter", str(alter_))
        _sub(d, "degree-type", type_)


def _words(parent: ET.Element, text: str, placement: str, **font: str) -> None:
    d = _sub(parent, "direction", placement=placement)
    dt = _sub(d, "direction-type")
    _sub(dt, "words", text, **font)


def rehearsal_letters(song: Song) -> tuple[dict[str, str], list[str]]:
    """A letter per kind of section, in order of first appearance; "Solo to
    Verse" counts as a Verse. Kinds after the fourth get none."""
    letters: dict[str, str] = {}
    notes: list[str] = []
    for s in song.sections:
        kind = _kind(s.name)
        if kind in letters or not s.name:
            continue
        if len(letters) < len(LETTERS):
            letters[kind] = LETTERS[len(letters)]
        else:
            letters[kind] = ""
            notes.append(f"{s.name}: no rehearsal letter (iReal Pro has A to D only)")
    return letters, notes


def to_musicxml(song: Song, key: Key, composer: str = "", lyrics: bool = True, bars_per_system: int = 4) -> str:
    beats = song.beats_per_bar
    letters, _ = rehearsal_letters(song)
    score = ET.Element("score-partwise", version="4.0")
    # The title as both <work-title> (MuseNik's iReal Pro chart reads that
    # first) and <movement-title> (MuseScore 4.0 shows that as the title).
    # No <credit>s: with any credit, MuseScore 4.0 shows only the credits,
    # and unplaced ones land on top of each other. So the subtitle is not
    # printed.
    if song.title:
        _sub(_sub(score, "work"), "work-title", song.title)
        _sub(score, "movement-title", song.title)
    ident = _sub(score, "identification")
    if composer:
        _sub(ident, "creator", composer, type="composer")
    _sub(_sub(ident, "encoding"), "software", "chordsheet")
    part_list = _sub(score, "part-list")
    sp = _sub(part_list, "score-part", id="P1")
    _sub(sp, "part-name", "Chords", **{"print-object": "no"})
    part = _sub(score, "part", id="P1")

    bars = song.bars()
    in_system = 0
    for n, bar in enumerate(bars, start=1):
        m = _sub(part, "measure", number=str(n))
        if n > 1 and (bar.section or in_system == bars_per_system):
            _sub(m, "print", **{"new-system": "yes"})
            in_system = 0
        in_system += 1
        if n == 1:
            attrs = _sub(m, "attributes")
            _sub(attrs, "divisions", "1")
            k = _sub(attrs, "key")
            _sub(k, "fifths", str(key.fifths))
            _sub(k, "mode", "minor" if key.minor else "major")
            t = _sub(attrs, "time")
            _sub(t, "beats", str(beats))
            _sub(t, "beat-type", "4")
            clef = _sub(attrs, "clef")
            _sub(clef, "sign", "G")
            _sub(clef, "line", "2")
        if bar.section:
            letter = letters.get(_kind(bar.section), "")
            if letter:   # a direction of its own: MuseScore 4.0 shows one direction-type of several
                _sub(_sub(_sub(m, "direction", placement="above"), "direction-type"), "rehearsal", letter)
            _words(m, bar.section, "above", **{"font-weight": "bold"})
        if lyrics and bar.lyric:
            _words(m, bar.lyric, "below", **{"font-style": "italic", "font-size": "9"})
        for beat in bar.beats:
            if beat is not None:
                if beat.alt:
                    _words(m, f"(or {beat.alt})", "below", **{"font-size": "9"})
                _harmony(m, beat)
            note = _sub(m, "note")
            pitch = _sub(note, "pitch")
            _sub(pitch, "step", "B")
            _sub(pitch, "octave", "4")
            _sub(note, "duration", "1")
            _sub(note, "type", "quarter")
            _sub(note, "stem", "none")
            _sub(note, "notehead", "slash")
        if n == len(bars) or bar.section_end:
            bl = _sub(m, "barline", location="right")
            _sub(bl, "bar-style", "light-heavy" if n == len(bars) else "light-light")

    ET.indent(score, space="  ")
    return '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + DOCTYPE + "\n" + \
        ET.tostring(score, encoding="unicode") + "\n"
