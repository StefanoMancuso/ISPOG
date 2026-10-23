// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Stefano Mancuso
//
// ISPOG - Is it Playable on Guitar? MuseScore Studio plugin (4.6 and later).
//
// Checks the guitar parts of the open score with the ISPOG playability engine
// (ispog_engine.js, a port of the ISPOG core) and colors the noteheads:
// green playable, orange difficult, red unplayable, purple playable only as one note.
//
// - Every guitar part is detected (instrument id) and analyzed with its own tuning and
//   number of frets, taken from the instrument and editable here; other plucked parts
//   can be enabled by hand. Settings are saved in the score.
// - The analysis runs only on request (Analyze), on the whole score or on the selected
//   measures: a full analysis of a large score takes seconds, and MuseScore waits for it.
// - Clicking a problem selects its notes in the score.

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import MuseScore 3.0
import "ispog_engine.js" as Engine

MuseScore {
    id: root

    version: "1.0.1.dev0"
    title: "ISPOG"
    description: "Is it Playable on Guitar? Colors the notes of the guitar parts by playability."
    categoryCode: "color-notes"
    requiresScore: true
    pluginType: "dialog"
    width: 480
    height: 680

    // --- Constants -----------------------------------------------------------

    readonly property string settingsTag: "ispogSettings"
    readonly property int settingsVersion: 1
    readonly property int voicesPerStaff: 4
    readonly property int repaintMs: 40              // lets "Analyzing…" appear before the work
    readonly property real microtoneCents: 25        // |tuning| from this many cents: not analyzed
    // Colors written by earlier versions of the plugin, removed by Clear and re-analysis
    readonly property var legacyColors: ["#8e24aa"]

    readonly property var theme: ({
        window: "#f5f5f5",
        text: "#1e1e1e",
        base: "#ffffff",
        button: "#e0e0e0",
        highlight: "#2e6db4",
        muted: "#6b6b6b",
        border: "#c8c8c8"
    })

    // --- State ---------------------------------------------------------------

    property bool busy: false
    property string statusText: ""
    property string reportText: ""
    property var problemRefs: []                     // per row of problemsModel: MuseScore notes
    property bool stale: false                        // settings changed since the last analysis
    property int lastDurationMs: 0

    ListModel { id: partsModel }
    ListModel { id: problemsModel }

    // Read-only views of the models (tests, other tools)
    readonly property var partRows: partsModel
    readonly property var problemRows: problemsModel

    // ========================================================================
    // Score reading
    // ========================================================================

    // [{start, number, beatType}] for every measure, in order.
    function readMeasures() {
        var measures = [];
        for (var m = curScore.firstMeasure; m; m = m.nextMeasure) {
            var beatType = 4;
            try {
                if (m.timesigActual && m.timesigActual.denominator > 0)
                    beatType = m.timesigActual.denominator;
            } catch (e) {
                // keep quarter beats
            }
            measures.push({ start: m.firstSegment.tick, number: String(m.no + 1), beatType: beatType });
        }
        return measures;
    }

    // Index of the measure containing tick (binary search).
    function measureIndexAt(measures, tick) {
        var low = 0, high = measures.length - 1;
        while (low < high) {
            var mid = (low + high + 1) >> 1;
            if (measures[mid].start <= tick)
                low = mid;
            else
                high = mid - 1;
        }
        return low;
    }

    // "3" or "2 1/2", in units of the time signature (as the desktop report).
    function beatLabel(offsetTicks, beatType) {
        var numerator = offsetTicks * beatType;
        var denominator = 4 * division;
        var whole = Math.floor(numerator / denominator);
        var rest = numerator - whole * denominator;
        if (rest === 0)
            return String(whole + 1);
        var a = rest, b = denominator;
        while (b) {
            var t = a % b; a = b; b = t;
        }
        return String(whole + 1) + " " + (rest / a) + "/" + (denominator / a);
    }

    // Step and alteration from a tonal pitch class (MuseScore tpc: 14 = C, 21 = C#).
    function spelling(tpc) {
        var steps = "FCGDAEB";
        return { step: steps.charAt(((tpc + 1) % 7 + 7) % 7), alter: Math.floor((tpc + 1) / 7) - 2 };
    }

    // Parts of the score with their staves, guitars detected.
    function readParts() {
        var parts = [];
        var start = null;
        try {
            start = fractionFromTicks(0);                // plugin API 4.6
        } catch (e) {
            start = null;
        }
        for (var i = 0; i < curScore.parts.length; i++) {
            var part = curScore.parts[i];
            var staves = [];
            var firstStaff = Math.floor(part.startTrack / voicesPerStaff);
            var endStaff = Math.floor(part.endTrack / voicesPerStaff);
            for (var s = firstStaff; s < endStaff; s++) {
                var tab = false;
                try {
                    tab = start !== null && part.hasPitchedStaff && curScore.staves[s].isTabStaff(start);
                } catch (e) {
                    tab = false;
                }
                if (!tab)                               // TAB doubling the notation: skipped
                    staves.push(s);
            }
            var instrument = null;
            try {
                instrument = start !== null ? part.instrumentAtTick(start) : null;
            } catch (e) {
                instrument = null;
            }
            if (!instrument && part.instruments.length)
                instrument = part.instruments[0];
            var tuning = [], frets = Engine.DEFAULT_NUM_FRETS;
            if (instrument && instrument.stringData) {
                var strings = instrument.stringData.strings;
                var pitches = [];
                for (var k = 0; k < strings.length; k++)
                    pitches.push(strings[k].pitch);
                // MuseScore lists the strings from the lowest; string 1 (highest) first here
                if (pitches.length > 1 && pitches[0] < pitches[pitches.length - 1])
                    pitches.reverse();
                tuning = pitches.map(Engine.midiToNoteName);
                if (instrument.stringData.frets > 0)
                    frets = instrument.stringData.frets;
            }
            var id = part.instrumentId || "";
            parts.push({
                index: i,
                key: i + ":" + id,
                name: part.longName || part.partName || id || ("Part " + (i + 1)),
                instrumentId: id,
                isGuitar: /guitar/i.test(id) && !/bass/i.test(id),
                staves: staves,
                instrumentTuning: tuning.join(" "),
                instrumentFrets: Math.max(Engine.MIN_FRETS, Math.min(Engine.MAX_FRETS, frets))
            });
        }
        return parts;
    }

    // Engine notes of one part, in score order (measure, staff, voice, time).
    function collectPart(staves, measures) {
        var notes = [];
        var cursor = curScore.newCursor();
        for (var s = 0; s < staves.length; s++) {
            for (var voice = 0; voice < voicesPerStaff; voice++) {
                cursor.staffIdx = staves[s];
                cursor.voice = voice;
                cursor.rewind(Cursor.SCORE_START);
                while (cursor.segment) {
                    var element = cursor.element;
                    if (element && element.type === Element.CHORD)
                        addChord(notes, element, cursor.tick, s + 1, voice + 1, measures);
                    cursor.next();
                }
            }
        }
        var order = function (n) { return n.measureIndex; };
        return Engine.stableSort(notes, function (a, b) {
            return (order(a) - order(b)) || (a.staff - b.staff) || (Number(a.voice) - Number(b.voice))
                    || (a.onset - b.onset);
        });
    }

    function addChord(notes, chord, tick, staff, voice, measures) {
        var duration = chord.actualDuration.ticks;
        // graceNotesBefore/After: plugin API of MuseScore 4.6; graceNotes before it
        var before = chord.graceNotesBefore !== undefined ? chord.graceNotesBefore : chord.graceNotes;
        var after = chord.graceNotesAfter !== undefined ? chord.graceNotesAfter : [];
        for (var b = 0; b < before.length; b++)
            addNotes(notes, before[b], tick, 0, true, staff, voice, measures);
        addNotes(notes, chord, tick, duration, false, staff, voice, measures);
        for (var a = 0; a < after.length; a++)
            addNotes(notes, after[a], tick + duration, 0, true, staff, voice, measures);
    }

    function addNotes(notes, chord, tick, duration, grace, staff, voice, measures) {
        var chordNotes = chord.notes;
        var measureIndex = measureIndexAt(measures, tick);
        var measure = measures[measureIndex];
        for (var i = 0; i < chordNotes.length; i++) {
            var n = chordNotes[i];
            var spelled = spelling(n.tpc1);
            var octave = Math.floor((n.pitch - Engine.STEP_SEMITONES[spelled.step] - spelled.alter) / 12) - 1;
            var microtone = Math.abs(n.tuning) >= microtoneCents;
            notes.push(Engine.makeNote({
                onset: tick,
                duration: duration,
                midi: microtone ? null : n.pitch,
                step: spelled.step,
                alter: spelled.alter,
                pitchName: Engine.spelledName(spelled.step, spelled.alter, octave),
                voice: String(voice),
                staff: staff,
                measureNumber: measure.number,
                measureIndex: measureIndex,
                beatLabel: beatLabel(tick - measure.start, measure.beatType),
                isGrace: grace,
                isChord: i > 0,
                isHidden: !n.visible,
                tieStart: n.tieForward !== null && n.tieForward !== undefined,
                tieStop: n.tieBack !== null && n.tieBack !== undefined,
                reason: microtone ? "microtone not analyzed" : "",
                ref: n
            }));
        }
    }

    // ========================================================================
    // Settings
    // ========================================================================

    function loadParts() {
        var saved = {};
        try {
            var text = curScore.metaTag(settingsTag);
            if (text) {
                var data = JSON.parse(text);
                if (data && data.parts)
                    saved = data.parts;
                if (data && data.showGreen !== undefined)
                    showGreen.checked = !!data.showGreen;
            }
        } catch (e) {
            statusText = "Saved settings unreadable: defaults used.";
        }
        partsModel.clear();
        var parts = readParts();
        for (var i = 0; i < parts.length; i++) {
            var p = parts[i];
            var s = saved[p.key] || {};
            var defaultTuning = p.instrumentTuning || Engine.TUNING_PRESETS[0].notes.join(" ");
            partsModel.append({
                key: p.key,
                partIndex: p.index,
                name: p.name,
                instrumentId: p.instrumentId,
                isGuitar: p.isGuitar,
                staves: JSON.stringify(p.staves),
                instrumentTuning: defaultTuning,
                instrumentFrets: p.instrumentFrets,
                analyze: s.analyze !== undefined ? !!s.analyze : p.isGuitar,
                tuning: s.tuning || defaultTuning,
                frets: s.frets || p.instrumentFrets
            });
        }
    }

    function saveSettings() {
        var parts = {};
        for (var i = 0; i < partsModel.count; i++) {
            var p = partsModel.get(i);
            parts[p.key] = { analyze: p.analyze, tuning: p.tuning, frets: p.frets };
        }
        var text = JSON.stringify({ version: settingsVersion, showGreen: showGreen.checked, parts: parts });
        curScore.startCmd();
        curScore.setMetaTag(settingsTag, text);
        curScore.endCmd();
        statusText = "Settings saved in the score (save the score to keep them).";
    }

    // Problem with a part's settings, or "" if valid.
    function settingsError(tuningText, frets) {
        var tuning = Engine.parseTuning(tuningText);
        if (!tuning)
            return "invalid tuning: use note names, string 1 first (e.g. E4 B3 G3 D3 A2 E2)";
        if (tuning.length < Engine.MIN_STRINGS || tuning.length > Engine.MAX_STRINGS)
            return "tuning: " + Engine.MIN_STRINGS + " to " + Engine.MAX_STRINGS + " strings";
        if (frets < Engine.MIN_FRETS || frets > Engine.MAX_FRETS)
            return "frets: " + Engine.MIN_FRETS + " to " + Engine.MAX_FRETS;
        return "";
    }

    function presetIndex(tuningText, instrumentTuning) {
        var normalized = (Engine.parseTuning(tuningText) || []).join(" ");
        if (normalized === (Engine.parseTuning(instrumentTuning) || []).join(" "))
            return 1;
        for (var i = 0; i < Engine.TUNING_PRESETS.length; i++)
            if (normalized === Engine.TUNING_PRESETS[i].notes.join(" "))
                return i + 2;
        return 0;
    }

    function presetNames() {
        var names = ["Custom", "Instrument"];
        for (var i = 0; i < Engine.TUNING_PRESETS.length; i++)
            names.push(Engine.TUNING_PRESETS[i].name);
        return names;
    }

    // ========================================================================
    // Analysis
    // ========================================================================

    // Ticks [start, end) of the selected measures, or null without a range selection.
    function selectedRange() {
        var selection = curScore.selection;
        if (!selection || !selection.isRange || !selection.startSegment)
            return null;
        var end = selection.endSegment ? selection.endSegment.tick : Number.MAX_VALUE;
        return { start: selection.startSegment.tick, end: end };
    }

    // Notes of every part, or only of the notes attacked in `range` ({start, end} ticks).
    function collectAll(range) {
        var measures = readMeasures();
        var collected = [];
        for (var i = 0; i < partsModel.count; i++) {
            var p = partsModel.get(i);
            var notes = collectPart(JSON.parse(p.staves), measures);
            if (range)
                notes = notes.filter(function (n) { return n.onset >= range.start && n.onset < range.end; });
            collected.push({ key: p.key, name: p.name, analyze: p.analyze, tuning: p.tuning, frets: p.frets,
                             notes: notes });
        }
        return collected;
    }

    // Shows "Analyzing…", then analyzes once the dialog has been repainted.
    function requestAnalysis(selectionOnly) {
        if (!curScore || busy)
            return;
        var range = null;
        if (selectionOnly) {
            range = selectedRange();
            if (!range) {
                statusText = "Select a range of measures first (click a measure, Shift+click another).";
                return;
            }
        }
        busy = true;
        statusText = "Analyzing…";
        pendingRange = range;
        analysisTimer.restart();
    }

    property var pendingRange: null

    Timer {
        id: analysisTimer
        interval: root.repaintMs
        repeat: false
        onTriggered: {
            root.busy = false;
            root.analyze(root.pendingRange);
        }
    }

    // Analyzes the whole score, or the notes attacked in `range` ({start, end} ticks): notes
    // still sounding from before the range are not taken into account. The ISPOG colors of
    // the parts not analyzed are removed; outside the range nothing changes.
    function analyze(range) {
        if (!curScore || busy)
            return;
        busy = true;
        var started = Date.now();
        try {
            var collected = collectAll(range || null);
            var sections = [], summaries = [], points = [], errors = [];
            var toColor = [];                          // [{note, color}] for every collected note

            for (var p = 0; p < collected.length; p++) {
                var part = collected[p];
                var error = part.analyze ? settingsError(part.tuning, part.frets) : "";
                if (!part.analyze || error) {
                    if (error)
                        errors.push(part.name + ": " + error);
                    for (var k = 0; k < part.notes.length; k++)
                        toColor.push({ note: part.notes[k].ref, color: null });
                    continue;
                }
                var fretboard = new Engine.Fretboard(Engine.parseTuning(part.tuning), part.frets);
                var result = Engine.analyzeNotes(part.notes, fretboard);
                var info = { name: part.name, fretboard: fretboard, notes: part.notes, result: result };
                sections.push(Engine.renderPartSection(info));
                summaries.push(Engine.renderSummary(info));

                for (var n = 0; n < part.notes.length; n++) {
                    var note = part.notes[n];
                    var color = note.color;
                    var visible = !note.isHidden && color !== Engine.DEFAULT_COLOR
                            && (color !== "green" || showGreen.checked);
                    toColor.push({ note: note.ref, color: visible ? Engine.COLOR_CODES[color] : null });
                }
                for (var e = 0; e < result.events.length; e++) {
                    var event = result.events[e];
                    if (event.analysis.playability === "green")
                        continue;
                    var point = Engine.describeEvent(event);
                    points.push({ part: p, tick: event.onset, refs: point.notes.map(function (x) { return x.ref; }),
                                  row: { part: part.name, measure: point.measureNumber, beat: point.beatLabel,
                                         status: point.status, label: point.label,
                                         color: Engine.COLOR_CODES[point.color], reason: event.analysis.reason } });
                }
                for (var u = 0; u < result.unisons.length; u++) {
                    var unison = result.unisons[u];
                    points.push({ part: p, tick: unison.onset, refs: [unison.ref],
                                  row: { part: part.name, measure: unison.measureNumber, beat: unison.beatLabel,
                                         status: "NOT AS WRITTEN", label: Engine.LABEL_TEXT.unison,
                                         color: Engine.COLOR_CODES.purple, reason: unison.reason } });
                }
            }

            applyColors(toColor);
            points = Engine.stableSort(points, function (a, b) { return (a.part - b.part) || (a.tick - b.tick); });
            setProblems(points.map(function (x) { return x.row; }), points.map(function (x) { return x.refs; }));
            reportText = ["ISPOG " + Engine.ENGINE_VERSION + " (MuseScore plugin " + root.version + ")"]
                    .concat(errors.length ? ["", "Settings: " + errors.join("; ")] : [])
                    .concat(sections.map(function (s) { return "\n" + s; })).join("\n");
            stale = false;
            lastDurationMs = Date.now() - started;
            statusText = (range ? "Selected measures only.\n" : "")
                    + (summaries.length ? summaries.join("\n") : "No part selected for analysis.")
                    + (errors.length ? "\n" + errors.join("\n") : "")
                    + "\nAnalyzed in " + (lastDurationMs / 1000).toFixed(1) + " s.";
        } catch (err) {
            statusText = "Analysis failed: " + err + (err.stack ? "\n" + err.stack : "");
        } finally {
            busy = false;
        }
    }

    function isIspogColor(color) {
        var codes = ["green", "orange", "red", "purple"];
        for (var i = 0; i < codes.length; i++)
            if (Qt.colorEqual(color, Engine.COLOR_CODES[codes[i]]))
                return true;
        for (var j = 0; j < legacyColors.length; j++)
            if (Qt.colorEqual(color, legacyColors[j]))
                return true;
        return false;
    }

    // Applies the colors in one undoable command; no command if nothing changes.
    // color null: an ISPOG color is removed, any other color is kept.
    function applyColors(items) {
        var changes = [];
        for (var i = 0; i < items.length; i++) {
            var note = items[i].note, color = items[i].color;
            if (color !== null) {
                if (!Qt.colorEqual(note.color, color))
                    changes.push({ note: note, color: color });
            } else if (isIspogColor(note.color)) {
                changes.push({ note: note, color: Engine.COLOR_CODES.black });
            }
        }
        if (!changes.length)
            return;
        curScore.startCmd();
        for (var c = 0; c < changes.length; c++)
            changes[c].note.color = changes[c].color;
        curScore.endCmd();
    }

    function clearColors() {
        if (!curScore || busy)
            return;
        var collected = collectAll(null);
        var items = [];
        for (var p = 0; p < collected.length; p++)
            for (var n = 0; n < collected[p].notes.length; n++)
                items.push({ note: collected[p].notes[n].ref, color: null });
        applyColors(items);
        setProblems([], []);
        statusText = "ISPOG colors removed.";
    }

    function setProblems(problems, refs) {
        problemsModel.clear();
        for (var i = 0; i < problems.length; i++)
            problemsModel.append(problems[i]);
        problemRefs = refs;
    }

    function selectProblem(row) {
        var notes = problemRefs[row] || [];
        if (!notes.length)
            return;
        try {
            curScore.selection.clear();
            for (var i = 0; i < notes.length; i++)
                curScore.selection.select(notes[i], i > 0);
            curScore.showElementInScore(notes[0]);
        } catch (e) {
            statusText = "Could not select the notes: " + e;
        }
    }

    // A part enabled or disabled, a tuning or a number of frets changed: the results are
    // out of date until the next analysis (not started here: it can take seconds).
    function settingsChanged() {
        stale = true;
    }

    // ========================================================================
    // Lifecycle
    // ========================================================================

    // Opening the dialog analyzes nothing: on a large score that would block MuseScore.
    onRun: {
        loadParts();
        statusText = "Press Analyze to check the ticked parts.";
    }

    // ========================================================================
    // Interface
    // ========================================================================

    Pane {
        anchors.fill: parent
        padding: 10

        palette.window: root.theme.window
        palette.windowText: root.theme.text
        palette.text: root.theme.text
        palette.base: root.theme.base
        palette.button: root.theme.button
        palette.buttonText: root.theme.text
        palette.highlight: root.theme.highlight
        palette.highlightedText: root.theme.base
        palette.placeholderText: root.theme.muted

        ColumnLayout {
            anchors.fill: parent
            spacing: 6

            Label {
                text: "Parts (tuning: string 1 first)"
                font.bold: true
            }

            ScrollView {
                id: partsView
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(partsColumn.implicitHeight, 190)
                clip: true

                ColumnLayout {
                    id: partsColumn
                    width: partsView.availableWidth
                    spacing: 4

                    Repeater {
                        model: partsModel

                        delegate: Frame {
                            Layout.fillWidth: true
                            padding: 6
                            background: Rectangle {
                                color: root.theme.base
                                border.color: root.theme.border
                                radius: 3
                            }

                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 4

                                CheckBox {
                                    text: model.name + (model.isGuitar ? "" : "  (not a guitar)")
                                    checked: model.analyze
                                    onToggled: {
                                        partsModel.setProperty(index, "analyze", checked);
                                        root.settingsChanged();
                                    }
                                }

                                RowLayout {
                                    visible: model.analyze
                                    Layout.fillWidth: true
                                    spacing: 6

                                    ComboBox {
                                        Layout.preferredWidth: 110
                                        model: root.presetNames()
                                        currentIndex: root.presetIndex(tuning, instrumentTuning)
                                        onActivated: function (i) {
                                            if (i === 1)
                                                partsModel.setProperty(index, "tuning", instrumentTuning);
                                            else if (i >= 2)
                                                partsModel.setProperty(index, "tuning",
                                                                       Engine.TUNING_PRESETS[i - 2].notes.join(" "));
                                            root.settingsChanged();
                                        }
                                    }
                                    TextField {
                                        Layout.fillWidth: true
                                        text: tuning
                                        selectByMouse: true
                                        color: root.settingsError(text, frets) ? "#b00020" : root.theme.text
                                        onEditingFinished: {
                                            if (text !== tuning) {
                                                partsModel.setProperty(index, "tuning", text.trim());
                                                root.settingsChanged();
                                            }
                                        }
                                    }
                                    Label { text: "Frets" }
                                    SpinBox {
                                        Layout.preferredWidth: 96
                                        from: Engine.MIN_FRETS
                                        to: Engine.MAX_FRETS
                                        value: frets
                                        editable: true
                                        onValueModified: {
                                            partsModel.setProperty(index, "frets", value);
                                            root.settingsChanged();
                                        }
                                    }
                                }

                                Label {
                                    readonly property string error: model.analyze ? root.settingsError(tuning, frets) : ""
                                    visible: error !== ""
                                    text: error
                                    color: "#b00020"
                                    wrapMode: Text.Wrap
                                    Layout.fillWidth: true
                                }
                            }
                        }
                    }
                }
            }

            RowLayout {
                spacing: 12
                CheckBox {
                    id: showGreen
                    text: "Show playable notes in green"
                    checked: true
                    onToggled: root.settingsChanged()
                }
            }

            RowLayout {
                spacing: 6
                Button {
                    text: "Analyze"
                    highlighted: true
                    enabled: !root.busy
                    onClicked: root.requestAnalysis(false)
                }
                Button {
                    text: "Selected measures"
                    enabled: !root.busy
                    onClicked: root.requestAnalysis(true)
                }
                Button { text: "Save settings"; enabled: !root.busy; onClicked: root.saveSettings() }
                Button { text: "Clear colors"; enabled: !root.busy; onClicked: root.clearColors() }
            }

            Label {
                Layout.fillWidth: true
                visible: root.stale
                text: "Settings changed: press Analyze to update the colors."
                color: "#b35c00"
                wrapMode: Text.Wrap
            }

            Label {
                Layout.fillWidth: true
                text: root.statusText
                wrapMode: Text.Wrap
                color: root.theme.muted
            }

            TabBar {
                id: tabs
                Layout.fillWidth: true
                TabButton { text: "Problems (" + problemsModel.count + ")" }
                TabButton { text: "Report" }
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: tabs.currentIndex

                ListView {
                    id: problemsView
                    clip: true
                    model: problemsModel
                    spacing: 2
                    ScrollBar.vertical: ScrollBar {}

                    delegate: ItemDelegate {
                        width: problemsView.width
                        onClicked: root.selectProblem(index)
                        contentItem: RowLayout {
                            spacing: 8
                            Rectangle {
                                Layout.preferredWidth: 6
                                Layout.fillHeight: true
                                color: model.color
                                radius: 2
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                Label {
                                    Layout.fillWidth: true
                                    text: "m. " + model.measure + ", beat " + model.beat + " — " + model.status
                                          + " · " + model.label
                                    font.bold: true
                                    elide: Text.ElideRight
                                }
                                Label {
                                    Layout.fillWidth: true
                                    text: model.part + ": " + model.reason
                                    wrapMode: Text.Wrap
                                    color: root.theme.muted
                                }
                            }
                        }
                    }

                    Label {
                        anchors.centerIn: parent
                        visible: problemsModel.count === 0
                        text: "No difficult or unplayable passages."
                        color: root.theme.muted
                    }
                }

                ScrollView {
                    clip: true
                    TextArea {
                        readOnly: true
                        selectByMouse: true
                        wrapMode: TextEdit.NoWrap
                        font.family: "Consolas, Menlo, monospace"
                        text: root.reportText
                    }
                }
            }
        }
    }
}
