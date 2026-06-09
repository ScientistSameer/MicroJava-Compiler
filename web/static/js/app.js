/* =====================================================================
   MicroJava Compiler — Frontend Application
   ===================================================================== */

'use strict';

// =========================================================================
// CodeMirror Editor Setup
// =========================================================================

const DEFAULT_CODE = `// MicroJava Mini Compiler —  By Sameer Babar
// Write your MicroJava program here and press Compile!

program HelloWorld
  final int MAX = 5;
  int result;

{
  void main()
    int i;
  {
    result = 0;
    i = 0;
    while (i < MAX) {
      result = result + i;
      i = i + 1;
    }
    print(result);
  }
}
`;

const editor = CodeMirror.fromTextArea(document.getElementById('code-editor'), {
  mode:          'text/x-java',
  theme:         'dracula',
  lineNumbers:   true,
  matchBrackets: true,
  autoCloseBrackets: true,
  indentUnit:    2,
  tabSize:       2,
  lineWrapping:  false,
  styleActiveLine: true,
  extraKeys: {
    'Ctrl-Enter': () => compile(),
    'Ctrl-L':     () => { editor.setValue(''); editor.focus(); },
    Tab: cm => cm.execCommand('indentMore'),
    'Shift-Tab': cm => cm.execCommand('indentLess'),
  },
});
editor.setValue(DEFAULT_CODE);

// =========================================================================
// State
// =========================================================================

let currentPhase   = 'all';
let lastResult     = null;
let compileMarkers = [];

// =========================================================================
// DOM helpers
// =========================================================================

const $ = id => document.getElementById(id);

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }

function setStatus(el, ok) {
  el.className = 'status-badge ' + (ok === true ? 'status-ok' : ok === false ? 'status-err' : 'status-warn');
  el.textContent = ok === true ? 'OK' : ok === false ? 'FAIL' : '—';
}

// =========================================================================
// Tab switching
// =========================================================================

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    const content = document.querySelector(`.tab-content[data-tab="${tab.dataset.tab}"]`);
    if (content) content.classList.add('active');
  });
});

// Sub-tabs
document.querySelectorAll('.sub-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const parent = tab.closest('.tab-content');
    parent.querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
    parent.querySelectorAll('.sub-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    const sub = parent.querySelector(`.sub-content[data-sub="${tab.dataset.sub}"]`);
    if (sub) sub.classList.add('active');
  });
});

// Phase buttons
document.querySelectorAll('.btn-phase').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.btn-phase').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentPhase = btn.dataset.phase;
  });
});

// =========================================================================
// Compile
// =========================================================================

async function compile() {
  const source  = editor.getValue();
  const phase   = currentPhase;
  const runLL1  = $('opt-ll1').checked;
  const runLR   = $('opt-lr').checked;

  if (!source.trim()) {
    showErrorBar('Please enter some MicroJava code first.');
    return;
  }

  // Clear old markers
  compileMarkers.forEach(m => m.clear());
  compileMarkers = [];
  hide($('error-bar'));
  hide($('success-bar'));
  show($('loading-overlay'));

  try {
    const res = await fetch('/api/compile', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ source, phase, ll1: runLL1, lr: runLR }),
    });
    const data = await res.json();

    if (data.error) {
      showErrorBar('Server error: ' + data.error);
      return;
    }

    lastResult = data;
    renderResult(data);

  } catch (err) {
    showErrorBar('Network error: ' + err.message);
  } finally {
    hide($('loading-overlay'));
  }
}

$('btn-compile').addEventListener('click', compile);

// =========================================================================
// Render results
// =========================================================================

function renderResult(data) {
  // Timing
  $('compile-time').textContent = data.elapsed_ms
    ? `${data.elapsed_ms.toFixed(1)} ms` : '';

  // Error / success bar
  if (data.success) {
    showSuccessBar(`Compiled successfully — ${(data.tokens || []).length} tokens, no errors.`);
  } else {
    const n = (data.errors || []).length;
    showErrorBar(`Compilation failed — ${n} error${n !== 1 ? 's' : ''} found.`);
  }

  // Mark errors in editor
  (data.errors || []).forEach(err => {
    if (err.line > 0) {
      const marker = editor.addLineClass(err.line - 1, 'background', 'error-line');
      compileMarkers.push(marker);
    }
  });

  renderTokens(data.tokens || []);
  renderAST(data.ast || '');
  renderRD(data);
  renderLL1(data);
  renderLR(data);
  renderSymTable(data.sym_table || []);
  renderTAC(data);
  renderErrors(data.errors || []);
  renderMetrics(data.metrics || {});

  $('error-badge').textContent = (data.errors || []).length;
}

// ---- Tokens ----
const TOKEN_COLORS = {
  PROGRAM:'tok-keyword', CLASS:'tok-keyword', IF:'tok-keyword',
  ELSE:'tok-keyword', WHILE:'tok-keyword', READ:'tok-keyword',
  PRINT:'tok-keyword', RETURN:'tok-keyword', VOID:'tok-keyword',
  FINAL:'tok-keyword', NEW:'tok-keyword', INT:'tok-keyword', CHAR:'tok-keyword',
  IDENT:'tok-ident',
  NUMBER:'tok-number',
  CHAR_CONST:'tok-char',
  PLUS:'tok-op', MINUS:'tok-op', TIMES:'tok-op', DIV:'tok-op', MOD:'tok-op',
  EQ:'tok-op', NE:'tok-op', LT:'tok-op', LE:'tok-op', GT:'tok-op', GE:'tok-op',
  ASSIGN:'tok-op',
  LPAREN:'tok-punct', RPAREN:'tok-punct', LBRACK:'tok-punct', RBRACK:'tok-punct',
  LBRACE:'tok-punct', RBRACE:'tok-punct', SEMICOLON:'tok-punct', COMMA:'tok-punct', DOT:'tok-punct',
  ERROR:'tok-error',
};

function renderTokens(tokens) {
  const tbody = $('token-body');
  tbody.innerHTML = '';
  tokens.forEach(tok => {
    const tr = document.createElement('tr');
    const cls = TOKEN_COLORS[tok.type] || '';
    tr.innerHTML = `
      <td>${tok.line}</td>
      <td>${tok.column}</td>
      <td class="${cls}">${escHtml(tok.type)}</td>
      <td class="${cls}">${escHtml(tok.value)}</td>
    `;
    tbody.appendChild(tr);
  });
  $('token-count').textContent = `${tokens.length} token${tokens.length !== 1 ? 's' : ''}`;
}

// ---- AST ----
function renderAST(ast) {
  $('ast-output').textContent = ast || '(no AST — parsing failed or phase not run)';
}

// ---- RD Parser ----
function renderRD(data) {
  setStatus($('rd-status'), data.rd_success);
  const trace = (data.rd_trace || []).slice(0, 60).join('\n');
  $('rd-output').textContent = trace || '(no trace)';
}

// ---- LL(1) ----
function renderLL1(data) {
  $('ll1-ff-output').textContent = data.ll1_first_follow || '(not run)';
  $('ll1-table-output').textContent = data.ll1_table || '(not run)';
  $('ll1-trace-output').textContent = data.ll1_trace || '(not run)';
  if (data.ll1_success !== undefined) {
    setStatus($('ll1-status'), data.ll1_success);
  }
}

// ---- LR ----
function renderLR(data) {
  $('lr-prods-output').textContent = data.lr_productions || '(not run)';
  $('lr-tables-output').textContent = data.lr_action_goto || '(not run)';
  $('lr-trace-output').textContent = data.lr_trace || '(not run)';
  if (data.lr_success !== undefined) {
    setStatus($('lr-status'), data.lr_success);
  }
}

// ---- Symbol Table ----
const KIND_COLORS = {
  const: 'kind-const', var: 'kind-var', param: 'kind-param',
  method: 'kind-method', class: 'kind-class', builtin: 'kind-builtin',
};

function renderSymTable(symbols) {
  const tbody = $('sym-body');
  tbody.innerHTML = '';
  symbols.forEach(sym => {
    const tr = document.createElement('tr');
    const cls = KIND_COLORS[sym.kind] || '';
    const val = sym.value !== null && sym.value !== undefined
      ? escHtml(String(sym.value)) : '—';
    tr.innerHTML = `
      <td>${escHtml(sym.scope_name || '')}</td>
      <td class="${cls}">${escHtml(sym.kind)}</td>
      <td>${escHtml(sym.type)}</td>
      <td class="${cls}">${escHtml(sym.name)}</td>
      <td>${sym.scope_level}</td>
      <td>${sym.line}</td>
      <td>${val}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ---- TAC ----
function renderTAC(data) {
  $('tac-output').textContent = data.tac_code || '(no TAC generated)';
  $('tac-opt-output').textContent = data.tac_optimized || '(no optimized TAC)';
}

// ---- Errors ----
function renderErrors(errors) {
  const list = $('error-list');
  if (!errors.length) {
    list.innerHTML = '<div class="empty-state"><i class="fa fa-check-circle"></i> No errors — compilation successful!</div>';
    return;
  }
  list.innerHTML = errors.map(e => {
    const kindCls = { Syntactic: 'ek-syntactic', Lexical: 'ek-lexical',
                      Semantic: 'ek-semantic', Warning: 'ek-warning' }[e.kind] || '';
    return `
      <div class="error-card ${(e.kind || '').toLowerCase()}">
        <div class="error-header">
          <span class="error-kind ${kindCls}">${escHtml(e.kind)}</span>
          <span class="error-loc">L${e.line}:C${e.column}</span>
        </div>
        <div class="error-msg">${escHtml(e.message)}</div>
        ${e.hint ? `<div class="error-hint">💡 ${escHtml(e.hint)}</div>` : ''}
      </div>
    `;
  }).join('');
}

// ---- Metrics ----
const METRIC_LABELS = {
  total_lines:           'Total Lines',
  non_blank_lines:       'Non-Blank Lines',
  token_count:           'Token Count',
  keyword_count:         'Keywords',
  identifier_count:      'Identifiers',
  operator_count:        'Operators',
  cyclomatic_complexity: 'Cyclomatic Complexity',
  lexical_error_count:   'Lexical Errors',
};

function renderMetrics(metrics) {
  const grid = $('metrics-grid');
  const entries = Object.entries(metrics);
  if (!entries.length) {
    grid.innerHTML = '<div class="empty-state"><i class="fa fa-chart-bar"></i> Run the compiler to see metrics.</div>';
    return;
  }
  grid.innerHTML = entries.map(([k, v]) => `
    <div class="metric-card">
      <div class="metric-value">${v}</div>
      <div class="metric-label">${METRIC_LABELS[k] || k.replace(/_/g, ' ')}</div>
    </div>
  `).join('');
}

// =========================================================================
// Toolbar actions
// =========================================================================

$('btn-clear').addEventListener('click', () => {
  editor.setValue('');
  editor.focus();
});

$('btn-copy').addEventListener('click', async () => {
  await navigator.clipboard.writeText(editor.getValue());
  const btn = $('btn-copy');
  const orig = btn.innerHTML;
  btn.innerHTML = '<i class="fa fa-check"></i>';
  setTimeout(() => btn.innerHTML = orig, 1500);
});

$('btn-pretty').addEventListener('click', async () => {
  const source = editor.getValue();
  try {
    const res  = await fetch('/api/compile', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ source, phase: 'lex' }),
    });
    // Just re-indent locally (server pretty-print needs different endpoint)
    const prettied = simpleIndent(source);
    editor.setValue(prettied);
  } catch (e) {}
});

$('btn-export').addEventListener('click', () => {
  if (!lastResult) return;
  const blob = new Blob([JSON.stringify(lastResult, null, 2)],
                        {type: 'application/json'});
  const a    = document.createElement('a');
  a.href     = URL.createObjectURL(blob);
  a.download = 'compiler_result.json';
  a.click();
});

// =========================================================================
// Sample loading
// =========================================================================

async function loadSamples() {
  try {
    const res     = await fetch('/api/samples');
    const samples = await res.json();
    const sel     = $('sample-select');
    samples.forEach(s => {
      const opt  = document.createElement('option');
      opt.value  = s.name;
      opt.text   = s.name;
      sel.appendChild(opt);
    });
    sel.addEventListener('change', () => {
      const chosen = samples.find(s => s.name === sel.value);
      if (chosen) editor.setValue(chosen.code);
      sel.value = '';
    });
  } catch (e) {}
}
loadSamples();

// =========================================================================
// Help modal
// =========================================================================

$('btn-help').addEventListener('click', () => show($('help-modal')));
$('modal-close').addEventListener('click', () => hide($('help-modal')));
$('help-modal').addEventListener('click', e => {
  if (e.target === $('help-modal')) hide($('help-modal'));
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') hide($('help-modal'));
});

// =========================================================================
// Status bar helpers
// =========================================================================

function showErrorBar(msg) {
  const bar = $('error-bar');
  $('error-bar-text').textContent = msg;
  hide($('success-bar'));
  show(bar);
}
function showSuccessBar(msg) {
  const bar = $('success-bar');
  $('success-bar-text').textContent = msg;
  hide($('error-bar'));
  show(bar);
}

// =========================================================================
// Utilities
// =========================================================================

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function simpleIndent(source) {
  const lines = source.split('\n');
  let indent = 0;
  return lines.map(line => {
    const s = line.trim();
    if (!s) return '';
    if (s.startsWith('}')) indent = Math.max(0, indent - 1);
    const result = '  '.repeat(indent) + s;
    if (s.endsWith('{')) indent++;
    return result;
  }).join('\n');
}

// Add CSS for editor error lines
const style = document.createElement('style');
style.textContent = '.error-line { background: rgba(248,81,73,.12) !important; }';
document.head.appendChild(style);

// Adjust CodeMirror height dynamically
function adjustEditorHeight() {
  const editorWrapper = document.querySelector('.editor-wrapper');
  if (editorWrapper) {
    editor.setSize('100%', editorWrapper.clientHeight + 'px');
  }
}
window.addEventListener('resize', adjustEditorHeight);
setTimeout(adjustEditorHeight, 100);
