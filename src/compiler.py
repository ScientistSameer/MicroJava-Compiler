"""
MicroJava Mini Compiler — Main Integration Module
==================================================

Integrates all compiler phases into one pipeline:
  1. Lexical Analysis    (Lexer + DoubleBuffer)
  2. Recursive Descent Parser (builds AST)
  3. LL(1) Predictive Parser  (table-driven verification)
  4. SLR(1) LR Parser         (shift-reduce verification)
  5. Symbol Table Manager
  6. Semantic Analyzer / Type Checker
  7. Three-Address Code Generator
  8. Constant Folding + Dead-Code Elimination Optimizer
  9. Error Handler (aggregates all phases)
 10. Pretty Printer, Metrics, AST Visualization (bonus features)

CLI usage:
  python -m src.compiler <source.mj> [--phase all|lex|rd|ll1|lr|sym|sem|tac]
  python -m src.compiler --help
"""

from __future__ import annotations
import sys
import os

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import time
import json
import argparse
from typing import Optional, List

from .token         import Token, TokenType
from .lexer         import Lexer
from .error_handler import ErrorHandler
from .symbol_table  import SymbolTable
from .rd_parser     import RDParser
from .ll1_parser    import LL1Parser
from .lr_parser     import LRParser
from .semantic      import SemanticAnalyzer
from .codegen       import CodeGenerator, ConstantFolder, DeadCodeEliminator
from .ast_nodes     import ProgramNode


# --------------------------------------------------------------------------
# CompileResult — returned by the compiler to callers (CLI + web API)
# --------------------------------------------------------------------------

class CompileResult:
    def __init__(self):
        self.source: str = ''
        self.tokens: List[Token] = []
        self.ast_str: str = ''
        self.rd_trace: List[str] = []
        self.rd_success: bool = False
        self.ll1_first_follow: str = ''
        self.ll1_table_str: str = ''
        self.ll1_trace: str = ''
        self.ll1_success: bool = False
        self.lr_productions: str = ''
        self.lr_action_goto: str = ''
        self.lr_trace: str = ''
        self.lr_success: bool = False
        self.lr_summary: str = ''
        self.sym_table_dump: str = ''
        self.sym_table_list: list = []
        self.tac_code: str = ''
        self.tac_optimized: str = ''
        self.errors: list = []
        self.warnings: list = []
        self.metrics: dict = {}
        self.elapsed_ms: float = 0.0
        self.success: bool = False
        self.lexer_stats: dict = {}

    def to_dict(self) -> dict:
        return {
            'source':           self.source,
            'tokens':           [
                {'type': t.type.name, 'value': t.value,
                 'line': t.line, 'column': t.column}
                for t in self.tokens if t.type != TokenType.EOF
            ],
            'ast':              self.ast_str,
            'rd_trace':         self.rd_trace[:200],
            'rd_success':       self.rd_success,
            'll1_first_follow': self.ll1_first_follow,
            'll1_table':        self.ll1_table_str,
            'll1_trace':        self.ll1_trace,
            'll1_success':      self.ll1_success,
            'lr_productions':   self.lr_productions,
            'lr_action_goto':   self.lr_action_goto,
            'lr_trace':         self.lr_trace,
            'lr_success':       self.lr_success,
            'lr_summary':       self.lr_summary,
            'sym_table':        self.sym_table_list,
            'sym_table_dump':   self.sym_table_dump,
            'tac_code':         self.tac_code,
            'tac_optimized':    self.tac_optimized,
            'errors':           self.errors,
            'warnings':         self.warnings,
            'metrics':          self.metrics,
            'elapsed_ms':       self.elapsed_ms,
            'success':          self.success,
            'lexer_stats':      self.lexer_stats,
        }


# --------------------------------------------------------------------------
# Bonus features
# --------------------------------------------------------------------------

def _compute_metrics(source: str, tokens: List[Token],
                     result: CompileResult) -> dict:
    lines = source.split('\n')
    non_blank = [l for l in lines if l.strip()]
    comment_toks = sum(1 for t in tokens if t.type == TokenType.ERROR)
    kw_count = sum(1 for t in tokens if t.is_keyword)
    ident_count = sum(1 for t in tokens if t.type == TokenType.IDENT)
    op_count = sum(1 for t in tokens
                   if t.type in (TokenType.PLUS, TokenType.MINUS,
                                 TokenType.TIMES, TokenType.DIV,
                                 TokenType.MOD))
    # Cyclomatic complexity ≈ 1 + number of branching statements
    branch_kws = sum(1 for t in tokens
                     if t.type in (TokenType.IF, TokenType.WHILE))
    cyclomatic = 1 + branch_kws
    return {
        'total_lines':    len(lines),
        'non_blank_lines': len(non_blank),
        'token_count':    len(tokens) - 1,  # exclude EOF
        'keyword_count':  kw_count,
        'identifier_count': ident_count,
        'operator_count': op_count,
        'cyclomatic_complexity': cyclomatic,
        'lexical_error_count': len(result.errors),
    }


def _pretty_print(source: str) -> str:
    """
    Bonus: simple pretty-printer that re-indents MicroJava source.
    Does not reformat within expressions — only statement-level indentation.
    """
    lines = source.split('\n')
    out = []
    indent = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append('')
            continue
        if stripped.startswith('}'):
            indent = max(0, indent - 1)
        out.append('    ' * indent + stripped)
        if stripped.endswith('{'):
            indent += 1
    return '\n'.join(out)


# --------------------------------------------------------------------------
# Main compiler pipeline
# --------------------------------------------------------------------------

class MicroJavaCompiler:
    def __init__(self):
        pass

    def compile(self, source: str, phase: str = 'all',
                run_ll1: bool = True, run_lr: bool = True) -> CompileResult:
        t0 = time.time()
        result = CompileResult()
        result.source = source

        eh  = ErrorHandler()
        sym = SymbolTable(error_handler=eh)

        # ------------------------------------------------------------------
        # Phase 1: Lexical Analysis
        # ------------------------------------------------------------------
        lexer  = Lexer(source, recover=True)
        tokens = lexer.tokenize()
        result.tokens      = tokens
        result.lexer_stats = lexer.get_stats()

        # Report lexical errors
        for err in lexer.get_errors():
            eh.lexical(f"Unexpected character {err.value!r}",
                       err.line, err.column)

        if phase == 'lex':
            result.errors      = eh.to_list()
            result.elapsed_ms  = (time.time() - t0) * 1000
            result.metrics     = _compute_metrics(source, tokens, result)
            return result

        # ------------------------------------------------------------------
        # Phase 2: Recursive Descent Parser
        # ------------------------------------------------------------------
        rd = RDParser(tokens, eh, sym)
        tree = rd.parse()
        result.rd_trace   = rd.get_trace()
        result.rd_success = (tree is not None and not eh.has_errors)
        if tree:
            result.ast_str = tree.to_str()

        if phase == 'rd':
            result.errors     = eh.to_list()
            result.elapsed_ms = (time.time() - t0) * 1000
            result.metrics    = _compute_metrics(source, tokens, result)
            return result

        # ------------------------------------------------------------------
        # Phase 3: LL(1) Parser
        # ------------------------------------------------------------------
        if run_ll1:
            ll1 = LL1Parser(tokens, eh)
            ll1_ok = ll1.parse()
            result.ll1_first_follow = ll1.first_follow
            result.ll1_table_str    = ll1.table_str
            result.ll1_trace        = ll1.format_trace()
            result.ll1_success      = ll1_ok
            if ll1.conflicts:
                eh.warning(
                    f'LL(1) table has {len(ll1.conflicts)} conflict(s)',
                    0, 0)

        # ------------------------------------------------------------------
        # Phase 4: LR (SLR(1)) Parser
        # ------------------------------------------------------------------
        if run_lr and phase != 'll1':
            try:
                lr = LRParser(tokens, eh)
                lr_ok = lr.parse()
                result.lr_productions = lr.automaton.format_productions()
                result.lr_action_goto = lr.automaton.format_action_goto()
                result.lr_trace       = lr.format_trace()
                result.lr_success     = lr_ok
                result.lr_summary     = lr.automaton.summary()
            except Exception as ex:
                result.lr_success = False
                result.lr_summary = f'LR parser error: {ex}'

        # ------------------------------------------------------------------
        # Phase 5: Symbol Table (already populated by RD parser)
        # ------------------------------------------------------------------
        result.sym_table_dump = sym.dump()
        result.sym_table_list = sym.to_list()

        if phase == 'sym':
            result.errors     = eh.to_list()
            result.elapsed_ms = (time.time() - t0) * 1000
            result.metrics    = _compute_metrics(source, tokens, result)
            return result

        # ------------------------------------------------------------------
        # Phase 6: Semantic Analysis
        # ------------------------------------------------------------------
        if tree:
            sem = SemanticAnalyzer(sym, eh)
            sem.analyze(tree)

        # ------------------------------------------------------------------
        # Phase 7 & 8: TAC + Optimization
        # ------------------------------------------------------------------
        if tree:
            gen = CodeGenerator()
            tac = gen.generate(tree)
            result.tac_code = gen.format_code()

            # Constant folding
            folder = ConstantFolder()
            optimized = folder.optimize(list(tac))

            # Dead code elimination
            eliminator = DeadCodeEliminator()
            optimized  = eliminator.optimize(optimized)
            result.tac_optimized = '\n'.join(str(i) for i in optimized)

        # ------------------------------------------------------------------
        # Finalize
        # ------------------------------------------------------------------
        result.errors     = eh.to_list()
        result.warnings   = [w.__str__() for w in eh.all_warnings()]
        result.metrics    = _compute_metrics(source, tokens, result)
        result.success    = not eh.has_errors
        result.elapsed_ms = (time.time() - t0) * 1000

        return result


# --------------------------------------------------------------------------
# CLI entry point
# --------------------------------------------------------------------------

def _print_section(title: str, content: str):
    print(f'\n{"="*70}')
    print(f'  {title}')
    print(f'{"="*70}')
    print(content)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='MicroJava Mini Compiler — By Sameer Babar'
    )
    parser.add_argument('source', nargs='?', help='MicroJava source file (.mj)')
    parser.add_argument('--phase', default='all',
                        choices=['all', 'lex', 'rd', 'll1', 'lr', 'sym', 'sem'],
                        help='Run up to (and including) this phase')
    parser.add_argument('--no-ll1', action='store_true',
                        help='Skip the LL(1) parser phase')
    parser.add_argument('--no-lr',  action='store_true',
                        help='Skip the LR parser phase')
    parser.add_argument('--json', action='store_true',
                        help='Output results as JSON')
    parser.add_argument('--pretty-print', action='store_true',
                        help='Pretty-print the source and exit')
    args = parser.parse_args(argv)

    if not args.source:
        parser.print_help()
        sys.exit(0)

    if not os.path.isfile(args.source):
        print(f'Error: file not found: {args.source}')
        sys.exit(1)

    with open(args.source, 'r', encoding='utf-8') as f:
        source = f.read()

    if args.pretty_print:
        print(_pretty_print(source))
        return

    compiler = MicroJavaCompiler()
    result   = compiler.compile(
        source,
        phase   = args.phase,
        run_ll1 = not args.no_ll1,
        run_lr  = not args.no_lr,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return

    # Human-readable output
    _print_section('TOKEN STREAM', '')
    print(f'  {"Line":>5}  {"Col":>4}  {"Type":<14}  {"Lexeme"}')
    print('  ' + '-' * 55)
    for tok in result.tokens:
        if tok.type == TokenType.EOF:
            continue
        print(f'  {tok.line:>5}  {tok.column:>4}  {tok.type.name:<14}  {tok.value!r}')

    if result.ast_str:
        _print_section('ABSTRACT SYNTAX TREE', result.ast_str)

    if result.rd_trace:
        _print_section('RECURSIVE DESCENT TRACE (first 40)',
                        '\n'.join(result.rd_trace[:40]))

    if result.ll1_first_follow:
        _print_section('FIRST & FOLLOW SETS', result.ll1_first_follow)

    if result.ll1_table_str:
        _print_section('LL(1) PARSING TABLE (first 30 entries)',
                        '\n'.join(result.ll1_table_str.split('\n')[:32]))

    if result.ll1_trace:
        _print_section('LL(1) PARSE TRACE', result.ll1_trace)

    if result.lr_productions:
        _print_section('LR GRAMMAR PRODUCTIONS', result.lr_productions)

    if result.lr_summary:
        _print_section('LR AUTOMATON SUMMARY', result.lr_summary)

    if result.lr_action_goto:
        _print_section('LR ACTION/GOTO TABLE (partial)',
                        '\n'.join(result.lr_action_goto.split('\n')[:30]))

    if result.lr_trace:
        _print_section('LR PARSE TRACE', result.lr_trace)

    if result.sym_table_dump:
        _print_section('SYMBOL TABLE', result.sym_table_dump)

    if result.tac_code:
        _print_section('THREE-ADDRESS CODE', result.tac_code)

    if result.tac_optimized:
        _print_section('OPTIMIZED TAC (constant folding + DCE)',
                        result.tac_optimized)

    if result.metrics:
        _print_section('CODE METRICS', '\n'.join(
            f'  {k:<30} {v}' for k, v in result.metrics.items()))

    _print_section('COMPILATION SUMMARY', '')
    status = 'SUCCESS' if result.success else 'FAILED'
    print(f'  Status       : {status}')
    print(f'  Errors       : {len(result.errors)}')
    print(f'  Warnings     : {len(result.warnings)}')
    print(f'  Time         : {result.elapsed_ms:.1f} ms')

    if result.errors:
        print('\n  Errors:')
        for e in result.errors:
            print(f'    [{e["kind"]}] L{e["line"]}:C{e["column"]}  {e["message"]}')
            if e.get('hint'):
                print(f'      hint: {e["hint"]}')


if __name__ == '__main__':
    main()
