# chordsheet

Turns a chords-over-lyrics text sheet (the kind on guitar-chord sites, e.g.
`/l/mus/Lyrics/FieldsOfGoldEvaCassidy.txt`) into a MusicXML lead sheet:
slash notation, chord symbols on their beats, section names, each lyric line
as text under its first bar. MuseScore lays it out, transposes it and prints
it; MuseNik opens it with **Edit Score** and makes an iReal Pro chart of it
(`musenik ireal <file>`, `src/core/IRealChart.cpp` there).

    uv run chordsheet SHEET.txt -o SONG.musicxml [--pdf] [--composer NAME] [--key "A major"]
    uv run chordsheet --help
    uv run pytest
    ./doit                      # tests, then Fields of Gold into out/

It prints the chart it made, bar by bar, and every guess it took (`***` for
a held line). Check it against the recording: a text sheet has no bar lines.

## How time is decided

The rules are in `src/chordsheet/sheet.py`'s docstring. In short: a lyric
line is `--bars-per-line` bars (2); its first chord is on the downbeat; the
chords are spread evenly over the bars, earlier bars taking the extra, and
evenly over the beats inside a bar; chords that all sit at or after the last
word go in the last bar. A lyric line without chords copies the same line of
the last section of its kind ("Verse 4" from "Verse 3"); an empty `[Bridge]`
repeats the last Bridge, `[Solo to Verse]` the last Verse. Anything else with
no chords is an error, or with `--hold` holds the chord before.

Everything before the first chord line or section header is skipped (a web
page's header, chord diagrams); `Title: X` there names the song. Sections are
`[Name]` or `Name:` (Intro, Verse 2, Chorus, ...), optionally followed by
chords on the same line (one bar each).

## Written for MuseNik's readers

- Rehearsal marks are only A to D, one per kind of section (iReal Pro has no
  others; MuseNik refuses the rest). The section's name goes beside it.
- The title is in both `<work-title>` (MuseNik reads that) and
  `<movement-title>` (MuseScore 4.0 shows that). No `<credit>`s, so a
  subtitle is not printed.
- `<kind>` has no `text` attribute: MuseScore 4.0 shows that text in place
  of the whole chord.

`tests/test_chordsheet.py::test_musenik_ireal_reads_it` compiles MuseNik's
`IRealChart.cpp` from `$MO/MuseNik` and runs it on the output.

## MuseScore

`--pdf` refuses MuseScore older than 4.1. MuseScore 4.0.0 (installed here
2026-10-23) prints chord symbols without their roots, and its `-o x.mscx`
empties the folder it writes into. MuseNik is tested on 4.7.5.
