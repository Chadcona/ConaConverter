"""VirtualDJ database.xml ↔ universal Playlist converter.

VirtualDJ XML structure:
  <VirtualDJ_Database Version="8.5">
    <Song FilePath="C:\\Music\\track.mp3" FileSize="12345678">
      <Tags Author="Artist" Title="Title" Genre="Electronic"/>
      <Infos SongLength="240.5" Bitrate="320"/>
      <Scan Version="801" Bpm="0.468750" Volume="0.8" Key="8m"/>
      <Poi Pos="-0.002" Type="beatgrid" Name=""/>
      <Poi Pos="4.123" Type="cue" Num="0" Name="Intro" Color="#28E214"/>
      <Poi Pos="16.000" Type="loop" Num="0" Name="" Size="16"/>
    </Song>
  </VirtualDJ_Database>

IMPORTANT: Scan/@Bpm is seconds-per-beat (NOT BPM).
  BPM = 60.0 / Scan_Bpm_value
  Scan_Bpm_value = 60.0 / BPM
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import List, Optional

from conaconverter.converters.base import BaseReader, BaseWriter
from conaconverter.models import (
    BeatGridMarker,
    CuePoint,
    CueType,
    Playlist,
    Track,
)

_VDJ_TYPE_TO_CUE = {
    "cue":      CueType.HOT_CUE,
    "automix":  CueType.MEMORY,
    "loop":     CueType.LOOP,
    "fade":     CueType.FADE_IN,   # refined to FADE_OUT via Point attr on read
}

_CUE_TO_VDJ_TYPE = {
    CueType.HOT_CUE:  "cue",
    CueType.MEMORY:   "automix",
    CueType.LOOP:     "loop",
    CueType.FADE_IN:  "fade",
    CueType.FADE_OUT: "fade",
}

# VirtualDJ uses the Point attribute to distinguish fade direction
_FADE_OUT_POINTS = {"fadeEnd", "fadeOut", "cutEnd", "realEnd"}


def _parse_vdj_color(color_str: Optional[str]) -> Optional[int]:
    if not color_str or not color_str.startswith("#"):
        return None
    try:
        return int(color_str[1:], 16)
    except ValueError:
        return None


def _format_vdj_color(rgb: int) -> str:
    return f"#{rgb:06X}"


class VirtualDjReader(BaseReader):
    def read(self, path: str) -> Playlist:
        tree = ET.parse(path)
        root = tree.getroot()

        if root.tag != "VirtualDJ_Database":
            raise ValueError(f"Not a VirtualDJ database file: root tag is <{root.tag}>")

        playlist_name = os.path.splitext(os.path.basename(path))[0]
        tracks: List[Track] = []

        for song in root.findall("Song"):
            track = self._parse_song(song)
            tracks.append(track)

        return Playlist(name=playlist_name, tracks=tracks)

    def _parse_song(self, song: ET.Element) -> Track:
        file_path = song.get("FilePath", "")

        track = Track(file_path=file_path)

        tags = song.find("Tags")
        if tags is not None:
            track.artist = tags.get("Author", "")
            track.title = tags.get("Title", "")
            track.genre = tags.get("Genre", "")
            track.album = tags.get("Album", "")
            track.comment = tags.get("Comment", "")

        infos = song.find("Infos")
        if infos is not None:
            length = infos.get("SongLength")
            if length:
                track.duration_seconds = float(length)

        scan = song.find("Scan")
        if scan is not None:
            bpm_spb = scan.get("Bpm")  # seconds-per-beat
            if bpm_spb:
                spb = float(bpm_spb)
                if spb > 0:
                    track.bpm = 60.0 / spb
            track.key = scan.get("Key")

        for poi in song.findall("Poi"):
            poi_type = poi.get("Type", "")
            pos_str = poi.get("Pos")
            if pos_str is None:
                continue
            pos = float(pos_str)

            if poi_type == "beatgrid":
                # The beatgrid Poi marks beat 1; BPM comes from Scan
                if track.bpm is not None and track.bpm > 0:
                    track.beat_grid.append(BeatGridMarker(
                        position_seconds=pos,
                        bpm=track.bpm,
                    ))
                continue

            cue_type = _VDJ_TYPE_TO_CUE.get(poi_type, CueType.HOT_CUE)

            # Distinguish fade-in from fade-out via Point attribute
            if cue_type == CueType.FADE_IN:
                point = poi.get("Point", "")
                if point in _FADE_OUT_POINTS:
                    cue_type = CueType.FADE_OUT

            num_str = poi.get("Num", "0")
            try:
                num = int(num_str)
            except (ValueError, TypeError):
                num = 0

            loop_end: Optional[float] = None
            if cue_type == CueType.LOOP:
                size_str = poi.get("Size")
                if size_str:
                    loop_end = pos + float(size_str)

            track.cue_points.append(CuePoint(
                position_seconds=pos,
                cue_type=cue_type,
                num=num,
                name=poi.get("Name", ""),
                color_rgb=_parse_vdj_color(poi.get("Color")),
                loop_end_seconds=loop_end,
            ))

        return track


class VirtualDjWriter(BaseWriter):
    def write(self, playlist: Playlist, output_path: str) -> None:
        root = ET.Element("VirtualDJ_Database", Version="8.5")

        for track in playlist.tracks:
            song = ET.SubElement(root, "Song",
                                 FilePath=track.file_path,
                                 FileSize="0")
            self._write_song(song, track)

        ET.indent(root, space="  ")
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

    def _write_song(self, song: ET.Element, track: Track) -> None:
        # Tags
        tags_attribs = {}
        if track.artist:
            tags_attribs["Author"] = track.artist
        if track.title:
            tags_attribs["Title"] = track.title
        if track.genre:
            tags_attribs["Genre"] = track.genre
        if track.album:
            tags_attribs["Album"] = track.album
        if track.comment:
            tags_attribs["Comment"] = track.comment
        ET.SubElement(song, "Tags", **tags_attribs)

        # Infos
        infos_attribs: dict = {}
        if track.duration_seconds is not None:
            infos_attribs["SongLength"] = f"{track.duration_seconds:.3f}"
        ET.SubElement(song, "Infos", **infos_attribs)

        # Scan — BPM stored as seconds-per-beat
        scan_attribs: dict = {}
        if track.bpm is not None and track.bpm > 0:
            scan_attribs["Bpm"] = f"{60.0 / track.bpm:.6f}"
        if track.key:
            scan_attribs["Key"] = track.key
        ET.SubElement(song, "Scan", **scan_attribs)

        # Beatgrid Poi
        for marker in track.beat_grid:
            ET.SubElement(song, "Poi",
                          Pos=f"{marker.position_seconds:.3f}",
                          Type="beatgrid",
                          Name="")

        # Cue Poi
        for cue in track.cue_points:
            vdj_type = _CUE_TO_VDJ_TYPE.get(cue.cue_type, "cue")
            attribs = {
                "Pos": f"{cue.position_seconds:.3f}",
                "Type": vdj_type,
                "Num": str(cue.num),
                "Name": cue.name,
            }
            if cue.color_rgb is not None:
                attribs["Color"] = _format_vdj_color(cue.color_rgb)
            if cue.cue_type == CueType.FADE_IN:
                attribs["Point"] = "fadeStart"
            elif cue.cue_type == CueType.FADE_OUT:
                attribs["Point"] = "fadeEnd"
            if cue.cue_type == CueType.LOOP and cue.loop_end_seconds is not None:
                size = cue.loop_end_seconds - cue.position_seconds
                attribs["Size"] = f"{size:.3f}"
            ET.SubElement(song, "Poi", **attribs)
