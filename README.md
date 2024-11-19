<img width="250" align="right" src="https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/USGS_logo_green.svg/500px-USGS_logo_green.svg.png"/>

[![GitHub tag (latest SemVer)](https://img.shields.io/github/v/release/DOI-USGS/gems-tools-pro)](https://github.com/DOI-USGS/gems-tools-pro/releases/latest) 
[![Wiki](https://img.shields.io/badge/-wiki-orange)](https://github.com/DOI-USGS/gems-tools-pro/wiki) 
[![Discuss](https://img.shields.io/badge/-discuss-orange)](https://github.com/DOI-USGS/gems-tools-pro/discussions) 
[![HTMLdoc](https://img.shields.io/badge/-jupyter_notebooks-orange)](https://github.com/DOI-USGS/gems-tools-pro/tree/notebooks) 
[![HTMLdoc](https://img.shields.io/badge/-online_gems_documentation-brihtgreen)](https://scgeology.github.io/GeMS/index.html)
[![gems on USGS](https://img.shields.io/badge/-NGMDB_GeMS-brightgreen)](https://ngmdb.usgs.gov/Info/standards/GeMS/)



# GeMS Tools for ArcGIS Pro
- [About](#about)
- [What's new](#whats-new)
- [Installation](#installation)
    - [Download](#download)
    - [Clone](#or-clone)
    - [Configure](#configure)
- [Getting Help](#getting-help)
- [Collaborate](#collaborate)
- [Known Issues](#known-issues)
- [Acknowledgements](#acknowledgements)
- [License](#license)
- [Disclaimer](#disclaimer)

## About
This repository contains an ArcGIS toolbox of Python 3 geoprocessing tools for creating, manipulating, and validating [GeMS](https://ngmdb.usgs.gov/Info/standards/GeMS/)-style geologic map databases for use in ArcGIS Pro. Additional resources; vocabularies, symbology, links to other projects, etc.; are available at the [NGMDB GeMS site](https://ngmdb.usgs.gov/Info/standards/GeMS/#reso).

If you are looking for tools that work in ArcMap using Python 2.7, go to [gems-tools-arcmap](https://github.com/DOI-USGS/gems-tools-arcmap). Due to the planned retirement for [ArcMap](https://www.esri.com/about/newsroom/arcuser/moving-from-arcmap-to-arcgis-pro-after-mature-support/), that repo is no longer being updated and the tools there are considered deprecated.

## What's new
- 11/19/2024, added a new Jupyter Notebook to the [notebooks](https://github.com/DOI-USGS/gems-tools-pro/tree/notebooks) branch. [Populate AreaFillRGB in the DMU table](https://github.com/DOI-USGS/gems-tools-pro/blob/notebooks/Populate%20AreaFillRGB.ipynb) leads you through the process of discovering the color values of the polygon fill symbols used to symbolize map unit polygons, convert the values if necessary to RGB, and update `AreaFillRGB` in the DescriptionOfMapUnits table.
- Version 3.0.0 is in development. It is based on the newer [ArcGIS toolbox](https://pro.arcgis.com/en/pro-app/latest/help/projects/connect-to-a-toolbox.htm#ESRI_SECTION1_3E9B0E3576C34CA18B2CDA3AB61ED7CD) file format (.atbx extension) and will require ArcGIS 2.9 or above.
- The new toolbox will include a Metadata toolset with four new tools for working with metadata:
  - Clear Metadata - deletes all embedded metadata from a file geodatabase object
  - Collate Metadata Sources - collates metadata from multiple sources to produce a single metadata XML file. It is similar to the existing Build Metadata tool but offers a few more options about how to deal with the various sources and can also write a record for each geodatabase item in addition to the single database-level record. It is also being written to work with geopackages. A folder of default GeMS-standardized XML metadata templates (that can be copied and customized) and a CSV file of custom table and field definitions and domain descriptions will replace the current method of saving most metadata template language in string variables and python dictionaries.
  - Export Metadata - replaces the Export metadata button in the Catalog tab > Metadata group in that it exports a spatial reference element along with the embedded metadata
  - Import Metadata - Imports metadata from either one file per geodatabase item or from a single database-level file that contains entity-attribute information about all geodatabase items. Because [upgrading metadata](https://pro.arcgis.com/en/pro-app/latest/help/metadata/upgrade-metadata-to-the-arcgis-format.htm) translates FGDC metadata to the ArcGIS schema, changing many element names and inserting new ones, there is the option with Import Metadata to embed without upgrading so that a completely unaltered version of the intended FGDC metadata is saved with the item. 

## Installation
There are two ways you can get the toolbox. You can download a zip file with the contents of this repository every time there is a new release or you can clone the repository using `git` and pull the latest changes as necessary with a simple terminal command.

### Download
* Download the [latest release](https://github.com/DOI-USGS/gems-tools-pro/releases/latest) from **Releases** or from the green **Code** button above.
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

The documentation for these tools may not be complete or may be poorly formatted for display in either the ArcGIS Pro help popup (hover your cursor over the ? icon when looking at the tool parameter form) or metadata view (right-click on the tool from the Catalog pane and choose View Metadata).

## Getting help
* Each tool comes with documentation inside the parameter form.
* Check out the [wiki](https://github.com/DOI-USGS/gems-tools-pro/wiki) for help on these tools and extensive advice on using these tools to create, edit, and validate GeMS-style databases.
*  If you have a question about how to build or attribute a GeMS-compliant database or the schema in general, visit the [Discussions](https://github.com/DOI-USGS/gems-tools-pro/discussions) tab of this repo. You will need a GitHub acccount to post there. <b>NOTE</b> we are no longer using Gitter for discussions.
* Documentation for the toolbox and all tools and  is also available in **GeMS_Tools_Arc10.docx** and **GeMS_Tools_Arc10.pdf** found in the `Docs` sub-folder — these are both somewhat out-of-date; check back for new versions.
* If, when using a tool, it fails to run and produces an error message, first check that you have the latest release of the tool. If that is not the source of the problem, start a new issue at this repository (see the [Issues](https://github.com/DOI-USGS/gems-tools-pro/issues) tab above). Provide a screenshot of the error message if you can.
* Explore the Jupyter Notebooks at the [notebooks](https://github.com/DOI-USGS/gems-tools-pro/tree/notebooks) branch of this repo.

## Collaborate
Suggestions for improvements and edited files submitted by [email](gems@usgs.gov) will be considered, but you are strongly encouraged to use GitHub to fork the project, create a new branch (e.g., "MyFixToProblemXXX"), make changes to this branch, and submit a pull request to have your changes merged with the master branch. Excellent guides for various aspects of the git workflow can be found here:

[https://guides.github.com/](https://guides.github.com/)

## Known issues
* "Project Map Data to Cross Section" does not always produce the correct apparent dip direction. The dip magnitude is correct, but it may be in the wrong direction.
* "MapOutline" stumbles over some choices of datum.
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

## [License](https://github.com/DOI-USGS/gems-tools-pro/blob/master/LICENSE.md)

## [Disclaimer](https://github.com/usgs/gems-tools-pro/blob/master/DISCLAIMER.md)
