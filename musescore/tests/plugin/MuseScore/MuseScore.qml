// Test double of the MuseScore plugin root item (MuseScore Studio 4.7 plugin API, the
// members ispog.qml uses). Not a MuseScore file.
import QtQuick 2.15

Item {
    property string version
    property string title
    property string description
    property string categoryCode
    property bool requiresScore: true
    property string pluginType
    property var curScore: null
    readonly property int division: 480

    signal run()
    signal scoreStateChanged(var state)

    function fractionFromTicks(ticks) {
        return { ticks: ticks, numerator: ticks, denominator: 4 * division };
    }

    function quit() {
    }
}
