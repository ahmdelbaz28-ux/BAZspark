"""Shared parser base class with security validation."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, TypeVar

from parsers._path_security import UnsafePathError, validate_file_size, validate_input_path

T = TypeVar('T')


@dataclass
class ParseResult[T]:
    """Generic parse result with typed data payload.

    T is the parser-specific data type (e.g., list[ParsedRoom], BuildingModel).
    Common metadata (source_file, success, errors, warnings) is lifted out
    of individual result types.

    Usage:
        def parse(self, path: str) -> ParseResult[list[ParsedRoom]]:
            data = parse_internal(path)
            return ParseResult(source_file=path, success=True, data=data)
    """

    source_file: str
    success: bool
    data: T
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ParserBase(ABC):
    allowed_extensions: ClassVar[set[str]] = set()
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
    def parse(self, filepath: str, **kwargs) -> ParseResult[Any]:
        ...
