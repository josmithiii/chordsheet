"""chordsheet SHEET.txt -o SONG.musicxml [--pdf]: a chords-over-lyrics text
sheet to a MusicXML lead sheet (slash notation and chord symbols), which
MuseNik opens with Edit Score and `musenik ireal` turns into an iReal Pro chart.

chordsheet SHEET.txt --outdir DIR [--pdf-dir DIR]: every song of the sheet,
as DIR/<name>.musicxml (and <name>-2, -3 ... for the other songs of a file of
several). chordsheet --list-chorded SHEET...: which of the sheets are in
FORMAT.md's form and have chords to chart (what a Makefile builds)."""
from __future__ import annotations

import argparse
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from .chords import ChordError, Key, parse_key
from .musicxml import rehearsal_letters, to_musicxml
from .sheet import NoChords, SheetError, Song, build_song, read_sheet, report, song_count

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


def convert(text: str, song_no: int | None, a: argparse.Namespace) -> tuple[str, Song, Key, str]:
    """One song of a sheet: its MusicXML, the Song, its key and its time."""
    sheet = read_sheet(text, song_no)
    if a.title is not None:
        sheet.title = a.title
    if a.subtitle is not None:
        sheet.subtitle = a.subtitle
    time = a.time or sheet.value("Time") or "4/4"
    if time not in TIMES:
        raise SheetError(f"Time: {time}; chordsheet writes {', '.join(TIMES)} (--time sets it)")
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
    return to_musicxml(song, key, composer, not a.no_lyrics, a.bars_per_system), song, key, time


def write_pdf(mscore: str, xml: Path, pdf: Path) -> bool:
    """MuseScore's PDF of `xml`. MuseNik's rule (runMuseScoreProcess in
    MuseNik's src/pipeline/RunProcess.h): on macOS 26, MuseScore 4.7.5 aborts
    on its way out on most runs, "mutex lock failed: Invalid argument"
    (MuseScore issue #34445), after writing a good file. That abort, with the
    PDF written by this run and not empty, is a run that worked. Any other
    failure is tried once more, then reported."""
    for attempt in (1, 2):
        start = time.time()
        r = subprocess.run([mscore, "-o", str(pdf), str(xml)], capture_output=True, text=True)
        written = pdf.is_file() and pdf.stat().st_size > 0 and pdf.stat().st_mtime >= start - 1
        if r.returncode == 0 and written:
            return True
        if r.returncode == -signal.SIGABRT and written and "mutex lock failed" in r.stdout + r.stderr:
            return True
        if attempt == 2:
            tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-5:])
            print(f"*** MuseScore could not write {pdf} (exit {r.returncode}, twice):\n{tail}", file=sys.stderr)
    return False


def chorded(path: Path) -> bool:
    """In FORMAT.md's form, with at least one song that has chords. A song
    that fails for any other reason counts as chorded, so a build reports it."""
    text = path.read_text(encoding="utf-8")
    if not next((l for l in text.splitlines() if l.strip()), "").startswith("Title:"):
        return False
    for k in range(1, song_count(text) + 1):
        try:
            read_sheet(text, k)
            return True
        except NoChords:
            continue
        except (SheetError, ChordError):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="chordsheet", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheet", type=Path, nargs="*", help="the text sheet: chord lines over lyric lines, [Section] headers "
                    "(several only with --list-chorded)")
    ap.add_argument("-o", "--output", type=Path, help="the .musicxml to write (default: <sheet name>.musicxml here)")
    ap.add_argument("--outdir", type=Path, help="write every song of the sheet into this folder: <name>.musicxml, <name>-2.musicxml ...")
    ap.add_argument("--pdf-dir", type=Path, help="with --outdir: MuseScore writes each song's .pdf into this folder")
    ap.add_argument("--list-chorded", action="store_true", help="print the sheets that are in FORMAT.md's form and have chords")
    ap.add_argument("-q", "--quiet", action="store_true", help="one line per song and the *** guesses, not the chart")
    ap.add_argument("--check-mscore", action="store_true", help="only check that MuseScore can make the PDFs (4.1 or later)")
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

    if a.check_mscore:
        mscore = find_mscore(a.mscore)
        check_mscore(mscore)
        print(f"MuseScore {'.'.join(map(str, mscore_version(mscore)))} at {mscore}")
        return 0
    if not a.sheet:
        ap.error("a sheet to read")
    for path in a.sheet:
        if not path.is_file():
            print(f"*** no such file: {path}", file=sys.stderr)
            return 1
    if a.list_chorded:
        for path in a.sheet:
            if chorded(path):
                print(path)
        return 0
    if len(a.sheet) > 1:
        ap.error("one sheet at a time (several only with --list-chorded)")
    if a.pdf_dir and not a.outdir:
        ap.error("--pdf-dir goes with --outdir")
    if a.outdir and (a.output or a.pdf):
        ap.error("--outdir names its own files: not with -o or --pdf")
    path = a.sheet[0]
    text = path.read_text(encoding="utf-8")

    if a.outdir:
        # Every song (or the one --song names): <name>.musicxml for the first, <name>-<k> for the others.
        mscore = None
        if a.pdf_dir:
            mscore = find_mscore(a.mscore)
            check_mscore(mscore)
            a.pdf_dir.mkdir(parents=True, exist_ok=True)
        a.outdir.mkdir(parents=True, exist_ok=True)
        songs = [a.song] if a.song else list(range(1, song_count(text) + 1))
        failed = 0
        for k in songs:
            stem = path.stem if k == 1 else f"{path.stem}-{k}"
            try:
                xml, song, key, time = convert(text, k, a)
            except NoChords:
                print(f"{path} song {k}: lyrics only, no chords to chart")
                continue
            except (SheetError, ChordError) as e:
                print(f"*** {path} song {k}: {e}", file=sys.stderr)
                failed += 1
                continue
            out = a.outdir / f"{stem}.musicxml"
            out.write_text(xml, encoding="utf-8")
            print(f"{out}: {song.title}, {len(song.bars())} bars in {time}, {key}")
            for n in song.notes:
                if not a.quiet or n.startswith("***"):
                    print(f"  {n}")
            if mscore and not write_pdf(mscore, out, a.pdf_dir / f"{stem}.pdf"):
                failed += 1
        return 1 if failed else 0

    try:
        xml, song, key, time = convert(text, a.song, a)
    except (SheetError, ChordError) as e:
        print(f"*** {path}: {e}", file=sys.stderr)
        return 1
    out = a.output or Path(path.stem + ".musicxml")
    out.write_text(xml, encoding="utf-8")
    print(f"{song.title or path.stem}: {len(song.bars())} bars in {time}, {key}")
    if not a.quiet:
        print(report(song))
    for n in song.notes:
        if not a.quiet or n.startswith("***"):
            print(n)
    print(f"Wrote {out}")

    if a.pdf:
        mscore = find_mscore(a.mscore)
        check_mscore(mscore)
        pdf = out.with_suffix(".pdf")
        if not write_pdf(mscore, out, pdf):
            return 1
        print(f"Wrote {pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
