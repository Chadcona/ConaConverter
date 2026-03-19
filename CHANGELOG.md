# Changelog

All notable changes to ConaConverter will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Direct Engine OS database integration (write playlists directly into existing Engine Library)
- Pre-built release binaries (Windows / macOS / Linux)
- Nested playlist / folder support
- Batch conversion (multiple files at once)
- Key notation conversion (Camelot ↔ musical)
- OneLibrary support (emerging universal standard — Pioneer + Algoriddim + Native Instruments)

---

## [0.3.0] - 2026-03-18

### Added
- Serato drag-and-drop — drag a crate from Serato DJ Pro's sidebar into ConaConverter
  - Intercepts Serato's proprietary `text/vnd.serato.library.crate_uri` MIME type
  - Shows a crate picker dialog listing all available crates from Serato's SQLite database
- Serato SQLite library support — reads track metadata directly from `location.sqlite`
- Smart browse menu — auto-detects installed DJ software and shows quick-open shortcuts
- Drop zone accepts text drops and resolves them as file paths or Serato crate names
- Traktor `.nml` extension in output path builder

### Changed
- Serato reader supports three input modes: `.crate` files, `location.sqlite`, and `serato-sqlite://` URIs
- Format detector recognizes `assetlist://` and `serato-sqlite://` URIs as Serato format

---

## [0.2.1] - 2026-03-17

### Fixed
- VirtualDJ fade-out markers were silently converted to fade-in on round-trip — now uses the `Point` attribute (`fadeStart` / `fadeEnd`) to distinguish direction
- Beat grid markers created with BPM=0 when track BPM was unknown (VirtualDJ and Traktor readers) — now skips grid markers when BPM is not available
- Engine OS file path construction was broken for tracks with both `path` and `filename` columns
- Rekordbox XML writer produced double-indented output (called both `_indent()` and `ET.indent()`)
- Engine OS writer silently dropped memory cues, loops, and fade markers without any indication — now logs a warning listing the dropped cue types
- UI file browser was missing `.nml` filter for Traktor files
- UI had no way to browse for Engine OS library folders (only files) — click now offers a context menu with both file and folder browsing
- Format detector docstring was missing `'traktor'` as a possible return value

---

## [0.2.0] - 2026-03-17

### Added
- Traktor NML reader and writer (`collection.nml`)
  - Hot cues, memory cues, loops, beat grid, full track metadata
  - Path encoding/decoding for Traktor's `/:dir/:` format (Windows and macOS)
  - Beat grid markers (CUE_V2 TYPE=4) read/written correctly and kept separate from cue points
  - Round-trip tested; path codec unit-tested independently
- Traktor added to format auto-detector (`.nml` extension, root tag `<NML>`)
- Updated README conversion matrix and supported file types table

---

## [0.1.0] - 2026-03-17

### Added
- Initial release
- Rekordbox XML reader and writer (hot cues, memory cues, loops, beat grid, full metadata)
- VirtualDJ `database.xml` reader and writer (handles seconds-per-beat BPM inversion)
- Engine OS `m.db` / `p.db` reader and writer (zlib BLOB codec for quickCues and beatGrid)
- Serato `.crate` reader and writer (GEOB audio tag embedding via serato-tools)
- Universal data model: `Playlist`, `Track`, `CuePoint`, `BeatGridMarker`
- Format auto-detection from file extension and XML root tag
- PySide6 drag-and-drop UI with dark theme
- Background conversion worker (non-blocking UI)
- Safety warning dialog before Serato write (modifies audio files)
- PyInstaller spec for cross-platform distribution
- 45 unit and integration tests
