"""Traktor (Native Instruments) .nml ↔ universal Playlist converter.

Traktor uses an XML format with a .nml extension.

NML structure:
  <NML VERSION="23">
    <HEAD COMPANY="www.native-instruments.com" PROGRAM="Traktor"/>
    <COLLECTION ENTRIES="N">
      <ENTRY TITLE="Track Title" ARTIST="Artist Name" MODIFIED_DATE="..." AUDIO_ID="...">
        <LOCATION DIR="/:Users/:name/:Music/:" FILE="track.mp3" VOLUME="C:" VOLUMEID="C:"/>
        <ALBUM TRACK="0" TITLE="Album Name"/>
        <INFO BITRATE="320000" GENRE="Techno" COMMENT="" KEY="8m"
              PLAYTIME="240" PLAYTIME_FLOAT="240.500"/>
        <TEMPO BPM="128.000000" BPM_QUALITY="100"/>
        <MUSICAL_KEY VALUE="0"/>
        <CUE_V2 NAME="Intro" DISPL_ORDER="0" TYPE="0" START="4123.000000"
                LEN="0.000000" REPEATS="-1" HOTCUE="0"/>
      </ENTRY>
    </COLLECTION>
    <PLAYLISTS>
      <NODE TYPE="FOLDER" NAME="$ROOT">
        <SUBNODES COUNT="1">
          <NODE TYPE="PLAYLIST" NAME="My Playlist">
            <PLAYLIST ENTRIES="2" TYPE="LIST" UUID="...">
              <ENTRY>
                <PRIMARYKEY TYPE="TRACK" KEY="C:/Music/track.mp3"/>
              </ENTRY>
            </PLAYLIST>
          </NODE>
        </SUBNODES>
      </NODE>
    </PLAYLISTS>
  </NML>

CUE_V2 TYPE values:
  0 = cue point
  1 = fade-in marker
  2 = fade-out marker
  3 = load marker
  4 = grid marker (beat grid anchor)
  5 = loop

CUE_V2 HOTCUE values:
  -1 = not a hot cue (memory cue / load marker)
  0-7 = hot cue slot index

CUE_V2 START: position in milliseconds (float string)
CUE_V2 LEN:   length in milliseconds for loops; 0 for all other types

LOCATION DIR encoding:
  Each path component is prefixed with /: — e.g. /Users/john/Music/
  is stored as /:Users/:john/:Music/:
  VOLUME holds the Windows drive letter (e.g. "C:") or macOS volume name.
"""

from __future__ import annotations

import hashlib
import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

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

# CUE_V2 TYPE integer → CueType
_TRAKTOR_TYPE_TO_CUE: Dict[int, CueType] = {
    0: CueType.HOT_CUE,   # refined to MEMORY if HOTCUE == -1
    1: CueType.FADE_IN,
    2: CueType.FADE_OUT,
    3: CueType.MEMORY,    # load marker
    5: CueType.LOOP,
    # TYPE 4 = grid marker — handled separately as BeatGridMarker
}

_CUE_TO_TRAKTOR_TYPE: Dict[CueType, int] = {
    CueType.HOT_CUE:  0,
    CueType.MEMORY:   0,  # TYPE=0, HOTCUE=-1
    CueType.LOOP:     5,
    CueType.FADE_IN:  1,
    CueType.FADE_OUT: 2,
}


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _decode_location(volume: str, dir_str: str, filename: str) -> str:
    """Reconstruct an absolute file path from Traktor's LOCATION attributes."""
    # DIR uses /: as path separator: /:Users/:john/:Music/: → /Users/john/Music/
    decoded_dir = dir_str.replace("/:", "/")

    if volume.endswith(":") and len(volume) == 2:
        # Windows drive letter e.g. "C:"
        return volume + decoded_dir + filename
    else:
        # macOS/Linux — volume is a name like "Macintosh HD"; path is already absolute
        return decoded_dir + filename


def _encode_location(file_path: str) -> Tuple[str, str, str]:
    """Return (volume, encoded_dir, filename) for a Traktor LOCATION element."""
    file_path = file_path.replace("\\", "/")
    filename  = os.path.basename(file_path)
    dir_path  = os.path.dirname(file_path)

    if not dir_path.endswith("/"):
        dir_path += "/"

    if len(dir_path) >= 3 and dir_path[1] == ":":
        # Windows: "C:/Users/john/Music/"
        volume   = dir_path[:2]       # "C:"
        dir_rest = dir_path[2:]       # "/Users/john/Music/"
        encoded_dir = dir_rest.replace("/", "/:")
    else:
        # macOS / Linux: "/Users/john/Music/"
        volume      = ""
        encoded_dir = dir_path.replace("/", "/:")

    return volume, encoded_dir, filename


def _audio_id(file_path: str) -> str:
    """Generate a stable pseudo-AUDIO_ID from the file path."""
    return hashlib.md5(file_path.encode()).hexdigest().upper()[:32]


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

class TraktorReader(BaseReader):
    def read(self, path: str) -> Playlist:
        tree = ET.parse(path)
        root = tree.getroot()

        if root.tag != "NML":
            raise ValueError(f"Not a Traktor NML file: root tag is <{root.tag}>")

        # Build track map: file_path → Track
        track_map: Dict[str, Track] = {}
        collection = root.find("COLLECTION")
        if collection is not None:
            for entry in collection.findall("ENTRY"):
                track, key = self._parse_entry(entry)
                if key:
                    track_map[key] = track

        # Resolve playlist order
        playlist_name = os.path.splitext(os.path.basename(path))[0]
        tracks: List[Track] = []

        playlists = root.find("PLAYLISTS")
        if playlists is not None:
            for node in playlists.iter("NODE"):
                if node.get("TYPE") == "PLAYLIST":
                    playlist_name = node.get("NAME", playlist_name)
                    pl = node.find("PLAYLIST")
                    if pl is not None:
                        for entry in pl.findall("ENTRY"):
                            pk = entry.find("PRIMARYKEY")
                            if pk is not None:
                                key = pk.get("KEY", "")
                                if key in track_map:
                                    tracks.append(track_map[key])
                    break  # first playlist only in MVP

        # Fallback: all tracks in collection order
        if not tracks and track_map:
            tracks = list(track_map.values())

        return Playlist(name=playlist_name, tracks=tracks)

    def _parse_entry(self, entry: ET.Element) -> Tuple[Track, str]:
        """Parse a single ENTRY element. Returns (Track, file_path_key)."""
        # --- Location ---
        loc = entry.find("LOCATION")
        if loc is None:
            return Track(file_path=""), ""

        file_path = _decode_location(
            loc.get("VOLUME", ""),
            loc.get("DIR", ""),
            loc.get("FILE", ""),
        )

        track = Track(
            file_path=file_path,
            title=entry.get("TITLE", ""),
            artist=entry.get("ARTIST", ""),
        )

        # --- Album ---
        album = entry.find("ALBUM")
        if album is not None:
            track.album = album.get("TITLE", "")

        # --- Info ---
        info = entry.find("INFO")
        if info is not None:
            track.genre   = info.get("GENRE", "")
            track.comment = info.get("COMMENT", "")
            track.key     = info.get("KEY") or None
            playtime = info.get("PLAYTIME_FLOAT") or info.get("PLAYTIME")
            if playtime:
                track.duration_seconds = float(playtime)

        # --- Tempo ---
        tempo = entry.find("TEMPO")
        if tempo is not None:
            bpm_str = tempo.get("BPM")
            if bpm_str:
                track.bpm = float(bpm_str)

        # --- Cues and grid ---
        for cue_elem in entry.findall("CUE_V2"):
            cue_type_int = int(cue_elem.get("TYPE", "0"))
            start_str    = cue_elem.get("START")
            if start_str is None:
                continue
            start_ms = float(start_str)

            # TYPE 4 = grid marker → BeatGridMarker
            if cue_type_int == 4:
                track.beat_grid.append(BeatGridMarker(
                    position_seconds=ms_to_seconds(start_ms),
                    bpm=track.bpm or 0.0,
                ))
                continue

            cue_type = _TRAKTOR_TYPE_TO_CUE.get(cue_type_int, CueType.HOT_CUE)
            hotcue   = int(cue_elem.get("HOTCUE", "-1"))

            # TYPE 0 with HOTCUE=-1 is a memory cue
            if cue_type_int == 0 and hotcue == -1:
                cue_type = CueType.MEMORY

            num = hotcue  # -1 for memory, 0-7 for hot cues

            loop_end: Optional[float] = None
            if cue_type == CueType.LOOP:
                len_ms = float(cue_elem.get("LEN", "0"))
                if len_ms > 0:
                    loop_end = ms_to_seconds(start_ms + len_ms)

            track.cue_points.append(CuePoint(
                position_seconds=ms_to_seconds(start_ms),
                cue_type=cue_type,
                num=num,
                name=cue_elem.get("NAME", ""),
                loop_end_seconds=loop_end,
            ))

        return track, file_path


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class TraktorWriter(BaseWriter):
    def write(self, playlist: Playlist, output_path: str) -> None:
        root = ET.Element("NML", VERSION="23")
        ET.SubElement(root, "HEAD",
                      COMPANY="www.native-instruments.com",
                      PROGRAM="Traktor")

        collection = ET.SubElement(root, "COLLECTION",
                                   ENTRIES=str(len(playlist.tracks)))

        for track in playlist.tracks:
            self._write_entry(collection, track)

        # Playlists section
        playlists_node = ET.SubElement(root, "PLAYLISTS")
        root_node = ET.SubElement(playlists_node, "NODE",
                                  TYPE="FOLDER", NAME="$ROOT",
                                  COUNT="1")
        subnodes = ET.SubElement(root_node, "SUBNODES", COUNT="1")
        pl_node = ET.SubElement(subnodes, "NODE",
                                TYPE="PLAYLIST", NAME=playlist.name)
        pl_elem = ET.SubElement(pl_node, "PLAYLIST",
                                ENTRIES=str(len(playlist.tracks)),
                                TYPE="LIST",
                                UUID="00000000000000000000000000000000")
        for track in playlist.tracks:
            entry_elem = ET.SubElement(pl_elem, "ENTRY")
            key = track.file_path.replace("\\", "/")
            ET.SubElement(entry_elem, "PRIMARYKEY", TYPE="TRACK", KEY=key)

        ET.indent(root, space="  ")
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

    def _write_entry(self, collection: ET.Element, track: Track) -> None:
        attribs: Dict[str, str] = {
            "AUDIO_ID":      _audio_id(track.file_path),
            "TITLE":         track.title,
            "ARTIST":        track.artist,
            "MODIFIED_DATE": "2026/1/1",
            "MODIFIED_TIME": "0",
        }
        entry = ET.SubElement(collection, "ENTRY", **attribs)

        # Location
        volume, encoded_dir, filename = _encode_location(track.file_path)
        loc_attribs: Dict[str, str] = {
            "DIR":      encoded_dir,
            "FILE":     filename,
            "VOLUMEID": volume,
        }
        if volume:
            loc_attribs["VOLUME"] = volume
        ET.SubElement(entry, "LOCATION", **loc_attribs)

        # Album
        ET.SubElement(entry, "ALBUM", TRACK="0", TITLE=track.album)

        # Info
        info_attribs: Dict[str, str] = {
            "BITRATE":  "0",
            "GENRE":    track.genre,
            "COMMENT":  track.comment,
        }
        if track.key:
            info_attribs["KEY"] = track.key
        if track.duration_seconds is not None:
            info_attribs["PLAYTIME"]       = str(int(track.duration_seconds))
            info_attribs["PLAYTIME_FLOAT"] = f"{track.duration_seconds:.3f}"
        ET.SubElement(entry, "INFO", **info_attribs)

        # Tempo
        if track.bpm is not None:
            ET.SubElement(entry, "TEMPO",
                          BPM=f"{track.bpm:.6f}",
                          BPM_QUALITY="100")

        # Beat grid markers (TYPE 4)
        for i, marker in enumerate(track.beat_grid):
            ET.SubElement(entry, "CUE_V2",
                          NAME="",
                          DISPL_ORDER=str(i),
                          TYPE="4",
                          START=f"{seconds_to_ms(marker.position_seconds):.6f}",
                          LEN="0.000000",
                          REPEATS="-1",
                          HOTCUE="-1")

        # Cue points
        for i, cue in enumerate(track.cue_points):
            traktor_type = _CUE_TO_TRAKTOR_TYPE.get(cue.cue_type, 0)
            hotcue_val   = str(cue.num)  # -1 for memory, 0-7 for hot cues

            len_ms = 0.0
            if cue.cue_type == CueType.LOOP and cue.loop_end_seconds is not None:
                len_ms = seconds_to_ms(cue.loop_end_seconds) - seconds_to_ms(cue.position_seconds)

            ET.SubElement(entry, "CUE_V2",
                          NAME=cue.name,
                          DISPL_ORDER=str(i),
                          TYPE=str(traktor_type),
                          START=f"{seconds_to_ms(cue.position_seconds):.6f}",
                          LEN=f"{len_ms:.6f}",
                          REPEATS="-1",
                          HOTCUE=hotcue_val)
