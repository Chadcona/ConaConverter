"""Engine OS (Denon DJ) m.db / p.db ↔ universal Playlist converter.

Engine OS uses two SQLite databases:
  m.db — metadata: Track, Playlist, PlaylistTrack tables
  p.db — performance: PerformanceData table with BLOB columns

BLOB encoding: 4-byte big-endian uncompressed-length prefix + zlib payload

quickCues BLOB layout (per Mixxx Engine Library Format wiki):
  8 repeated slots, each slot:
    label_length  (u8)      — length of label string in bytes
    label         (utf-8)   — label bytes
    position      (i32 BE)  — position in milliseconds; -1 = empty slot
    color         (u32 BE)  — 0xRRGGBB color; 0 = no color

beatGrid BLOB layout:
  num_markers  (u32 BE)
  per marker:
    sample_number (u64 BE)  — sample offset of this beat
    bpm_x100      (u32 BE)  — BPM * 100 (e.g. 12800 = 128.00 BPM)

IMPORTANT:
  - Never modify Engine OS databases while Engine DJ is open.
  - Never write to hardware device databases directly.
  - Always check the Information table schema version before writing.
"""

from __future__ import annotations

import os
import sqlite3
import struct
import zlib
from typing import List, Optional, Tuple

from conaconverter.converters.base import BaseReader, BaseWriter
from conaconverter.models import (
    BeatGridMarker,
    CuePoint,
    CueType,
    Playlist,
    Track,
    ms_to_seconds,
    samples_to_seconds,
    seconds_to_ms,
    seconds_to_samples,
)

# Minimum supported schema version
_MIN_SCHEMA_VERSION = "1.0.0"
# Default sample rate used for beat grid if not stored in track metadata
_DEFAULT_SAMPLE_RATE = 44100

_NUM_CUE_SLOTS = 8


def _decode_blob(data: bytes) -> bytes:
    """Decode a zlib-compressed BLOB with 4-byte big-endian length prefix."""
    if len(data) < 4:
        return b""
    uncompressed_len = struct.unpack(">I", data[:4])[0]
    try:
        result = zlib.decompress(data[4:])
    except zlib.error:
        return b""
    return result


def _encode_blob(data: bytes) -> bytes:
    """Encode bytes as a zlib-compressed BLOB with 4-byte big-endian length prefix."""
    compressed = zlib.compress(data)
    return struct.pack(">I", len(data)) + compressed


def _parse_quick_cues(blob: bytes) -> List[CuePoint]:
    """Parse the quickCues BLOB into a list of CuePoints."""
    cues: List[CuePoint] = []
    data = _decode_blob(blob)
    offset = 0

    for slot in range(_NUM_CUE_SLOTS):
        if offset >= len(data):
            break

        label_len = struct.unpack_from("B", data, offset)[0]
        offset += 1

        label = data[offset:offset + label_len].decode("utf-8", errors="replace")
        offset += label_len

        if offset + 8 > len(data):
            break

        position_ms = struct.unpack_from(">i", data, offset)[0]
        offset += 4
        color_raw = struct.unpack_from(">I", data, offset)[0]
        offset += 4

        if position_ms == -1:
            continue  # empty slot

        color_rgb: Optional[int] = None
        if color_raw != 0:
            color_rgb = color_raw & 0xFFFFFF

        cues.append(CuePoint(
            position_seconds=ms_to_seconds(float(position_ms)),
            cue_type=CueType.HOT_CUE,
            num=slot,
            name=label,
            color_rgb=color_rgb,
        ))

    return cues


def _encode_quick_cues(cue_points: List[CuePoint]) -> bytes:
    """Encode a list of CuePoints into the quickCues BLOB format."""
    # Build a slot map from cue num → CuePoint
    slot_map = {c.num: c for c in cue_points if c.cue_type == CueType.HOT_CUE and 0 <= c.num < _NUM_CUE_SLOTS}

    data = b""
    for slot in range(_NUM_CUE_SLOTS):
        cue = slot_map.get(slot)
        if cue is None:
            # Empty slot: label_len=0, label="", position=-1, color=0
            data += struct.pack("B", 0)
            data += struct.pack(">i", -1)
            data += struct.pack(">I", 0)
        else:
            label = cue.name.encode("utf-8")
            data += struct.pack("B", len(label))
            data += label
            pos_ms = int(seconds_to_ms(cue.position_seconds))
            color = (cue.color_rgb & 0xFFFFFF) if cue.color_rgb else 0
            data += struct.pack(">i", pos_ms)
            data += struct.pack(">I", color)

    return _encode_blob(data)


def _parse_beat_grid(blob: bytes, sample_rate: int) -> List[BeatGridMarker]:
    """Parse the beatGrid BLOB into a list of BeatGridMarkers."""
    markers: List[BeatGridMarker] = []
    data = _decode_blob(blob)

    if len(data) < 4:
        return markers

    num_markers = struct.unpack_from(">I", data, 0)[0]
    offset = 4

    for _ in range(num_markers):
        if offset + 12 > len(data):
            break
        sample_number = struct.unpack_from(">Q", data, offset)[0]
        offset += 8
        bpm_x100 = struct.unpack_from(">I", data, offset)[0]
        offset += 4

        pos_seconds = samples_to_seconds(sample_number, sample_rate)
        bpm = bpm_x100 / 100.0
        markers.append(BeatGridMarker(position_seconds=pos_seconds, bpm=bpm))

    return markers


def _encode_beat_grid(beat_grid: List[BeatGridMarker], sample_rate: int) -> bytes:
    """Encode a list of BeatGridMarkers into the beatGrid BLOB format."""
    data = struct.pack(">I", len(beat_grid))
    for marker in beat_grid:
        sample_number = seconds_to_samples(marker.position_seconds, sample_rate)
        bpm_x100 = int(round(marker.bpm * 100))
        data += struct.pack(">Q", sample_number)
        data += struct.pack(">I", bpm_x100)
    return _encode_blob(data)


def _find_db_files(path: str) -> Tuple[str, str]:
    """Given a folder or .db path, return (m_db_path, p_db_path)."""
    if os.path.isdir(path):
        m_db = os.path.join(path, "m.db")
        p_db = os.path.join(path, "p.db")
    else:
        # Assume the .db file is m.db; look for p.db alongside it
        folder = os.path.dirname(path)
        m_db = path
        p_db = os.path.join(folder, "p.db")

    if not os.path.exists(m_db):
        raise FileNotFoundError(f"Engine OS m.db not found: {m_db}")
    if not os.path.exists(p_db):
        raise FileNotFoundError(f"Engine OS p.db not found: {p_db}")

    return m_db, p_db


def _check_schema_version(conn: sqlite3.Connection) -> None:
    """Read the Information table and warn if schema version is unexpected."""
    try:
        cur = conn.execute("SELECT schemaVersion FROM Information LIMIT 1")
        row = cur.fetchone()
        if row:
            version = row[0]
            # Basic check: version should be a dotted numeric string
            parts = str(version).split(".")
            if not all(p.isdigit() for p in parts):
                raise ValueError(f"Unexpected Engine OS schema version: {version}")
    except sqlite3.OperationalError:
        pass  # Information table may not exist in older versions


class EngineOsReader(BaseReader):
    def read(self, path: str) -> Playlist:
        m_db, p_db = _find_db_files(path)

        m_conn = sqlite3.connect(m_db)
        p_conn = sqlite3.connect(p_db)

        try:
            _check_schema_version(m_conn)
            return self._read_library(m_conn, p_conn, path)
        finally:
            m_conn.close()
            p_conn.close()

    def _read_library(self, m_conn: sqlite3.Connection,
                      p_conn: sqlite3.Connection,
                      source_path: str) -> Playlist:
        playlist_name = os.path.basename(os.path.dirname(source_path)) or "Engine Library"

        tracks: List[Track] = []

        # Read all tracks from m.db
        cur = m_conn.execute("""
            SELECT id, title, artist, album, genre, comment,
                   bpm, key, length, path, filename, sampleRate
            FROM Track
        """)

        for row in cur.fetchall():
            (track_id, title, artist, album, genre, comment,
             bpm, key, length, path, filename, sample_rate) = row

            file_path = os.path.join(path or "", filename or "") if not path else path
            track = Track(
                file_path=file_path,
                title=title or "",
                artist=artist or "",
                album=album or "",
                genre=genre or "",
                comment=comment or "",
                bpm=float(bpm) if bpm else None,
                key=str(key) if key else None,
                duration_seconds=float(length) if length else None,
                sample_rate=int(sample_rate) if sample_rate else _DEFAULT_SAMPLE_RATE,
            )

            # Read cues and beat grid from p.db
            sr = track.sample_rate or _DEFAULT_SAMPLE_RATE
            p_cur = p_conn.execute(
                "SELECT quickCues, beatGrid FROM PerformanceData WHERE id = ?",
                (track_id,)
            )
            p_row = p_cur.fetchone()
            if p_row:
                quick_cues_blob, beat_grid_blob = p_row
                if quick_cues_blob:
                    track.cue_points = _parse_quick_cues(bytes(quick_cues_blob))
                if beat_grid_blob:
                    track.beat_grid = _parse_beat_grid(bytes(beat_grid_blob), sr)

            tracks.append(track)

        return Playlist(name=playlist_name, tracks=tracks)


class EngineOsWriter(BaseWriter):
    """Writes playlist data into an Engine Library folder (m.db + p.db).

    IMPORTANT: Never call this while Engine DJ is running.
    Always write to the desktop Engine Library, not a hardware device.
    """

    def write(self, playlist: Playlist, output_path: str) -> None:
        os.makedirs(output_path, exist_ok=True)
        m_db = os.path.join(output_path, "m.db")
        p_db = os.path.join(output_path, "p.db")

        m_conn = sqlite3.connect(m_db)
        p_conn = sqlite3.connect(p_db)

        try:
            self._init_schema(m_conn, p_conn)
            _check_schema_version(m_conn)
            self._write_playlist(m_conn, p_conn, playlist)
            m_conn.commit()
            p_conn.commit()
        finally:
            m_conn.close()
            p_conn.close()

    def _init_schema(self, m_conn: sqlite3.Connection,
                     p_conn: sqlite3.Connection) -> None:
        m_conn.executescript("""
            CREATE TABLE IF NOT EXISTS Information (
                id            INTEGER PRIMARY KEY,
                schemaVersion TEXT NOT NULL DEFAULT '1.0.0',
                createdAt     TEXT
            );
            INSERT OR IGNORE INTO Information (id, schemaVersion)
            VALUES (1, '1.0.0');

            CREATE TABLE IF NOT EXISTS Track (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT,
                artist      TEXT,
                album       TEXT,
                genre       TEXT,
                comment     TEXT,
                bpm         REAL,
                key         TEXT,
                length      REAL,
                path        TEXT,
                filename    TEXT,
                sampleRate  INTEGER
            );

            CREATE TABLE IF NOT EXISTS Playlist (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS PlaylistTrack (
                playlistId  INTEGER,
                trackId     INTEGER,
                trackNumber INTEGER
            );
        """)

        p_conn.executescript("""
            CREATE TABLE IF NOT EXISTS PerformanceData (
                id         INTEGER PRIMARY KEY,
                quickCues  BLOB,
                beatGrid   BLOB
            );
        """)

    def _write_playlist(self, m_conn: sqlite3.Connection,
                        p_conn: sqlite3.Connection,
                        playlist: Playlist) -> None:
        # Insert playlist
        cur = m_conn.execute(
            "INSERT INTO Playlist (name) VALUES (?)", (playlist.name,)
        )
        playlist_id = cur.lastrowid

        for i, track in enumerate(playlist.tracks, start=1):
            # Insert track
            cur = m_conn.execute("""
                INSERT INTO Track
                  (title, artist, album, genre, comment, bpm, key, length, path, filename, sampleRate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                track.title, track.artist, track.album, track.genre, track.comment,
                track.bpm, track.key, track.duration_seconds,
                os.path.dirname(track.file_path),
                os.path.basename(track.file_path),
                track.sample_rate or _DEFAULT_SAMPLE_RATE,
            ))
            track_id = cur.lastrowid

            # Insert performance data
            sr = track.sample_rate or _DEFAULT_SAMPLE_RATE
            quick_cues_blob = _encode_quick_cues(track.cue_points) if track.cue_points else None
            beat_grid_blob  = _encode_beat_grid(track.beat_grid, sr) if track.beat_grid else None

            p_conn.execute("""
                INSERT INTO PerformanceData (id, quickCues, beatGrid)
                VALUES (?, ?, ?)
            """, (track_id, quick_cues_blob, beat_grid_blob))

            # Link track to playlist
            m_conn.execute("""
                INSERT INTO PlaylistTrack (playlistId, trackId, trackNumber)
                VALUES (?, ?, ?)
            """, (playlist_id, track_id, i))
