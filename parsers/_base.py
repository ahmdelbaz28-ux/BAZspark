"""Shared parser base class with security validation."""

import os
from abc import ABC, abstractmethod
from typing import ClassVar, Set

from parsers._path_security import UnsafePathError, validate_file_size, validate_input_path


class ParserBase(ABC):
    allowed_extensions: ClassVar[Set[str]] = set()
    max_file_size_bytes: ClassVar[int] = 50 * 1024 * 1024

    def validate_input(self, filepath: str) -> str:
        filepath = validate_input_path(
            filepath,
            allowed_extensions=frozenset(self.allowed_extensions) if self.allowed_extensions else None,
            parser_name=type(self).__name__,
        )
        ext = os.path.splitext(filepath)[1].lower()
        if self.allowed_extensions and ext not in self.allowed_extensions:
            raise UnsafePathError(
                f"{type(self).__name__}: unsupported file extension '{ext}'. "
                f"Allowed: {', '.join(sorted(self.allowed_extensions))}"
            )
        validate_file_size(
            filepath,
            max_size_bytes=self.max_file_size_bytes,
            parser_name=type(self).__name__,
        )
        return filepath

    @abstractmethod
    def parse(self, filepath: str, **kwargs):
        ...
