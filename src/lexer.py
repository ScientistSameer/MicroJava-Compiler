"""
MicroJava Lexical Analyzer
--------------------------
Reads source characters through a DoubleBuffer, produces a stream of Tokens.

Tokens recognized (per MicroJava spec, Lab 3 / Lab 5):
  Keywords : program class if else while read print return void final new int char
  Identifiers : letter {letter | digit}
  Numbers     : digit {digit}
  CharConsts  : ' char '  (including escape sequences \\n \\t \\r)
  Operators   : + - * / %  == != < <= > >=  =
  Delimiters  : ( ) [ ] { } ; , .
  Comments    : // …end-of-line
"""

from __future__ import annotations
from typing import List, Optional

from .double_buffer import DoubleBuffer, SENTINEL
from .token import Token, TokenType, KEYWORDS, SINGLE_CHAR_TOKENS, TWO_CHAR_TOKENS


class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int):
        super().__init__(message)
        self.line   = line
        self.column = column


class Lexer:
    def __init__(self, source: str, recover: bool = True):
        """
        source  : file path or raw source string
        recover : if True, on lexical error emit an ERROR token and continue;
                  if False, raise LexerError immediately.
        """
        self._buf     = DoubleBuffer(source)
        self._recover = recover
        self._line    = 1
        self._col     = 1
        self._tokens: List[Token] = []
        self._errors: List[Token] = []

        # Cache of all tokens (filled lazily or on demand)
        self._all_tokens: Optional[List[Token]] = None
        self._token_pos  = 0   # index into _all_tokens for get_all_tokens()

    # ------------------------------------------------------------------
    # Public interface used by parsers
    # ------------------------------------------------------------------

    def next_token(self) -> Token:
        """Return the next token from the source stream (skip comments)."""
        while True:
            tok = self._scan_one()
            if tok.type == TokenType.ERROR:
                self._errors.append(tok)
                if not self._recover:
                    raise LexerError(
                        f"Unexpected character {tok.value!r}",
                        tok.line, tok.column
                    )
            return tok

    def tokenize(self) -> List[Token]:
        """Tokenize the entire source; returns all tokens including EOF."""
        if self._all_tokens is not None:
            return self._all_tokens
        tokens = []
        while True:
            tok = self.next_token()
            tokens.append(tok)
            if tok.type == TokenType.EOF:
                break
        self._all_tokens = tokens
        return tokens

    def get_errors(self) -> List[Token]:
        return list(self._errors)

    def get_stats(self) -> dict:
        return self._buf.get_stats()

    # ------------------------------------------------------------------
    # Character-level helpers
    # ------------------------------------------------------------------

    def _ch(self) -> str:
        """Peek at current character."""
        return self._buf.current_char()

    def _adv(self) -> str:
        """Advance and return the consumed character; update line/col."""
        ch = self._buf.advance()
        if ch == '\n':
            self._line += 1
            self._col   = 1
        elif ch != SENTINEL:
            self._col += 1
        return ch

    def _ret(self):
        """Retract one character."""
        self._buf.retract()
        self._col = max(1, self._col - 1)

    def _peek_next(self) -> str:
        return self._buf.peek(1)

    # ------------------------------------------------------------------
    # Main scanning routine
    # ------------------------------------------------------------------

    def _scan_one(self) -> Token:
        # Skip whitespace
        while self._ch() in (' ', '\t', '\r', '\n'):
            self._adv()

        if self._buf.at_end:
            return Token(TokenType.EOF, '$', self._line, self._col)

        start_line = self._line
        start_col  = self._col
        ch         = self._ch()

        # --- Identifier or keyword ---
        if ch.isalpha():
            return self._scan_ident(start_line, start_col)

        # --- Number ---
        if ch.isdigit():
            return self._scan_number(start_line, start_col)

        # --- Character constant ---
        if ch == "'":
            return self._scan_char_const(start_line, start_col)

        # --- Comment or division ---
        if ch == '/':
            self._adv()
            nxt = self._ch()
            if nxt == '/':
                return self._scan_line_comment(start_line, start_col)
            # Not a comment — it's the division operator
            return Token(TokenType.DIV, '/', start_line, start_col)

        # --- Two-character operators first ---
        if ch in ('=', '!', '<', '>'):
            self._adv()
            two = ch + self._ch()
            if two in TWO_CHAR_TOKENS:
                self._adv()
                return Token(TWO_CHAR_TOKENS[two], two, start_line, start_col)
            # Single-char fallback
            if ch in SINGLE_CHAR_TOKENS:
                return Token(SINGLE_CHAR_TOKENS[ch], ch, start_line, start_col)
            return Token(TokenType.ERROR, ch, start_line, start_col)

        # --- Single-character tokens ---
        if ch in SINGLE_CHAR_TOKENS:
            self._adv()
            return Token(SINGLE_CHAR_TOKENS[ch], ch, start_line, start_col)

        # --- Unknown character ---
        self._adv()
        tok = Token(TokenType.ERROR, ch, start_line, start_col)
        return tok

    # ------------------------------------------------------------------
    # Sub-scanners
    # ------------------------------------------------------------------

    def _scan_ident(self, line: int, col: int) -> Token:
        lexeme = ''
        while self._ch().isalpha() or self._ch().isdigit() or self._ch() == '_':
            lexeme += self._adv()
        tt = KEYWORDS.get(lexeme, TokenType.IDENT)
        return Token(tt, lexeme, line, col)

    def _scan_number(self, line: int, col: int) -> Token:
        lexeme = ''
        while self._ch().isdigit():
            lexeme += self._adv()
        return Token(TokenType.NUMBER, lexeme, line, col, int(lexeme))

    def _scan_char_const(self, line: int, col: int) -> Token:
        """Scan ' char ' where char may be an escape sequence."""
        self._adv()   # consume opening '
        lexeme = "'"
        if self._ch() == '\\':
            self._adv()
            esc = self._adv()
            escape_map = {'n': '\n', 't': '\t', 'r': '\r',
                          "'": "'", '\\': '\\'}
            if esc in escape_map:
                ch_val = escape_map[esc]
                lexeme += '\\' + esc
            else:
                lexeme += '\\' + esc
                ch_val = esc
        elif self._ch() not in ('', '\n', SENTINEL):
            ch_val = self._adv()
            lexeme += ch_val
        else:
            return Token(TokenType.ERROR, "'", line, col)

        if self._ch() != "'":
            return Token(TokenType.ERROR, lexeme, line, col)
        self._adv()   # consume closing '
        lexeme += "'"
        return Token(TokenType.CHAR_CONST, lexeme, line, col, ch_val)

    def _scan_line_comment(self, line: int, col: int) -> Token:
        """Consume // comment and skip it, then return next real token."""
        while self._ch() not in ('\n', SENTINEL):
            self._adv()
        # Recursively get the next token (comment is skipped)
        return self._scan_one()

    # ------------------------------------------------------------------
    # Pretty printing
    # ------------------------------------------------------------------

    def print_tokens(self):
        tokens = self.tokenize()
        header = f"\n{'Line':>5}  {'Col':>4}  {'Type':<14}  {'Lexeme'}"
        print(header)
        print('-' * 60)
        for tok in tokens:
            if tok.type == TokenType.EOF:
                continue
            print(f"{tok.line:>5}  {tok.column:>4}  {tok.type.name:<14}  {tok.value!r}")
        print('-' * 60)
        errors = self.get_errors()
        print(f"Total tokens : {len(tokens) - 1}")
        print(f"Lexical errors: {len(errors)}")
        if errors:
            print("Errors:")
            for e in errors:
                print(f"  L{e.line}:C{e.column} — unexpected {e.value!r}")
