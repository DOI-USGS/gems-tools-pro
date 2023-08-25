# -*- coding: utf-8 -*-
"""Validate Database

Audits a geodatabase for conformance with the GeMS schema and reports compliance 
as "may be LEVEL 1 COMPLIANT", "is LEVEL 2 COMPLIANT", or "is LEVEL 3 COMPLIANT". 
It also runs mp (metadata parser) to check for formal errors in geodatabase-level 
FGDC metadata. 

Usage:
    Use parameter form in ArcGIS Pro or at command line with the arguments below. 
    Use '' or '#' for optional arguments that are not required.
    
Args:
    gdb_path (str) : Path to database. Required.
    workdir (str) : Path to output directory. Optional but if not supplied, a 
      folder called 'validate' will be created in the parent folder of the database.
    metadata_file (str) : Path to metadata file to validate. Optional.
    arc_md (bool or str) : True or false whether the embedded metadata of the file 
      geodatabase as a whole (feature datasets, feature classes, tables, etc. will be
      ignored) are to be validated. If left blank and metadata_file is blank, no 
      metadata will be validated. Optional. False by default.
    use_idfield (bool or str) : True or false whether errors in the report should
      be identified by values in the <TableName _ID> field, not the OBJECTID field.
      Useful in the case of validating a copy of an enterprise database that has 
      been exported (which overwrites OBJECTIDs) to a file geodatabase but errors 
      will be corrected in the enterprise database. For those tables that do not have
      a <TableName_ID> field or where the value is null, the OBJECTID will be reported.
      Optional. False by default.
    skip_topology (bool or str) : True or false whether checking topology should be 
      skipped. Optional. False by default.
    refresh_gmd (bool or str) : True or false whether the GeoMaterialDict
      table in the database should be re-written to the latest required version.
      Optional. False by default.
    delete_extra (bool or str) : True or false whether to delete unused rows in 
      DataSources and Glossary. Optional. False by default.
    compact_db (bool or str) : True or false whether to compact the file geodatabase.
      Not applicable to geopackages. Optional. False by default.
    open_report (bool or str) : True or false whether to open the html validation file 
      upone completion. Optional. False by default.
    
      
Returns:
    <gdb name>-Validation.html (file) : Reports level of 
      compliance, lists errors and warnings. Written to workdir. 
    <gdb name>-ValidationErrors.html (file) : Detailed list of errors and warnings
      by table, field, ObjectID, etc. Written to workdir.
    <gdb name>_Validation.gdb (file gdb)

"""

# every level 2 or 3 errors list needs to contain
# [
#   the message that will appear in the pass/fail cell of -Validation.html file if the rule fails,
#   the header for the rule section in -ValidationErrors.html file,
#   the name of the anchor in the -ValidationErrors file for the rule,
#   error1, error2, error3, errorI...
# ]
#
# val dictionary entries for specific entries take the form of
# [
#   message in the pass/fail cell in -Validation,
#   header for the list of errors in -ValidationErrors,
#   html anchor
# ]
# unless there is an error that precludes the listing of errors, for example,
# without a MapUnitPolys feature class there can be no topology errors.
# In that case, the entry has only one item in the list and it is only reported
# in -Validation.html
#
# lists of warnings begin with a description of the warning followed by the
# warnings. If there are no warnings, each dictionary entry (term_warnings, for example)
# is only one item long

import arcpy
import os
import sys
import time
import copy
from pathlib import Path
import GeMS_utilityFunctions as guf
import GeMS_Definition as gdef
import topology as tp
import requests
from jinja2 import Environment, FileSystemLoader

from importlib import reload

reload(gdef)

# values dictionary gets sent to report_template.jinja errors_template.jinja
val = {}

version_string = "GeMS_ValidateDatabase.py, version of 8/24/2023"
val["version_string"] = version_string
val["datetime"] = time.asctime(time.localtime(time.time()))

rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_ValidateDatabase.py"

py_path = __file__
scripts_dir = Path.cwd()
toolbox_dir = scripts_dir.parent
resources_path = toolbox_dir / "Resources"

ap = guf.addMsgAndPrint

lc_standard_fields = []
for f in gdef.standard_fields:
    lc_standard_fields.append(f.lower())

use_idfield = False


def check_sr(db_obj, db_dict):
    """Checks the datum of the spatial reference. Warning if not NAD83 or WGS84"""
    sr_warnings = []
    sr = db_dict[db_obj]["spatialReference"]

    # check for NAD83 or WGS84
    if sr.type == "Geographic":
        pcsd = sr.datumName
    else:  # is projected
        pcsd = sr.PCSName
    if pcsd.find("World_Geodetic_System_1984") < 0 and pcsd.find("NAD_1983") < 0:
        sr_warnings.append(
            f"""Spatial reference of {db_obj} is {pcsd}. 
            Consider reprojecting to NAD83 or WGS84"""
        )

    if sr_warnings:
        return sr_warnings


def compare_sr(obj1, obj2, db_dict):
    """Compares two spatial reference objects. Differences reported as warning,
    not error"""
    sr_warnings = []
    sr1 = db_dict[obj1]["spatialReference"].name
    sr2 = db_dict[obj1]["spatialReference"].name
    if sr1 != sr2:
        sr_warnings = [f"{obj1} and {obj2} have different spatial references"]
    else:
        sr_warnings = "ok"

    return sr_warnings


def values(db_dict, table, field, what, where=None):
    """List or dictionary {[oid]: value} of values found in a field in a
    dictionary is {oid: value}"""
    vals = None
    if table in db_dict:
        # fields = db_dict[table]["fields"]
        if what == "dictionary":
            oid = which_id(db_dict, table)

            vals = {
                r[0]: r[1]
                for r in arcpy.da.SearchCursor(
                    db_dict[table]["catalogPath"],
                    field_names=[oid, field],
                    where_clause=where,
                    sql_clause=(None, f"ORDER BY {field}"),
                )
            }
        else:
            vals = [
                r[0]
                for r in arcpy.da.SearchCursor(
                    db_dict[table]["catalogPath"], field_names=field, where_clause=where
                )
            ]
    return vals


def which_id(db_dict, table):
    """Determine whether to report the value in the table's _ID field or OBJECTID"""
    fields = db_dict[table]["fields"]
    global use_idfield
    # try:
    if use_idfield:
        fields = db_dict[table]["fields"]
        gemsid = [f.name for f in fields if f.name.lower().endswith("_id")]
        if gemsid:
            return gemsid[0]
        else:
            return [f.name for f in fields if f.type == "OID"][0]
    else:
        return [f.name for f in fields if f.type == "OID"][0]


def rule2_1(db_dict, is_gpkg):
    """Has required elements: nonspatial tables DataSources, DescriptionOfMapUnits,
    GeoMaterialDict; feature dataset GeologicMap with feature classes ContactsAndFaults
    and MapUnitPolys"""
    tp_pairs = []
    sr_warnings = ["Spatial reference warnings"]
    errors = ["items(s) missing", "2.1 Missing required elements", "MissingElements"]

    # first look for GeologicMap feature dataset
    if not is_gpkg:
        gmaps = [k for k, v in db_dict.items() if v["gems_equivalent"] == "GeologicMap"]
        if not gmaps:
            errors.append(f'Feature dataset <span class="table">GeologicMap</span>')
        else:
            # check the spatial reference of each 'GeologicMap' feature dataset
            for gmap in gmaps:
                check_sr_result = check_sr(gmap, db_dict)
                if check_sr_result:
                    sr_warnings.extend(check_sr_result)

    fcs = [
        k
        for k, v in db_dict.items()
        if v["gems_equivalent"] in gdef.required_geologic_map_feature_classes
    ]
    # find_topology_pairs returns [GeologicMap feature dataset(if gdb), fd_tag_name, mapunitpolys, contactsandfaults]
    possible_pairs = tp.find_topology_pairs(fcs, is_gpkg, db_dict)
    if possible_pairs:
        # check each tagged name pair in the case of no feature dataset (pair[0])
        for pair in possible_pairs:
            # warning about missing feature class:
            for n in pair[2:]:
                if "_missing_" in n:
                    errors.append(
                        f'Feature class <span class="table">{n.replace("__missing__", "")}</span>'
                    )
                else:
                    if is_gpkg or db_dict[n]["feature_dataset"] == "":
                        # check each feature class for old datum
                        check_sr_result = check_sr(n, db_dict)
                        if check_sr_result:
                            sr_warnings.extend(check_sr_result)

            if all(n.find("__missing__") == -1 for n in pair[2:]):
                compare_results = compare_sr(pair[2], pair[3], db_dict)
                if not compare_results == "ok":
                    sr_warnings.append(compare_results)
                else:
                    # if both required feature classes are in the pair,
                    # and have the same sr
                    # add to tp_pairs to be evaluated for topology in rule 2.3
                    tp_pairs.append(pair)
    else:
        for n in ("MapUnitPolys", "ContactsAndFaults"):
            errors.append(f'Feature class <span class="table">{n}</span>')

    # consider non-spatial tables
    db_tables = set(
        [k for k, v in db_dict.items() if v["gems_equivalent"] in gdef.required_tables]
    )
    if set(db_tables) != set(gdef.required_tables):
        for n in set(gdef.required_tables).difference(set(db_tables)):
            errors.append(f'<span class="table">{n}</span>')

    return (errors, tp_pairs, sr_warnings)


def check_fields(db_dict, level, schema_extensions):
    """Controlled fields are present and correctly defined
    right now this only looks at controlled fields in tables that have been tagged
    with a gems_equivalent.
    """
    header = "<h4>Fields</h4>"
    if not schema_extensions:
        schema_extensions.append(header)

    fld_warnings = ["Recommended fields that are missing"]
    req_tables = [t for t in gdef.rule2_1_elements if t != "GeologicMap"]
    if level == 2:
        # only required tables and fcs
        tables = [k for k, v in db_dict.items() if v["gems_equivalent"] in req_tables]
        header = "2.2 Missing or mis-defined fields"
    elif level == 3:
        # all other tables and fcs
        tables = [
            k
            for k, v in db_dict.items()
            if not v["gems_equivalent"] in req_tables
            and not v["gems_equivalent"] == ""
            and not v["dataType"] in ("Topology", "Annotation")
            and not "cartographicpoints" in k.lower()
            and not "cartographiclines" in k.lower()
        ]
        header = "3.1 Missing or mis-defined fields"

    errors = [
        "missing or mis-defined field(s)",
        header,
        f"MissingFields{level}",
    ]

    for table in tables:
        gems_eq = db_dict[table]["gems_equivalent"]
        req_fields = copy.copy(gdef.startDict[gems_eq])

        # the following is a workaround for a problem that should get fixed when a schema for
        # a GeoChemPoints feature class is decided on. Like GeoChronPoints, GeoChemPoints shouldn't
        # require a DataSourceID. Hopefully, there is an AnalysisSourceID or similar but we won't check it
        if "geochempoints" in table.lower():
            req_fields = [i for i in req_fields if not i[0] == "DataSourceID"]

        # add an _ID field for the table
        if not table == "GeoMaterialDict":
            req_fields.append([f"{table}_ID", "String", "NoNulls", gdef.IDLength])

        found_fields = db_dict[table]["fields"]
        f_field_names = [f.name for f in found_fields]
        for field in req_fields:
            if not field[0] in f_field_names:
                if not field[2] == "Optional":
                    html = f'<span class="table">{table}</span> missing field <span class="field">{field[0]}</span>'
                    errors.append(html)
            else:
                req_type = field[1]

                # get field object from the gdb/feature class dictionary for this required field
                cur_field = [f for f in found_fields if f.name.endswith(field[0])]
                if cur_field:
                    cur_field = cur_field[0]
                    html = f'<span class="table">{table}</span>, field <span class="field">{cur_field.name}</span> should be'
                    if req_type != cur_field.type:
                        errors.append(f"{html} type {req_type}")

        req_names = [f[0].lower() for f in req_fields]
        lower_standard = [n.lower() for n in gdef.standard_fields]
        for field in [
            f.name
            for f in found_fields
            if f.name.lower() not in req_names
            and not f.name.lower().endswith("_id")
            and not f.name.lower() in lower_standard
        ]:
            schema_extensions.append(
                '<span class="tab"></span><span class="table">'
                + table
                + '</span>, <span class="field">'
                + field
                + "</span>"
            )

    return errors, schema_extensions, fld_warnings


def check_topology(db_dict, workdir, is_gpkg, topo_pairs):
    """2.3 GeologicMap topology: no internal gaps or overlaps in MapUnitPolys, boundaries of
    MapUnitPolys are covered by ContactsAndFaults 3.2 All map-like feature datasets obey
    topology rules. No MapUnitPolys gaps or overlaps. No ContactsAndFaults overlaps, self-overlaps,
    or self-intersections. MapUnitPoly boundaries covered by ContactsAndFaults"""
    has_been_validated = False
    level_2_errors = [
        "topology errors",
        "2.3 Topology errors",
        "topology2",
    ]

    level_3_errors = [
        "topology errors",
        "3.2 Topology errors",
        "topology3",
    ]

    for topo_pair in topo_pairs:
        make_topology = False
        gmap = topo_pair[0]
        if gmap:
            children = db_dict[gmap]["children"]
            tops = [c["name"] for c in children if c["dataType"] == "Topology"]
            if tops:
                ap(f"\tTopology in {gmap} found")
                top_path = db_dict[tops[0]]["catalogPath"]
                has_been_validated = tp.has_been_validated(top_path)
            else:
                make_topology = True
        else:
            make_topology = True

        if make_topology:
            if not is_gpkg:
                ap(f"\tNo topology found in {gmap}")

            top_path, has_been_validated = tp.make_topology(workdir, topo_pair, db_dict)

        # evaluate the topology
        # eval_topology returns (level_2, level_3, missing_rules, top_errors)
        # do we need to validate first?
        # look for DirtyAreas
        if not has_been_validated:
            ap("\t\tValidating topology")
            arcpy.ValidateTopology_management(top_path)

        ap("\t\tLooking at validation results for errors")

        # topologies have to be in feature dataset, so topology.parent.parent
        # gets the file geodatabase, whether the original or the Topology.gdb copy
        gmap = Path(top_path).parent.stem
        topo_gdb = Path(top_path).parent.parent
        top_name = Path(top_path).stem
        level_2_errors, level_3_errors = tp.eval_topology(
            str(topo_gdb), top_name, db_dict, gmap, level_2_errors, level_3_errors
        )

    return level_2_errors, level_3_errors


def check_map_units(db_dict, level, all_map_units, fds_map_units):
    """All MapUnits entries can be found in DescriptionOfMapUnits table
    Rules 2.4 and 3.8
    Also, collect additions to all_mu_units and fds_map_units"""
    if not "DescriptionOfMapUnits" in db_dict:
        message = [
            '<span class="table>DescriptionOfMapUnits</span> cannot be found. See Rule 2.1',
        ]
        missing = message
        unused = message
        if level == 2:
            return missing, all_map_units, None
        else:
            return missing, unused, None, None

    dmu_units = list(set(values(db_dict, "DescriptionOfMapUnits", "MapUnit", "list")))
    dmu_units = [u for u in dmu_units if not u == None]
    fds_map_units["DescriptionOfMapUnits"] = dmu_units

    if level == 2:
        # just checking MapUnitPolys gems_equivalent feature classes
        mu_tables = [
            k for k, v in db_dict.items() if v["gems_equivalent"] == "MapUnitPolys"
        ]
        mu_fields = ["MapUnit"]
        missing_header = "2.4 MapUnits missing from DMU. Only one reference to each missing unit is cited"
    else:
        # checking all other tables that have fields with "MapUnit" in the name.
        # fields that equal "MapUnit" will be checked for errors
        # fields that have "MapUnit" in the name with a prefix or suffix, eg.,
        # "OrigMapUnit" will be checked for warnings.
        mu_tables = []

        # find all tables that have MapUnit-y field names
        for table in [
            k
            for k, v in db_dict.items()
            if any(n in v["concat_type"] for n in ("Feature Class", "Table"))
            and not v["dataType"] == "FeatureDataset"
            and not k in ["DescriptionOfMapUnits", "MapUnitPolys"]
        ]:
            for f in [f.name for f in db_dict[table]["fields"]]:
                if "mapunit" in f.lower() and not f.lower().endswith("_id"):
                    mu_tables.append(table)

        missing_header = "3.8 MapUnits missing from DMU. Only one reference to each missing unit is cited"

    missing = [
        "map unit(s) missing in DMU",
        missing_header,
        f"UnitsMissing{level}",
    ]

    unused = [
        "missing map unit(s) in DMU",
        "3.9 MapUnits in DMU that are not found anywhere else",
        f"UnusedUnits{level}",
    ]

    mu_warnings = [
        """Values in fields with <span class="field">MapUnit</span> in the name 
                that are not in <span class="table">DescriptionOfMapUnits</span>. 
                Please add descriptions to the database or make sure descriptions are
                in the metadata."""
    ]

    # iterate through the tables
    mu_tables = list(set(mu_tables))
    if mu_tables:
        for mu_table in mu_tables:
            # find out which feature dataset this table is in
            fd = (
                db_dict[mu_table]["feature_dataset"]
                if db_dict[mu_table]["feature_dataset"]
                else mu_table
            )
            if not fd in fds_map_units:
                fds_map_units[fd] = []

            # look at fields that are named "MapUnit"
            # undefined mapunits are errors
            mu_fields = [
                f.name
                for f in db_dict[mu_table]["fields"]
                if f.name.lower() == "mapunit"
            ]

            if mu_fields:
                with arcpy.da.SearchCursor(
                    db_dict[mu_table]["catalogPath"], mu_fields
                ) as cursor:
                    for row in cursor:
                        for i, val in enumerate(row):
                            if val:
                                if not val in dmu_units:
                                    html = f"""
                                        <span class="value">{val}</span>, 
                                        field <span class="field">{mu_fields[i]}</span>, 
                                        table <span class="table">{mu_table}</span>"""
                                    missing.append(html)
                                all_map_units.append(val)
                                fds_map_units[fd].extend(row)

            # reset mu_fields and check again
            # look at fields that have MapUnit in the name but are qualified
            # by a prefix or suffix, eg, OrigMapUnit. Accommodates compilations
            # where new DMU does not have the same units as new DMU
            mu_fields = [
                f.name
                for f in db_dict[mu_table]["fields"]
                if "mapunit" in f.name.lower()
                and not f.name.lower().endswith("_id")
                and not f.name.lower() == "mapunit"
                and not "guid" in f.name.lower()
            ]

            if mu_fields:
                with arcpy.da.SearchCursor(
                    db_dict[mu_table]["catalogPath"], mu_fields
                ) as cursor:
                    for row in cursor:
                        for i, val in enumerate(row):
                            if not val in dmu_units and not val == None:
                                html = f"""<span class="value">{val}</span>, 
                                field <span class="field">{mu_fields[i]}</span>, 
                                table <span class="table">{mu_table}</span>"""
                                mu_warnings.append(html)

            fds_map_units[fd] = list(set(fds_map_units[fd]))

        all_map_units.extend(list(set(all_map_units)))

    missing = [i for n, i in enumerate(missing) if i not in missing[:n]]

    unused.extend(list(set(dmu_units) - set(all_map_units)))

    if level == 2:
        return (missing, all_map_units, fds_map_units)
    else:
        return (
            missing,
            unused,
            all_map_units,
            fds_map_units,
            mu_warnings,
        )


def glossary_check(db_dict, level, all_gloss_terms):
    """Rule 2.6 Certain field values within required elements have entries in Glossary table
    Rule 3.4 No missing terms in Glossary"""
    missing = []
    # decide which tables to check
    # just the core required elements...
    req = [el for el in gdef.rule2_1_elements if not el in ("GeologicMap", "Glossary")]

    if level == 2:
        tables = [t for t in db_dict if db_dict[t]["gems_equivalent"] in req]
        missing_header = "2.6 Missing terms in Glossary. Only one reference to each missing term is cited"
    else:
        # or every other table in the database
        # at level 3, we have already checked level 2 elements
        tables = [
            k
            for k, v in db_dict.items()
            if not v["dataType"] in ("FeatureDataset", "Annotation", "Topology")
            and not k == "GeoMaterialDict"
            and v["gems_equivalent"] not in req
        ]
        missing_header = "3.4 Missing terms in Glossary. Only one reference to each missing term is cited"
        term_warnings = [
            """Terms in GeMS-like fields that do not have definitions in the Glossary.<br>
            All fields ending in <span class="field">type</span>, <span class="field">method</span>, 
            or <span class="field">confidence</span> are checked.<br>
            Please define these terms in Glossary, provide a look-up table, or at minimum define in the metadata"""
        ]

    missing_glossary_terms = [
        "term(s) missing in Glossary",
        missing_header,
        f"MissingTerms{level}",
    ]

    # compare Term fields in the tables with the Glossary
    glossary_terms = values(db_dict, "Glossary", "Term", "list")
    if tables:
        for table in tables:
            id_fld = which_id(db_dict, table)
            # look for fields matching the controlled fields
            # the tables to look through get defined above depending on level
            fields = [
                f.name
                for f in db_dict[table]["fields"]
                if f.name in gdef.defined_term_fields_list
            ]

            if fields:
                for field in fields:
                    if field == "GeoMaterialConfidence":
                        where = "GeoMaterial IS NOT NULL"
                    else:
                        where = None

                    # vals = values(db_dict, table, field, "dictionary", where)
                    vals = values(db_dict, table, field, "list", where)

                    # put all of these glossary terms in all_gloss_terms list
                    field_vals = list(set(vals))
                    if None in field_vals:
                        field_vals.remove(None)
                    all_gloss_terms.extend(field_vals)

                    # sort the list and remove null values
                    # sorted_vals = {k: vals[k] for k in sorted(vals) if vals[k]}
                    vals = [el for el in vals if el]
                    sorted_vals = [el for el in sorted(vals) if el]

                    for el in sorted_vals:
                        if not el in glossary_terms:
                            html = f"""table <span class="table">{table}</span>, 
                                        field <span class="field">{field}</span>, 
                                        <span class="value">{el}</span>"""
                            missing.append(html)

            if level == 3:
                # also look for all non-GeMS field names in all tables ending in a controlled suffix, GeMS-sy fields
                tables = [
                    k
                    for k, v in db_dict.items()
                    if not v["dataType"] in ("FeatureDataset", "Annotation", "Topology")
                    and not k == "GeoMaterialDict"
                ]
                if tables:
                    for table in tables:
                        gemsy_fields = []
                        term_suffixes = ["type", "method", "confidence"]
                        for suffix in term_suffixes:
                            more_fields = [
                                f.name
                                for f in db_dict[table]["fields"]
                                if f.name.lower().endswith(suffix)
                                and not f.name in gdef.defined_term_fields_list
                            ]
                            gemsy_fields.extend(more_fields)
                        if gemsy_fields:
                            # values in gems-like fields that are not found in the glossary are
                            # listed as warnings, not errors
                            for g_field in gemsy_fields:
                                vals = values(db_dict, table, g_field, "list")

                                vals = [el for el in vals if el]
                                sorted_vals = [el for el in sorted(vals) if el]

                                # look for missing values
                                for el in sorted_vals:
                                    if not el in glossary_terms:
                                        html = f"""table <span class="table">{table}</span>, 
                                                    field <span class="field">{g_field}</span>, 
                                                    value <span class="value">{el}</span>"""
                                        # not sure why term_warnings gets duplicates...
                                        if not html in term_warnings:
                                            term_warnings.append(html)

    missing_glossary_terms.extend(list(set(missing)))

    if level == 2:
        return missing_glossary_terms, all_gloss_terms
    else:
        return missing_glossary_terms, all_gloss_terms, term_warnings


def sources_check(db_dict, level, all_sources):
    """Rule 2.8 All xxxSourceID values in required elements have entries in DataSources table
    Rule 3.6 No missing sources in DataSources"""

    # first check for DataSources table and DataSources_ID field
    if not "DataSources" in db_dict:
        return "Could not find DataSources table. See Rule 2.1"

    if not "DataSources_ID" in [f.name for f in db_dict["DataSources"]["fields"]]:
        return "Could not find DataSources_ID field in DataSources. See Rule 2.1"

    # found table and filed, proceeed
    # decide which tables to check
    if level == 2:
        # just required fc and tables
        req = [t for t in gdef.rule2_1_elements if not t == "GeologicMap"]
        tables = [t for t in db_dict if db_dict[t]["gems_equivalent"] in req]
        missing_header = "2.8 Missing DataSources entries. Only one reference to each missing entry is cited"

    if level == 3:
        # all other tables and fcs in the database
        tables = [
            k
            for k, v in db_dict.items()
            if not v["dataType"] in ["FeatureDataset", "Annotation", "Topology"]
            and not k in gdef.rule2_1_elements
        ]
        # tables = [t for t in tables if not t in gdef.rule2_1_elements]
        missing_header = "3.6 Missing DataSources entries. Only one reference to each missing entry is cited"

    missing_source_ids = [
        "entry(ies) missing in DataSources",
        missing_header,
        f"MissingDataSources{level}",
    ]

    gems_sources = list(set(values(db_dict, "DataSources", "DataSources_ID", "list")))
    missing = []
    for table in tables:
        # special case where DescriptionSourceID in DMU can be null:
        # if there is no MapUnit
        if table == "DescriptionOfMapUnits":
            where = "MapUnit IS NOT NULL"
        else:
            where = None

        # id_fld = which_id(db_dict, table)

        ds_fields = [
            f.name
            for f in db_dict[table]["fields"]
            if f.name.lower().endswith("sourceid")
        ]
        for ds_field in ds_fields:
            d_sources = values(db_dict, table, ds_field, "dictionary", where)

            for val in d_sources.values():
                if val:
                    # if "|" in val:
                    for el in val.split("|"):
                        if not el.strip() in all_sources:
                            all_sources.append(el.strip())
                        if not el.strip() in gems_sources:
                            missing.append(
                                f'<span class="table">{table}</span>, field <span class="field">{ds_field}</span>, <span class="value">{el}</span>'
                            )
                    # else:
                    #     all_sources.append(val.strip())
                    #     if not val.strip() in gems_sources:
                    #         missing.append(
                    #             f'table <span class="table">{table}</span>, field <span class="field">{ds_field}</span>, <span class="value">{val}</span>'
                    #         )
                else:
                    if ds_field in gdef.req_source_ids:
                        missing.append(
                            f'<span class="table">{table}</span>, field <span class="field">{ds_field}</span> has null values'
                        )

    missing_source_ids.extend(list(set(missing)))

    return missing_source_ids, all_sources


def rule3_3(db_dict):
    """All NoNulls fields in all GeMS tables should be filled"""
    # find all gems_equivalent tables
    tables = [
        k
        for k, v in db_dict.items()
        if not v["gems_equivalent"] == ""
        and not v["dataType"] == "FeatureDataset"
        and not v["gems_equivalent"] == "GeoMaterialDict"
    ]

    missing_required_values = [
        "missing required value(s)",
        "3.3 Fields that are missing required values (NULL values in critical NoNulls fields)",
        "MissingReqValues",
    ]

    missing_warnings = [
        "Possible mistaken omissions (NULL values in non-critical NoNulls fields)"
    ]

    errors = []
    warnings = []
    for table in tables:
        # collect all NoNulls fields
        gems_eq = db_dict[table]["gems_equivalent"]
        def_fields = gdef.startDict[gems_eq]
        no_nulls = [n[0] for n in def_fields if n[2] == "NoNulls"]
        fields = [f.name for f in db_dict[table]["fields"] if f.name in no_nulls]
        # oid = [f.name for f in db_dict[table]["fields"] if f.type == "OID"][0]
        for field in fields:
            vals = values(db_dict, table, field, "dictionary")

            for k, v in vals.items():
                if guf.empty(v) or guf.is_bad_null(v):
                    html = f'<span class="table">{table}</span>, field <span class="field">{field}</span>'
                    if field.lower() in ["fieldid"]:
                        warnings.append(html)
                    else:
                        errors.append(html)

    missing_required_values.extend(list(set(errors)))
    missing_warnings.extend(list(set(warnings)))

    return missing_required_values, missing_warnings


def rule3_5_and_7(db_dict, table, all_vals):
    """3.5 No unnecessary terms in Glossary
    3.7 No unnecessary sources in DataSources"""
    if table == "glossary":
        terms = set(values(db_dict, "Glossary", "Term", "list"))
        unused = [
            "unnecessary term(s) in Glossary",
            "3.5 Terms in Glossary that are not used in geodatabase",
            "UnusedTerms",
        ]

    elif table == "datasources":
        terms = set(values(db_dict, "DataSources", "DataSources_ID", "list"))
        unused = [
            "unused source(s) in DataSources",
            "3.7 DataSources_IDs in DataSources that are not used in geodatabase",
            "UnusedSources",
        ]

    unused.extend(list(terms - set(all_vals)))

    return unused


def piped(s, chrs):
    # replace multiple delimiters with pipe
    for c in chrs:
        if c in s:
            s = s.replace(c, "|")

    return s


def rule3_10(db_dict):
    """HierarchyKey values in DescriptionOfMapUnits are unique and well formed"""
    hkey_errors = [
        "HierarchyKey error(s) in DMU",
        "3.10 HierarchyKey errors",
        "hkey_errors",
    ]

    hkey_warnings = ["Hierarchy keys"]

    # dictionary of hkey values [oid]: hkey
    hk_dict = values(db_dict, "DescriptionOfMapUnits", "HierarchyKey", "dictionary")

    # return early if HKs is empty
    if not hk_dict:
        hkey_errors.append("No HierarchyKey values")
        return hkey_errors

    # check for empty values
    id_fld = which_id(db_dict, "DescriptionOfMapUnits")
    for k, v in hk_dict.items():
        if guf.empty(v):
            hkey_errors.append(
                f'{id_fld} {k} has no <span class="field">HierarchyKey</span> value'
            )

    # find the delimiter
    # make a list of all non-alphanumeric characters found in all hkeys
    # if the length of the list is not 1, there are multiple delimiters.
    # list of just the hkeys
    delims = []
    for hkey in hk_dict.values():
        if not guf.empty(hkey):
            for c in hkey:
                delims.extend([c for c in hkey if c.isalnum() == False])
    delims = list(set(delims))

    frag_lengths = []
    id_fld = which_id(db_dict, "DescriptionOfMapUnits")
    if delims:
        # dealing with a list of character-delimited keys
        # look for multiple delimiters
        if len(delims) > 1:
            formatted = [f"<code>{c}</code>" for c in delims]
            hkey_errors.append(f'Multiple delimiters found: {", ".join(formatted)}')

        # turn each hk_dict value into a tuple (piped hkey, original hkey)
        piped_dict = {
            k: (piped(v, delims), v) for k, v in hk_dict.items() if not guf.empty(v)
        }

        # find duplicated pipe delim keys
        pipe_keys = [v[0] for v in piped_dict.values()]
        dupe_pipes = [hk for hk in pipe_keys if pipe_keys.count(hk) > 1]
        dupe_pipes = set(dupe_pipes)

        # iterate through dictionary items
        for k, v in piped_dict.items():
            new_key = v[0]
            old_key = v[1]
            # check for duplicated key
            if new_key in dupe_pipes:
                hkey_errors.append(
                    f"{id_fld} {k} has duplicated key: {old_key} (ignore delimiter)"
                )

            # collect fragment length
            for frag in new_key.split("|"):
                if frag:
                    frag_lengths.append(len(frag))

                # look for non-numeric characters
                for c in frag if c != "|" else c:
                    if c.isnumeric() == False:
                        hkey_warnings.append(
                            f"""{id_fld} {k}: <span class="value">{old_key}</span> 
                            includes non-numeric character span class="value">{c}</span>. Please check!"""
                        )
    else:
        # dealing with a list of integers or single fragment values, that is,
        # hkey values are not materialized paths, just numbers; 1,2,3,4...
        # or 001, 002, 003

        # look for duplicates
        hks = list(hk_dict.values())
        dupes = [hk for hk in hks if hks.count(hk) > 1]
        dupes = set(dupes)

        # itrate through dictionary
        for oid, hkey in hk_dict.items():
            # look for duplicates
            if hkey in dupes:
                hkey_errors.append(f"{id_fld} {oid} has duplicated key: {hkey}")

            # look for non-numeric characters
            for c in hkey:
                if c.isnumeric == False:
                    hkey_warnings.append(
                        f"""<span class="tab"></span>{id_fld} {oid}: <span class="value">{hkey}</span> 
                        includes non-numeric character <span class="value">{c}</span>. Please check!"""
                    )

            # collect hkey length
            if hkey:
                frag_lengths.append(len(hkey))

    # evaluate lengths
    frag_lengths = set(frag_lengths)
    if len(frag_lengths) != 1:
        hkey_warnings.append(
            "Hierarchy keys/fragments are of inconsistent length. Please check!"
        )

    return hkey_errors, hkey_warnings


def rule3_11(db_dict, ref_gmd):
    """All values of GeoMaterial are defined in GeoMaterialDict."""
    # return early if there is no GeoMaterialsDict
    ref_gmd = str(ref_gmd)
    gdb_gmd = db_dict["GeoMaterialDict"]["catalogPath"]

    if not "GeoMaterialDict" in db_dict:
        errors = '<span class="table">GeoMaterialDict</span> not found! See Rule 2.1'
        return errors

    errors = [
        "GeoMaterial error(s)",
        "3.11 GeoMaterial Errors - not found in GeoMaterialsDict or GeoMaterialsDict does not meet standard",
        "gmErrors",
    ]

    # look for null values in GeoMaterialDict
    flds = ["HierarchyKey", "GeoMaterial", "IndentedName", "Definition"]
    with arcpy.da.SearchCursor(gdb_gmd, flds) as cursor:
        for row in cursor:
            if any(n is None for n in row):
                errors.append(
                    f'There are null values in <span class="table">GeoMaterialDict</span>. Check "Refresh GeoMaterial Dict" on next validation'
                )
                return errors

    # compare ref_gmd with gdb_gmd
    ref_gmd_dict = {
        # r[0].lower().strip(): r[1].lower().strip()
        r[0]: r[1]
        for r in arcpy.da.SearchCursor(ref_gmd, ["GeoMaterial", "Definition"])
    }
    gdb_gmd_dict = {
        # r[0].lower().strip(): r[1].lower().strip()
        r[0]: r[1]
        for r in arcpy.da.SearchCursor(gdb_gmd, ["GeoMaterial", "Definition"])
    }
    for k, v in gdb_gmd_dict.items():
        if k:
            # is the geomaterial in ref_gmd?
            if k.lower().strip() in [n.lower().strip() for n in ref_gmd_dict.keys()]:
                if v:
                    # is the definition correct?
                    if not v.lower().strip() == ref_gmd_dict[k].lower().strip():
                        html = f'Definition of <span class="value">{k}</span> does not match GeMS standard'
                        errors.append(html)
                else:
                    html = f'Definition for <span class="value">{k}</span> is missing. Check "Refresh GeoMaterial Dict" on next validation.'
                    errors.append(html)

            else:
                html = f"""<span class="value">{k}</span> in <span class="table">GeoMaterialDict</span> is not a valid GeoMaterial. 
                Check "Refresh GeoMaterial Dict" on next validation and update any tables using this geomaterial."""
                errors.append(html)

    # compare geomaterials in the tables to ref_gmd
    # exclude some gdb objects to look for GeoMaterial field
    db_tables = [
        k
        for k, v in db_dict.items()
        if any(v["concat_type"].endswith(n) for n in ("Table", "Feature Class"))
        and not k == "GeoMaterialDict"
        and not "Annotation" in v["concat_type"]
    ]

    # list of tables that do have a GeoMaterial field
    geomat_tables = []
    for table in db_tables:
        for f in [f.name for f in db_dict[table]["fields"]]:
            if "GeoMaterial" in f:
                geomat_tables.append(table)

    # iterate through those tables
    msgs = []
    # list of reference geomaterials
    ref_geomats = [
        r[0].lower().strip() for r in arcpy.da.SearchCursor(ref_gmd, "GeoMaterial")
    ]
    for table in geomat_tables:
        # list of GeoMaterials in the table
        tbl_geomats = list(set(values(db_dict, table, "GeoMaterial", "list")))
        if None in tbl_geomats:
            tbl_geomats = list(filter(None, tbl_geomats))
        if tbl_geomats:
            for geomat in tbl_geomats:
                if not geomat.lower().strip() in ref_geomats and not guf.empty(geomat):
                    html = f'<span class="value">{geomat}</span> in <span class="table">{table}</span> is not a valid GeoMaterial'
                    msgs.append(html)
    if msgs:
        msgs = list(set(msgs))
        errors.extend(msgs)

    return errors


def rule3_12(db_dict):
    """No duplicate _ID values"""
    duplicate_ids = [
        "duplicated _ID value(s)",
        "3.12 Duplicated _ID Values",
        "duplicate_ids",
    ]
    id_tables = []
    db_tables = [
        k
        for k, v in db_dict.items()
        if any(v["concat_type"].endswith(n) for n in ("Table", "Feature Class"))
        and not k == "GeoMaterialDict"
        and not "Annotation" in v["concat_type"]
    ]
    for table in db_tables:
        for f in [f.name for f in db_dict[table]["fields"]]:
            if f == f"{table}_ID":
                id_tables.append(table)

    all_ids = []
    for table in id_tables:
        table_path = db_dict[table]["catalogPath"]
        # need a tuple here because duplicated keys added to a dictionary
        # are ignored. need to look for duplicate (_ID Value: table) pairs.
        # that is, we won't use the values() method here like in other functions
        table_ids = [
            (r[0], table)
            for r in arcpy.da.SearchCursor(table_path, f"{table}_ID")
            if r[0]
        ]
        all_ids.extend(table_ids)
        dup_ids = list(set([id for id in all_ids if all_ids.count(id) > 1]))

    if dup_ids:
        to_html = [
            f'<span class="value">{d[0]}</span> in table <span class="table">{d[1]}</span>'
            for d in dup_ids
        ]
        duplicate_ids.extend(to_html)

    return duplicate_ids


def rule3_13(db_dict):
    """No zero-length or whitespace-only strings"""
    zero_length_strings = [
        "zero-length or whitespace string(s)",
        "3.13 Zero-length, whitespace-only, or bad null value",
        "zero_length_strings",
    ]

    leading_trailing_spaces = ["Text values with leading or trailing spaces:"]

    tables = [
        k
        for k, v in db_dict.items()
        if any(v["concat_type"].endswith(n) for n in ("Table", "Feature Class"))
        and not k == "GeoMaterialDict"
        and not "Annotation" in v["concat_type"]
    ]
    for table in tables:
        id_fld = which_id(db_dict, table)
        text_fields = [f.name for f in db_dict[table]["fields"] if f.type == "String"]
        for field in text_fields:
            val_dict = values(db_dict, table, field, "dictionary")
            for k, v in val_dict.items():
                if v:
                    if v.isspace() or v.lower() in ("&ltnull&gt", "<null>", ""):
                        html = f'<span class="table">{table}</span>, field <span class="field"> {field}</span>, {id_fld} {str(k)}'
                        zero_length_strings.append(html)

            # also collect leading_trailing_spaces for 'other stuff' report
            for n in [
                k for k, v in val_dict.items() if v and (len(v.strip()) != len(v))
            ]:
                html = f'<span class="table">{table}</span>, field <span class="field"> {field}</span>, {id_fld} {str(n)}'
                leading_trailing_spaces.append(html)

    return zero_length_strings, leading_trailing_spaces


def validate_online(metadata_file, workdir):
    """validate the xml metadata against the USGS metadata validation service API"""

    metadata_name = metadata_file.stem
    # metadata_dir = metadata_file.parent
    metadata_errors = workdir / f"{metadata_name}_errors.txt"

    # send the temp file to the API
    url = r"https://www1.usgs.gov/mp/service.php"
    try:
        with open(metadata_file, "rb") as f:
            r = requests.post(url, files={"input_file": f})
    except:
        message = "Could not connect to the metadata validation service. Check your internet connection and try again."
        ap(message)

        return False, message

    if r.ok:
        links = r.json()["output"]["link"]
        errors = requests.get(links["error_txt"])
        with open(metadata_errors, "wt") as f:
            for line in errors.iter_lines():
                if not b"appears in unexpected order within" in line:
                    f.write(f"{line.decode('utf-8')}\n")

        summary = r.json()["summary"]
        if "No errors" in summary:
            message = f"""The database-level FGDC metadata are <a href="{metadata_errors.name}">formally correct</a> 
                although the metadata record should be reviewed to verify that it is meaningful.<br>"""
            ap("The metadata for this record are formally correct.")
        else:
            message = f'The metadata record for this database has <a href="{str(metadata_errors.name)}">formal errors</a>. Please fix!<br>'
            ap(f"The metadata record for this database has errors. Please fix!")
    else:
        message = (
            "There was a problem with the connection to the metadata validation service:<br>"
            + r.reason
        )
        ap(message)

    return message


def write_html(template, out_file):
    """Writes either the Validation or ValidationErrors file sending the val{}
    dictionary as parameter
    """
    environment = Environment(loader=FileSystemLoader(scripts_dir))
    validation_template = environment.get_template(template)
    with open(out_file, mode="w", encoding="utf-8") as results:
        results.write(validation_template.render(val=val))


def determine_level(val):
    """Determine level of compliance of the database depending on the length of
    lists built for each of the rules. Must equal 3 items long to pass"""
    level2 = False
    level3 = False

    if all(len(n) == 3 for n in [val[f"rule2_{i}"] for i in range(1, 9)]):
        level2 = True
    if all(len(n) == 3 for n in [val[f"rule3_{i}"] for i in range(1, 13)]):
        level3 = True

    if level2 and level3:
        level = 'This database is <a href=#Level3><font size="+1"><b>LEVEL 3 COMPLIANT.</b></a></font>\n'
    elif level2:
        level = 'This database is <a href=#Level2><font size="+1"><b>LEVEL 2 COMPLIANT.</b></a></font>\n'
    else:
        level = 'This database may be <a href=#Level1><font size="+1"><b>LEVEL 1 COMPLIANT.</b></a></font>\n'

    return level


def extra_tables(db_dict, schema_extensions):
    """Find extensions to GeMS by looking at the gems_equivalent entry in the
    database dictionary. If blank, it is an extension"""
    schema_extensions.append("<h4>Tables</h4>")
    extras = [
        k
        for k, v in db_dict.items()
        if v["gems_equivalent"] == ""
        or v["gems_equivalent"] in ["GenericSamples", "GenericPoints"]
        and not "Annotation" in v["concat_type"]
        and any(n in v["concat_type"] for n in ("Feature Class", "Table"))
    ]
    if extras:
        for table in extras:
            schema_extensions.append(
                f'<span class="tab"></span><span class="table">{table}</span>'
            )

    return schema_extensions


def sort_fds_units(fds_map_units):
    """Makes sure that units from the DMU are listed first (left to right) in the table of
    MapUnit occurrences"""
    new_dict = {}
    keys = [k for k in fds_map_units.keys()]
    if "DMU" in fds_map_units.keys():
        keys.remove("DMU")
        keys.sort()
        new_dict["DMU"] = fds_map_units["DMU"]

    if keys:
        for k in keys:
            new_dict[k] = fds_map_units[k]

    return new_dict


def build_tr(db_dict, tb):
    table = [
        '<table class="ess-tables">',
        "<thead>",
        "<tr>",
    ]
    fields = [
        f.name for f in db_dict[tb]["fields"] if not f.name in gdef.standard_fields
    ]
    # standard_fields includes OBJECTID, so generator excludes it
    # but we do want it in the table, insert it back into 0 index.
    fields.insert(0, "OBJECTID")
    for f in fields:
        table.append(f"<th>{f}</th>")

    table.append("<//tr>")
    table.append("<//thead>")

    if tb == "DescriptionOfMapUnits":
        sql = (None, "Order By HierarchyKey Asc")
    elif tb == "Glossary":
        sql = (None, "Order By Term Asc")
    elif tb == "DataSources":
        sql = (None, "Order By DataSources_ID Asc")
    else:
        sql = (None, None)

    with arcpy.da.SearchCursor(
        db_dict[tb]["catalogPath"], fields, sql_clause=sql
    ) as cursor:
        for row in cursor:
            table.append("<tr>")
            for val in row:
                table.append(f"<td>{val}<//td>")
            table.append("<//tr>")

    table.append("</table>")
    table.append("</div>")

    return "".join(table)


def dump_tables(db_dict):
    non_spatial = {}
    tables = [
        k
        for k, v in db_dict.items()
        if v["concat_type"] == "Nonspatial Table" and not k == "GeoMaterialDict"
    ]
    tables.sort()
    for t in tables:
        non_spatial[t] = build_tr(db_dict, t)

    return non_spatial


def raster_size(db_dict, name):
    n = db_dict[name]
    width = int(n["width"])
    bands = int(n["bandCount"])
    height = int(n["height"])
    depth = n["pixelType"]
    depth = "".join(ch for ch in depth if ch.isdigit())
    depth = int(depth) / 8
    kb = width * height * depth * bands / 1000
    return int(kb)


def inventory(db_dict):
    # build inventory
    inv_list = []

    # first list nonspatial tables
    tbs = [k for k, v in db_dict.items() if v["concat_type"] == "Nonspatial Table"]
    tbs.sort()
    for tb in tbs:
        n_type = db_dict[tb]["concat_type"].lower()
        count = arcpy.GetCount_management(db_dict[tb]["catalogPath"])
        inv_list.append(f"{tb}, {n_type}, {count} rows")

    # list feature datasets and children
    fds = [k for k, v in db_dict.items() if v["concat_type"] == "Feature Dataset"]
    for fd in fds:
        inv_list.append(f"{fd}, feature dataset")
        children = db_dict[fd]["children"]
        if len(children) > 0:
            for child in children:
                tbs.append(child["name"])
                n_type = child["concat_type"].lower()
                if any(w in n_type for w in ("feature class", "table")):
                    count = arcpy.GetCount_management(child["catalogPath"])
                    inv_list.append(
                        f'<span class="tab"></span>{child["name"]}, {n_type}, {count} rows'
                    )
                else:
                    inv_list.append(
                        f'<span class="tab"></span>{child["name"]}, {n_type}'
                    )

    # list anything else
    els = [
        k
        for k, v in db_dict.items()
        if not v["concat_type"] in ("Feature Dataset", "Raster Band") and not k in tbs
    ]
    for el in els:
        n_type = db_dict[el]["concat_type"].lower()
        if any(w in n_type for w in ("feature class", "table")):
            count = arcpy.GetCount_management(db_dict[el]["catalogPath"])
            inv_list.append(f"{el}, {n_type}, {count} rows")
        elif n_type == "raster dataset":
            size = raster_size(db_dict, el)
            inv_list.append(f"{el}, {n_type}, aprx. {size} kb uncompressed size")
        else:
            inv_list.append(f"{el}, {n_type}")

    return inv_list


def del_extra(db_dict, table, field, all_terms):
    with arcpy.da.UpdateCursor(db_dict[table]["catalogPath"], field) as cursor:
        for row in cursor:
            if not row[0] in all_terms:
                cursor.deleteRow()


##############start here##################
# get inputs
def main(argv):
    val["parameters"] = ["Runtime parameters"]
    guf.checkVersion(version_string, rawurl, "gems-tools-pro")
    args_len = len(argv)

    # we already know argv[1] exists, no check
    gdb_path = Path(argv[1])
    val["parameters"].append(f"Database path: {gdb_path}")
    gdb_name = gdb_path.name
    # val["db_path"] = gdb_path
    val["db_name"] = gdb_name

    # bail early if we don't have a gdb or gpkg
    if gdb_path.suffix not in [".gdb", ".gpkg"]:
        ap("This tool only validates File Geodatabases or Geopackages.")
        guf.forceExit()

    # are we working with a geopackage?
    if gdb_path.suffix == ".gpkg":
        is_gpkg = True
    else:
        is_gpkg = False

    # output folder
    if 2 < args_len:
        if Path(argv[2]).exists():
            workdir = Path(argv[2])
        else:
            workdir = gdb_path.parent / "validate"
            workdir.mkdir(exist_ok=True)
    else:
        workdir = gdb_path.parent / "validate"
        workdir.mkdir(exist_ok=True)
    val["parameters"].append(f"Output directory: {workdir}")

    # path to metadata file
    metadata_file = None
    if 3 < args_len:
        if not Path(argv[3]).suffix == ".xml":
            ap("Metadata not checked. File needs to be in XML format.")

        if Path(argv[3]).suffix == ".xml" and Path(argv[3]).exists():
            metadata_file = Path(argv[3])

    arc_md = False
    if 4 < args_len:
        arc_md = guf.eval_bool(argv[4])
        if arc_md:
            metadata_file = workdir / f"{gdb_name}_metadata.xml"

    val["parameters"].append(f"Metadata file: {metadata_file}")
    val["parameters"].append(f"Check embedded metadata: {arc_md}")
    # val["metadata_file"] = str(metadata_file)
    val["metadata_name"] = metadata_file.name if metadata_file else "valid metadata"
    val["md_errors_name"] = (
        f"{metadata_file.name}_errors.txt"
        if metadata_file
        else "a metadata summary from mp"
    )

    # use _ID field value instead of OBJECTID for reporting errors?
    global use_idfield
    if 5 < args_len:
        use_idfield = guf.eval_bool(argv[5])
    else:
        use_idfield = False

    # skip topology?
    if 6 < args_len:
        skip_topology = guf.eval_bool(argv[6])
        top_db = workdir / "Topology.gdb"
        if arcpy.Exists(str(top_db)):
            arcpy.Delete_management(str(top_db))
    else:
        skip_topology = False
    val["parameters"].append(f"Skip topology check: {skip_topology}")

    # refresh GeoMaterialDict?
    if 7 < args_len:
        refresh_gmd = guf.eval_bool(argv[7])
    else:
        refresh_gmd = False
    val["parameters"].append(f"Refresh GeoMaterialDict: {refresh_gmd}")

    # delete extra rows in Glossary and Data Sources?
    if 8 < args_len:
        delete_extra = guf.eval_bool(argv[8])
    else:
        delete_extra = False
    val["parameters"].append(
        f"Delete extra rows in Glossary and DataSources: {delete_extra}"
    )

    # compact database?
    if 9 < args_len:
        compact_db = guf.eval_bool(argv[9])
    else:
        compact_db = False
    val["parameters"].append(f"Compact GDB: {compact_db}")

    # open html report when done?
    if 10 < args_len:
        open_report = guf.eval_bool(argv[10])
    else:
        open_report = False

    val["report_path"] = workdir / f"{gdb_name}-Validation.html"
    val["report_name"] = f"{gdb_name}-Validation.html"
    val["errors_name"] = f"{gdb_name}-ValidationErrors.html"
    val["errors_path"] = str(workdir / f"{gdb_name}-ValidationErrors.html")

    # make the database dictionary
    db_dict = guf.gdb_object_dict(str(gdb_path))

    # edit session?
    if guf.editSessionActive(gdb_path):
        arcpy.AddWarning(
            "\nDatabase is being edited. Results may be incorrect if there are unsaved edits\n"
        )

    # appear to have a good database, proceed
    # refresh geomaterial
    geo_material_errors = [
        "Errors associated with GeoMaterialDict and GeoMaterial values"
    ]
    ref_gmd = scripts_dir / "GeoMaterialDict.csv"
    if refresh_gmd:
        if not arcpy.Exists(ref_gmd):
            ap(f"Cannot find reference GeoMaterialDict table at {str(ref_gmd)}")
            geo_material_errors.append(
                "\nGeoMaterialDict.csv is missing from scripts folder"
            )
        else:
            ap("Refreshing GeoMaterialDict")
            gmd = gdb_path / "GeoMaterialDict"
            guf.testAndDelete(str(gmd))
            arcpy.conversion.TableToTable(
                str(ref_gmd), str(gdb_path), "GeoMaterialDict"
            )

            if not is_gpkg:
                ap("Replacing GeoMaterial domain")
                arcpy.management.TableToDomain(
                    str(ref_gmd),
                    "GeoMaterial",
                    "IndentedName",
                    str(gdb_path),
                    "GeoMaterials",
                    "",
                    "REPLACE",
                )

                ap("Assigning domain to GeoMaterial")
                dmu_path = db_dict["DescriptionOfMapUnits"]["catalogPath"]
                dmu_fields = db_dict["DescriptionOfMapUnits"]["fields"]
                for f in dmu_fields:
                    if f.name == "GeoMaterial" and not f.domain == "GeoMaterials":
                        arcpy.management.AssignDomainToField(
                            dmu_path, f.name, "GeoMaterials"
                        )
    val["gm_errors"] = geo_material_errors

    # look for geodatabase version
    # not implemented yet
    if "PublicationTable" in db_dict.keys():
        ver_table = db_dict["Version"]["catalogPath"]
        result = arcpy.GetCount_management(ver_table)
        if result[0] == 1:
            gdb_ver = f" version {[row[0] for row in arcpy.da.SearchCursor(ver_table, 'Version')]}"
        else:
            gdb_ver = ""

    # level 2 compliance
    ap("\u200B")
    ap("Looking at level 2 compliance")
    # check 2.1
    ap(
        """Rule 2.1 - Has required elements: nonspatial tables DataSources, 
        DescriptionOfMapUnits, GeoMaterialDict; feature dataset GeologicMap with 
        feature classes ContactsAndFaults and MapUnitPolys"""
    )
    rule2_1_results = rule2_1(db_dict, is_gpkg)
    val["rule2_1"] = rule2_1_results[0]
    val["sr_warnings"] = rule2_1_results[2]

    # rule 2.2
    # Required fields within required elements are present and correctly defined
    ap(
        "Rule 2.2 - Required fields within required elements are present and correctly defined"
    )
    schema_extensions = []
    # fld_warnings is not getting defined right now. Should we use it?
    val["rule2_2"], schema_extensions, fld_warnings = check_fields(
        db_dict, 2, schema_extensions
    )

    # rule 2.3 topology
    ap(
        """2.3 All MapUnitPolys and ContactsAndFaults based feature classes obey Level 2 topology rules: 
        no internal gaps or overlaps in MapUnitPolys, boundaries of MapUnitPolys are covered by ContactsAndFaults"""
    )

    if skip_topology:
        level_2_errors = ["Topology check was skipped"]
        level_3_errors = ["Topology check was skipped"]
        ap("Topology check was skipped")
    elif not rule2_1_results[1]:
        level_2_errors = [
            "No MapUnitPolys and ContactAndFaults pairs on which to check topology",
            None,
        ]
        level_3_errors = [
            "No MapUnitPolys and ContactAndFaults pairs on which to check topology",
            None,
        ]
        ap("No MapUnitPolys and ContactAndFaults pairs on which to check topology")
    else:
        # returns (level_2_errors, level_3_errors
        topo_results = check_topology(db_dict, workdir, is_gpkg, rule2_1_results[1])
        level_2_errors = topo_results[0]
        level_3_errors = topo_results[1]

    val["rule2_3"] = level_2_errors

    # rule 2.4
    # All map units in MapUnitPolys have entries in DescriptionOfMapUnits table
    # make a list of MapUnits found in the DMU
    # dmu_units = values("DescriptonOfMapUnits", "MapUnit", "list")
    ap("2.4 All map units in MapUnitPolys have entries in DescriptionOfMapUnits table")
    all_map_units = []
    fds_map_units = {}
    val["rule2_4"], all_map_units, fds_map_units = check_map_units(
        db_dict, 2, all_map_units, fds_map_units
    )

    # rule 2.5
    # No duplicate MapUnit values in DescriptionOfMapUnit table
    ap("2.5 No duplicate MapUnit values in DescriptionOfMapUnits table")
    dmu_map_units_duplicates = [
        "duplicated MapUnit(s) in DMU",
        "Duplicated MapUnit values in DescriptionOfMapUnits",
        "DuplicatedMU",
    ]
    dmu_path = db_dict["DescriptionOfMapUnits"]["catalogPath"]
    dmu_map_units_duplicates.extend(guf.get_duplicates(dmu_path, "MapUnit"))
    val["rule2_5"] = dmu_map_units_duplicates

    # rule 2.6
    # Certain field values within required elements have entries in Glossary table
    ap(
        "2.6 Certain field values within required elements have entries in Glossary table"
    )
    all_gloss_terms = []
    val["rule2_6"], all_gloss_terms = glossary_check(db_dict, 2, all_gloss_terms)

    # rule 2.7
    # No duplicate Term values in Glossary table
    ap("2.7 No duplicate Term values in Glossary table")
    glossary_term_duplicates = [
        "duplicated terms in Glossary",
        "2.7 Duplicated terms in Glossary",
        "DuplicatedTerms",
    ]
    gloss_path = db_dict["Glossary"]["catalogPath"]
    glossary_term_duplicates.extend(guf.get_duplicates(gloss_path, "Term"))
    val["rule2_7"] = glossary_term_duplicates

    # rule 2.8
    # All xxxSourceID values in required elements have entries in DataSources table
    ap(
        "2.8 All xxxSourceID values in required elements have entries in DataSources table"
    )
    all_sources = []
    val["rule2_8"], all_sources = sources_check(db_dict, 2, all_sources)

    # rule 2.9
    # No duplicate DataSources_ID values in DataSources table
    ap("2.9 No duplicate DataSources_ID values in DataSources table")
    duplicated_source_ids = [
        "duplicated source IDs in DataSources",
        "Duplicated source_IDs in DataSources",
        "DuplicatedIDs",
    ]
    ds_path = db_dict["DataSources"]["catalogPath"]
    duplicated_source_ids.extend(guf.get_duplicates(ds_path, "DataSources_ID"))
    val["rule2_9"] = duplicated_source_ids

    ap("\u200B")
    ap("Looking at level 3 compliance")
    # rule 3.1
    # Table and field definitions conform to GeMS schema
    ap("3.1 Table and field definitions conform to GeMS schema")
    val["rule3_1"], schema_extensions, val["fld_warnings"] = check_fields(
        db_dict, 3, schema_extensions
    )

    # rule 3.2
    ap(
        """3.2 All MapUnitPolys and ContactsAndFaults based feature classes obey Level 3 topology rules: 
        no ContactsAndFaults overlaps, self-overlaps, or self-intersections."""
    )
    val["rule3_2"] = level_3_errors

    # rule 3.3
    # No missing required values
    ap("3.3 No missing required values")
    val["rule3_3"], val["missing_warnings"] = rule3_3(db_dict)

    # rule 3.4
    # No missing terms in Glossary
    ap("3.4 No missing terms in Glossary")
    val["rule3_4"], all_gloss_terms, val["term_warnings"] = glossary_check(
        db_dict, 3, all_gloss_terms
    )

    # rule 3.5
    # No unnecessary terms in Glossary
    ap("3.5 No unnecessary terms in Glossary")
    if delete_extra:
        ap("\tRemoving unused terms from Glossary")
        del_extra(db_dict, "Glossary", "Term", all_gloss_terms)

    val["rule3_5"] = rule3_5_and_7(db_dict, "glossary", all_gloss_terms)

    # rule 3.6
    # No missing sources in DataSources
    ap("3.6 No missing sources in DataSources")
    val["rule3_6"], all_sources = sources_check(db_dict, 3, all_sources)

    # rule 3.7
    # No unnecessary sources in DataSources
    ap("3.7 No unnecessary sources in DataSources")

    if delete_extra:
        ap("\tRemoving unused sources from DataSources")
        del_extra(db_dict, "DataSources", "DataSources_ID", all_sources)

    val["rule3_7"] = rule3_5_and_7(db_dict, "datasources", all_sources)

    # rule 3.8
    # No map units without entries in DescriptionOfMapUnits
    # rule 3.9
    # No unnecessary map units in DescriptionOfMapUnits
    ap("3.8 No map units without entries in DescriptionOfMapUnits")
    ap("3.9 No unnecessary map units in DescriptionOfMapUnits")
    (
        val["rule3_8"],
        val["rule3_9"],
        all_map_units,
        fds_map_units,
        val["mu_warnings"],
    ) = check_map_units(db_dict, 3, all_map_units, fds_map_units)

    # rule 3.10
    # HierarchyKey values in DescriptionOfMapUnits are unique and well formed
    ap("3.10 HierarchyKey values in DescriptionOfMapUnits are unique and well formed")
    val["rule3_10"], val["hkey_warnings"] = rule3_10(db_dict)
    # 3.11
    # All values of GeoMaterial are defined in GeoMaterialDict.
    ap(
        "3.11 All values of GeoMaterial are defined in GeoMaterialDict. GeoMaterialDict is as specified in the GeMS standard"
    )
    val["rule3_11"] = rule3_11(db_dict, ref_gmd)

    # 3.12
    # No duplicate _ID values
    ap("3.12 No duplicate _ID values")
    val["rule3_12"] = rule3_12(db_dict)

    # 3.13
    # No zero-length or whitespace-only strings
    ap("3.13 No zero-length or whitespace-only strings")
    val["rule3_13"], val["end_spaces"] = rule3_13(db_dict)

    # check for editor tracking
    val["et_warnings"] = ["Editor tracking enabled on:"]
    for k, v in db_dict.items():
        if "editorTrackingEnabled" in v:
            if v["editorTrackingEnabled"]:
                html = f'<span class="table">{k}</span>'
                val["et_warnings"].append(html)

    # METADATA
    if arc_md:
        ap("Exporting embedded ArcGIS metadata to FGDC")
        # export the metadata from Arc
        # this method only exports good metadata if it has been written in ArcCatalog at the
        # gdb level or imported from an xml such as that produced at the end of Build Metadata.
        src_md = arcpy.metadata.Metadata(str(gdb_path))
        src_md.exportMetadata(str(metadata_file), "FGDC_CSDGM")

    if metadata_file:
        if Path(metadata_file).exists:
            md_summary = validate_online(metadata_file, workdir)
        else:
            md_summary = f"{metadata_file} does not exist."
    else:
        ap("Check Metadata option was skipped")
        md_summary = "<b>Check Metadata</b> option was skipped. Be sure to have prepared valid metadata and check this option to produce a complete report."

    # now that rules have been checked, prepare some summary entries
    val["metadata_summary"] = md_summary
    val["level"] = determine_level(val)

    ap("\u200B")
    ap("Inventorying database:")
    # other stuff
    # find extensions to schema
    ap("\tLooking for extensions to GeMS schema")
    val["extras"] = extra_tables(db_dict, schema_extensions)

    # prepare lists of units for Occurrence table
    ap("\tFinding occurrences of map units")
    all_map_units.sort()
    val["all_units"] = list(set(all_map_units))
    fds_map_units = sort_fds_units(fds_map_units)
    val["fds_units"] = fds_map_units

    # prepare contents of non-spatial tables
    ap("\tStoring contents of non-spatial tables")
    val["non_spatial"] = dump_tables(db_dict)

    # build inventory
    ap("\tBuilding database inventory")
    val["inventory"] = inventory(db_dict)

    ### Compact DB option
    if compact_db == "true":
        ap("\u200B")
        ap(f"Compacting {gdb_name}")
        arcpy.Compact_management(gdb_path)
    else:
        pass

    write_html("report_template.jinja", val["report_path"])
    write_html("errors_template.jinja", val["errors_path"])

    if open_report:
        os.startfile(val["report_path"])

    ap("DONE")


if __name__ == "__main__":
    main(sys.argv)
