Transcribing an existing analog map is similar to [making a new map](https://github.com/usgs/GeMS_Tools/wiki/MakeNewGeomorphicMap) (heads-up digitizing). but without the need to think about earth history. And it is similar to translating an existing digital map in that most of the text material (map-unit descriptions, Type definitions) can be copied and pasted, perhaps with a bit of OCR thrown in. 

### 1. Inventory the map

What feature classes will you need? Are there any cross sections? Will you digitize a *Correlation of Map Units* diagram, or save it as an image file?  Make a list of the database elements you will need. 

Does the *Explanation of Symbols* accurately reflect the kinds of features on the map, or will you have to add other feature types? If you will need additional feature types, note them. 

Where do map unit descriptions reside? Are they on the map sheet, in a separate pamphlet, or missing? Are they available as machine-comprehensible text, or will you need to feed an image of the text to Optical Character Recognition (OCR) software?  

If OCR is in order, do you have OCR software?  It may be available to you in Adobe Acrobat, or perhaps it was bundled with your all-in-one printer driver.  If you need OCR software and don't have it, search the web. Free stuff (may mean lots of ads) is available. 

### 2. Start ArcMap, select reference map and projection, create empty database

1. Make a new folder for this project if you haven't done so already. See [Hard Drive Hygiene](https://github.com/usgs/GeMS_Tools/wiki/HardDriveHygiene)

2. [Configure ArcMap](https://github.com/usgs/GeMS_Tools/wiki/ConfigureArcMap), if you haven't already

3. Is your geologic-map image registered or not?

   1. If yes (for example, you have downloaded a GeoTiff from [NGMDB MapView](https://ngmdb.usgs.gov/mapview/)), add the registered geologic map image to your map composition (which will set the dataframe projection) and skip to step b.3

   2. If not, to what will you georeference the map image? (I do not recommend generating tics.) *For small areas (a 7.5' quad), the choice of projection at this step is generally not critical: using the right UTM zone is good enough. For larger areas (a 1:250,000-scale map), you should register the map image to a base that is in the same projection as the map image* 

      1. Georeference to the topographic map that matches (or a map that is similar to) the geologic map:

         Go to [NGMDB TopoView](https://ngmdb.usgs.gov/topoview/viewer/#4/40.01/-99.93). Navigate to your area, zoom in, filter/search as needed, and select a map. Download the GeoTiff version. Unzip. Add the map to your map composition. This will set the dataframe projection to something appropriate, give you lots of registration points, and provide a base map

      2. Georeference to something else, perhaps one of Esri's base maps available via **Add Data▼** > **Add Basemap...**

         Add the basemap of choice to your map composition. Is Web Mercator a suitable projection for your geologic map? (Probably not if it is a small-scale map that covers a large area)

         1. If yes, go to step b.3
         2. If not, right-click somewhere in the map window, select **Data Frame Properties...**, and go to the **Coordinate System** tab. Select an appropriate map projection. **OK**

4. Run the GeMS Tools [Create New Database](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#CreateNewDatabase) script.  For **Spatial reference system**, click on the select button (finger pointing to list, at right), expand the **Layers** option and take the offered choice. Add any optional feature classes, tables, and feature datasets you identified when you inventoried the map.  You probably don't need edit tracking. Check **Add LTYPE and PTTYPE**. Leave **Add standard confidence values** checked

5. **Save**

### 3. Create templates for map features 

Create a library of feature templates that correspond to the feature types present in the map you are transcribing. You should be able to use the *Explanation of Symbols* on the map as a guide to what you need. 

1. Add the ContactsAndFaults feature class from your new database to your map composition. Right-click on the new layer and select **Edit Features** > **Start Editing**. Go to **Create Features** window. If it is not available, **Editor▼** > **Editing Windows** > **Create Features**.

   ![1525556785636]  (C:\Users\rhaugerud\Code\GeMS_Tools.wiki\WikiImages\CreateFeatures1.png)

   Right-click on the ContactsAndFaults template and select Copy. Double-click on the newly-created template. 

   ![1525556841629](C:\Users\rhaugerud\Code\GeMS_Tools.wiki\WikiImages\TemplatePropertiesCopy.png)

   Edit these properties. Set **Name:** to a line type (for example, "fault, concealed", or "approximate contact") in the map you are transcribing. Set **LTYPE** to the same value. I find it helpful to pick names that alphabetize into an easily-comprehended order. 

   Set as many of the GeMS attributes as you can: if the LTYPE is "fault" and this is a 1:24,000-scale map, Type = "fault", IsConcealed = "N", LocationConfidenceMeters = "24", ExistenceConfidence = "certain", IdentityConfidence = "certain".  Symbol = "02.01.01". DataSourceID might be "USGS I-854B" (if you are transcribing USGS I-854B). 

   Repeat until you have made templates for all the varieties of line identified in the map explanation that will be transcribed into ContactsAndFaults.

   Using these templates, digitize lines, one line for each template. These can be arbitrary, bogus lines that you soon delete, or--if convenient--lines present on the source map that you will keep.

   Open the **Layer Properties** window for the ContactsAndFaults layer. Go to the **Symbolization** tab, and under **Show:** select **Categories - Unique values**. Set the **Value** Field to LTYPE. **Add All Values**.  For each row, double-click on the symbol shown and change it to something useful. This will reset the Drawing Symbol in the feature template. 

   If your lines were bogus, select and delete them. 

2. Ditto GeologicLines, GeochronPoints, etc., as necessary

   Make templates for each feature class into which you will be digitizing feature, following the steps above.

   OrientationPoints gets one more step.  In the **Layer Properties** window, at the **Symbolization** tab, hit the **Advanced▼** dropdown, select **Rotation...**, and set **Rotation Style:** to **Geographic** and **Rotate Points by Angle in this field:** to Azimuth. 

3. No templates for MapUnitPolys

   Because we won't digitize polygons directly. Rather, we will construct them from ContactsAndFaults lines. 

4. **Save** .mxd

### 4. Heads-up digitize, making polys as you go

See steps [5b](https://github.com/usgs/GeMS_Tools/wiki/MakeNewGeomorphicMap#b.-digitize-contacts), [5c](https://github.com/usgs/GeMS_Tools/wiki/MakeNewGeomorphicMap#c.-check-topology), and [5d](https://github.com/usgs/GeMS_Tools/wiki/MakeNewGeomorphicMap#d.-make-and-color-polygons) in [MakeNewGeomorphicMap](https://github.com/usgs/GeMS_Tools/wiki/MakeNewGeomorphicMap). 

Save your work! 

1. **Editor**▼> **Save Edits**
2. **Editor**▼> **Stop Editing**
3. **Save** .mxd 
4. [Compact and back up](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#compact-and-back-up)

### 5. Set DataSourceIDs and DataSources entry

If you have not [set DataSourceID values with feature templates](#c.-create-templates-for-map-features), start editing, open feature attribute tables, and use the Field Calculator to set DataSourceID (and OrientationSourceID, AnalysisSourceID, etc.) values.   

Table DataSources will probably have only one entry. **DataSources_ID** should correspond to the DataSourceID you gave to map features. **Source** should be a complete reference to the map you are transcribing.  **Notes** should include a statement *Transcribed by yourname from a georeferenced image of the source map, with RMSE = xx meters.*  State that you assigned LCM values, and why you chose the values you did.  If you chose to not transcribe certain classes of features (isograds, borrow pits), state which classes of features you did not transcribe. 

### 6. [CMU and DMU](https://github.com/usgs/GeMS_Tools/wiki/CMUandDMU)

### 7. [Topology Check](https://github.com/usgs/GeMS_Tools/wiki/TopologyCheck)

### 8. [Complete metadata](https://github.com/usgs/GeMS_Tools/wiki/CompleteMetadata)

### 9. [Finalize database](https://github.com/usgs/GeMS_Tools/wiki/FinalizeDatabase)