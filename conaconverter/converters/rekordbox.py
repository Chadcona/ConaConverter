"""Rekordbox XML ↔ universal Playlist converter.

Uses xml.etree.ElementTree directly against the Pioneer Rekordbox XML schema
(documented in rekordbox XML format list PDF).

Rekordbox XML structure:
  <DJ_PLAYLISTS Version="1.0.0">
    <PRODUCT Name="rekordbox" Version="6.x" Company="Pioneer DJ"/>
    <COLLECTION Entries="N">
      <TRACK TrackID="1" Name="..." Artist="..." Album="..." Genre="..."
             TotalTime="240" AverageBpm="128.00" Tonality="8m"
             Location="file://localhost/C:/Music/track.mp3" ...>
        <POSITION_MARK Name="" Type="0" Start="4.123" Num="0"
                       Red="40" Green="226" Blue="20"/>
        <TEMPO Inizio="0.150" Bpm="128.00" Metro="4/4" Battito="1"/>
      </TRACK>
    </COLLECTION>
    <PLAYLISTS>
      <NODE Type="0" Name="ROOT">
        <NODE Name="My Playlist" Type="1" KeyType="0" Entries="2">
          <TRACK Key="1"/>
          <TRACK Key="2"/>
        </NODE>
      </NODE>
    </PLAYLISTS>
  </DJ_PLAYLISTS>

POSITION_MARK Type values:
  0 = cue, 1 = fade-in, 2 = fade-out, 3 = load, 4 = loop
POSITION_MARK Num values:
  -1 = memory cue, 0-8 = hot cue slot
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from conaconverter.converters.base import BaseReader, BaseWriter
from conaconverter.models import (
    BeatGridMarker,
    CuePoint,
    CueType,
    Playlist,
    Track,
)

# Map Rekordbox POSITION_MARK Type integers to CueType
_RB_TYPE_TO_CUE: Dict[int, CueType] = {
    0: CueType.HOT_CUE,
    1: CueType.FADE_IN,
    2: CueType.FADE_OUT,
    3: CueType.MEMORY,   # "load" marker treated as memory cue
    4: CueType.LOOP,
}

_CUE_TO_RB_TYPE: Dict[CueType, int] = {
    CueType.HOT_CUE:  0,
    CueType.FADE_IN:  1,
    CueType.FADE_OUT: 2,
    CueType.MEMORY:   0,  # write memory cues as type 0 with Num=-1
    CueType.LOOP:     4,
}


def _parse_color(r: Optional[str], g: Optional[str], b: Optional[str]) -> Optional[int]:
    if r is None or g is None or b is None:
        return None
    return (int(r) << 16) | (int(g) << 8) | int(b)


def _split_color(rgb: int):
    return (rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF


class RekordboxReader(BaseReader):
    def read(self, path: str) -> Playlist:
        tree = ET.parse(path)
        root = tree.getroot()

        if root.tag != "DJ_PLAYLISTS":
            raise ValueError(f"Not a Rekordbox XML file: root tag is <{root.tag}>")

        # Build a map of TrackID → Track
        track_map: Dict[str, Track] = {}
        collection = root.find("COLLECTION")
        if collection is not None:
            for elem in collection.findall("TRACK"):
                track = self._parse_track(elem)
                track_id = elem.get("TrackID", "")
                track_map[track_id] = track

        # Find the first non-root playlist node and collect its tracks
        playlists_node = root.find("PLAYLISTS")
        playlist_name = os.path.splitext(os.path.basename(path))[0]
        tracks: List[Track] = []

        if playlists_node is not None:
            # Walk to first TYPE=1 (track list) node
            for node in playlists_node.iter("NODE"):
                if node.get("Type") == "1":
                    playlist_name = node.get("Name", playlist_name)
                    for t in node.findall("TRACK"):
                        key = t.get("Key", "")
                        if key in track_map:
                            tracks.append(track_map[key])
                    break  # only first playlist in MVP

        # Fallback: if no playlist nodes, return all tracks in collection order
        if not tracks and track_map:
            tracks = list(track_map.values())

        return Playlist(name=playlist_name, tracks=tracks)

    def _parse_track(self, elem: ET.Element) -> Track:
        location = elem.get("Location", "")
        # Rekordbox stores paths as file://localhost/... or file:///...
        if location.startswith("file://localhost"):
            location = location[len("file://localhost"):]
        elif location.startswith("file:///"):
            location = location[len("file:///"):]
        # URL-decode basic percent encoding
        location = location.replace("%20", " ")

        bpm_str = elem.get("AverageBpm")
        total_time_str = elem.get("TotalTime")

        track = Track(
            file_path=location,
            title=elem.get("Name", ""),
            artist=elem.get("Artist", ""),
            album=elem.get("Album", ""),
            genre=elem.get("Genre", ""),
            comment=elem.get("Comments", ""),
            bpm=float(bpm_str) if bpm_str else None,
            key=elem.get("Tonality"),
            duration_seconds=float(total_time_str) if total_time_str else None,
        )

        # Parse cue points
        for mark in elem.findall("POSITION_MARK"):
            rb_type = int(mark.get("Type", "0"))
            cue_type = _RB_TYPE_TO_CUE.get(rb_type, CueType.HOT_CUE)
            num = int(mark.get("Num", "0"))
            # Num=-1 in Rekordbox = memory cue
            if num == -1:
                cue_type = CueType.MEMORY

            start = mark.get("Start")
            if start is None:
                continue

            loop_end = mark.get("End")
            color = _parse_color(mark.get("Red"), mark.get("Green"), mark.get("Blue"))

            track.cue_points.append(CuePoint(
                position_seconds=float(start),
                cue_type=cue_type,
                num=num,
                name=mark.get("Name", ""),
                color_rgb=color,
                loop_end_seconds=float(loop_end) if loop_end else None,
            ))

        # Parse beat grid (TEMPO elements)
        for tempo in elem.findall("TEMPO"):
            inizio = tempo.get("Inizio")
            bpm = tempo.get("Bpm")
            if inizio and bpm:
                track.beat_grid.append(BeatGridMarker(
                    position_seconds=float(inizio),
                    bpm=float(bpm),
                ))

        return track


class RekordboxWriter(BaseWriter):
    def write(self, playlist: Playlist, output_path: str) -> None:
        root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
        ET.SubElement(root, "PRODUCT",
                      Name="rekordbox", Version="6.0.0", Company="Pioneer DJ")

        collection = ET.SubElement(root, "COLLECTION",
                                   Entries=str(len(playlist.tracks)))

        # Write each track and keep a list of generated IDs
        track_ids: List[str] = []
        for i, track in enumerate(playlist.tracks, start=1):
            track_id = str(i)
            track_ids.append(track_id)
            self._write_track(collection, track, track_id)

        # Write PLAYLISTS section
        playlists_node = ET.SubElement(root, "PLAYLISTS")
        root_node = ET.SubElement(playlists_node, "NODE",
                                  Type="0", Name="ROOT", Count="1")
        playlist_node = ET.SubElement(root_node, "NODE",
                                      Name=playlist.name,
                                      Type="1",
                                      KeyType="0",
                                      Entries=str(len(track_ids)))
        for tid in track_ids:
            ET.SubElement(playlist_node, "TRACK", Key=tid)

        # Pretty-print
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

    def _write_track(self, collection: ET.Element, track: Track, track_id: str) -> None:
        # Build file:// URL for Location
        path = track.file_path.replace("\\", "/")
        if not path.startswith("/"):
            path = "/" + path
        location = "file://localhost" + path.replace(" ", "%20")

        attribs = {
            "TrackID": track_id,
            "Name": track.title,
            "Artist": track.artist,
            "Album": track.album,
            "Genre": track.genre,
            "Comments": track.comment,
            "Location": location,
        }
        if track.bpm is not None:
            attribs["AverageBpm"] = f"{track.bpm:.2f}"
        if track.duration_seconds is not None:
            attribs["TotalTime"] = str(int(track.duration_seconds))
        if track.key is not None:
            attribs["Tonality"] = track.key

        elem = ET.SubElement(collection, "TRACK", **attribs)

        # Write cue points
        for cue in track.cue_points:
            rb_type = _CUE_TO_RB_TYPE.get(cue.cue_type, 0)
            mark_attribs = {
                "Name": cue.name,
                "Type": str(rb_type),
                "Start": f"{cue.position_seconds:.3f}",
                "Num": str(cue.num),
            }
            if cue.loop_end_seconds is not None:
                mark_attribs["End"] = f"{cue.loop_end_seconds:.3f}"
            if cue.color_rgb is not None:
                r, g, b = _split_color(cue.color_rgb)
                mark_attribs["Red"] = str(r)
                mark_attribs["Green"] = str(g)
                mark_attribs["Blue"] = str(b)
            ET.SubElement(elem, "POSITION_MARK", **mark_attribs)

        # Write beat grid
        for marker in track.beat_grid:
            ET.SubElement(elem, "TEMPO",
                          Inizio=f"{marker.position_seconds:.3f}",
                          Bpm=f"{marker.bpm:.2f}",
                          Metro="4/4",
                          Battito="1")
