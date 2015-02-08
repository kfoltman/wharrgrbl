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
* double-sided milling
* roughing out large areas of copper with an endmill instead of v-bit
* support for Z-probing
* integration with gcode sender for advanced features like integrated
auto-Z-probing, 


## Gcode sender UI

This is a highly 'work-in-progress' machine control interface, similar
to UGCS or Grbl-Panel, but using a more open-source friendly language. The
goal is to integrate it with the PCB generator and perhaps other CAM
utilities in future. It's not tested with an actual CNC machine, only with
Grbl running standalone, so it's not recommended for use yet.

### TODO
* UGCS-style conversation output
* better designed and full featured job support (the current one is a complete hack)
* adjustable step size and feed for jogging
* separate step size for X/Y and Z
* adjustable feed for jogging
* ad-hoc operations/canned cycles (peck and spiral drilling, milling slots, pocketing holes for hex nuts etc.)
