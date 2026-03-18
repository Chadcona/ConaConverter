# Changelog

All notable changes to ConaConverter will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Pre-built release binaries (Windows / macOS / Linux)
- Nested playlist / folder support
- Batch conversion (multiple files at once)
- Traktor NML support
- Key notation conversion (Camelot ↔ musical)

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
