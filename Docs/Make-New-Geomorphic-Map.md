This exercise was developed for a senior-level *GIS for Earth Sciences* class. It has the following objectives: 

- Work with lidar topography
- Learn about geologic maps
- Learn GeMS 
- Improve your ArcMap skills

PRODUCT: a draft geomorphic map report. Includes 5 files:

1. .gdb (database), zipped for transport
2. .pdf of map sheet, described below
3. a short summary earth history (perhaps a bulleted list; can be .txt, .docx, .html, or .pdf)
4. .html output from **Topology Check** script
5. .html output from **Validate Database** script 

REQUIREMENTS:

- Mapped area shall have an area of at least 25 million ft<sup>2</sup> (5,000 ft x 5,000 ft, about 1 mile x 1 mile)
- Map units shall fall into at least 3 age classes
- Map sheet has map graphic at a scale of circa 1:20,000, Correlation of Map Units diagram, Explanation of Symbols, Title, Author, Scale, Date, location diagram
- Map database (.gdb) conforms to GeMS schema: GeologicMap and CorrelationOfMapUnits feature datasets; populated DescriptionOfMapUnits, Glossary, and DataSources tables. Passes Topology Check and Validate Database scripts. *Note that, for this project, null values in DMU fields GeoMaterial, GeoMaterialConfidence, ParagraphStyle, AreaFillRGB, and AreaFillPatternDescription are acceptable*

While these instructions are for making a new geomorphic map, making a geologic map (heads-up digitizing from field sheets, aerial images, topography, and other existing maps) is similar. 

### 0. Geologic map or geomorphic map?

A geologic map shows the distribution of earth materials which are classified—largely—by age. Such maps are both descriptive (showing observations) and predictive (suggesting the presence of materials where they have not been observed). They are of significance both for their direct utility in showing where to find granite, groundwater, and gold, and for the earth history that they disclose.  Making a geologic map generally requires a significant amount of expensive field work and is not a task that can be completed in the short time frame of this exercise. 

A geomorphic map shows the distribution of surfaces that form the upper bound of earth materials. In many settings such surfaces can be classified—largely—by age, and the resulting map also discloses earth history. With adequate topographic information, a geomorphic map can be made quickly.  Making a geomorphic map is good practice at seeing earth history and an excellent way to learn some of the GIS skills and tools used in geologic mapping. 

### [1. Read about directory structure](https://github.com/usgs/GeMS_Tools/wiki/HardDriveHygiene)

Check out the link above. Then decide what your file system will look like. Here's one possibility:

```
    MyFileSystem/
​	Projects/
​            ThisProject/
            AnotherProject/
        Resources/
 ​	    GeMS_Tools/
            DEM_Library/
```

### 2. Download lidar DEM and make derivative images

#### a.  Download lidar

1. Go to <http://lidarportal.dnr.wa.gov>. Explore. Find an interesting area to interpret. Avoid built-up areas. Avoid steep mountains. Don’t choose too large an area, but get more than the 5,000 ft x 5,000 ft minimum area; perhaps a 10,000 ft x 10,000 ft area. 
2. Select an area that shows an interesting geomorphic history. The eastern margin of the Puget Lowland provides lots of good possibilities; look in the vicinity of  http://lidarportal.dnr.wa.gov/#47.88605:-121.84979:14, http://lidarportal.dnr.wa.gov/#47.11693:-122.02841:13, and http://lidarportal.dnr.wa.gov/#47.09569:-122.15106:14. The area should have easily-discerned landforms that correspond to at least 3 stages of geomorphic/geologic history. These might be glaciation, subsequent terrace formation, and modern erosion and alluviation. Or something else, or additional stages. 

3. Adjust your field of view to barely encompass the area you have chosen. Select "**Download Current View**" (upper left corner of page). Unselect boxes until you only have the DTM (Digital terrain model). Click **Download**. When the download is complete, unzip your download file. 


#### b.   Mosaic downloaded tiles, make images

1. Make a new, empty file .gdb, e.g., *MyLidarData*.gdb. This .gdb should be in your Projects folder, in subfolder *ThisProject* 

2. Start ArcMap or ArcCatalog
3. If download contains multiple tiles, use the ArcGIS **Mosaic to New Raster** tool, with output inside the file gdb; otherwise, copy the single tile into the file gdb. Name new bare-earth raster *myarea*_be

*If you use **Mosaic to New Raster** for lidar data, be sure to set **Pixel Type (optional)** to **<u>32_BIT_FLOAT</u>**. Number of Bands should be 1. When piecing together tiles from a single survey the Mosaic Operator and Mosaic Colormap Mode can be left at default values*

4. When you have successfully moved/merged the tile(s) from your lidar download into a file geodatabase, delete the zip file and the directory you unzipped it to 
5. Using ArcGIS Hillshade command, make 3 hillshades:  myarea_be_ne, myarea_be_nw, myarea_be_v10. Put them all within *MyLidarData*.gdb

| Output  raster | Input  raster | azimuth  | altitude | Z factor |
| :------------: | :-----------: | :------: | :------: | :------: |
|  myarea_be_ne  |   myarea_be   |    45    |    45    |    1     |
|  myarea_be_nw  |   myarea_be   |   315    |    45    |    1     |
| myarea_be_v10  |   myarea_be   | anything |    90    |    10    |

### 3. Download and install GeMS Tools

If you haven't already: 

1. Go to <https://github.com/usgs/GeMS_Tools>  

2. Partway down left side of page, find button that says “Branch: master”.  Tap the button, select the Tags tab, and select “06Jan2018” (or the most recent tag). The button should now say “Tag: 06Jan2018”

3. At the right side of the page, find the green “Clone or download” button. Tap it, and select “Download ZIP”

4. After the download is completed, find your downloaded file, unzip it, and place the resulting GeMS_Tools_*date* folder within your Resources (or similar) directory 


### 4. Start ArcMap 

1. Add the lidar bare-earth DEM and the derivative images you made to the map composition.  Turn off all of the layers except a NE or NW hillshade.  **SAVE** the map composition into your ThisProject folder. Name might be ThisProject-edit.mxd
2. [Configure ArcMap](https://github.com/usgs/GeMS_Tools/wiki/ConfigureArcMap). Note that you won't be able to set Snap-to-sketch until you have added a line feature class to your map composition

3. Open the ArcToolbox window. If **GeMS Tools** is not listed, [add the GeMS_Tools toolbox](https://github.com/usgs/GeMS_Tools/wiki/ConfigureArcMap#add-gems_tools)

4. Expand **GeMS Tools** and make an empty GeMS-style database with the [Create New Database](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#create-new-database) script
   1. Output workspace is your ThisProject folder. Name of new geodatabase could be ThisProject.gdb  
   2. For Spatial Reference System, click the select folder icon at right, open **Layers**, and take the option presented (which will be the Spatial Reference System for your lidar DEM and derivatives)
   3. Check the following optional elements: CorrelationOfMapUnits, MiscellaneousMapInformation
   4. Ensure that **Add fields for cartographic representations** is unchecked 
   5. Check **Add LTYPE and PTTYPE**
   6. Check **Add standard confidence values**  
   7. **Enable edit tracking** can be checked or unchecked  
   8. **OK**. Script will run 
5. Add ContactsAndFaults24K.lyr to the map composition
   1. Click on the Add Data button, navigate to the Resources folder of our GeMS_Tools directory, and select ContactsAndFaults24K.lyr. This will add a group of 4 layers to your map composition
   2. Right-click on layer LTYPE and select **Data** > **Repair data source**... Set the data source to the ContactsAndFaults layer within the GeologicMap feature dataset of your newly-created database. **SAVE**
6. Add ThisProject.gdb/GeologicMap/MapUnitPolys to your map composition. **SAVE**
7. Finish configuring ArcMap 
   1. On the Editor toolbar, click the **Editor▼** dropdown and select **Start Editing**
   2. On the Snapping toolbar, click the **Snapping**▼ dropdown and ensure that **Snap To Sketch** is checked. **SAVE**

### 5. Map geomorphology

#### a.  Think

What are your map units? Make a list of geomorphic surface types (for example, glaciated surface, hillslope, alluvial flat). This list may grow as you explore the DEM. As you map, you may discover that you can subdivide some surface types (especially alluvial flats) on the basis of cross-cutting relations and elevation differences that require different ages for different instances of the same surface type. For example, old alluvial flat, young alluvial flat, younger alluvial flat.

How well can you locate contacts that separate different surface types? Most such contacts are breaks in slope and, where not rounded by subsequent history, can be located within a few raster cells, commonly within 3-5 meters. Poor DEM quality or human modification may obscure some contacts, decreasing the accuracy of location. Some contacts are subtle textural changes, or hard-to-define boundaries between assemblages of features (a worst case: ice melt-out terrain adjacent to landslide), and locational error will be greater. In this landscape, with an excellent lidar DEM, the most significant limit to the accuracy of your map is likely to be the care with which you digitize boundaries. 

Human-modified surfaces are (for this exercise) generally uninteresting. Try to see through such modifications and map the surface before humans modified it. If there are areas where you cannot see through human modification, map “modified ground”. There will be small areas that are dominated by artifacts in the lidar DEM—mostly ‘crystal forest’ that is the result of very dense vegetation, very few ground returns, and inaccurate discrimination of ground and vegetation returns. Try to ignore such artifacts.

#### b. Digitize contacts

Your task is to outline the map area and divide it into areas that will become map-unit polygons. You need not digitize all contacts at once. It is quite reasonable to digitize part of the map, check topology, make and color polygons, and then return to digitize more contacts. 

1. If you are not already in edit mode in the GeologicMap feature dataset, go to the **Table of Contents** pane, right-click on ContactsAndFaults24K--LTYPE and select **Edit Features** > **Start editing**. 
2. On the toolbar, click the **Editor▼**  dropdown and select **Editing Windows** > **Create Features** 
3. Click the **Snapping▼** dropdown on the ArcMap toolbar and ensure that **Use Snapping** is set. This is important! Click the **Snapping** dropdown again and ensure that **Snap To Sketch** is checked. **SAVE**
4. Digitize your map boundary first 
   1. Select the “contact  10 m” template and digitize the boundary
   2. With the Edit Tool (tail-less arrow to right of **Editor**▼ on the Editing toolbar), select the just-digitized boundary. Right-click and select Attributes…  Set Type = "map boundary”. Set IsConcealed = "N". Set ExistenceConfidence and IdentityConfidence = "certain". Set LocationConfidenceMeters = 0.  (*Why?*)  Select the map boundary and, using the Split tool (on Editor toolbar), break it into a couple of pieces 
5. Select an appropriate feature template from the LTYPE list in the **Create Features** pane and start digitizing. Work from younger to older, mostly. 1st line is map boundary; 2nd set of lines might be waterlines; 3rd, boundaries of modified land (if you map any)
6. As you work, note whether the width of the grey LocationConfidenceMeters envelope is appropriate.  If not, 
    1.  Right-click on the arc, select **Attributes…**, and change the value of LocationConfidenceMeters
    2.  Next time, select a more appropriate feature template
7. **Editor▼** > **Save Edits** frequently
8. At the end of each digitizing session, or whenever you change the source material (lidar, scanned field sheet, aerial image, etc.), set DataSourceID values
    1. Open the ContactsAndFaults2k--LTYPE attribute table
    2. RIght-click on column header DataSourceID and Sort Ascending
    3. Select rows with no value for DataSourceID
    4. Use the Field Calculator... to set DataSourceID to an appropriate value
        1. Note that you need to double-quote "  " the value, as it is a string
        2. Value will correspond to an entry (that need not yet exist) in table DataSources
        3. Value might be "DAS02", or "lidar", or "ESRI World Imagery", or ...

#### c.  Check topology

When you have digitized a number of contacts it is useful to check that they have correct topology (no dangles, no overlaps, no self-intersections) before you make polygons. Topology is not difficult to build from scratch using the ArcGIS Topology wizard, but you may find it easier to use the GeMS [Make Topology](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#make-topology) script: 

1. Open the ArcToolbox window. Expand GeMS Tools. Double-click on **Make Topology**. 
   1. For **Input feature dataset**, select the GeologicMap feature dataset of your geodatabase. **Use MUP rules** may be checked or unchecked--at this point it may be moot, as you may have no map-unit polygons 
   2. OK 

2.  Add the resulting topology class to your map composition  
    1.  Click on the Add Data button on the ArcMap toolbar, navigate to ThisProject.gdb/GeologicMap, and select GeologicMap_topology 
    2.  Add 
    3.  You will be asked if you wish to add the participating feature classes—select NO 


3.  If you are not already in Edit mode: In **Table of Contents** pane, right-click on ContactsAndFaults24K--LTYPE and select **Edit Features** > **Start Editing**
4.  Pan and zoom around looking for topology errors, or use the Error Inspector window, available on the Topology toolbar. Fix any errors, especially dangles, that will interfere with building polygons 
5.  **Editor**▼> **Save Edits**

#### d. Make and color polygons

1.  There are at least three ways to [make polygons](https://github.com/usgs/GeMS_Tools/wiki/MakeColorPolygons#make-polygons).  Here we review just one (digitize arcs/build polys as you go) 
    1.  If you are not already in edit mode, start editing within the GeologicMap feature dataset
    2.  Select lines that bound one or more polygons-to-be
    3.  Use the Make polygons tool (wrench over box in Advanced Editing toolbar) [[WikiImages/MakePolygonsTool.png]]
    4.  If necessary, select and delete duplicate polygons
    5.  Select each newly-created polygon, right-click and select **Attributes...**, and type in a value for MapUnit. This will be a short (1-4 character) tag that identifies the map unit (for example, modified land = m, hillslope = h, alluvial flat = al, ...). If you are uncertain about the identity of the polygon (for example, it <u>might</u> be a landslide), enter "uncertain" as a value for IdentityConfidence. If you are certain, leave this value blank. 

2. While you are in the early stages of developing your map, [color MapUnitPolys by categories using MapUnit](https://github.com/usgs/GeMS_Tools/wiki/MakeColorPolygons#color-by-categories-using-mapunit)
3. While still viewing the **Layer Properties** window for MapUnitPolys, go to the **Display** tab and set **Transparent:** to 50% 
4. While still viewing the **Layer Properties** window, you might wish to click the **Labels** tab, check the box **Label features in this layer**, and set **Label Field:** to MapUnit

*These colors and labels are convenient kludges. Eventually you will [assign Symbol values to each polygon with the Set Symbol Values script and color using these values](https://github.com/usgs/GeMS_Tools/wiki/MakeColorPolygons#match-symbol-to-style). Labels will be explicitly calculated and stored, so that we add queries (“?”) to labels for polygons with IdentityConfidence = questionable. You will get a better map graphic if you then convert these labels to annotation so that they can be precisely positioned.*

#### e. Save your work

1. **Editor**▼> **Save Edits**. **Editor**▼> **Stop Editing**
2. **SAVE** .mxd 
3. [Compact and back up](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#compact-and-back-up)

#### f. Repeat steps a-e until area is mapped

### 6. CMU and DMU

What are your map units? What are their relations to each other, by age, facies, or otherwise? 

Before you can check the details of map topology (beyond what ArcGIS can natively do), or set final map-unit symbolization and labels, it helps to partly complete the DescriptionOfMapUnits table (DMU). The CorrelationOfMapUnits diagram (CMU), represented in GeMS as a separate feature dataset, corresponds closely to the DMU; most of us find it easier to sketch out the CMU before tackling the DMU. 

[Follow this link](https://github.com/usgs/GeMS_Tools/wiki/CMUandDMU) for advice on building a CMU and DMU. While you need not complete the DMU at this time, you do need a row for each unit on your map with values of MapUnit, Name, Label, and HierarchyKey. 

### 7. Topology Check

Run the **Topology Check** script on your database.  [Follow this link for further instructions](https://github.com/usgs/GeMS_Tools/wiki/TopologyCheck). Use these inputs:

​	**Geodatabase**:  *ThisProject*.gdb	

​	**Validate topology of all feature datasets (optional)**:   unchecked (default)

​	**Validate topology of specified datasets (optional)**:  no entries

​	next 5 check boxes: checked (default)

​	**Identify short lines, small polys, and sliver polys**: uncheck

​	**Map scale denominator**: 20000

​	minima for line length, poly area, and poly width: accept defaults

​	**Force exit with error**: unchecked (default)

### 8. Symbolization and Labeling

At this point your lines may be symbolized primarily via **LTYPE** and your map-unit polys are colored and labled by **MapUnit**. The GeMS default is that all features are symbolized on Symbol, and that MapUnit polys are labeled with **Label**.  [Follow this link for instructions](https://github.com/usgs/GeMS_Tools/wiki/SymbolsAndLabels). 

### 9. [Complete metadata](https://github.com/usgs/GeMS_Tools/wiki/CompleteMetadata) 

### 10. Finalize database

​Has the DMU been revised? If yes, insert new values (name, fullname, description, ...). Has unit hierarchy changed? Fix HierarchyKey values. 	

Then follow instructions to [finalize your database](https://github.com/usgs/GeMS_Tools/wiki/FinalizeDatabase).