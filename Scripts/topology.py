import arcpy
from osgeo import ogr
from lxml import etree
import GeMS_Definition as gdef

top_rules = [
    "esriTRTLineNoOverlap",
    "esriTRTLineNoSelfOverlap",
    "esriTRTLineNoSelfIntersect",
    "esriTRTAreaNoOverlap",
    "esriTRTAreaNoGaps",
    "esriTRTAreaBoundaryCoveredByLine",
]
level_2_rules = [
    "esriTRTAreaNoOverlap",
    "esriTRTAreaNoGaps",
    "esriTRTAreaBoundaryCoveredByLine",
]
level_3_rules = [
    "esriTRTLineNoOverlap",
    "esriTRTLineNoSelfOverlap",
    "esriTRTLineNoSelfIntersect",
]
level_2_ids = [1, 3, 37]
level_3_ids = [19, 39, 40]
rules_dict = {
    1: "Polygons must not have gap",
    3: "Polygons must not overlap",
    19: "Lines must not overlap",
    37: "Polygon boundaries must be covered by lines",
    39: "Lines must not self-overlap",
    40: "Lines must not self-intersect",
}


def make_topology_dict(root):
    rules = root.findall(".//TopologyRule")
    top_dict = {}
    for rule in rules:
        origin_id = rule.find("OriginClassID").text
        origin_class = get_gdb_item(
            ds, f"SELECT Name from GDB_Items WHERE ObjectID = {origin_id}"
        )
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
    print(f"check table {table}")
    for n in rule_ids:
        print(f"check rule {n}")
        if n != 37:
            sql = f"""SELECT * from {table} WHERE TopoRuleType = {n} 
             and OriginClassID = {origin_id}
             and IsException = 0"""
            l = ds.ExecuteSQL(sql)
            if l.GetFeatureCount() > 0:
                i = l.GetFeatureCount()
                errors.append(f"Rule '{rules_dict[n]}' has {i} errors")
                errors_pass = False

        elif n == 37:
            sql = f"""SELECT * from {table} WHERE TopoRuleType = 37 
              and OriginClassID = {origin_id}
              and DestClassID = {dest_id}
              and IsException = 0"""
            l = ds.ExecuteSQL(sql)
            if l.GetFeatureCount() > 0:
                i = l.GetFeatureCount()
                errors.append(f"Rule '{rules_dict[n]}' has {i} errors")
                errors_pass = False

    return (errors_pass, errors)


def eval_topology(gmap):
    # if it's a map, does it have topology?
    has_top = False
    children = db_dict[gmap]["children"]
    tops = [c["name"] for c in children if c["dataType"] == "Topology"]
    if tops:
        has_top = True

    # if it has topology, does it have the required rules?
    # for this, open the ds with ogr and inspect Definition in GDB_items
    ds = ogr.GetDriverByName("OpenFileGDB").Open(db)
    rules_pass = True
    message = ""
    missing_rules = []
    top_errors = []
    for top in tops:
        top_def = get_gdb_item(
            ds, f"SELECT Definition FROM GDB_Items WHERE name = '{top}'"
        )

        # make a dictionary of d[FeatureClass] = [rule1, rule2, rule3] from the Definition in XML
        root = etree.fromstring(top_def)
        top_dict = make_topology_dict(root)
        top_id = root.find("TopologyID").text
        point_errors = f"T_{top_id}_PointErrors"
        line_errors = f"T_{top_id}_LineErrors"
        poly_errors = f"T_{top_id}_PolyErrors"

        # iterate
        level_2 = True
        level_3 = True
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
            # and if there is one, compare the rules with level 2 rules
            if set(mup_rules) == set(level_2_rules):
                mup_dest = top_dict["mup_dest"]
                if not db_dict[mup_dest]["gems_equivalent"] == "ContactsAndFaults":
                    level_2 = False
                    level_3 = False
                    message = (
                        "wrong line featureclass for rule boundary must be covered by"
                    )
                    raise StopIteration

                # now, check the T_<top_id>_errors tables
                print("check T_ table mup")
                origin_id = get_gdb_item(
                    ds, f"SELECT ObjectID FROM GDB_Items WHERE Name = '{mup}'"
                )
                dest_id = get_gdb_item(
                    ds, f"SELECT ObjectID FROM GDB_Items WHERE Name = '{mup_dest}'"
                )
                for table in [line_errors, poly_errors]:
                    results = check_errors_table(
                        ds, table, origin_id, level_2_ids, dest_id
                    )
                    if not results[0]:
                        level_2 = False
                        level_3 = False
                        top_errors.extend(results[1])
            else:
                rules_pass = False
                level_2 = False
                level_3 = False
                missing_rules.extend([r for r in lev_2_rules if not r in mup_rules])

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
            if set(caf_rules) == set(level_3_rules):
                # now, check the T_<top_id>_errors tables
                print("check T_ table caf")
                origin_id = get_gdb_item(
                    ds, f"SELECT ObjectID FROM GDB_Items WHERE Name = '{caf}'"
                )
                for table in [point_errors, line_errors, poly_errors]:
                    results = check_errors_table(ds, table, origin_id, level_3_ids)
                    if not results[0]:
                        level_3 = False
                        top_errors.extend(results[1])
            else:
                rules_pass = False
                level_2 = False
                level_3 = False
                missing_rules.extend([r for r in level_3_rules if not r in caf_rules])

        if not found_caf:
            message = "Topology is missing a ContactsAndFaults feature class"
            rules_pass = False

        if not found_mup:
            message = "Topology is missing a MapUnitPolys feature class"
            rules_pass = False
