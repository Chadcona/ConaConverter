"""Auto-detects the DJ software format from a file or folder path."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET


def detect_format(path: str) -> str:
    """Return the format key for the file/folder at *path*.

    Returns one of: 'serato', 'engineos', 'virtualdj', 'rekordbox', 'traktor'

    Raises ValueError if the format cannot be determined.
    """
    # Serato drag-and-drop or SQLite URI
    if path.startswith("assetlist://") or path.startswith("serato-sqlite://"):
        return "serato"

    name = os.path.basename(path)

    # Serato: .crate files, location.sqlite, or the 'database V2' file
    if path.endswith(".crate"):
        return "serato"
    if path.endswith("location.sqlite"):
        return "serato"
    if name == "database V2":
        return "serato"

    # Engine OS: folder containing m.db, or a .db file
    if os.path.isdir(path):
        if os.path.exists(os.path.join(path, "m.db")):
            return "engineos"

    if path.endswith(".db"):
        return "engineos"

    # Traktor: .nml extension
    if path.endswith(".nml"):
        try:
            root_tag = _read_xml_root_tag(path)
        except (ET.ParseError, OSError) as exc:
            raise ValueError(f"Cannot parse NML file: {path}") from exc
        if root_tag == "NML":
            return "traktor"
        raise ValueError(f"Not a Traktor NML file: root tag is <{root_tag}>")

    # XML-based formats: inspect the root element tag
    if path.endswith(".xml"):
        try:
            root_tag = _read_xml_root_tag(path)
        except (ET.ParseError, OSError) as exc:
            raise ValueError(f"Cannot parse XML file: {path}") from exc

        if root_tag == "VirtualDJ_Database":
            return "virtualdj"
        if root_tag == "DJ_PLAYLISTS":
            return "rekordbox"

        raise ValueError(
            f"Unrecognised XML format (root tag <{root_tag}>). "
            "Expected <DJ_PLAYLISTS> for Rekordbox or <VirtualDJ_Database> for VirtualDJ."
        )

    raise ValueError(
        f"Cannot determine format for: {path!r}\n"
        "Supported files: .crate (Serato), rekordbox.xml, database.xml (VirtualDJ), "
        ".db or Engine Library folder (Engine OS), collection.nml (Traktor)."
    )


def _read_xml_root_tag(path: str) -> str:
    """Return the root element tag of an XML file without parsing the whole file."""
    for _, elem in ET.iterparse(path, events=("start",)):
        return elem.tag
    return ""
