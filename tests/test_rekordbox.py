import os
import tempfile

import pytest

from conaconverter.converters.rekordbox import RekordboxReader, RekordboxWriter
from conaconverter.models import CueType, Playlist, Track, CuePoint, BeatGridMarker

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "rekordbox_minimal.xml")


class TestRekordboxReader:
    def setup_method(self):
        self.reader = RekordboxReader()
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
        assert t.bpm == pytest.approx(128.0)
        assert t.key == "8m"
        assert t.duration_seconds == pytest.approx(240.0)

    def test_track_two_metadata(self):
        t = self.playlist.tracks[1]
        assert t.title == "Test Track Two"
        assert t.bpm == pytest.approx(124.0)
        assert t.genre == "House"

    def test_hot_cues_parsed(self):
        t = self.playlist.tracks[0]
        hot_cues = [c for c in t.cue_points if c.cue_type == CueType.HOT_CUE]
        assert len(hot_cues) == 2
        intro = next(c for c in hot_cues if c.name == "Intro")
        assert intro.position_seconds == pytest.approx(4.123)
        assert intro.num == 0
        # Check color parsing: R=40, G=226, B=20 → 0x28E214
        assert intro.color_rgb == (40 << 16) | (226 << 8) | 20

    def test_memory_cue_parsed(self):
        t = self.playlist.tracks[0]
        mem_cues = [c for c in t.cue_points if c.cue_type == CueType.MEMORY]
        assert len(mem_cues) == 1
        assert mem_cues[0].num == -1
        assert mem_cues[0].position_seconds == pytest.approx(0.0)

    def test_loop_parsed(self):
        t = self.playlist.tracks[0]
        loops = [c for c in t.cue_points if c.cue_type == CueType.LOOP]
        assert len(loops) == 1
        assert loops[0].position_seconds == pytest.approx(16.0)
        assert loops[0].loop_end_seconds == pytest.approx(32.0)

    def test_beat_grid_parsed(self):
        t = self.playlist.tracks[0]
        assert len(t.beat_grid) == 1
        assert t.beat_grid[0].position_seconds == pytest.approx(0.150)
        assert t.beat_grid[0].bpm == pytest.approx(128.0)

    def test_file_path_stripped(self):
        t = self.playlist.tracks[0]
        assert "file://localhost" not in t.file_path
        assert t.file_path.endswith("track_one.mp3")


class TestRekordboxWriter:
    def setup_method(self):
        self.reader = RekordboxReader()
        self.writer = RekordboxWriter()

    def _round_trip(self, source_path: str) -> Playlist:
        original = self.reader.read(source_path)
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            tmp_path = f.name
        try:
            self.writer.write(original, tmp_path)
            return self.reader.read(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_round_trip_track_count(self):
        rt = self._round_trip(FIXTURE)
        original = self.reader.read(FIXTURE)
        assert len(rt.tracks) == len(original.tracks)

    def test_round_trip_metadata(self):
        rt = self._round_trip(FIXTURE)
        assert rt.tracks[0].title == "Test Track One"
        assert rt.tracks[0].bpm == pytest.approx(128.0, abs=0.01)
        assert rt.tracks[0].genre == "Techno"
        assert rt.tracks[0].key == "8m"

    def test_round_trip_cue_positions(self):
        rt = self._round_trip(FIXTURE)
        original = self.reader.read(FIXTURE)
        orig_cues = sorted(original.tracks[0].cue_points, key=lambda c: c.position_seconds)
        rt_cues   = sorted(rt.tracks[0].cue_points, key=lambda c: c.position_seconds)
        assert len(rt_cues) == len(orig_cues)
        for orig, result in zip(orig_cues, rt_cues):
            assert result.position_seconds == pytest.approx(orig.position_seconds, abs=0.001)
            assert result.cue_type == orig.cue_type
            assert result.name == orig.name

    def test_round_trip_beat_grid(self):
        rt = self._round_trip(FIXTURE)
        original = self.reader.read(FIXTURE)
        assert len(rt.tracks[0].beat_grid) == len(original.tracks[0].beat_grid)
        for orig, result in zip(original.tracks[0].beat_grid, rt.tracks[0].beat_grid):
            assert result.position_seconds == pytest.approx(orig.position_seconds, abs=0.001)
            assert result.bpm == pytest.approx(orig.bpm, abs=0.01)

    def test_round_trip_loop(self):
        rt = self._round_trip(FIXTURE)
        loops = [c for c in rt.tracks[0].cue_points if c.cue_type == CueType.LOOP]
        assert len(loops) == 1
        assert loops[0].loop_end_seconds == pytest.approx(32.0, abs=0.001)

    def test_round_trip_playlist_name(self):
        rt = self._round_trip(FIXTURE)
        assert rt.name == "Test Playlist"
