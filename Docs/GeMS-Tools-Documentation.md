# Tool documentation

GeMS Tools is an ArcGIS toolbox to facilitate working with the GeMS geologic map database schema. 

To obtain and install GeMS Tools, see the README file at https://github.com/usgs/gems-tools-pro. 

If you see a need to correct or improve this documentation, please feel free to edit this wiki.  

These scripts are far from perfect. When things fail, here are a couple of things to look at.

- Check for unexpected file and directory locks.  Have you Stopped Editing?  Is there another ArcMap process lurking somewhere with a lock on your database?  Quit everything Arc, open Windows Task Manager, check for orphan ArcMap and ArcCatalog process, and restart ArcMap.
- Some of the scripts appear to run into name-space issues that I (RH) don't understand. Quit ArcMap and try running the script from ArcCatalog.

Scripts **.docx to DMU**, **Deplanarize CAF**, **DMU to .docx**, and **FGDC CSDGM2 Metadata** are particularly problematic. MapOutline doesn't handle non-NAD27/NAD83 datums well. 

Here is the current tool set. Click on a tool name to jump to its documentation. 

| Tool                              | Create and edit database | Cartography | Finalize database | Validate database |
| --------------------------------- | :----------------------: | :---------------: | :---------: | :-------------------------------: |
| [(re)Set ID values](#(re)SetIDvalues) |                         |                   | X |  |
| [.docx to DMU](#.docxtoDMU) | X | |  |  |
| [Attribute by Key Values](#AttributebyKeyValues) | X | | |  |
| [Build Metadata](#BuildMetadata) | | | X | |
| [Compact and Backup](#CompactAndBackup) | X | | X |  |
| [Create New Database](#CreateNewDatabase) | X | | |  |
| [Deplanarize CAF](#DeplanarizeCAF) | X | | |  |
| [DMU to .docx](#DMUtodocx) |  | | X | X |
| [Geologic Names Check](#GeologicNamesCheck) |  | | X | X |
| [Inclination Numbers](#InclinationNumbers) |  | X | |  |
| [Make Polygons](#MakePolygons) | X | | |  |
| [Make Topology](#MakeTopology) | X | | |  |
| [MapOutline](#MapOutline) | X | | |  |
| [Project Map Data to Cross Section](#ProjectMap) | X | | |  |
| [Relationship Classes](#RelationshipClasses) |  | | X |  |
| [Set PlotAtScale Values](#SetPlotAtScaleValues) |  | X | X |  |
| [Set Symbol Values](#SetSymbolValues) |  | X | X |  |
| [Symbol to RGB](#SymbolToRGB) |  | | X |  |
| [Topology Check](#TopologyCheck) |  | | X | X |
| [Translate to Shapefiles](#TranslateToShapefiles) |  | | X |  |
| [Validate Database](#ValidateDatabase) |  | | X | X |

### <a name="(re)SetIDvalues"></a>(re)Set ID values

*[GeMS_reID_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_reID_AGP2.py)*

GeMS-style databases use _ID values as primary keys; these values are repeated as ID values in other tables where they serve as foreign keys to tie tables together. **(re)Set ID values** generates _ID values while preserving any links established by existing _ID and ID values. As an option, GUIDs may be substituted for plain-text _ID and ID values.

This script modifies the input geodatabase. Make a backup copy (with **Compact and Backup**) before you run it! 

| **Parameter**                | **Explanation**                                              | **Data Type** |
| ---------------------------- | ------------------------------------------------------------ | ------------- |
| Input_GeMS-style_geodatabase | The geodatabase for which _ID values are to be created or recreated. Must exist. May be file geodatabase (.gdb) or personal geodatabase (.mdb). | Workspace     |
| Use_GUIDs (Optional)         | Default is unchecked (false),which creates _ID values as several characters which denote the table (e.g., MUP for MapUnitPolys) followed by consecutive zero-padded integers: MUP0001, MUP0002, MUP0003, etc. If checked, creates GUIDs (Globally-Unique IDs which are many-byte nonsense strings) for _ID values. | Boolean       |
| Do_not_reset_DataSource_IDs  | If unchecked, resets values of DataSources_ID and all DataSourcesID, LocationSourceID, AnalysisSourceID and similar that refer to DataSources_ID. Default is checked, which leaves these values unchanged. | Boolean       |

### <a name=".docxtoDMU"></a>.docx to DMU

*[GeMS_DocxToDMU_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_DMUtoDocx_AGP2.py)*

.docx to DMU** extracts DMU paragraphs from a Microsoft Word document, calculates values of HierarchyKey, and partially fills in table DescriptionOfMapUnits. Non-DMU paragraphs (the rest of the map text) are ignored. The Word document must be formatted using the paragraph styles in USGS Pubs template *MapManuscript_v1-0_04-11.dotx*, which is included with in folder *GeMS_Tools/Docs*.

DMU paragraphs in the manuscript are those tagged with styles DMU-Heading1, DMU-Heading2, DMU Headnote, DMU Paragraph, DMU Unit 1, DMUUnit 1 (1st after heading), DMU Unit 2, etc. Some character formatting (bold,italic, superscript, subscript, DMU Unit Label character style, FGDCGeoAgefont) is recognized and preserved in DescriptionOfMapUnits. 

If a paragraph is a unit description, UnitLabl in the mapmanuscript is related to field Label in the database tableDescriptionOfMapUnits. If there is no match, UnitLabl is matched to the fieldMapUnit in DescriptionOfMapUnits. If the paragraph is a heading, the headingtext is matched to the Name field in DescriptionOfMapUnits. If a headnote, thefirst 20 characters of the headnote text is matched to the Description field.If no matching row is present in DescriptionOfMapUnits, a new row is created.If a new row is created, the UnitLabl is used to fill both MapUnit and Labelfields in DescriptionOfMapUnits. 

Values of UnitLabl in the manuscript must be unique. 

| **Parameter**            | **Explanation**                                              | **Data Type** |
| ------------------------ | ------------------------------------------------------------ | ------------- |
| DMU_manuscript_file      | Microsoft Word .docx file formatted according to USGS template MapManuscript_v1-0_04-11.dotx. | File          |
| Geologic_map_geodatabase | GeMS-style geodatabase with DescriptionOfMapUnits table. DMU table may be empty or partly complete. | Workspace     |

#####  Significant dependencies 

- The [lxml](http://lxml.de) package must be present on the host computer. Easiest to install using the Python pip utility. Note that you may want to install it for both 64-bit and 32-bit Pythons (e.g., C:\Python27\ArcGISx6410.5and C:\Python27\ArcGIS10.5). 
- *[docxModified.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/docxModified.py)*, which is included in the GeMS toolbox

### <a name="AttributebyKeyValues"></a>Attribute by Key Values

*[GeMS_AttributeByKeyValues_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_AttributeByKeyValues_AGP2.py)*

**Attribute By Key Values** steps through an identified subset of feature classes in the GeologicMap feature dataset and, for specified values of an independent field, calculates values of multiple dependent fields. It is useful for translating single-attribute datasets into GeMS format, and for using GeMS to digitize in single-attribute mode.

Many geologic map database schemas have characterized features--especially lines--with a single attribute such as"contact--approximate". GeMS characterizes lines by multiple attributes, such that 

	LTYPE="contact--approximate"

might, depending on map scale and the author’s intentions, translate to 

	Type="contact”
	IsConcealed="N"
	LocationConfidenceMeters=150
	ExistenceConfidence="certain"
	IdentifyConfidence="certain"
	Symbol="01.01.03"

This tool simplifies the translation from such schemas into GeMS.

| **Parameter**     | **Explanation**                                              | **Data Type** |
| ----------------- | ------------------------------------------------------------ | ------------- |
| Input_geodatabase | An existing GeMS-style geodatabase with a GeologicMap feature dataset. | Workspace     |
| Key_Value_file    | A pipe ( \| ) -delimited text file that describes mapping from unique values of an independent attribute to values of multiple dependent attributes. See file Dig24K_KeyValues.txt (should be located in folder GeMS_Toolbox/Resources) for an example with format instructions. | Text File     |

#####  Comments

**Attribute By Key Values** requires an accessory keyvalue file. You must create a plain-text file (use gedit, Notepad or Wordpad, save as .txt) that looks like: 

	ContactsAndFaults
	LTYPE|Type|LocationConfidenceMeters| ExistenceConfidence| IdentityConfidence| Symbol
	contact|contact| 20| certain| certain| 01.01.01
	contact--approximate|contact| 150| certain| certain| 01.01.03
	…
	OrientationPoints
	STYPE|Type|LocationConfidenceMeters|OrientationConfidenceDegrees|IdentityConfidence|Symbol
	bedding|bedding| 20| 5| certain| 06.01.01
	…

 An [example keyvalue file](https://github.com/usgs/gems-tools-pro/blob/master/Resources/Dig24K_KeyValues.txt) is provided with the toolbox, in the folder *GeMS_Tools\Resources.* Important aspects of the keyvalue file are: 

1. It contains one or more sets of header lines, such as lines 1, 2, and 6, 7 above. Header lines come in pairs: the first line identifies a feature class within the GeologicMap feature dataset. The second line names the independent attribute within that feature class and then the dependent attributes whose values will be calculated based upon the independent attribute. 
2. All lines after a pair of header lines are definitions for the respective values specified in that header line, until the next pair of header lines is encountered. 
3. Values within lines are separated by the pipe symbol (|). This permits the use of commas within values. Trailing (or leading) spaces are acceptable, but not required. 

This file can also be created and edited with a spreadsheet program (e.g., LibreOffice Calc, Microsoft Excel), saving as a .csv file and setting the delimiter to “|”.

**Attribute By Key Values** will:

- Read the keyvalue file for instructions

- Open the GeMS-format database and calculate unassigned feature attributes (values of <NULL>, zero-length string, or zero) based on key values (LTYPE, STYPE, or other). Note that if any attributes have already been assigned they will NOT be changed WITH THE EXCEPTION OF NUMERIC FIELDS WITH ZERO (0) VALUE. This allows you to somewhat easily override the default attributes 

- Write short messages to the script output window if unknown key values are encountered


Tool **Attribute By Key Values** can be run multiple times during the course of building a geodatabase (recommended) or just once at the end.

### <a name="BuildMetadata"></a>Build Metadata

*[GeMS_FGDCMetadata_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_FGDCMetadata_AGP2.py)*

**Build Metadata** helps elaborate [FGDC CSDGM2](https://www.fgdc.gov/metadata) metadata for a GeMS-style geodatabase. The database can be an ArcGIS file geodatabase or a geopackage.

A fully GeMS-compliant database contains the information required for many elements in CSDGM2 metadata, but which must nonetheless be transcribed into a separate file. Likewise, definitions of GeMS-required tables and fields can be found in the [GeMS schema publication](https://scgeology.github.io/GeMS/index.html), but are also required in the metadata. This tool tries to automate the creation of as many of those elements as possible and also adds boilerplate language appropriate to the schema.

Note that this ArcGIS Pro tool does not use the same workflow as the three ArcMap metadata tools and the output is different. The result of running all of the ArcMap tools is a separate metadata record for each table in the database and the metadata are imported back into the embedded ArcGIS metadata. Instead, this tool writes out one database-level record wherein all feature classes and tables are enumerated and defined. This is more in-line with how metadata describing USGS data releases that consist of several related tables are being published. Though this makes for longer metadata records, there is only one to have to look through and keep associated with the database. Furthermore, because the GeMS submittal process does not require embedded metadata (and is moot if submitting a geopackage), this tool forgoes that step. But let us know if you think a tool like that would be useful or would like to add one of your own creation to the toolbox.

**Dependencies** 

Because of a [bug](https://support.esri.com/en/bugs/nimbus/QlVHLTAwMDEyNDI5NA==) in ArcGIS Pro, this tool relies on the open-source GDAL library to collect some of the metadata required by the CSDGM standard for geospatial data. This library is installed with ArcGIS Pro so no extra installation is necessary but you will likely need to configure one environment variable. If you get an error when running the tool that advises you to set ```PROJ_LIB``` to the location of proj.db, follow the steps below:

1. Locate proj.db and copy the path to the folder it is in. It will probably be within the ArcGIS Pro installation folder at ```ArcGIS\Pro\Resources\pedata\gdaldata``` but could be somewhere else.
2. In the Windows Search box on the taskbar, type 'environment variable' and click on the result that reads 'Edit environment variables for your account' (you can 'Edit the system environment variables' if you like but you will probably need admin privileges).
3. Click New and use ```PROJ_LIB``` for the Variable name and the path you copied in step 1. for the Variable value.
4. Close all open dialogs and re-start ArcGIS Pro.

**Use**

To use this tool, first decide if ArcGIS embedded metadata is to be used as the starting point for building the rest of the metadata or if metadata are to be created from scratch. This only applies to file geodatabases as ArcGIS metadata cannot be stored inside geopackages. Note that feature class and table-specific metadata will not be exported; only the metadata embedded in the top-level file-geodatabase container.

If you have added non-GeMS tables or fields to the database, you must provide Entity, Attribute, and Domain definitions and definition sources in the metadata for those items. You can do this in a metadata editor after running the tool or you may provide a path at runtime to a file in which the definitions are stored. The definitions must be formatted in python dictionaries. Examples are [provided in ```my_definitions.py```](https://github.com/usgs/gems-tools-pro/blob/master/Resources/my_definitions.py) in the Resources folder of the toolbox.

To either the embedded or built-from-scratch metadata, the tool will add:

* sources from DataSources to Source Information elements (depending on some choices outlined below)
* Entity, Attribute, and Domain Definitions and Definition Sources from built-in GeMS defintions and, if specified, a custom definitions file
* a Bounding Coordinates element built from the maximum Bounding Coordinates of ```MapUnitPolys``` and ```ContactsAndFaults```
* a Spatial Data Organization Information element (which ArcGIS Pro does not export)
* a Spatial Reference element derived from ```MapUnitPolys```. There can be only one spatial reference section in CSDGM2 metadata so other spatial references, of basedata or cross sections for example, will be ignored.
* GeMS-related text to Supplemental Information, Attribute Accuracy, and Horizontal Positional Accuracy Report elements

If there are missing Entity, Attribute, or Domain definitions, you may choose to leave them blank or replaced with a flag, "MISSING", so that you can find them in a text editor. But if you are using a validating metadata editor, such as Metadata Wizard, those occurrences of "MISSING", though meaningless for the metadata, will not be considered invalid.. It may be best to leave missing definitions blank so that they can be flagged as errors. Metadata Wizard, at least, will color those empty text entry boxes red so you can easily see what is still required.

You can export the metadata at this point and fill in other required sections in a metadata editor or you can specify a path to a template metadata file to which the metadata generated so far should be added.

When working in ArcGIS, every geoprocessing task run on a file geodatabase is recorded as a Process Step in Lineage. This section of the metadata is arguably better used for recording less granular steps in the worklow, so if you find this level of detail distracting, you can choose to have the steps removed completely or replaced by process steps recorded in the template metadata.

For validation of the exported metadata, the tool sends the file to the [USGS Geospatial Metadata Validation Service](https://www1.usgs.gov/mp/) API. The API re-orders any out-of-order elements, re-writing the XML file in the process, and outputs an error log and, if chosen, a more human-readable version of the metadata.

At this point, open the output xml file, which will be in the same folder as the source database, in your favorite metadata editor and fill in the blanks, validating either in the application or with the USGS metadata service until you get compliant metadata. It is NOT recommended to finalize the metadata in ArcGIS. On import, ArcGIS will convert the FGDC-CSDGM2 metadata into ESRI metadata and though you can edit individual CSDGM2 elements, upon export, you will likely not get the results you expect.

Finally, have the record reviewed by a skilled metadata reviewer.


| Parameter Label | Parameter Name | Explanation | Data Type |
| --------------|-------------- | ------------------------- | --------- |
| GeMS database | dataset |  GeMS-compliant file geodatabase or geopackage  | path to dataset |
| Start with embedded metadata? | embedded_metadata | Should metadata embedded in a file geodatabase be exported as the starting document to which GeMS metadata will be added? Boolean. False by default. Optional. | boolean      |
| Custom Definition file | my_defs_file | Path to a python (.py ) file storing dictionaries of definitions of non-GeMS tables and fields. See my_definitions.py in the resources sub-folder of the GeMS Tools folder as an example. Optional. | path to file|
| template | Template metadata | Path to an XML file with reusable boilerplate language that will be added to the output metadata. This file will not be overwritten. Optional. | path to file |
| Sources | sources | Which set(s) of sources should be saved in the output metadata? Sources can come from the DataSources table, the Data Source elements in the embedded metadata, and/or the Source_Information elements in the template metadata. Choices, depending on previous parameter choices, are:<ul><li>save only DataSources</li><li>save only embedded sources</li><li>save only template sources</li><li>save DataSources and embedded sources</li><li>save DataSources and template sources</li><li>save embedded and template sources</li><li>save all sources</li><li>save no sources</li></ul> Default is 'save only DataSources'. Optional | string |
| History (process steps) | history | Which record of processing history should be saved in the output metadata? History can come from the Geoprocessing History elements in the embedded metadata or Process_Step elements in template metadata. Choices are:<ul><li>clear all history</li><li>save only template history</li><li>save only embedded history</li><li>save all history</li></ul> Default is 'clear all history'. Optional. | string |
| Missing definitions and sources | missing | How should the Definition and Definition_Source elements for Entities (tables) and Attributes (fields) be filled out if no definition is found? Choices are:<ul><li>leave blank <em>(seen as an error when validating; easy to find in Metadata Wizard)</em><li>flag as 'MISSING' <em>(not seen as an error when validating but can be easier to find in a text editor)</em></li></ul> Default is 'leave blank'. Optional. Use a custom definitions file to automate the creation of definitions and source text. | string |
| Export .txt version of metadata? | export_text | Should a text (more human readable) version of the output metadata by exported? Boolean. False by default. Optional. | boolean |

### <a name="CompactAndBackup"></a>Compact and Backup

*[GeMS_CompactAndBackup_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_CompactAndBackup_AGP2.py)*

**Compact and Backup** compacts a database and copies it to an archive version. The archive version is 
named *geodatabasename*_current date. Multiple backups in a single day will have suffixes a, b, c, etc. 

| **Parameter**                   | **Explanation**                                              | **Data Type** |
| ------------------------------- | ------------------------------------------------------------ | ------------- |
| Input_geodatabase               | The geodatabase which will be compacted and then backed up   | Workspace     |
| Message_for_log_file (Optional) | Optional message to be written, with timestamp and username, to file 00log.txt inside the geodatabase directory. If this is a personal geodatabase, the write should fail gracefully and this message will not be recorded. | String        |



### <a name="CreateNewDatabase"></a>Create New Database

*[GeMS_CreateDatabase_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_CreateDatabase_AGP2.py)*

**Create New Database** creates a new GeMS-style geodatabase. 

Note that with default settings this tool creates only the minimum required feature dataset, feature classes, and tables. Check the appropriate boxes to add OrientationPoints, GeologicLines, etc. See the GeMS documentation for the purposes of these optional elements. Change the number of cross sections to 1 (or more) to create feature dataset(s) for cross sections. 

This tool may take several minutes to run. 

| **Parameter**                                                | **Explanation**                                              | **Data Type**     |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ----------------- |
| Output_Workspace                                             | Name of a directory. Must exist and be writable.             | Folder            |
| Name_of_new_geodatabase                                      | Name of a file or directory to be created; must not exist in output workspace. Use .gdb extension to create a file geodatabase, .mdb extension to create a personal geodatabase. If no extension is given, will default to .gdb. | String            |
| Spatial_reference_system                                     | May select an ESRI projection file, import a spatial reference from an existing dataset, or define a new spatial reference system from scratch. | Coordinate System |
| Optional_feature_classes_tables_ and_feature_datasets (Optional) | Select items from this list as needed. Note that if you later discover you need an additional feature class, table, or feature dataset, you may 1) define this element from scratch in ArcCatalog, or 2) run this tool again, creating a new geodatabase with the same spatial reference system, and creating the needed feature class(es), table(s), or feature dataset(s). Then copy and paste the additional elements into your existing geodatabase. | Multiple Value    |
| Number_of_cross_sections                                     | An integer in the range 0 to 26.                             | Long              |
| Enable_edit_tracking                                         | If checked, enables edit tracking on all feature classes. Adds fields created_user, created_date, last_edited_user, and last_edited_date. Dates are recorded in database (local) time. Default is checked. This parameter is ignored if the installed version of ArcGIS is less than 10.1. | Boolean           |
| Add_fields_for_cartographic_ representations                 | Default is unchecked. If checked, adds a representation--fields RuleID and Override--and representation rules to feature classes ContactsAndFaults, GeologicLines, and OrientationPoints, and equivalent feature classes in any CrossSection feature datasets that are created. Also adds coded-value domains that tie RuleID values (consecutive integers) to FGDC symbol identifiers (e.g., 1.1.7 for a dotted contact). The representation rules (*aka* symbols) are from the Arizona Geological Survey and are a subset of the FGDC symbology with a few additional symbols. Rules and coded-value domains are copied from a geodatabase and .lyr files in the Resources\CartoRepsAZGS directory within the GeMS toolbox directory. | Boolean           |
| Add_LTYPE_and_PTTYPE                                         | If checked, adds LTYPE field to ContactsAndFaults and GeologicLines and adds PTTYPE field to OrientationPoints. Useful for digitizing purposes, or for ingesting ALACARTE-style data sets. Default is unchecked. With the use of Feature Templates for digitizing, values of LTYPE may be helpful proxies for clusters of Type - IsConcealed - LocationConfidenceMeters - ExistenceConfidence - IdentityConfidence - Symbol values. | Boolean           |
| Add_standard_confidence_values                               | Default is checked. If checked: 1) Attaches standard values of "certain" and "questionable" as a coded-value domain to all ExistenceConfidence, IdentityConfidence, and ScientificConfidence fields. 2) Adds definitions and definition source for "certain" and "questionable" to the Glossary table. 3) Adds the definition source (FGDC-STD-013-2006) to the DataSources table. The use of these particular values, or of only 2 values for confidence, is not required. You may use other values, but they must be defined in the Glossary table. | Boolean           |

##### Significant dependencies 

- *[GeMS_definitions.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_Definition.py)*


### <a name="DeplanarizeCAF"></a>Deplanarize CAF

*[GeMS_Deplanarize_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_Deplanarize_AGP2.py)*

**Deplanarize CAF** removes excess nodes from arcs in the ContactsAndFaults feature class of the GeologicMaps feature dataset of a GeMS-style geodatabase. *Note: This script has not been extensively tested. PLEASE back up your geodatabase before running it. Examine the results for correctness.*

Arcs are IDENTITYed with MapUnitPolys to ascertain their bounding MapUnits. Arc-end points are created, labeled with XY, and sorted by XY to identify nodes. If 2 arcs meet at a node and have identical values for attributes Type, IsConcealed, ExistenceConfidence, IdentityConfidence, LocationConfidenceMeters, DataSourceID, Label, and Notes, they are merged. If 3 arcs meet at a node, the HierarchyKey values of the bounding map units are used to determine which pair of arcs bound the youngest polygon and thus should be continuous across that node if their values of attributes Type, IsConcealed, ExistenceConfidence, IdentityConfidence, LocationConfidenceMeters, DataSourceID, Label, and Notes are identical. If 4 arcs meet at a node, one of the arcs should be IsConcealed = 'Y'. The remaining 3 arcs are then treated as a 3-arc node.

Input geodatabase is assumed to have a GeologicMap feature dataset that contains feature classes ContactAndFaults and MapUnitPolys and a DescriptionOfMapUnits table. 

This script will fail if the geodatabase has a Topology class that involves ContactsAndFaults. 

Feature classContactsAndFaults is assumed to have attributes Type, IsConcealed, ExistenceConfidence,IdentityConfidence, LocationConfidenceMeters, DataSourceID, Label, Notes, ContactsAndFaults_ID, and Symbol. Feature class MapUnitPolys is assumed to have attribute MapUnit. Table DescriptionOfMapUnits is assumed to have attributes MapUnit and HierarchyKey. HierarchyKey must be populated and populated correctly. 

Nodes are named by their XY coordinates recorded to within 0.01 map units. We assume no nodes are so close that they have the same name. 

| **Parameter**     | **Explanation**                     | **Data Type** |
| ----------------- | ----------------------------------- | ------------- |
| Input_geodatabase | Should be a GeMS-style geodatabase. | Workspace     |

### <a name="DMUtodocx"></a>DMU to .docx

*[GeMS_DMUtoDocx_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_DocxToDMU_AGP2.py)*

**DMU to .docx** reads table DescriptionOfMapUnits in a GeMS-style geodatabase and creates"Description of Map Units" as a Microsoft Word .docx file using paragraph styles defined in USGS Pubs template *MapManuscript_v1-0_04-11.dotx*. The resulting file is likely to need minor editing, particularly finding and replacing all instances of “--” with em dashes. 

Use the following style names for ParagraphStyle in your DescriptionOfMapUnits table:

* ```DMU-Heading1``` (number may up to 5)
* ```DMUUnit11stafterheading```
* ```DMUunit1``` (number may be up to 5)

Put heading values in the Name field, accompanying headnote text (if any) in the Description field, and use the appropriate DMU-Heading style in ParagraphStyle.

**DMU to .docx** supports a minimal set of markup tags in text within the Description field: 

`<b> ... </b>`  	bold

`<i>... </i>`  	italic

`<g> ... </g>`  	FGDCGeoAge font

`<sup>...</sup>` 	superscript

`<sub>...</sub>` 	subscript

`<br>` 			break(start new paragraph)

| **Parameter**           | **Explanation**                                              | **Data Type**                |
| ----------------------- | ------------------------------------------------------------ | ---------------------------- |
| Source_geodatabase      | An existing GeMS-style geodatabase. Table DescriptionOfMapUnits should be (at least partially) populated, and HierarchyKey values should be present, as DMU table is sorted on HierarchyKey before translation to .docx file | Workspace or Feature Dataset |
| Output_workspace        | Directory in which output file will be written. Should exist and be writable. | Folder                       |
| Output_filename         | Name of output file. File will be overwritten if it already exists. If filename does not end with ".docx", ".docx" will be appended to file name. | String                       |
| Use_MapUnit_as_UnitLabl | Values in fields *MapUnit* or *Label* can be used for UnitLabl. Default (use *MapUnit*) is recommended for constructing and proofing the DMU table. It may be useful to use *Label* (box unchecked) for creating a final MSWord file of the DMU. | Boolean                      |
| List_of_Map_Units       | If checked, creates a **List of Map Units** which omits map unit descriptions. | Boolean                      |

##### Significant dependencies: 

- *[docxModified.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/docxModified.py)*,which is included in the *GeMS_Toolbox/Scripts* directory
- *MSWordDMUtemplate*, which is a directory within the GeMS Tools\Resources directory. This directory provides essential elements of a Microsoft Word document that uses the paragraph styles defined in USGS Pubs template *MapManuscript_v1-0_04-11.dotx*


### <a name="GeologicNamesCheck"></a>Geologic Names Check

*[GeMS_GeolexCheck_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_GeolexCheck_AGP2.py)*

**Geologic Names Check** automates some of the steps in a geologic names review as required by USGS publication policy. It searches within the DescriptionOfMapUnits table for names and usages found in the U.S. Geologic Names Lexicon (Geolex) and provides a report template in spreadsheet form for the author and reviewer to use during the review process. The tool reports the Geolex names found within the map unit name, the usages associated with those names, and whether or not the author's choice of geographic extent matches that found in Geolex. Comparisons of age and status (formal vs informal) are not at this time considered.

| **Parameter**                         | **Explanation**                                              | **Data Type** |
| ------------------------------------- | ------------------------------------------------------------ | ------------- |
| DMU_Table                     | a GeMS-compliant DescriptionOfMapUnits table. Must contain the fields HierarchyKey, MapUnit, Fullname, and Age, but they may be in any order, need not be CamelCase, and there are no special constraints on how the values are formatted. Values in Name are searched for Geolex names. If no Geolex name is found, Fullname is searched as well.        | Table  |
| States_extent | One or more (comma separated) state or territory abbreviations. Examples are "WA", or "ID,OR,WA" | String |
| open_report_when_completed? (optional) | Should the Excel report file be opened when the script has finished running? | Boolean|

More info at [Filling out the Geologic Names Report](https://github.com/usgs/gems-tools-pro/wiki/Filling-out-the-Geologic-Names-Check-report)

### <a name="InclinationNumbers"></a>Inclination Numbers

*[GeMS_InclinationNumbers_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_InclinationNumbers_AGP2.py)*

Creates annotation feature class OrientationPointLabels with dip and plunge numbers for appropriate features within OrientationPoints. Adds a layer representing the new annotation feature class to your map composition. 

Note that this script invokes a definition query using PlotAtScale values. These must exist! If the output layer appears to be empty, open layer properties and delete the definition query. Do you see inclination numbers? Good. Run **Set PlotAtScales** and then rerun **Inclination Numbers**

If this script fails because of locking issues, try (a) Stop Editing, or (b) save any edits and save the map composition, exit ArcMap, and restart ArcMap. Maybe the script will then run satisfactorily. 

| **Parameter**         | **Explanation**                                              | **Data Type**   |
| --------------------- | ------------------------------------------------------------ | --------------- |
| Feature_dataset       | The feature dataset with class OrientationPoints for which inclination annotation is to be created. | Feature Dataset |
| Map_scale_denominator | Denominator of the map scale fraction. For a 1:24,000-scale map, enter 24000. | Double          |

##### Significant dependencies

Inclination Numbers calls function isPlanar, defined in GeMS_utilityFunctions.py: 

```
returns True if orientationType is a planar (not linear) feature
def isPlanar(orientationType):
    planarTypes = ['joint','bedding','cleavage','foliation','parting']
    isPlanarType = False
    for pT in planarTypes:
        if pT in orientationType.lower():
            isPlanarType = True
    return isPlanarType
```



###<a name="MakePolygons"></a>Make Polygons

*[GeMS_MakePolys3_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_MakePolys3_AGP2.py)*

**Make Polygons**:

- Creates (or recreates) feature classMapUnitPolys from lines in ContactsAndFaults, excluding lines for which IsConcealed='Y'
- Attributes polygons using temporary label points created from any polygons in the pre-existing MapUnitPolys and any label points in feature class MapUnitPoints 
- Flags (a) polygons with multiple, conflicting, label points, (b) multiple, conflicting label points within a single polygon, (c) polygons with blank or null MapUnit values, and (d) contacts that separate polygons of the same MapUnit. These errors are written to feature classes errors_multilabelPolys errors_multilabels, errors_unlabeledPolys, and errors_excessContacts
- IDENTITYs the new MapUnitPolys with a temporary copy of the old MapUnitPolys. Any polygons--or fragments of polygons--that have changed their MapUnit are saved in feature class edit_ChangedPolys
- Optionally, saves old feature class MapUnitPolys to MapUnitPolysNNN, where NNN is a successively higher integer 
- When used within ArcMap, selecting a MapUnitPolys layer will cause the data source of the layer to be changed to the newly created polygon feature class with no other change in layer properties (e.g., symbolization)

Note that if you remove a contact or fault that separates two existing polygons with different MapUnit values and run **Make Polygons**, the resulting multi-(temporary) label polygon is correctly flagged as an error. Re-running **Make Polygons** will (incorrectly) cause this error to disappear! Moral: Run **Make Polygons** once and FIX THE PROBLEMS.

While running, **Make Polygons** writes (overwrites) and deletes temporary feature classesxxxlabel, xxxpolys, and xxxtlabels, all within the GeologicMap feature dataset.

| **Parameter**                         | **Explanation**                                              | **Data Type** |
| ------------------------------------- | ------------------------------------------------------------ | ------------- |
| input_geodatabase                     | An existing GeMS-style geodatabase.                          | Workspace     |
| Save_old_MapUnitPolys (Optional)      | If checked, saves old MapUnitPolys feature class to feature class MapUnitPolysNNN, where NNN is a successively higher zero-padded integer. Default is checked (true). | Boolean       |
| Saved-layer_directory (Optional)      | Directory in which .lyr files are saved for any map layers with sources MapUnitPolys, errors_excessContacts, errors_multilabelPolys, errors_multilabels, and errors_unlabeledPolys. These .lyr files are deleted when script completes. Must have write permission. Default is the directory that hosts the input geodatabase. | Folder        |
| Label_points_feature_class (Optional) | An optional point feature class with attribute MapUnit (and perhaps other attributes), which may used to label polygons. Familiar to those who used workstation ArcInfo, in which such features were necessary. ArcGIS does not _require_ label points; polygons can be created and attributed without them. | Feature Class |



### <a name="MakeTopology"></a>Make Topology

*[GeMS_MakeTopology_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_MakeTopology_AGP2.py)*

Creates and validates a topology feature class within a GeMS-style feature dataset. The new topology class is named GeologicMap_Topology (for the GeologicMap feature class) or xxx_Topology (for all other feature classes, where xxx is the prefix for the ContactsAndFaults-equivalent feature class within that feature dataset). Any existing topology with this name will be deleted. The input feature dataset should contain feature classes xxxContactsAndFaults and xxxMapUnitPolys (where xxx may be null). 

Esri topology rules applied are:

- Must Not Overlap (Line)
- Must Not Self-Overlap (Line)
- Must Not Self-Intersect (Line)
- Must Be Single Part (Line)
- Must Not Have Dangles (Line)
- Must Not Overlap (Area)
- Must Not Have Gaps (Area)
- Boundary Must Be Covered By (Area-Line)

| **Parameter**         | **Explanation**                                              | **Data Type** |
| --------------------- | ------------------------------------------------------------ | ------------- |
| Input_feature_dataset |                                                              | Dataset       |
| use_MUP_rules         | Default = checked. If checked, adds rules that involve MapUnitPolys feature class (no gaps, no overlaps, boundaries must be covered by ContactsAndFaults). In some cases it is useful to build a topology that does not incorporate MapUnitPolys, most commonly so that this topology need not be deleted before (re)making polygons. | Boolean       |

 

### <a name="MapOutline"></a>MapOutline  

*[mapOutline_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/mapOutline_AGP2.py)*

**MapOutline** calculates a map boundary and tics for rectangular (in latitude-longitude space) areas. Locations of boundary and tics are projected to the specified output coordinate system. 

Locations of boundary and tics may be specified in either NAD27 or NAD83, independently of the output datum and projection. This may be useful if, for example, it is desirable that a map boundary coincides with that of a published USGS quadrangle map (most of which are located at even latitude-longitude values in NAD27) but because the mapper is working with GPS coordinates or dense lidar data, both of which are commonly in NAD83-based projections, the map database should be in a NAD83-based projection. 

Output feature classes MapOutline and Tics are written to the top level of the output geodatabase. Any existing feature classes with these names will be overwritten. 

| **Parameter**                | **Explanation**                                              | **Data Type**                |
| ---------------------------- | ------------------------------------------------------------ | ---------------------------- |
| SE_longitude                 | Longitude of SE corner of map rectangle. May be in decimal degrees (-120.625), degrees - decimal minutes (-120 37.5) or degrees - minutes - seconds (-120 37 30). West longitudes (all of US) are negative. | String                       |
| SE_latitude                  | Latitude of SE corner of map rectangle. May be in decimal degrees (42.375), degrees - decimal minutes (42 22.5) or degrees - minutes - seconds (48 22 30). South latitudes (none in US) are negative. | String                       |
| width_(longitudinal_extent)  | E-W extent of map rectangle. Values <= 5 are assumed to be in degrees. Values >5 are assumed to be in minutes. Enter 600 to obtain a 10 degree extent. | Double                       |
| height__(latitudinal_extent) | N-S extent of map rectangle. Values <= 5 are assumed to be in degrees. Values >5 are assumed to be in minutes. Enter 600 to obtain a 10 degree extent. | Double                       |
| tic_spacing                  | Value is in decimal minutes                                  | Double                       |
| Is_NAD27                     | Check to locate map boundary and tics at NAD27 lat-long positions. Uncheck to locate at NAD83 positions. | Boolean                      |
| output_geodatabase           | Must be an existing, writable geodatabase. Please do not select a feature dataset or feature class (though ArcGIS will let you do so). | Workspace or Feature Dataset |
| output_coordinate_system     | Browse to select coordinate system from ArcGIS-provided coordinate system definitions, to import a coordinate system from an existing data set (RECOMMENDED) or define a coordinate system from scratch. | Coordinate System            |
| scratch_workspace            | Directory that is writable. Files xxxbox.csv, xxxtics.csv, xxx1.dbf, xxx1.dbf.xml will be written to this directory and then deleted. Existing files with these names will be lost! | Folder                       |



### <a name="ProjectMap"></a>Project Map Data to Cross Section

*[GeMS_ProjectCrossSectionData_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_ProjectCrossSectionData_AGP2.py)*

**Project Map Data toCross Section** generates backdrop feature classes useful in constructing a geologic cross section. Inputs include the GeologicMap feature dataset of a GeMS-style geodatabase, a cross-section line (feature class, feature layer, or selection), and a DEM. The cross-section line need not be straight. 

Final output is written to feature dataset **CrossSectionxx**,where xx is Output_name_token. This feature dataset will be created if it does not exist. 

By default, all feature classes in the GeologicMap feature dataset are projected into the cross section feature dataset, with the exception of feature classes whose names begin with errors_ and ed_. Alternately, you may choose to project specified feature classes. 

- Polygons are projected to line segments that follow the topographic profile of the section line. Projected lines for MapUnitPolys (or any other polygon feature class that spans the entire section line) constitute the topographic profile. 

- Lines are projected to short vertical line segments located at the point where lines cross the section line. Line segments for ContactsAndFaults are below the topographic profile. All other line feature classes are projected to line segments above the topographic profile. 

- Points are projected to points at the appropriate elevation in the vertical plane of the section line. 


For point feature classes the distance from the section line and the local azimuth of the section line at the projection point are recorded in fields DistanceFromSection and LocalCsAzimuth. If a point feature class has fields Azimuth and Inclination (e.g., OrientationPoints), new fields ApparentDip, Obliquity (angle between Azimuth and LocalCsAzimuth), and PlotAzimuth (rotation field for symbolization) are calculated. 

Output feature classes are named **ed_CsxxInputFeatureClass**, where xx is Output_name_token. Existing feature classes with these names will be overwritten. 

This script also creates empty GeMS feature classes CSxxContactsAndFaults, CSxxMapUnitPolys, and CSxxOrientationPoints if they are not already present in the output feature dataset. You may find it useful to load data from the appropriate ed_CSxxxx feature class into these classes. 

| **Parameter**                         | **Explanation**                                              | **Data Type**                |
| ------------------------------------- | ------------------------------------------------------------ | ---------------------------- |
| GeMS-style_geodatabase                | An existing GeMS-style geodatabase. May be .gdb or .mdb. Must have a GeologicMap feature data set. | Workspace                    |
| Project_all_features_in_GeologicMap   | Default = true (checked). If checked, all point, line, and polygon feature classes within GeologicMap feature dataset (except for certain edit classes) are projected into cross section. If checked, the Feature_classes_to_Project parameter is ignored. If unchecked, you should specify which feature classes should be projected with the Feature_classes_to_Project parameter | Boolean                      |
| Feature_classes_to_Project (Optional) | Used only if Project_all_features_in_GeologicMap is False (unchecked). Specify which point, line, and polygon feature classes to project. Note that the tool will happily project feature classes that are not within the GeologicMap feature dataset. This may not be meaningful! | Multiple Value               |
| DEM                                   | Digital elevation model that encompasses section line and buffered selection polygon. Z units should be equal to XY units of GeologicMap feature dataset. | Raster Dataset               |
| Section_line                          | Feature class, feature layer, or selection that contains ONLY ONE element. Section line need not be straight. Zigs are OK and you can make a section along a stream course. Points to be projected onto section line are selected by buffering the section line with FLAT line ends. To project points that are beyond the ends of the section line, extend the section line. Points are projected to nearest point on section line using *LocateFeaturesAlongRoutes*. | Feature Layer                |
| Start_quadrant                        | Where does section start? (This may not control the section orientation. If you don't get the results you expect, try flipping the section line.) | String                       |
| Output_name_token                     | Short text token used to name output feature dataset and feature classes. The output feature dataset will be named CrossSection *Output_name_token*. If this feature dataset does not exist it will be created. Output feature classes will be named ed_CS*Output_name_tokenInput_featureclass_name* Suggested values are A, B, C, ... If the cross section has vertical exaggeration that is not 1, set the token to B5x, or C10x, or ... | String                       |
| Vertical_exaggeration                 | Default is 1. If you change to another value, suggest you incorporate this value in the output name token. | Double                       |
| Selection_distance                    | Distance, in GeologicMap XY units, within which point features are projected onto the cross section plane. | Double                       |
| Add_LTYPE_and_PTTYPE                  | Feature classes CSxxMapUnitPolys, CSxxContactsAndFaults, and CSxxOrientationPoints will be created in the output feature dataset if they are not already present. Check this box to add LTYPE field to CSxxContactsAndFaults and PTTYPE field to CSxxOrientationPoints. | Boolean                      |
| Force_exit                            | If checked, use sys.exit() to force an exit with error. Allows re-run of tool without re-entry of all parameters. Default is false (unchecked). | Boolean                      |
| Scratch_workspace (Optional)          | If blank, output feature dataset will be used as scratch workspace. Temporary feature classes have names that begin with 'xxx'. Existing feature classes with these names will be overwritten. | Workspace or Feature Dataset |
| Save_intermediate_data                | Default = NO (unchecked). This script creates temporary tables in the input geodatabase and temporary feature classes in the scratch workspace (default is the output feature dataset). If this box is unchecked, these tables and feature classes will not be deleted when the script finished. Check this box if you need these temporary data for troubleshooting. Note that using the default scratch workspace, saving intermediate data and then running the tool to create another feature dataset will not work. You must first delete the temporary data files within the first feature dataset. | Boolean                      |

### <a name="RelationshipClasses"></a>Relationship Classes

*[GeMS_RelationshipClasses1_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_RelationshipClasses1_AGP2.py)*

A GeMS geodatabase has numerous implicit relationships. For example, 

- table DescriptionOfMapUnits references table DataSources via the DefinitionSourceID
- table DescriptionOfMapUnits references table GeoMaterialDict via GeoMaterial
- feature class MapUnitPolys references table DescriptionOfMapUnits via MapUnit
- feature class MapUnitPolys references table DataSources via DataSourceID
- feature class MapUnitPolys references table Glossary via IdentifyConfidence

These relationships may be made explicit as joins or relates (which live in an .mxd document) or as relationship classes which live in the geodatabase. **Relationship Classes** creates a number (though in many cases not all useful or all possible) of relationship classes within a GeMS-style database. 

Note that: 

- Relationship classes are named by the referencing table and field, e.g., DMU_DefinitionSource, DMU_GeoMaterial, MUP_MapUnit, MUP_DataSource, MUP_IdentityConfidence
- Any existing relationship class with the same name is overwritten
- This script creates a RelationshipClasses feature dataset. If this feature dataset already exists it is overwritten. Newly-created relationship classes are NOT placed in this feature dataset, though you may do so afterwards

| **Parameter**    | **Explanation**                                              | **Data Type** |
| ---------------- | ------------------------------------------------------------ | ------------- |
| GeMS_geodatabase | Name of geodatabase to which relationship classes will be added. Note that any existing relationship classes with the same names will be deleted. | Workspace     |



### <a name="SetPlotAtScaleValues"></a>Set PlotAtScale Values

*[GeMS_SetPlotAtScales_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_SetPlotAtScales_AGP2.py)*

Sets values of item PlotAtScale so that a definition query 

`[PlotAtScale] >=MapScale`

limits displayed features to those that can be shown without crowding at the specified map scale. Note that MapScale is the DENOMINATOR of the scale ratio; that is, PlotAtScale of 24000 means feature can be plotted without crowding at map scales of 1:24,000 and larger. 

Input feature class must have PlotAtScale field. If input feature class is named "OrientationPoints", point to be plotted of a too-close pair is biased towards (a) upright or overturned bedding (not bedding without facing direction), (b) bedding (not joint, foliation, lineation, ...), and (c) lower value of OrientationConfidenceDegrees. Large feature classes (>1,000) and large Maximum_value_of_PlotAtScale (>100,000) lead to long calculation times. A more efficient algorithm might be in order. 

| **Parameter**                | **Explanation**                                              | **Data Type** |
| ---------------------------- | ------------------------------------------------------------ | ------------- |
| Feature_class                | Must have PlotAtScale field.                                 | Feature Class |
| Minimum_separation _(mm)     | Set this on basis of symbol diameter, in mm on the page. For FGDC structure symbols, 8 works OK. | Double        |
| Maximum_value_of_PlotAtScale | Large values (e.g., >100,000) with large feature classes (e.g., > 1,000 features) can take a LONG time to calculate. | Double        |



### <a name="SetSymbolValues"></a>Set Symbol Values

*[GeMS_SetSymbols_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_SetSymbols_AGP2.py)*

**Set Symbol Values** sets the *Symbol* attribute for some features in a GeMS-style geodatabase to match symbol IDs in the GSC implementation of the FGDC Digital Cartographic Standard forGeologic Map Symbolization (FGDC-STD-013-2006). 

Values for line symbols are calculated on the basis of map scale and the GeMS attributes *Type*, *IsConcealed*, *LocationConfidenceMeters*, *ExistenceConfidence*,and *IdentityConfidence*. 

Values for orientation point symbols are calculated from *Type* and *OrientationConfidenceDegrees*, for example,

```python
for Type = bedding:
	if OrientationConfidenceDegrees <= threshold:
		symbol = 06.02
	if OrientationConfidenceDegrees > threshold:
		symbol = 06.33 #bedding symbol with open center
```

This script calculates Symbol for feature classes ContactsAndFaults, GeologicLines, and OrientationPoints. 

Symbols are only calculated for recognized Type values. Recognized *Type* values are given in file *[Type-FgdcSymbol.txt](https://github.com/usgs/gems-tools-pro/blob/master/Resources/Type-FgdcSymbol.txt)*, which is located in the Resources folder of GeMS Tools. This file may be edited to reflect your choices for *Type* values, add additional *Type* values, or change the correlation between *Type *and symbol ID. 

| **Parameter**                                           | **Explanation**                                              | **Data Type**   |
| ------------------------------------------------------- | ------------------------------------------------------------ | --------------- |
| Feature_dataset                                         | The feature dataset with classes xxxContactsAndFaults, xxxGeologicLines, and xxxOrientationPoints for which Symbol values are to be calculated. xxx may be null (the GeologicMap feature dataset), "CSA" for CrossSectionA, or similar. | Feature Dataset |
| Map_scale_denominator                                   | Denominator of the map scale fraction. For a 1:24,000-scale map, enter 24000. | Double          |
| Certain_to_approximate_­threshold_mm_on_map             | The value of LocationConfidenceMeters, converted to mm on the map, at which lines change from "certain" (continuous) to "approximate" (dashed). If map scale denominator is 24,000 and the certain to approximate threshold is 1.0, lines with LocationConfidenceMeters <= 24 will have continous-line symbols. If map scale denominator is 100,000 and the certain to approximate threshold is 2.5, lines with LocationConfidenceMeters <= 250 will have continuous-line symbols. | Double          |
| Use_inferred_short_dash_line_­symbols                   | FGDC-STD-013-2006 defines "approximate" (long dash) and "inferred" (short dash) symbols and distinguishes inferred on the basis of how-located, not how-well-located. Yet by this how-located standard (not directly observed), most geologic lines are inferred, and this is not common usage. Check this box to use "inferred" symbols for lines with LocationConfidenceMeters greater than a threshold value. | Boolean         |
| Approximate_to_inferred_­threshold_mm_on_map (Optional) | The value of LocationConfidenceMeters, converted to mm on the map, at which lines change from "approximate" (long dash) to "inferred" (short dash). If threshold is 4 and map scale denominator is 24,000, lines with LocationConfidenceMeters > 98 will be drawn with short dashes. | Double          |
| Use_approximate_strike-and-dip_symbols                  | Default is checked. Uncheck to avoid use of open-center symbols for approximately-oriented bedding. | Boolean         |
| OrientationConfidenceDegrees_­threshold                 | FGDC-STD-013-2006 describes special symbols for some common orientation-data types to denote "when the measurement of strike and (or) dip value is approximate but the location of observation is accurate." For these types, if OrientationConfidenceDegrees > threshold value, the approximate symbol is assigned. | Double          |
| Set_polygon_symbols_and_labels                          | If checked, *Symbol* and *Label* values will be calculated for MapUnitPolys, using values from table DescriptionOfMapUnits. Default is checked. | Boolean         |

##### Significant dependencies

If you check **Set_polygon_symbols_and_labels** there must be a *DescriptionOfMapUnits* table with rows for each map unit AND with values, for each map unit, of *MapUnit*, *IdentityConfidence*, *Symbol*, and *Label*.



### <a name="SymbolToRGB"></a>Symbol to RGB

*[GeMS_WPGCMYK_RGB.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_WPGCMYK_RGB.py)*

Calculates values of AreaFillRGB in table DescriptionOfMapUnits of a GeMS-style geodatabase. Symbol values must be present and are assumed to reference the WPGCYMK color set, which is included in style file USGS Symbols2.style.

| **Parameter**     | **Explanation**                                              | **Data Type** |
| ----------------- | ------------------------------------------------------------ | ------------- |
| Input_geodatabase | An existing geodatabase. May be a file (.gdb) or personal (.mdb) geodatabase. | Workspace     |

##### Significant dependencies: 

- Calls module *[colortrans.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/colortrans.py)*, which calls module *[wpgdict.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/wpgdict.py)*. Both are included in the *GeMS_Toolbox/Scripts *directory




### <a name="TopologyCheck"></a>Topology Check

*[GeMS_TopologyCheck_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_TopologyCheck_AGP2.py)*

**Topology Check** evaluates topological aspects of feature datasets in a GeMS-style geologic map geodatabase. It does not substantially alter the input geodatabase. Output is a new geodatabase *inGeodatabase_*errors.gdb and an HTML file *inGeodatabase*_topologyReport.html. For each feature dataset evaluated the output geodatabase will contain a feature dataset of the same name that contains feature classes which identify possible errors of various kinds. Default is that only the GeologicMap feature dataset is evaluated. 

Note that not all possible topological errors will be identified by this script. Some “errors” flagged by this script may be acceptable. Use your judgment!

The **Nodes** and **MapUnit adjacency** modules use functions *isFault* and *isContact*. These functions, listed below, may need to be modified for some geodatabases. 

```python
def isFault(lType):
   if lType.upper().find('FAULT') > -1:
   	  return True
   else:
      return False

 def isContact(lType):
   lType = lType.upper()
   if lType.find('CONTACT') > -1:
      return True
   elif lType.find('FAULT'):
      return False
   elif lType.find('SHORE') > -1 or lType.find('WATER') >-1:
      return True
   elif lType.find('MAP') > -1: # is map boundary?
      return False
   elif lType.find('GLACIER') > -1 or lType.find('SNOW') >-1 or lType.find('ICE') > -1:
      return True
   else:
      return False
```

| Parameter                                               | Explanation                                                  | Data Type      |
| ------------------------------------------------------- | ------------------------------------------------------------ | -------------- |
| Geodatabase                                             | Input Geodatabase. Note that code was developed with file geodatabases (.gdb) and you may encounter bugs with a personal geodatabase (.mdb). | Workspace      |
| Validate_topology_of_all_­feature_datasets (Optional)   | Default is unchecked (false). Check to evaluate topology of all feature datasets within input geodatabase.  Evaluation of a feature dataset that lacks an identifiable *ContactsAndFaults* feature class will trigger an error. | Boolean        |
| Validate_topology_of_these_­feature_datasets (Optional) | Select specific feature datasets to evaluate. Note that if no feature datasets are selected and Validate_topology_of_all_feature_datasets is unchecked the *GeologicMap* feature dataset will be evaluated by default. Evaluation of a feature dataset that lacks an identifiable *ContactsAndFaults* feature class will trigger an error. Checking "Validate_topology_of_all_data_sets" overrides any selection made here. | Multiple Value |
| Line_and_polygon_topology                               | Default is checked (true). Check to create and validate an ArcGIS topology class for each feature dataset. [See discussion below](#LineAndPolygonTopology). Any identified errors are written to feature classes *errors_xxxTopology_line, errors_xxxTopology_point*, and *errors_xxxTopology_poly*. | Boolean        |
| Nodes                                                   | Geologic map-logic imposes another set of topological constraints on nodes (line junctions) in the ContactsAndFaults feature class. [See discussion below](#Nodes). | Boolean        |
| Fault_directions                                        | Fault lines that are contiguous generally should have the same direction. This, for example, allows thrust teeth to consistently be on same side. Fault lines are identified with the SQL query `"TYPE" LIKE '%fault%'` Nodes where fault direction changes are written to feature class *errors_xxxFaultDirNodes*. [See discussion below](#FaultDirection). | Boolean        |
| MapUnit_adjacency                                       | Creates tables, in the output HTML file, of adjacent map units for three classes of lines. [See discussion below](#MapUnitAdjacency). | Boolean        |
| Identify_duplicate_point_­features                      | Scans each point feature class and identifies possible duplicate features. Any duplicates are listed in tables *dups_XXXXXX.* [See discussion below](#DuplicatePointFeatures). | Boolean        |
| Identify_short_lines_small_­polys_and_sliver_polys      | Scans ContactsAndFaults and MapUnitPolys feature classes to identify lines that are shorter than a threshold value, polygons that are smaller than a threshold value, and polygons that have area-circumference ratios (polygon width) that are smaller than a threshold value. Map scale denominator (below) must be set correctly! Identified features are written to feature classes *errors_xxxShortArcs*, *errors_xxxSkinnyPolys*, and *errors_xxxSmallPolys*. | Boolean        |
| Map_scale_denominator                                   | Value used to identify too-short arcs, too-small polys, and too-skinny polys. Integer. | Long           |
| minimum_line_length__mm                                 | Threshold value, in millimeters at map scale, used to identify too-short arcs. | Double         |
| minimum_poly_area__sq_mm                                | Threshold value, in square millimeters at map scale, used to identify too-small polygons. | Double         |
| minimum_poly_width__mm                                  | Threshold value, in millimeters at map scale, used to identify sliver polygons. | Double         |
| force_exit_with_error                                   | Default is unchecked (false). When checked, forces an error upon normal completion of script. Useful when debugging, as it returns focus to the script window while preserving all input values. | Boolean        |

##### <a name="LineAndPolygonTopology"></a>Line and polygon topology includes the following rules

- Must Not Overlap (Line) *xxxContactsAndFaults* 
- Must Not Self-Overlap (Line) *xxxContactsAndFaults, xxxGeologicLines* 
- Must Not Self-Intersect (Line) *xxxContactsAndFaults, xxxGeologicLines* 
- Must Be Single Part (Line*) xxxContactsAndFaults, xxxGeologicLInes* 
- Must Not Overlap (Area) *xxxMapUnitPolys* 
- Must Not Have Gaps (Area) *xxxMapUnitPolys* 
- Boundary Must Be Covered By (Area-Line) *xxxMapUnitPolys / xxxContactsAndFaults*  

Note the lack of a rule *Must Not Have Dangles (Line)*. This is because dangling fault lines (and dangling concealed fault or contact lines) are common in geologic maps and are not errors. Dangling contacts (which are errors) are identified by the **Nodes** option. 

##### <a name="Nodes"></a>Nodes may be evaluated by the following rules

- More than 4 lines never join at a node. 
- Four lines join at a node only if two opposite lines are contacts (not concealed) and the other lines are both of the same Type and one or both is concealed. ***This explicitly disallows the possibility of faults that do not offset contacts.*** 
- Where three lines join, either none are concealed or all are concealed. An exception is where two of the lines are the map boundary.  
- There should be no pseudonodes (junctions between only two lines where both lines have same values for Type, LocationConfidenceMeters, ExistenceConfidence, IdentityConfidence, and DataSourceID). Pseudonodes where the lines are identical—i.e., the line joins itself (forming a closed loop) are OK.  
- Nodes with one line are dangles. Dangles are permissible where the line is a fault or the line is concealed. Note that some fault dangles are errors.  To evaluate conformance with these rules, the input ContactsAndFaults feature class is first planarized, that is, all lines are broken at intersections. Nodes that do not meet these constraints are written to output feature class *errors_xxxBadNodes*.

##### <a name="FaultDirection"></a>Fault direction

Note that this routine may not identify some direction errors where three fault arcs meet.  Also, some changes of fault-arc direction are intentional, for example on a scissors fault where the DOWN side changes along fault strike. 

##### <a name="MapUnitAdjacency"></a>Tables of MapUnit adjacency

ContactsAndFaults can be IDENTITYed with MapUnitPolys to ascertain the map units on either side. Results are displayed in tables arranged by LEFT MAP UNIT (Y axis) and RIGHT MAP UNIT (X axis). Values on each axis are sorted by DescriptionOfMapUnits.HierarchyKey. Arcs in ContactsAndFaults are divided into 3 groups and a table is written for each:

- Concealed contacts and faults (*IsConcealed = 'Y')* 
- Contacts (not concealed) (*isContact* and *IsConcealed = 'N*') 
- Faults (not concealed) (*isFault* and *IsConcealed = 'N'*) 

These tables can be useful for identifying mis-tagged polygons and lines. In the table for **Concealed contacts and faults**, all arcs should list along the diagonal (same unit on either side). Table **Contacts (not concealed)** should have no diagonal values (no internal contacts) and significant unconformities will correspond to rows & columns with large numbers of populated cells. Table **Faults (not concealed)** makes it easy to identify faults that cut young map units; in many cases these are likely to be digitizing errors.  

Identifying information for concealed lines that separate polygons with different MapUnit values and non-concealed contacts that separate polygons with identical MapUnit values is written to HTML tables **Bad concealed contacts and faults** and **Internal contacts**.

##### <a name="DuplicatePointFeatures"></a>Duplicate point features

Flags those features that:  

- Have the same location, and 
- Have the same *Type* values, and  
- If attributes *Azimuth* and *Inclination* are present, have the same *Azimuth* and *Inclination* values 

Note that entries in a geochem, geochron, or sample table that represent multiple samples taken at a single locale will (incorrectly) generate errors. 

##### <a name"SmallFeatures"></a>Small feature inventory

Uses the values for minimum line length, minimum polygon area, and minimum polygon width to identify arcs and polygons that are, perhaps, too small. Note that none of these are in any sense errors in the content of the geologic map. 

These inventories may be useful to find digitizing errors and to help enforce cartographic standards regarding minimum map-unit polygon size. 

### <a name="TranslateToShapefiles"></a>Translate To Shapefiles

*[GeMS_TranslateToShape_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_TranslateToShape_AGP2.py)*

**Translate to Shapefiles** converts a GeMS-style ArcGIS geodatabase to two shapefile packages:

- OPEN--Consists of shapefiles, additional .dbf files, and pipe-delimited text files. Field renaming is documented in output file *logfile.txt*. This package will be a complete transcription of the geodatabase without loss of any information. 
- SIMPLE--Consists of shapefiles alone. Tables Glossary, DataSources, and DescriptionOfMapUnits are joined to selected feature classes within feature dataset GeologicMap, long fields are truncated, and these feature classes are written to shapefiles. Field renaming is documented in output file *logfile.txt*. This package is a partial (incomplete) transcription of the geodatabase, but will be easier to use than the OPEN package. 

Output is written to directories *DBName*-simple and *DBName*-open, where *DBName* is the name of the input geodatabase, without gdb or mdb suffix. If these directories already exist, any files within them will be deleted. 

| **Parameter**     | **Explanation**                                              | **Data Type** |
| ----------------- | ------------------------------------------------------------ | ------------- |
| Input_geodatabase | An existing geodatabase. May be a file (.gdb) or personal (.mdb) geodatabase. | Workspace     |
| Output_workspace  | Must be an existing folder. Output folders *DBName*-open and *DBName*-simple will be written here, as well as temporary geodatabase xx*DBName*. | Folder        |

### <a name="ValidateDatabase"></a>Validate Database

*[GeMS_ValidateDatabase_AGP2.py](https://github.com/usgs/gems-tools-pro/blob/master/Scripts/GeMS_ValidateDatabase_AGP2.py)*

**Validate Database** audits a geodatabase for conformance with the GeMS schema and reports compliance as “may be **LEVEL 1 COMPLIANT**”, “is **LEVEL 2 COMPLIANT**”, or “is **LEVEL 3 COMPLIANT**”. It also runs mp (metadata parser) to check for formal errors in geodatabase-level FGDC metadata. Note that qualify as LEVEL 2 or LEVEL 3 compliant a database must also be accompanied by a peer-reviewed geologic names report. 

Compliance criteria are:

**Level 1**: 
* No overlaps or internal gaps in map-unit polygon layer
* Contacts and faults in single feature class
* Map-unit polygon boundaries are covered by contacts and faults lines

Databases with a variety of schema may meet these criteria. **Validate Database** cannot confirm LEVEL 1 compliance. 

**Level 2**:
* 2.1 Has required elements: nonspatial tables DataSources, DescriptionOfMapUnits, GeoMaterialDict; feature dataset GeologicMap with feature classes ContactsAndFaults and MapUnitPolys
* 2.2 Required fields within required elements are present and correctly defined
* 2.3 GeologicMap topology: no internal gaps or overlaps in MapUnitPolys, boundaries of MapUnitPolys are covered by ContactsAndFaults
* 2.4 All map units in MapUnitPolys have entries in DescriptionOfMapUnits table
* 2.5 No duplicate MapUnit values in DescriptionOfMapUnit table
* 2.6 Certain field values within required elements have entries in Glossary table
* 2.7 No duplicate Term values in Glossary table
* 2.8 All xxxSourceID values in required elements have entries in DataSources table
* 2.9 No duplicate DataSources_ID values in DataSources table

**Level 3**
* 3.1 Table and field definitions conform to GeMS schema
* 3.2 All map-like feature datasets obey topology rules. No MapUnitPolys gaps or overlaps. No ContactsAndFaults overlaps, self-overlaps, or self-intersections. MapUnitPoly boundaries covered by ContactsAndFaults
* 3.3 No missing required values
* 3.4 No missing terms in Glossary
* 3.5 No unnecessary terms in Glossary
* 3.6 No missing sources in DataSources
* 3.7 No unnecessary sources in DataSources
* 3.8 No map units without entries in DescriptionOfMapUnits
* 3.9 No unnecessary map units in DescriptionOfMapUnits
* 3.10 HierarchyKey values in DescriptionOfMapUnits are unique and well formed
* 3.11 All values of GeoMaterial are defined in GeoMaterialDict. GeoMaterialDict is as specified in the GeMS standard
* 3.12 No duplicate _ID values
* 3.13 No zero-length or whitespace-only strings

**Validate Database** checks for schema extensions: are there tables, feature datasets, feature classes or fields that are not defined by the standard?

**Validate Database** lists contents of tables DataSources, DefinitionOfMapUnits, Glossary, and (if present) MiscellaneousMapInformation in human-readable form.

**Validate Database** also inventories the database and reports the number of rows, fields, and field definitions for all tables and feature classes. 

Output is written to several files in *Output_workspace*: *Input*.gdb-Validation.html, *Input*.gdb-ValidationErrors.html, *Input*.gdb-vFgdcMetadata.txt, *Input*.gdb-vFgdcMetadata.xml, and *Input*.gdb-vFgdcMetadataErrors.txt.  Topology errors are recorded in *Input*_Validation.gdb.


***If ArcMap is open, any joins--e.g., MapUnitPolys to DescriptionOfMapUnits--may need to be removed. If, when running this script from ArcMap, it fails to inventory some feature classes, try running it from ArcCatalog. If MapUnitPolys, ContactsAndFaults, or a similar feature class in another feature dataset participates in a relationship class--e.g., feature-linked annotation--ArcGIS may crash when the script attempts to copy the feature class into the Validation gdb to check topology.*** 

Note that using this script with a geodatabase with a schema that differs significantly from GeMS may not yield a useful report.

| **Parameter**               | **Explanation**                                              | **Data Type** |
| --------------------------- | ------------------------------------------------------------ | ------------- |
| Input_geodatabase           | A file geodatase (.gdb). The .gdb extension must be included. | Workspace     |
| Output_workspace (optional) | A directory that must exist and be writable. If no directory is specified, defaults to host directory for *Input_geodatabase*. | Folder        |
| Refresh GeoMaterialDict     | Databases built with earlier versions of the GeMS toolbox will generate numerous errors associated with GeoMaterialDict and GeoMaterial values. Check this box to replace the GeoMaterialDict table in the database with the current version. The GeoMaterials domain (available as a picklist while editing the DescriptionOfMapUnits table) is also replaced. ***This option permanently modifies the geodatabase. Perhaps you should back it up before using this option.*** | Boolean |
| Skip topology checks        | If checked, potentially time-consuming topology checks will be skipped and database will FAIL level 2 and level 3 compliance checks. This may be useful when testing for other aspects of compliance with the GeMS schema. | Boolean |
| Delete unused Glossary and DataSources rows | Automatically delete any rows in Glossary and DataSources that describe Terms and Sources that are unused elsewhere in the database. If deleted rows have missing required values these still show up as errors. Rerun the Validate Database script to clear such errors. Deletion of a Glossary row may render a DataSource row unneeded. Rerun the Validate Database script to discover such errors. ***This option permanently modifies the geodatabase. Perhaps you should back it up before using this option.*** | Boolean |