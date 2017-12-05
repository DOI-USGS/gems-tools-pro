GeMS Toolbox

This repository contains an ArcGIS toolbox and associated scripts and resources for creating, manipulating, and validating GeMS-style geologic map databases, as well as documentation.  See the Docs folder for more information. 

For information on the GeMS database schema, see http://ngmdb.usgs.gov/Info/standards/GeMS/

GeMS Toolbox was written in Python 2.7 by Ralph Haugerud, Evan Thoms, and others. Scripts have been developed and tested on Windows 7, using various versions of ArcGIS (9.1 - 10.5). 

This software is preliminary or provisional and is subject to revision. It is being provided to meet the need for timely best science. The software has not received final approval by the U.S. Geological Survey (USGS). No warranty, expressed or implied, is made by the USGS or the U.S. Government as to the functionality of the software and related material nor shall the fact of release constitute any such warranty. The software is provided on the condition that neither the USGS nor the U.S. Government shall be held liable for any damages resulting from the authorized or unauthorized use of the software.

Any use of trade, firm, or product names is for descriptive purposes only and does not imply endorsement by the U.S. Government.

-----------------------------------------------------------------

To install the GeMS toolbox, either

1. Create a folder GeMS_Toolbox in a locale of your choice. Copy 

    Resources (folder)

    Scripts  (folder) 

    GeMS_ToolsArc10.tbx  (file)

    GeMS_ToolsArc105.tbx  (file)
    
    license.md    (file)

    into this folder. Start ArcCatalog or ArcMap, open the Arc Toolbox window, right click on empty space in the Arc Toolbox window, and select "Add Toolbox".  Then navigate to the GeMS_Toolbox folder and select file GeMSToolsArc105.tbx (if you are running ArcGIS 10.5) or file GeMSToolsArc10.tbx (if you are running an older version of ArcGIS).

    Right-click again on empty space in the Arc Toolbox window and select "Save settings" and then "Default" to have the GeMS toolbox available next time you open ArcCatalog or ArcMap.

or 

2. Place the folders and files identified above in

C:\Documents and Settings\<user>\AppData\Roaming\ESRI\Desktop10.5\ArcToolbox\My Toolboxes

    (this is the pathname for ArcGIS 10.5 on Windows 7; it may differ with other operating systems). Then, in ArcCatalog, scroll to the bottom of the left-hand "Catalog Tree" pane, open Toolboxes/My Toolboxes, and the new toolboxes should be present. You may need to refresh the listing. 

See the help that is part of the individual tool interfaces for documentation. Also the Docs subdirectory of this package for documentation in .docx and .pdf format. 

-----------------------------------------------------------------

Known issues with these scripts include:

* "Project Map Data to Cross Section" doesn't always produce the correct apparent dip direction. The dip magnitude is correct, but it may be in the wrong direction.

* "MapOutline" stumbles over some choices of datum.

* ".docx to DMU" and "DMU to .docx" are incompletely debugged and do not produce the desired output. These modules also 
require the lxml Python module, which some find difficult to install. The other scripts run without lxml.  

* "Purge Metadata" requires that the USGS EGIS tools for ArcGIS be installed. 

