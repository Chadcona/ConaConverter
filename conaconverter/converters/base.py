from abc import ABC, abstractmethod

from conaconverter.models import Playlist


class BaseReader(ABC):
    @abstractmethod
    def read(self, path: str) -> Playlist:
        """Read the file/folder at *path* and return a universal Playlist."""
        ...


class BaseWriter(ABC):
    @abstractmethod
    def write(self, playlist: Playlist, output_path: str) -> None:
        """Write *playlist* to the file/folder at *output_path*."""
        ...
