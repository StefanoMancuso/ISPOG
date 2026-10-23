// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Stefano Mancuso
//
// ISPOG - playability engine for the MuseScore plugin.
//
// JavaScript port of the ISPOG core (software/core): fretboard.py, stretch.py,
// fingering.py, analyzer.py, unison.py, playability.py and the report of report.py.
// The Python core is the reference implementation: tests/run_tests.js checks that this
// port gives the same colors, positions, fingers and reasons on fixtures exported from
// it (tests/make_fixtures.py). Any change to the rules goes into the Python core first.
//
// No QML and no MuseScore dependency: the plugin (ispog.qml) builds the note list from
// the score, calls analyzeNotes() and writes the colors back. Time is in integer ticks
// (any resolution); pitch is the sounding MIDI number.
//
// Plain ES5 plus Map and Set, for the QML JavaScript engine: the file is loaded both by
// QML (import "ispog_engine.js" as Engine) and by Node and QJSEngine in the tests.
// QML freezes the built-in prototypes: never name a property after a built-in one
// (apply, call, toString...), the assignment would be silently ignored.

var ENGINE_VERSION = "1.0.1.dev0";

// ============================================================================
// Settings (config/settings.py)
// ============================================================================

var MAX_FINGERS = 4;
var HIGH_POSITION_FRET = 7;
var PINKY_BARRE_MAX_STRINGS = 4;
var BEAM_WIDTH = 64;
var BEAM_CANDIDATES = 24;
var POSITION_SHIFT_COST = 0.2;
var DEFAULT_NUM_FRETS = 19;
var MIN_FRETS = 12;
var MAX_FRETS = 24;
var MIN_STRINGS = 4;
var MAX_STRINGS = 8;

var TUNING_PRESETS = [
    { key: "standard", name: "Standard", notes: ["E4", "B3", "G3", "D3", "A2", "E2"] },
    { key: "drop_d", name: "Drop D", notes: ["E4", "B3", "G3", "D3", "A2", "D2"] },
    { key: "open_g", name: "Open G", notes: ["D4", "B3", "G3", "D3", "G2", "D2"] }
];

var DEFAULT_COLOR = "black";
var NOT_AS_WRITTEN_COLOR = "purple";

// Notehead colors (COLOR_CODES)
var COLOR_CODES = {
    red: "#CF0000",
    green: "#005000",
    orange: "#FF8C00",
    purple: "#7B1FA2",
    black: "#000000"
};

var Playability = { PLAYABLE: "green", DIFFICULT: "orange", UNPLAYABLE: "red" };
var RANK = { green: 0, orange: 1, red: 2 };

var Issue = {
    NONE: "",
    FINGERS: "fingers",
    SPAN: "span",
    OUT_OF_RANGE: "out_of_range",
    STRINGS: "strings",
    CONFLICT: "conflict",
    FINGER_CONFLICT: "finger_conflict",
    PINKY_BARRE: "pinky_barre",
    STRETCH: "stretch",
    CROSSING: "crossing",
    NO_SHAPE: "no_shape",
    UNISON: "unison"
};

// Short labels for difficult and unplayable points (LABEL_TEXT)
var LABEL_TEXT = {
    fingers: "{fingers} fingers",
    span: "span {span}",
    out_of_range: "out of range",
    strings: "no free string",
    conflict: "string conflict",
    finger_conflict: "no free finger",
    no_shape: "no hand position",
    pinky_barre: "pinky barré",
    stretch: "stretch",
    crossing: "crossed fingers",
    unison: "unison"
};

// config/finger_stretch.csv, verbatim (tests/run_tests.js checks it against the file)
var STRETCH_TABLE_CSV = [
    "fingers,1-1,1-2,1-3,1-4,1-5,1-6,2-1,2-2,2-3,2-4,2-5,2-6,3-1,3-2,3-3,3-4,3-5,3-6,4-1,4-2,4-3,4-4,4-5,4-6,5-1,5-2,5-3,5-4,5-5,5-6,6-1,6-2,6-3,6-4,6-5,6-6",
    "1-2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2,2/2",
    "1-2 >7,3/3,3/3,3/3,3/3,2/3,2/3,3/3,3/3,3/3,3/3,3/3,2/3,3/3,3/3,3/3,3/3,3/3,3/3,2/3,3/3,3/3,3/3,3/3,3/3,2/3,3/3,3/3,3/3,3/3,3/3,2/3,2/3,3/3,3/3,3/3,3/3",
    "1-3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3,3/3",
    "1-3 >7,4/4,4/4,4/4,4/4,3/4,3/4,4/4,4/4,4/4,4/4,4/4,3/4,4/4,4/4,4/4,4/4,4/4,4/4,4/4,4/4,4/4,4/4,4/4,4/4,3/4,4/4,4/4,4/4,4/4,4/4,3/4,3/4,4/4,4/4,4/4,4/4",
    "1-4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4",
    "1-4 >7,4/4,4/4,4/4,4/4,3/4,3/4,4/4,4/4,4/4,4/4,4/4,3/4,4/4,4/4,4/4,4/4,4/4,4/4,4/4,4/4,4/4,4/4,4/4,4/4,3/4,4/4,4/4,4/4,4/4,4/4,3/4,3/4,4/4,4/4,4/4,4/4",
    "2-3,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1,1/1",
    "2-3 >7,1/2,1/2,1/2,1/2,1/1,1/1,1/2,1/2,1/2,1/2,1/2,1/1,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/1,1/2,1/2,1/2,1/2,1/2",
    "2-4,2/3,2/3,2/2,2/2,1/2,1/2,2/3,2/2,2/2,2/2,2/2,1/2,2/3,2/3,2/2,2/2,2/2,2/2,2/3,2/3,2/3,2/3,2/3,2/3,2/3,2/3,2/3,2/3,2/3,2/3,2/3,2/3,2/3,2/3,2/3,2/3",
    "2-4 >7,3/3,3/3,2/3,2/3,1/2,1/2,3/3,3/3,3/3,2/3,2/3,1/2,3/3,3/3,3/3,3/3,3/3,2/3,2/3,2/3,2/3,2/3,2/3,2/3,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4,3/4",
    "3-4,1/2,1/2,1/1,1/1,0/1,0/1,1/2,1/2,1/2,1/2,1/1,0/1,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2",
    "3-4 >7,2/3,2/3,1/2,1/2,0/1,0/1,2/3,2/2,2/2,2/2,1/2,0/1,2/3,2/3,2/2,2/2,2/2,2/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2,1/2"
].join("\n");

var INDEX = 1;
var PINKY = MAX_FINGERS;
var OPEN = 0;
var NO_FRET = [-1, -1];

// ============================================================================
// Helpers
// ============================================================================

// Stable sort (the QML engine does not guarantee a stable Array.prototype.sort).
function stableSort(items, compare) {
    var indexed = new Array(items.length);
    for (var i = 0; i < items.length; i++)
        indexed[i] = { value: items[i], index: i };
    indexed.sort(function (a, b) { return compare(a.value, b.value) || (a.index - b.index); });
    var result = new Array(items.length);
    for (var j = 0; j < indexed.length; j++)
        result[j] = indexed[j].value;
    return result;
}

// Lexicographic comparison of arrays of numbers (Python tuple order).
function compareTuples(a, b) {
    for (var i = 0; i < a.length && i < b.length; i++) {
        if (a[i] < b[i])
            return -1;
        if (a[i] > b[i])
            return 1;
    }
    return a.length - b.length;
}

// First element with the smallest key (Python min).
function minBy(items, key) {
    var best = null, bestKey = null;
    for (var i = 0; i < items.length; i++) {
        var k = key(items[i]);
        if (best === null || compareTuples(k, bestKey) < 0) {
            best = items[i];
            bestKey = k;
        }
    }
    return best;
}

// itertools.combinations(values, size), in the same order.
function combinations(values, size) {
    var result = [];
    var current = [];
    function recurse(start) {
        if (current.length === size) {
            result.push(current.slice());
            return;
        }
        for (var i = start; i < values.length; i++) {
            current.push(values[i]);
            recurse(i + 1);
            current.pop();
        }
    }
    recurse(0);
    return result;
}

// itertools.permutations(values), in the same order.
function permutations(values) {
    var result = [];
    var used = new Array(values.length);
    var current = [];
    function recurse() {
        if (current.length === values.length) {
            result.push(current.slice());
            return;
        }
        for (var i = 0; i < values.length; i++) {
            if (used[i])
                continue;
            used[i] = true;
            current.push(values[i]);
            recurse();
            current.pop();
            used[i] = false;
        }
    }
    recurse();
    return result;
}

function maxOf(values) {
    var m = values[0];
    for (var i = 1; i < values.length; i++)
        if (values[i] > m)
            m = values[i];
    return m;
}

function minOf(values) {
    var m = values[0];
    for (var i = 1; i < values.length; i++)
        if (values[i] < m)
            m = values[i];
    return m;
}

function plural(n, noun) {
    return n + " " + noun + (n === 1 ? "" : "s");
}

function format(template, values) {
    return template.replace(/\{(\w+)\}/g, function (match, name) {
        return values.hasOwnProperty(name) ? String(values[name]) : match;
    });
}

// ============================================================================
// Fretboard (core/fretboard.py)
// ============================================================================

var STEP_SEMITONES = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
var ACCIDENTAL_SEMITONES = { "": 0, "#": 1, "##": 2, "x": 2, "b": -1, "bb": -2 };
var SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
var ACCIDENTAL_TEXT = { "-2": "bb", "-1": "b", "0": "", "1": "#", "2": "##" };

// MIDI number of a note name such as E4, F#1 or Bb3 (C4 = 60); NaN if invalid.
function noteNameToMidi(name) {
    var match = /^([A-Ga-g])(##|#|bb|b|x)?(-?\d+)$/.exec(String(name).trim());
    if (!match)
        return NaN;
    return 12 * (parseInt(match[3], 10) + 1) + STEP_SEMITONES[match[1].toUpperCase()]
            + ACCIDENTAL_SEMITONES[match[2] || ""];
}

// Note name with sharps: 54 -> F#3.
function midiToNoteName(midi) {
    return SHARP_NAMES[((midi % 12) + 12) % 12] + (Math.floor(midi / 12) - 1);
}

// Spelled name: ("F", 1, 3) -> F#3.
function spelledName(step, alter, octave) {
    var accidental = ACCIDENTAL_TEXT[String(alter)];
    return step + (accidental === undefined ? "(" + (alter > 0 ? "+" : "") + alter + ")" : accidental)
            + octave;
}

// Parses "E4 B3 G3 D3 A2 E2" (string 1 first); null if a name is invalid.
function parseTuning(text) {
    var tokens = String(text).trim().split(/[\s,;]+/);
    var names = [];
    for (var i = 0; i < tokens.length; i++) {
        if (!tokens[i])
            continue;
        if (isNaN(noteNameToMidi(tokens[i])))
            return null;
        names.push(tokens[i]);
    }
    return names.length ? names : null;
}

// A guitar neck: open strings, string 1 (the highest, as on the guitar) first, and the
// number of frets. The order of `tuning` is the order of the strings (re-entrant tunings
// are kept as they are).
function Fretboard(tuning, numFrets) {
    if (!tuning || !tuning.length)
        throw new Error("tuning must name at least one string");
    if (!(numFrets >= 0))
        throw new Error("invalid number of frets: " + numFrets);
    this.tuning = [];
    this.openMidi = [];
    for (var i = 0; i < tuning.length; i++) {
        var midi = noteNameToMidi(tuning[i]);
        if (isNaN(midi))
            throw new Error("invalid note name " + tuning[i]);
        this.tuning.push(String(tuning[i]).trim());
        this.openMidi.push(midi);
    }
    this.numFrets = numFrets;
    this.numStrings = this.openMidi.length;
}

// All [string, fret] positions of a pitch, string 1 first.
Fretboard.prototype.positions = function (midi) {
    var result = [];
    for (var i = 0; i < this.openMidi.length; i++) {
        var fret = midi - this.openMidi[i];
        if (fret >= 0 && fret <= this.numFrets)
            result.push([i + 1, fret]);
    }
    return result;
};

Fretboard.prototype.outOfRangeReason = function (midi) {
    var lowest = minOf(this.openMidi);
    if (midi < lowest)
        return "below the lowest string " + midiToNoteName(lowest);
    return "above fret " + this.numFrets;
};

Fretboard.prototype.describe = function () {
    return this.tuning.join(" ") + " · " + this.numFrets + " frets";
};

// ============================================================================
// Stretch table (core/stretch.py)
// ============================================================================

var TABLE_STRINGS = 6;

function StretchTable(csvText) {
    var rows = [];
    var lines = String(csvText).split(/\r?\n/);
    for (var i = 0; i < lines.length; i++) {
        if (lines[i].trim())
            rows.push(lines[i].split(","));
    }
    if (!rows.length)
        throw new Error("stretch table: empty");
    var columns = [];
    for (var c = 1; c < rows[0].length; c++) {
        var pair = rows[0][c].replace(/\s+/g, "").split("-");
        columns.push({ index: c, a: parseInt(pair[0], 10), b: parseInt(pair[1], 10) });
    }
    this._limits = {};
    var seen = 0;
    for (var r = 1; r < rows.length; r++) {
        var name = rows[r][0].replace(/\s+/g, "");
        var high = /> ?7$/.test(name);
        var fingers = name.replace(/>7$/, "").split("-");
        for (var k = 0; k < columns.length; k++) {
            var cell = (rows[r][columns[k].index] || "").replace(/\s+/g, "").split("/");
            var green = parseInt(cell[0], 10), orange = parseInt(cell[1], 10);
            if (isNaN(green) || isNaN(orange) || orange < green)
                throw new Error("stretch table: invalid cell in row " + rows[r][0]);
            this._limits[[fingers[0], fingers[1], high ? 1 : 0, columns[k].a, columns[k].b].join(",")]
                    = { green: green, orange: orange };
        }
        seen++;
    }
    if (seen !== 12 || columns.length !== TABLE_STRINGS * TABLE_STRINGS)
        throw new Error("stretch table: expected 12 rows and 36 columns");
}

// Limits for two fingers (any order) on their strings, hand at `position` (lowest fret).
StretchTable.prototype.limit = function (fingerA, stringA, fingerB, stringB, position) {
    if (fingerA > fingerB) {
        var f = fingerA; fingerA = fingerB; fingerB = f;
        var s = stringA; stringA = stringB; stringB = s;
    }
    return this._limits[[fingerA, fingerB, position >= HIGH_POSITION_FRET ? 1 : 0,
                         Math.min(stringA, TABLE_STRINGS), Math.min(stringB, TABLE_STRINGS)].join(",")];
};

var _defaultTable = null;
function defaultTable() {
    if (_defaultTable === null)
        _defaultTable = new StretchTable(STRETCH_TABLE_CSV);
    return _defaultTable;
}

// ============================================================================
// Fretting hand (core/fingering.py)
// ============================================================================

// positions: [[string, fret], ...]; pins: finger per position or null (held notes).
// Returns { valid: [HandShape], invalid: [HandShape], minFingers }.
var _shapeCache = {};
var _shapeCacheSize = 0;
var SHAPE_CACHE_LIMIT = 4096;

function handShapes(positions, pins, table) {
    pins = pins || positions.map(function () { return null; });
    if (pins.length !== positions.length)
        throw new Error("pins must have one entry per position");
    table = table || defaultTable();
    var key = positions.map(function (p) { return p[0] + "/" + p[1]; }).join(" ") + "|"
            + pins.map(function (p) { return p === null || p === undefined ? "-" : p; }).join(" ");
    var cached = table === defaultTable() ? _shapeCache[key] : undefined;
    if (cached)
        return cached;
    var result = _searchShapes(positions, pins, table);
    if (table === defaultTable()) {
        if (_shapeCacheSize >= SHAPE_CACHE_LIMIT) {
            _shapeCache = {};
            _shapeCacheSize = 0;
        }
        _shapeCache[key] = result;
        _shapeCacheSize++;
    }
    return result;
}

function _searchShapes(positions, pins, table) {
    var groups = _fretGroups(positions);
    for (var i = 0; i < positions.length; i++) {
        if (positions[i][1] === 0 && pins[i] !== null && pins[i] !== undefined && pins[i] !== OPEN)
            return { valid: [], invalid: [], minFingers: _minFingers(positions, groups) };
    }
    var valid = [], invalid = [];
    _assignments(positions, pins, groups, function (fingers, barre) {
        var shape = _grade(positions, fingers, barre, groups, table);
        if (shape === null)
            return;
        (shape.playability === Playability.UNPLAYABLE ? invalid : valid).push(shape);
    });
    valid = stableSort(valid, function (a, b) {
        return (RANK[a.playability] - RANK[b.playability]) || (a.cost - b.cost);
    });
    invalid = stableSort(invalid, function (a, b) {
        return (a.excess - b.excess) || (a.cost - b.cost);
    });
    return { valid: valid, invalid: invalid, minFingers: _minFingers(positions, groups) };
}

// Fretted positions grouped by fret, lowest fret first; in a group, low strings first.
function _fretGroups(positions) {
    var byFret = {};
    var frets = [];
    for (var i = 0; i < positions.length; i++) {
        var fret = positions[i][1];
        if (fret > 0) {
            if (!byFret.hasOwnProperty(fret)) {
                byFret[fret] = [];
                frets.push(fret);
            }
            byFret[fret].push(i);
        }
    }
    frets.sort(function (a, b) { return a - b; });
    return frets.map(function (fret) {
        return {
            fret: fret,
            indices: stableSort(byFret[fret], function (a, b) { return positions[b][0] - positions[a][0]; })
        };
    });
}

function _assignments(positions, pins, groups, emit) {
    var fingers = positions.map(function () { return OPEN; });
    var last = groups.length - 1;

    function fits(indices, chosen) {
        for (var i = 0; i < indices.length; i++) {
            var pin = pins[indices[i]];
            if (pin !== null && pin !== undefined && pin !== chosen[i])
                return false;
        }
        return true;
    }

    function repeat(value, n) {
        var result = [];
        for (var i = 0; i < n; i++)
            result.push(value);
        return result;
    }

    function recurse(g, lowest, barre) {
        if (g > last) {
            emit(fingers.slice(), barre);
            return;
        }
        var indices = groups[g].indices;
        var size = indices.length;
        var available = [];
        for (var f = lowest; f <= MAX_FINGERS; f++)
            available.push(f);
        // one finger per position, in any order (crossings graded later)
        var chosenSets = combinations(available, size);
        for (var c = 0; c < chosenSets.length; c++) {
            var orders = permutations(chosenSets[c]);
            for (var o = 0; o < orders.length; o++) {
                var order = orders[o];
                if (!fits(indices, order))
                    continue;
                for (var k = 0; k < indices.length; k++)
                    fingers[indices[k]] = order[k];
                recurse(g + 1, maxOf(order) + 1, barre);
            }
        }
        if (size < 2)
            return;
        var strings = indices.map(function (i) { return positions[i][0]; }).sort(function (a, b) { return a - b; });
        // index barré on the lowest fret
        if (g === 0 && lowest === INDEX && fits(indices, repeat(INDEX, size))) {
            for (var m = 0; m < indices.length; m++)
                fingers[indices[m]] = INDEX;
            recurse(g + 1, INDEX + 1, INDEX);
        }
        // pinky barré on the highest fret: strings 1, 2, ... contiguous
        var contiguous = true;
        for (var s = 0; s < strings.length; s++)
            if (strings[s] !== s + 1)
                contiguous = false;
        if (g === last && lowest <= PINKY && size <= PINKY_BARRE_MAX_STRINGS && contiguous
                && fits(indices, repeat(PINKY, size))) {
            for (var n = 0; n < indices.length; n++)
                fingers[indices[n]] = PINKY;
            emit(fingers.slice(), PINKY);
        }
    }

    recurse(0, INDEX, null);
}

// Fingers needed at least: an index barré on the lowest fret, a pinky barré on the top.
function _minFingers(positions, groups) {
    var total = 0;
    for (var g = 0; g < groups.length; g++) {
        var indices = groups[g].indices;
        var strings = indices.map(function (i) { return positions[i][0]; }).sort(function (a, b) { return a - b; });
        var contiguous = true;
        for (var s = 0; s < strings.length; s++)
            if (strings[s] !== s + 1)
                contiguous = false;
        if (indices.length > 1 && (g === 0 || (g === groups.length - 1
                && indices.length <= PINKY_BARRE_MAX_STRINGS && contiguous)))
            total += 1;
        else
            total += indices.length;
    }
    return total;
}

function _problem(playability, issue, text, indices, excess, distance) {
    var unique = [];
    for (var i = 0; i < indices.length; i++)
        if (unique.indexOf(indices[i]) < 0)
            unique.push(indices[i]);
    return { playability: playability, issue: issue, text: text, indices: unique,
             excess: excess || 0, distance: distance || 0 };
}

// Grades one assignment; null if it is not a hand position at all.
function _grade(positions, fingers, barre, groups, table) {
    var fretted = [];
    for (var i = 0; i < fingers.length; i++)
        if (fingers[i] !== OPEN)
            fretted.push(i);
    if (!fretted.length)
        return { fingers: fingers, playability: Playability.PLAYABLE, problems: [], span: 0,
                 fingersUsed: 0, barreFinger: null, barreFret: null, cost: 0.0, excess: 0 };

    var stringsOf = {}, indicesOf = {}, fretOf = {};
    for (var k = 0; k < fretted.length; k++) {
        var idx = fretted[k], f = fingers[idx];
        (stringsOf[f] = stringsOf[f] || []).push(positions[idx][0]);
        (indicesOf[f] = indicesOf[f] || []).push(idx);
        fretOf[f] = positions[idx][1];
    }

    var barreFret = barre ? fretOf[barre] : null;
    if (barre === INDEX) {
        var low = minOf(stringsOf[INDEX]), high = maxOf(stringsOf[INDEX]);
        for (var p = 0; p < positions.length; p++)
            if (positions[p][1] === 0 && low <= positions[p][0] && positions[p][0] <= high)
                return null;                                 // open string under the barré
    }

    var difficult = [], violations = [];
    var excess = 0;
    var position = groups[0].fret;

    if (barre === PINKY) {
        var pinkyStrings = stringsOf[PINKY].slice().sort(function (a, b) { return a - b; });
        difficult.push(_problem(Playability.DIFFICULT, Issue.PINKY_BARRE,
                                "pinky barré on fret " + barreFret + ", strings " + pinkyStrings[0]
                                + "–" + pinkyStrings[pinkyStrings.length - 1], indicesOf[PINKY]));
    }

    var used = Object.keys(fretOf).map(function (x) { return parseInt(x, 10); }).sort(function (a, b) { return a - b; });
    var pairs = combinations(used, 2);
    for (var q = 0; q < pairs.length; q++) {
        var a = pairs[q][0], b = pairs[q][1];
        var involved = indicesOf[a].concat(indicesOf[b]);
        var distance = fretOf[b] - fretOf[a];
        if (distance === 0) {
            var crossing = _crossing(positions, indicesOf[a], indicesOf[b]);
            if (crossing === null)
                continue;
            if (!crossing)
                return null;                                 // crossed on strings that are not adjacent
            difficult.push(_problem(Playability.DIFFICULT, Issue.CROSSING,
                                    "fingers " + a + " and " + b + " crossed on fret " + fretOf[a], involved));
            continue;
        }
        var limit = _bestLimit(table, a, stringsOf[a], b, stringsOf[b], position);
        if (distance <= limit.green)
            continue;
        if (distance <= limit.orange) {
            difficult.push(_problem(Playability.DIFFICULT, Issue.STRETCH,
                                    "stretch: fingers " + a + "–" + b + " over " + distance + " frets",
                                    involved, 0, distance));
        } else {
            excess += distance - limit.orange;
            violations.push(_problem(Playability.UNPLAYABLE, Issue.SPAN,
                                     "fingers " + a + "–" + b + " over " + distance + " frets (max "
                                     + limit.orange + ")", involved, distance - limit.orange, distance));
        }
    }

    var frets = fretted.map(function (i) { return positions[i][1]; });
    var span = maxOf(frets) - minOf(frets);
    var playability, problems;
    if (violations.length) {
        // the worst violation first: it is the one the reason names
        playability = Playability.UNPLAYABLE;
        problems = stableSort(violations, function (x, y) {
            return (y.excess - x.excess) || (y.distance - x.distance);
        });
    } else if (difficult.length) {
        playability = Playability.DIFFICULT;
        problems = stableSort(difficult, function (x, y) { return _priority(x.issue) - _priority(y.issue); });
    } else {
        playability = Playability.PLAYABLE;
        problems = [];
    }
    return { fingers: fingers, playability: playability, problems: problems, span: span,
             fingersUsed: used.length, barreFinger: barre, barreFret: barreFret,
             cost: _cost(used, fretOf, span, barre, difficult), excess: excess };
}

// Two fingers on the same fret: null natural order, true crossed on adjacent strings,
// false crossed otherwise.
function _crossing(positions, indicesA, indicesB) {
    var stringA = positions[indicesA[0]][0];
    var stringB = positions[indicesB[0]][0];
    if (stringA > stringB)
        return null;
    return stringB - stringA === 1;
}

// The most favorable limit over the strings of the two fingers (barrés cover several).
function _bestLimit(table, a, stringsA, b, stringsB, position) {
    var best = null;
    for (var i = 0; i < stringsA.length; i++) {
        for (var j = 0; j < stringsB.length; j++) {
            var limit = table.limit(a, stringsA[i], b, stringsB[j], position);
            if (best === null || limit.orange > best.orange
                    || (limit.orange === best.orange && limit.green > best.green))
                best = limit;
        }
    }
    return best;
}

function _priority(issue) {
    if (issue === Issue.PINKY_BARRE)
        return 0;
    if (issue === Issue.STRETCH)
        return 1;
    if (issue === Issue.CROSSING)
        return 2;
    return 9;
}

// Lower is more natural (same arithmetic, in the same order, as fingering._cost).
function _cost(used, fretOf, span, barre, difficult) {
    var cost = span + 0.5 * used.length + 2.0 * difficult.length;
    if (barre === INDEX)
        cost += 1.5;
    var perFret = {}, fretOrder = [];
    for (var i = 0; i < used.length; i++) {
        var fret = fretOf[used[i]];
        if (!perFret.hasOwnProperty(fret)) {
            perFret[fret] = 0;
            fretOrder.push(fret);
        }
        perFret[fret]++;
    }
    var crowded = 0;
    for (var k = 0; k < fretOrder.length; k++)
        if (perFret[fretOrder[k]] > 2)
            crowded += perFret[fretOrder[k]] - 2;
    cost += 0.4 * crowded;
    for (var j = 0; j + 1 < used.length; j++) {
        var frets = fretOf[used[j + 1]] - fretOf[used[j]];
        if (frets)
            cost += 0.3 * Math.abs((used[j + 1] - used[j]) - frets);
    }
    cost += 0.1 * (used[0] - INDEX);
    return cost;
}

// ============================================================================
// Chord analyzer (core/analyzer.py)
// ============================================================================

// Note: plain object built by the caller, see analyzeNotes(). Placement: {string, fret, finger}.

function ChordAnalyzer(fretboard, table) {
    this._fretboard = fretboard || null;
    this._table = table || defaultTable();
    this._cache = {};
}

ChordAnalyzer.sortNotesByPitch = function (notes) {
    return stableSort(notes, function (a, b) { return b.midi - a.midi; });
};

// Every playable or difficult fingering of `notes` (best first) or a single unplayable
// analysis with the closest fingering and the reason. Empty without pitched notes.
ChordAnalyzer.prototype.candidates = function (notes, held) {
    held = held || [];
    var attacked = ChordAnalyzer.sortNotesByPitch(notes.filter(function (n) {
        return n.midi !== null && n.midi !== undefined;
    }));
    if (!attacked.length)
        return [];
    var key = attacked.map(function (n) { return n.uid; }).join(",") + "|"
            + held.map(function (h) {
                return h.note.uid + ":" + h.placement.string + "/" + h.placement.fret + "/" + h.placement.finger;
            }).join(",");
    var cached = this._cache[key];
    if (cached === undefined) {
        cached = this._candidates(attacked, held);
        this._cache[key] = cached;
    }
    return cached;
};

// The best fingering of a fixed set of positions ([{string, fret}]), nothing held.
ChordAnalyzer.prototype.analyzePositions = function (positions) {
    var search = handShapes(positions.map(function (p) { return [p.string, p.fret]; }), null, this._table);
    if (search.valid.length)
        return this._fromShape(positions, search.valid[0], [], [], []);
    return this._unplayableFromSearch(positions, search, []);
};

// Writes string, fret, finger, color and reason of `analysis` to its notes.
ChordAnalyzer.applyAnalysis = function (analysis) {
    var positions = analysis.positions.slice(analysis.fixed.length);
    var fingers = analysis.fingers.slice(analysis.fixed.length);
    for (var i = 0; i < analysis.attacked.length; i++) {
        var note = analysis.attacked[i];
        var pos = i < positions.length ? positions[i] : null;
        note.fret = pos ? [pos.string, pos.fret] : NO_FRET;
        note.finger = pos && i < fingers.length ? fingers[i] : null;
        note.color = analysis.playability;
        note.reason = analysis.reason;
    }
};

ChordAnalyzer.prototype._candidates = function (attacked, held) {
    var fixed = held.map(function (h) { return { string: h.placement.string, fret: h.placement.fret }; });
    var pins = held.map(function (h) { return h.placement.finger; });
    var usedStrings = {};
    for (var u = 0; u < fixed.length; u++)
        usedStrings[fixed[u].string] = true;
    var options = this._stringOptions(attacked, usedStrings);

    var found = [];
    for (var o = 0; o < options.length; o++) {
        var positions = fixed.concat(options[o]);
        var optionPins = pins.slice();
        for (var k = 0; k < options[o].length; k++)
            optionPins.push(null);
        var search = handShapes(positions.map(function (p) { return [p.string, p.fret]; }), optionPins, this._table);
        for (var s = 0; s < search.valid.length; s++)
            found.push(this._fromShape(positions, search.valid[s], fixed, held, attacked));
    }
    if (found.length) {
        return stableSort(found, function (a, b) {
            return (RANK[a.playability] - RANK[b.playability]) || (a.cost - b.cost);
        });
    }
    return [this._unplayable(attacked, held, fixed, options)];
};

// Every assignment of the notes to distinct free strings.
ChordAnalyzer.prototype._stringOptions = function (notes, used) {
    var result = [];
    var current = [];
    function recurse(i) {
        if (i === notes.length) {
            result.push(current.slice());
            return;
        }
        var positions = notes[i].fretPos;
        for (var p = 0; p < positions.length; p++) {
            var string = positions[p][0];
            if (used[string])
                continue;
            used[string] = true;
            current.push({ string: string, fret: positions[p][1] });
            recurse(i + 1);
            current.pop();
            delete used[string];
        }
    }
    recurse(0);
    return result;
};

ChordAnalyzer.prototype._fromShape = function (positions, shape, fixed, held, attacked) {
    var reason;
    if (shape.playability === Playability.PLAYABLE)
        reason = shape.fingersUsed ? "playable" : "open strings";
    else
        reason = this._problemsText(shape.problems, fixed.length);
    return {
        playability: shape.playability, positions: positions, fingersUsed: shape.fingersUsed,
        hasBarre: shape.barreFinger !== null, barreFret: shape.barreFret, span: shape.span,
        reason: reason, issue: shape.problems.length ? shape.problems[0].issue : Issue.NONE,
        fixed: fixed, held: (held || []).map(function (h) { return h.note; }),
        fingers: shape.fingers.slice(), attacked: (attacked || []).slice(), cost: shape.cost
    };
};

ChordAnalyzer.prototype._unplayable = function (attacked, held, fixed, options) {
    var self = this;
    var pins = held.map(function (h) { return h.placement.finger; });
    var heldNotes = held.map(function (h) { return h.note; });
    function nulls(n) {
        var result = [];
        for (var i = 0; i < n; i++)
            result.push(null);
        return result;
    }

    if (!options.length) {
        var explained = this._explainNoStrings(attacked, held, fixed);
        return {
            playability: Playability.UNPLAYABLE, positions: [], fingersUsed: 0, hasBarre: false,
            barreFret: null, span: 0, reason: explained.reason, issue: explained.issue, fixed: fixed,
            held: heldNotes, fingers: [], attacked: attacked, cost: 0.0
        };
    }

    // without pins: is the conflict only with the fingers of the held notes?
    var free = options.map(function (option) {
        var positions = fixed.concat(option);
        return { option: option,
                 search: handShapes(positions.map(function (p) { return [p.string, p.fret]; }), null, self._table) };
    });
    var withShape = [];
    for (var i = 0; i < free.length; i++)
        if (free[i].search.valid.length)
            withShape.push({ option: free[i].option, shape: free[i].search.valid[0] });
    if (withShape.length) {
        // the new notes would need fingers that the held notes keep: no finger shown
        var best = minBy(withShape, function (o) { return [RANK[o.shape.playability], o.shape.cost]; });
        var analysis = this._fromShape(fixed.concat(best.option), best.shape, fixed, held, attacked);
        analysis.playability = Playability.UNPLAYABLE;
        analysis.issue = Issue.FINGER_CONFLICT;
        analysis.reason = this._fingerConflictText(held);
        analysis.fingers = pins.concat(nulls(best.option.length));
        return analysis;
    }

    var closest = minBy(free, function (o) { return self._closeness(fixed.concat(o.option), o.search); });
    var result = this._unplayableFromSearch(fixed.concat(closest.option), closest.search, fixed);
    result.held = heldNotes;
    result.attacked = attacked;
    if (held.length)
        result.fingers = pins.concat(nulls(closest.option.length));     // geometric explanation
    return result;
};

// The closest impossible fingering: the most compact hand, then the smallest excess.
ChordAnalyzer.prototype._closeness = function (positions, search) {
    var frets = positions.filter(function (p) { return p.fret > 0; }).map(function (p) { return p.fret; });
    var span = frets.length ? maxOf(frets) - minOf(frets) : 0;
    if (search.invalid.length) {
        var best = search.invalid[0];
        return [span, 0, best.excess, best.cost];
    }
    return [span, 1, search.minFingers, 0.0];
};

ChordAnalyzer.prototype._unplayableFromSearch = function (positions, search, fixed) {
    if (search.invalid.length) {
        var shape = search.invalid[0];
        return {
            playability: Playability.UNPLAYABLE, positions: positions, fingersUsed: shape.fingersUsed,
            hasBarre: shape.barreFinger !== null, barreFret: shape.barreFret, span: shape.span,
            reason: "fret span " + shape.span + ": " + this._problemsText(shape.problems.slice(0, 1), fixed.length),
            issue: Issue.SPAN, fixed: fixed, held: [], fingers: shape.fingers.slice(), attacked: [],
            cost: shape.cost
        };
    }
    var frets = positions.filter(function (p) { return p.fret > 0; }).map(function (p) { return p.fret; });
    var span = frets.length ? maxOf(frets) - minOf(frets) : 0;
    var needed = search.minFingers;
    var reason, issue;
    if (needed > MAX_FINGERS) {
        reason = "requires " + needed + " fingers (max " + MAX_FINGERS + ")";
        issue = Issue.FINGERS;
    } else {
        reason = "no hand position (open string under a barré, or crossed fingers)";
        issue = Issue.NO_SHAPE;
    }
    return {
        playability: Playability.UNPLAYABLE, positions: positions, fingersUsed: needed, hasBarre: false,
        barreFret: null, span: span, reason: reason, issue: issue, fixed: fixed, held: [],
        fingers: positions.map(function () { return null; }), attacked: [], cost: 0.0
    };
};

ChordAnalyzer.prototype._problemsText = function (problems, heldCount) {
    return problems.map(function (p) {
        var onlyHeld = p.indices.length > 0;
        for (var i = 0; i < p.indices.length; i++)
            if (p.indices[i] >= heldCount)
                onlyHeld = false;
        return p.text + (onlyHeld ? " (held notes)" : "");
    }).join("; ");
};

ChordAnalyzer.prototype._fingerConflictText = function (held) {
    var sorted = stableSort(held, function (a, b) { return a.note.midi - b.note.midi; });
    var fretted = [];
    for (var i = 0; i < sorted.length; i++) {
        var p = sorted[i].placement;
        if (p.finger)
            fretted.push(sorted[i].note.pitchName + " (" + p.string + "/" + p.fret + ":" + p.finger + ")");
    }
    return "no free finger, held: " + fretted.join(" ");
};

// Why no string assignment exists for the attacked notes: {reason, issue}.
ChordAnalyzer.prototype._explainNoStrings = function (notes, held, fixed) {
    var self = this;
    var unreachable = notes.filter(function (n) { return !n.fretPos.length; });
    if (unreachable.length) {
        return { reason: unreachable.map(function (n) { return self._outOfRange(n); }).join("; "),
                 issue: Issue.OUT_OF_RANGE };
    }
    var strings;
    if (this._fretboard !== null) {
        strings = this._fretboard.numStrings;
    } else {
        var set = {};
        notes.forEach(function (n) { n.fretPos.forEach(function (p) { set[p[0]] = true; }); });
        fixed.forEach(function (p) { set[p.string] = true; });
        strings = Object.keys(set).length;
    }
    if (notes.length + fixed.length > strings) {
        var heldText = fixed.length ? " + " + plural(fixed.length, "held note") : "";
        return { reason: plural(notes.length, "note") + heldText + " on " + strings + " strings",
                 issue: Issue.STRINGS };
    }
    if (fixed.length) {
        return { reason: "string conflict with held notes: " + held.map(function (h) {
                     return h.note.pitchName + " (" + h.placement.string + "/" + h.placement.fret + ")";
                 }).join(", "), issue: Issue.CONFLICT };
    }
    return { reason: "string conflict: " + notes.map(function (n) { return n.pitchName; }).join(" "),
             issue: Issue.CONFLICT };
};

ChordAnalyzer.prototype._outOfRange = function (note) {
    if (this._fretboard === null)
        return note.pitchName + " out of range";
    return note.pitchName + " out of range (" + this._fretboard.outOfRangeReason(note.midi) + ")";
};

// ============================================================================
// Unisons across voices (core/unison.py)
// ============================================================================

function _soundingEnd(note, ends) {
    return ends.has(note) ? ends.get(note) : note.onset + note.soundingDuration;
}

// Whether two notes of the same pitch are meant as two notes on different strings.
function areDistinct(a, b) {
    if (a.staff === b.staff && a.voice === b.voice)
        return true;
    if (a.stringMark !== null && a.stringMark !== undefined && b.stringMark !== null && b.stringMark !== undefined)
        return a.stringMark !== b.stringMark;
    if (a.step !== b.step || a.alter !== b.alter)
        return true;
    return a.fingeringMark !== null && a.fingeringMark !== undefined
            && b.fingeringMark !== null && b.fingeringMark !== undefined
            && a.fingeringMark !== b.fingeringMark;
}

// Groups of consecutive notes with the same onset (itertools.groupby).
function _groupByOnset(notes) {
    var groups = [];
    for (var i = 0; i < notes.length; i++) {
        var last = groups.length ? groups[groups.length - 1] : null;
        if (last && last.onset === notes[i].onset)
            last.notes.push(notes[i]);
        else
            groups.push({ onset: notes[i].onset, notes: [notes[i]] });
    }
    return groups;
}

// Merges graphic doublings and finds re-attacks of sounding unisons.
// Returns {heads, merged: Map, ends: Map, reattacks: Map}.
function resolveUnisons(heads) {
    var result = { heads: [], merged: new Map(), ends: new Map(), reattacks: new Map() };
    var sounding = {};                                   // midi -> fingered notes
    var groups = _groupByOnset(heads);
    for (var g = 0; g < groups.length; g++) {
        var group = groups[g].notes;
        var kept = _mergeDoublings(group.filter(function (n) { return !n.isGrace; }), result);
        for (var k = 0; k < kept.length; k++)
            _checkReattack(kept[k], groups[g].onset, sounding, result);
        for (var i = 0; i < group.length; i++)
            if (group[i].isGrace || kept.indexOf(group[i]) >= 0)
                result.heads.push(group[i]);
    }
    return result;
}

function _mergeDoublings(notes, result) {
    var kept = [];
    var clusters = _clusters(notes);
    for (var c = 0; c < clusters.length; c++) {
        var cluster = clusters[c];
        var primary = cluster[0];                        // first among the longest
        for (var i = 1; i < cluster.length; i++)
            if (cluster[i].soundingDuration > primary.soundingDuration)
                primary = cluster[i];
        for (var j = 0; j < cluster.length; j++)
            if (cluster[j] !== primary)
                result.merged.set(cluster[j], primary);
        kept.push(primary);
    }
    return stableSort(kept, function (a, b) { return notes.indexOf(a) - notes.indexOf(b); });
}

function _clusters(notes) {
    var clusters = [];
    for (var i = 0; i < notes.length; i++) {
        var note = notes[i];
        var placed = false;
        for (var c = 0; c < clusters.length && !placed; c++) {
            var cluster = clusters[c];
            if (cluster[0].midi !== note.midi)
                continue;
            var distinct = false;
            for (var m = 0; m < cluster.length; m++)
                if (areDistinct(note, cluster[m]))
                    distinct = true;
            if (!distinct) {
                cluster.push(note);
                placed = true;
            }
        }
        if (!placed)
            clusters.push([note]);
    }
    return clusters;
}

function _checkReattack(note, onset, sounding, result) {
    var previous = sounding[note.midi] || [];
    var active = previous.filter(function (h) { return _soundingEnd(h, result.ends) > onset; });
    var released = active.filter(function (h) { return !areDistinct(h, note); });
    if (released.length) {
        result.reattacks.set(note, released[0]);
        var end = _soundingEnd(note, result.ends);
        for (var i = 0; i < released.length; i++)
            end = Math.max(end, _soundingEnd(released[i], result.ends));
        if (end !== note.onset + note.soundingDuration)
            result.ends.set(note, end);
        for (var j = 0; j < released.length; j++)
            result.ends.set(released[j], onset);
    }
    sounding[note.midi] = active.filter(function (h) { return released.indexOf(h) < 0; }).concat([note]);
}

// ============================================================================
// Playability engine (core/playability.py)
// ============================================================================

// Pitched, visible, not a cue note, not a harmonic.
function isAnalyzable(note) {
    return note.midi !== null && note.midi !== undefined
            && !(note.isRest || note.isCue || note.isHarmonic || note.isHidden);
}

var _nextUid = 1;

// Fills the defaults of a note built by the caller. Required: onset, duration (ticks),
// midi (sounding, or null), pitchName. Optional: voice, staff, step, alter, measureNumber,
// beatLabel, isGrace, isChord (grace chords), isHidden, isCue, isHarmonic, isRest,
// isUnpitched, tieStart, tieStop, stringMark, fingeringMark, reason, ref (caller's data).
function makeNote(fields) {
    var note = {
        uid: _nextUid++,
        onset: 0, duration: 0, midi: null, pitchName: "", step: null, alter: 0,
        voice: "1", staff: 1, measureNumber: "", beatLabel: "",
        isRest: false, isUnpitched: false, isChord: false, isGrace: false, isCue: false,
        isHarmonic: false, isHidden: false, tieStart: false, tieStop: false,
        stringMark: null, fingeringMark: null,
        fretPos: [], fret: NO_FRET, finger: null, color: DEFAULT_COLOR, reason: "",
        soundingDuration: null, ref: null
    };
    for (var key in fields)
        if (fields.hasOwnProperty(key))
            note[key] = fields[key];
    if (note.soundingDuration === null)
        note.soundingDuration = note.duration;
    return note;
}

// Colors every analyzable note of one part (color, fret, finger, reason).
// `notes` in score order (makeNote objects). Returns {events, notAnalyzed, unisons}.
function analyzeNotes(notes, fretboard) {
    var result = { events: [], notAnalyzed: [], unisons: [] };
    var candidates = [];
    for (var i = 0; i < notes.length; i++) {
        var note = notes[i];
        if (isAnalyzable(note)) {
            note.fretPos = fretboard.positions(note.midi);
            candidates.push(note);
        } else if (!(note.isRest || note.isUnpitched || note.isHidden)) {
            if (note.isCue && !note.reason)
                note.reason = "cue note";
            result.notAnalyzed.push(note);
        }
    }

    var ordered = stableSort(candidates, function (a, b) { return a.onset - b.onset; });
    var linked = _linkTies(ordered);
    var unisons = resolveUnisons(linked.heads);

    var search = new BeamSearch(new ChordAnalyzer(fretboard), unisons.ends);
    var groups = _groupByOnset(unisons.heads);
    for (var g = 0; g < groups.length; g++)
        search.step(groups[g].onset, groups[g].notes);

    var choices = search.bestChoices();
    for (var c = 0; c < choices.length; c++) {
        var choice = choices[c];
        ChordAnalyzer.applyAnalysis(choice.analysis);
        result.events.push({ onset: choice.onset, measureNumber: choice.notes[0].measureNumber,
                             notes: choice.notes, held: choice.analysis.held,
                             analysis: choice.analysis, grace: choice.grace });
    }

    result.unisons = _markReattacks(unisons.reattacks);
    _propagateResults(unisons.merged);
    _propagateResults(linked.continuations);
    return result;
}

function _handPosition(analysis, previous) {
    if (analysis.playability === Playability.UNPLAYABLE)
        return previous;
    var frets = analysis.positions.filter(function (p) { return p.fret > 0; }).map(function (p) { return p.fret; });
    return frets.length ? minOf(frets) : previous;
}

// Beam search over the onsets: keeps the best BEAM_WIDTH partial fingerings of the part.
function BeamSearch(analyzer, ends) {
    this._analyzer = analyzer;
    this._ends = ends || new Map();
    // cost: [unplayable notes, difficult notes, earliness of unplayable events, ergonomic cost]
    this._paths = [{ cost: [0, 0, 0, 0.0], state: [], position: null, parent: null, choices: [] }];
    this._active = [];                                   // [{end, note}] still sounding
    this._index = 0;
}

BeamSearch.prototype.step = function (onset, group) {
    this._active = this._active.filter(function (a) { return a.end > onset; });
    var sounding = new Set(this._active.map(function (a) { return a.note; }));
    this._index++;

    var graces = _graceChords(group.filter(function (n) { return n.isGrace; }));
    var attacks = group.filter(function (n) { return !n.isGrace; });

    var extended = [];
    var paths = this._merged(sounding);
    for (var p = 0; p < paths.length; p++) {
        var path = paths[p];
        var cost = path.cost, choices = [];
        var held = path.state;
        for (var g = 0; g < graces.length; g++) {           // fingered alone: they do not constrain
            var graceOptions = this._analyzer.candidates(graces[g], held);
            if (graceOptions.length) {
                cost = this._add(cost, graceOptions[0], graces[g].length, null);
                choices.push({ onset: onset, notes: graces[g], analysis: graceOptions[0], grace: true });
            }
        }
        if (!attacks.length) {
            extended.push({ cost: cost, state: path.state, position: path.position, parent: path, choices: choices });
            continue;
        }
        var options = this._analyzer.candidates(attacks, held).slice(0, BEAM_CANDIDATES);
        for (var o = 0; o < options.length; o++) {
            extended.push({
                cost: this._add(cost, options[o], attacks.length, path.position),
                state: path.state.concat(BeamSearch._placements(options[o])),
                position: _handPosition(options[o], path.position),
                parent: path,
                choices: choices.concat([{ onset: onset, notes: attacks, analysis: options[o], grace: false }])
            });
        }
    }

    extended = stableSort(extended, function (a, b) { return compareTuples(a.cost, b.cost); });
    this._paths = extended.slice(0, BEAM_WIDTH);
    for (var a = 0; a < attacks.length; a++) {
        var n = attacks[a];
        this._active.push({ end: this._ends.has(n) ? this._ends.get(n) : n.onset + n.soundingDuration, note: n });
    }
};

// The choices of the best complete path, in onset order.
BeamSearch.prototype.bestChoices = function () {
    var path = minBy(this._paths, function (p) { return p.cost; });
    var chain = [];
    while (path !== null) {
        chain.push(path.choices);
        path = path.parent;
    }
    var result = [];
    for (var i = chain.length - 1; i >= 0; i--)
        for (var j = 0; j < chain[i].length; j++)
            result.push(chain[i][j]);
    return result;
};

// Drops released notes from the states; equal states keep only their best path.
BeamSearch.prototype._merged = function (sounding) {
    var best = new Map();
    for (var i = 0; i < this._paths.length; i++) {
        var path = this._paths[i];
        var state = path.state.filter(function (h) { return sounding.has(h.note); });
        var key = state.map(function (h) {
            return h.note.uid + ":" + h.placement.string + "/" + h.placement.fret + "/" + h.placement.finger;
        }).sort().join(",") + "@" + path.position;
        var current = best.get(key);
        if (current === undefined || compareTuples(path.cost, current.cost) < 0)
            best.set(key, { cost: path.cost, state: state, position: path.position,
                            parent: path.parent, choices: path.choices });
    }
    var values = [];
    best.forEach(function (value) { values.push(value); });
    return stableSort(values, function (a, b) { return compareTuples(a.cost, b.cost); });
};

BeamSearch.prototype._add = function (cost, analysis, count, position) {
    var red = cost[0], orange = cost[1], earliness = cost[2], ergonomic = cost[3];
    if (analysis.playability === Playability.UNPLAYABLE) {
        red += count;
        earliness -= this._index;
    } else if (analysis.playability === Playability.DIFFICULT) {
        orange += count;
    }
    ergonomic += analysis.cost;
    var newPosition = _handPosition(analysis, null);
    if (position !== null && newPosition !== null)
        ergonomic += POSITION_SHIFT_COST * Math.abs(newPosition - position);
    return [red, orange, earliness, ergonomic];
};

// Placements of the attacked notes; unplayable notes do not constrain.
BeamSearch._placements = function (analysis) {
    if (analysis.playability === Playability.UNPLAYABLE)
        return [];
    var positions = analysis.positions.slice(analysis.fixed.length);
    var fingers = analysis.fingers.slice(analysis.fixed.length);
    var count = Math.min(analysis.attacked.length, positions.length, fingers.length);
    var result = [];
    for (var i = 0; i < count; i++)
        result.push({ note: analysis.attacked[i],
                      placement: { string: positions[i].string, fret: positions[i].fret, finger: fingers[i] || 0 } });
    return result;
};

// Groups grace notes into chords: a note with isChord joins the previous one.
function _graceChords(graces) {
    var chords = [];
    for (var i = 0; i < graces.length; i++) {
        if (graces[i].isChord && chords.length)
            chords[chords.length - 1].push(graces[i]);
        else
            chords.push([graces[i]]);
    }
    return chords;
}

// Splits notes into heads (analyzed) and tied continuations (Map continuation -> head).
function _linkTies(ordered) {
    var heads = [];
    var continuations = new Map();
    var openByVoice = new Map();
    var openByPitch = new Map();

    function close(head) {
        [openByVoice, openByPitch].forEach(function (table) {
            var keys = [];
            table.forEach(function (value, key) { if (value === head) keys.push(key); });
            keys.forEach(function (key) { table.delete(key); });
        });
    }

    for (var i = 0; i < ordered.length; i++) {
        var note = ordered[i];
        var voiceKey = note.staff + "|" + note.voice + "|" + note.midi;
        var pitchKey = note.staff + "|" + note.midi;
        var head = null;
        if (note.tieStop)
            head = openByVoice.get(voiceKey) || openByPitch.get(pitchKey) || null;
        if (head !== null) {
            continuations.set(note, head);
            head.soundingDuration += note.duration;
            close(head);
            if (note.tieStart) {
                openByVoice.set(voiceKey, head);
                openByPitch.set(pitchKey, head);
            }
            continue;
        }
        heads.push(note);
        if (note.tieStart) {
            openByVoice.set(voiceKey, note);
            openByPitch.set(pitchKey, note);
        }
    }
    return { heads: heads, continuations: continuations };
}

// Marks purple the re-attacks of a sounding unison that are playable or difficult.
function _markReattacks(reattacks) {
    var marked = [];
    reattacks.forEach(function (released, note) {
        if (note.color !== "green" && note.color !== "orange")
            return;
        var reason = "re-attacks " + released.pitchName + " still sounding in voice "
                + released.voice + ": one note on one string";
        if (note.color === "orange")
            reason += "; " + note.reason;
        note.color = NOT_AS_WRITTEN_COLOR;
        note.reason = reason;
        marked.push(note);
    });
    return marked;
}

// Copies the result of the fingered note to tied continuations and graphic doublings.
function _propagateResults(sources) {
    sources.forEach(function (head, note) {
        note.color = head.color;
        note.fret = head.fret;
        note.finger = head.finger;
        note.reason = head.reason;
    });
}

// ============================================================================
// Labels and report (core/writer.py label_text, core/report.py)
// ============================================================================

function labelText(analysis) {
    var template = LABEL_TEXT.hasOwnProperty(analysis.issue) ? LABEL_TEXT[analysis.issue] : analysis.issue;
    return format(template, { fingers: analysis.fingersUsed, span: analysis.span });
}

// string/fret:finger (finger only on fretted notes), or "-" without a position.
function formatPosition(note, withFinger) {
    if (withFinger === undefined)
        withFinger = true;
    var string = note.fret[0], fret = note.fret[1];
    if (string <= 0)
        return "-";
    if (withFinger && fret > 0 && note.finger)
        return string + "/" + fret + ":" + note.finger;
    return string + "/" + fret;
}

// Pitched, visible notes per color.
function countColors(notes) {
    var counts = { green: 0, orange: 0, red: 0, purple: 0, black: 0 };
    for (var i = 0; i < notes.length; i++) {
        var n = notes[i];
        if (n.isRest || n.isUnpitched || n.isHidden)
            continue;
        counts[n.color] = (counts[n.color] || 0) + 1;
    }
    return counts;
}

function _field(label, value, indent) {
    var pad = label;
    while (pad.length < 8)
        pad += " ";
    var spaces = "";
    for (var i = 0; i < (indent || 0); i++)
        spaces += " ";
    return spaces + pad + " " + value;
}

// One point of the report: {measureNumber, beatLabel, status, lines, notes, color}.
function describeEvent(event) {
    var analysis = event.analysis;
    var notes = stableSort(event.notes, function (a, b) { return a.midi - b.midi; });
    var status = (analysis.playability === Playability.UNPLAYABLE ? "UNPLAYABLE" : "DIFFICULT")
            + (event.grace ? " (grace notes)" : "");
    var lines = [_field("Notes:", notes.map(function (n) { return n.pitchName; }).join(" "), 2)];
    if (event.held.length) {
        var held = stableSort(event.held, function (a, b) { return a.midi - b.midi; });
        lines.push(_field("Held:", held.map(function (n) {
            return n.pitchName + " (" + formatPosition(n) + ")";
        }).join(" "), 2));
    }
    lines.push(_field("Reason:", analysis.reason, 2));
    var placed = notes.some(function (n) { return n.fret[0] !== -1 || n.fret[1] !== -1; });
    if (placed)
        lines.push(_field("Closest:", notes.map(function (n) { return formatPosition(n); }).join(" "), 2));
    return { measureNumber: event.measureNumber, beatLabel: notes[0].beatLabel, status: status,
             label: labelText(analysis), color: analysis.playability, lines: lines, notes: notes };
}

// Text report of one analyzed part (report.py _part_section).
function renderPartSection(part) {
    var counts = countColors(part.notes);
    var analyzed = counts.green + counts.orange + counts.red + counts.purple;
    var percent = analyzed ? Math.round(100 * counts.green / analyzed) : 0;
    var lines = [
        "== " + part.name + " ==",
        _field("Tuning:", part.fretboard.describe()),
        "Notes analyzed " + analyzed + " · playable " + counts.green + " (" + percent + "%) · difficult "
                + counts.orange + " · unplayable " + counts.red + " · not as written " + counts.purple
                + " · not analyzed " + counts.black
    ];
    var problems = part.result.events.filter(function (e) { return e.analysis.playability !== Playability.PLAYABLE; });
    if (!problems.length)
        lines.push("", "No difficult or unplayable passages.");
    problems.forEach(function (event) {
        var point = describeEvent(event);
        lines.push("", "m. " + point.measureNumber + ", beat " + point.beatLabel + " — " + point.status);
        Array.prototype.push.apply(lines, point.lines);
    });
    [["Not playable as written: unisons played as one note", part.result.unisons],
     ["Not analyzed", part.result.notAnalyzed]].forEach(function (section) {
        if (!section[1].length)
            return;
        lines.push("", section[0]);
        section[1].forEach(function (n) {
            lines.push("  m. " + n.measureNumber + ", beat " + n.beatLabel + " — " + n.pitchName + ": " + n.reason);
        });
    });
    return lines.join("\n");
}

// One line per part: "Guitar: 120 notes · 3 difficult · 1 unplayable (m. 12)".
function renderSummary(part, maxMeasures) {
    maxMeasures = maxMeasures || 8;
    var counts = countColors(part.notes);
    var total = counts.green + counts.orange + counts.red + counts.purple;
    var red = [];
    part.notes.forEach(function (n) {
        if (n.color === "red" && !n.isHidden && red.indexOf(n.measureNumber) < 0)
            red.push(n.measureNumber);
    });
    var where = "";
    if (red.length)
        where = " (m. " + red.slice(0, maxMeasures).join(", ") + (red.length > maxMeasures ? " …" : "") + ")";
    return part.name + ": " + total + " notes · " + counts.orange + " difficult · " + counts.red + " unplayable"
            + (counts.purple ? " · " + counts.purple + " not as written" : "") + where;
}
