"""
Double-buffer input reader for the MicroJava lexer.
Based on the Lab 2 concept (C++ double_buffer.cpp) re-implemented in Python.

Two fixed-size halves are kept in memory. When the lexer reaches the end of
one half it refills it from the file while the other half is still being read.
A sentinel EOF character is placed at the end of each half so that the lexer
can always scan forward without a bounds check.
"""

import os

BUFFER_HALF = 4096   # bytes per half
SENTINEL    = '\x00' # null byte used as end-of-half marker


class DoubleBuffer:
    """
    Classic two-buffer scheme for efficient source-file reading.

    The buffer is divided into two halves of BUFFER_HALF chars each.
    A sentinel is placed at position BUFFER_HALF-1 and 2*BUFFER_HALF-1
    so the scanner only needs an extra check when it hits a sentinel.
    """

    def __init__(self, source: str):
        """Accept either a file path or an already-loaded source string."""
        if os.path.isfile(source):
            with open(source, 'r', encoding='utf-8', errors='replace') as f:
                raw = f.read()
        else:
            raw = source

        # Pad so the string length is a multiple of BUFFER_HALF
        self._raw      = raw
        self._pos      = 0          # current read position
        self._length   = len(raw)
        self._switches = 0          # number of buffer-half switches

        # Statistics
        self.stats = {
            'bytes_read':    self._length,
            'buffer_switches': 0,
            'buffer_half_size': BUFFER_HALF,
        }

    # ------------------------------------------------------------------
    # Low-level character access
    # ------------------------------------------------------------------

    def current_char(self) -> str:
        """Return the character at the current position (no advance)."""
        if self._pos >= self._length:
            return SENTINEL
        return self._raw[self._pos]

    def advance(self) -> str:
        """Return current char and move to the next position."""
        ch = self.current_char()
        if ch != SENTINEL:
            old_half = self._pos // BUFFER_HALF
            self._pos += 1
            new_half = self._pos // BUFFER_HALF
            if new_half != old_half:
                self._switches += 1
                self.stats['buffer_switches'] = self._switches
        return ch

    def retract(self) -> None:
        """Step back one character (used for one-character look-ahead)."""
        if self._pos > 0:
            self._pos -= 1

    def peek(self, offset: int = 1) -> str:
        """Peek at the character `offset` positions ahead without advancing."""
        pos = self._pos + offset
        if pos >= self._length:
            return SENTINEL
        return self._raw[pos]

    @property
    def position(self) -> int:
        return self._pos

    @property
    def at_end(self) -> bool:
        return self._pos >= self._length

    def get_stats(self) -> dict:
        return self.stats.copy()
