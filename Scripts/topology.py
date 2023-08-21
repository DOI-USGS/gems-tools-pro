import arcpy
from osgeo import ogr
from lxml import etree
from pathlib import Path
from GeMS_utilityFunctions import addMsgAndPrint as ap

# find the version of Pro being used
# we have at least one 3+ only method - ExportFeatures
# may have to test for others
pro = arcpy.GetInstallInfo()["Version"]

top_rules = [
    "esriTRTLineNoOverlap",
    "esriTRTLineNoSelfOverlap",
    "esriTRTLineNoSelfIntersect",
    "esriTRTAreaNoOverlap",
    "esriTRTAreaNoGaps",
    "esriTRTAreaBoundaryCoveredByLine",
]
level_2_rules = {
    "esriTRTAreaNoOverlap": "Must Not Overlap (Area)",
    "esriTRTAreaNoGaps": "Must Not Have Gaps (Area)",
    "esriTRTAreaBoundaryCoveredByLine": "Boundary Must Be Covered By (Area-Line)",
}
level_3_rules = {
    "esriTRTLineNoOverlap": "Must Not Overlap (Line)",
    "esriTRTLineNoSelfOverlap": "Must Not Self-Overlap (Line)",
    "esriTRTLineNoSelfIntersect": "Must Not Self-Intersect (Line)",
}
level_2_ids = [1, 3, 37]
level_3_ids = [19, 39, 40]
rules_dict = {
    1: "Must Not Have Gaps (Area)",
    3: "Must Not Overlap (Area)",
    19: "Must Not Overlap (Line)",
    37: "Boundary Must Be Covered By (Area-Line)",
    39: "Must Not Self-Overlap (Line)",
    40: "Must Not Self-Intersect (Line)",
}


def n_or_missing(n, l):
    if n in l:
        return n
    else:
        return f"__missing__{n}"


def find_topology_pairs(fcs, is_gpkg, db_dict):
    # collect prefixes and suffixes, call them fd_tags
    fd_tags = []
    for fc in fcs:
        for s in (
            ("mapunitpolys", 12),
            ("map_unit_polys", 14),
            ("contactsandfaults", 17),
            ("contacts_and_faults", 19),
        ):
            if s[0] in fc.lower():
                i = fc.lower().find(s[0])
                prefix = fc[0:i]
                suffix = fc[i + s[1] :]
                fd_tags.append((prefix, suffix))

    include_mup = False
    include_caf = False
    pairs = []
    for fd_tag in set(fd_tags):
        mups = [k for k in db_dict if k == fd_tag[0] + "MapUnitPolys" + fd_tag[1]]

        cafs = [k for k in db_dict if k == fd_tag[0] + "ContactsAndFaults" + fd_tag[1]]

        if mups:
            include_mup = True
            mup = mups[0]
        else:
            mup = fd_tag[0] + "MapUnitPolys" + fd_tag[1]
        if cafs:
            include_caf = True
            caf = cafs[0]
        else:
            caf = f"{fd_tag[0]}ContactsAndFaults{fd_tag[1]}"

        if include_mup == True or include_caf == True:
            tag_name = f"{fd_tag[0]}|{fd_tag[1]}"
            pairs.append([tag_name, n_or_missing(mup, fcs), n_or_missing(caf, fcs)])

    # determine the index 0 item in the list, feature dataset or prefix+suffix tag
    for pair in pairs:
        if not is_gpkg:
            fc = pair[1] if not "__missing__" in pair[1] else pair[2]
            gmap = Path(db_dict[fc]["path"]).stem
            pair.insert(0, gmap)
        else:
            pair.insert(0, None)

    # mup equivalent will always be pairs[2]
    # caf equivalent will always be pairs[3]
    return pairs


def export(source, dest, pro):
    # Try to use ExportFeatures first but if the version is not 3 or above
    # try the deprecated method FeatureClassToFeatureClass
    ver = int(pro.split(".")[0])
    if ver == 3:
        arcpy.ExportFeatures_conversion(str(source), str(dest))
    else:
        arcpy.FeatureClassToFeatureClass_conversion(
            source, str(dest.parent), str(dest.stem)
        )


def create_fd(work_dir, gmap, sr, topo_pair, db_dict):
    """create gdb and feature dataset and copy feature classes
    for topology check if they do not exist"""
    work_dir = Path(work_dir)
    gdb_path = work_dir / "Topology.gdb"
    if not arcpy.Exists(str(gdb_path)):
        ap(f"\t\tCreating geodatabase for topology - {str(gdb_path)}")
        arcpy.CreateFileGDB_management(str(work_dir), "Topology")

    fd_path = work_dir / "Topology.gdb" / gmap
    if not arcpy.Exists(str(fd_path)):
        ap(f"\t\tCreating feature dataset {gmap}")
        arcpy.CreateFeatureDataset_management(str(gdb_path), gmap, sr.name)

    # copy the feature
    source_mup = db_dict[topo_pair[2]]["catalogPath"]
    source_caf = db_dict[topo_pair[3]]["catalogPath"]
    copy_mup = fd_path / topo_pair[2]
    copy_caf = fd_path / topo_pair[3]

    ap("\t\tCopying feature classes")
    export(source_mup, copy_mup, pro)
    export(source_caf, copy_caf, pro)

    return gdb_path, str(copy_mup), str(copy_caf)


def add_topology(gdb_path, gmap, topo_caf, topo_mup):
    """create an empty topology for topology check. Delete any existing"""

    ap(f"\t\tCreating topology {gmap}_Topology")
    top_path = gdb_path / gmap / f"{gmap}_Topology"
    if arcpy.Exists(str(top_path)):
        arcpy.Delete_management(str(top_path))
    arcpy.CreateTopology_management(str(gdb_path / gmap), f"{gmap}_Topology")

    for fc in (topo_caf, topo_mup):
        arcpy.AddFeatureClassToTopology_management(str(top_path), fc)

    return str(top_path)


def add_rules(topology, caf, mup, db_dict):
    """add gems-required topology rules to a new topology"""
    ap("\t\tAdding topology rules to topology")
    # caf = [fc for fc in fcs if db_dict[fc]["gems_equivalent"] == "ContactsAndFaults"][0]
    # mup = [fc for fc in fcs if db_dict[fc]["gems_equivalent"] == "MapUnitPolys"][0]
    # caf_path = Path(topology).parent / caf
    # mup_path = Path(topology).parent / mup
    for i in (1, 3):
        rule_type = rules_dict[i]
        arcpy.AddRuleToTopology_management(topology, rule_type, mup)

    for i in (19, 39, 40):
        rule_type = rules_dict[i]
        arcpy.AddRuleToTopology_management(topology, rule_type, caf)

    arcpy.AddRuleToTopology_management(topology, rules_dict[37], mup, None, caf)


def make_topology(work_dir, topo_pair, db_dict):
    """make a topology in a scratch gdb. Called in the case of no topology
    in input gdb or geopackage
    topo_pair  = [GeologicMap feature dataset(if gdb), fd_tag_name, mapunitpolys, contactsandfaults]
    """

    if topo_pair[0]:
        gmap = topo_pair[0]
        sr = db_dict[gmap]["spatialReference"]

    elif not topo_pair[1] == "|":
        tags = topo_pair[1].split("|")
        tag_name = f"{tags[0].strip('_')}{tags[1]}"

        if topo_pair[0]:
            gmap = f"{topo_pair[0].strip('_')}{tag_name}"
        else:
            gmap = tag_name
            sr = db_dict[topo_pair[2]]["spatialReference"]

    else:
        sr = db_dict[topo_pair[2]]["spatialReference"]
        gmap = "GeologicMap"

    if not topo_pair[0] is None:  # there IS a gdb feature dataset name
        # catching the case of a gdb feature dataset having more than
        # one pair of MapUnitPolys and ContactsAndFaults. In that case,
        # the feature classes must have either a prefix or suffix or both
        # to distinguish them from other pairs. So, find those tags and
        # make a new feature dataset name
        if not topo_pair[1] == "|":
            tags = topo_pair[1].split("|")

            if tags[0].endswith("_") or tags[0] == "":
                prefix = tags[0]
            else:
                prefix = f"{tags[0]}_"

            if tags[1].startswith("_") or tags[1] == "":
                suffix = tags[1]
            else:
                suffix = f"_{tags[1]}"

            gmap = f"{prefix}{gmap}{suffix}"

    gdb_path, topo_mup, topo_caf = create_fd(work_dir, gmap, sr, topo_pair, db_dict)
    top_path = add_topology(gdb_path, gmap, topo_caf, topo_mup)
    add_rules(top_path, topo_caf, topo_mup, db_dict)
    arcpy.ValidateTopology_management(top_path)

    # return full path to topology and has_been_validated
    return top_path, True


def get_gdb_item(ds, sql):
    """helper function to query ogr dataset
    only one value returned. For looking up one field from one row"""
    l = ds.ExecuteSQL(sql)
    if not l is None:
        return l.GetNextFeature().GetField(0)
    else:
        return None


def make_topology_dict(ds, root, db_dict):
    rules = root.findall(".//TopologyRule")
    top_dict = {}
    for rule in rules:
        origin_id = rule.find("OriginClassID").text
        sql = f"SELECT Name from GDB_Items WHERE ObjectID = {origin_id}"
        origin_class = get_gdb_item(ds, sql)
        rule_type = rule.find("TopologyRuleType").text
        if not origin_class in top_dict:
            top_dict[origin_class] = [rule_type]

        else:
            top_dict[origin_class].append(rule_type)

        if (
            rule_type == "esriTRTAreaBoundaryCoveredByLine"
            and db_dict[origin_class]["gems_equivalent"] == "MapUnitPolys"
        ):
            sql = f"SELECT Name from GDB_Items WHERE ObjectID = {rule.find('DestinationClassID').text}"
            dest_class = get_gdb_item(ds, sql)
            top_dict["mup_dest"] = dest_class
        else:
            top_dict["mup_dest"] = None

    return top_dict


def check_errors_table(ds, table, origin_id, rule_ids, dest_id=None):
    """select rows from the T_errors table where the rule and the class ids match
    a valid topology will return no rows"""
    errors = []
    errors_pass = True

    for n in rule_ids:
        # if n != 37:
        sql = f"""SELECT * from {table} WHERE TopoRuleType = {n} 
            and OriginClassID = {origin_id}
            and IsException = 0"""
        l = ds.ExecuteSQL(sql)
        if l.GetFeatureCount() > 0:
            i = l.GetFeatureCount()
            if i == 1:
                errors.append(f"Rule '{rules_dict[n]}' has {i} error")
            else:
                errors.append(f"Rule '{rules_dict[n]}' has {i} errors")
            errors_pass = False

    return (errors_pass, errors)


def has_been_validated(top_path):
    """query the T_<id>_DirtyAreas feature class to see if there are any dirty areas
    apparently this will contain polygons of 0 area if they were once dirty but
    have since been validated"""
    db = Path(top_path).parent.parent
    top_name = Path(top_path).stem

    # open with ogr driver to find out the topology id
    ds = ogr.GetDriverByName("OpenFileGDB").Open(str(db))
    top_def = get_gdb_item(
        ds, f"SELECT Definition FROM GDB_Items WHERE name = '{top_name}'"
    )
    root = etree.fromstring(top_def)
    top_id = root.find("TopologyID").text

    # use arcpy search cursor to look at table
    dirty_areas = f"T_{top_id}_DirtyAreas"
    has_been_validated = True
    sql = f"SELECT DirtyArea_Area from {dirty_areas}"
    result = ds.ExecuteSQL(sql)
    if not result is None:
        for area in result:
            if area.GetField(0) > 0:
                has_been_validated = False
    else:
        has_been_validated = False

    return has_been_validated


def eval_topology(db, top, db_dict, gmap, level_2_errors, level_3_errors):
    ds = ogr.GetDriverByName("OpenFileGDB").Open(db)
    top_def = get_gdb_item(ds, f"SELECT Definition FROM GDB_Items WHERE name = '{top}'")

    # make a dictionary of d[FeatureClass] = [rule1, rule2, rule3] from the Definition in XML
    root = etree.fromstring(top_def)
    top_dict = make_topology_dict(ds, root, db_dict)
    top_id = root.find("TopologyID").text
    point_errors = f"T_{top_id}_PointErrors"
    line_errors = f"T_{top_id}_LineErrors"
    poly_errors = f"T_{top_id}_PolyErrors"

    found_caf = False
    found_mup = False

    # look at level 2 / MapUnitPolys rules first
    mup_list = [
        k
        for k in top_dict
        if k != "mup_dest" and db_dict[k]["gems_equivalent"] == "MapUnitPolys"
    ]
    if mup_list:
        mup = mup_list[0]
        found_mup = True
        mup_rules = top_dict[mup]
        mup_dest = top_dict["mup_dest"]

        if set(mup_rules) != set(list(level_2_rules.keys())):
            level_2_errors.extend(
                [
                    f"&emsp;Rule '{level_2_rules[r]}' is missing"
                    for r in level_2_rules
                    if not r in mup_rules
                ]
            )

        if not mup_dest == None:
            if not db_dict[mup_dest]["gems_equivalent"] == "ContactsAndFaults":
                level_2_errors.append(
                    f"&emsp;Wrong line featureclass for rule Boundary Must Be Covered By (Area-Line), {mup_dest}"
                )

        # now, check the T_<top_id>_errors tables
        origin_id = get_gdb_item(
            ds, f"SELECT ObjectID FROM GDB_Items WHERE Name = '{mup}'"
        )
        dest_id = None
        if mup_dest:
            dest_id = get_gdb_item(
                ds, f"SELECT ObjectID FROM GDB_Items WHERE Name = '{mup_dest}'"
            )

        for table in [line_errors, poly_errors]:
            results = check_errors_table(ds, table, origin_id, level_2_ids, dest_id)
            if not results[0]:
                level_2_errors.extend([f"&emsp;{res}" for res in results[1]])

    # now look for a level 3 / ContactsAndFaults rules
    caf_list = [
        k
        for k in top_dict
        if k != "mup_dest" and db_dict[k]["gems_equivalent"] == "ContactsAndFaults"
    ]
    if caf_list:
        caf = caf_list[0]
        found_caf = True
        caf_rules = top_dict[caf]
        # now, check the T_<top_id>_errors tables
        origin_id = get_gdb_item(
            ds, f"SELECT ObjectID FROM GDB_Items WHERE Name = '{caf}'"
        )

        level_3_errors.extend(
            [
                f"&emsp;Rule '{level_3_errors[r]}' is missing"
                for r in level_3_rules
                if not r in caf_rules
            ]
        )

        for table in [point_errors, line_errors, poly_errors]:
            results = check_errors_table(ds, table, origin_id, level_3_ids)
            if not results[0]:
                level_3_errors.extend([f"&emsp;{r}" for r in results[1]])

    if not found_caf:
        level_2_errors.append("Topology is missing a ContactsAndFaults feature class")
        level_3_errors.append("Topology is missing a ContactsAndFaults feature class")

    if not found_mup:
        level_2_errors.append("Topology is missing a MapUnitPolys feature class")
        level_3_errors.append("Topology is missing a MapUnitPolys feature class")

    if "&emsp;Rule 'Must Not Have Gaps (Area)' has 1 error" in level_2_errors:
        level_2_errors.remove("&emsp;Rule 'Must Not Have Gaps (Area)' has 1 error")

    if len(level_2_errors) > 3:
        level_2_errors.insert(3, f"&ensp;{gmap}")

    if len(level_3_errors) > 3:
        level_3_errors.insert(3, f"&ensp;{gmap}")

    return level_2_errors, level_3_errors
