# wharrgrbl
Machine control and CAM utilities for grbl CNC firmware.

This is my collection of hastily made scripts to help in various hobby CNC related
tasks, mainly milling PCBs. The scripts are written in Python and use PyQt4
as a GUI framework where applicable.

## PCB toolpath generator

The main program is called pcbf.py. As it is, it generates toolpaths to
create single-sided printed circuit boards from KiCAD pcbnew files, using
the recent sexpr-based version of the file format. The .kicad_pcb file is
converted into gcode in three ways:

* track outlines are converted to appropriate toolpaths for isolation milling with 
a v-bit of a selected diameter (0.1, 0.2 or 0.3mm)

* holes and slots are converted to drilling operations to use with 0.8mm endmills
(turned out to be a good compromise between price, fragility and speed)

* board edges are converted into milling operation, this time without compensation
for tool size (it's not always obvious as to whether a given line should be on
the outside or inside of the board)

The generated gcode is simple enough to be interpreted correctly by a recent
(0.9g) version of Grbl.

### TODO
* double-sided milling with some sort of auto alignment holes or support for pre-made fixed-size alignment jigs
* roughing out large areas of copper with an endmill instead of v-bit
* support for Z-probing
* integration with gcode sender for advanced features like integrated
auto-Z-probing and selective re-milling of underetched areas or nets


## Gcode sender UI

This is a highly 'work-in-progress' machine control interface, similar
to UGCS or Grbl-Panel, but using a more open-source friendly language (Python).
The goal is to integrate it with the PCB generator and perhaps other CAM
utilities in future.

### Features
* Open source and written in Python 2.7
* Supports Linux and Windows (serial port autodetection not fully working)
* Graphical user interface using PyQt4
* Interactive mode with command history and feed hold/resume support
* Job mode (running gcode content from a file) including pause/resume/cancel
* Jogging with separate, configurable step sizes and feed rates for X/Y axes and Z axis
* Support for character-counting protocol for efficient transmission of complex gcode
* User buttons for frequently used commands (probing etc.)
* Grbl setting editor (GUI for $$/$number)
* Configuration via Python source file, no UI configuration support yet
