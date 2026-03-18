import os
import tempfile

import pytest

from conaconverter.converters.traktor import (
    TraktorReader,
    TraktorWriter,
    _decode_location,
    _encode_location,
)
from conaconverter.models import CueType

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "traktor_minimal.nml")


# ---------------------------------------------------------------------------
# Path codec unit tests
# ---------------------------------------------------------------------------

class TestPathCodec:
    def test_decode_windows_path(self):
        result = _decode_location("C:", "/:C/:Music/:", "track.mp3")
        assert result == "C:/C/Music/track.mp3"

    def test_decode_macos_path(self):
        result = _decode_location("Macintosh HD", "/:Users/:john/:Music/:", "track.mp3")
        assert result == "/Users/john/Music/track.mp3"

    def test_encode_windows_path(self):
        volume, encoded_dir, filename = _encode_location("C:/Music/track.mp3")
        assert volume == "C:"
        assert filename == "track.mp3"
        assert "/:" in encoded_dir

    def test_encode_macos_path(self):
        volume, encoded_dir, filename = _encode_location("/Users/john/Music/track.mp3")
        assert volume == ""
        assert filename == "track.mp3"
        assert "/:" in encoded_dir

    def test_round_trip_windows(self):
        original = "C:/Users/john/Music/track.mp3"
        volume, encoded_dir, filename = _encode_location(original)
        decoded = _decode_location(volume, encoded_dir, filename)
        assert decoded == original

    def test_round_trip_macos(self):
        original = "/Users/john/Music/track.mp3"
        volume, encoded_dir, filename = _encode_location(original)
        decoded = _decode_location(volume, encoded_dir, filename)
        assert decoded == original


# ---------------------------------------------------------------------------
# Reader tests
# ---------------------------------------------------------------------------

class TestTraktorReader:
    def setup_method(self):
        self.reader = TraktorReader()
        self.playlist = self.reader.read(FIXTURE)

    def test_playlist_name(self):
        assert self.playlist.name == "Test Playlist"

    def test_track_count(self):
        assert len(self.playlist.tracks) == 2

    def test_track_one_metadata(self):
        t = self.playlist.tracks[0]
        assert t.title == "Test Track One"
        assert t.artist == "Artist A"
        assert t.album == "Album One"
        assert t.genre == "Techno"
        assert t.comment == "First track"
        assert t.bpm == pytest.approx(128.0)
        assert t.key == "8m"
        assert t.duration_seconds == pytest.approx(240.0)

    def test_track_two_metadata(self):
        t = self.playlist.tracks[1]
        assert t.title == "Test Track Two"
        assert t.bpm == pytest.approx(124.0)
        assert t.genre == "House"
        assert t.key == "11A"

    def test_hot_cues_parsed(self):
        t = self.playlist.tracks[0]
        hot_cues = [c for c in t.cue_points if c.cue_type == CueType.HOT_CUE]
        assert len(hot_cues) == 2

        intro = next(c for c in hot_cues if c.name == "Intro")
        assert intro.position_seconds == pytest.approx(4.123)
        assert intro.num == 0

        drop = next(c for c in hot_cues if c.name == "Drop")
        assert drop.position_seconds == pytest.approx(32.5)
        assert drop.num == 1

    def test_memory_cue_parsed(self):
        t = self.playlist.tracks[0]
        mem = [c for c in t.cue_points if c.cue_type == CueType.MEMORY]
        assert len(mem) == 1
        assert mem[0].num == -1
        assert mem[0].position_seconds == pytest.approx(0.0)

    def test_loop_parsed(self):
        t = self.playlist.tracks[0]
        loops = [c for c in t.cue_points if c.cue_type == CueType.LOOP]
        assert len(loops) == 1
        assert loops[0].position_seconds == pytest.approx(16.0)
        assert loops[0].loop_end_seconds == pytest.approx(32.0)
        assert loops[0].num == 2

    def test_beat_grid_parsed(self):
        t = self.playlist.tracks[0]
        assert len(t.beat_grid) == 1
        assert t.beat_grid[0].position_seconds == pytest.approx(0.150)
        assert t.beat_grid[0].bpm == pytest.approx(128.0)

    def test_grid_markers_not_in_cue_points(self):
        """TYPE=4 grid markers must not appear in cue_points."""
        t = self.playlist.tracks[0]
        for cue in t.cue_points:
            assert cue.position_seconds != pytest.approx(0.150), \
                "Grid marker should not appear as a cue point"

    def test_file_path_decoded(self):
        t = self.playlist.tracks[0]
        assert "track_one.mp3" in t.file_path
        assert "/:" not in t.file_path


# ---------------------------------------------------------------------------
# Writer / round-trip tests
# ---------------------------------------------------------------------------

class TestTraktorWriter:
    def setup_method(self):
        self.reader = TraktorReader()
        self.writer = TraktorWriter()

    def _round_trip(self) -> object:
        original = self.reader.read(FIXTURE)
        with tempfile.NamedTemporaryFile(suffix=".nml", delete=False) as f:
            tmp = f.name
        try:
            self.writer.write(original, tmp)
            return self.reader.read(tmp)
        finally:
            os.unlink(tmp)

    def test_round_trip_track_count(self):
        assert len(self._round_trip().tracks) == 2

    def test_round_trip_metadata(self):
        rt = self._round_trip()
        assert rt.tracks[0].title == "Test Track One"
        assert rt.tracks[0].bpm == pytest.approx(128.0, abs=0.001)
        assert rt.tracks[0].genre == "Techno"
        assert rt.tracks[0].key == "8m"
        assert rt.tracks[0].duration_seconds == pytest.approx(240.0)

    def test_round_trip_cue_positions(self):
        original = self.reader.read(FIXTURE)
        rt = self._round_trip()
        orig_cues = sorted(original.tracks[0].cue_points, key=lambda c: c.position_seconds)
        rt_cues   = sorted(rt.tracks[0].cue_points,       key=lambda c: c.position_seconds)
        assert len(rt_cues) == len(orig_cues)
        for o, r in zip(orig_cues, rt_cues):
            assert r.position_seconds == pytest.approx(o.position_seconds, abs=0.001)
            assert r.cue_type == o.cue_type
            assert r.name == o.name

    def test_round_trip_loop(self):
        rt = self._round_trip()
        loops = [c for c in rt.tracks[0].cue_points if c.cue_type == CueType.LOOP]
        assert len(loops) == 1
        assert loops[0].loop_end_seconds == pytest.approx(32.0, abs=0.001)

    def test_round_trip_beat_grid(self):
        original = self.reader.read(FIXTURE)
        rt = self._round_trip()
        assert len(rt.tracks[0].beat_grid) == len(original.tracks[0].beat_grid)
        for o, r in zip(original.tracks[0].beat_grid, rt.tracks[0].beat_grid):
            assert r.position_seconds == pytest.approx(o.position_seconds, abs=0.001)
            assert r.bpm == pytest.approx(o.bpm, abs=0.001)

    def test_round_trip_playlist_name(self):
        assert self._round_trip().name == "Test Playlist"

    def test_written_file_is_valid_xml(self):
        original = self.reader.read(FIXTURE)
        with tempfile.NamedTemporaryFile(suffix=".nml", delete=False) as f:
            tmp = f.name
        try:
            self.writer.write(original, tmp)
            tree = __import__("xml.etree.ElementTree", fromlist=["ElementTree"])
            root = tree.parse(tmp).getroot()
            assert root.tag == "NML"
        finally:
            os.unlink(tmp)
