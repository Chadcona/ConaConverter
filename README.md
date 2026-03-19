# ConaConverter

> Convert DJ playlists between Serato, Rekordbox, Engine OS, VirtualDJ, and Traktor — cue points, beat grids, and metadata included.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-Qt6-41CD52?logo=qt&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-68%20passing-brightgreen)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## What it does

ConaConverter is a lightweight, cross-platform desktop app that lets DJs move their library data between major DJ software platforms without losing their work — hot cues, memory cues, loops, beat grids, BPM, key, and genre all come along for the ride.

| From / To     | Rekordbox | Serato | Engine OS | VirtualDJ | Traktor |
|---------------|:---------:|:------:|:---------:|:---------:|:-------:|
| **Rekordbox**  | —         | ✅     | ✅         | ✅         | ✅       |
| **Serato**     | ✅         | —      | ✅         | ✅         | ✅       |
| **Engine OS**  | ✅         | ✅     | —          | ✅         | ✅       |
| **VirtualDJ**  | ✅         | ✅     | ✅          | —         | ✅       |
| **Traktor**    | ✅         | ✅     | ✅          | ✅         | —       |

---

## Features

- **Drag-and-drop interface** — drop a playlist file onto the window and go. Drag crates directly from Serato DJ Pro!
- **Smart file browser** — auto-detects installed DJ software and offers shortcuts to Serato Crates, Rekordbox XML, and Traktor collections
- **Preserves what matters** — hot cues, memory cues, loops, beat grids, BPM, key, genre, track metadata
- **Auto-detects format** — no need to tell the app what software the file came from
- **Serato SQLite support** — reads directly from Serato's modern SQLite library (no `.crate` files needed)
- **Non-destructive by default** — only Serato write touches audio files (and shows a warning before it does)
- **Cross-platform** — runs on Windows, macOS, and Linux from the same codebase
- **Background conversion** — UI stays responsive during conversion

---

## Screenshots

> _UI screenshot coming soon_

---

## Supported File Types

| Software      | File(s) to drop                                      |
|---------------|------------------------------------------------------|
| **Rekordbox**  | `rekordbox.xml` (exported via File > Export Collection in XML) |
| **Serato**     | Drag crate from Serato, or `.crate` file, or `location.sqlite` |
| **Engine OS**  | `Engine Library` folder (contains `m.db` + `p.db`)  |
| **VirtualDJ**  | `database.xml`                                       |
| **Traktor**    | `collection.nml` from the Traktor data folder        |

---

## Installation

### Prerequisites

- Python 3.10 or newer
- pip

### From source

```bash
git clone https://github.com/Chadcona/ConaConverter.git
cd ConaConverter
pip install -r requirements.txt
python -m conaconverter.main
```

### From a release (coming soon)

Pre-built binaries for Windows (`.exe`), macOS (`.app`), and Linux will be available on the [Releases](https://github.com/Chadcona/ConaConverter/releases) page — no Python installation required.

---

## Usage

1. **Launch the app**
   ```bash
   python -m conaconverter.main
   ```

2. **Drop your playlist file** onto the drop zone, or click it to browse. The app will auto-detect the format.

3. **Select your target software** from the dropdown menu.

4. **Click Convert.** The output file is placed in the same folder as the input, with the target format appended to the filename (e.g. `MyPlaylist_rekordbox.xml`).

5. **Import the output** into your target software:
   - **Rekordbox:** File > Import > rekordbox xml
   - **Engine OS:** File > Import > Import from rekordbox.xml (or open folder)
   - **VirtualDJ:** Browser > Files > load database.xml
   - **Traktor:** File > Import Collection
   - **Serato:** Drag the `.crate` file into Serato's crates panel

---

## What gets converted

| Data                  | Rekordbox | Serato | Engine OS | VirtualDJ | Traktor |
|-----------------------|:---------:|:------:|:---------:|:---------:|:-------:|
| Track title / artist  | ✅         | ✅     | ✅         | ✅         | ✅       |
| Album / genre         | ✅         | ✅     | ✅         | ✅         | ✅       |
| BPM                   | ✅         | ✅     | ✅         | ✅         | ✅       |
| Key                   | ✅         | ✅     | ✅         | ✅         | ✅       |
| Hot cues (slots 0–7)  | ✅         | ✅     | ✅         | ✅         | ✅       |
| Memory cues           | ✅         | ✅     | —          | ✅         | ✅       |
| Loops                 | ✅         | ✅     | ✅         | ✅         | ✅       |
| Beat grid             | ✅         | ✅     | ✅         | ✅         | ✅       |
| Cue colors            | ✅         | ✅     | ✅         | ✅         | —        |
| Waveforms             | —          | —      | —          | —          | —        |
| Artwork               | —          | —      | —          | —          | —        |

---

## Important notes

### Rekordbox
ConaConverter reads and writes **Rekordbox XML** (the export format), not the `master.db` database file. Before converting:
- In Rekordbox, go to **File > Export Collection in XML Format**
- Import back via **File > Import > rekordbox xml**

### Traktor
ConaConverter reads and writes **Traktor NML** (`collection.nml`). Export from Traktor via _File > Export Collection_ and import back with _File > Import Collection_. Cue colors are not stored in the NML format and will not be carried across.

### Serato
Writing to Serato embeds cue and beat grid data as tags **directly inside your audio files**. ConaConverter will show a warning dialog before doing this. **Back up your music files before converting to Serato format.**

### Engine OS
- **Recommended workflow:** Convert your playlist to **Rekordbox XML** format first. Engine DJ has built-in Rekordbox XML import — open Engine DJ, find the Rekordbox panel in the left sidebar, and drag your playlists into your collection. This is the most reliable path and preserves all metadata.
- Never convert while **Engine DJ is running** — it locks the database
- After importing, use Engine DJ to sync to your hardware (CDJ/standalone players)

### File paths
Track file paths are stored as-is from the source library. If your music is on a different drive or the path structure differs between machines, you may need to relocate tracks inside the target software after importing.

---

## Development

See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for architecture details, how to run tests, and how to build a distributable binary.

See [FORMAT_NOTES.md](docs/FORMAT_NOTES.md) for deep-dive documentation on each platform's file format.

### Quick start for contributors

```bash
git clone https://github.com/Chadcona/ConaConverter.git
cd ConaConverter
pip install -r requirements-dev.txt
pytest
```

---

## Project structure

```
ConaConverter/
├── conaconverter/
│   ├── main.py              # App entry point
│   ├── models.py            # Universal data model
│   ├── detector.py          # Format auto-detection
│   ├── converters/          # One module per DJ platform
│   │   ├── rekordbox.py
│   │   ├── serato.py
│   │   ├── engineos.py
│   │   ├── virtualdj.py
│   │   └── traktor.py
│   └── ui/
│       ├── mainwindow.py    # Main window
│       └── widgets.py       # DropZoneWidget
├── tests/
│   ├── fixtures/            # Synthetic test files
│   ├── test_rekordbox.py
│   ├── test_virtualdj.py
│   ├── test_engineos.py
│   └── test_traktor.py
├── ConaConverter.spec       # PyInstaller build spec
├── requirements.txt
└── requirements-dev.txt
```

---

## Roadmap

- [x] Traktor NML support
- [x] Serato drag-and-drop from Serato DJ Pro
- [x] Serato SQLite library reading (modern Serato without .crate files)
- [ ] Direct Engine OS database integration (write playlists directly to Engine Library)
- [ ] Nested playlist / folder support
- [ ] Batch conversion (multiple files at once)
- [ ] Key notation conversion (Camelot ↔ musical)
- [ ] Pre-built release binaries (Windows / macOS / Linux)
- [ ] OneLibrary support (emerging universal standard — Pioneer + Algoriddim + Native Instruments)
- [ ] Waveform data preservation (where technically possible)

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

Format documentation sourced from:
- [Pioneer DJ Rekordbox XML spec](https://cdn.rekordbox.com/files/20200410160904/xml_format_list.pdf)
- [Mixxx Engine Library Format wiki](https://github.com/mixxxdj/mixxx/wiki/Engine-Library-Format)
- [Mixxx Serato Database Format wiki](https://github.com/mixxxdj/mixxx/wiki/Serato-Database-Format)
- [Mixxx VirtualDJ Cue Storage Format wiki](https://github.com/mixxxdj/mixxx/wiki/Virtual-Dj-Cue-Storage-Format)
- [Mixxx Traktor Library Format wiki](https://github.com/mixxxdj/mixxx/wiki/Traktor-Library-Format)
