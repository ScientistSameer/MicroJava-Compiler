# MicroJava Mini Compiler — Makefile
# Usage: make [target]

PYTHON  = python
SRC_DIR = src
TEST_DIR = test
OUT_DIR  = output

.PHONY: all install test web clean help

# Default: run all sample programs
all: test

install:
	pip install -r requirements.txt

# Run the CLI compiler on all test files
test: $(OUT_DIR)/sample1.txt $(OUT_DIR)/sample2.txt $(OUT_DIR)/sample3.txt
	@echo ""
	@echo "All samples compiled. Check $(OUT_DIR)/ for results."

$(OUT_DIR)/sample1.txt: $(TEST_DIR)/sample1.mj
	@mkdir -p $(OUT_DIR)
	$(PYTHON) -m $(SRC_DIR).compiler $(TEST_DIR)/sample1.mj > $@ 2>&1
	@echo "  sample1.mj -> $@"

$(OUT_DIR)/sample2.txt: $(TEST_DIR)/sample2.mj
	@mkdir -p $(OUT_DIR)
	$(PYTHON) -m $(SRC_DIR).compiler $(TEST_DIR)/sample2.mj > $@ 2>&1
	@echo "  sample2.mj -> $@"

$(OUT_DIR)/sample3.txt: $(TEST_DIR)/sample3.mj
	@mkdir -p $(OUT_DIR)
	$(PYTHON) -m $(SRC_DIR).compiler $(TEST_DIR)/sample3.mj > $@ 2>&1
	@echo "  sample3.mj -> $@"

# Run just the lexer phase
lex:
	$(PYTHON) -m $(SRC_DIR).compiler $(TEST_DIR)/sample1.mj --phase lex

# Run with JSON output
json:
	$(PYTHON) -m $(SRC_DIR).compiler $(TEST_DIR)/sample1.mj --json

# Start the web UI
web:
	$(PYTHON) web/app.py

# Clean outputs
clean:
	rm -f $(OUT_DIR)/*.txt
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

help:
	@echo "MicroJava Mini Compiler"
	@echo ""
	@echo "  make            Run compiler on all test files"
	@echo "  make install    Install Python dependencies"
	@echo "  make web        Start the web UI (http://localhost:5000)"
	@echo "  make lex        Run lexer phase only on sample1"
	@echo "  make json       Output JSON result for sample1"
	@echo "  make clean      Remove generated output files"
	@echo ""
	@echo "CLI usage:"
	@echo "  python -m src.compiler <file.mj>"
	@echo "  python -m src.compiler <file.mj> --phase lex"
	@echo "  python -m src.compiler <file.mj> --json"
	@echo "  python -m src.compiler <file.mj> --no-lr --no-ll1"
