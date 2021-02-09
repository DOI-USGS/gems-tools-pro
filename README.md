[![GitHub tag (latest SemVer)](https://img.shields.io/github/v/release/usgs/gems-tools-pro)](https://github.com/usgs/gems-tools-pro/releases/latest) [![resources](https://img.shields.io/badge/gems-resources-orange)](https://github.com/usgs/gems-resources) [![Wiki](https://img.shields.io/badge/gems-wiki-orange)](https://github.com/usgs/gems-resources/wiki) [![pro](https://img.shields.io/badge/gems--tools-arcmap-orange)](https://github.com/usgs/gems-tools-arcmap) [![Gitter chat](https://badges.gitter.im/gitterHQ/gitter.png)](https://gitter.im/gems-schema/community) [![gems on USGS](https://img.shields.io/badge/gems-%40%20USGS-brightgreen)](https://ngmdb.usgs.gov/Info/standards/GeMS/) 

<img width="250" align="right" src="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/USGS_logo_green.svg/500px-USGS_logo_green.svg.png"/>

# GeMS Tools for ArcGIS Pro

This repository contains an ArcGIS toolbox of Python 3 geoprocessing tools for creating, manipulating, and validating [GeMS](https://ngmdb.usgs.gov/Info/standards/GeMS/)-style geologic map databases for use in ArcGIS Pro. Note that some files previously distributed in the Resources folder have been moved to a separate repository called [gems-resources.](https://github.com/usgs/gems-resources)

If you are looking for tools that work in ArcMap using Python 2.7, go to [gems-tools-arcmap](https://github.com/usgs/gems-tools-arcmap)

## Installation

* Download the [latest release](https://github.com/usgs/gems-tools-pro/releases/latest).
* Unzip the file to a folder of your choice. This will extract a single folder named `gems-tools-pro-` followed by the version number (e.g., `gems-tools-pro-2.1`).  *Automated version checking has not been implemented yet, but keeping the version number in the folder name will provide you with a quick way to compare your version with the latest at the repository.*
* Open ArcGIS Pro and go to either the Contents or Catalog pane.
* Under Project, right-click on Folders to add a folder connection. Navigate to the toolbox folder.
* Note that this only saves the folder connection with the current project file. If you want to have the toolbox handy for any project that you open up,
  * go to the Catalog pane
  * select the Favorites tab
  * click Add Item
  * choose Add Folder, and navigate to the folder.

The documentation for these tools may not be complete or may be poorly formatted for display in either the ArcGIS Pro help popup (hover your cursor over the ? icon when looking at the tool parameter form) or metadata view (right-click on the tool from the Catalog pane and choose View Metadata), but, for the most part, the Python 3 versions produce the same results as the older Python 2.7 versions.

## Getting help
* Each tool comes with documentation inside the parameter form.
* Check out the [wiki](https://github.com/usgs/gems-resources/wiki) for help on these tools and extensive advice on using these tools to create, edit, and validate GeMS-style databases.
* Documentation for the toolbox and all tools and  is also available in **GeMS_Tools_Arc10.docx** and **GeMS_Tools_Arc10.pdf** found in the `Docs` sub-folder — these are both somewhat out-of-date; check back for new versions.
* If, when using a tool, it fails to run and produces an error message, first check that you have the latest release of the tool. If that is not the source of the problem, start a new issue at this repository (see the [Issues](https://github.com/usgs/gems-tools-pro/issues) tab above). Provide a screenshot of the error message if you can.
* If you have a question about how to build or attribute a GeMS-compliant database or the schema in general, please visit the [GeMS Gitter](https://gitter.im/gems-schema/community#) chat room. If you already have a GitHub account, you can sign in there with those credentials.

## Collaborate
Suggestions for improvements and edited files submitted by [email](gems@usgs.gov) will be considered, but you are strongly encouraged to use GitHub to fork the project, create a new branch (e.g., "MyFixToProblemXXX"), make changes to this branch, and submit a pull request to have your changes merged with the master branch. Excellent guides for various aspects of the git workflow can be found here:

[https://guides.github.com/](https://guides.github.com/)

## Known issues

* "Project Map Data to Cross Section" does not always produce the correct apparent dip direction. The dip magnitude is correct, but it may be in the wrong direction.

* "MapOutline" stumbles over some choices of datum.

* All metadata tools have been removed from the ArcGIS Pro version of the toolbox. With ArcGIS Pro, FGDC CSDGM metadata is exported with no Spatial Reference Information node ([BUG-000124294](https://community.esri.com/t5/arcgis-pro-questions/fgdc-spatial-reference-info-missing-when-using-export-metadata/m-p/681417)). Until the bug is addressed or we find a workaround, only the ArcMap versions of these tools will be available.

* "DMU to .docx" requires the [python-docx](https://python-docx.readthedocs.io/en/latest/) third party package. **Do not try to install this package into your default arcgispro-py3 python environment**. Instead, install it into a [clone](https://pro.arcgis.com/en/pro-app/latest/arcpy/get-started/work-with-python-environments.htm#ESRI_SECTION1_175473E6EB0D46E0B195996EAE768C1D). Remember to activate this environment before running the tool.

## Acknowledgements
GeMS Tools was originally written by in Python 2.7 by Ralph Haugerud, Evan Thoms, and others and ported to Python 3 by Evan Thoms.

## Disclaimer
This software is preliminary or provisional and is subject to revision. It is being provided to meet the need for timely best science. The software has not received final approval by the U.S. Geological Survey (USGS). No warranty, expressed or implied, is made by the USGS or the U.S. Government as to the functionality of the software and related material nor shall the fact of release constitute any such warranty. The software is provided on the condition that neither the USGS nor the U.S. Government shall be held liable for any damages resulting from the authorized or unauthorized use of the software.

Any use of trade, firm, or product names is for descriptive purposes only and does not imply endorsement by the U.S. Government.
