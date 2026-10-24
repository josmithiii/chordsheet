"""chordsheet SHEET.txt -o SONG.musicxml [--pdf]: a chords-over-lyrics text
sheet to a MusicXML lead sheet (slash notation and chord symbols), which
MuseNik opens with Edit Score and `musenik ireal` turns into an iReal Pro chart."""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .chords import ChordError, Key, parse_key
from .musicxml import rehearsal_letters, to_musicxml
from .sheet import SheetError, build_song, read_sheet, report

MSCORE_DEFAULT = "/Applications/MuseScore 4.app/Contents/MacOS/mscore"
TIMES = ["4/4", "3/4", "2/4"]


def find_mscore(given: str | None) -> str:
    for candidate in ([given] if given else [MSCORE_DEFAULT, shutil.which("mscore") or "", shutil.which("mscore4") or ""]):
        if candidate and Path(candidate).is_file():
            return candidate
    raise SystemExit(f"*** MuseScore not found{' at ' + given if given else ''} (pass --mscore <path>)")


def mscore_version(mscore: str) -> tuple[int, int, int]:
    """'MuseScore4 4.0.0' -> (4, 0, 0)."""
    out = subprocess.run([mscore, "--version"], capture_output=True, text=True).stdout
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    if not m:
        raise SystemExit(f"*** cannot read MuseScore's version from {mscore} --version: {out.strip()!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def check_mscore(mscore: str) -> None:
    # Seen with MuseScore 4.0.0 (2026-10-23): its PDFs draw chord symbols with
    # no root ("m" for F#m; the imported score has the roots), and `-o x.mscx`
    # empties the folder it writes into. MuseNik is tested on 4.7.5.
    v = mscore_version(mscore)
    if v < (4, 1, 0):
        raise SystemExit(f"*** MuseScore {'.'.join(map(str, v))} at {mscore} draws chord symbols without their "
                         f"roots; install a current MuseScore 4 (MuseNik is tested on 4.7.5)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="chordsheet", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheet", type=Path, help="the text sheet: chord lines over lyric lines, [Section] headers")
    ap.add_argument("-o", "--output", type=Path, help="the .musicxml to write (default: <sheet name>.musicxml here)")
    ap.add_argument("--pdf", action="store_true", help="also have MuseScore write a .pdf beside it")
    ap.add_argument("--mscore", help=f"MuseScore's program (default: {MSCORE_DEFAULT})")
    ap.add_argument("--bars-per-line", type=int, default=2, help="bars per lyric line (default 2)")
    ap.add_argument("--bars-per-system", type=int, default=4, help="bars per line of the printed score (default 4)")
    ap.add_argument("--song", type=int, help="which song of a file of several (--- between them), from 1")
    ap.add_argument("--time", choices=TIMES, help="time signature (default: the sheet's Time:, else 4/4)")
    ap.add_argument("--key", help='e.g. "A major", "F# minor" (default: the sheet\'s Key:, else the last chord)')
    ap.add_argument("--title", help="default: the sheet's Title:, or its first line before any ' - '")
    ap.add_argument("--subtitle", help="default: the sheet's Artist:, or the rest of its first line")
    ap.add_argument("--composer", help="default: the sheet's Composer:")
    ap.add_argument("--no-lyrics", action="store_true", help="leave the lyric lines out of the score")
    ap.add_argument("--hold", action="store_true",
                    help="hold the chord before through a lyric line with no chords and nothing to copy them from "
                         "(default: stop with an error)")
    a = ap.parse_args(argv)

    if not a.sheet.is_file():
        print(f"*** no such file: {a.sheet}", file=sys.stderr)
        return 1
    try:
        sheet = read_sheet(a.sheet.read_text(encoding="utf-8"), a.song)
        if a.title is not None:
            sheet.title = a.title
        if a.subtitle is not None:
            sheet.subtitle = a.subtitle
        time = a.time or sheet.value("Time") or "4/4"
        if time not in TIMES:
            raise SheetError(f"Time: {time}; chordsheet writes {', '.join(TIMES)} (--time sets it)")
        a.time = time
        song = build_song(sheet, a.bars_per_line, int(time.split("/")[0]), a.hold)
        if sheet.preamble:
            song.notes.append(f"skipped {sheet.preamble} line(s) before the first chords or [Section]")
        composer = a.composer if a.composer is not None else sheet.value("Composer")
        if a.key:
            key = parse_key(a.key)
        elif sheet.value("Key"):
            # "Key: G (probably)", "Key: Db (C#)": the key is what comes before any note.
            key = parse_key(sheet.value("Key").split("(")[0])
            song.notes.append(f"key {key}, from the sheet's Key: {sheet.value('Key')}")
        else:
            last = song.last_chord()
            key = Key(last.root, last.minor)
            key.fifths  # noqa: B018 - refuses a key with no signature
            song.notes.append(f"key {key}, from the last chord ({last.text()}); --key sets it")
        _, letter_notes = rehearsal_letters(song)
        song.notes.extend(letter_notes)
        xml = to_musicxml(song, key, composer, not a.no_lyrics, a.bars_per_system)
    except (SheetError, ChordError) as e:
        print(f"*** {a.sheet}: {e}", file=sys.stderr)
        return 1

    out = a.output or Path(a.sheet.stem + ".musicxml")
    out.write_text(xml, encoding="utf-8")
    print(f"{sheet.title or a.sheet.stem}: {len(song.bars())} bars in {a.time}, {key}")
    print(report(song))
    for n in song.notes:
        print(n)
    print(f"Wrote {out}")

    if a.pdf:
        mscore = find_mscore(a.mscore)
        check_mscore(mscore)
        pdf = out.with_suffix(".pdf")
        r = subprocess.run([mscore, "-o", str(pdf), str(out)], capture_output=True, text=True)
        if r.returncode != 0 or not pdf.is_file():
            print(f"*** MuseScore could not write {pdf} (exit {r.returncode}):\n{r.stderr.strip()}", file=sys.stderr)
            return 1
        print(f"Wrote {pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
