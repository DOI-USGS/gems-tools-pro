The GeMS **[Topology Check](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#TopologyCheck)** script examines topological aspects of a geologic map database that cannot be checked with standard topology tools in ArcGIS. As a convenience it also incorporates some standard topology checks.  

The script generates an HTML report (*ThisProject*.gdb-TopologyReport.html) and a geodatabase *ThisProject*-errors.gdb. Look at both. 

To your map composition (ThisProject-edit.mxd), add these feature classes from database ThisProject-errors.gdb/GeologicMap:  

- ContactsAndFaults_MUPid
- dups_*PointFeatureClass*, could be as many as one per each point feature class in the dataset

- errors_BadNodes
- errors_GeologicMapTopology_point
- errors_GeologicMapTopology_line
- errors_GeologicMapTopology_poly
- errors_SgirtARcs
- errors_SkinnyPolys
- errors_SmallPolyPoints
- errors_SmallPolys

Names may be different if feature datasets other than GeologicMap are evaluated. If any of these are not present in the XXX-errors database, congratulations!  

Work through the following. Some errors may show up under several headings: don't be surprised that once you've fixed some line or polygon topology errors the map-unit adjacency errors are no longer relevant. You may want to save edits, stop editing, and re-run [Topology Check](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#TopologyCheck) to refresh the lists of things to fix. 

#### a. Line, polygon, and point topology errors

Expect to find one line error around the edge of the map. Ignore it.  Other errors need to be fixed. 

#### b. Node geometry (errors_BadNodes)

Change symbolization of errors_BadNodes to a large, light-colored spot without a border. Place it (in Drawing-order view) beneath ContactsAndFaults.  If you have a reference scale set for this data frame (on ArcMap toolbar, **View** > **Data Frame Properties...** > **General** tab), change it to &lt;none&gt;. 

Right-click on errors_BadNodes and **Open Attribute Table**. If there are more than a few rows, you may find it useful to sort the table on **NodeStatus**, then **ArcType** (right-click on the **NodeStatus** header and select **Advanced Sorting...**). 

Your task is to work through errors_BadNodes, fixing each problem identified or convincing yourself (and eventually your map editor) that the identified problem is actually OK. 

1. Right-click on ContactsAndFaults--LTYPE, **Edit Features** > **Start Editing** 
2. Go to the first line in the errors_BadNodes attribute table, click on the selection box at the left edge of the first row to highlight the row, and right-click **Pan To** or right-click **Zoom To**
3. Line overshoot and undershoots can be readily dealt with by Trim and Extend tools on the Advanced Editing toolbar. If a line is misplaced and needs moving:
   1. Is this your line (it won't need a new DataSourceID value if you move it)? Double-click on the line to Edit Vertices and move/add/delete vertices as needed
   2. Is this a line from another source? Best to digitize a new, intersecting line, then grab old and new lines, Planarize Lines (Advanced Editing toolbar), and delete the unneeded parts
4. Does polygon geometry need to change to match the revised linework? Use Split Polygons (Advanced Editing toolbar) to divide the old poly(s). Then select polys to be joined and **Editor ▼ Merge**
5. **Editor**▼> **Save Edits**

#### c. Fault direction (errors_FaultDirNodes)

Fault arcs are commonly broken as they change from concealed to unconcealed, or become more or less well located, or have different DataSourceIDs.  But, especially for ornamented (thrust teeth, bar-and-ball, etc.) fault arcs for which we use directionality to control which side the ornament is on, the direction should remain the same.  Errors_FaultDirNodes identifies fault-arc junctions where the directionality does not change, that is, both fault-arc ends at that point are TO, or FROM, instead of the one TO and one FROM that we expect.  

Not all of the nodes identified in errors_FaultDirNodes are truly errors. 

1. Where three fault arcs meet (a T or Y, one fault truncated by another), at least two of the nodes must be TO or FROM and this generates a point in errors_FaultDirNodes. This is not an error, unless it is the wrong arcs that are both TO or FROM. Three arcs that are all TO or all FROM are probably an error
2. Representation of a scissors fault along which the down-thrown direction changes requires a node where both fault-arc directions are TO or both are FROM

Add errors_FaultDirNodes to your map composition. Open the attribute table. Work through it, checking each identified node to see if one of the fault arcs that meet there need to be flipped. Flipping one arc may require flipping one or more additional arcs farther along the fault.  

**Editor**▼> **Save Edits**

#### d. Map Unit adjacency (tables in xx_TopologyReport.html)

Contacts, faults, and map-unit polygons should follow several rules:

- Concealed contacts and faults should have the same map unit on each side. 
- As a matter of practice many geologic map publishers don't draw internal contacts (e.g., one landslide against another, though this may be the most common exception). 
- If there are no lateral, facies-dependent map-unit boundaries (e.g., wetland against alluvium), no intrusions, and no lithodemic units, map units should only be in unfaulted contact with immediately older and younger units, unless there are significant unconformities. 
- We generally don't expect to see many faults cutting young map units. 

Inventories of contact and fault arcs categorized and organized by their adjacent map units readily disclose violations of these rules. ThisProject.gdb-TopologyReport.html contains 3 such inventories. 

- Table **Concealed contacts and faults** should only have entries along the diagonal
- Table **Contacts (not concealed)** should have NO entries along the diagonal, unless the author/editor/publisher choose to allow internal (within map-unit) contacts
- Table **Faults (not concealed)** should have few entries in the upper left (young against young) corner

If you see problems, fix them. I find it easiest to locate internal contacts with a selection (*LEFT_MapUnit = RIGHT_MapUnit*) on ContactsAndFaults_MUPid.  Mistaken concealed contacts (off diagonal entries in Concealed contacts and faults) can be located with *LEFT_MapUnit <> RIGHT_MapUnit AND IsConcealed = 'Y'*. Too-young faults can be found with *Type IN ('fault', 'normal fault', ...) AND LEFT_MapUnit = 'XX' AND RIGHT_MapUnit = 'YY'*, where values of XX and YY are read from the **Faults (not concealed)** table. 

**Editor**▼> **Save Edits**. **Editor**▼> **Stop Editing**. 

#### e. Duplicate point features

Some workflows make it easy to duplicate point features. These are errors and should be fixed. In other cases (multiple samples at a single station, or multiple analyses of a single sample), coincident point features with the same Type values are common and are not errors. Check any dup_*pointFeatureClass* classes to see what you have. Fix problems. 

#### f. Small feature inventory

Small features are not necessarily a violation of geologic map logic. However, they can signify digitizing errors. Because they reduce the readability of the map graphic, some agencies have editorial standards that dictate that polygons be larger, or wider, than some minimum size.  

What are your standards?  Does reconnaissance of the errors_SmallXXX feature classes indicate digitizing problems that need to be fixed?

#### f. Repeat until done

Re-run [Topology Check](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#TopologyCheck) and fix errors until you are satisfied your database is clean. 