"""Engine OS reader/writer tests.

These tests use a synthetic in-memory SQLite database — no real DJ hardware needed.
"""

import os
import sqlite3
import struct
import tempfile
import zlib

import pytest

from conaconverter.converters.engineos import (
    EngineOsReader,
    EngineOsWriter,
    _decode_blob,
    _encode_blob,
    _parse_quick_cues,
    _encode_quick_cues,
    _parse_beat_grid,
    _encode_beat_grid,
)
from conaconverter.models import CuePoint, CueType, BeatGridMarker, Playlist, Track


# ---------------------------------------------------------------------------
# BLOB codec unit tests
# ---------------------------------------------------------------------------

class TestBlobCodec:
    def test_encode_decode_roundtrip(self):
        data = b"hello world test data"
        encoded = _encode_blob(data)
        assert _decode_blob(encoded) == data

    def test_encoded_has_length_prefix(self):
        data = b"abc"
        encoded = _encode_blob(data)
        length = struct.unpack(">I", encoded[:4])[0]
        assert length == len(data)

    def test_decode_empty(self):
        assert _decode_blob(b"") == b""

    def test_decode_too_short(self):
        assert _decode_blob(b"\x00\x00") == b""


class TestQuickCuesCodec:
    def _make_cue(self, num, pos_s, name="", color=None):
        return CuePoint(
            position_seconds=pos_s,
            cue_type=CueType.HOT_CUE,
            num=num,
            name=name,
            color_rgb=color,
        )

    def test_round_trip_single_cue(self):
        cues = [self._make_cue(0, 4.123, name="Intro", color=0x28E214)]
        encoded = _encode_quick_cues(cues)
        decoded = _parse_quick_cues(encoded)
        assert len(decoded) == 1
        assert decoded[0].position_seconds == pytest.approx(4.123, abs=0.001)
        assert decoded[0].name == "Intro"
        assert decoded[0].color_rgb == 0x28E214
        assert decoded[0].num == 0

    def test_round_trip_multiple_cues(self):
        cues = [
            self._make_cue(0, 4.0, name="A"),
            self._make_cue(3, 32.5, name="B", color=0xFF0000),
            self._make_cue(7, 64.0),
        ]
        encoded = _encode_quick_cues(cues)
        decoded = _parse_quick_cues(encoded)
        assert len(decoded) == 3
        positions = {c.num: c.position_seconds for c in decoded}
        assert positions[0] == pytest.approx(4.0, abs=0.001)
        assert positions[3] == pytest.approx(32.5, abs=0.001)
        assert positions[7] == pytest.approx(64.0, abs=0.001)

    def test_empty_cues(self):
        encoded = _encode_quick_cues([])
        decoded = _parse_quick_cues(encoded)
        assert decoded == []

    def test_position_accuracy(self):
        """Cue positions must survive encode/decode within 1ms."""
        pos = 123.456
        cues = [self._make_cue(0, pos)]
        decoded = _parse_quick_cues(_encode_quick_cues(cues))
        assert decoded[0].position_seconds == pytest.approx(pos, abs=0.001)


class TestBeatGridCodec:
    _SR = 44100

    def test_round_trip_single_marker(self):
        markers = [BeatGridMarker(position_seconds=0.150, bpm=128.0)]
        encoded = _encode_beat_grid(markers, self._SR)
        decoded = _parse_beat_grid(encoded, self._SR)
        assert len(decoded) == 1
        assert decoded[0].position_seconds == pytest.approx(0.150, abs=0.001)
        assert decoded[0].bpm == pytest.approx(128.0, abs=0.01)

    def test_round_trip_multiple_markers(self):
        markers = [
            BeatGridMarker(0.0, 128.0),
            BeatGridMarker(32.0, 140.0),
        ]
        encoded = _encode_beat_grid(markers, self._SR)
        decoded = _parse_beat_grid(encoded, self._SR)
        assert len(decoded) == 2
        assert decoded[1].bpm == pytest.approx(140.0, abs=0.01)

    def test_empty_beat_grid(self):
        encoded = _encode_beat_grid([], self._SR)
        decoded = _parse_beat_grid(encoded, self._SR)
        assert decoded == []


# ---------------------------------------------------------------------------
# Full reader/writer integration tests using a synthetic SQLite DB
# ---------------------------------------------------------------------------

def _build_engine_library(folder: str) -> None:
    """Create a minimal Engine Library in *folder* for testing."""
    m_db = os.path.join(folder, "m.db")
    p_db = os.path.join(folder, "p.db")

    m_conn = sqlite3.connect(m_db)
    p_conn = sqlite3.connect(p_db)

    m_conn.executescript("""
        CREATE TABLE Information (id INTEGER PRIMARY KEY, schemaVersion TEXT);
        INSERT INTO Information VALUES (1, '1.0.0');

        CREATE TABLE Track (
            id INTEGER PRIMARY KEY, title TEXT, artist TEXT, album TEXT,
            genre TEXT, comment TEXT, bpm REAL, key TEXT, length REAL,
            path TEXT, filename TEXT, sampleRate INTEGER
        );
        CREATE TABLE Playlist (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);
        CREATE TABLE PlaylistTrack (playlistId INTEGER, trackId INTEGER, trackNumber INTEGER);
    """)

    p_conn.executescript("""
        CREATE TABLE PerformanceData (id INTEGER PRIMARY KEY, quickCues BLOB, beatGrid BLOB);
    """)

    cues = [CuePoint(4.0, CueType.HOT_CUE, 0, name="Drop", color_rgb=0xFF0000)]
    grid = [BeatGridMarker(0.0, 128.0)]
    sr = 44100

    quick_blob = _encode_quick_cues(cues)
    grid_blob  = _encode_beat_grid(grid, sr)

    m_conn.execute("""
        INSERT INTO Track VALUES
          (1,'Test Track','Artist A','Album','Techno','',128.0,'8m',240.0,
           '/Music','track.mp3',44100)
    """)
    p_conn.execute("INSERT INTO PerformanceData VALUES (1,?,?)", (quick_blob, grid_blob))
    m_conn.execute("INSERT INTO Playlist VALUES (1,'Test Playlist')")
    m_conn.execute("INSERT INTO PlaylistTrack VALUES (1,1,1)")

    m_conn.commit()
    p_conn.commit()
    m_conn.close()
    p_conn.close()


class TestEngineOsReader:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        _build_engine_library(self.tmpdir)
        self.playlist = EngineOsReader().read(self.tmpdir)

    def test_track_count(self):
        assert len(self.playlist.tracks) == 1

    def test_metadata(self):
        t = self.playlist.tracks[0]
        assert t.title == "Test Track"
        assert t.artist == "Artist A"
        assert t.bpm == pytest.approx(128.0)
        assert t.key == "8m"

    def test_cue_points(self):
        t = self.playlist.tracks[0]
        assert len(t.cue_points) == 1
        assert t.cue_points[0].position_seconds == pytest.approx(4.0, abs=0.001)
        assert t.cue_points[0].name == "Drop"
        assert t.cue_points[0].color_rgb == 0xFF0000

    def test_beat_grid(self):
        t = self.playlist.tracks[0]
        assert len(t.beat_grid) == 1
        assert t.beat_grid[0].bpm == pytest.approx(128.0, abs=0.01)


class TestEngineOsWriter:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _make_playlist(self) -> Playlist:
        track = Track(
            file_path="/Music/track.mp3",
            title="Writer Track",
            artist="Artist W",
            bpm=130.0,
            key="5A",
            duration_seconds=300.0,
            sample_rate=44100,
            cue_points=[CuePoint(8.0, CueType.HOT_CUE, 0, name="Start", color_rgb=0x00FF00)],
            beat_grid=[BeatGridMarker(0.0, 130.0)],
        )
        return Playlist(name="Writer Test", tracks=[track])

    def test_write_creates_db_files(self):
        out = os.path.join(self.tmpdir, "output")
        EngineOsWriter().write(self._make_playlist(), out)
        assert os.path.exists(os.path.join(out, "m.db"))
        assert os.path.exists(os.path.join(out, "p.db"))

    def test_round_trip(self):
        out = os.path.join(self.tmpdir, "output")
        EngineOsWriter().write(self._make_playlist(), out)
        rt = EngineOsReader().read(out)
        assert len(rt.tracks) == 1
        assert rt.tracks[0].title == "Writer Track"
        assert rt.tracks[0].bpm == pytest.approx(130.0)
        assert len(rt.tracks[0].cue_points) == 1
        assert rt.tracks[0].cue_points[0].position_seconds == pytest.approx(8.0, abs=0.001)
        assert rt.tracks[0].cue_points[0].name == "Start"
        assert len(rt.tracks[0].beat_grid) == 1
        assert rt.tracks[0].beat_grid[0].bpm == pytest.approx(130.0, abs=0.01)
