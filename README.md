[![GitHub tag (latest SemVer)](https://img.shields.io/github/v/release/usgs/gems-tools-pro)](https://github.com/usgs/gems-tools-pro/releases/latest) [![Wiki](https://img.shields.io/badge/-wiki-orange)](https://github.com/usgs/gems-tools-pro/wiki) [![Wiki](https://img.shields.io/badge/-discuss-orange)](https://github.com/usgs/gems-tools-pro/discussions) [![HTMLdoc](https://img.shields.io/badge/-jupyter_notebooks-orange)](https://github.com/usgs/gems-tools-pro/tree/notebooks) [![ArcMap](https://img.shields.io/badge/-tools_for_arcmap-orange)](https://github.com/usgs/gems-tools-arcmap) [![HTMLdoc](https://img.shields.io/badge/-gems_documentation-brightgreen)](https://scgeology.github.io/GeMS/index.html) [![gems on USGS](https://img.shields.io/badge/-NGMDB-brightgreen)](https://ngmdb.usgs.gov/Info/standards/GeMS/)

<img width="250" align="right" src="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/USGS_logo_green.svg/500px-USGS_logo_green.svg.png"/>

> **Note**
> New Validate Database tool on branch [`validate`](https://github.com/DOI-USGS/gems-tools-pro/tree/validate) for beta testing. 
> * Understands custom name variations of GeMS elements, e.g., `SurficialContactsAndFaults`
> * Validates and checks an existing topology if it exists; recognizes exceptions
> * Checks standalone metadata file as required for submission to NGMDB
> * Accepts multiple pipe-delimited (|) source ids in all fields ending in `SourceID`
> * Validates OGC GeoPackages with multiple `MapUnitPolys` and `ContactsAndFaults` pairs (use name variations) to accommodate lack of feature datasets
> * Opens HTML report file upon completion

# GeMS Tools for ArcGIS Pro

This repository contains an ArcGIS toolbox of Python 3 geoprocessing tools for creating, manipulating, and validating [GeMS](https://ngmdb.usgs.gov/Info/standards/GeMS/)-style geologic map databases for use in ArcGIS Pro. Additional resources; vocabularies, symbology, links to other projects, etc.; are available at the [NGMDB GeMS site](https://ngmdb.usgs.gov/Info/standards/GeMS/#reso).

If you are looking for tools that work in ArcMap using Python 2.7, go to [gems-tools-arcmap](https://github.com/usgs/gems-tools-arcmap)

## Installation
There are two ways you can get the toolbox. You can download a zip file with the contents of this repository every time there is a new release or you can clone the repository using `git` and pull the latest changes as necessary with a simple terminal command.

### Download
* Download the [latest release](https://github.com/usgs/gems-tools-pro/releases/latest) from **Releases** or from the green **Code** button above.
* Unzip the file to a folder of your choice. This will extract a single folder named `gems-tools-pro-` followed by either the version number (e.g., `gems-tools-pro-2.1`) if downloaded from **Releases** or `master` if downloaded from the **Code** button.

### or Clone
This method requires you to have `git` installed on your computer. If you know you do, you can skip down two steps and use that instance of it. If not, you can use the instance that was installed in the default conda environment when ArcGIS Pro was installed.

* Click on 'Start' (![image](https://user-images.githubusercontent.com/5376315/186263217-79a685f5-4942-4f95-bba0-810b070b6de8.png)) in the lower-left of your desktop.
* From the list of programs, select **ArcGIS** and then **Python Command Prompt**.
* At the prompt, type `cd` and the path of the location where you would like the toolbox to be.
* Paste in `git clone https://github.com/usgs/gems-tools-pro.git`
* `cd` to `gems-tools-pro`
* Now, whenever you get notice of a new release or if it's just been awhile and you want to make sure you are using the most up-to-date version, go back to this folder and type `git pull`.

### Configure
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
* Check out the [wiki](https://github.com/usgs/gems-tools-pro/wiki) for help on these tools and extensive advice on using these tools to create, edit, and validate GeMS-style databases.
* If you have a question about how to build or attribute a GeMS-compliant database or the schema in general, please visit the [Discussions]([GeMS Gitter](https://github.com/DOI-USGS/gems-tools-pro/discussions) tab of this repo. You will need a GitHub account to post there. <b>NOTE</b> we are no longer using Gitter for chats. 
* Documentation for the toolbox and all tools and  is also available in **GeMS_Tools_Arc10.docx** and **GeMS_Tools_Arc10.pdf** found in the `Docs` sub-folder — these are both somewhat out-of-date; check back for new versions.
* If, when using a tool, it fails to run and produces an error message, first check that you have the latest release of the tool. If that is not the source of the problem, start a new issue at this repository (see the [Issues](https://github.com/usgs/gems-tools-pro/issues) tab above). Provide a screenshot of the error message if you can.
* Explore the Jupyter Notebooks at the [notebooks](https://github.com/usgs/gems-tools-pro/tree/notebooks) branch of this repo. 


## Collaborate
Suggestions for improvements and edited files submitted by [email](gems@usgs.gov) will be considered, but you are strongly encouraged to use GitHub to fork the project, create a new branch (e.g., "MyFixToProblemXXX"), make changes to this branch, and submit a pull request to have your changes merged with the master branch. Excellent guides for various aspects of the git workflow can be found here:

[https://guides.github.com/](https://guides.github.com/)

## Known issues
* The toolbox was developed against ArcGIS 2.x. It is untested with ArcGIS Pro 3.0
* "Project Map Data to Cross Section" does not always produce the correct apparent dip direction. The dip magnitude is correct, but it may be in the wrong direction.
* "MapOutline" stumbles over some choices of datum.
* "DMU to .docx" requires the [python-docx](https://python-docx.readthedocs.io/en/latest/) third party package. **Do not try to install this package into your default arcgispro-py3 python environment**. Instead, install it into a [clone](https://pro.arcgis.com/en/pro-app/latest/arcpy/get-started/work-with-python-environments.htm#ESRI_SECTION1_175473E6EB0D46E0B195996EAE768C1D). Remember to activate this environment before running the tool.
* Issue 11 describes a problem found when using the Fix Strings tools but may occur elsewhere as well; trying to update rows with an update cursor may throw an error if there is an attribute rule on the field with a message similar to:

```
Failed to evaluate Arcade expression. [
Rule name: Calc _ID,
Triggering event: Update,
Class name: MapUnitLines,
GlobalID: ,
Arcade error: Field not found GlobalID,
Script line: 1]
```

even when the field, e.g.,  ```GlobalID```, does exist. The workaround for now is to disable the attribute rule.

## Acknowledgements
GeMS Tools was originally written by in Python 2.7 by Ralph Haugerud, Evan Thoms, and others and ported to Python 3 by Evan Thoms.

## Disclaimer
This software is preliminary or provisional and is subject to revision. It is being provided to meet the need for timely best science. The software has not received final approval by the U.S. Geological Survey (USGS). No warranty, expressed or implied, is made by the USGS or the U.S. Government as to the functionality of the software and related material nor shall the fact of release constitute any such warranty. The software is provided on the condition that neither the USGS nor the U.S. Government shall be held liable for any damages resulting from the authorized or unauthorized use of the software.

Any use of trade, firm, or product names is for descriptive purposes only and does not imply endorsement by the U.S. Government.
