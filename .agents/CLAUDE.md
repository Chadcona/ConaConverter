# ConaConverter — Agent Context

## Project Overview

ConaConverter is a cross-platform desktop DJ playlist converter. It reads playlists from one DJ software format, converts through a universal intermediate model, and writes to another format. Preserves hot cues, memory cues, loops, beat grids, BPM, key, genre, and track metadata.

**Supported platforms:** Rekordbox, Serato, Engine OS (Denon DJ), VirtualDJ, Traktor (Native Instruments)

**Stack:** Python 3.10+ / PySide6 (Qt6, LGPL) / PyInstaller for distribution

## Architecture

### Universal data model pattern

Every reader converts its native format **into** the universal model (`models.py`). Every writer converts **from** it. This avoids N×N converter complexity.

```
Source format → Reader → Playlist/Track/CuePoint/BeatGridMarker → Writer → Target format
```

### Key design rules

- **Positions are always stored in seconds (float)** in the universal model. Convert at the reader/writer boundary only.
- **Colors are 0xRRGGBB integers.** Each format encodes colors differently; normalize at the boundary.
- **Sample rate is stored on Track** — required for sample-based position conversion (Serato BeatGrid, Engine OS beatGrid).
- **File paths are preserved as-is** — no path remapping. Source audio files are never copied or moved (except Serato, which embeds tags in audio files).

### Format-specific gotchas

| Format | Gotcha |
|---|---|
| VirtualDJ | `Scan/@Bpm` is **seconds-per-beat**, NOT BPM. `BPM = 60.0 / value`. Most common bug source. |
| Traktor | Paths use `/:` encoding: `/Users/john/Music/` → `/:Users/:john/:Music/:`. CUE_V2 positions are in **milliseconds**. TYPE=4 is beat grid, not a cue point. |
| Engine OS | BLOBs use 4-byte BE length prefix + zlib. quickCues = 8 fixed hot cue slots only (no memory cues, loops, or fades). Beat grid positions are in **samples**. |
| Rekordbox | Uses XML export only (`rekordbox.xml`), NOT `master.db` (encrypted with SQLCipher). POSITION_MARK `Num=-1` = memory cue. Positions in seconds. |
| Serato | Cue/grid data stored as GEOB ID3 tags **inside audio files**. Writing modifies audio files — always warn. Cue positions in ms, beat grid in samples. |

### Converter registry

`converters/__init__.py` has `READERS`, `WRITERS`, and `FORMAT_LABELS` dicts keyed by format string (`"rekordbox"`, `"serato"`, `"engineos"`, `"virtualdj"`, `"traktor"`).

Adding a new format: implement `BaseReader`/`BaseWriter`, register in `__init__.py`, add detection in `detector.py`, add label to `FORMAT_LABELS`.

## Project Structure

```
conaconverter/
  main.py              # Entry point (QApplication + MainWindow)
  models.py            # Universal model: Playlist, Track, CuePoint, BeatGridMarker, CueType
  detector.py          # Auto-detect format from file path/extension/XML root tag
  converters/
    base.py            # Abstract BaseReader / BaseWriter
    __init__.py        # READERS / WRITERS / FORMAT_LABELS registry
    rekordbox.py       # xml.etree.ElementTree
    serato.py          # serato-tools library
    engineos.py        # sqlite3 + zlib BLOB codec
    virtualdj.py       # xml.etree.ElementTree
    traktor.py         # xml.etree.ElementTree
  ui/
    mainwindow.py      # Main window, ConvertWorker (QRunnable), dark theme
    widgets.py         # DropZoneWidget (drag-and-drop + click-to-browse)
tests/
  fixtures/            # Synthetic test files (no real DJ software needed)
  test_rekordbox.py
  test_virtualdj.py
  test_engineos.py
  test_traktor.py
docs/
  DEVELOPMENT.md       # Architecture, testing, build instructions
  FORMAT_NOTES.md      # Deep-dive format documentation for all 5 platforms
```

## Testing

- 68 tests, all pass (`pytest tests/ -v`)
- Every reader tested with synthetic fixtures
- Every writer tested via round-trip (read → write → read → assert)
- Engine OS BLOB codecs unit-tested independently
- Traktor path codec unit-tested independently
- Position accuracy tolerance: 0.001s for XML, 1ms for Engine OS
- No real DJ software or audio files needed

## Dependencies

- `PySide6` — Qt6 UI (LGPL)
- `serato-tools` — Serato binary parsing
- `mutagen` — Audio file metadata (transitive dep)
- `pytest`, `pytest-qt` — Testing
- Core parsing uses stdlib only: `xml.etree`, `sqlite3`, `zlib`, `struct`

## UI

- Dark-themed PySide6 window with drag-and-drop zone
- Click zone shows context menu: "Browse for file" or "Browse for folder (Engine OS)"
- Format auto-detected on drop; target format selected via dropdown
- Conversion runs in QThreadPool (non-blocking)
- Warning dialog shown before Serato writes (modifies audio files)
- Output placed next to input with format suffix (e.g. `MyPlaylist_rekordbox.xml`)

## Things to watch out for

- Pylance reports false positives on PySide6 imports, `bytes` slicing, and `dict` unpacking — code runs fine at runtime.
- Engine OS: never modify while Engine DJ is running; never write to hardware device DBs directly.
- VirtualDJ BPM inversion is the #1 bug source — always test this conversion.
- Beat grid markers should be skipped when track BPM is unknown (not created with BPM=0).
- VirtualDJ fade direction requires the `Point` attribute (`fadeStart`/`fadeEnd`) — without it, fade-out becomes fade-in on round-trip.

## Future targets

- OneLibrary (emerging universal standard by Pioneer + Algoriddim + Native Instruments)
- Nested playlist/folder support
- Key notation conversion (Camelot <-> musical)
- Pre-built release binaries
