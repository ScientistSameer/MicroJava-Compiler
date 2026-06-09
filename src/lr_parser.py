"""
SLR(1) Parser for MicroJava (New Module).

Implementation:
  1. Augments the grammar with  Program' -> Program
  2. Computes the canonical collection of LR(0) item sets
  3. Computes FOLLOW sets (reused from the LL1 module)
  4. Builds ACTION (shift/reduce/accept/error) and GOTO tables
  5. Simulates the standard shift-reduce algorithm with a state stack

The grammar used here is the ORIGINAL (left-recursive-allowed) MicroJava
grammar which SLR(1) can handle directly.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, FrozenSet

from .token         import Token, TokenType
from .error_handler import ErrorHandler


# --------------------------------------------------------------------------
# Grammar for LR parsing (original MicroJava BNF, slightly reformatted)
# Productions are numbered 0 .. N-1.
# --------------------------------------------------------------------------

# Each production is  (head, [body_symbols])
# 'eps' = empty body  (not used directly; just empty list)

LR_GRAMMAR_PRODS: List[Tuple[str, List[str]]] = [
    # 0  augmented start
    ("Program'",   ['Program']),
    # 1
    ('Program',    ['program', 'ident', 'DeclList', 'lbrace', 'MethodList', 'rbrace']),
    # 2
    ('DeclList',   ['DeclList', 'ConstDecl']),
    # 3
    ('DeclList',   ['DeclList', 'VarDecl']),
    # 4
    ('DeclList',   ['DeclList', 'ClassDecl']),
    # 5
    ('DeclList',   []),
    # 6
    ('ConstDecl',  ['final', 'Type', 'ident', 'assign', 'Literal', 'semicolon']),
    # 7
    ('Literal',    ['number']),
    # 8
    ('Literal',    ['charconst']),
    # 9
    ('VarDecl',    ['Type', 'NameList', 'semicolon']),
    # 10
    ('NameList',   ['NameList', 'comma', 'ident']),
    # 11
    ('NameList',   ['ident']),
    # 12
    ('ClassDecl',  ['class', 'ident', 'lbrace', 'VarDeclSeq', 'rbrace']),
    # 13
    ('VarDeclSeq', ['VarDeclSeq', 'VarDecl']),
    # 14
    ('VarDeclSeq', []),
    # 15
    ('MethodList', ['MethodList', 'MethodDecl']),
    # 16
    ('MethodList', []),
    # 17
    ('MethodDecl', ['MethodType', 'ident', 'lparen', 'FormParsOpt', 'rparen',
                    'VarDeclSeq', 'Block']),
    # 18
    ('MethodType', ['Type']),
    # 19
    ('MethodType', ['void']),
    # 20
    ('FormParsOpt',['FormPars']),
    # 21
    ('FormParsOpt',[]),
    # 22
    ('FormPars',   ['FormPars', 'comma', 'Type', 'ident']),
    # 23
    ('FormPars',   ['Type', 'ident']),
    # 24
    ('Type',       ['ident']),
    # 25
    ('Type',       ['ident', 'lbrack', 'rbrack']),
    # 26
    ('Type',       ['int']),
    # 27
    ('Type',       ['int', 'lbrack', 'rbrack']),
    # 28
    ('Type',       ['char']),
    # 29
    ('Type',       ['char', 'lbrack', 'rbrack']),
    # 30
    ('Block',      ['lbrace', 'StmtSeq', 'rbrace']),
    # 31
    ('StmtSeq',    ['StmtSeq', 'Statement']),
    # 32
    ('StmtSeq',    []),
    # 33
    ('Statement',  ['Designator', 'assign', 'Expr', 'semicolon']),
    # 34
    ('Statement',  ['Designator', 'ActPars', 'semicolon']),
    # 35
    ('Statement',  ['if', 'lparen', 'Condition', 'rparen', 'Statement']),
    # 36
    ('Statement',  ['if', 'lparen', 'Condition', 'rparen', 'Statement',
                    'else', 'Statement']),
    # 37
    ('Statement',  ['while', 'lparen', 'Condition', 'rparen', 'Statement']),
    # 38
    ('Statement',  ['return', 'semicolon']),
    # 39
    ('Statement',  ['return', 'Expr', 'semicolon']),
    # 40
    ('Statement',  ['read', 'lparen', 'Designator', 'rparen', 'semicolon']),
    # 41
    ('Statement',  ['print', 'lparen', 'Expr', 'rparen', 'semicolon']),
    # 42
    ('Statement',  ['print', 'lparen', 'Expr', 'comma', 'number', 'rparen', 'semicolon']),
    # 43
    ('Statement',  ['Block']),
    # 44
    ('Statement',  ['semicolon']),
    # 45
    ('ActPars',    ['lparen', 'ExprList', 'rparen']),
    # 46
    ('ActPars',    ['lparen', 'rparen']),
    # 47
    ('ExprList',   ['ExprList', 'comma', 'Expr']),
    # 48
    ('ExprList',   ['Expr']),
    # 49
    ('Condition',  ['Expr', 'relop', 'Expr']),
    # 50
    ('Expr',       ['Expr', 'plus', 'Term']),
    # 51
    ('Expr',       ['Expr', 'minus', 'Term']),
    # 52
    ('Expr',       ['Term']),
    # 53
    ('Expr',       ['minus', 'Term']),
    # 54
    ('Term',       ['Term', 'times', 'Factor']),
    # 55
    ('Term',       ['Term', 'div', 'Factor']),
    # 56
    ('Term',       ['Term', 'mod', 'Factor']),
    # 57
    ('Term',       ['Factor']),
    # 58
    ('Factor',     ['Designator']),
    # 59
    ('Factor',     ['Designator', 'ActPars']),
    # 60
    ('Factor',     ['number']),
    # 61
    ('Factor',     ['charconst']),
    # 62
    ('Factor',     ['new', 'ident']),
    # 63
    ('Factor',     ['new', 'ident', 'lbrack', 'Expr', 'rbrack']),
    # 64
    ('Factor',     ['lparen', 'Expr', 'rparen']),
    # 65
    ('Designator', ['ident']),
    # 66
    ('Designator', ['Designator', 'dot', 'ident']),
    # 67
    ('Designator', ['Designator', 'lbrack', 'Expr', 'rbrack']),
]

# Map token -> grammar terminal
def _tok_terminal(tok: Token) -> str:
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
        TokenType.EQ:         'relop',
        TokenType.NE:         'relop',
        TokenType.LT:         'relop',
        TokenType.LE:         'relop',
        TokenType.GT:         'relop',
        TokenType.GE:         'relop',
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
    return mapping.get(tok.type, '$')


# --------------------------------------------------------------------------
# LR(0) Item
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    prod_idx: int      # index into LR_GRAMMAR_PRODS
    dot:      int      # dot position (0 = before first symbol)

    @property
    def head(self) -> str:
        return LR_GRAMMAR_PRODS[self.prod_idx][0]

    @property
    def body(self) -> List[str]:
        return LR_GRAMMAR_PRODS[self.prod_idx][1]

    @property
    def after_dot(self) -> Optional[str]:
        body = self.body
        return body[self.dot] if self.dot < len(body) else None

    @property
    def is_complete(self) -> bool:
        return self.dot >= len(self.body)

    def advanced(self) -> 'Item':
        return Item(self.prod_idx, self.dot + 1)

    def __str__(self):
        body = list(self.body)
        body.insert(self.dot, '.')
        return f'{self.head} -> {" ".join(body)}'


ItemSet = FrozenSet[Item]


# --------------------------------------------------------------------------
# LR(0) automaton builder
# --------------------------------------------------------------------------

class LRAutomaton:
    def __init__(self):
        self.prods = LR_GRAMMAR_PRODS
        self._non_terminals: Set[str] = {p[0] for p in self.prods}
        self._terminals:     Set[str] = self._collect_terminals()

        self._states: List[ItemSet] = []
        self._state_idx: Dict[ItemSet, int] = {}
        self._goto_map: Dict[Tuple[int, str], int] = {}

        self._build()

        # SLR(1) requires FOLLOW sets — compute them from the grammar
        self._follow: Dict[str, Set[str]] = self._compute_follow()

        # ACTION and GOTO tables
        self.action: Dict[Tuple[int, str], Tuple[str, int]] = {}
        self.goto:   Dict[Tuple[int, str], int] = {}
        self.conflicts: List[str] = []
        self._build_tables()

    # ------------------------------------------------------------------

    def _collect_terminals(self) -> Set[str]:
        t = {'$'}
        nts = {p[0] for p in self.prods}
        for _, body in self.prods:
            for sym in body:
                if sym not in nts:
                    t.add(sym)
        return t

    def _closure(self, items: Set[Item]) -> ItemSet:
        closed = set(items)
        worklist = list(items)
        while worklist:
            item = worklist.pop()
            B = item.after_dot
            if B and B in self._non_terminals:
                for idx, (head, _) in enumerate(self.prods):
                    if head == B:
                        new_item = Item(idx, 0)
                        if new_item not in closed:
                            closed.add(new_item)
                            worklist.append(new_item)
        return frozenset(closed)

    def _goto(self, items: ItemSet, sym: str) -> ItemSet:
        moved = {item.advanced() for item in items
                 if item.after_dot == sym}
        return self._closure(moved) if moved else frozenset()

    def _build(self):
        start_item = Item(0, 0)   # Program' -> • Program
        s0 = self._closure({start_item})
        self._states.append(s0)
        self._state_idx[s0] = 0
        worklist = [s0]
        while worklist:
            state = worklist.pop(0)
            si    = self._state_idx[state]
            # Collect all symbols after dot
            symbols = {item.after_dot for item in state
                       if item.after_dot is not None}
            for sym in symbols:
                next_state = self._goto(state, sym)
                if not next_state:
                    continue
                if next_state not in self._state_idx:
                    ni = len(self._states)
                    self._states.append(next_state)
                    self._state_idx[next_state] = ni
                    worklist.append(next_state)
                self._goto_map[(si, sym)] = self._state_idx[next_state]

    # ------------------------------------------------------------------
    # FOLLOW sets (simple iterative algorithm on LR grammar)
    # ------------------------------------------------------------------

    def _compute_follow(self) -> Dict[str, Set[str]]:
        nts  = self._non_terminals
        follow: Dict[str, Set[str]] = {nt: set() for nt in nts}
        follow["Program'"].add('$')
        changed = True
        while changed:
            changed = False
            for head, body in self.prods:
                for i, sym in enumerate(body):
                    if sym not in nts:
                        continue
                    rest = body[i + 1:]
                    # FIRST of rest
                    first_rest: Set[str] = set()
                    all_eps = True
                    for s in rest:
                        if s in nts:
                            # rough FIRST: collect terminals reachable
                            # (we use a simplified direct approach here)
                            reachable = self._first_of(s)
                            first_rest |= reachable - {'eps'}
                            if 'eps' not in reachable:
                                all_eps = False
                                break
                        else:
                            first_rest.add(s)
                            all_eps = False
                            break
                    for a in first_rest:
                        if a not in follow[sym]:
                            follow[sym].add(a)
                            changed = True
                    if all_eps or not rest:
                        for a in follow[head]:
                            if a not in follow[sym]:
                                follow[sym].add(a)
                                changed = True
        return follow

    def _first_of(self, nt: str) -> Set[str]:
        """Approximate FIRST for a non-terminal (iterative)."""
        nts  = self._non_terminals
        seen: Set[str] = set()
        work = [nt]
        result: Set[str] = set()
        while work:
            cur = work.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for head, body in self.prods:
                if head != cur:
                    continue
                if not body:
                    result.add('eps')
                    continue
                first_sym = body[0]
                if first_sym in nts:
                    work.append(first_sym)
                else:
                    result.add(first_sym)
        return result

    # ------------------------------------------------------------------
    # Build ACTION / GOTO tables
    # ------------------------------------------------------------------

    def _set_action(self, state: int, sym: str, value: Tuple[str, int]):
        key = (state, sym)
        if key in self.action:
            existing = self.action[key]
            if existing != value:
                self.conflicts.append(
                    f'State {state}, symbol "{sym}": '
                    f'{existing} vs {value}'
                )
            return
        self.action[key] = value

    def _build_tables(self):
        for state_idx, state in enumerate(self._states):
            # Shifts and non-terminal gotos
            for (si, sym), next_si in self._goto_map.items():
                if si != state_idx:
                    continue
                if sym in self._terminals:
                    self._set_action(state_idx, sym, ('shift', next_si))
                else:
                    self.goto[(state_idx, sym)] = next_si

            # Reduces
            for item in state:
                if not item.is_complete:
                    continue
                head = item.head
                if head == "Program'":
                    self._set_action(state_idx, '$', ('accept', 0))
                    continue
                prod_len = len(item.body)
                follow_head = self._follow.get(head, set())
                for a in follow_head:
                    self._set_action(state_idx, a,
                                     ('reduce', item.prod_idx))

    # ------------------------------------------------------------------
    # Format tables for report
    # ------------------------------------------------------------------

    def format_action_goto(self, max_states: int = 60) -> str:
        terminals = sorted(self._terminals)
        nts_used  = sorted({sym for (_, sym) in self.goto.keys()})
        lines = []
        head_row = f'{"State":>6}  ' + '  '.join(f'{t[:8]:>8}' for t in terminals)
        if nts_used:
            head_row += '  |  ' + '  '.join(f'{n[:10]:>10}' for n in nts_used)
        lines.append(head_row)
        lines.append('-' * len(head_row))
        for si in range(min(len(self._states), max_states)):
            row = f'{si:>6}  '
            for t in terminals:
                cell = self.action.get((si, t))
                if cell is None:
                    row += f'{"":>10}'
                elif cell[0] == 'shift':
                    row += f'{"s"+str(cell[1]):>10}'
                elif cell[0] == 'reduce':
                    row += f'{"r"+str(cell[1]):>10}'
                elif cell[0] == 'accept':
                    row += f'{"acc":>10}'
            if nts_used:
                row += '  |  '
                for n in nts_used:
                    cell = self.goto.get((si, n))
                    row += f'{str(cell) if cell is not None else "":>10}  '
            lines.append(row)
        if len(self._states) > max_states:
            lines.append(f'  ... ({len(self._states) - max_states} more states)')
        return '\n'.join(lines)

    def format_productions(self) -> str:
        lines = ['LR Grammar Productions:']
        for i, (head, body) in enumerate(self.prods):
            body_str = ' '.join(body) if body else 'ε'
            lines.append(f'  [{i:>3}]  {head} -> {body_str}')
        return '\n'.join(lines)

    def summary(self) -> str:
        return (f'States: {len(self._states)}  '
                f'Productions: {len(self.prods)}  '
                f'Conflicts: {len(self.conflicts)}')


# --------------------------------------------------------------------------
# Shift-reduce driver
# --------------------------------------------------------------------------

_CACHED_AUTOMATON: Optional['LRAutomaton'] = None

def _get_automaton() -> 'LRAutomaton':
    global _CACHED_AUTOMATON
    if _CACHED_AUTOMATON is None:
        _CACHED_AUTOMATON = LRAutomaton()
    return _CACHED_AUTOMATON


class LRParser:
    def __init__(self, tokens: List[Token], error_handler: ErrorHandler):
        self._tokens  = tokens
        self._eh      = error_handler
        self._auto    = _get_automaton()
        self._trace: List[dict] = []

    @property
    def automaton(self) -> LRAutomaton:
        return self._auto

    def parse(self) -> bool:
        auto   = self._auto
        pos    = 0
        stack: List[int] = [0]    # state stack
        sym_stack: List[str] = [] # symbol stack (for display)
        success = True

        def current_tok() -> Token:
            return self._tokens[min(pos, len(self._tokens) - 1)]

        while True:
            state = stack[-1]
            tok   = current_tok()
            a     = _tok_terminal(tok)

            stack_disp  = str(stack[-6:])
            sym_disp    = str(sym_stack[-6:])

            if (state, a) not in auto.action:
                # Error entry
                self._eh.syntactic(
                    f"Syntax error: unexpected '{tok.value}' (state {state})",
                    tok.line, tok.column,
                    hint=f"No LR action for state {state} on '{a}'"
                )
                self._trace.append({
                    'stack':  stack_disp,
                    'syms':   sym_disp,
                    'input':  tok.value,
                    'action': f'ERROR(state={state}, sym={a})',
                })
                success = False
                # Panic recovery: pop states until a state has a valid action
                recovered = False
                for _ in range(min(10, len(stack))):
                    stack.pop()
                    if sym_stack:
                        sym_stack.pop()
                    if not stack:
                        break
                    state = stack[-1]
                    if (state, a) in auto.action:
                        recovered = True
                        break
                if not recovered:
                    pos += 1  # skip token
                    if pos >= len(self._tokens):
                        break
                continue

            action, val = auto.action[(state, a)]

            self._trace.append({
                'stack':  stack_disp,
                'syms':   sym_disp,
                'input':  tok.value,
                'action': f'{action} {val}',
            })

            if action == 'accept':
                return success

            elif action == 'shift':
                stack.append(val)
                sym_stack.append(a)
                pos += 1

            elif action == 'reduce':
                prod_idx = val
                head, body = LR_GRAMMAR_PRODS[prod_idx]
                # Pop |body| states/symbols
                for _ in range(len(body)):
                    stack.pop()
                    if sym_stack:
                        sym_stack.pop()
                # Goto
                top = stack[-1]
                if (top, head) in auto.goto:
                    stack.append(auto.goto[(top, head)])
                    sym_stack.append(head)
                else:
                    self._eh.syntactic(
                        f"LR GOTO error: no goto for ({top}, {head})",
                        tok.line, tok.column)
                    success = False

            if pos >= len(self._tokens):
                break

        return success

    def format_trace(self, max_rows: int = 150) -> str:
        lines = [f'{"STACK":>30}  {"INPUT":<15}  {"ACTION"}']
        lines.append('-' * 80)
        for step in self._trace[:max_rows]:
            lines.append(
                f'{step["stack"]:>30}  {step["input"]:<15}  {step["action"]}'
            )
        if len(self._trace) > max_rows:
            lines.append(f'  ... ({len(self._trace) - max_rows} more steps)')
        return '\n'.join(lines)
