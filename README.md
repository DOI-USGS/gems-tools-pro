# GeMS Tools for ArcGIS Pro
![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/usgs/gems-tools-pro)  [![Wiki](https://img.shields.io/badge/wiki-%40%20gems--resources-brightgreen)](https://github.com/usgs/gems-resources/wiki) [![Gitter chat](https://badges.gitter.im/gitterHQ/gitter.png)](https://gitter.im/gems-schema/community)

This repository contains an ArcGIS Pro toolbox and associated Python 3 scripts and resources for creating, manipulating, and validating GeMS-style geologic map databases, as well as documentation. Note that some files previously distributed in the Resources folder have been moved to a separate repository called [gems-resources.](https://github.com/usgs/gems-resources)

If you are looking for tools that work in ArcMap using Python 2.7, go to https://github.com/usgs/gems-tools-arcmap

See below for download and installation. See the [Wiki](https://github.com/usgs/gems-tools-pro/wiki) tab (above) for documentation of the tools and instructions on the use of the GeMS schema. For information on the GeMS database schema, go to https://ngmdb.usgs.gov/Info/standards/GeMS/.

This software is preliminary or provisional and is subject to revision. It is being provided to meet the need for timely best science. The software has not received final approval by the U.S. Geological Survey (USGS). No warranty, expressed or implied, is made by the USGS or the U.S. Government as to the functionality of the software and related material nor shall the fact of release constitute any such warranty. The software is provided on the condition that neither the USGS nor the U.S. Government shall be held liable for any damages resulting from the authorized or unauthorized use of the software.

Any use of trade, firm, or product names is for descriptive purposes only and does not imply endorsement by the U.S. Government.

## Download

To install the GeMS Tools toolbox, click on the "Code" button above and choose "Download zip". Save and unzip the contents to any folder.

Open ArcGIS Pro and go to either the Contents or Catalog pane. Under Project, right-click on Folders to add a folder connection. Navigate to the toolbox folder. Note that this only saves the folder connection with the current project file. If you want to have the toolbox handy for any project that you open up, go to the Catalog pane, select the Favorites tab, click Add Item, choose Add Folder, and navigate to the folder.

The documentation for these tools may not be complete or may be poorly formatted for display in either the ArcGIS Pro help popup (hover your cursor over the ? icon when looking at the tool parameter form) or metadata view (right-click on the tool from the Catalog pane and choose View Metadata), but, for the most part, the Python 3 versions produce the same results as the older Python 2.7 versions. Also the Docs subdirectory of this package contains documentation in .docx and .pdf format.

## Getting help
If, when using a tool, it fails to run and produces an error message, please start a new issue at this repository (see the Issues tab above). Provide a screenshot of the error message if you can.

If you have a question about how to build or attribute a GeMS-compliant database or the schema in general, please visit the [GeMS Gitter](https://gitter.im/gems-schema/community#) chat room. If you already have a GitHub account, you can sign in there with those credentials.

## Collaborate
Suggestions for improvements and edited files submitted by email will be considered, but you are strongly encouraged to use GitHub to fork the project, create a new branch (e.g., "MyFixToProblemXXX"), make changes to this branch, and submit a pull request to have your changes merged with the master branch. Excellent guides for various aspects of the git workflow can be found here:

[https://guides.github.com/](https://guides.github.com/)

## Known issues

* "Project Map Data to Cross Section" does not always produce the correct apparent dip direction. The dip magnitude is correct, but it may be in the wrong direction.

* "MapOutline" stumbles over some choices of datum.

* "Purge Metdata" and "FDGC CSDGM2 Metadata" have been removed from the ArcGIS Pro version of the toolbox. With the Python 3 version of arcpy, it is no longer possible to automate the export or import of metadata.

* "DMU to .docx" requires the python-docx third party module. Install by opening the ArcGIS Pro Python Command Prompt so that you are starting in the arcgispro-py conda environment and type

`conda install -c conda-forge python-docx`
