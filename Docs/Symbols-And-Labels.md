The GeMS default is that all features are symbolized on Symbol and that MapUnit polys are labeled with **Label**.  One can automate the placement of dip and inclination numbers. 

These instructions cover the standard GeMS feature classes ContactsAndFaults, GeologicLines, MapUnitPolys, and OrientationPoints in the GeologicMap feature dataset. Use your judgment and imagination to extend the instructions to other feature classes and other feature datasets. 

### a. Supply missing Type, MapUnit, and confidence values

Step through ContactsAndFaults, MapUnitPolys, GeologicLines (if present), and OrientationPoints (if present). For each feature class,

1. If necessary, **Edit Features** > **Start Editing**
2. **Open Attribute Table**
3. For attributes Type, MapUnit, IdentifyConfidence, ExistenceConfidence, LocationConfidenceMeters, and OrientationConfidenceDegrees:
   1. If attribute is present in the feature class, right-click on column header and **Sort Ascending** 
   2. If empty or null values are present, fill them in appropriately. This may require a bit of sleuthing
4. **Editor**▼> **Save Edits**

### b. Run **Set Symbol Values** script

The GeMS_Tools [**Set Symbol Values**](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#SetSymbolValues) script calculates scale- and confidence-appropriate values of Symbol that reference the GSC  and Alaska DGGS implementations of the FGDC digital geologic map symbolization standard. It works on feature classes ContactsAndFaults, GeologicLines, and OrientationPoints. If **Set polygon symbols and labels** is checked, the script will also assign values of Symbol and Label defined in the DMU table to each polygon in MapUnitPolys and append "?" to labels of polygons with IdentityConfidence = "questionable".  

If **Set Symbol Values** finds unrecognized Type values, you may either:


   1. Edit  your local copy of **Type-FgdcSymbol.txt** (in the **Resources** folder of your **GeMS_Tools** folder) to include additional Type values and corresponding FGDC symbol identifiers, then re-run **Set Symbol Values**, or
   2. Add missing Symbol values by hand-editing the relevant feature class attribute table

### c. If feature class OrientationPoints is present and has rows 

1. Run GeMS_Tools script [**Set PlotAtScale Values**](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#SetPlotAtScaleValues). Once you have run this script, you may add a definition query to the OrientationPoints feature class:

    `[PlotAtScale] >= MapScale`

   This will thin any too-close bedding, foliation, joint, etc, features to a density appropriate for the given map scale

2. Run the GeMS_Tools [**Inclination Numbers**](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#InclinationNumbers) script. **Inclination Numbers** assumes that values of PlotAtScale exist and are appropriate! The script will 
   1. Create a new point feature class OrientationPointLabels with attributes OrientationPointsID, Inclination, and PlotAtScale. All of these are taken from OrientationPoints. Positions for these points are taken from the corresponding OrientationPoints position with an offset that is calculated from the map scale, Azimuth (in OrientationPoints), and whether the point corresponds to a linear (lineation, fold axis) or planar (bedding, foliation) feature. Points are not created for OrientationPoints features with Type values that contain "horizontal" or "vertical"
   2. Creates and installs a layer that symbolizes these dip and plunge numbers

### d. You may wish to reset symbolization for your map document

Symbolization and labeling as described here are likely more appropriate for a publication graphic than for editing the database. Thus your next step may be, while your .mxd for editing (*ThisProject-edit.mxd*) is open in ArcMap, to **Save As...** *ThisProject-publication.mxd*. 

   1. For ContactsAndFaults, add a new layer to your map composition
      1. **Add Data**, ContactsAndFaults from *ThisProject.gdb/GeologicMap*
      2. On the new ContactsAndFaults layer, right-click and select **Properties...**
      3. On the **Symbolization** tab, under **Show:**, select **Categories**, **Match to symbols in a style**. Set **Value Field** to Symbol. Under **Match to symbols in Style**, select (or **Browse...** to) USGS Symbols2.style. Click **Match Symbols**. **OK** to exit the Layer Properties window 
      4. You can now choose to symbolize on multiple attributes (ContactsAndFaults14k.lyr group) or with publication symbology  (the new ContactsAndFaults layer). Or both, which is ugly

   2. If you have a GeologicLines layer, make similar changes 

   3. Right-click on MapUnitPolys layer and select **Properties...**
      1. On the **Symbology** tab, **Show:**, select **Categories, Match to symbols in a style**. Set **Value Field** to Symbol.  Under **Match to symbols in Style**, select (or **Browse...** to) USGS Symbols2.style. Click **Match Symbols**
      2. For labels, you have some choices
         1. On the **Labels** tab of the **Layer Properties** window, check **Label features in this layer**. Set **Label Field:** to Label. Make any changes to **Placement Properties...**, **Scale Range...**, etc.) you think necessary. **OK** to exit. *Or*
         2. Add a new MapUnitPolys layer to your map composition. Rename the layer to MapUnitPolys--labels. In **Layer Properties** window, on the **Symbology** tab, **Show:** **Features Single Symbol**. Set the symbol to no color, no border color, border width = 0. On the **Labels** tab, check the box and set **Label Field:** to Label.  Go to the **Definition Query** tab and build a query that selects polys with Shape_Area larger than some minimum value. **OK**
         3. Add multiple MapUnitPolys--labels layers. (Group them.)  Set different definition queries for each layer so that as you zoom in more and more polys are labeled. 

4. If there are rows in feature class OrientationPoints:
   1. On the OrientationPoints layer, right-click and select **Properties...**
   2. On the **Symbolization** tab, under **Show:**, select **Categories**, **Match to symbols in a style**. Set **Value Field** to Symbol. Under **Match to symbols in Style**, select (or **Browse...** to) USGS Symbols2.style. Click **Match Symbols**
   3. Set symbol rotation. Still on the **Symbolization** tab, at the lower right, click on **Advanced▼**> **Rotation...** to open the **Rotate** window. Ensure that **Rotation Style:** is **Geographic**. Set **Rotate Points by Angle in this field:** to Azimuth. **OK** to exit the **Rotate** window
   4. **OK** to exit the Layer Properties window 

5. **Save**

  ​    