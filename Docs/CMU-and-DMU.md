<a name="top"></a>

**Geologic map units do not have arbitrary relations to each other.**  Unit B is younger than unit A, or B is the same age as A but a different facies, or B is a subspecies of A, or ...

These relations are commonly shown graphically in a **Correlation of Map Units** diagram (**CMU**) ([example 1](http://www.dnr.sc.gov/geology/GeologicMap/3_corr.htm), [example 2](https://pubs.usgs.gov/sim/2940/sim2940_sheet2.pdf)) in which colored, perhaps patterned, and labeled rectangular patches that represent map units are organized by time (vertical axis, higher is younger) and by other dimension(s) such as facies or geography (horizontal axis).  Frequently units are grouped into clusters in age-other space. We read the CMU from top to bottom, left to right, cluster to cluster and within each cluster.  

Most geologic maps also have a free-text description of each map unit. Geologic maps published by the USGS in recent decades have these descriptions organized into a strongly formatted **Description of Map Units** (**DMU**) (see pages 49-50 in [Suggestions to authors of the reports of the United States Geological Survey, 7th edition](https://pubs.usgs.gov/msb/7000088/report.pdf)).  The organization of the DMU, created by headings, font variations, and indentation style, is hierarchical--that of a branching tree, extending from root to branchlet tips--and should correspond to that expressed graphically in the CMU.

In some older maps the CMU and DMU are combined, with blocks of text (descriptions of individual map units or groups of map units) arranged in time-other space ([example](https://ngmdb.usgs.gov/Prodesc/proddesc_26346.htm)). 

The organization of the CMU and DMU conveys an essential part of the story of the map. Without the CMU and DMU--perhaps the map has an alphabetical, single-rank list of map units with descriptions--the map says much less.  

GeMS requires that the CMU and DMU be captured in the database report.  

### CMU

The CMU is fundamentally graphic. It may be created in Illustrator or Paint and stored as a PDF, PNG, or other variety of image file. GeMS allows this. GeMS also provides for representation of the CMU as a feature dataset within the map database. This facilitates consistent symbolization (same unit colors in CMU and map).  

Grab a bar napkin and sketch out the CMU you think fits your map. 

Then, to create the CMU in the GeMS database:

1. Check the **CorrelationOfMapUnits** box when you [create a new database](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#create-new-database).  If you want to add a CMU to an existing database, create a new scratch database (CorrelationOfMapUnits box checked) with the same spatial reference framework as the existing database and copy/paste the scratch CMU into the existing database.
2. Choose the scale at which you will draw the CMU. (Same as the map scale is convenient.) Write this down someplace, perhaps as a one-line note in 00logfile.txt within the database. Get your agency's specification for minimum CMU box size  (USGS: 0.45" x 0.25") and convert this to map units at your chosen scale
3. Open up your editing .mxd (ThisProject-edit.mxd). In the **Table of Contents** pane, right-click on MapUnitPolys and select **Save as Layer File...**  *(Note that we assume you have neither filled out the DMU table nor run Set Symbol Values, and that your unit polygons are symbolized by MapUnit)*
4. Start a new map document (**File** / **New...**) 
   1. Tap the **Add Data** button, navigate to the layer file you just saved, and add it to your map composition
   2. Rename this layer, from MapUnitPolys (probably) to CMUMapUnitPolys (probably)
   3. Right-click on the layer name, select **Properties...**, go to the **Source** tab, and **Set Data Source...** to ThisProject.gdb/CorrelationOfMapUnits/CMUMapUnitPolys
   4. **SAVE** your map document as ThisProject-CMU.mxd
5. Right-click on CMUMapUnitPolys, Edit Features > Start Editing. Create a rectangle the right size.  Select it, right-click and select Attributes, and assign a value to MapUnit
6. Select, right-click on the newly-colored rectangle and Copy. Right-click somewhere on the screen and Paste. Drag the new rectangle to an appropriate position, then select, right-click on it, **Attributes** and assign a (different) value to MapUnit. Repeat until you have all the necessary rectangles. **Editor▼ Save Edits**
7. Add CMULines to your map composition. Draw any necessary brackets and horizontal rules.
8. Create a new annotation feature class within the CorrelationOfMapUnits feature dataset, add it to your map composition, and add any needed headers to the CMU. **Editor▼ Save Edits**. **SAVE**
9. Add another CMUMapUnitPolys layer to your map composition, drawn above the existing CMUMUP layer. Rename it to CMUMUP--borders and labels. Set the symbolization to No color, surrounded by a 0.4-pt wide black line. Turn labels on and label with MapUnit.  Once you have Set Symbol Values, change Label Field: to Label, and set the font to FGDCGeoAgeSubNum. **SAVE**


This process is eased by generating a snap-grid of points spaced 0.05" (page unit) in X and Y at the appropriate display scale, installing this point grid in the CMU map composition, and setting the Snapping environment appropriately. There is a script coming. 


### DMU

[[WikiImages/DMUfragment1.png]]

Once you have the CMU sketched out you can outline the DMU.  **Please read Appendix C, p. 61-68** in the [draft GeMS specification](https://ngmdb.usgs.gov/Info/standards/GeMS/docs/GeMSv2_draft7g_ProvisionalRelease.pdf), for advice and examples on how a DMU table is put together, particularly the construction of HierarchyKey values. 

There are several ways to make a GeMS DMU table. 

1. Edit the database DMU table directly. Enter values in fields as they occur to you and revise as needed.  Works well for a small DMU, but you may stumble at editing a several hundred word unit description in a little box in the ArcMap table interface

2. Build the DMU in Excel. Columns in your Excel worksheet will be the DMU table attributes: MapUnit, Age, Label, FullName, Description, HierarchyKey, GeoMaterial, GeoMaterialConfidence, etc. Name these columns in a header row.  Save the Excel file as "CSV UTF-8 (Comma delimited) (*.csv)". 

   In the Catalog window of ArcMap (or ArcCatalog), right-click on the DescriptionOfMapUnits table in your database and **Load** > **Load Data...**  to wake up the **Simple Data Loader**. Navigate to the just-saved .csv file and load all values. 

   This method handles long fields (>255 characters) and most--perhaps all--special characters

3. Build the DMU in Word, using the [USGS map document template](https://github.com/usgs/GeMS_Tools/blob/master/Docs/MapManuscript_v1-0_04-11.dotx) (in the GeMS_Tools/Docs directory), and feed the Word file to script [.docx to DMU](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#.docxtoDMU). 

   This would be excellent if it consistently worked. Unfortunately the format-parsing code in .docx to DMU is not as robust as it should be. It requires installing the lxml package, which some find difficult, or impossible because of lack of administrator privilege. And it requires that you correctly use MSWord character and paragraph styles


**If you are building a new map (that is, you start with an unknown list of units and incomplete or missing descriptions), it may be easiest to** 

1. Start the DMU directly in the table interface in ArcMap (#1 above)
2. Flesh the DMU out in an Excel or Word table, then copy/paste values from the Excel/Word table into the Description and FullName fields in the database DMU table 
3. Read the HTML transcription of the DMU table generated by the [Validate Database](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#ValidateDatabase) script to ensure that the database DMU table says what you intend it to

**If you are translating or transcribing an existing map it may be easiest to**

1. Build the DMU completely in Excel (option 2 above) and **Load** all fields 
2. Read the HTML transcription of the DMU table generated by the [Validate Database](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#ValidateDatabase) script to ensure that the database DMU table says what you intend it to

If you have installed the Python lxml module on your computer, use script [DMU to .docx](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#DMUtodocx) to convert the database DMU table to a WORD .docx file with full formatting. Use this file to check content and, perhaps, as the final report text, though some editing (e.g., deletion of redundant map-unit ages, formatting of some font effects) will likely be required. Note that this requires that ParagraphStyle values be present and conform to the values used in the  [USGS map document template](https://github.com/usgs/GeMS_Tools/blob/master/Docs/MapManuscript_v1-0_04-11.dotx).  

### A simplified DMU example, with explanation

Suppose a simple [geomorphic map](https://github.com/usgs/GeMS_Tools/wiki/MakeNewGeomorphicMap#0-geologic-map-or-geomorphic-map) has units "alluvial flat", "landslide", "glaciated upland", and "open water". *Note that by convention we don't show open water as a unit in the graphic CMU or text DMU, but open water is necessarily a unit in the GIS representation of many maps, as it covers area and interlocks with other map units.* We might choose to organize these units under two headings: "Holocene Surfaces" (younger, includes alluvial flat and landslide) and "Pleistocene surfaces" (older, includes glaciated upland). 

```
Holocene Surfaces   
	Alluvial flat—Description of alluvial flat map unit… 
	Landslide—Description of landslide map unit… 
Pleistocene Surfaces   
	Glaciated upland—Description of glaciated upland mapunit… 
Open water 
```

The corresponding DMU table will have 6 rows: 

| MapUnit      | Label        | Name                 | Description                                 | HierarchyKey | Symbol       |
| ------------ | ------------ | -------------------- | ------------------------------------------- | ------------ | ------------ |
| &lt;null&gt; | &lt;null&gt; | Holocene Surfaces    | &lt;null&gt;                                | 1            | &lt;null&gt; |
| al           | al           | Alluvial flat        | *Description of alluvial flat map unit…*    | 1-1          | 172          |
| ls           | ls           | Landslide            | *Description of landslide map  unit…*       | 1-2          | 291          |
| &lt;null&gt; | &lt;null&gt; | Pleistocene Surfaces | &lt;null&gt;                                | 2            | &lt;null&gt; |
| gu           | gu           | Glaciated upland     | *Description of glaciated upland map unit…* | 2-1          | 606          |
| wtr          | &lt;null&gt; | Open water           | *Description of open water map unit..*.     | 3            | 411          |

Note the absence of **MapUnit**, **Label**, and **Symbol** values for the headings (Holocene Surfaces, Pleistocene Surfaces). 

**MapUnit** is the ASCII tag--by USGS convention, almost always 4 characters or less--that links rows in this table to the polygons in MapUnitPolys. 

**Label** is almost the same as MapUnit—but MapUnit is a plain-ASCII identifier, whereas we choose to label some of our map units (probably none on this map) with special characters in a [custom font](https://pubs.usgs.gov/tm/2006/11A02/FGDCgeostdTM11A2web_Sec32.pdf) ([download the font here](https://pubs.usgs.gov/tm/2006/11A02/fonts/FGDCGeoAge_win_unix.zip)), using, for example, ^ to indicate the run-together TR that signifies Triassic. Label is a place to store the ASCII strings that create these non-ASCII values. Headings, which do not have corresponding polys, and open water, which by tradition we do not label on the map, have Label = &lt;null&gt;. 

Some map units (e.g., Exe Group), where they are entirely mapped as their constituent formations (e.g., Wye Formation and Zed Formation), will have both MapUnit and Label = &lt;null&gt;.  

**Name** is the term given in boldface in a traditional map explanation, the fully-written out name of this map unit. 

**Description** is a free-text field. Put whatever you need to here, but it should describe the map unit! Headings have no descriptions but they can have headnotes, which are stored in the Description field. 

**HierarchyKey** is a specially-formatted string (see the GeMS documentation for rules) that expresses the order and arrangement of the DMU. It tells us that alluvial flat (HKey=1-1) and landslide (HKey=1-2) are siblings; that Landslide (HKey=1-2) is a variety of Holocene Surfaces (HKey =1); and that Holocene Surfaces (HKey=1) come before (because they are younger than) Pleistocene Surfaces (HKey =2). Sorting on HKey places rows in their correct order. 

Typically the **Symbol** field contains names of fill symbols in an ArcGIS .style file. The values given here are for colors defined in [USGS Symbols2.style](https://github.com/usgs/GeMS_Tools/blob/master/Resources/USGS_Symbols2.zip). Note that Symbol has values (is not &lt;null&gt;) only for rows that have corresponding polygons in MapUnitPolys. Heading rows and unmapped units do not have symbol values. 

### Other GeMS DMU attributes 

GeMS requires several other attributes for rows in the DMU table. 

**Age**  The geologic age as shown in traditional DMU (commonly as bold text within parentheses). Use null values for headings and headnotes.

**FullName**  Full name of unit, including identification of containing higher rank units, e.g., ‘Shnabkaib Member of Moenkopi Formation’. This is the text you would like to see as a fly-out when the cursor lingers over a polygon in an electronic map display. Null values permitted (e.g., for headings, headnotes, geologic units not shown on map).

**ParagraphStyle**  Values are Heading1st, Heading2nd, Heading3rd, …, Headnote, DMU1, DMU2, DMU3, …, or similar. Formatting associated with a paragraph style should be explained with a definition of the style in the glossary. Null values not permitted.

**AreaFillRGB**   {Red, Green, Blue} tuples that specify the suggested color (e.g., '255,255,255', ‘124,005,255’) of area fill for symbolizing this MapUnit. Use of consistent syntax is important to enable computer programs to read this field and display intended color. Each color value is an integer between 0 and 255; values are zero-padded so that there are 3 digits to each R, G, and B value; and color values are separated by commas with no space: NNN,NNN,NNN. Especially important to non-Esri users unable to use the .style file. Null values permitted (e.g., for headings, headnotes). 

If values in the Symbol field are identifiers for colors in the WPGCMYK shadeset (encapsulated in [USGS Symbols2.style](https://github.com/usgs/GeMS_Tools/blob/master/Resources/USGS_Symbols2.zip)), you may use the **[Symbol to RGB](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#SymbolToRGB)** script in GeMS Tools to set AreaFillRGB values.

**AreaFillPatternDescription**  Text description (e.g., 'random small red dashes') provided as a convenience for users who must recreate symbolization. Especially important to non-Esri users unable to use the .style file. Null values permitted (e.g., for headings, headnotes, unpatterned map units). 

**DescriptionSourceID**  Foreign key to table DataSources. Identifies source of DescriptionOfMapUnits
entry. Null values not permitted in map-unit rows. 

**GeoMaterial**  Term to categorize the map unit based on lithologic and genetic character, from
standard term list supplied in table GeoMaterialDict.  Null values permitted for headings and unmapped units. *Note that this term does not replace the map-unit description!  It is present to facilitate ready compilation of simple earth-materials maps. See [draft GeMS standard](https://ngmdb.usgs.gov/Info/standards/GeMS/docs/GeMSv2_draft7g_ProvisionalRelease.pdf) for further discussion*.

**GeoMaterialConfidence**  Describes appropriateness of GeoMaterial term for describing the map
unit. Null values permitted for headings and unmapped units. Possible values are High, Medium, and Low. 

**DescriptionOfMapUnits_ID**  Primary key: DMU1, DMU2, DMU3, etc. Null values not permitted. 

   