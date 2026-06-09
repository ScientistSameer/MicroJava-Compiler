"""
Three-Address Code Generator + Basic Optimizer for MicroJava.

Bonus feature: generates TAC (Three-Address Code) from the AST,
then applies constant folding and dead-code elimination.

TAC instruction forms:
  x = y op z        BinaryOp
  x = -y            UnaryMinus
  x = y             Copy
  x = y[i]          ArrayIndex
  x[i] = y          ArrayAssign
  x = y.f           FieldAccess
  x.f = y           FieldAssign
  if x relop y goto L   CondJump
  goto L            Jump
  label L           Label
  param x           Param (push argument)
  x = call f, n     Call  (n = number of args)
  return x          Return
  x = new C         NewObject
  x = new T[n]      NewArray
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from .ast_nodes import (
    ASTNode, ProgramNode, MethodDeclNode, BlockNode,
    AssignStmtNode, CallStmtNode, IfStmtNode, WhileStmtNode,
    ReturnStmtNode, ReadStmtNode, PrintStmtNode, EmptyStmtNode,
    BinaryOpNode, UnaryMinusNode, NumberLitNode, CharLitNode,
    DesignatorNode, CallExprNode, NewObjectNode, NewArrayNode, ConditionNode,
    VarDeclNode, ConstDeclNode,
)


# --------------------------------------------------------------------------
# TAC Instruction
# --------------------------------------------------------------------------

@dataclass
class TACInstr:
    op:     str
    result: Optional[str] = None
    arg1:   Optional[str] = None
    arg2:   Optional[str] = None

    def __str__(self):
        if self.op == 'label':
            return f'{self.result}:'
        if self.op == 'goto':
            return f'    goto {self.result}'
        if self.op == 'if':
            return f'    if {self.arg1} {self.result} {self.arg2} goto ...'
        if self.op == 'cond_jump':
            return f'    if {self.arg1} goto {self.result}'
        if self.op == 'param':
            return f'    param {self.result}'
        if self.op == 'call':
            return f'    {self.result} = call {self.arg1}, {self.arg2}'
        if self.op == 'return':
            return f'    return {self.result or ""}'
        if self.op == 'copy':
            return f'    {self.result} = {self.arg1}'
        if self.op == 'unary_minus':
            return f'    {self.result} = -{self.arg1}'
        if self.op == 'read':
            return f'    read {self.result}'
        if self.op == 'print':
            return f'    print {self.result}'
        if self.op in ('+', '-', '*', '/', '%'):
            return f'    {self.result} = {self.arg1} {self.op} {self.arg2}'
        if self.op == 'array_load':
            return f'    {self.result} = {self.arg1}[{self.arg2}]'
        if self.op == 'array_store':
            return f'    {self.result}[{self.arg2}] = {self.arg1}'
        if self.op == 'field_load':
            return f'    {self.result} = {self.arg1}.{self.arg2}'
        if self.op == 'field_store':
            return f'    {self.result}.{self.arg2} = {self.arg1}'
        if self.op == 'new_obj':
            return f'    {self.result} = new {self.arg1}'
        if self.op == 'new_arr':
            return f'    {self.result} = new {self.arg1}[{self.arg2}]'
        return f'    {self.op} {self.result} {self.arg1 or ""} {self.arg2 or ""}'


# --------------------------------------------------------------------------
# Code Generator
# --------------------------------------------------------------------------

class CodeGenerator:
    def __init__(self):
        self._code: List[TACInstr] = []
        self._temp_count  = 0
        self._label_count = 0

    def _new_temp(self) -> str:
        self._temp_count += 1
        return f't{self._temp_count}'

    def _new_label(self) -> str:
        self._label_count += 1
        return f'L{self._label_count}'

    def emit(self, op: str, result=None, arg1=None, arg2=None) -> TACInstr:
        instr = TACInstr(op, result, arg1, arg2)
        self._code.append(instr)
        return instr

    def generate(self, tree: Optional[ProgramNode]) -> List[TACInstr]:
        if tree is None:
            return []
        self._gen_program(tree)
        return self._code

    def get_code(self) -> List[TACInstr]:
        return list(self._code)

    def format_code(self) -> str:
        return '\n'.join(str(i) for i in self._code)

    # ------------------------------------------------------------------

    def _gen_program(self, node: ProgramNode):
        self.emit('label', f'program_{node.name}')
        for m in node.methods:
            self._gen_method(m)

    def _gen_method(self, node: MethodDeclNode):
        self.emit('label', f'method_{node.name}')
        self._gen_block(node.body)

    def _gen_block(self, node: BlockNode):
        for stmt in node.stmts:
            self._gen_stmt(stmt)

    def _gen_stmt(self, node: ASTNode):
        if isinstance(node, AssignStmtNode):
            src = self._gen_expr(node.expr)
            des = self._designator_lval(node.target)
            if des[0] == 'simple':
                self.emit('copy', des[1], src)
            elif des[0] == 'array':
                self.emit('array_store', src, des[1], des[2])
            elif des[0] == 'field':
                self.emit('field_store', src, des[1], des[2])

        elif isinstance(node, CallStmtNode):
            for arg in node.args:
                a = self._gen_expr(arg)
                self.emit('param', a)
            self.emit('call', None, node.target.name, str(len(node.args)))

        elif isinstance(node, IfStmtNode):
            cond_var = self._gen_condition(node.cond)
            else_lbl = self._new_label()
            end_lbl  = self._new_label()
            self.emit('cond_jump_false', else_lbl, cond_var)
            self._gen_stmt(node.then_)
            if node.else_:
                self.emit('goto', end_lbl)
                self.emit('label', else_lbl)
                self._gen_stmt(node.else_)
                self.emit('label', end_lbl)
            else:
                self.emit('label', else_lbl)

        elif isinstance(node, WhileStmtNode):
            start_lbl = self._new_label()
            end_lbl   = self._new_label()
            self.emit('label', start_lbl)
            cond_var  = self._gen_condition(node.cond)
            self.emit('cond_jump_false', end_lbl, cond_var)
            self._gen_stmt(node.body)
            self.emit('goto', start_lbl)
            self.emit('label', end_lbl)

        elif isinstance(node, ReturnStmtNode):
            if node.expr:
                val = self._gen_expr(node.expr)
                self.emit('return', val)
            else:
                self.emit('return')

        elif isinstance(node, ReadStmtNode):
            des = self._designator_lval(node.target)
            self.emit('read', des[1] if des else '_')

        elif isinstance(node, PrintStmtNode):
            val = self._gen_expr(node.expr)
            self.emit('print', val)

        elif isinstance(node, BlockNode):
            self._gen_block(node)

    def _gen_condition(self, node: ConditionNode) -> str:
        lt = self._gen_expr(node.left)
        rt = self._gen_expr(node.right)
        tmp = self._new_temp()
        self.emit(f'cmp_{node.op}', tmp, lt, rt)
        return tmp

    def _gen_expr(self, node: ASTNode) -> str:
        if isinstance(node, NumberLitNode):
            return str(node.value)

        if isinstance(node, CharLitNode):
            return repr(node.value)

        if isinstance(node, DesignatorNode):
            if not node.suffixes:
                return node.name
            # Array / field access
            base = node.name
            for kind, val in node.suffixes:
                tmp = self._new_temp()
                if kind == '.':
                    self.emit('field_load', tmp, base, val)
                else:
                    idx = self._gen_expr(val)
                    self.emit('array_load', tmp, base, idx)
                base = tmp
            return base

        if isinstance(node, CallExprNode):
            for arg in node.args:
                a = self._gen_expr(arg)
                self.emit('param', a)
            tmp = self._new_temp()
            self.emit('call', tmp, node.target.name, str(len(node.args)))
            return tmp

        if isinstance(node, NewObjectNode):
            tmp = self._new_temp()
            self.emit('new_obj', tmp, node.class_name)
            return tmp

        if isinstance(node, NewArrayNode):
            size = self._gen_expr(node.size_expr)
            tmp  = self._new_temp()
            self.emit('new_arr', tmp, node.elem_type, size)
            return tmp

        if isinstance(node, UnaryMinusNode):
            inner = self._gen_expr(node.expr)
            tmp   = self._new_temp()
            self.emit('unary_minus', tmp, inner)
            return tmp

        if isinstance(node, BinaryOpNode):
            l = self._gen_expr(node.left)
            r = self._gen_expr(node.right)
            tmp = self._new_temp()
            self.emit(node.op, tmp, l, r)
            return tmp

        return '_unknown_'

    def _designator_lval(self, node: DesignatorNode):
        if not node.suffixes:
            return ('simple', node.name)
        base = node.name
        suffixes = node.suffixes
        for i, (kind, val) in enumerate(suffixes[:-1]):
            tmp = self._new_temp()
            if kind == '.':
                self.emit('field_load', tmp, base, val)
            else:
                idx = self._gen_expr(val)
                self.emit('array_load', tmp, base, idx)
            base = tmp
        last_kind, last_val = suffixes[-1]
        if last_kind == '.':
            return ('field', base, last_val)
        else:
            idx = self._gen_expr(last_val)
            return ('array', base, idx)


# --------------------------------------------------------------------------
# Constant Folding Optimizer (bonus feature)
# --------------------------------------------------------------------------

class ConstantFolder:
    """
    Walks TAC instructions and evaluates constant binary expressions at
    compile time, replacing them with direct assignments.
    """

    def optimize(self, code: List[TACInstr]) -> List[TACInstr]:
        changed = True
        constants: Dict[str, Any] = {}

        while changed:
            changed = False
            new_code = []
            for instr in code:
                optimized = self._fold(instr, constants)
                if optimized != instr:
                    changed = True
                new_code.append(optimized)
            code = new_code

        return code

    def _fold(self, instr: TACInstr,
              constants: Dict[str, Any]) -> TACInstr:
        op  = instr.op
        a1  = instr.arg1
        a2  = instr.arg2
        res = instr.result

        # Resolve known constants
        a1v = constants.get(a1, a1) if a1 else a1
        a2v = constants.get(a2, a2) if a2 else a2

        try:
            v1 = int(a1v) if a1v is not None else None
            v2 = int(a2v) if a2v is not None else None
        except (ValueError, TypeError):
            v1 = v2 = None

        if op == 'copy' and a1v is not None:
            try:
                constants[res] = int(a1v)
            except (ValueError, TypeError):
                pass
            return instr

        if op in ('+', '-', '*', '/', '%') and v1 is not None and v2 is not None:
            try:
                if op == '+':  val = v1 + v2
                elif op == '-': val = v1 - v2
                elif op == '*': val = v1 * v2
                elif op == '/' and v2 != 0: val = v1 // v2
                elif op == '%' and v2 != 0: val = v1 % v2
                else:
                    return instr
                constants[res] = val
                return TACInstr('copy', res, str(val))
            except Exception:
                pass

        if op == 'unary_minus' and v1 is not None:
            constants[res] = -v1
            return TACInstr('copy', res, str(-v1))

        return instr


# --------------------------------------------------------------------------
# Dead Code Eliminator (bonus feature)
# --------------------------------------------------------------------------

class DeadCodeEliminator:
    """
    Removes TAC instructions whose result is never used.
    (Simple single-pass liveness analysis.)
    """

    def optimize(self, code: List[TACInstr]) -> List[TACInstr]:
        # Compute used variables
        used: set = set()
        for instr in reversed(code):
            if instr.op not in ('label', 'goto', 'cond_jump', 'cond_jump_false',
                                 'param', 'call', 'return', 'read', 'print',
                                 'array_store', 'field_store', 'cond_jump_false'):
                # Mark args as used
                if instr.arg1:
                    used.add(instr.arg1)
                if instr.arg2:
                    used.add(instr.arg2)

        # Keep instructions whose result is used (or side-effecting)
        result = []
        for instr in code:
            side_effect = instr.op in (
                'label', 'goto', 'cond_jump', 'cond_jump_false',
                'param', 'call', 'return', 'read', 'print',
                'array_store', 'field_store',
            )
            if side_effect or instr.result is None or instr.result in used:
                result.append(instr)
        return result
