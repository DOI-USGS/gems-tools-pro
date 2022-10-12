Translating an existing digital dataset into the GeMS schema can be relatively straightforward. Inventory the dataset to determine which elements will be needed in the equivalent GeMS database, make an empty database, load features into the new database, and (mostly) copy and paste to create metadata tables that are internal to GeMS. 

### 1. Inventory and plan

What feature classes will you need? If there are strike-and-dip measurements in the dataset, *OrientationPoints* will be needed. If there are age sample locations and analyses in the dataset, some variant of *GeochronPoints* will be needed. Structure contours dictate the use of *IsoValueLines*. And so on. Perhaps the dataset includes elements not provided for in any of the feature classes or tables defined in GeMS_definitions.py, and you will need to elaborate something new. Do not create alternate feature classes or tables for data that can be incorporated into standard GeMS containers. 

Are the default GeMS attributes for these feature classes sufficient, or do you need to add additional attributes?  

Watch for variable-type incompatibilities. If GeMS declares an field to be a floating point number (e.g., Azimuth), you will be unable to load string values into it--you may need to create a temporary string field ("AziStr"), LOAD string data into it, and then calculate Azimuth = float(!AziStr!) (Python interpreter).

Tables (and feature classes, shapefiles) that contain multiple fields for information that GeMS stores in incompatible fields, or in a single field, present a special challenge. In general, you can

1. Add the input fields to the GeMS table. LOAD data into the table. Use Field Calculator (or code, or hand editing) to translate input field values into GeMS field values. Delete the input fields

   or

2. Add LTYPE, PTYPE, and PTTYPE fields to the empty GeMS database. Add a surrogate field to the input table. Using Field Calculator, calc SurrogateField = str(!InputFieldA!)+'_'_str(!InputFieldB!) ...  Load data, mapping SurrogateField into LTYPE, PTYPE, or PTTYPE, as appropriate. Then use Field Calculator, your own code, or Attribute By Key Value script to assign appropriate values to GeMS fields. Delete LTYPE, PTYPE, and (or) PTTYPE fields

### 2. Make empty database, load features

With your list of needed feature classes, feature datasets, and tables at hand, run the GeMS [Create New Database](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#CreateNewDatabase) script to create an appropriate empty GeMS database. 

As necessary, add unusual fields and feature classes that you identified in your earlier inventory. *Note that if you have many datasets with similar structure, you may find it helpful to extend the feature class definitions given in your local copy of [GeMS_Definition.py](https://github.com/usgs/GeMS_Tools/blob/2018-05-18/Scripts/GeMS_Definition.py).*

LOAD features into their appropriate feature classes. In ArcCatalog, or the Catalog window in ArcMap, 

 	1.  Right-click on target feature class and select **Load** > **Load Data...** 
 	2.  **Next**. Tap the folder symbol at the right of the **Input data** window and navigate to the input feature class (shapefile, coverage, table)
 	3.  **Add**. **Next**
 	4.  Check **I do not want to load all features into a subtype**. **Next**
 	5.  Set field matching. If you are not shown the source field you expect, there may be a type incompatibility. **Next**
 	6.  Check **Load all of the source data**. **Next**
 	7.  **Finish**

Repeat for each set of input features. 

### 3. Set Attributes

In the most common case, where single non-GeMS feature attributes (e.g., LTYPE) are to be mapped into one or multiple GeMS attributes, use script [Attribute By Key Values](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#AttributeByKeyValues) to define and implement these translations. 

Create a DataSOurces row that describes the input dataset ("Source"). In the Notes field of this row, describe any translations and interpretations that you are making.  Invent a DataSource_ID value for this row (e.g., "DAS1").  Calc DataSourceID for all your newly loaded features to be this value. 

At this point no features will have _ID values except the one row in DataSources. Run the [GeMS (re)Set ID values](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#(re)SetIDValues) script to assign _ID values.

Scan the attribute tables for your new feature classes. What values are missing? Can you supply these missing values? If not, try to find the geologist responsible for the input data set. If all else fails and the fields are not required primary or foreign keys, assign null values. 

### 4. CMU and DMU

An already-published map may have a graphic Correlation of Map Units diagram that meets the GeMS requirement for an analog (image) CMU. Or you may choose to use this image as a backdrop and digitize a vector CMU. 

If your source dataset has been published it likely has some sort of Description of Map Units text that you can transcribe into the DMU table. If not, see the map author(s).  

See [CMU and DMU](https://github.com/usgs/GeMS_Tools/wiki/CMUandDMU) for further advice. 

### 5. Topology check

This is tricky. The source digital dataset may contain topological errors. Are you going to faithfully translate these errors or fix them? 

[Run the Topology Check](https://github.com/usgs/GeMS_Tools/wiki/TopologyCheck) script on your database.  If you decide to fix errors, fix them and re-run Topology Check until you are satisfied. 

### 6. Does your database match the source map image?

Many maps are plotted from the source database and then improved for publication using Adobe Illustrator. While often necessary, this is a recipe for map graphics that don't match the source database.  

If you are translating the database for a published map with a graphic image, carefully examine the map image. Are all geologic elements in the image present in the database you have just translated?  If not, you may need to georeference the image to the database and heads-up digitize to capture the missing elements. See [transcribing an analog map](https://github.com/usgs/GeMS_Tools/wiki/TranscribeAnalogMap) for further instructions. 

### 7. [Complete metadata](https://github.com/usgs/GeMS_Tools/wiki/CompleteMetadata)

Most database translation efforts will have a single data source and reference to it will constitute the Source attribute in a single-row DataSources table. Describe any database improvements you have made, such as rectification of topological errors and heads-up digitizing to capture missing features, in the accompanying Notes field. 

### 8. [Finalize database](https://github.com/usgs/GeMS_Tools/wiki/FinalizeDatabase)

