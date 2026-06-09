"""
Symbol Table Manager for MicroJava (Lab 7 extended).

Uses a hash-based table (Python dict) for O(1) lookup within each scope.
Scopes are managed as a stack of dicts (linked scope chain).

Each entry stores:
  name, kind, type, scope_level, line, column, extra info

Supports: insert, lookup (with scope chain traversal), delete, dump.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class SymbolKind(Enum):
    CONST   = 'const'
    VAR     = 'var'
    PARAM   = 'param'
    METHOD  = 'method'
    CLASS   = 'class'
    ARRAY   = 'array'
    BUILTIN = 'builtin'


@dataclass
class Symbol:
    name:        str
    kind:        SymbolKind
    type_name:   str
    scope_level: int
    line:        int
    column:      int
    value:       Any = None          # for constants
    param_types: List[str] = field(default_factory=list)  # for methods
    is_array:    bool = False        # for array vars

    def __str__(self):
        extra = ''
        if self.kind == SymbolKind.CONST:
            extra = f' = {self.value!r}'
        elif self.kind == SymbolKind.METHOD:
            extra = f'({", ".join(self.param_types)}) -> {self.type_name}'
        elif self.is_array:
            extra = '[]'
        return (f'{self.kind.value:<8} {self.type_name+extra:<24} '
                f'{self.name:<20} scope={self.scope_level} '
                f'L{self.line}:C{self.column}')

    def to_dict(self):
        return {
            'name':        self.name,
            'kind':        self.kind.value,
            'type':        self.type_name,
            'scope_level': self.scope_level,
            'line':        self.line,
            'column':      self.column,
            'value':       self.value,
            'param_types': self.param_types,
            'is_array':    self.is_array,
        }


class ScopeTable:
    """Single-scope hash table."""

    def __init__(self, level: int, name: str = '<anonymous>'):
        self.level   = level
        self.name    = name
        self._table: Dict[str, Symbol] = {}

    def insert(self, sym: Symbol) -> bool:
        """Returns False if the name is already declared in this scope."""
        if sym.name in self._table:
            return False
        self._table[sym.name] = sym
        return True

    def lookup(self, name: str) -> Optional[Symbol]:
        return self._table.get(name)

    def delete(self, name: str) -> bool:
        if name in self._table:
            del self._table[name]
            return True
        return False

    def all_symbols(self) -> List[Symbol]:
        return list(self._table.values())

    def __len__(self):
        return len(self._table)


class SymbolTable:
    """
    Stack of ScopeTable objects.
    The bottom scope (level 0) is the universe / predeclared names.
    """

    def __init__(self, error_handler=None):
        self._eh      = error_handler
        self._scopes: List[ScopeTable] = []
        self._level   = 0
        self._all_scopes: List[ScopeTable] = []  # history for dump

        # Universe scope
        self._push_scope('universe')
        self._install_builtins()

    # ------------------------------------------------------------------
    # Scope management
    # ------------------------------------------------------------------

    def _push_scope(self, name: str):
        scope = ScopeTable(self._level, name)
        self._scopes.append(scope)
        self._all_scopes.append(scope)

    def open_scope(self, method_name: str = None, class_name: str = None):
        self._level += 1
        label = method_name or class_name or f'scope_{self._level}'
        self._push_scope(label)

    def close_scope(self):
        if len(self._scopes) > 1:
            self._scopes.pop()
            self._level -= 1

    @property
    def current_level(self) -> int:
        return self._level

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------

    def _insert(self, sym: Symbol) -> bool:
        current = self._scopes[-1]
        if not current.insert(sym):
            if self._eh:
                self._eh.semantic(
                    f"Duplicate declaration of '{sym.name}' in this scope",
                    sym.line, sym.column,
                    hint=f"'{sym.name}' was already declared in scope "
                         f"'{current.name}'"
                )
            return False
        return True

    def insert_const(self, name: str, type_name: str, value: Any,
                     line: int, col: int) -> bool:
        return self._insert(Symbol(name, SymbolKind.CONST, type_name,
                                   self._level, line, col, value=value))

    def insert_var(self, name: str, type_name: str,
                   line: int, col: int,
                   kind: SymbolKind = SymbolKind.VAR,
                   is_array: bool = False) -> bool:
        sym = Symbol(name, kind, type_name, self._level, line, col,
                     is_array=is_array)
        return self._insert(sym)

    def insert_method(self, name: str, ret_type: str,
                      param_types: List[str],
                      line: int, col: int) -> bool:
        sym = Symbol(name, SymbolKind.METHOD, ret_type, self._level,
                     line, col, param_types=param_types)
        return self._insert(sym)

    def insert_class(self, name: str, line: int, col: int) -> bool:
        sym = Symbol(name, SymbolKind.CLASS, 'class', self._level,
                     line, col)
        return self._insert(sym)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def lookup(self, name: str) -> Optional[Symbol]:
        """
        Search from innermost scope outward.
        If the active scope stack is shallow (post-parse), also search
        all historical scopes so semantic analysis still works.
        """
        # Search active scopes first
        for scope in reversed(self._scopes):
            sym = scope.lookup(name)
            if sym is not None:
                return sym
        # Post-parse fallback: search all historical scopes (innermost first)
        for scope in reversed(self._all_scopes):
            sym = scope.lookup(name)
            if sym is not None:
                return sym
        return None

    def lookup_local(self, name: str) -> Optional[Symbol]:
        """Only the current (innermost) scope."""
        return self._scopes[-1].lookup(name)

    def delete(self, name: str) -> bool:
        return self._scopes[-1].delete(name)

    # ------------------------------------------------------------------
    # Built-ins
    # ------------------------------------------------------------------

    def _install_builtins(self):
        builtins = [
            Symbol('int',  SymbolKind.BUILTIN, 'type', 0, 0, 0),
            Symbol('char', SymbolKind.BUILTIN, 'type', 0, 0, 0),
            Symbol('null', SymbolKind.BUILTIN, 'null', 0, 0, 0),
            Symbol('ord',  SymbolKind.METHOD, 'int',  0, 0, 0,
                   param_types=['char']),
            Symbol('chr',  SymbolKind.METHOD, 'char', 0, 0, 0,
                   param_types=['int']),
            Symbol('len',  SymbolKind.METHOD, 'int',  0, 0, 0,
                   param_types=['array']),
        ]
        for sym in builtins:
            self._scopes[0].insert(sym)

    # ------------------------------------------------------------------
    # Dump
    # ------------------------------------------------------------------

    def dump(self) -> str:
        lines = []
        lines.append('=' * 72)
        lines.append('SYMBOL TABLE DUMP')
        lines.append('=' * 72)
        for scope in self._all_scopes:
            lines.append(f'\nScope [{scope.level}] "{scope.name}"  '
                         f'({len(scope)} entries)')
            lines.append('-' * 60)
            for sym in sorted(scope.all_symbols(), key=lambda s: s.name):
                lines.append('  ' + str(sym))
        lines.append('=' * 72)
        return '\n'.join(lines)

    def to_list(self) -> List[dict]:
        result = []
        for scope in self._all_scopes:
            for sym in scope.all_symbols():
                d = sym.to_dict()
                d['scope_name'] = scope.name
                result.append(d)
        return result
