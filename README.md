# GeMS Tools

This repository contains an ArcGIS toolbox and associated Python scripts and resources for creating, manipulating, and validating GeMS-style geologic map databases, as well as documentation.  

See below for download and installation. See the Wiki (tab above) for documentation of the tools and instructions on the use of the GeMS schema. For information on NCGMP09, the precursor to the GeMS database schema, see the Archive section at http://ngmdb.usgs.gov/Info/standards/GeMS/.

The current version of GeMS Tools reflects the on-going transition from tools that work in ArcMap 10 with Python 2.7 to those that will only work in ArcGIS Pro 2 with Python 3. The scripts that end in 'AGP2' have been updated. Those that end in 'Arc10' have not. The tools were writen by Ralph Haugerud, Evan Thoms, and others. Scripts have been developed and tested on Windows 7, using ArcGIS Pro 2.1.3 and the Python 3.6.7 as installed alongside ArcGIS Pro.

This software is preliminary or provisional and is subject to revision. It is being provided to meet the need for timely best science. The software has not received final approval by the U.S. Geological Survey (USGS). No warranty, expressed or implied, is made by the USGS or the U.S. Government as to the functionality of the software and related material nor shall the fact of release constitute any such warranty. The software is provided on the condition that neither the USGS nor the U.S. Government shall be held liable for any damages resulting from the authorized or unauthorized use of the software.

Any use of trade, firm, or product names is for descriptive purposes only and does not imply endorsement by the U.S. Government.

-----------------------------------------------------------------

To install GeMS Tools, download this repository as follows: On GitHub, at the mid-upper left of this repository page, tap gray "Branch:master" button, tap "Tags" in the window that opens, and select the appropriate (probably the most recent) entry.  Then tap the "Clone or download button" (green box with down caret at upper right of screen) and select "Download ZIP". 

After the download completes, go to your download directory and unzip the just-downloaded file. Inside the unzipped file there will be a single folder named something like "GeMS_Tools-14Dec2017". Copy this folder to a locale of your choice. Open a project in ArcGIS Pro. In the Catalog window, click on the Project tab. Go to Folders, right-click, choose 'Add Folder Connection' and then browse to the folder that contains the toolbox (or one or more parent folders above that folder).

To download a version of the toolbox that works with ArcMap 10, go to the Releases tab of this page and download the zip file for v1.0.0.

The documentation for the tools may not be complete, but, for the most part, the Python 3 versions produce the same results as the older Python 2.7 versions. See the help that is part of the individual tool interfaces for documentation. Also the Docs subdirectory of this package for documentation in .docx and .pdf format. 

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
