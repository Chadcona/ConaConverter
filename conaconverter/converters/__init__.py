from .rekordbox import RekordboxReader, RekordboxWriter
from .virtualdj import VirtualDjReader, VirtualDjWriter
from .serato import SeratoReader, SeratoWriter
from .engineos import EngineOsReader, EngineOsWriter

READERS = {
    "rekordbox": RekordboxReader(),
    "serato":    SeratoReader(),
    "engineos":  EngineOsReader(),
    "virtualdj": VirtualDjReader(),
}

WRITERS = {
    "rekordbox": RekordboxWriter(),
    "serato":    SeratoWriter(),
    "engineos":  EngineOsWriter(),
    "virtualdj": VirtualDjWriter(),
}

FORMAT_LABELS = {
    "rekordbox": "Rekordbox XML",
    "serato":    "Serato",
    "engineos":  "Engine OS",
    "virtualdj": "VirtualDJ",
}
