# ConaConverter

> Convert DJ playlists between Serato, Rekordbox, Engine OS, and VirtualDJ — cue points, beat grids, and metadata included.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-Qt6-41CD52?logo=qt&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-45%20passing-brightgreen)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

---

## What it does

ConaConverter is a lightweight, cross-platform desktop app that lets DJs move their library data between major DJ software platforms without losing their work — hot cues, memory cues, loops, beat grids, BPM, key, and genre all come along for the ride.

| From / To     | Rekordbox | Serato | Engine OS | VirtualDJ |
|---------------|:---------:|:------:|:---------:|:---------:|
| **Rekordbox**  | —         | ✅     | ✅         | ✅         |
| **Serato**     | ✅         | —      | ✅         | ✅         |
| **Engine OS**  | ✅         | ✅     | —          | ✅         |
| **VirtualDJ**  | ✅         | ✅     | ✅          | —         |

---

## Features

- **Drag-and-drop interface** — drop a playlist file onto the window and go
- **Preserves what matters** — hot cues, memory cues, loops, beat grids, BPM, key, genre, track metadata
- **Auto-detects format** — no need to tell the app what software the file came from
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
| **Serato**     | `.crate` file from `_Serato_/SubCrates/`             |
| **Engine OS**  | `Engine Library` folder (contains `m.db` + `p.db`)  |
| **VirtualDJ**  | `database.xml`                                       |

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
   - **Serato:** Drag the `.crate` file into Serato's crates panel

---

## What gets converted

| Data                  | Rekordbox | Serato | Engine OS | VirtualDJ |
|-----------------------|:---------:|:------:|:---------:|:---------:|
| Track title / artist  | ✅         | ✅     | ✅         | ✅         |
| Album / genre         | ✅         | ✅     | ✅         | ✅         |
| BPM                   | ✅         | ✅     | ✅         | ✅         |
| Key                   | ✅         | ✅     | ✅         | ✅         |
| Hot cues (slots 0–7)  | ✅         | ✅     | ✅         | ✅         |
| Memory cues           | ✅         | ✅     | —          | ✅         |
| Loops                 | ✅         | ✅     | ✅         | ✅         |
| Beat grid             | ✅         | ✅     | ✅         | ✅         |
| Cue colors            | ✅         | ✅     | ✅         | ✅         |
| Waveforms             | —          | —      | —          | —          |
| Artwork               | —          | —      | —          | —          |

---

## Important notes

### Rekordbox
ConaConverter reads and writes **Rekordbox XML** (the export format), not the `master.db` database file. Before converting:
- In Rekordbox, go to **File > Export Collection in XML Format**
- Import back via **File > Import > rekordbox xml**

### Serato
Writing to Serato embeds cue and beat grid data as tags **directly inside your audio files**. ConaConverter will show a warning dialog before doing this. **Back up your music files before converting to Serato format.**

### Engine OS
- Never convert while **Engine DJ is running** — it locks the database
- ConaConverter writes to the **desktop Engine Library** only, not hardware device databases
- After converting, use Engine DJ to sync to your hardware (CDJ/standalone players)

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
│   │   └── virtualdj.py
│   └── ui/
│       ├── mainwindow.py    # Main window
│       └── widgets.py       # DropZoneWidget
├── tests/
│   ├── fixtures/            # Synthetic test files
│   ├── test_rekordbox.py
│   ├── test_virtualdj.py
│   └── test_engineos.py
├── ConaConverter.spec       # PyInstaller build spec
├── requirements.txt
└── requirements-dev.txt
```

---

## Roadmap

- [ ] Nested playlist / folder support
- [ ] Batch conversion (multiple files at once)
- [ ] Key notation conversion (Camelot ↔ musical)
- [ ] Traktor NML support
- [ ] Pre-built release binaries (Windows / macOS / Linux)
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
