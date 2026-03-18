from .rekordbox import RekordboxReader, RekordboxWriter
from .virtualdj import VirtualDjReader, VirtualDjWriter
from .serato import SeratoReader, SeratoWriter
from .engineos import EngineOsReader, EngineOsWriter
from .traktor import TraktorReader, TraktorWriter

READERS = {
    "rekordbox": RekordboxReader(),
    "serato":    SeratoReader(),
    "engineos":  EngineOsReader(),
    "virtualdj": VirtualDjReader(),
    "traktor":   TraktorReader(),
}

WRITERS = {
    "rekordbox": RekordboxWriter(),
    "serato":    SeratoWriter(),
    "engineos":  EngineOsWriter(),
    "virtualdj": VirtualDjWriter(),
    "traktor":   TraktorWriter(),
}

FORMAT_LABELS = {
    "rekordbox": "Rekordbox XML",
    "serato":    "Serato",
    "engineos":  "Engine OS",
    "virtualdj": "VirtualDJ",
    "traktor":   "Traktor NML",
}
