"""Tests for chordsheet, on a made-up song (no real lyrics)."""
from __future__ import annotations

import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from chordsheet.chords import ChordError, Key, looks_like_chord_line, parse_chord, parse_chord_line, parse_key
from chordsheet.cli import main
from chordsheet.musicxml import to_musicxml
from chordsheet.sheet import SheetError, build_song, read_sheet, report

SONG = """\
Paper Boats - test version

[Intro]: Am  F  C  G

[Verse 1]
       Am                C
We fold the morning into paper boats
F        G        C
And send them down the gutter
     Am      Am7/G       F     C/E
They spin a little, catch the light, and go
   Dm7 or F     G       C
Wherever water wants them

[Verse 2]
We fold the evening into paper planes
And throw them at the shutters
They dip a little, find the wind, and climb
Wherever air will take them

[Chorus]
F           G          Am
Nothing that we make stays
F           G          C    C/E
All of it is borrowed

[Solo over Verse]

[Chorus]
Nothing that we keep stays
All of it is borrowed

[Outro]: Am F C
"""


def song(text: str = SONG, **kw):
    return build_song(read_sheet(text), **kw)


def bars_text(s) -> list[str]:
    return [" ".join(c.text() for c in b.beats if c) or "%" for b in s.bars()]


# ── chords

def test_parse_chord() -> None:
    c = parse_chord("F#m7/E")
    assert (c.root, c.suffix, c.bass, c.kind) == ("F#", "m7", "E", "minor-seventh")
    assert parse_chord("DM7/C#").kind == "major-seventh"
    assert parse_chord("Bb").kind == "major"
    assert parse_chord("Cadd9").degrees == ((9, 0, "add"),)


def test_unknown_quality_fails() -> None:
    with pytest.raises(ChordError, match="unknown chord quality"):
        parse_chord("C7#9b13")


def test_chord_line_or_and_bass_only() -> None:
    cl = parse_chord_line("   Dm7 or F     G   C  /E")
    assert [p.chord.text() for p in cl.chords] == ["Dm7", "G", "C", "C/E"]
    assert cl.chords[0].chord.alt == "F"
    assert [p.column for p in cl.chords] == [3, 16, 20, 23]


def test_chord_line_detection() -> None:
    assert looks_like_chord_line("  Am   F  C/E ")
    assert looks_like_chord_line("D or Bm7 E A")
    assert not looks_like_chord_line("And send them down the gutter")
    assert not looks_like_chord_line("or")


def test_keys() -> None:
    assert parse_key("A major").fifths == 3
    assert parse_key("F# minor").fifths == 3
    assert parse_key("Bbm") == Key("Bb", True)
    with pytest.raises(ChordError):
        parse_key("H major")


# ── the sheet

def test_title_and_sections() -> None:
    sh = read_sheet(SONG)
    assert (sh.title, sh.subtitle) == ("Paper Boats", "test version")
    assert [s.name for s in sh.sections] == ["Intro", "Verse 1", "Verse 2", "Chorus", "Solo over Verse", "Chorus", "Outro"]


def test_preamble_is_skipped() -> None:
    text = ("https://example.com/tabs/paper-boats\n\nAuthor\nsomebody 1,234\nTitle: Paper Boats \n"
            "C#m (446654)\n\nVerse:\nC       G\nWe fold the morning\n")
    sh = read_sheet(text)
    assert sh.title == "Paper Boats" and sh.preamble == 5
    assert [s.name for s in sh.sections] == ["Verse"]
    assert bars_text(build_song(sh)) == ["C", "G"]


def test_named_headers() -> None:
    sh = read_sheet("Intro: D A7 D\n\nChorus 2:\nG       D\nla la la la\n")
    assert [s.name for s in sh.sections] == ["Intro", "Chorus 2"]
    assert bars_text(build_song(sh)) == ["D", "A7", "D", "G", "D"]


def test_placement_rules() -> None:
    b = bars_text(song())
    assert b[:4] == ["Am", "F", "C", "G"]                 # inline chords: a bar each
    assert b[4:6] == ["Am", "C"]                          # 2 chords, 2 bars
    assert b[6:8] == ["F G", "C"]                         # 3: the first bar takes two
    assert b[8:10] == ["Am Am7/G", "F C/E"]               # 4: two a bar
    first = song().bars()[6]
    assert [c.text() if c else None for c in first.beats] == ["F", None, "G", None]   # beats 1 and 3


def test_alternative_kept() -> None:
    b = song().bars()[10]
    assert b.beats[0].text() == "Dm7" and b.beats[0].alt == "F"


def test_chordless_lines_copy_earlier_section_of_same_kind() -> None:
    s = song()
    v1, v2 = s.sections[1], s.sections[2]
    assert [l.bars for l in v2.lines] == [l.bars for l in v1.lines]
    assert v2.lines[0].lyric.startswith("We fold the evening")
    assert all(l.how == "from Verse 1" for l in v2.lines)


def test_empty_section_repeats_its_kind() -> None:
    s = song()
    solo = s.sections[4]
    assert solo.how == "repeats Verse 2"
    assert [l.bars for l in solo.lines] == [l.bars for l in s.sections[1].lines]
    assert all(l.lyric == "" for l in solo.lines)


def test_chords_at_the_end_go_in_the_last_bar() -> None:
    text = "[A]\nG\nWalk on\n\n[B]\n                 D   /F#\nThe road goes on forever\n"
    assert bars_text(song(text)) == ["G", "%", "%", "D D/F#"]
    # One column before the last word, the even rule applies instead.
    text = "[A]\nG\nWalk on\n\n[B]\n                D   /F#\nThe road goes on forever\n"
    assert bars_text(song(text)) == ["G", "%", "D", "D/F#"]


def test_chordless_line_with_nothing_to_copy_fails() -> None:
    text = "[A]\nG       C\nWalk on home\nand on\n"
    with pytest.raises(SheetError, match="line 4 .*--hold"):
        song(text)


def test_hold_holds_and_says_so() -> None:
    text = "[A]\nG       C\nWalk on home\nand on\n"
    s = song(text, hold=True)
    assert bars_text(s) == ["G", "C", "%", "%"]
    assert any(n.startswith("*** line 4") for n in s.notes)


def test_no_chords_fails() -> None:
    with pytest.raises(SheetError, match="no chord lines"):
        read_sheet("Just words\nand more words\n")


def test_too_many_chords_fails() -> None:
    with pytest.raises(SheetError, match="do not fit"):
        song("[A]\nC D E F G A B C D\nla la la\n", bars_per_line=2)


def test_report_lists_every_bar() -> None:
    r = report(song())
    assert "[Solo over Verse]  (repeats Verse 2)" in r
    assert "| F G | C |" in r


# ── MusicXML

def xml_of(s, key: Key = Key("C", False)) -> ET.Element:
    text = to_musicxml(s, key, "Nobody")
    return ET.fromstring(text.split("\n", 2)[2])


def test_musicxml_structure() -> None:
    s = song()
    root = xml_of(s)
    measures = root.findall("./part/measure")
    assert len(measures) == len(s.bars())
    assert root.findtext("./work/work-title") == "Paper Boats"
    assert root.findtext("./movement-title") == "Paper Boats"
    assert root.findtext("./identification/creator") == "Nobody"
    assert root.find("./credit") is None
    assert root.findtext(".//key/fifths") == "0"
    for m in measures:
        assert len(m.findall("note")) == 4
        assert all(n.findtext("notehead") == "slash" for n in m.findall("note"))
    assert measures[-1].findtext("./barline/bar-style") == "light-heavy"


def test_harmony_at_its_beat() -> None:
    m = xml_of(song()).findall("./part/measure")[6]          # F on beat 1, G on beat 3
    beat = 0
    found: list[tuple[int, str]] = []
    for e in m:
        if e.tag == "harmony":
            found.append((beat, e.findtext("root/root-step")))
            assert "text" not in e.find("kind").attrib
        elif e.tag == "note":
            beat += 1
    assert found == [(0, "F"), (2, "G")]


def test_rehearsal_letters_by_kind() -> None:
    root = xml_of(song())
    marks = [r.text for r in root.iter("rehearsal")]
    # Intro A, Verse B (Verse 2 and the solo over the verse too), Chorus C, Outro D
    assert marks == ["A", "B", "B", "C", "B", "C", "D"]


# ── the command

def test_cli_writes_musicxml(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "paper.txt"
    src.write_text(SONG)
    out = tmp_path / "paper.musicxml"
    assert main([str(src), "-o", str(out), "--composer", "Nobody"]) == 0
    assert out.read_text().startswith("<?xml")
    printed = capsys.readouterr().out
    assert "key A minor, from the last chord (C)" not in printed       # last chord is C -> C major
    assert "key C major, from the last chord (C)" in printed


def test_cli_missing_file(tmp_path: Path) -> None:
    assert main([str(tmp_path / "nope.txt")]) == 1


def test_cli_bad_sheet(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "bad.txt"
    src.write_text("[A]\nG       C\nWalk on home\nand on\n")
    assert main([str(src), "-o", str(tmp_path / "bad.musicxml")]) == 1
    assert capsys.readouterr().err.startswith("***")


# ── MuseNik's own iReal Pro reader, compiled from a MuseNik checkout

MUSENIK_CORE = Path(os.environ.get("MO", "/nonexistent")) / "MuseNik" / "src" / "core"
DRIVER = r"""
#include "IRealChart.h"
#include <cstdio>
#include <fstream>
#include <iterator>
int main(int, char** argv) {
    std::ifstream in(argv[1]);
    const std::string xml((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    try {
        auto c = musenik::irealChart(xml, 0, 0, false, "untitled", false);
        std::printf("%s\n%s\n", c.title.c_str(), c.progression.c_str());
    } catch (const std::exception& e) { std::fprintf(stderr, "%s\n", e.what()); return 1; }
}
"""


@pytest.mark.skipif(not (MUSENIK_CORE / "IRealChart.cpp").is_file() or not shutil.which("clang++"),
                    reason="needs $MO/MuseNik and clang++")
def test_musenik_ireal_reads_it(tmp_path: Path) -> None:
    (tmp_path / "main.cpp").write_text(DRIVER)
    exe = tmp_path / "irealcheck"
    subprocess.run(["clang++", "-std=c++17", f"-I{MUSENIK_CORE}", str(tmp_path / "main.cpp"),
                    str(MUSENIK_CORE / "IRealChart.cpp"), str(MUSENIK_CORE / "MiniXml.cpp"), "-o", str(exe)], check=True)
    xml = tmp_path / "paper.musicxml"
    xml.write_text(to_musicxml(song(), Key("C", False)))
    r = subprocess.run([str(exe), str(xml)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    title, prog = r.stdout.splitlines()
    assert title == "Paper Boats"
    assert prog.startswith("*A[T44A-, , , |F, , , |C, , , |G, , , ]*B[A-, , , |C, , , |F, ,G, |")
    assert prog.endswith("Z")
