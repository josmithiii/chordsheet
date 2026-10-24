# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`README.md` is the user-facing account (usage, the time rules in short, the MuseNik/MuseScore constraints); read it first. This file adds what you need to change the code.

## Commands

    ./doit                                   # pytest, then Fields of Gold -> out/FieldsOfGold.musicxml
    uv run pytest -q                         # all tests
    uv run pytest -q tests/test_chordsheet.py::test_placement_rules
    uv run chordsheet SHEET.txt -o X.musicxml [--hold] [--pdf]

No linter is configured. Pure stdlib at runtime (`dependencies = []`); keep it that way unless there is a real need.

## Pipeline

Four stages, each a pure function, glued by `cli.main`:

1. `sheet.read_sheet(text) -> TextSheet` - lexing only: skip the preamble, find section headers, pair each chord line with the lyric line under it (`TextLine.chords` / `.lyric`, either may be `None`). Chord tokens are parsed here via `chords.parse_chord_line`, which keeps each chord's character column.
2. `sheet.build_song(TextSheet, bars_per_line, beats_per_bar, hold) -> Song` - all musical-time decisions. A `Song` is sections -> lines -> bars -> beats, where a beat is a `Chord` or `None` (hold). Copying chords from an earlier section of the same *kind* (`_kind`: "Verse 2" and "Solo to Verse" are both `verse`) happens here.
3. `musicxml.rehearsal_letters` + `musicxml.to_musicxml(Song, Key, ...) -> str` - serialization only. `divisions` is 1: one slash quarter note per beat, a `<harmony>` before each beat that has a chord.
4. `sheet.report(Song)` - the bar-by-bar text chart the CLI prints.

The placement rules are specified in `sheet.py`'s module docstring: that docstring is the single source of truth for how time is decided. Change it together with `_line_bars` / `build_song` and the README's short summary.

`Song.notes` collects every guess the tool made (copied lines, held lines, inferred key, missing rehearsal letters); the CLI prints them after the chart. When you add a new heuristic, append a note so the guess is visible, `***`-prefixed if it may be wrong. Errors are `SheetError` / `ChordError` with the sheet's line number in the message; `cli.main` turns them into `*** file: message` and exit 1.

## MusicXML constraints

`musicxml.py` is shaped by two readers, and each workaround is commented where it sits: MuseScore 4.x (title placement, no `<credit>`, no `<kind text=...>`, one direction per rehearsal mark) and MuseNik's iReal Pro converter (`$MO/MuseNik/src/core/IRealChart.cpp`: rehearsal letters A-D only, `<work-title>`). Keep those comments with the code they explain.

`test_musenik_ireal_reads_it` compiles MuseNik's `IRealChart.cpp` + `MiniXml.cpp` with `clang++` and checks the exact iReal progression string. It **skips** when `$MO` (here `/l/pc`) or `clang++` is missing, so confirm pytest's summary shows no skips after any change to `musicxml.py` or bar layout, and update its expected prefix when the layout change is intended.

## Test data

Tests use a made-up song (`SONG` in `tests/test_chordsheet.py`, "Paper Boats"). Real sheets (e.g. under `/l/mus/Lyrics/`) carry copyrighted lyrics: run them through `doit` / the CLI, and write new test cases as invented lyrics in the same style. `out/` is git-ignored.
