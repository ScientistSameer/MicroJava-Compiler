# MicroJava Mini Compiler

**CS-471L Compiler Construction — Spring 2026**  
University of Engineering and Technology, Lahore  
Department of Computer Science

---

## Overview

A complete mini-compiler for the MicroJava language, integrating all lab modules:

| Module | Description |
|--------|-------------|
| **Lexer** (Lab 2+3) | Double-buffer input reader + full tokenizer |
| **RD Parser** (Lab 4/9) | Recursive-descent parser, builds AST |
| **LL(1) Parser** (Lab 5/10) | Table-driven predictive parser with FIRST/FOLLOW |
| **LR Parser** (New) | SLR(1) parser with automatic table construction |
| **Symbol Table** (Lab 7+) | Hash-based, scoped, with dump support |
| **Error Handler** (Bonus) | Lexical/syntactic/semantic errors + panic-mode recovery |
| **Semantic Analyzer** | Type checking, scope verification |
| **TAC Generator** | Three-address code + constant folding + DCE |

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. CLI — compile a file

```bash
python -m src.compiler test/sample1.mj
python -m src.compiler test/sample2.mj          # shows error recovery
python -m src.compiler test/sample3.mj          # complex program
```

### 3. Run with specific phase

```bash
python -m src.compiler test/sample1.mj --phase lex    # lexer only
python -m src.compiler test/sample1.mj --phase rd     # through RD parser
python -m src.compiler test/sample1.mj --phase ll1    # through LL(1)
python -m src.compiler test/sample1.mj --phase lr     # through LR parser
python -m src.compiler test/sample1.mj --phase sym    # through symbol table
python -m src.compiler test/sample1.mj --phase sem    # full semantic analysis
```

### 4. JSON output

```bash
python -m src.compiler test/sample1.mj --json
```

### 5. Web UI

```bash
python web/app.py
```
Then open **http://localhost:5000** in your browser.

### 6. Makefile

```bash
make            # run all samples
make web        # start web UI
make install    # install dependencies
make clean      # clean outputs
```

---

## Project Structure

```
MicroJavaCompiler/
├── src/
│   ├── token.py          Token types and Token dataclass
│   ├── double_buffer.py  Two-buffer input reader (Lab 2)
│   ├── lexer.py          MicroJava lexical analyzer (Lab 3)
│   ├── ast_nodes.py      AST node hierarchy
│   ├── rd_parser.py      Recursive descent parser (Lab 4/9)
│   ├── ll1_parser.py     LL(1) predictive parser (Lab 5/10)
│   ├── lr_parser.py      SLR(1) LR parser (new)
│   ├── symbol_table.py   Symbol table manager (Lab 7+)
│   ├── error_handler.py  Error handler + panic-mode recovery
│   ├── semantic.py       Type checker + semantic analysis
│   ├── codegen.py        TAC generator + optimizer
│   └── compiler.py       Main CLI integration
├── web/
│   ├── app.py            Flask web server
│   ├── templates/
│   │   └── index.html    Web UI (CodeMirror editor)
│   └── static/
│       ├── css/style.css Dark IDE theme
│       └── js/app.js     Frontend JavaScript
├── test/
│   ├── sample1.mj        Valid program (loops, conditions)
│   ├── sample2.mj        Program with errors (recovery demo)
│   └── sample3.mj        Complex program (classes, arrays, methods)
├── output/               Generated compiler outputs
├── Makefile
├── requirements.txt
└── README.md
```

---

## MicroJava Grammar (BNF)

```
Program  = "program" ident {ConstDecl | VarDecl | ClassDecl} "{" {MethodDecl} "}".
ConstDecl = "final" Type ident "=" (number | charConst) ";".
VarDecl  = Type ident {"," ident} ";".
ClassDecl = "class" ident "{" {VarDecl} "}".
MethodDecl = (Type | "void") ident "(" [FormPars] ")" {VarDecl} Block.
FormPars = Type ident {"," Type ident}.
Type     = ident ["[" "]"].
Block    = "{" {Statement} "}".
Statement = Designator ("=" Expr | ActPars) ";"
          | "if" "(" Condition ")" Statement ["else" Statement]
          | "while" "(" Condition ")" Statement
          | "return" [Expr] ";"
          | "read" "(" Designator ")" ";"
          | "print" "(" Expr ["," number] ")" ";"
          | Block | ";".
ActPars  = "(" [Expr {"," Expr}] ")".
Condition = Expr Relop Expr.
Relop    = "==" | "!=" | ">" | ">=" | "<" | "<=".
Expr     = ["-"] Term {Addop Term}.
Term     = Factor {Mulop Factor}.
Factor   = Designator [ActPars] | number | charConst
         | "new" ident ["[" Expr "]"] | "(" Expr ")".
Designator = ident {"." ident | "[" Expr "]"}.
Addop    = "+" | "-".
Mulop    = "*" | "/" | "%".
```

---

## 10 Bonus Features

1. **AST Visualization** — text-tree dump of the full AST
2. **Type Checking** — full semantic analysis with type compatibility
3. **Three-Address Code** — TAC generation from AST
4. **Constant Folding** — compile-time evaluation of constant expressions
5. **Dead Code Elimination** — removes unused TAC instructions
6. **Pretty Printer** — re-indents MicroJava source code
7. **Code Metrics** — lines, tokens, cyclomatic complexity
8. **Symbol Table Visualization** — scoped dump with all attributes
9. **Web UI** — full browser-based IDE with syntax highlighting
10. **JSON Export** — all compiler data exportable as JSON

---

## Web UI Features

- **CodeMirror Editor** with syntax highlighting and bracket matching
- **Phase selector** — run any subset of compiler phases
- **Token Stream** — color-coded by type in a sortable table
- **AST Tree** — formatted text visualization
- **Parser Traces** — step-by-step for RD, LL(1), and LR parsers
- **LL(1) FIRST/FOLLOW** — computed sets and parsing table
- **LR ACTION/GOTO** — full SLR(1) tables
- **Symbol Table** — all symbols with scope, type, line info
- **TAC Code** — raw and optimized three-address code
- **Error Panel** — categorized errors with hints and line highlighting
- **Metrics** — code quality dashboard
- **Sample programs** — load built-in examples instantly
- **JSON export** — download full compiler output

---

## Error Recovery

- **Panic-mode recovery**: skip tokens until a synchronisation set is found
- **Phrase-level recovery**: replace/skip single erroneous tokens
- **Line/column info**: every error includes exact source location
- **Hint messages**: helpful suggestions for common mistakes
- **Summary**: all errors reported at end with counts per category
