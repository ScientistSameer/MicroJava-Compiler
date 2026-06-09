"""
Flask Web Server for the MicroJava Mini Compiler.
Provides a REST API consumed by the browser frontend.
"""

import os
import sys
import json

# Add project root to path so we can import src.*
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

from src.compiler import MicroJavaCompiler

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(_THIS_DIR, 'templates'),
            static_folder=os.path.join(_THIS_DIR, 'static'))
CORS(app)

compiler = MicroJavaCompiler()


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


# --------------------------------------------------------------------------
# API Endpoints
# --------------------------------------------------------------------------

@app.route('/api/compile', methods=['POST'])
def api_compile():
    """
    POST /api/compile
    Body: { "source": "<code>", "phase": "all", "ll1": true, "lr": true }
    Returns: CompileResult JSON
    """
    data = request.get_json(force=True, silent=True) or {}
    source  = data.get('source', '')
    phase   = data.get('phase', 'all')
    run_ll1 = data.get('ll1', True)
    run_lr  = data.get('lr', True)

    if not source.strip():
        return jsonify({'error': 'Empty source code'}), 400

    try:
        result = compiler.compile(
            source,
            phase   = phase,
            run_ll1 = run_ll1,
            run_lr  = run_lr,
        )
        return jsonify(result.to_dict())
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500


@app.route('/api/samples')
def api_samples():
    """Return list of available sample programs."""
    test_dir = os.path.join(ROOT, 'test')
    samples  = []
    if os.path.isdir(test_dir):
        for fn in sorted(os.listdir(test_dir)):
            if fn.endswith('.mj'):
                path = os.path.join(test_dir, fn)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                samples.append({'name': fn, 'code': content})
    return jsonify(samples)


@app.route('/api/sample/<name>')
def api_sample(name):
    """Return one sample program by filename."""
    test_dir = os.path.join(ROOT, 'test')
    path = os.path.join(test_dir, name)
    if not os.path.isfile(path):
        return jsonify({'error': 'Not found'}), 404
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({'name': name, 'code': content})


@app.route('/api/grammar')
def api_grammar():
    """Return the MicroJava grammar and FIRST/FOLLOW sets."""
    from src.ll1_parser import LL1Table, GRAMMAR, START_SYMBOL
    table = LL1Table(GRAMMAR, START_SYMBOL)
    return jsonify({
        'first_follow': table.format_first_follow(),
        'table': table.format_table(),
        'conflicts': table.conflicts,
    })


@app.route('/api/lr_tables')
def api_lr_tables():
    """Return LR automaton tables (expensive — pre-compute on startup)."""
    from src.lr_parser import LRAutomaton
    auto = LRAutomaton()
    return jsonify({
        'summary':     auto.summary(),
        'productions': auto.format_productions(),
        'action_goto': auto.format_action_goto(max_states=40),
        'conflicts':   auto.conflicts,
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f'MicroJava Compiler Web UI starting on http://localhost:{port}')
    app.run(debug=True, port=port, host='0.0.0.0')
