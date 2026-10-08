// SPDX-License-Identifier: GPL-3.0-or-later
//
// ISPOG MuseScore plugin - parity checks shared by the test runners.
//
// Plain script (no Node, no QML): evaluated next to ispog_engine.js by run_tests.js
// (Node) and run_tests_qt.py (the Qt JavaScript engine used by MuseScore).

// Engine checks independent of the fixtures: tests/test_playability.py, test_fingering_reasons.
function parityPositionChecks(Engine) {
    var cases = [
        [[[1, 0], [2, 0]], "green", "open strings"],
        [[[5, 3], [4, 2], [2, 1]], "green", "playable"],
        [[[6, 1], [5, 2], [4, 3], [3, 4], [2, 5]], "red", "requires 5 fingers (max 4)"],
        [[[6, 1], [1, 7]], "red", "fret span 6: fingers 1–4 over 6 frets (max 4)"],
        [[[6, 5], [5, 6], [4, 7], [2, 8], [1, 8]], "orange", "pinky barré on fret 8, strings 1–2"],
        [[[6, 1], [1, 5]], "orange", "stretch: fingers 1–4 over 4 frets"],
        [[[6, 1], [4, 3], [3, 2], [2, 1], [1, 5]], "orange",
         "stretch: fingers 1–4 over 4 frets; stretch: fingers 2–4 over 3 frets; " +
         "stretch: fingers 3–4 over 2 frets"]
    ];
    var analyzer = new Engine.ChordAnalyzer();
    var failures = [];
    for (var i = 0; i < cases.length; i++) {
        var positions = cases[i][0].map(function (p) { return { string: p[0], fret: p[1] }; });
        var analysis = analyzer.analyzePositions(positions);
        if (analysis.playability !== cases[i][1] || analysis.reason !== cases[i][2])
            failures.push("positions " + JSON.stringify(cases[i][0]) + ": " + analysis.playability + " \""
                          + analysis.reason + "\", expected " + cases[i][1] + " \"" + cases[i][2] + "\"");
    }
    return { checks: cases.length, failures: failures };
}

function _same(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
}

// Differences between the engine and the Python core on one fixture case.
function parityCase(Engine, fixture) {
    var notes = fixture.notes.map(function (n) {
        return Engine.makeNote({
            uid: 1000000 + n.id,
            onset: n.onset, duration: n.duration, voice: n.voice, staff: n.staff,
            step: n.step, alter: n.alter, midi: n.midi, pitchName: n.pitchName,
            measureNumber: n.measureNumber, beatLabel: n.beatLabel,
            isRest: n.isRest, isUnpitched: n.isUnpitched, isChord: n.isChord, isGrace: n.isGrace,
            isCue: n.isCue, isHarmonic: n.isHarmonic, isHidden: n.isHidden,
            tieStart: n.tieStart, tieStop: n.tieStop, stringMark: n.stringMark,
            fingeringMark: n.fingeringMark, reason: n.reason, ref: n.id
        });
    });
    var fretboard = new Engine.Fretboard(fixture.tuning, fixture.frets);
    var result = Engine.analyzeNotes(notes, fretboard);
    var id = function (n) { return n.ref; };
    var expected = fixture.expected;
    var problems = [];

    expected.notes.forEach(function (e, i) {
        var n = notes[i];
        var got = { id: id(n), color: n.color, fret: n.fret, finger: n.finger, reason: n.reason };
        if (!_same(got, e))
            problems.push("note " + i + " (" + n.pitchName + " m." + n.measureNumber + " b." + n.beatLabel
                          + "): got " + JSON.stringify(got) + ", expected " + JSON.stringify(e));
    });
    if (result.events.length !== expected.events.length)
        problems.push(result.events.length + " events, expected " + expected.events.length);
    result.events.forEach(function (event, i) {
        var e = expected.events[i];
        if (!e)
            return;
        var a = event.analysis;
        var block = null;
        if (a.playability !== "green") {
            var point = Engine.describeEvent(event);
            block = ["m. " + point.measureNumber + ", beat " + point.beatLabel + " — " + point.status]
                    .concat(point.lines);
        }
        var got = {
            onset: event.onset, grace: event.grace,
            notes: event.notes.map(id), held: event.held.map(id),
            playability: a.playability, issue: a.issue, reason: a.reason, span: a.span,
            fingersUsed: a.fingersUsed,
            positions: a.positions.map(function (p) { return [p.string, p.fret]; }),
            fingers: a.fingers,
            block: block
        };
        if (!_same(got, e))
            problems.push("event " + i + ": got " + JSON.stringify(got) + ", expected " + JSON.stringify(e));
    });
    if (!_same(result.notAnalyzed.map(id), expected.notAnalyzed))
        problems.push("not analyzed " + JSON.stringify(result.notAnalyzed.map(id)) + ", expected "
                      + JSON.stringify(expected.notAnalyzed));
    if (!_same(result.unisons.map(id), expected.unisons))
        problems.push("unisons " + JSON.stringify(result.unisons.map(id)) + ", expected "
                      + JSON.stringify(expected.unisons));
    var summary = Engine.renderSummary({ name: fixture.name, notes: notes });
    if (summary !== expected.summary)
        problems.push("summary \"" + summary + "\", expected \"" + expected.summary + "\"");
    return problems;
}

// Runs every case of a fixture file: {cases, passed, failures: [{name, problems}], ms}.
function parityFixtures(Engine, data) {
    var started = Date.now();
    var failures = [];
    var passed = 0;
    for (var i = 0; i < data.cases.length; i++) {
        var problems;
        try {
            problems = parityCase(Engine, data.cases[i]);
        } catch (error) {
            problems = [String(error) + (error.stack ? "\n" + error.stack : "")];
        }
        if (problems.length)
            failures.push({ name: data.cases[i].name, problems: problems });
        else
            passed++;
    }
    return { cases: data.cases.length, passed: passed, failures: failures, ms: Date.now() - started };
}
