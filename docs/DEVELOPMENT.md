# Development Guide

## Prerequisites

- Python 3.10+
- pip
- Git

## Setup

```bash
git clone https://github.com/Chadcona/ConaConverter.git
cd ConaConverter
pip install -r requirements-dev.txt
```

## Running the app

```bash
python -m conaconverter.main
```

## Running tests

```bash
pytest                        # all tests
pytest tests/test_rekordbox.py -v   # single file, verbose
pytest -k "round_trip"        # filter by test name
```

All 45 tests run without needing any real DJ software or audio files installed. Synthetic fixtures and in-memory SQLite databases are used throughout.

---

## Architecture

### Universal data model

Everything flows through a single intermediate representation defined in `conaconverter/models.py`. Every reader converts its native format **into** this model; every writer converts **from** it.

```
Native format
    ↓  Reader
Universal Playlist / Track / CuePoint / BeatGridMarker
    ↓  Writer
Target format
```

**Key design decisions:**

| Decision | Reason |
|---|---|
| Positions stored in **seconds** (float) | Each format uses a different native unit (samples, ms, seconds). Seconds is the only lossless common ground when the sample rate is available. |
| Colors stored as **0xRRGGBB int** | Normalises the varied color encoding schemes across platforms. |
| Sample rate stored on Track | Required to convert sample-based positions (Serato, Engine OS) to/from seconds. |
| No nested playlists in MVP | Keeps the model simple; can be added later. |

### Converter registry

`conaconverter/converters/__init__.py` exposes two dicts:

```python
READERS = {"rekordbox": RekordboxReader(), "serato": ..., ...}
WRITERS = {"rekordbox": RekordboxWriter(), "serato": ..., ...}
```

Adding a new format means implementing `BaseReader` and `BaseWriter` and registering the instances here.

### Format detection

`conaconverter/detector.py` inspects the file extension and, for XML files, the root element tag to return a format key string. Detection order:

1. `.crate` or filename `database V2` → `serato`
2. Folder containing `m.db` → `engineos`
3. `.db` extension → `engineos`
4. XML root `DJ_PLAYLISTS` → `rekordbox`
5. XML root `VirtualDJ_Database` → `virtualdj`

### UI threading model

Conversion runs in a `QRunnable` on `QThreadPool` so the UI never freezes. Signals carry the result back to the main thread:

```
MainWindow (main thread)
    → creates ConvertWorker (QRunnable)
    → QThreadPool.globalInstance().start(worker)
        worker.run() [thread pool thread]
            → signals.finished.emit(output_path)
            → signals.error.emit(message)
    ← slot: _on_conversion_finished / _on_conversion_error (main thread)
```

---

## Adding a new format

1. Create `conaconverter/converters/myformat.py` implementing `BaseReader` and `BaseWriter`.
2. Register in `conaconverter/converters/__init__.py`.
3. Add detection logic in `conaconverter/detector.py`.
4. Add a label to `FORMAT_LABELS` in `converters/__init__.py`.
5. Write tests with a fixture file in `tests/fixtures/`.

---

## Building a distributable binary

### Prerequisites

```bash
pip install pyinstaller
```

### Build

```bash
pyinstaller ConaConverter.spec
```

Output lands in `dist/ConaConverter/`. Distribute the entire folder as a zip.

### macOS .app bundle

Uncomment the `BUNDLE` block at the bottom of `ConaConverter.spec`, then:

```bash
pyinstaller ConaConverter.spec
```

For distribution outside the App Store, code-sign with:

```bash
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (TEAMID)" \
  dist/ConaConverter.app
```

### Linux AppImage

After running PyInstaller, wrap the output folder with [appimagetool](https://github.com/AppImage/AppImageKit):

```bash
pyinstaller ConaConverter.spec
# Then follow appimagetool instructions to wrap dist/ConaConverter/
```

---

## Code style

- Standard Python (PEP 8)
- Type hints on all public functions
- Dataclasses for all model types
- No external dependencies for core parsing (stdlib `xml.etree`, `sqlite3`, `zlib`, `struct`)

---

## Testing philosophy

- Every reader is tested with a **synthetic fixture file** — no real DJ software needed
- Every writer is tested via a **round-trip** (`read → write → read → assert equal`)
- Binary BLOB codecs (Engine OS) are **unit-tested independently** before integration
- Position accuracy tolerance: **0.001 seconds** for XML formats, **1ms** for Engine OS

---

## Environment

| Dependency | Purpose |
|---|---|
| `PySide6` | Qt6 UI framework (LGPL) |
| `serato-tools` | Serato binary `.crate` and GEOB tag parser |
| `mutagen` | Audio file metadata (transitive dep of serato-tools) |
| `pyrekordbox` | Available for future use; current Rekordbox converter uses stdlib `xml.etree` |
| `pytest` | Test runner |
| `pytest-qt` | PySide6 widget testing helpers |
