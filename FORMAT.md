# The chord sheet text format

Plain text, readable and printable as it stands, that `chordsheet` reads.
It keeps the chords-over-lyrics layout guitar-chord sites use and adds a
header of `Name: value` fields, so one format holds everything such sheets
carry: the key, credits, sources, performance notes, tabs, chord shapes,
and more than one version of a song in a file.

## A song

```
Title: Paper Boats
Artist: The Folders
Composer: A. Nonymous
Key: Am
Time: 4/4
Source: https://example.com/paper-boats-chords
Note: Capo off; the recording is a half step low.

[Intro]
Am  F  C  G

[Verse 1]
       Am                C
We fold the morning into paper boats
F        G        C
And send them down the gutter {softly}

[Chorus]
F           G          Am
Nothing that we make stays (stays)
F           G          C    C/E
All of it is borrowed

{Guitar solo over the verse}

[Verse 2: harmony]
We fold the evening into paper planes
And throw them at the shutters

[Chorus]
```

## The header

The first lines of a song, up to the first blank line: one `Name: value`
per line. Only `Title` is required. A name may repeat (`Source`, `Note`).

| Field | Holds |
|---|---|
| `Title` | the song's title |
| `Artist` | who performs this version |
| `Composer`, `Lyricist` | who wrote it (`Composer` alone when the source says "songwriters") |
| `Key` | `A`, `F#m`, `Bb`; a note may follow in parentheses: `Key: G (probably)`, `Key: Bm (recording; written in Am)` |
| `Time` | `4/4`, `3/4`, `6/8` |
| `Tempo` | beats a minute, or words |
| `Capo`, `Tuning`, `Instrument` | how it is played: `Capo: 2`, `Tuning: DADGAD`, `Instrument: 12-string guitar` |
| `Form` | the order of sections, as the source gives it: `V1, C1, V2, C2, Bridge, C3` |
| `Source` | where the text came from: a URL, a book, "email from R. Goldman, 1990" |
| `Recording` | a recording to learn it from: a URL, or album and track |
| `Copyright` | a copyright or publisher line the source carried |
| `Note` | anything else about the song as a whole |

## The body

- **Sections**: `[Name]` alone on a line: `[Intro]`, `[Verse 1]`,
  `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`, `[Solo]`, `[Interlude]`,
  `[Outro]`, or a suite's movement: `[II: One Note]`. Who sings it may
  follow a colon: `[Verse 1: Paul McCartney]`. A section with no lines
  under it means "that section again" (a bare "Chorus" in a source becomes
  `[Chorus]`); a new section with nothing to sing says so in a note:
  `[I: From Nowhere]` then `{instrumental}`.
- **Chords over lyrics**: a chord line directly above its lyric line, no
  blank line between; each chord starts over the syllable where it
  changes. A chord line with no lyric under it is instrumental, one bar per
  chord unless written with bar lines: `| A G | D |`.
- **Chords** as written in the source: `F#m7/E`, `Bb11`, `Dmaj7/C#`,
  `C#m7-5`. Minor is `m`, never `-`. `D or Bm7` offers a choice; `/E`
  alone means the chord before, over E. Chords joined by hyphens are a run
  played in quick succession, timing not given: `C-Am-Dm7-G` on a line of
  its own, `Fm-C` over one syllable.
- **Lyrics** exactly as the source has them. Parentheses in a lyric line
  are sung, usually by backing voices: `You won't see me (you won't see me)`.
- **Notes** in braces, never sung: on a line of their own for an event
  (`{Guitar solo: John Lennon}`, `{intro riff x 8}`, `{repeat chorus, fade}`)
  or after a lyric for how it is sung (`{w harmony}`). Words the source
  marked as unsure go in a note too: `{unclear: ...}`. A section of notes
  alone repeats its kind like an empty one (`[Solo to Verse]` then a `{Tab}`);
  with no earlier section of its kind (`[Instrumental]` then
  `{descending cascade, 2 measures}`) it is played but has no chords to chart.
- **Borrowed chords**: `{chords: Chorus}` under a section header says its
  lines with no chords take a Chorus's chords, when a sheet writes a verse's
  chords only over the chorus.
- **Tabs** under a `{Tab}` note, the lines exactly as written:
  `e|--3--2--0---|`.
- **Chord shapes**, when a source gives them, as a `[Chord shapes]` section
  of `Name = shape` lines (`C#m = 446654`, `Cs+5 = G#,C,F`).

## More than one song in a file

A line of three or more dashes alone (`---`) ends one song; the next starts
with its own header. For a second version of the same song (another key,
another arrangement) repeat the `Title` and say what differs in a `Note`.

## Plain text

UTF-8; no tabs, no trailing spaces; one blank line between sections, none
inside a chord/lyric pair; the file ends with one newline. Apostrophes are
`'`, not backticks.
