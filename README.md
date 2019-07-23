# GeMS Tools

This repository contains an ArcGIS toolbox and associated Python scripts and resources for creating, manipulating, and validating GeMS-style geologic map databases, as well as documentation.  

See below for download and installation. See the Wiki (tab above) for documentation of the tools and instructions on the use of the GeMS schema. For information on NCGMP09, the precursor to the GeMS database schema, see the Archive section at http://ngmdb.usgs.gov/Info/standards/GeMS/.

There are two versions of the GeMS Tools scripts and toolbox. Version 1 releases work in ArcMap 10 using Python 2.7 and version 2 releases work with ArcGIS Pro 2 using Python 3. The tools were written by Ralph Haugerud, Evan Thoms, and others. 

This software is preliminary or provisional and is subject to revision. It is being provided to meet the need for timely best science. The software has not received final approval by the U.S. Geological Survey (USGS). No warranty, expressed or implied, is made by the USGS or the U.S. Government as to the functionality of the software and related material nor shall the fact of release constitute any such warranty. The software is provided on the condition that neither the USGS nor the U.S. Government shall be held liable for any damages resulting from the authorized or unauthorized use of the software.

Any use of trade, firm, or product names is for descriptive purposes only and does not imply endorsement by the U.S. Government.

-----------------------------------------------------------------

To install the latest version of GeMS Tools for use with ArcGIS Pro, download this repository as follows: On GitHub, at the mid-upper left of this repository page, tap gray "Branch:master" button, tap "Tags" in the window that opens, and select the appropriate (probably the most recent) entry.  Then tap the "Clone or download button" (green box with down caret at upper right of screen) and select "Download ZIP". 

To download a version that works with ArcMap 10, go to the Releases tab of this page and download the zip file for the latest version 1 release.

After the download completes, go to your download directory and unzip the just-downloaded file. Inside the unzipped file there will be a single folder named something like "GeMS_Tools-master". Copy this folder to a locale of your choice. Open a project in ArcGIS Pro. In the Catalog window, click on the Project tab. Go to Folders, right-click, choose 'Add Folder Connection' and then browse to the folder that contains the toolbox (or one or more parent folders above that folder).

The documentation for the tools may not be complete, but, for the most part, the Python 3 versions produce the same results as the older Python 2.7 versions. See the help that is part of the individual tool interfaces for documentation. Also the Docs subdirectory of this package for documentation in .docx and .pdf format. 

-----------------------------------------------------------------

Collaboration: Suggestions for improvements and edited files submitted by email will be considered, but you are strongly encouraged to use GitHub to fork the project, create a new branch (e.g., "MyFixToProblemXXX"), make changes to this branch, and submit a pull request to have your changes merged with the master branch. Excellent guides for various aspects of the git workflow can be found here:

[https://guides.github.com/](https://guides.github.com/)

-----------------------------------------------------------------

Known issues with these scripts include:

* "Project Map Data to Cross Section"does not always produce the correct apparent dip direction. The dip magnitude is correct, but it may be in the wrong direction.

* "MapOutline" stumbles over some choices of datum.

* "Purge Metdata" and "FDGC CSDGM2 Metadata"have been removed from the version 2 toolbox. With the Python 3 version of arcpy, it is no longer possible to automate the export or import of metadata.

* "DMU to .docx" requires the python-docx third party module. Install by opening the ArcGIS Pro Python Command Prompt so that you are starting in the arcgispro-py conda environment and type

`conda install -c conda-forge python-docx`

Version 1 issues:

* ".docx to DMU" and "DMU to .docx" are incomplete and do not fully produce the desired output. These modules also 
require the lxml Python module, which some find difficult to install. The other scripts run without lxml.  

* "Purge Metadata" requires that the USGS EGIS tools for ArcGIS be installed. 
