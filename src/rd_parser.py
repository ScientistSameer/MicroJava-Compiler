"""
Recursive Descent Parser for MicroJava (Lab 4 / Lab 9 extended).

One parsing method per non-terminal. Builds a full AST while parsing.
Reports syntactic errors through the ErrorHandler and attempts panic-mode
recovery to continue after an error.

Grammar (left-recursion-free):
  Program  → 'program' ident Decls '{' MethodDecls '}'
  Decls    → (ConstDecl | VarDecl | ClassDecl)*
  ConstDecl→ 'final' Type ident '=' (number|charConst) ';'
  VarDecl  → Type ident {',' ident} ';'
  ClassDecl→ 'class' ident '{' VarDecl* '}'
  MethodDecl→ (Type|'void') ident '(' [FormPars] ')' VarDecl* Block
  FormPars → Type ident {',' Type ident}
  Type     → ident ['[' ']']
  Block    → '{' Statement* '}'
  Statement→ Designator ('=' Expr | ActPars) ';'
           | 'if' '(' Condition ')' Statement ['else' Statement]
           | 'while' '(' Condition ')' Statement
           | 'return' [Expr] ';'
           | 'read' '(' Designator ')' ';'
           | 'print' '(' Expr [',' number] ')' ';'
           | Block | ';'
  ActPars  → '(' [Expr {',' Expr}] ')'
  Condition→ Expr relop Expr
  Expr     → ['-'] Term {Addop Term}
  Term     → Factor {Mulop Factor}
  Factor   → Designator [ActPars] | number | charConst
           | 'new' ident ['[' Expr ']'] | '(' Expr ')'
  Designator→ ident {'.' ident | '[' Expr ']'}
"""

from __future__ import annotations
from typing import List, Optional, Tuple

from .token  import Token, TokenType
from .lexer  import Lexer
from .ast_nodes import (
    ASTNode, ProgramNode, ConstDeclNode, VarDeclNode, ClassDeclNode,
    MethodDeclNode, ParamNode, TypeNode, BlockNode,
    AssignStmtNode, CallStmtNode, IfStmtNode, WhileStmtNode,
    ReturnStmtNode, ReadStmtNode, PrintStmtNode, EmptyStmtNode,
    BinaryOpNode, UnaryMinusNode, NumberLitNode, CharLitNode,
    DesignatorNode, CallExprNode, NewObjectNode, NewArrayNode, ConditionNode,
)
from .error_handler import ErrorHandler
from .symbol_table  import SymbolTable, SymbolKind


# --------------------------------------------------------------------------
# Token-type sets used for FIRST / synchronisation
# --------------------------------------------------------------------------

_DECL_FIRST  = {TokenType.FINAL, TokenType.CLASS,
                TokenType.INT, TokenType.CHAR, TokenType.IDENT}
_TYPE_FIRST  = {TokenType.INT, TokenType.CHAR, TokenType.IDENT}
_STMT_FIRST  = {TokenType.IDENT, TokenType.IF, TokenType.WHILE,
                TokenType.RETURN, TokenType.READ, TokenType.PRINT,
                TokenType.LBRACE, TokenType.SEMICOLON}
_EXPR_FIRST  = {TokenType.MINUS, TokenType.IDENT, TokenType.NUMBER,
                TokenType.CHAR_CONST, TokenType.NEW, TokenType.LPAREN}


class ParseError(Exception):
    pass


class RDParser:
    """
    Recursive-descent parser.  Consumes the full token list produced by
    the Lexer, builds an AST, and populates the SymbolTable.
    """

    def __init__(self, tokens: List[Token],
                 error_handler: ErrorHandler,
                 sym_table: SymbolTable):
        self._tokens  = tokens
        self._pos     = 0
        self._eh      = error_handler
        self._sym     = sym_table
        self._trace: List[str] = []   # optional parse trace

    # ------------------------------------------------------------------
    # Token access
    # ------------------------------------------------------------------

    @property
    def _current(self) -> Token:
        return self._tokens[min(self._pos, len(self._tokens) - 1)]

    def _peek(self, offset: int = 0) -> Token:
        idx = self._pos + offset
        return self._tokens[min(idx, len(self._tokens) - 1)]

    def _match(self, tt: TokenType) -> Token:
        tok = self._current
        if tok.type == tt:
            self._pos += 1
            self._trace.append(f'match {tt.name} ({tok.value!r})')
            return tok
        # Error — report but try to continue
        self._error(f"Expected '{tt.value}', found '{tok.value}' ({tok.type.name})",
                    tok,
                    hint=f"Insert '{tt.value}' before '{tok.value}'")
        # Return a synthetic token so callers don't crash
        return Token(tt, '', tok.line, tok.column)

    def _error(self, msg: str, tok: Token, hint: str = None):
        self._eh.syntactic(msg, tok.line, tok.column, hint)
        self._trace.append(f'ERROR: {msg}')

    def _skip_to(self, sync_set: set):
        """Panic-mode: discard tokens until one in sync_set (or EOF)."""
        while (self._current.type != TokenType.EOF
               and self._current.type not in sync_set):
            self._pos += 1

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def parse(self) -> Optional[ProgramNode]:
        try:
            node = self._parse_program()
            if self._current.type != TokenType.EOF:
                self._error(
                    f"Trailing tokens after end of program",
                    self._current)
            return node
        except ParseError:
            return None

    def get_trace(self) -> List[str]:
        return list(self._trace)

    # ------------------------------------------------------------------
    # Grammar rules
    # ------------------------------------------------------------------

    def _parse_program(self) -> ProgramNode:
        tok = self._match(TokenType.PROGRAM)
        name_tok = self._match(TokenType.IDENT)
        name = name_tok.value

        self._sym.open_scope()
        decls: List[ASTNode] = []
        while self._current.type in _DECL_FIRST:
            try:
                if self._current.type == TokenType.FINAL:
                    decls.append(self._parse_const_decl())
                elif self._current.type == TokenType.CLASS:
                    decls.append(self._parse_class_decl())
                else:
                    decls += self._parse_var_decl()
            except ParseError:
                self._skip_to({TokenType.FINAL, TokenType.CLASS,
                               TokenType.INT, TokenType.CHAR, TokenType.IDENT,
                               TokenType.LBRACE})

        self._match(TokenType.LBRACE)
        methods: List[MethodDeclNode] = []
        while self._current.type in {TokenType.VOID, *_TYPE_FIRST}:
            try:
                methods.append(self._parse_method_decl())
            except ParseError:
                self._skip_to({TokenType.VOID, TokenType.INT, TokenType.CHAR,
                               TokenType.IDENT, TokenType.RBRACE})
        self._match(TokenType.RBRACE)
        self._sym.close_scope()
        return ProgramNode(name, decls, methods, tok.line, tok.column)

    def _parse_const_decl(self) -> ConstDeclNode:
        tok = self._match(TokenType.FINAL)
        typ = self._parse_type()
        name_tok = self._match(TokenType.IDENT)
        self._match(TokenType.ASSIGN)
        if self._current.type == TokenType.NUMBER:
            val_tok = self._match(TokenType.NUMBER)
            value = val_tok.literal
        elif self._current.type == TokenType.CHAR_CONST:
            val_tok = self._match(TokenType.CHAR_CONST)
            value = val_tok.literal
        else:
            self._error("Expected number or char constant", self._current)
            value = 0
        self._match(TokenType.SEMICOLON)
        node = ConstDeclNode(typ, name_tok.value, value, tok.line, tok.column)
        self._sym.insert_const(name_tok.value, str(typ), value,
                               name_tok.line, name_tok.column)
        return node

    def _parse_var_decl(self) -> List[VarDeclNode]:
        """Returns a list because one VarDecl can declare multiple names."""
        tok = self._current
        typ = self._parse_type()
        names = [self._match(TokenType.IDENT).value]
        while self._current.type == TokenType.COMMA:
            self._match(TokenType.COMMA)
            names.append(self._match(TokenType.IDENT).value)
        self._match(TokenType.SEMICOLON)
        for n in names:
            self._sym.insert_var(n, str(typ), tok.line, tok.column)
        return [VarDeclNode(typ, names, tok.line, tok.column)]

    def _parse_class_decl(self) -> ClassDeclNode:
        tok = self._match(TokenType.CLASS)
        name_tok = self._match(TokenType.IDENT)
        self._match(TokenType.LBRACE)
        self._sym.open_scope(class_name=name_tok.value)
        fields: List[VarDeclNode] = []
        while self._current.type in _TYPE_FIRST:
            fields += self._parse_var_decl()
        self._match(TokenType.RBRACE)
        self._sym.close_scope()
        self._sym.insert_class(name_tok.value, tok.line, tok.column)
        return ClassDeclNode(name_tok.value, fields, tok.line, tok.column)

    def _parse_method_decl(self) -> MethodDeclNode:
        tok = self._current
        if self._current.type == TokenType.VOID:
            self._match(TokenType.VOID)
            ret_type = None
        else:
            ret_type = self._parse_type()

        name_tok = self._match(TokenType.IDENT)
        self._sym.open_scope(method_name=name_tok.value)

        self._match(TokenType.LPAREN)
        params: List[ParamNode] = []
        if self._current.type in _TYPE_FIRST:
            params = self._parse_form_pars()
        self._match(TokenType.RPAREN)

        locals_: List[VarDeclNode] = []
        while self._current.type in _TYPE_FIRST:
            locals_ += self._parse_var_decl()

        body = self._parse_block()
        self._sym.close_scope()

        ret_str = str(ret_type) if ret_type else 'void'
        param_types = [str(p.typ) for p in params]
        self._sym.insert_method(name_tok.value, ret_str, param_types,
                                tok.line, tok.column)
        return MethodDeclNode(ret_type, name_tok.value, params, locals_,
                              body, tok.line, tok.column)

    def _parse_form_pars(self) -> List[ParamNode]:
        params = []
        typ = self._parse_type()
        name_tok = self._match(TokenType.IDENT)
        self._sym.insert_var(name_tok.value, str(typ), name_tok.line,
                             name_tok.column, kind=SymbolKind.PARAM)
        params.append(ParamNode(typ, name_tok.value, name_tok.line, name_tok.column))
        while self._current.type == TokenType.COMMA:
            self._match(TokenType.COMMA)
            typ = self._parse_type()
            name_tok = self._match(TokenType.IDENT)
            self._sym.insert_var(name_tok.value, str(typ), name_tok.line,
                                 name_tok.column, kind=SymbolKind.PARAM)
            params.append(ParamNode(typ, name_tok.value, name_tok.line, name_tok.column))
        return params

    def _parse_type(self) -> TypeNode:
        tok = self._current
        if tok.type not in _TYPE_FIRST:
            self._error(f"Expected type name, found {tok.value!r}", tok)
            return TypeNode('int', False, tok.line, tok.column)
        name_tok = self._match(tok.type)
        is_array = False
        if self._current.type == TokenType.LBRACK:
            self._match(TokenType.LBRACK)
            self._match(TokenType.RBRACK)
            is_array = True
        return TypeNode(name_tok.value, is_array, tok.line, tok.column)

    def _parse_block(self) -> BlockNode:
        tok = self._match(TokenType.LBRACE)
        stmts: List[ASTNode] = []
        while (self._current.type != TokenType.RBRACE
               and self._current.type != TokenType.EOF):
            try:
                stmts.append(self._parse_statement())
            except ParseError:
                self._skip_to({*_STMT_FIRST, TokenType.RBRACE})
        self._match(TokenType.RBRACE)
        return BlockNode(stmts, tok.line, tok.column)

    def _parse_statement(self) -> ASTNode:
        tok = self._current

        if tok.type == TokenType.IDENT:
            des = self._parse_designator()
            if self._current.type == TokenType.ASSIGN:
                self._match(TokenType.ASSIGN)
                expr = self._parse_expr()
                self._match(TokenType.SEMICOLON)
                return AssignStmtNode(des, expr, tok.line, tok.column)
            elif self._current.type == TokenType.LPAREN:
                args = self._parse_act_pars()
                self._match(TokenType.SEMICOLON)
                return CallStmtNode(des, args, tok.line, tok.column)
            else:
                self._error(
                    f"Expected '=' or '(' after designator, found {self._current.value!r}",
                    self._current)
                self._skip_to({TokenType.SEMICOLON})
                self._match(TokenType.SEMICOLON)
                return EmptyStmtNode(tok.line, tok.column)

        if tok.type == TokenType.IF:
            return self._parse_if()
        if tok.type == TokenType.WHILE:
            return self._parse_while()
        if tok.type == TokenType.RETURN:
            return self._parse_return()
        if tok.type == TokenType.READ:
            return self._parse_read()
        if tok.type == TokenType.PRINT:
            return self._parse_print()
        if tok.type == TokenType.LBRACE:
            return self._parse_block()
        if tok.type == TokenType.SEMICOLON:
            self._match(TokenType.SEMICOLON)
            return EmptyStmtNode(tok.line, tok.column)

        self._error(f"Unexpected token in statement: {tok.value!r}", tok)
        self._skip_to({TokenType.SEMICOLON, TokenType.RBRACE})
        if self._current.type == TokenType.SEMICOLON:
            self._match(TokenType.SEMICOLON)
        return EmptyStmtNode(tok.line, tok.column)

    def _parse_if(self) -> IfStmtNode:
        tok = self._match(TokenType.IF)
        self._match(TokenType.LPAREN)
        cond = self._parse_condition()
        self._match(TokenType.RPAREN)
        then_ = self._parse_statement()
        else_ = None
        if self._current.type == TokenType.ELSE:
            self._match(TokenType.ELSE)
            else_ = self._parse_statement()
        return IfStmtNode(cond, then_, else_, tok.line, tok.column)

    def _parse_while(self) -> WhileStmtNode:
        tok = self._match(TokenType.WHILE)
        self._match(TokenType.LPAREN)
        cond = self._parse_condition()
        self._match(TokenType.RPAREN)
        body = self._parse_statement()
        return WhileStmtNode(cond, body, tok.line, tok.column)

    def _parse_return(self) -> ReturnStmtNode:
        tok = self._match(TokenType.RETURN)
        expr = None
        if self._current.type in _EXPR_FIRST:
            expr = self._parse_expr()
        self._match(TokenType.SEMICOLON)
        return ReturnStmtNode(expr, tok.line, tok.column)

    def _parse_read(self) -> ReadStmtNode:
        tok = self._match(TokenType.READ)
        self._match(TokenType.LPAREN)
        des = self._parse_designator()
        self._match(TokenType.RPAREN)
        self._match(TokenType.SEMICOLON)
        return ReadStmtNode(des, tok.line, tok.column)

    def _parse_print(self) -> PrintStmtNode:
        tok = self._match(TokenType.PRINT)
        self._match(TokenType.LPAREN)
        expr = self._parse_expr()
        width = None
        if self._current.type == TokenType.COMMA:
            self._match(TokenType.COMMA)
            w_tok = self._match(TokenType.NUMBER)
            width = w_tok.literal
        self._match(TokenType.RPAREN)
        self._match(TokenType.SEMICOLON)
        return PrintStmtNode(expr, width, tok.line, tok.column)

    def _parse_act_pars(self) -> List[ASTNode]:
        self._match(TokenType.LPAREN)
        args: List[ASTNode] = []
        if self._current.type in _EXPR_FIRST:
            args.append(self._parse_expr())
            while self._current.type == TokenType.COMMA:
                self._match(TokenType.COMMA)
                args.append(self._parse_expr())
        self._match(TokenType.RPAREN)
        return args

    def _parse_condition(self) -> ConditionNode:
        tok = self._current
        left  = self._parse_expr()
        if not self._current.is_relop:
            self._error("Expected relational operator in condition",
                        self._current)
            return ConditionNode(left, '==',
                                 NumberLitNode(0, tok.line, tok.column),
                                 tok.line, tok.column)
        op_tok = self._match(self._current.type)
        right  = self._parse_expr()
        return ConditionNode(left, op_tok.value, right, tok.line, tok.column)

    # ---------- Expressions ----------

    def _parse_expr(self) -> ASTNode:
        tok = self._current
        negate = False
        if self._current.type == TokenType.MINUS:
            self._match(TokenType.MINUS)
            negate = True
        node = self._parse_term()
        if negate:
            node = UnaryMinusNode(node, tok.line, tok.column)
        while self._current.is_addop:
            op_tok = self._match(self._current.type)
            right  = self._parse_term()
            node   = BinaryOpNode(op_tok.value, node, right,
                                  op_tok.line, op_tok.column)
        return node

    def _parse_term(self) -> ASTNode:
        node = self._parse_factor()
        while self._current.is_mulop:
            op_tok = self._match(self._current.type)
            right  = self._parse_factor()
            node   = BinaryOpNode(op_tok.value, node, right,
                                  op_tok.line, op_tok.column)
        return node

    def _parse_factor(self) -> ASTNode:
        tok = self._current

        if tok.type == TokenType.IDENT:
            des = self._parse_designator()
            # Lookup in symbol table
            self._sym.lookup(des.name)
            if self._current.type == TokenType.LPAREN:
                args = self._parse_act_pars()
                return CallExprNode(des, args, tok.line, tok.column)
            return des

        if tok.type == TokenType.NUMBER:
            self._match(TokenType.NUMBER)
            return NumberLitNode(tok.literal if tok.literal is not None
                                 else int(tok.value), tok.line, tok.column)

        if tok.type == TokenType.CHAR_CONST:
            self._match(TokenType.CHAR_CONST)
            return CharLitNode(tok.literal if tok.literal is not None
                               else tok.value, tok.line, tok.column)

        if tok.type == TokenType.NEW:
            self._match(TokenType.NEW)
            # 'new' can be followed by ident, int, or char (for arrays)
            if self._current.type in _TYPE_FIRST:
                name_tok = self._match(self._current.type)
            else:
                name_tok = self._match(TokenType.IDENT)
            if self._current.type == TokenType.LBRACK:
                self._match(TokenType.LBRACK)
                size_expr = self._parse_expr()
                self._match(TokenType.RBRACK)
                return NewArrayNode(name_tok.value, size_expr,
                                    tok.line, tok.column)
            return NewObjectNode(name_tok.value, tok.line, tok.column)

        if tok.type == TokenType.LPAREN:
            self._match(TokenType.LPAREN)
            node = self._parse_expr()
            self._match(TokenType.RPAREN)
            return node

        self._error(f"Unexpected token in expression: {tok.value!r}", tok)
        self._match(tok.type)   # consume the bad token
        return NumberLitNode(0, tok.line, tok.column)

    def _parse_designator(self) -> DesignatorNode:
        tok = self._match(TokenType.IDENT)
        suffixes = []
        while self._current.type in {TokenType.DOT, TokenType.LBRACK}:
            if self._current.type == TokenType.DOT:
                self._match(TokenType.DOT)
                field_tok = self._match(TokenType.IDENT)
                suffixes.append(('.', field_tok.value))
            else:
                self._match(TokenType.LBRACK)
                idx_expr = self._parse_expr()
                self._match(TokenType.RBRACK)
                suffixes.append(('[', idx_expr))
        return DesignatorNode(tok.value, suffixes, tok.line, tok.column)
