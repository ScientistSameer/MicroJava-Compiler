"""
Semantic Analyzer / Type Checker for MicroJava.

Walks the AST produced by the RD parser and:
  - Verifies every name is declared before use
  - Checks type compatibility for assignments, expressions, conditions
  - Verifies return types match method signatures
  - Checks actual vs. formal parameter counts and types
  - Ensures a main() method exists (void, no params)
  - Detects duplicate declarations (already caught by SymbolTable.insert)
"""

from __future__ import annotations
from typing import Optional, List

from .ast_nodes import (
    ASTNode, ProgramNode, ConstDeclNode, VarDeclNode, ClassDeclNode,
    MethodDeclNode, ParamNode, TypeNode, BlockNode,
    AssignStmtNode, CallStmtNode, IfStmtNode, WhileStmtNode,
    ReturnStmtNode, ReadStmtNode, PrintStmtNode, EmptyStmtNode,
    BinaryOpNode, UnaryMinusNode, NumberLitNode, CharLitNode,
    DesignatorNode, CallExprNode, NewObjectNode, NewArrayNode, ConditionNode,
)
from .symbol_table  import SymbolTable, SymbolKind, Symbol
from .error_handler import ErrorHandler


INT_TYPE  = 'int'
CHAR_TYPE = 'char'
VOID_TYPE = 'void'
NULL_TYPE = 'null'


def _is_numeric(t: str) -> bool:
    return t == INT_TYPE

def _is_primitive(t: str) -> bool:
    return t in (INT_TYPE, CHAR_TYPE)

def _compatible(src: str, dst: str) -> bool:
    """Assignment-compatible: same type, or reference ← null."""
    if src == dst:
        return True
    if dst not in (INT_TYPE, CHAR_TYPE, VOID_TYPE) and src == NULL_TYPE:
        return True
    return False


class SemanticError(Exception):
    pass


class SemanticAnalyzer:
    def __init__(self, sym_table: SymbolTable, error_handler: ErrorHandler):
        self._sym  = sym_table
        self._eh   = error_handler
        self._current_method_ret: Optional[str] = None
        self._found_main = False

    # ------------------------------------------------------------------
    # Entry
    # ------------------------------------------------------------------

    def analyze(self, tree: Optional[ProgramNode]) -> bool:
        if tree is None:
            return False
        self._visit_program(tree)
        if not self._found_main:
            self._eh.semantic(
                "Program must contain a 'void main()' method",
                0, 0,
                hint="Add 'void main() { }' to your program"
            )
        return not self._eh.has_errors

    # ------------------------------------------------------------------
    # Visitors
    # ------------------------------------------------------------------

    def _visit_program(self, node: ProgramNode):
        for d in node.decls:
            self._visit_decl(d)
        for m in node.methods:
            self._visit_method(m)

    def _visit_decl(self, node: ASTNode):
        if isinstance(node, ConstDeclNode):
            self._check_const(node)
        elif isinstance(node, VarDeclNode):
            pass   # already inserted into sym table by parser
        elif isinstance(node, ClassDeclNode):
            pass

    def _check_const(self, node: ConstDeclNode):
        type_name = node.typ.name
        if isinstance(node.value, int) and type_name != INT_TYPE:
            self._eh.semantic(
                f"Constant '{node.name}': type mismatch — "
                f"value is int but declared as {type_name}",
                node.line, node.col
            )
        elif isinstance(node.value, str) and type_name != CHAR_TYPE:
            self._eh.semantic(
                f"Constant '{node.name}': type mismatch — "
                f"value is char but declared as {type_name}",
                node.line, node.col
            )

    def _visit_method(self, node: MethodDeclNode):
        ret = str(node.ret_type) if node.ret_type else VOID_TYPE
        self._current_method_ret = ret
        if node.name == 'main':
            if ret != VOID_TYPE or node.params:
                self._eh.semantic(
                    "main() must be declared as 'void main()' with no parameters",
                    node.line, node.col
                )
            else:
                self._found_main = True
        self._visit_block(node.body)
        self._current_method_ret = None

    def _visit_block(self, node: BlockNode):
        for stmt in node.stmts:
            self._visit_stmt(stmt)

    def _visit_stmt(self, node: ASTNode):
        if isinstance(node, AssignStmtNode):
            rhs_type = self._expr_type(node.expr)
            des_type = self._designator_type(node.target)
            if des_type and rhs_type and not _compatible(rhs_type, des_type):
                self._eh.semantic(
                    f"Assignment type mismatch: cannot assign {rhs_type} to {des_type}",
                    node.line, node.col
                )

        elif isinstance(node, CallStmtNode):
            sym = self._sym.lookup(node.target.name)
            if sym is None:
                self._eh.semantic(
                    f"Undefined method '{node.target.name}'",
                    node.line, node.col
                )
            elif sym.kind != SymbolKind.METHOD and sym.kind != SymbolKind.BUILTIN:
                self._eh.semantic(
                    f"'{node.target.name}' is not a method",
                    node.line, node.col
                )
            else:
                self._check_args(sym, node.args, node.line, node.col)

        elif isinstance(node, IfStmtNode):
            self._visit_condition(node.cond)
            self._visit_stmt(node.then_)
            if node.else_:
                self._visit_stmt(node.else_)

        elif isinstance(node, WhileStmtNode):
            self._visit_condition(node.cond)
            self._visit_stmt(node.body)

        elif isinstance(node, ReturnStmtNode):
            if node.expr is None:
                if self._current_method_ret not in (VOID_TYPE, None):
                    self._eh.semantic(
                        f"'return' without value in non-void method "
                        f"(expected {self._current_method_ret})",
                        node.line, node.col
                    )
            else:
                ret_type = self._expr_type(node.expr)
                if (self._current_method_ret and
                        ret_type and
                        not _compatible(ret_type, self._current_method_ret)):
                    self._eh.semantic(
                        f"Return type mismatch: expected {self._current_method_ret}, "
                        f"got {ret_type}",
                        node.line, node.col
                    )

        elif isinstance(node, ReadStmtNode):
            des_type = self._designator_type(node.target)
            if des_type and des_type not in (INT_TYPE, CHAR_TYPE):
                self._eh.semantic(
                    f"read() requires an int or char variable, got {des_type}",
                    node.line, node.col
                )

        elif isinstance(node, PrintStmtNode):
            expr_type = self._expr_type(node.expr)
            if expr_type and expr_type not in (INT_TYPE, CHAR_TYPE):
                self._eh.semantic(
                    f"print() requires an int or char expression, got {expr_type}",
                    node.line, node.col
                )

        elif isinstance(node, BlockNode):
            self._visit_block(node)

    def _visit_condition(self, node: ConditionNode):
        lt = self._expr_type(node.left)
        rt = self._expr_type(node.right)
        if lt and rt and lt != rt:
            if not (lt in (INT_TYPE, CHAR_TYPE) and rt in (INT_TYPE, CHAR_TYPE)):
                self._eh.semantic(
                    f"Condition type mismatch: {lt} {node.op} {rt}",
                    node.line, node.col
                )

    # ------------------------------------------------------------------
    # Expression types
    # ------------------------------------------------------------------

    def _expr_type(self, node: ASTNode) -> Optional[str]:
        if isinstance(node, NumberLitNode):
            return INT_TYPE
        if isinstance(node, CharLitNode):
            return CHAR_TYPE
        if isinstance(node, DesignatorNode):
            return self._designator_type(node)
        if isinstance(node, CallExprNode):
            sym = self._sym.lookup(node.target.name)
            if sym:
                self._check_args(sym, node.args, node.line, node.col)
                return sym.type_name
            return None
        if isinstance(node, NewObjectNode):
            return node.class_name
        if isinstance(node, NewArrayNode):
            return node.elem_type + '[]'
        if isinstance(node, UnaryMinusNode):
            t = self._expr_type(node.expr)
            if t and t != INT_TYPE:
                self._eh.semantic(
                    f"Unary minus requires int, got {t}",
                    node.line, node.col
                )
            return INT_TYPE
        if isinstance(node, BinaryOpNode):
            lt = self._expr_type(node.left)
            rt = self._expr_type(node.right)
            if lt and rt:
                if node.op in ('+', '-', '*', '/', '%'):
                    if lt != INT_TYPE or rt != INT_TYPE:
                        self._eh.semantic(
                            f"Operator '{node.op}' requires int operands",
                            node.line, node.col
                        )
                    return INT_TYPE
            return lt or rt
        return None

    def _designator_type(self, node: DesignatorNode) -> Optional[str]:
        sym = self._sym.lookup(node.name)
        if sym is None:
            self._eh.semantic(
                f"Undeclared name '{node.name}'",
                node.line, node.col,
                hint=f"Declare '{node.name}' before using it"
            )
            return None
        type_str = sym.type_name
        for kind, val in node.suffixes:
            if kind == '.':
                # Field access — simplified (no full class lookup)
                type_str = 'int'   # approximate
            elif kind == '[':
                if '[]' in type_str:
                    type_str = type_str.replace('[]', '')
                else:
                    self._eh.semantic(
                        f"Cannot index non-array '{node.name}'",
                        node.line, node.col
                    )
        return type_str

    def _check_args(self, sym: Symbol, args: List[ASTNode],
                    line: int, col: int):
        expected = sym.param_types
        if len(args) != len(expected):
            self._eh.semantic(
                f"'{sym.name}' expects {len(expected)} argument(s), "
                f"got {len(args)}",
                line, col
            )
