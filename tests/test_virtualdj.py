import os
import tempfile

import pytest

from conaconverter.converters.virtualdj import VirtualDjReader, VirtualDjWriter
from conaconverter.models import CueType

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "virtualdj_minimal.xml")


class TestVirtualDjReader:
    def setup_method(self):
        self.reader = VirtualDjReader()
        self.playlist = self.reader.read(FIXTURE)

    def test_track_count(self):
        assert len(self.playlist.tracks) == 2

    def test_track_one_metadata(self):
        t = self.playlist.tracks[0]
        assert t.title == "Test Track One"
        assert t.artist == "Artist A"
        assert t.genre == "Techno"
        assert t.duration_seconds == pytest.approx(240.0)

    def test_bpm_conversion(self):
        """Scan/@Bpm is seconds-per-beat; BPM = 60 / value."""
        t = self.playlist.tracks[0]
        # 0.468750 spb → 60 / 0.468750 = 128.0 BPM
        assert t.bpm == pytest.approx(128.0, abs=0.01)

    def test_track_two_bpm(self):
        t = self.playlist.tracks[1]
        # 0.483871 spb → 60 / 0.483871 ≈ 124.0 BPM
        assert t.bpm == pytest.approx(124.0, abs=0.1)

    def test_cue_positions(self):
        t = self.playlist.tracks[0]
        cues = [c for c in t.cue_points if c.cue_type == CueType.HOT_CUE]
        assert len(cues) == 2
        intro = next(c for c in cues if c.name == "Intro")
        assert intro.position_seconds == pytest.approx(4.123)
        assert intro.num == 0
        assert intro.color_rgb == 0x28E214

    def test_loop_parsed(self):
        t = self.playlist.tracks[0]
        loops = [c for c in t.cue_points if c.cue_type == CueType.LOOP]
        assert len(loops) == 1
        assert loops[0].position_seconds == pytest.approx(16.0)
        assert loops[0].loop_end_seconds == pytest.approx(32.0, abs=0.001)

    def test_beat_grid_parsed(self):
        t = self.playlist.tracks[0]
        assert len(t.beat_grid) == 1
        assert t.beat_grid[0].position_seconds == pytest.approx(-0.002)

    def test_key_parsed(self):
        assert self.playlist.tracks[0].key == "8m"


class TestVirtualDjWriter:
    def setup_method(self):
        self.reader = VirtualDjReader()
        self.writer = VirtualDjWriter()

    def _round_trip(self) -> object:
        original = self.reader.read(FIXTURE)
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            tmp_path = f.name
        try:
            self.writer.write(original, tmp_path)
            return self.reader.read(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_round_trip_track_count(self):
        rt = self._round_trip()
        assert len(rt.tracks) == 2

    def test_round_trip_bpm(self):
        """BPM must survive the seconds-per-beat conversion in both directions."""
        rt = self._round_trip()
        assert rt.tracks[0].bpm == pytest.approx(128.0, abs=0.01)
        assert rt.tracks[1].bpm == pytest.approx(124.0, abs=0.1)

    def test_round_trip_cue_positions(self):
        original = self.reader.read(FIXTURE)
        rt = self._round_trip()
        orig_cues = sorted(original.tracks[0].cue_points, key=lambda c: c.position_seconds)
        rt_cues   = sorted(rt.tracks[0].cue_points, key=lambda c: c.position_seconds)
        assert len(rt_cues) == len(orig_cues)
        for orig, result in zip(orig_cues, rt_cues):
            assert result.position_seconds == pytest.approx(orig.position_seconds, abs=0.001)

    def test_round_trip_loop(self):
        rt = self._round_trip()
        loops = [c for c in rt.tracks[0].cue_points if c.cue_type == CueType.LOOP]
        assert len(loops) == 1
        assert loops[0].loop_end_seconds == pytest.approx(32.0, abs=0.001)

    def test_round_trip_metadata(self):
        rt = self._round_trip()
        assert rt.tracks[0].title == "Test Track One"
        assert rt.tracks[0].genre == "Techno"
        assert rt.tracks[0].key == "8m"
