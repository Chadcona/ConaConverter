"""Serato .crate / SQLite library ↔ universal Playlist converter.

Serato stores playlist membership in binary .crate files or in a
SQLite database (location.sqlite) on the drive containing the music.
Cue points and beat grid are stored as GEOB ID3 tags embedded
directly in each audio file ('Serato Markers2', 'Serato BeatGrid').

WARNING: Writing Serato format modifies the audio files themselves.
The application displays a warning dialog before performing any write.

Dependencies: serato-tools (pip install serato-tools), mutagen
"""

from __future__ import annotations

import logging
import os
import sqlite3
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

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serato SQLite helpers
# ---------------------------------------------------------------------------

def _find_serato_sqlite() -> list[str]:
    """Return paths to all Serato location.sqlite files found on the system."""
    results = []
    # Check all drive letters on Windows
    if os.name == "nt":
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            db = f"{letter}:/_Serato_/Library/location.sqlite"
            if os.path.isfile(db):
                results.append(db)
    else:
        # macOS / Linux: check ~/Music and mounted volumes
        home_db = os.path.expanduser("~/Music/_Serato_/Library/location.sqlite")
        if os.path.isfile(home_db):
            results.append(home_db)
        volumes = "/Volumes" if os.path.isdir("/Volumes") else "/media"
        if os.path.isdir(volumes):
            try:
                for entry in os.listdir(volumes):
                    db = os.path.join(volumes, entry, "_Serato_", "Library", "location.sqlite")
                    if os.path.isfile(db):
                        results.append(db)
            except OSError:
                pass
    return results


def _read_container_from_sqlite(db_path: str, container_id: int) -> Playlist | None:
    """Read a crate (container) and its tracks from a Serato SQLite database."""
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT name FROM container WHERE id = ?", (container_id,)
        ).fetchone()
        if not row:
            conn.close()
            return None

        crate_name = row[0]
        tracks: list[Track] = []

        # Join through container_asset → space_asset → asset to get track info
        rows = conn.execute("""
            SELECT a.file_name, a.artist, a.name, a.album, a.genre,
                   a.bpm, a.key, a.length_sec, a.file_sample_rate
            FROM container_asset ca
            JOIN space_asset sa ON ca.space_asset_id = sa.id
            JOIN asset a ON sa.asset_id = a.id
            WHERE ca.container_id = ?
            ORDER BY ca.list_order
        """, (container_id,)).fetchall()

        # Determine the drive/root where this DB lives
        drive_root = os.path.splitdrive(db_path)[0] + os.sep

        for r in rows:
            file_name, artist, title, album, genre, bpm, key, length, sr = r
            # file_name in the DB is relative to the drive root
            file_path = os.path.join(drive_root, file_name) if file_name else ""
            track = Track(
                file_path=file_path,
                title=title or "",
                artist=artist or "",
                album=album or "",
                genre=genre or "",
                bpm=float(bpm) if bpm else None,
                key=key or None,
                duration_seconds=float(length) if length else None,
                sample_rate=int(sr) if sr else None,
            )
            tracks.append(track)

        conn.close()
        return Playlist(name=crate_name, tracks=tracks)
    except (sqlite3.Error, OSError) as exc:
        log.warning("Failed to read Serato SQLite DB %s: %s", db_path, exc)
        return None


def _list_containers_from_sqlite(db_path: str) -> list[tuple[int, str, int | None]]:
    """Return (id, name, parent_id) for all crate containers in a Serato SQLite DB."""
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT id, name, parent_id FROM container WHERE type = 1 ORDER BY id"
        ).fetchall()
        conn.close()
        return rows
    except (sqlite3.Error, OSError):
        return []


def resolve_serato_container_uri(uri: str) -> Playlist | None:
    """Resolve a Serato assetlist://container/NNN URI to a Playlist.

    Serato drag-and-drop sends these URIs. The container ID is an internal
    ID that may not match the SQLite row ID, so we try all available
    Serato databases and also try matching by scanning containers.
    """
    # Parse the container ID
    prefix = "assetlist://container/"
    if not uri.startswith(prefix):
        return None
    try:
        container_id = int(uri[len(prefix):])
    except ValueError:
        return None

    # Try each database
    for db_path in _find_serato_sqlite():
        result = _read_container_from_sqlite(db_path, container_id)
        if result:
            return result

    return None


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

class SeratoReader(BaseReader):
    def read(self, path: str) -> Playlist:
        # serato-sqlite:// URI from the crate picker dialog
        if path.startswith("serato-sqlite://"):
            result = self._read_from_sqlite_uri(path)
            return self._enrich_tracks(result)

        # assetlist:// URI from Serato drag-and-drop (fallback)
        if path.startswith("assetlist://"):
            result = resolve_serato_container_uri(path)
            if result:
                return self._enrich_tracks(result)
            raise ValueError(f"Could not resolve Serato container URI: {path}")

        # If path is a SQLite database, read all tracks
        if path.endswith("location.sqlite"):
            return self._read_from_sqlite(path)

        # Otherwise treat as .crate file
        return self._read_from_crate(path)

    def _read_from_sqlite_uri(self, uri: str) -> Playlist:
        """Parse a serato-sqlite://PATH?container=ID URI and read the crate."""
        # Format: serato-sqlite:///path/to/location.sqlite?container=13
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(uri)
        db_path = parsed.netloc + parsed.path  # reconstruct full path
        params = parse_qs(parsed.query)
        container_id = int(params["container"][0])

        result = _read_container_from_sqlite(db_path, container_id)
        if result:
            return result
        raise ValueError(
            f"Could not find container {container_id} in {db_path}"
        )

    def _read_from_sqlite(self, db_path: str) -> Playlist:
        """Read all tracks from a Serato SQLite database."""
        try:
            conn = sqlite3.connect(db_path)
            rows = conn.execute("""
                SELECT a.file_name, a.artist, a.name, a.album, a.genre,
                       a.bpm, a.key, a.length_sec, a.file_sample_rate
                FROM asset a
                ORDER BY a.id
            """).fetchall()
            drive_root = os.path.splitdrive(db_path)[0] + os.sep
            tracks: list[Track] = []
            for r in rows:
                file_name, artist, title, album, genre, bpm, key, length, sr = r
                file_path = os.path.join(drive_root, file_name) if file_name else ""
                tracks.append(Track(
                    file_path=file_path,
                    title=title or "",
                    artist=artist or "",
                    album=album or "",
                    genre=genre or "",
                    bpm=float(bpm) if bpm else None,
                    key=key or None,
                    duration_seconds=float(length) if length else None,
                    sample_rate=int(sr) if sr else None,
                ))
            conn.close()
            return Playlist(name="Serato Library", tracks=tracks)
        except (sqlite3.Error, OSError) as exc:
            raise ValueError(f"Failed to read Serato SQLite DB: {exc}") from exc

    def _read_from_crate(self, path: str) -> Playlist:
        """Read a .crate file."""
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

    def _enrich_tracks(self, playlist: Playlist) -> Playlist:
        """Read GEOB cue/grid data from audio files for tracks that exist."""
        for i, track in enumerate(playlist.tracks):
            if os.path.isfile(track.file_path):
                enriched = self._read_track(track.file_path)
                # Merge: keep SQLite metadata, add GEOB cues/grid
                enriched.title = track.title or enriched.title
                enriched.artist = track.artist or enriched.artist
                enriched.album = track.album or enriched.album
                enriched.genre = track.genre or enriched.genre
                enriched.bpm = track.bpm or enriched.bpm
                enriched.key = track.key or enriched.key
                enriched.duration_seconds = track.duration_seconds or enriched.duration_seconds
                enriched.sample_rate = track.sample_rate or enriched.sample_rate
                playlist.tracks[i] = enriched
        return playlist

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
