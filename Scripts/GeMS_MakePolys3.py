import arcpy
import sys
from pathlib import Path
import GeMS_utilityFunctions as guf

"""
Parameters
----------
fds : Path to feature dataset that contains ContactsAndFaults and MapUnitPolys feature 
    classes. Required
save_mup : Save a copy of the existing MapUnitPolys? Boolean, optional, false
    by default
label_points : path to feature class of points to be used for polygon attributes
    optional. If provided, will always be favored over points generated within
    polygons by feature to point tool  .
simple_mode : Use simple mode or reporting mode. Boolean, true by default. Use
    simple_mode for speed. New polygons will be constructed from lines and 
    label_points (if provided) with no error reporting. Reporting mode will,
    additionally, check for polygons that have more than one label_point, 
    MapUnitPolygons where MapUnit is Null, and find polgyons where MapUnit has 
    changed. The result, if any of the above are found, will be a group layer
    in the map with relevant feature layers created from definition queries on 
    existing feature classes; label_points that are redundant (more than one
    found in a polgyon), polygons that contain those multiple points, polygons
    where MapUnit = Null, and polgyons where MapUnit has changed. Reporting mode
    can take a long time but might be useful in large maps with conmplicated, 
    convoluted polygon boundaries.
"""

versionString = "GeMS_MakePolys3.py, version of 24 June 2022"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_MakePolys3.py"
guf.checkVersion(versionString, rawurl, "gems-tools-pro")

debug = False

guf.addMsgAndPrint(versionString)


def sql_list(var):
    """
    Parameters
    ----------
    var : set, tuple, or list
        List of integers (OBJECTIDs)

    Returns
    -------
    string or tuple
        Multiple-item tuples evaluate as (i1, i2, i3) which can be used in an
        SQL query without error. One-item tuples, however, evaluate as (i1,)
        (the one item with a trailing comma), which throws an error in SQL.
        This function returns a string for one-item tuples (or lists or sets)
        and a tuple for multiple-item lists or sets
    """
    var = list(var)
    if len(var) > 1:
        return tuple(var)
    else:
        n = var[0]
        return f"({n})"


fds = sys.argv[1]
gdb = Path(fds).parent
save_mup = False
if sys.argv[2].lower() == "true":
    save_mup = True

try:
    label_points = arcpy.da.Describe(sys.argv[3])["catalogPath"]
except:
    label_points = ""

simple_mode = True
if sys.argv[4].lower() in ["false", "no"]:
    simple_mode = False

# get caf, mup, name_token
# dictionary
fd_dict = arcpy.da.Describe(fds)
children = fd_dict["children"]

# ContactsAndFaults
caf = [
    child["catalogPath"]
    for child in children
    if child["baseName"].lower().endswith("contactsandfaults")
][0]
short_caf = Path(caf).name

# MapUnitPolys
mup_dict = [
    child for child in children if child["baseName"].lower().endswith("mapunitpolys")
][0]
mup = mup_dict["catalogPath"]
mup_fields = mup_dict["fields"]
short_mup = Path(mup).name

# feature dataset name token
fd_name = fd_dict["baseName"]
if fd_name.lower().endswith("correlationofmapunits"):
    name_token = "CMU"
else:
    name_token = fd_name

# save a copy of MapUnitPolys
## saving a copy also saves a copy of any relationship classes
if save_mup:
    arcpy.AddMessage("Saving MapUnitPolys")
    arcpy.management.Copy(mup, guf.getSaveName(mup))

# make selection set without concealed lines
fld = arcpy.AddFieldDelimiters(caf, "IsConcealed")
where = f"LOWER({fld}) NOT IN ('y', 'yes')"
arcpy.AddMessage("Selecting all non-concealed lines")
contacts = arcpy.management.SelectLayerByAttribute(caf, where_clause=where)

# make new polys
new_polys = r"memory\mup"
if simple_mode:
    arcpy.AddMessage("Continuing in simple mode")
    # simple mode is for speed. EITHER label_points or existing polygons will
    # be used for attributes of new polygons. No reconciliation or error reporting
    if label_points:
        arcpy.AddMessage("Using label points source in simple mode")
    else:
        arcpy.AddMessage("Using existing polygon attributes in simple mode")
        label_points = rf"memory\{short_mup}_labels"
        # Feature to point adds a ORIG_FID to table but it will be not be
        # added to the final output if Append is used.
        arcpy.management.FeatureToPoint(mup, label_points, "INSIDE")

    arcpy.AddMessage("Building new map unit polygons in memory")
    arcpy.management.FeatureToPolygon(contacts, new_polys, label_features=label_points)

    # truncate MapUnitPolys
    arcpy.AddMessage(f"Emptying {short_mup}")
    arcpy.management.TruncateTable(mup)

    # append to the now empty MapUnitPolys
    arcpy.AddMessage(f"Adding features from memory to {mup}")
    arcpy.management.Append(new_polys, mup, "NO_TEST")

else:
    arcpy.AddMessage("Continuing in reporting mode")
    # in reporting mode
    # 1) turn map unit polygons into points - adds ORIG_FID
    # 2) merge with optional label point - adds MERGE_SRC
    # 3) create polgyons from the lines, no attributes
    # 4) Run Identity with empty polygons and all merged labels - adds FID_ for
    #   label points and polys
    # 5) if there is a mup point and a label point in any polygon, choose the
    #    label point
    # 6) build new MapUnitPolys
    # 7) report multiple label points
    # 8) report polygons with those extra points
    # 9) report changed polygons
    # 10) report polygons that have no MapUnit value

    # turn map unit polygons into points - adds ORIG_FID
    orig_mup_labels = rf"memory\{short_mup}_labels"
    arcpy.management.FeatureToPoint(mup, orig_mup_labels, "INSIDE")

    # merge with optional label point - adds MERGE_SRC
    filter_from_labels = []
    extra_labels = []
    if label_points:
        arcpy.AddMessage("Organizing label points")
        # make a copy in memory in order to add ORIG_FID
        # used later to identify multiple labels in a single polygon
        out = r"memory\labels_copy"
        labels_copy = arcpy.management.CopyFeatures(label_points, out)
        arcpy.management.AddField(labels_copy, "ORIG_FID", "LONG")
        arcpy.management.CalculateField(labels_copy, "ORIG_FID", "!OBJECTID!")

        # merge with the feature-to-point points
        merge_labels = r"memory\merge_labels"
        arcpy.management.Merge(
            [orig_mup_labels, labels_copy], merge_labels, add_source="ADD_SOURCE_INFO"
        )

        # make polygons from selected contacts. these will be empty but are needed
        # in order to reconcile multiple label points
        empty_polys = r"memory\empty"
        arcpy.management.FeatureToPolygon(contacts, empty_polys)

        # intersect with the merged label points
        inter_points = r"memory\inter_points"
        arcpy.analysis.Intersect([empty_polys, merge_labels], inter_points)

        # find duplicate FID_empty; polygons that intersected with multiple points
        # keep a list of oids of feature-to-points that are found in a polygon
        # along with label_points; prioritize label_points by removing co-located
        # feature-to-points
        FIDs = [row[0] for row in arcpy.da.SearchCursor(inter_points, "FID_empty")]
        dup_FIDs = list(set([x for x in FIDs if FIDs.count(x) > 1]))
        for FID in dup_FIDs:
            exp = f"FID_empty = {FID}"
            with arcpy.da.SearchCursor(
                inter_points, ["ORIG_FID", "MERGE_SRC"], exp
            ) as cursor:
                # list of ORIG_IDs to exclude from the feature-to-points
                for row in cursor:
                    if row[1] == orig_mup_labels:
                        filter_from_labels.append(row[0])

            # extra labels
            exp = f"FID_empty = {FID} and MERGE_SRC = '{out}'"
            selected = arcpy.management.SelectLayerByAttribute(
                inter_points, where_clause=exp
            )
            if int(arcpy.management.GetCount(selected)[0]) > 1:
                extra_labels.extend(
                    [r[0] for r in arcpy.da.SearchCursor(selected, "ORIG_FID")]
                )

        # remove extra labels from merge_labels
        with arcpy.da.UpdateCursor(merge_labels, ["ORIG_FID", "MERGE_SRC"]) as cursor:
            for row in cursor:
                if row[0] in filter_from_labels and row[1] == orig_mup_labels:
                    cursor.deleteRow()

        # make new polygons based on the contacts and this new set of label points
        arcpy.management.FeatureToPolygon(
            contacts, new_polys, label_features=merge_labels
        )
    else:
        arcpy.management.FeatureToPolygon(
            contacts, new_polys, label_features=orig_mup_labels
        )

    # make a copy in memory in order to look for changed polys later
    old_polys = r"memory\old_polys"
    arcpy.management.CopyFeatures(mup, old_polys)

    # truncate MapUnitPolys
    arcpy.AddMessage(f"Emptying {short_mup}")
    arcpy.management.TruncateTable(mup)

    # append to the now empty MapUnitPolys
    arcpy.AddMessage(f"Adding features from memory to {mup}")
    arcpy.management.Append(new_polys, mup, "NO_TEST")

    arcpy.AddMessage("Looking for errors and changes")
    # do we need to build report layers?
    # look for null values
    mup_oid = mup_dict["OIDFieldName"]
    null_vals = [
        row[0]
        for row in arcpy.da.SearchCursor(mup, [mup_oid, "MapUnit"])
        if row[1] in (None, "", " ")
    ]

    # look for multiple label points in the new polygons
    mup_inter_labels = r"memory\mup_inter_labels"
    arcpy.analysis.Intersect([mup, label_points], mup_inter_labels)
    oids = [
        row[0] for row in arcpy.da.SearchCursor(mup_inter_labels, f"FID_{short_mup}")
    ]
    dup_oids = set([x for x in oids if oids.count(x) > 1])

    # look for changed polygons
    inter_polys = r"memory\inter_polys"
    arcpy.analysis.Intersect([old_polys, mup], inter_polys)
    changed = []
    with arcpy.da.SearchCursor(
        inter_polys, [f"FID_{short_mup}", "MapUnit", "MapUnit_1"]
    ) as cursor:
        for row in cursor:
            if row[1] != row[2] and row[1] not in [None, ""]:
                changed.append(row[0])

    # look for contacts with the same MapUnit on either side
    inter_lines = r"memory\inter_lines"
    arcpy.analysis.Identity(caf, mup, inter_lines, relationship="KEEP_RELATIONSHIPS")
    id_field = f"FID_{str(short_caf)}"
    same_unit = []
    with arcpy.da.SearchCursor(
        inter_lines, [id_field, "left_mapunit", "right_mapunit"]
    ) as cursor:
        for row in cursor:
            if row[1] == row[2]:
                same_unit.append(row[0])

    if null_vals or extra_labels or dup_oids or changed or same_unit:
        # build report feature layers
        arcpy.AddMessage("Preparing report layers")

        # prepare group layer
        # get the active map
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        active_map = aprx.activeMap

        for l in active_map.listLayers():
            if l.longName == "Make Polys - Report Layers":
                active_map.removeLayer(l)

        # find genericgroup.lyrx in the \Scripts folder
        this_py = Path(__file__)
        scripts = this_py.parent
        group_lyr = scripts / "genericgroup.lyrx"

        # add it to the map and rename it
        group = active_map.addDataFromPath(str(group_lyr))
        group.name = "Make Polys - Report Layers"

        # add report layers
        # multiple label point polygons
        # just testing for boolean(True) of lists seemed to miss them so we'll
        # test for length > 0
        if len(extra_labels) > 0:
            arcpy.AddMessage("Creating extra labels layer")
            exp = f"OBJECTID in {sql_list(extra_labels)}"
            extras = arcpy.management.MakeFeatureLayer(
                label_points, "Extra label points", exp
            )[0]
            active_map.addLayerToGroup(group, extras)

        # the polygons where those extra labels are found
        if len(dup_oids) > 0:
            arcpy.AddMessage("Creating layer for polygons with extra labels")
            exp = f"OBJECTID in {sql_list(dup_oids)}"
            poly_layer = arcpy.management.MakeFeatureLayer(
                mup, "Polygons with extra labels", exp
            )[0]
            active_map.addLayerToGroup(group, poly_layer)

        # polygons that don't have a MapUnit value
        if len(null_vals) > 0:
            arcpy.AddMessage("Creating layer for polygons with no MapUnit value")
            exp = f"OBJECTID in {sql_list(null_vals)}"
            null_polys = arcpy.management.MakeFeatureLayer(
                mup, "Polygons with no MapUnit", exp
            )[0]
            active_map.addLayerToGroup(group, null_polys)

        # polygons that changed MapUnit (but not Null to a new map unit)
        if len(changed) > 0:
            arcpy.AddMessage("Creating layer for polygons where MapUnit changed")
            exp = f"OBJECTID in {sql_list(changed)}"
            changed_polys = arcpy.management.MakeFeatureLayer(
                mup, "Polygons where MapUnit changed", exp
            )[0]
            active_map.addLayerToGroup(group, changed_polys)

        # contacts that have the same MapUnit on either side
        if len(same_unit) > 0:
            arcpy.AddMessage(
                "Creating layer for contacts that have the same MapUnit on either side"
            )
            exp = f"OBJECTID in {sql_list(same_unit)}"
            sandwiched_lines = arcpy.management.MakeFeatureLayer(
                caf, "Contacts with same MapUnit on either side", exp
            )[0]
            active_map.addLayerToGroup(group, sandwiched_lines)
    else:
        arcpy.AddMessage("No errors or changes to report")
