Polygon boundaries should be coincident with ContactsAndFaults arcs.  The easiest (in my experience) way of guaranteeing this is to create polygons from these arcs. Polys may be [built and attributed piecemeal as you digitize](#BuildAsYouGo) (when making a new map), or [in bulk](#BulkBuild) (when translating a digital data set, or at the end stages of a digitizing effort). You may know another path that works better. 

Once polygons are created, it is initially easiest to [color them by MapUnit](#ColorByMapUnit). When the map is nearly finished, switch to [coloring by Symbol](#ColorBySymbol). After you have some attributed, colored polys, you can propagate their MapUnit and color attributes to other polys by [merging and exploding](#MergeExplode). 

##### <a name="BuildAsYouGo"></a>Build and tag polys as you go

Perhaps the most useful. You must have a layer that exposes ContactsAndFaults in your map composition, such as the layer group supplied by ContactsAndFaults 24k.lyr. You also need to have a MapUnitPolys layer in your map composition, and both CAF and MUP must be visible. Right-click the LTYPE (or equivalent) layer and select  **Edit Features** > **Start Editing**.

1. Digitize arcs that bound one or more polygons-to-be. Easiest to use the LTYPE templates supplied with ContactsAndFaults24k.lyr, or similar templates that you or your colleagues have created. It may be helpful to break long arcs that bound many polys--especially loop arcs, like the map boundary--into two or more pieces to avoid building of redundant polys whenever you use those arcs 
2. Select (with the Edit Tool on the Editor toolbar) arcs that bound one or more polygons-to-be
3. Tap the Construct Polygons button (wrench over a white square) on the **Advanced Editing** toolbar. This will make polygons
4. If you inadvertently create polygons you don't intend, delete them
5. As you make polys, select each with the Edit Tool, if necessary right-click to open the Attributes window, and type in an appropriate MapUnit value. I generally leave IdentityConfidence blank at this stage unless is should be "questionable"

##### <a name="BulkBuild"></a>Build polys in bulk

The ArcMap **Feature To Polygon** tool builds polys in bulk and can use label points to provide attributes, similar to the way polygons are created in Workstation ArcInfo. The GeMS [Make Polygons](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#MakePolygons) script provides a wrapper to this tool. 

[Make Polygons](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#MakePolygons) uses all ContactsAndFaults arcs, propagates the identities of any existing polys in MapUnitPolys, and can incorporate a label points feature class. It generates additional feature classes of polys with multiple, conflicting label points, unlabelled polys, and polys whose value of MapUnit changed when polygons were rebuilt (perhaps because line topology had changed). 

Once the Make Polygons script has run, search for polys with an empty value of MapUnit, select each with the Edit Tool, right-click to bring up the Attribute window, and enter MapUnit. Or select many polys that should have the same MapUnit value, open the MapUnitPolys attribute table, and use the Field Calculator to calc MapUnit. 

##### <a name="ColorByMapUnit"></a>Color polygons by Categories using MapUnit

In the initial stages of creating a map I find it most useful to color MapUnitPolys by Categories/Unique values using MapUnit. This simultaneously creates a Table of Contents that informs you of the color-MapUnit relation.

1. Right-click on MapUnitPolys and select Properties…
2. In the Layer Properties window, select the Symbology Tab 
3. At the left Show: pane of the Layer Properties window, select Categories/Unique values. 
4. Set Value Field to MapUnit 
5. Add All Values 
6. Adjust colors (double-click on each color box) as appropriate. Best to use fill colors without a border: select border, set width to 0.0 and color to No Color

##### <a name="ColorBySymbol"></a>Color polygons by categories using Symbol values from DMU

Run Set Symbol Values (must have partial DMU)

Set layer symbolization

##### <a name="MergeExplode"></a>Merge new polygon with existing non-adjacent polygon and explode

You can transfer attributes to a polygon by merging it with an attributed polygon and then exploding the resulting compound polygon.

1. With the Edit Tool, select one or more un- (or mis-) attributed polygon and a source polygon whose attributes you wish to copy.
2. On the Editor toolbar, tap **Editor▼** dropdown and select **Merge...**
3. In the **Merge** window, select the correct poly to which other features will be merged
4. **OK**
5. Tap the **Explode Multi-part Feature** button on the Advanced Editing toolbar