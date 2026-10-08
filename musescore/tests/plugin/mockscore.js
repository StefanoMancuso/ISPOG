// SPDX-License-Identifier: GPL-3.0-or-later
//
// Test double of a MuseScore score for the plugin tests (run_plugin_tests.py): the
// members of the MuseScore 4.7 plugin API that ispog.qml uses, built from a JSON spec.
// Records undoable commands, color writes outside a command and selections.

function build(spec, types) {
    var score = {
        startCmdCount: 0,
        endCmdCount: 0,
        inCmd: false,
        writesOutsideCmd: 0,
        colorWrites: 0,
        shown: null,
        metaTags: {},
        nmeasures: spec.measures.length,
        duration: spec.duration,
        ntracks: spec.staves * 4,
        parts: [],
        staves: [],
        notes: [],                                 // every note, for the tests
        notesByKey: {}
    };

    function makeNote(n) {
        var note = {
            type: types.NOTE, eid: "note-" + n.key, key: n.key, pitch: n.pitch, tpc1: n.tpc1,
            tuning: n.tuning || 0, visible: n.visible, tieForward: n.tieForward ? {} : null,
            tieBack: n.tieBack ? {} : null, _color: n.color || "#000000"
        };
        Object.defineProperty(note, "color", {
            get: function () { return this._color; },
            set: function (value) {
                if (!score.inCmd)
                    score.writesOutsideCmd++;
                score.colorWrites++;
                this._color = String(value);
            }
        });
        score.notes.push(note);
        score.notesByKey[n.key] = note;
        return note;
    }

    function makeChord(c, tick, duration) {
        return {
            type: types.CHORD, tick: tick, actualDuration: { ticks: duration },
            notes: c.notes.map(makeNote),
            graceNotesBefore: (c.graceBefore || []).map(function (g) { return makeChord(g, tick, 0); }),
            graceNotesAfter: []
        };
    }

    // chords per "staff/voice", in time order
    var tracks = {};
    spec.chords.forEach(function (c) {
        var key = c.staff + "/" + c.voice;
        (tracks[key] = tracks[key] || []).push(makeChord(c, c.tick, c.duration));
    });
    Object.keys(tracks).forEach(function (key) {
        tracks[key].sort(function (a, b) { return a.tick - b.tick; });
    });

    var measures = spec.measures.map(function (m) {
        return { no: m.no, firstSegment: { tick: m.start }, timesigActual: { denominator: m.beatType },
                 nextMeasure: null };
    });
    for (var i = 0; i + 1 < measures.length; i++)
        measures[i].nextMeasure = measures[i + 1];
    score.firstMeasure = measures[0];

    var firstStaff = 0;
    spec.parts.forEach(function (p) {
        var instrument = {
            stringData: { strings: p.strings.map(function (pitch) { return { pitch: pitch, open: false }; }),
                          frets: p.frets }
        };
        score.parts.push({
            startTrack: firstStaff * 4, endTrack: (firstStaff + p.staves) * 4,
            instrumentId: p.instrumentId, longName: p.name, partName: p.name,
            hasPitchedStaff: true, hasTabStaff: false, instruments: [instrument],
            instrumentAtTick: function () { return instrument; }
        });
        firstStaff += p.staves;
    });
    for (var s = 0; s < spec.staves; s++)
        score.staves.push({ isTabStaff: function () { return false; } });

    score.selection = {
        isRange: false, startSegment: null, endSegment: null, elements: [],
        clear: function () { this.elements = []; return true; },
        select: function (element, add) {
            if (!add)
                this.elements = [];
            this.elements.push(element);
            return true;
        }
    };

    score.metaTag = function (tag) { return score.metaTags[tag] || ""; };
    score.setMetaTag = function (tag, value) { score.metaTags[tag] = String(value); };
    score.startCmd = function () {
        if (score.inCmd)
            throw new Error("startCmd inside a command");
        score.inCmd = true;
        score.startCmdCount++;
    };
    score.endCmd = function () {
        if (!score.inCmd)
            throw new Error("endCmd without startCmd");
        score.inCmd = false;
        score.endCmdCount++;
    };
    score.showElementInScore = function (element) { score.shown = element; };

    score.newCursor = function () {
        var cursor = {
            staffIdx: 0, voice: 0, _list: [], _index: 0,
            rewind: function () {
                this._list = tracks[this.staffIdx + "/" + this.voice] || [];
                this._index = 0;
            },
            next: function () {
                this._index++;
                return this._index < this._list.length;
            }
        };
        Object.defineProperty(cursor, "segment", {
            get: function () { return this._index < this._list.length ? { tick: this.tick } : null; }
        });
        Object.defineProperty(cursor, "element", {
            get: function () { return this._index < this._list.length ? this._list[this._index] : null; }
        });
        Object.defineProperty(cursor, "tick", {
            get: function () { return this._index < this._list.length ? this._list[this._index].tick : 0; }
        });
        return cursor;
    };

    return score;
}
