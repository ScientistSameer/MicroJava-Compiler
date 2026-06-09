"""
Non-Recursive Predictive (LL(1)) Parser for MicroJava (Lab 5 / Lab 10 extended).

The parser:
  1. Computes FIRST and FOLLOW sets automatically from the CFG.
  2. Builds the LL(1) parsing table.
  3. Simulates the table-driven parser with an explicit stack.
  4. Reports parsing trace (stack | input | action) for each step.
  5. Performs panic-mode recovery on error entries.

The grammar is in the left-factored, left-recursion-free form required for LL(1).
"""

from __future__ import annotations
from typing import Dict, List, Set, Tuple, Optional

from .token         import Token, TokenType
from .error_handler import ErrorHandler


# --------------------------------------------------------------------------
# Grammar definition
# Each production is a list of symbols. 'epsilon' = empty production.
# Terminal symbols match Token.type.name (lowercase for grammar terminals).
# --------------------------------------------------------------------------

EPSILON = 'epsilon'

GRAMMAR: Dict[str, List[List[str]]] = {
    'Program':       [['program', 'ident', 'Decls', 'lbrace', 'MethodDecls', 'rbrace']],
    'Decls':         [['ConstDecl', 'Decls'],
                      ['VarDecl', 'Decls'],
                      ['ClassDecl', 'Decls'],
                      [EPSILON]],
    'ConstDecl':     [['final', 'Type', 'ident', 'assign', 'NumberOrChar', 'semicolon']],
    'NumberOrChar':  [['number'], ['charconst']],
    'VarDecl':       [['Type', 'ident', 'IdentList', 'semicolon']],
    'IdentList':     [['comma', 'ident', 'IdentList'], [EPSILON]],
    'ClassDecl':     [['class', 'ident', 'lbrace', 'VarDecls', 'rbrace']],
    'VarDecls':      [['VarDecl', 'VarDecls'], [EPSILON]],
    'MethodDecls':   [['MethodDecl', 'MethodDecls'], [EPSILON]],
    'MethodDecl':    [['MethodType', 'ident', 'lparen', 'OptFormPars',
                       'rparen', 'VarDecls', 'Block']],
    'MethodType':    [['Type'], ['void']],
    'OptFormPars':   [['FormPars'], [EPSILON]],
    'FormPars':      [['Type', 'ident', 'FormParsList']],
    'FormParsList':  [['comma', 'Type', 'ident', 'FormParsList'], [EPSILON]],
    'Type':          [['ident', 'OptBrackets'],
                      ['int', 'OptBrackets'],
                      ['char', 'OptBrackets']],
    'OptBrackets':   [['lbrack', 'rbrack'], [EPSILON]],
    'Block':         [['lbrace', 'Statements', 'rbrace']],
    'Statements':    [['Statement', 'Statements'], [EPSILON]],
    'Statement':     [
        ['Designator', 'StatementSuffix', 'semicolon'],
        ['if', 'lparen', 'Condition', 'rparen', 'Statement', 'OptElse'],
        ['while', 'lparen', 'Condition', 'rparen', 'Statement'],
        ['return', 'OptExpr', 'semicolon'],
        ['read', 'lparen', 'Designator', 'rparen', 'semicolon'],
        ['print', 'lparen', 'Expr', 'OptPrintNumber', 'rparen', 'semicolon'],
        ['Block'],
        ['semicolon'],
    ],
    'StatementSuffix': [['assign', 'Expr'], ['ActPars']],
    'OptElse':       [['else', 'Statement'], [EPSILON]],
    'OptExpr':       [['Expr'], [EPSILON]],
    'OptPrintNumber':[['comma', 'number'], [EPSILON]],
    'ActPars':       [['lparen', 'OptExprs', 'rparen']],
    'OptExprs':      [['Expr', 'ExprList'], [EPSILON]],
    'ExprList':      [['comma', 'Expr', 'ExprList'], [EPSILON]],
    'Condition':     [['Expr', 'Relop', 'Expr']],
    'Relop':         [['eq'], ['ne'], ['lt'], ['le'], ['gt'], ['ge']],
    'Expr':          [['OptMinus', 'Term', 'ExprPrime']],
    'OptMinus':      [['minus'], [EPSILON]],
    'ExprPrime':     [['Addop', 'Term', 'ExprPrime'], [EPSILON]],
    'Term':          [['Factor', 'TermPrime']],
    'TermPrime':     [['Mulop', 'Factor', 'TermPrime'], [EPSILON]],
    'Factor':        [
        ['Designator', 'OptActPars'],
        ['number'],
        ['charconst'],
        ['new', 'NewTypeName', 'OptNewArray'],
        ['lparen', 'Expr', 'rparen'],
    ],
    'NewTypeName':   [['ident'], ['int'], ['char']],
    'OptActPars':    [['ActPars'], [EPSILON]],
    'OptNewArray':   [['lbrack', 'Expr', 'rbrack'], [EPSILON]],
    'Designator':    [['ident', 'DesignatorList']],
    'DesignatorList':[
        ['dot', 'ident', 'DesignatorList'],
        ['lbrack', 'Expr', 'rbrack', 'DesignatorList'],
        [EPSILON]
    ],
    'Addop':         [['plus'], ['minus']],
    'Mulop':         [['times'], ['div'], ['mod']],
}

START_SYMBOL = 'Program'


def _tok_to_terminal(tok: Token) -> str:
    """Map a Token to the grammar terminal name used above."""
    mapping = {
        TokenType.PROGRAM:    'program',
        TokenType.CLASS:      'class',
        TokenType.IF:         'if',
        TokenType.ELSE:       'else',
        TokenType.WHILE:      'while',
        TokenType.READ:       'read',
        TokenType.PRINT:      'print',
        TokenType.RETURN:     'return',
        TokenType.VOID:       'void',
        TokenType.FINAL:      'final',
        TokenType.NEW:        'new',
        TokenType.INT:        'int',
        TokenType.CHAR:       'char',
        TokenType.IDENT:      'ident',
        TokenType.NUMBER:     'number',
        TokenType.CHAR_CONST: 'charconst',
        TokenType.PLUS:       'plus',
        TokenType.MINUS:      'minus',
        TokenType.TIMES:      'times',
        TokenType.DIV:        'div',
        TokenType.MOD:        'mod',
        TokenType.EQ:         'eq',
        TokenType.NE:         'ne',
        TokenType.LT:         'lt',
        TokenType.LE:         'le',
        TokenType.GT:         'gt',
        TokenType.GE:         'ge',
        TokenType.ASSIGN:     'assign',
        TokenType.LPAREN:     'lparen',
        TokenType.RPAREN:     'rparen',
        TokenType.LBRACK:     'lbrack',
        TokenType.RBRACK:     'rbrack',
        TokenType.LBRACE:     'lbrace',
        TokenType.RBRACE:     'rbrace',
        TokenType.SEMICOLON:  'semicolon',
        TokenType.COMMA:      'comma',
        TokenType.DOT:        'dot',
        TokenType.EOF:        '$',
    }
    return mapping.get(tok.type, tok.value.lower())


# --------------------------------------------------------------------------
# LL(1) table builder
# --------------------------------------------------------------------------

class LL1Table:
    """Computes FIRST, FOLLOW, and the LL(1) parsing table from the grammar."""

    def __init__(self, grammar: Dict, start: str):
        self.grammar      = grammar
        self.start        = start
        self.non_terminals: Set[str] = set(grammar.keys())
        self.terminals:    Set[str]  = self._get_terminals()
        self.first:  Dict[str, Set[str]] = self._compute_first()
        self.follow: Dict[str, Set[str]] = self._compute_follow()
        self.table:  Dict[Tuple[str,str], List[str]] = {}
        self.conflicts: List[str] = []
        self._build_table()

    def _get_terminals(self) -> Set[str]:
        t: Set[str] = {'$'}
        for prods in self.grammar.values():
            for prod in prods:
                for sym in prod:
                    if sym not in self.non_terminals and sym != EPSILON:
                        t.add(sym)
        return t

    def _first_of_seq(self, seq: List[str]) -> Set[str]:
        result: Set[str] = set()
        for sym in seq:
            if sym == EPSILON:
                result.add(EPSILON)
                break
            if sym in self.non_terminals:
                result |= self.first[sym] - {EPSILON}
                if EPSILON not in self.first[sym]:
                    return result
            else:
                result.add(sym)
                return result
        result.add(EPSILON)
        return result

    def _compute_first(self) -> Dict[str, Set[str]]:
        first: Dict[str, Set[str]] = {nt: set() for nt in self.grammar}
        changed = True
        while changed:
            changed = False
            for head, prods in self.grammar.items():
                for prod in prods:
                    if prod == [EPSILON]:
                        if EPSILON not in first[head]:
                            first[head].add(EPSILON)
                            changed = True
                        continue
                    for sym in prod:
                        if sym in self.non_terminals:
                            add = first[sym] - {EPSILON}
                            for a in add:
                                if a not in first[head]:
                                    first[head].add(a)
                                    changed = True
                            if EPSILON not in first[sym]:
                                break
                        else:
                            if sym not in first[head]:
                                first[head].add(sym)
                                changed = True
                            break
                    else:
                        if EPSILON not in first[head]:
                            first[head].add(EPSILON)
                            changed = True
        return first

    def _compute_follow(self) -> Dict[str, Set[str]]:
        follow: Dict[str, Set[str]] = {nt: set() for nt in self.grammar}
        follow[self.start].add('$')
        changed = True
        while changed:
            changed = False
            for head, prods in self.grammar.items():
                for prod in prods:
                    for i, sym in enumerate(prod):
                        if sym not in self.non_terminals:
                            continue
                        rest = prod[i + 1:]
                        f = self._first_of_seq(rest)
                        for a in f - {EPSILON}:
                            if a not in follow[sym]:
                                follow[sym].add(a)
                                changed = True
                        if EPSILON in f or not rest:
                            for a in follow[head]:
                                if a not in follow[sym]:
                                    follow[sym].add(a)
                                    changed = True
        return follow

    def _build_table(self):
        for head, prods in self.grammar.items():
            for prod in prods:
                first_prod = self._first_of_seq(prod)
                for a in first_prod - {EPSILON}:
                    key = (head, a)
                    if key in self.table:
                        self.conflicts.append(
                            f'Conflict at M[{head},{a}]: '
                            f'{self.table[key]} vs {prod}'
                        )
                    else:
                        self.table[key] = prod
                if EPSILON in first_prod:
                    for b in self.follow[head]:
                        key = (head, b)
                        if key in self.table:
                            self.conflicts.append(
                                f'Conflict at M[{head},{b}]: '
                                f'{self.table[key]} vs {prod}'
                            )
                        else:
                            self.table[key] = prod

    def format_table(self, max_rows: int = 80) -> str:
        lines = [f'{"Non-Terminal":<22} {"Terminal":<16} {"Production"}']
        lines.append('-' * 80)
        count = 0
        for (nt, term), prod in sorted(self.table.items()):
            lines.append(f'{nt:<22} {term:<16} {nt} -> {" ".join(prod)}')
            count += 1
            if count >= max_rows:
                lines.append(f'  ... ({len(self.table) - max_rows} more entries)')
                break
        return '\n'.join(lines)

    def format_first_follow(self) -> str:
        lines = ['FIRST sets:']
        for nt in sorted(self.grammar.keys()):
            lines.append(f'  FIRST({nt}) = {{ {", ".join(sorted(self.first[nt]))} }}')
        lines.append('\nFOLLOW sets:')
        for nt in sorted(self.grammar.keys()):
            lines.append(f'  FOLLOW({nt}) = {{ {", ".join(sorted(self.follow[nt]))} }}')
        return '\n'.join(lines)


# --------------------------------------------------------------------------
# LL(1) Parser (table-driven)
# --------------------------------------------------------------------------

class LL1Parser:
    def __init__(self, tokens: List[Token], error_handler: ErrorHandler):
        self._tokens = tokens
        self._eh     = error_handler
        self._table_obj = LL1Table(GRAMMAR, START_SYMBOL)
        self._trace: List[dict] = []

    @property
    def first_follow(self) -> str:
        return self._table_obj.format_first_follow()

    @property
    def table_str(self) -> str:
        return self._table_obj.format_table()

    @property
    def conflicts(self) -> List[str]:
        return self._table_obj.conflicts

    def parse(self) -> bool:
        table    = self._table_obj.table
        nts      = self._table_obj.non_terminals
        stack    = ['$', START_SYMBOL]
        pos      = 0
        success  = True

        def current() -> Token:
            return self._tokens[min(pos, len(self._tokens) - 1)]

        while stack:
            X   = stack[-1]
            tok = current()
            a   = _tok_to_terminal(tok)

            self._trace.append({
                'stack': list(stack),
                'input': tok.value,
                'action': '',
            })

            if X == '$':
                if a == '$':
                    self._trace[-1]['action'] = 'ACCEPT'
                    return success
                else:
                    self._eh.syntactic(
                        f"Expected end of input, found '{tok.value}'",
                        tok.line, tok.column)
                    return False

            stack.pop()

            if X == EPSILON:
                self._trace[-1]['action'] = 'pop epsilon'
                continue

            if X not in nts:
                # Terminal — must match
                if X == a:
                    pos += 1
                    self._trace[-1]['action'] = f'match {X}'
                else:
                    self._eh.syntactic(
                        f"Expected '{X}', found '{tok.value}'",
                        tok.line, tok.column,
                        hint=f"Insert '{X}' before '{tok.value}'"
                    )
                    self._trace[-1]['action'] = f'ERROR: expected {X}'
                    success = False
                    # phrase-level: skip one token and retry
                    pos += 1
                continue

            # Non-terminal
            key = (X, a)
            if key in table:
                prod = table[key]
                action = f'{X} -> {" ".join(prod)}'
                self._trace[-1]['action'] = action
                if prod != [EPSILON]:
                    for sym in reversed(prod):
                        stack.append(sym)
            else:
                # Error entry — panic-mode: skip tokens
                self._eh.syntactic(
                    f"No rule for ({X}, '{tok.value}')",
                    tok.line, tok.column,
                    hint=f"Unexpected '{tok.value}' while parsing {X}"
                )
                self._trace[-1]['action'] = f'ERROR: no rule for ({X}, {a})'
                success = False
                # Skip tokens until something in FOLLOW(X) or a terminal expected by parent
                follow_x = self._table_obj.follow.get(X, set())
                while (a not in follow_x and a != '$'):
                    pos += 1
                    tok = current()
                    a   = _tok_to_terminal(tok)
                # Push X back for re-evaluation
                stack.append(X)
                continue

        return success

    def format_trace(self, max_rows: int = 200) -> str:
        lines = [f'{"STACK":<55} {"INPUT":<20} {"ACTION"}']
        lines.append('-' * 100)
        for i, step in enumerate(self._trace[:max_rows]):
            stack_s = str(step['stack'][-8:])   # last 8 elements
            lines.append(f'{stack_s:<55} {step["input"]:<20} {step["action"]}')
        if len(self._trace) > max_rows:
            lines.append(f'  ... ({len(self._trace) - max_rows} more steps)')
        return '\n'.join(lines)
