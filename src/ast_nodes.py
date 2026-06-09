"""
AST Node definitions for MicroJava.
Each non-terminal in the grammar maps to one or more node classes.
Nodes carry their source position (line, column) for error reporting.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Any


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class ASTNode:
    def __init__(self, line: int = 0, col: int = 0):
        self.line = line
        self.col  = col

    def accept(self, visitor):
        method = f'visit_{type(self).__name__}'
        return getattr(visitor, method, visitor.generic_visit)(self)

    # --- tree-printing helpers ---

    def _indent(self, level: int) -> str:
        return '  ' * level

    def to_str(self, level: int = 0) -> str:
        return self._indent(level) + type(self).__name__

    def __str__(self):
        return self.to_str()


# ---------------------------------------------------------------------------
# Program-level nodes
# ---------------------------------------------------------------------------

class ProgramNode(ASTNode):
    def __init__(self, name: str, decls: List[ASTNode],
                 methods: List['MethodDeclNode'], line=0, col=0):
        super().__init__(line, col)
        self.name    = name
        self.decls   = decls      # list of ConstDeclNode | VarDeclNode | ClassDeclNode
        self.methods = methods

    def to_str(self, level=0):
        lines = [self._indent(level) + f'Program({self.name!r})']
        for d in self.decls:
            lines.append(d.to_str(level + 1))
        for m in self.methods:
            lines.append(m.to_str(level + 1))
        return '\n'.join(lines)


class ConstDeclNode(ASTNode):
    def __init__(self, typ: 'TypeNode', name: str,
                 value: Any, line=0, col=0):
        super().__init__(line, col)
        self.typ   = typ
        self.name  = name
        self.value = value   # int or str (char)

    def to_str(self, level=0):
        return self._indent(level) + f'ConstDecl({self.name!r} : {self.typ} = {self.value!r})'


class VarDeclNode(ASTNode):
    def __init__(self, typ: 'TypeNode', names: List[str], line=0, col=0):
        super().__init__(line, col)
        self.typ   = typ
        self.names = names

    def to_str(self, level=0):
        return self._indent(level) + f'VarDecl({self.typ} {", ".join(self.names)})'


class ClassDeclNode(ASTNode):
    def __init__(self, name: str, fields: List[VarDeclNode], line=0, col=0):
        super().__init__(line, col)
        self.name   = name
        self.fields = fields

    def to_str(self, level=0):
        lines = [self._indent(level) + f'ClassDecl({self.name!r})']
        for f in self.fields:
            lines.append(f.to_str(level + 1))
        return '\n'.join(lines)


class MethodDeclNode(ASTNode):
    def __init__(self, ret_type: Optional['TypeNode'], name: str,
                 params: List['ParamNode'],
                 locals_: List[VarDeclNode],
                 body: 'BlockNode', line=0, col=0):
        super().__init__(line, col)
        self.ret_type = ret_type   # None means void
        self.name     = name
        self.params   = params
        self.locals_  = locals_
        self.body     = body

    def to_str(self, level=0):
        ret = str(self.ret_type) if self.ret_type else 'void'
        params = ', '.join(str(p) for p in self.params)
        lines = [self._indent(level) + f'Method({ret} {self.name!r}({params}))']
        for loc in self.locals_:
            lines.append(loc.to_str(level + 1))
        lines.append(self.body.to_str(level + 1))
        return '\n'.join(lines)


class ParamNode(ASTNode):
    def __init__(self, typ: 'TypeNode', name: str, line=0, col=0):
        super().__init__(line, col)
        self.typ  = typ
        self.name = name

    def __str__(self):
        return f'{self.typ} {self.name}'


class TypeNode(ASTNode):
    def __init__(self, name: str, is_array: bool = False, line=0, col=0):
        super().__init__(line, col)
        self.name     = name
        self.is_array = is_array

    def __str__(self):
        return self.name + ('[]' if self.is_array else '')


# ---------------------------------------------------------------------------
# Statement nodes
# ---------------------------------------------------------------------------

class BlockNode(ASTNode):
    def __init__(self, stmts: List[ASTNode], line=0, col=0):
        super().__init__(line, col)
        self.stmts = stmts

    def to_str(self, level=0):
        lines = [self._indent(level) + 'Block']
        for s in self.stmts:
            lines.append(s.to_str(level + 1))
        return '\n'.join(lines)


class AssignStmtNode(ASTNode):
    def __init__(self, target: 'DesignatorNode', expr: ASTNode, line=0, col=0):
        super().__init__(line, col)
        self.target = target
        self.expr   = expr

    def to_str(self, level=0):
        lines = [self._indent(level) + 'Assign']
        lines.append(self.target.to_str(level + 1))
        lines.append(self.expr.to_str(level + 1))
        return '\n'.join(lines)


class CallStmtNode(ASTNode):
    def __init__(self, target: 'DesignatorNode', args: List[ASTNode], line=0, col=0):
        super().__init__(line, col)
        self.target = target
        self.args   = args

    def to_str(self, level=0):
        lines = [self._indent(level) + f'Call({self.target})']
        for a in self.args:
            lines.append(a.to_str(level + 1))
        return '\n'.join(lines)


class IfStmtNode(ASTNode):
    def __init__(self, cond: 'ConditionNode', then_: ASTNode,
                 else_: Optional[ASTNode], line=0, col=0):
        super().__init__(line, col)
        self.cond  = cond
        self.then_ = then_
        self.else_ = else_

    def to_str(self, level=0):
        lines = [self._indent(level) + 'If']
        lines.append(self.cond.to_str(level + 1))
        lines.append(self._indent(level + 1) + 'then:')
        lines.append(self.then_.to_str(level + 2))
        if self.else_:
            lines.append(self._indent(level + 1) + 'else:')
            lines.append(self.else_.to_str(level + 2))
        return '\n'.join(lines)


class WhileStmtNode(ASTNode):
    def __init__(self, cond: 'ConditionNode', body: ASTNode, line=0, col=0):
        super().__init__(line, col)
        self.cond = cond
        self.body = body

    def to_str(self, level=0):
        lines = [self._indent(level) + 'While']
        lines.append(self.cond.to_str(level + 1))
        lines.append(self.body.to_str(level + 1))
        return '\n'.join(lines)


class ReturnStmtNode(ASTNode):
    def __init__(self, expr: Optional[ASTNode], line=0, col=0):
        super().__init__(line, col)
        self.expr = expr

    def to_str(self, level=0):
        lines = [self._indent(level) + 'Return']
        if self.expr:
            lines.append(self.expr.to_str(level + 1))
        return '\n'.join(lines)


class ReadStmtNode(ASTNode):
    def __init__(self, target: 'DesignatorNode', line=0, col=0):
        super().__init__(line, col)
        self.target = target

    def to_str(self, level=0):
        return self._indent(level) + f'Read({self.target})'


class PrintStmtNode(ASTNode):
    def __init__(self, expr: ASTNode, width: Optional[int], line=0, col=0):
        super().__init__(line, col)
        self.expr  = expr
        self.width = width

    def to_str(self, level=0):
        w = f', {self.width}' if self.width is not None else ''
        lines = [self._indent(level) + f'Print{w}']
        lines.append(self.expr.to_str(level + 1))
        return '\n'.join(lines)


class EmptyStmtNode(ASTNode):
    def to_str(self, level=0):
        return self._indent(level) + 'EmptyStmt'


# ---------------------------------------------------------------------------
# Expression nodes
# ---------------------------------------------------------------------------

class BinaryOpNode(ASTNode):
    def __init__(self, op: str, left: ASTNode, right: ASTNode,
                 line=0, col=0):
        super().__init__(line, col)
        self.op    = op
        self.left  = left
        self.right = right

    def to_str(self, level=0):
        lines = [self._indent(level) + f'BinOp({self.op!r})']
        lines.append(self.left.to_str(level + 1))
        lines.append(self.right.to_str(level + 1))
        return '\n'.join(lines)


class UnaryMinusNode(ASTNode):
    def __init__(self, expr: ASTNode, line=0, col=0):
        super().__init__(line, col)
        self.expr = expr

    def to_str(self, level=0):
        lines = [self._indent(level) + 'UnaryMinus']
        lines.append(self.expr.to_str(level + 1))
        return '\n'.join(lines)


class NumberLitNode(ASTNode):
    def __init__(self, value: int, line=0, col=0):
        super().__init__(line, col)
        self.value = value

    def to_str(self, level=0):
        return self._indent(level) + f'Number({self.value})'


class CharLitNode(ASTNode):
    def __init__(self, value: str, line=0, col=0):
        super().__init__(line, col)
        self.value = value

    def to_str(self, level=0):
        return self._indent(level) + f'Char({self.value!r})'


class DesignatorNode(ASTNode):
    def __init__(self, name: str, suffixes: List[Any], line=0, col=0):
        super().__init__(line, col)
        self.name     = name
        self.suffixes = suffixes   # list of ('.', 'field') or ('[', expr)

    def __str__(self):
        s = self.name
        for kind, val in self.suffixes:
            if kind == '.':
                s += f'.{val}'
            else:
                s += f'[{val}]'
        return s

    def to_str(self, level=0):
        return self._indent(level) + f'Designator({self})'


class CallExprNode(ASTNode):
    def __init__(self, target: DesignatorNode, args: List[ASTNode],
                 line=0, col=0):
        super().__init__(line, col)
        self.target = target
        self.args   = args

    def to_str(self, level=0):
        lines = [self._indent(level) + f'CallExpr({self.target})']
        for a in self.args:
            lines.append(a.to_str(level + 1))
        return '\n'.join(lines)


class NewObjectNode(ASTNode):
    def __init__(self, class_name: str, line=0, col=0):
        super().__init__(line, col)
        self.class_name = class_name

    def to_str(self, level=0):
        return self._indent(level) + f'NewObject({self.class_name!r})'


class NewArrayNode(ASTNode):
    def __init__(self, elem_type: str, size_expr: ASTNode, line=0, col=0):
        super().__init__(line, col)
        self.elem_type = elem_type
        self.size_expr = size_expr

    def to_str(self, level=0):
        lines = [self._indent(level) + f'NewArray({self.elem_type!r})']
        lines.append(self.size_expr.to_str(level + 1))
        return '\n'.join(lines)


class ConditionNode(ASTNode):
    def __init__(self, left: ASTNode, op: str, right: ASTNode,
                 line=0, col=0):
        super().__init__(line, col)
        self.left  = left
        self.op    = op
        self.right = right

    def to_str(self, level=0):
        lines = [self._indent(level) + f'Condition({self.op!r})']
        lines.append(self.left.to_str(level + 1))
        lines.append(self.right.to_str(level + 1))
        return '\n'.join(lines)
