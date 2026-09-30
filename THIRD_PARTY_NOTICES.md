# Third-party notices

ISPOG is distributed under the GNU GPL v3.0 or later (see [LICENSE](LICENSE)).
The desktop executables and the repository include or depend on the components below,
each under its own license.

| Component | Used for | License |
|---|---|---|
| [Python](https://www.python.org/) | runtime, bundled in the executables | PSF License Agreement |
| [Tcl/Tk](https://www.tcl.tk/) | desktop interface, bundled in the executables | Tcl/Tk License (BSD-style) |
| [lxml](https://lxml.de/) | MusicXML parsing and writing | BSD-3-Clause |
| [libxml2](https://gitlab.gnome.org/GNOME/libxml2) | XML engine, bundled with lxml | MIT |
| [libxslt](https://gitlab.gnome.org/GNOME/libxslt) | XSLT engine, bundled with lxml | MIT |
| [PyInstaller](https://pyinstaller.org/) bootloader | desktop executables | GPL-2.0-or-later with bootloader exception |
| [Gradio](https://www.gradio.app/) | web version only, not in the executables | Apache-2.0 |

## MusicXML 4.0 specification files

| File | Used for | Source |
|---|---|---|
| `resources/timepart.xsl` | converting timewise scores to partwise | MusicXML 4.0 |
| `tests/schema/musicxml.xsd` | validating the output in the test suite (not in the executables) | MusicXML 4.0 |
| `tests/schema/xlink.xsd` | imported by `musicxml.xsd` | MusicXML 3.1 |
| `tests/schema/xml.xsd` | imported by `musicxml.xsd` | MusicXML 3.1 (W3C) |

Unmodified from <https://github.com/w3c/musicxml> (tags `v4.0` and `v3.1`; the 4.0 schema
imports `xlink.xsd` and `xml.xsd` from musicxml.org, the last release shipping them in the
repository is 3.1).
Copyright © 2004-2021 the Contributors to the MusicXML Specification, published by the
W3C Music Notation Community Group under the
[W3C Community Final Specification Agreement (FSA)](https://www.w3.org/community/about/agreements/final/).
`xml.xsd` is the W3C schema for the XML namespace, distributed under the
[W3C Software and Document License](https://www.w3.org/copyright/software-license-2023/).

The license texts are available at the links above and in each package's distribution.
