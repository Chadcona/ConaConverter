from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class CueType(Enum):
    HOT_CUE  = "hot_cue"
    MEMORY   = "memory"
    LOOP     = "loop"
    FADE_IN  = "fade_in"   # VirtualDJ-specific
    FADE_OUT = "fade_out"  # VirtualDJ-specific


@dataclass
class CuePoint:
    position_seconds: float
    cue_type: CueType
    num: int                              # hot cue slot 0-7; -1 for memory cues
    name: str = ""
    color_rgb: Optional[int] = None       # 0xRRGGBB; None = use format default
    loop_end_seconds: Optional[float] = None  # set only for LOOP type


@dataclass
class BeatGridMarker:
    position_seconds: float   # position of this beat in the track
    bpm: float                # BPM from this marker until the next


@dataclass
class Track:
    file_path: str            # absolute path on the source machine
    title: str = ""
    artist: str = ""
    album: str = ""
    genre: str = ""
    comment: str = ""
    bpm: Optional[float] = None
    key: Optional[str] = None             # stored as-is (Camelot or musical notation)
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None     # Hz — required for sample↔seconds conversion
    cue_points: List[CuePoint] = field(default_factory=list)
    beat_grid: List[BeatGridMarker] = field(default_factory=list)


@dataclass
class Playlist:
    name: str
    tracks: List[Track] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Unit-conversion helpers
# ---------------------------------------------------------------------------

def samples_to_seconds(samples: int, sample_rate: int) -> float:
    return samples / sample_rate


def seconds_to_samples(seconds: float, sample_rate: int) -> int:
    return round(seconds * sample_rate)


def ms_to_seconds(ms: float) -> float:
    return ms / 1000.0


def seconds_to_ms(seconds: float) -> float:
    return seconds * 1000.0
