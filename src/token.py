from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any


class TokenType(Enum):
    # Keywords
    PROGRAM   = 'program'
    CLASS     = 'class'
    IF        = 'if'
    ELSE      = 'else'
    WHILE     = 'while'
    READ      = 'read'
    PRINT     = 'print'
    RETURN    = 'return'
    VOID      = 'void'
    FINAL     = 'final'
    NEW       = 'new'

    # Predeclared type names (treated as keywords in lexer)
    INT       = 'int'
    CHAR      = 'char'

    # Literals
    NUMBER    = 'NUMBER'
    CHAR_CONST = 'CHAR_CONST'
    IDENT     = 'IDENT'

    # Arithmetic operators
    PLUS      = '+'
    MINUS     = '-'
    TIMES     = '*'
    DIV       = '/'
    MOD       = '%'

    # Relational operators
    EQ        = '=='
    NE        = '!='
    LT        = '<'
    LE        = '<='
    GT        = '>'
    GE        = '>='

    # Assignment
    ASSIGN    = '='

    # Delimiters
    LPAREN    = '('
    RPAREN    = ')'
    LBRACK    = '['
    RBRACK    = ']'
    LBRACE    = '{'
    RBRACE    = '}'
    SEMICOLON = ';'
    COMMA     = ','
    DOT       = '.'

    # Special
    EOF       = 'EOF'
    ERROR     = 'ERROR'


# All MicroJava keywords mapped to their TokenType
KEYWORDS: dict[str, TokenType] = {
    'program': TokenType.PROGRAM,
    'class':   TokenType.CLASS,
    'if':      TokenType.IF,
    'else':    TokenType.ELSE,
    'while':   TokenType.WHILE,
    'read':    TokenType.READ,
    'print':   TokenType.PRINT,
    'return':  TokenType.RETURN,
    'void':    TokenType.VOID,
    'final':   TokenType.FINAL,
    'new':     TokenType.NEW,
    'int':     TokenType.INT,
    'char':    TokenType.CHAR,
}

# Single-character operators/punctuation
SINGLE_CHAR_TOKENS: dict[str, TokenType] = {
    '+': TokenType.PLUS,
    '-': TokenType.MINUS,
    '*': TokenType.TIMES,
    '/': TokenType.DIV,
    '%': TokenType.MOD,
    '<': TokenType.LT,
    '>': TokenType.GT,
    '=': TokenType.ASSIGN,
    '(': TokenType.LPAREN,
    ')': TokenType.RPAREN,
    '[': TokenType.LBRACK,
    ']': TokenType.RBRACK,
    '{': TokenType.LBRACE,
    '}': TokenType.RBRACE,
    ';': TokenType.SEMICOLON,
    ',': TokenType.COMMA,
    '.': TokenType.DOT,
}

# Two-character operators that start with = ! < >
TWO_CHAR_TOKENS: dict[str, TokenType] = {
    '==': TokenType.EQ,
    '!=': TokenType.NE,
    '<=': TokenType.LE,
    '>=': TokenType.GE,
}


@dataclass
class Token:
    type:    TokenType
    value:   str
    line:    int
    column:  int
    literal: Any = field(default=None, compare=False)

    def __str__(self):
        return (f"Token({self.type.name:<12} | {self.value!r:<20} | "
                f"L{self.line}:C{self.column})")

    def __repr__(self):
        return self.__str__()

    @property
    def is_keyword(self):
        return self.type in (
            TokenType.PROGRAM, TokenType.CLASS, TokenType.IF,
            TokenType.ELSE, TokenType.WHILE, TokenType.READ,
            TokenType.PRINT, TokenType.RETURN, TokenType.VOID,
            TokenType.FINAL, TokenType.NEW, TokenType.INT, TokenType.CHAR,
        )

    @property
    def is_type_name(self):
        return self.type in (TokenType.INT, TokenType.CHAR, TokenType.IDENT)

    @property
    def is_relop(self):
        return self.type in (
            TokenType.EQ, TokenType.NE,
            TokenType.LT, TokenType.LE,
            TokenType.GT, TokenType.GE,
        )

    @property
    def is_addop(self):
        return self.type in (TokenType.PLUS, TokenType.MINUS)

    @property
    def is_mulop(self):
        return self.type in (TokenType.TIMES, TokenType.DIV, TokenType.MOD)
