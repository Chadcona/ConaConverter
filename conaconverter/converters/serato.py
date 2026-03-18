"""Serato .crate / database V2 ↔ universal Playlist converter.

Serato stores playlist membership in binary .crate files.
Cue points and beat grid are stored as GEOB ID3 tags embedded
directly in each audio file ('Serato Markers2', 'Serato BeatGrid').

WARNING: Writing Serato format modifies the audio files themselves.
The application displays a warning dialog before performing any write.

Dependencies: serato-tools (pip install serato-tools), mutagen
"""

from __future__ import annotations

import os
from typing import List

from conaconverter.converters.base import BaseReader, BaseWriter
from conaconverter.models import (
    BeatGridMarker,
    CuePoint,
    CueType,
    Playlist,
    Track,
    ms_to_seconds,
    seconds_to_ms,
)


class SeratoReader(BaseReader):
    def read(self, path: str) -> Playlist:
        try:
            from serato_tools.crate import Crate  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "serato-tools is required to read Serato files. "
                "Install it with: pip install serato-tools"
            ) from exc

        playlist_name = os.path.splitext(os.path.basename(path))[0]
        crate = Crate(path)
        tracks: List[Track] = []

        for track_path in crate.get_tracks():
            track = self._read_track(track_path)
            tracks.append(track)

        return Playlist(name=playlist_name, tracks=tracks)

    def _read_track(self, file_path: str) -> Track:
        try:
            from serato_tools.track import Track as SeratoTrack  # type: ignore
        except ImportError as exc:
            raise ImportError("serato-tools is required") from exc

        track = Track(file_path=file_path)

        try:
            s_track = SeratoTrack(file_path)
        except Exception:
            # File may not exist on this machine — return path-only track
            return track

        # Read basic metadata via mutagen if available
        try:
            import mutagen  # type: ignore
            audio = mutagen.File(file_path, easy=True)
            if audio:
                track.title  = (audio.get("title",  [""])[0])
                track.artist = (audio.get("artist", [""])[0])
                track.album  = (audio.get("album",  [""])[0])
                track.genre  = (audio.get("genre",  [""])[0])
                if hasattr(audio.info, "length"):
                    track.duration_seconds = audio.info.length
                if hasattr(audio.info, "sample_rate"):
                    track.sample_rate = audio.info.sample_rate
        except Exception:
            pass

        # Read cue points from Serato Markers2 GEOB tag
        try:
            markers = s_track.get_markers2()
            if markers:
                for marker in markers:
                    cue_type = CueType.HOT_CUE
                    if hasattr(marker, "type"):
                        mt = str(marker.type).lower()
                        if "loop" in mt:
                            cue_type = CueType.LOOP
                        elif "memory" in mt:
                            cue_type = CueType.MEMORY

                    pos_ms = getattr(marker, "start_ms", None) or getattr(marker, "start", None)
                    if pos_ms is None:
                        continue

                    num = getattr(marker, "index", 0) or 0
                    color = getattr(marker, "color", None)
                    color_rgb: int | None = None
                    if color is not None:
                        try:
                            color_rgb = int(color) & 0xFFFFFF
                        except (ValueError, TypeError):
                            pass

                    loop_end: float | None = None
                    if cue_type == CueType.LOOP:
                        end_ms = getattr(marker, "end_ms", None) or getattr(marker, "end", None)
                        if end_ms is not None:
                            loop_end = ms_to_seconds(float(end_ms))

                    track.cue_points.append(CuePoint(
                        position_seconds=ms_to_seconds(float(pos_ms)),
                        cue_type=cue_type,
                        num=num,
                        name=getattr(marker, "name", "") or "",
                        color_rgb=color_rgb,
                        loop_end_seconds=loop_end,
                    ))
        except Exception:
            pass

        # Read beat grid
        try:
            beatgrid = s_track.get_beatgrid()
            if beatgrid:
                for point in beatgrid:
                    pos_samples = getattr(point, "position", None)
                    bpm = getattr(point, "bpm", None)
                    if pos_samples is not None and bpm is not None and track.sample_rate:
                        from conaconverter.models import samples_to_seconds
                        track.beat_grid.append(BeatGridMarker(
                            position_seconds=samples_to_seconds(int(pos_samples), track.sample_rate),
                            bpm=float(bpm),
                        ))
        except Exception:
            pass

        return track


class SeratoWriter(BaseWriter):
    """Writes Serato cue/grid data back into audio file GEOB tags.

    WARNING: This modifies the audio files themselves.
    The UI must present a warning dialog before calling this.
    """

    def write(self, playlist: Playlist, output_path: str) -> None:
        try:
            from serato_tools.crate import Crate  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "serato-tools is required to write Serato files. "
                "Install it with: pip install serato-tools"
            ) from exc

        crate = Crate()
        for track in playlist.tracks:
            crate.add_track(track.file_path)
            self._write_track_tags(track)

        crate.save_to_file(output_path)

    def _write_track_tags(self, track: Track) -> None:
        """Embed Serato Markers2 GEOB tag into the audio file."""
        try:
            from serato_tools.track import Track as SeratoTrack  # type: ignore
        except ImportError:
            return

        if not os.path.exists(track.file_path):
            return

        try:
            s_track = SeratoTrack(track.file_path)

            markers = []
            for cue in track.cue_points:
                marker_data = {
                    "start_ms": int(seconds_to_ms(cue.position_seconds)),
                    "index": cue.num,
                    "name": cue.name,
                    "color": cue.color_rgb or 0xCC0000,
                }
                if cue.cue_type == CueType.LOOP and cue.loop_end_seconds is not None:
                    marker_data["end_ms"] = int(seconds_to_ms(cue.loop_end_seconds))
                    marker_data["type"] = "LOOP"
                else:
                    marker_data["type"] = "CUE"
                markers.append(marker_data)

            s_track.set_markers2(markers)
            s_track.save()
        except Exception:
            pass  # Best-effort; caller can surface errors via UI
