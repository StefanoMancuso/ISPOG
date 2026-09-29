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

Files from the MusicXML specification (`resources/timepart.xsl`, `tests/schema/*.xsd`)
will be listed here, with their license, when they are added.

The license texts are available at the links above and in each package's distribution.
