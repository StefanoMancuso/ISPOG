// Drives ispog.qml against the test double of a score (run_plugin_tests.py).
import QtQuick 2.15
import QtQuick.Controls 2.15
import MuseScore 3.0
import "mockscore.js" as Mock

ApplicationWindow {
    id: test
    width: 480
    height: 680
    visible: false

    property url pluginUrl
    property var score: null

    Loader {
        id: loader
        anchors.fill: parent
        source: test.pluginUrl
    }

    function plugin() {
        return loader.item;
    }

    // First item below `item` whose text property equals `text`.
    function findByText(item, text) {
        if (!item)
            return null;
        if (item.text === text)
            return item;
        var children = item.children || [];
        for (var i = 0; i < children.length; i++) {
            var found = findByText(children[i], text);
            if (found)
                return found;
        }
        var content = item.contentItem;
        if (content && children.indexOf(content) < 0) {
            var inContent = findByText(content, text);
            if (inContent)
                return inContent;
        }
        return null;
    }

    function setUp(specText) {
        score = Mock.build(JSON.parse(specText), { NOTE: Element.NOTE, CHORD: Element.CHORD });
        plugin().curScore = score;
        plugin().run();
        return snapshot();
    }

    // Selects the measures from startTick (included) to endTick (excluded) as a range.
    function selectRange(startTick, endTick) {
        score.selection.elements = [];
        score.selection.isRange = true;
        score.selection.startSegment = { tick: startTick };
        score.selection.endSegment = { tick: endTick };
        return snapshot();
    }

    function colors() {
        var result = {};
        score.notes.forEach(function (n) { result[n.key] = String(n.color).toUpperCase(); });
        return result;
    }

    function problems() {
        var model = plugin().problemRows;
        var rows = [];
        for (var i = 0; i < model.count; i++) {
            var row = model.get(i);
            rows.push({ part: row.part, measure: row.measure, beat: row.beat, status: row.status,
                        label: row.label, reason: row.reason });
        }
        return rows;
    }

    function snapshot() {
        return JSON.stringify({
            colors: colors(), problems: problems(), status: plugin().statusText,
            report: plugin().reportText, busy: plugin().busy, stale: plugin().stale, startCmd: score.startCmdCount, endCmd: score.endCmdCount,
            writesOutsideCmd: score.writesOutsideCmd, colorWrites: score.colorWrites,
            metaTags: score.metaTags,
            selection: score.selection.elements.map(function (e) { return e.key; }),
            shown: score.shown ? score.shown.key : null
        });
    }

    function call(name, args) {
        var p = plugin();
        p[name].apply(p, args || []);
        return snapshot();
    }

    function toggle(text) {
        var box = findByText(plugin(), text);
        if (!box)
            throw new Error("no control with text " + text);
        box.toggle();
        box.toggled();
        return snapshot();
    }

    // Changes the settings of a part as the dialog does.
    function setPart(row, analyze, tuning, frets) {
        var model = plugin().partRows;
        model.setProperty(row, "analyze", analyze);
        model.setProperty(row, "tuning", tuning);
        model.setProperty(row, "frets", frets);
        plugin().settingsChanged();
        return snapshot();
    }

    // Saves a picture of the dialog (asynchronous: keep the event loop running).
    function saveImage(path) {
        loader.item.grabToImage(function (result) { result.saveToFile(path); });
        return snapshot();
    }

    // Edits a note as the user would: new pitch, the note selected.
    function editNote(key, pitch, tpc1) {
        var note = score.notesByKey[key];
        note.pitch = pitch;
        note.tpc1 = tpc1;
        score.selection.elements = [note];
        return snapshot();
    }
}
