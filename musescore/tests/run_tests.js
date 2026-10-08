// SPDX-License-Identifier: GPL-3.0-or-later
//
// ISPOG MuseScore plugin - parity tests in Node.
//
// Runs ISPOG/ispog_engine.js on the notes in fixtures/*.json (written by
// make_fixtures.py from the Python core) and checks that colors, positions, fingers,
// reasons, events, report blocks and summaries are identical. run_tests_qt.py runs the
// same checks in the Qt JavaScript engine that MuseScore uses.
//
//     node musescore/tests/run_tests.js            (Node 18 or later)
//     node musescore/tests/run_tests.js --verbose  (every difference of a case)
//
// Exit code 0 if every check passes.

"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const HERE = __dirname;
const ENGINE = path.join(HERE, "..", "ISPOG", "ispog_engine.js");
const SOFTWARE = process.env.ISPOG_SOFTWARE || path.join(HERE, "..", "..");
const VERBOSE = process.argv.includes("--verbose");

const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(ENGINE, "utf8"), context, { filename: ENGINE });
vm.runInContext(fs.readFileSync(path.join(HERE, "parity.js"), "utf8"), context, { filename: "parity.js" });

let failures = 0;
let checks = 0;

function report(name, problems) {
    failures++;
    const shown = VERBOSE ? problems : problems.slice(0, 1);
    const more = problems.length > shown.length ? `\n    (+${problems.length - shown.length} more)` : "";
    console.log(`FAIL ${name}: ${shown.join("\n    ")}${more}`);
}

// The stretch table embedded in the engine is the one of the Python core.
const csvPath = path.join(SOFTWARE, "config", "finger_stretch.csv");
if (fs.existsSync(csvPath)) {
    checks++;
    const normalize = (text) => text.replace(/^﻿/, "").split(/\r?\n/).map((l) => l.trim())
        .filter(Boolean).join("\n");
    if (normalize(fs.readFileSync(csvPath, "utf8")) !== normalize(context.STRETCH_TABLE_CSV))
        report("stretch table", ["ispog_engine.js STRETCH_TABLE_CSV differs from config/finger_stretch.csv"]);
} else {
    console.log(`skip stretch table check: ${csvPath} not found`);
}

const positions = context.parityPositionChecks(context);
checks += positions.checks;
positions.failures.forEach((f) => report("analyzePositions", [f]));

const dir = path.join(HERE, "fixtures");
const files = fs.existsSync(dir) ? fs.readdirSync(dir).filter((f) => f.endsWith(".json")).sort() : [];
if (!files.length)
    report("fixtures", [`no fixtures in ${dir}: run make_fixtures.py first`]);
for (const file of files) {
    const data = JSON.parse(fs.readFileSync(path.join(dir, file), "utf8"));
    if (data.ispog !== context.ENGINE_VERSION)
        console.log(`note: ${file} exported by ISPOG ${data.ispog}, engine ${context.ENGINE_VERSION}`);
    const result = context.parityFixtures(context, data);
    checks += result.cases;
    result.failures.forEach((f) => report(f.name, f.problems));
    console.log(`${file}: ${result.passed}/${result.cases} cases match (${result.ms} ms)`);
}

console.log(failures ? `${failures} of ${checks} checks FAILED` : `all ${checks} checks passed`);
process.exit(failures ? 1 : 0);
