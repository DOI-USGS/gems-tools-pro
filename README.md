GeMS Tools

This repository contains an ArcGIS toolbox and associated Python scripts and resources for creating, manipulating, and validating GeMS-style geologic map databases, as well as documentation.  See the Docs folder for more information. 

For information on the NCGMP09, the precursor to the GeMS database schema, see http://ngmdb.usgs.gov/Info/standards/NCGMP09/

GeMS Toolbox was written in Python 2.7 by Ralph Haugerud, Evan Thoms, and others. Scripts have been developed and tested on Windows 7, using various versions of ArcGIS (9.1 - 10.5). 

This software is preliminary or provisional and is subject to revision. It is being provided to meet the need for timely best science. The software has not received final approval by the U.S. Geological Survey (USGS). No warranty, expressed or implied, is made by the USGS or the U.S. Government as to the functionality of the software and related material nor shall the fact of release constitute any such warranty. The software is provided on the condition that neither the USGS nor the U.S. Government shall be held liable for any damages resulting from the authorized or unauthorized use of the software.

Any use of trade, firm, or product names is for descriptive purposes only and does not imply endorsement by the U.S. Government.

-----------------------------------------------------------------

To install the GeMS toolbox, download this repository. On GitHub, at the mid-upper left of this repository page, tap gray "Branch:master" button, tap "Tags" in the window that opens, and select the appropriate (probably the most recent) entry.  Then tap the "Clone or download button" (green box with down caret at upper right of screen) and select "Download ZIP". 

After the download completes, go to your download directory and unzip the just-downloaded file. Inside the unzipped file there will be a single folder named something like "GeMS_Tools-0.2-version14Dec2017". Either 

1. Copy this folder to a locale of your choice. Start ArcCatalog or ArcMap, open the Arc Toolbox window, right click on empty space in the Arc Toolbox window, and select "Add Toolbox".  Then navigate to the GeMS_Tools folder and select file GeMSToolsArc105.tbx (if you are running ArcGIS 10.5) or file GeMSToolsArc10.tbx (if you are running an older version of ArcGIS).

    Right-click again on empty space in the Arc Toolbox window and select "Save settings" and then "Default" to have the GeMS toolbox available next time you open ArcCatalog or ArcMap.

or 

2. Place the CONTENTS of the GeMS_Tools folder (including folders Resources and Scripts, and files GeMS_ToolsArc10.tbx, GeMS_ToolsArc105.tbx, README.md, and LICENSE.md) in

    C:\Documents and Settings\<user>\AppData\Roaming\ESRI\Desktop10.5\ArcToolbox\My Toolboxes

    This is the pathname for ArcGIS 10.5 on Windows 7; it may differ with other operating systems and ArcGIS versions. Delete the .tbx file that is not needed. Then, in ArcCatalog, scroll to the bottom of the left-hand "Catalog Tree" pane, open Toolboxes/My Toolboxes, and the new toolboxes should be present. You may need to refresh the listing. 

See the help that is part of the individual tool interfaces for documentation. Also the Docs subdirectory of this package for documentation in .docx and .pdf format. 

-----------------------------------------------------------------

Collaboration: Suggestions for improvements and edited files submitted by email will be considered, but you are strongly encouraged to use GitHub to fork the project, create a new branch (e.g., "MyFixToProblemXXX"), make changes to this branch, and submit a pull request to have your changes merged with the master branch. Excellent guides for various aspects of the git workflow can be found here:

[https://guides.github.com/](https://guides.github.com/)

-----------------------------------------------------------------

Known issues with these scripts include:

* "Project Map Data to Cross Section" doesn't always produce the correct apparent dip direction. The dip magnitude is correct, but it may be in the wrong direction.

* "MapOutline" stumbles over some choices of datum.

* ".docx to DMU" and "DMU to .docx" are incomplete and do not fully produce the desired output. These modules also 
require the lxml Python module, which some find difficult to install. The other scripts run without lxml.  

* "Purge Metadata" requires that the USGS EGIS tools for ArcGIS be installed. 
