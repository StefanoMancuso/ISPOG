# -*- coding: utf-8 -*-
"""
ISPOG MuseScore plugin - parity tests in the Qt JavaScript engine.

The same checks as run_tests.js, run by QJSEngine: the JavaScript engine of Qt 6 that
MuseScore Studio 4 runs plugins with. Catches what Node accepts and Qt does not, and
measures the speed the plugin will have.

    pip install PySide6-Essentials
    python musescore/tests/run_tests_qt.py

Exit code 0 if every check passes.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, qVersion
from PySide6.QtQml import QJSEngine, QJSValue

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent / 'ISPOG' / 'ispog_engine.js'
FREEZE_BUILTINS = """
[Object, Function, Array, String, Number, Boolean, Date, RegExp, Error, Map, Set, JSON, Math]
    .forEach(function (o) { Object.freeze(o); if (o.prototype) Object.freeze(o.prototype); });
"""
CHUNK = 20                       # cases per evaluation: keeps the memory of one call small


def evaluate(js: QJSEngine, source: str, name: str):
    value = js.evaluate(source, name)
    if value.isError():
        raise RuntimeError(f'{name}: {value.toString()} (line {value.property("lineNumber").toInt()})')
    return value


def main() -> int:
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)  # noqa: F841
    js = QJSEngine()
    js.installExtensions(QJSEngine.Extension.ConsoleExtension)
    # QML freezes the built-in objects: so does this runner, to fail as the plugin would
    evaluate(js, FREEZE_BUILTINS, 'freeze')
    evaluate(js, ENGINE.read_text(encoding='utf-8'), str(ENGINE))
    evaluate(js, (HERE / 'parity.js').read_text(encoding='utf-8'), 'parity.js')
    print(f'Qt {qVersion()}')

    failures = checks = 0
    positions = evaluate(js, 'JSON.stringify(parityPositionChecks(this))', 'positions')
    result = json.loads(positions.toString())
    checks += result['checks']
    for failure in result['failures']:
        failures += 1
        print(f'FAIL analyzePositions: {failure}')

    files = sorted((HERE / 'fixtures').glob('*.json'))
    if not files:
        print('FAIL no fixtures: run make_fixtures.py first')
        return 1
    for path in files:
        data = json.loads(path.read_text(encoding='utf-8'))
        passed, elapsed = 0, 0.0
        for start in range(0, len(data['cases']), CHUNK):
            chunk = {'cases': data['cases'][start:start + CHUNK]}
            js.globalObject().setProperty('fixtureText', QJSValue(json.dumps(chunk)))
            started = time.perf_counter()
            value = evaluate(js, 'JSON.stringify(parityFixtures(this, JSON.parse(fixtureText)))',
                             path.name)
            elapsed += time.perf_counter() - started
            result = json.loads(value.toString())
            checks += result['cases']
            passed += result['passed']
            for failure in result['failures']:
                failures += 1
                print(f"FAIL {failure['name']}: {failure['problems'][0]}")
        print(f"{path.name}: {passed}/{len(data['cases'])} cases match ({elapsed * 1000:.0f} ms)")

    print(f'{failures} of {checks} checks FAILED' if failures else f'all {checks} checks passed')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
