"""
Error Handler — collects, reports, and recovers from compile-time errors.

Supports:
  - Lexical errors   (from the Lexer)
  - Syntactic errors (from any parser)
  - Semantic errors  (from the type checker)

Recovery strategies:
  - Panic-mode recovery: skip tokens until a synchronisation token is found
  - Phrase-level recovery: replace / insert a token (best-effort)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ErrorKind(Enum):
    LEXICAL   = 'Lexical'
    SYNTACTIC = 'Syntactic'
    SEMANTIC  = 'Semantic'
    WARNING   = 'Warning'


@dataclass
class CompileError:
    kind:    ErrorKind
    message: str
    line:    int
    column:  int
    hint:    Optional[str] = None

    def __str__(self):
        loc  = f'L{self.line}:C{self.column}'
        hint = f'\n        hint: {self.hint}' if self.hint else ''
        return f'[{self.kind.value}] {loc}  {self.message}{hint}'

    def to_dict(self):
        return {
            'kind':    self.kind.value,
            'message': self.message,
            'line':    self.line,
            'column':  self.column,
            'hint':    self.hint,
        }


class ErrorHandler:
    def __init__(self):
        self._errors:   List[CompileError] = []
        self._warnings: List[CompileError] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def lexical(self, msg: str, line: int, col: int, hint: str = None):
        self._errors.append(CompileError(ErrorKind.LEXICAL, msg, line, col, hint))

    def syntactic(self, msg: str, line: int, col: int, hint: str = None):
        self._errors.append(CompileError(ErrorKind.SYNTACTIC, msg, line, col, hint))

    def semantic(self, msg: str, line: int, col: int, hint: str = None):
        self._errors.append(CompileError(ErrorKind.SEMANTIC, msg, line, col, hint))

    def warning(self, msg: str, line: int, col: int, hint: str = None):
        self._warnings.append(CompileError(ErrorKind.WARNING, msg, line, col, hint))

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    @property
    def has_errors(self) -> bool:
        return bool(self._errors)

    @property
    def error_count(self) -> int:
        return len(self._errors)

    @property
    def warning_count(self) -> int:
        return len(self._warnings)

    def all_errors(self) -> List[CompileError]:
        return list(self._errors)

    def all_warnings(self) -> List[CompileError]:
        return list(self._warnings)

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def report(self) -> str:
        lines = []
        for e in sorted(self._errors + self._warnings,
                        key=lambda x: (x.line, x.column)):
            lines.append(str(e))
        lines.append('')
        lines.append(f'Total errors: {self.error_count}  '
                     f'warnings: {self.warning_count}')
        return '\n'.join(lines)

    def to_list(self) -> List[dict]:
        return [e.to_dict() for e in self._errors + self._warnings]

    # ------------------------------------------------------------------
    # Panic-mode recovery helpers
    # ------------------------------------------------------------------

    @staticmethod
    def skip_to(tokens, pos: int, sync_set: set) -> int:
        """
        Advance pos past tokens until one in sync_set is found.
        Returns the new position (pointing at the sync token or EOF).
        """
        from .token import TokenType
        while pos < len(tokens):
            if tokens[pos].type in sync_set or tokens[pos].type == TokenType.EOF:
                break
            pos += 1
        return pos

    @staticmethod
    def phrase_replace(tokens, pos: int, expected_type, handler: 'ErrorHandler') -> int:
        """
        Phrase-level recovery: if the token at pos+1 matches expected_type,
        report the current token as erroneous and skip it (insert recovery).
        Returns the new pos if recovery was possible, else the original pos.
        """
        if pos + 1 < len(tokens) and tokens[pos + 1].type == expected_type:
            tok = tokens[pos]
            handler.syntactic(
                f'Phrase-level recovery: skipping unexpected {tok.type.name} '
                f'{tok.value!r}',
                tok.line, tok.column,
                hint=f'Expected {expected_type.name} before {tok.value!r}'
            )
            return pos + 1
        return pos
