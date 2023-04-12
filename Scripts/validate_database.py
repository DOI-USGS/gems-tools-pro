# -*- coding: utf-8 -*-
"""Validate Database

Audits a geodatabase for conformance with the GeMS schema and reports compliance 
as "may be LEVEL 1 COMPLIANT", "is LEVEL 2 COMPLIANT", or "is LEVEL 3 COMPLIANT". 
It also runs mp (metadata parser) to check for formal errors in geodatabase-level 
FGDC metadata. Note that to qualify as LEVEL 2 or LEVEL 3 compliant a database must 
also be accompanied by a peer-reviewed geologic names report.

Usage:
    Use parameter form in ArcGIS Pro or at command line with the arguments below. 
    Use '' or '#' for optional arguments that are not required.
    Use 'true' or 'false' for boolean values per ArcGIS Pro parameter form values
    
Args:
    gdb_path (str) : Path to database. Required.
    workdir (str) : Path to output directory. Optional but if not supplied, a 
      folder called 'validate' will be created in the parent folder of the database.
    metadata_file (str) : Path to metadata file to validate. Optional. Previous
      versions of this tool validated embedded metadata. If left blank, no meta-
      data at all will be validated.
    skip_topology (str) : True or false whether checking topology should be 
      skipped.
    refresh_gmd (str) : True or false whether the GeoMaterialDict
      table in the database should be re-written to the latest required version.
    delete_extra (str) : True or false whether to delete unused rows in 
      DataSources and Glossary.
    compact_db (str) : True or false whether to compact the file geodatabase.
      Not applicable to geopackages. 
      
Returns:
    <gdb name>-Validation.html (file) : Reports level of 
      compliance, lists errors and warnings. Written to workdir. 
    <gdb name>-ValidationErrors.html (file) : Detailed list of errors and warnings
      by table, field, ObjectID, etc. Written to workdir.
    <gdb name>_Validation.gdb (file gdb)
    

https://google.github.io/styleguide/pyguide.html#316-naming

module_name, package_name, ClassName, method_name, ExceptionName, function_name, 
GLOBAL_CONSTANT_NAME, global_var_name, instance_var_name, function_parameter_name, 
local_var_name, query_proper_noun_for_thing, send_acronym_via_https
"""

# every level 2 or 3 errors list needs to contain
# [the message that will appear in the pass/fail cell of -Validation.html file if the rule fails,
# the header for the rule section in -ValidationErrors.html file,
# the name of the anchor in the -ValidationErrors file for the rule,
# error1, error2, error3, errori...]
# val dictionary entries for specific entries take the form of
# [message in the pass/fail cell in -Validation, header for the list of errors
# in -ValidationErrors, html anchor]
# unless there is an error that precludes the listing of errors, for example,
# without a MapUnitPolys feature class there can be no topology errors.
# In that case, the entry has only one item in the list and it is only reported
# in -Validation.html

import arcpy
import os
import sys
import time
from pathlib import Path
import GeMS_utilityFunctions as guf
import GeMS_Definition as gdef
import topology as tp
import requests
from jinja2 import Environment, FileSystemLoader

from importlib import reload

reload(gdef)
reload(tp)

val = {}

version_string = "validate_database.py, version of 24 March 2023"
val["version_string"] = version_string
val["datetime"] = time.asctime(time.localtime(time.time()))

rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_ValidateDatabase_AGP2.py"

py_path = __file__
scripts_dir = Path.cwd()
toolbox_path = scripts_dir.parent
resources_path = toolbox_path / "Resources"

ap = guf.addMsgAndPrint

lc_standard_fields = []
for f in gdef.standard_fields:
    lc_standard_fields.append(f.lower())

metadata_checked = False  # script will set to True if metadata record is checked


def check_sr(db_obj):
    sr_warnings = []
    sr = db_dict[db_obj]["spatialReference"]

    # check for NAD83 or WGS84
    if sr.type == "Geographic":
        pcsd = sr.datumName
    else:  # is projected
        pcsd = sr.PCSName
    if pcsd.find("World_Geodetic_System_1984") < 0 and pcsd.find("NAD_1983") < 0:
        sr_warnings.append(
            f"Spatial reference framework of {db_obj} is {pcsd}. Consider reprojecting this dataset to NAD83 or WGS84"
        )

    if sr_warnings:
        return sr_warnings


def compare_sr(obj1, obj2):
    sr_warnings = []
    sr1 = db_dict[obj1]["spatialReference"].name
    sr2 = db_dict[obj1]["spatialReference"].name
    if sr1 != sr2:
        sr_warnings = [f"{obj1} and {obj2} have different spatial references"]
    else:
        sr_warnings = "ok"

    return sr_warnings


def values(table, field, what, where=None):
    """list or dictionary {[oid]: value} of values found in a field in a table
    dictionary is {oid: value}"""
    vals = None
    if table in db_dict:
        fields = db_dict[table]["fields"]
        if what == "dictionary":
            oid = [f.name for f in fields if f.type == "OID"][0]
            vals = {
                r[0]: r[1]
                for r in arcpy.da.SearchCursor(
                    db_dict[table]["catalogPath"],
                    field_names=[oid, field],
                    where_clause=where,
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


def rule2_1(db_dict):
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
            errors.append(f'Feature dataset <span class="table">GeologicMap</span>)')
        else:
            # check the spatial reference of each 'GeologicMap' feature dataset
            for gmap in gmaps:
                check_sr_result = check_sr(gmap)
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
                        f'Feature class <span class="table"</span>{n.replace("__missing__", "")}</span>'
                    )
                else:
                    # check each feature class for old datum
                    check_sr_result = check_sr(n)
                    if check_sr_result:
                        sr_warnings.extend(check_sr_result)

            if all(n.find("__missing__") == -1 for n in pair[2:]):
                compare_results = compare_sr(pair[2], pair[3])
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
            errors.append(f'Table <span class="table">{n}</span>')

    return (errors, tp_pairs, sr_warnings)


def check_fields(db_dict, level, schema_extensions):
    """controlled fields are present and correctly defined
    right now this only looks at controlled fields in tables that have been tagged
    with a gems_equivalent.
    """

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
            and not v["dataType"] == "FeatureDataset"
        ]
        header = "3.1 Missing or mis-defined fields"

    errors = [
        "missing or mis-defined field(s)",
        header,
        f"MissingFields{level}",
    ]

    for table in tables:
        gems_eq = db_dict[table]["gems_equivalent"]
        req_fields = gdef.startDict[gems_eq]
        found_fields = db_dict[table]["fields"]
        f_field_names = [f.name for f in found_fields]
        for field in req_fields:
            if not field[0] in f_field_names:
                errors.append(
                    f'<span class="table">{table}</span>, field <span class="field">{field[0]}</span> is missing'
                )
            else:
                req_type = field[1]
                req_null = field[2]
                if len(field) == 4:
                    req_length = field[3]
                else:
                    req_length = None

                if req_type != field[1]:
                    errors.append(
                        f'<span class="table">{table}</span>, field <span class="field">{field}</span> should be type {req_type}'
                    )
                if req_null != field[2]:
                    errors.append(
                        f'<span class="table">{table}</span>, field <span class="field">{field}</span> should  be {req_null}'
                    )
                if req_length:
                    if field[3] < req_length:
                        errors.append(
                            f'<span class="table">{table}</span>, field <span class="field">{field}</span> should be at least {req_length} long'
                        )

        req_names = [f[0] for f in req_fields]
        for field in [
            f.name
            for f in found_fields
            if f.name not in req_names
            and not f.name.endswith("_ID")
            and not f.name in gdef.standard_fields
        ]:
            schema_extensions.append(
                '<span class="table">'
                + table
                + '</span>, field <span class="field">'
                + field
                + "</span>"
            )

    return errors, schema_extensions


def check_topology(topo_pairs):
    """2.3 GeologicMap topology: no internal gaps or overlaps in MapUnitPolys, boundaries of
    MapUnitPolys are covered by ContactsAndFaults 3.2 All map-like feature datasets obey
    topology rules. No MapUnitPolys gaps or overlaps. No ContactsAndFaults overlaps, self-overlaps,
    or self-intersections. MapUnitPoly boundaries covered by ContactsAndFaults"""
    has_been_validated = False
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
        ap(f"\tNo topology found in {gmap}")
        top_path, has_been_validated = tp.make_topology(workdir, topo_pair, db_dict)

    # evaluate the topology
    # eval_topology returns (level_2, level_3, missing_rules, top_errors)
    # do we need to validate first?
    # look for DirtyAreas
    if not has_been_validated:
        ap("\tValidating topology")
        arcpy.ValidateTopology_management(top_path)

    ap("\tLooking at validation results for errors")

    # topologies have to be in feature dataset, so topology.parent.parent
    # gets the file geodatabase, whether the original or the Topology.gdb copy
    gmap = Path(top_path).parent.stem
    topo_gdb = Path(top_path).parent.parent
    top_name = Path(top_path).stem
    level_2_errors, level_3_errors = tp.eval_topology(
        str(topo_gdb), top_name, db_dict, gmap
    )

    return level_2_errors, level_3_errors


def check_map_units(db_dict, level, all_map_units, fds_map_units):
    """All MapUnits entries can be found in DescriptionOfMapUnits table
    Rules 2.4 and 3.8
    Also, collect additions to all_mu_units and fds_map_units"""
    if not "DescriptionOfMapUnits" in db_dict:
        message = [
            "DescriptionOfMapUnits cannot be found. See Rule 2.1",
        ]
        missing = message
        unused = message

        return (missing, unused)

    dmu_units = list(set(values("DescriptionOfMapUnits", "MapUnit", "list")))
    fds_map_units["DescriptionOfMapUnits"] = dmu_units

    if level == 2:
        # just checking MapUnitPolys
        mu_tables = [
            k for k, v in db_dict.items() if v["gems_equivalent"] == "MapUnitPolys"
        ]
        mu_fields = ["MapUnit"]
        missing_header = "2.4 MapUnits missing from DMU. Only one reference to each missing unit is cited"
    else:
        # checking all other tables that have a 'MapUnit' field
        mu_tables = []

        for table in [
            k
            for k, v in db_dict.items()
            if any(n in v["concat_type"] for n in ("Feature Class", "Table"))
            and not v["dataType"] == "FeatureDataset"
            and not k in ["DescriptionOfMapUnits", "MapUnitPolys"]
        ]:
            for f in [f.name for f in db_dict[table]["fields"]]:
                if "MapUnit" in f and not f.endswith("_ID"):
                    mu_tables.append(table)
        missing_header = "3.8 MapUnits missing from DMU. Only one reference to each missing unit is cited"

    missing = [
        "map unit(s) missing in DMU",
        missing_header,
        f"UnitsMissing{level}",
    ]

    unused = [
        "missing map unit(s) in DMU",
        "3.9 MapUnits in DMU that are not present on map, in CMU, or elsewhere",
        f"UnusedUnits{level}",
    ]

    mu_tables = list(set(mu_tables))
    if mu_tables:
        for mu_table in mu_tables:
            fd = (
                db_dict[mu_table]["feature_dataset"]
                if db_dict[mu_table]["feature_dataset"]
                else mu_table
            )
            if not fd in fds_map_units:
                fds_map_units[fd] = []

            mu_fields = [
                f.name
                for f in db_dict[mu_table]["fields"]
                if "MapUnit" in f.name and not f.name.endswith("_ID")
            ]
            with arcpy.da.SearchCursor(
                db_dict[mu_table]["catalogPath"], mu_fields
            ) as cursor:
                for row in cursor:
                    for val in row:
                        if val:
                            all_map_units.append(val)
                            fds_map_units[fd].extend(row)

            fds_map_units[fd] = list(set(fds_map_units[fd]))

        all_map_units.extend(list(set(all_map_units)))

    if not set(all_map_units).issubset(set(dmu_units)):
        missing.extend(set(all_map_units) - set(dmu_units))

    if set(dmu_units).issubset(set(all_map_units)):
        unused.extend(list(set(dmu_units) - set(all_map_units)))

    if level == 2:
        return missing, all_map_units, fds_map_units
    else:
        return missing, unused, all_map_units, fds_map_units


def glossary_check(db_dict, level, all_gloss_terms):
    """Certain field values within required elements have entries in Glossary table"""
    missing = []

    # decide which tables to check
    if level == 2:
        tables = [
            t for t in gdef.rule2_1_elements if not t in ("GeologicMap", "Glossary")
        ]
        term_fields = gdef.defined_term_fields_list
        missing_header = "2.6 Missing terms in Glossary. Only one reference to each missing term is cited"
    else:
        tables = [
            k
            for k, v in db_dict.items()
            if not v["dataType"] in ("FeatureDataset", "Annotation", "Topology")
        ]
        tables = [t for t in tables if not t in gdef.rule2_1_elements]
        term_suffixes = ["Type", "Method", "Confidence"]
        missing_header = "3.4 Missing terms in Glossary. Only one reference to each missing term is cited"

    missing_glossary_terms = [
        "term(s) missing in Glossary",
        missing_header,
        f"MissingTerms{level}",
    ]
    # compare Term fields in the tables with the Glossary
    glossary_terms = values("Glossary", "Term", "list")
    for table in tables:
        if level == 2:
            # look for fields matching the controlled fields
            fields = [f.name for f in db_dict[table]["fields"] if f.name in term_fields]
        elif level == 3:
            fields = []
            # look for field names ending in a controlled suffix
            for suffix in term_suffixes:
                more_fields = [
                    f.name for f in db_dict[table]["fields"] if f.name.endswith(suffix)
                ]
                if more_fields:
                    fields.extend(more_fields)

        if fields:
            for field in fields:
                if field == "GeoMaterialConfidence":
                    where = "GeoMaterial IS NOT NULL"
                else:
                    where = None

                vals = values(table, field, "list", where)
                field_vals = list(set(vals))
                if None in field_vals:
                    field_vals.remove(None)

                # put all of these glossary terms in all_gloss_terms list
                all_gloss_terms.extend(field_vals)

                missing_vals = [val for val in field_vals if not val in glossary_terms]
                for val in missing_vals:
                    missing.append(
                        f'<span class="value">{val}</span>, field <span class="field">{field}</span>, table <span class="table">{table}</span>'
                    )

    missing_glossary_terms.extend(list(set(missing)))

    return missing_glossary_terms, all_gloss_terms


def gm_confidence(table):
    """Collect the values of GeoMaterialConfidence only where GeoMaterial is not null"""
    vals = []
    with arcpy.da.SearchCursor(
        db_dict[table]["catalogPath"], ["GeoMaterial", "GeoMaterialConfidence"]
    ) as rows:
        for row in rows:
            if not row[0] is None:
                vals.append.row[1]
    return vals


def sources_check(db_dict, level, all_sources):
    # first check for DataSources table and DataSources_ID field
    if not "DataSources" in db_dict:
        return "Could not find DataSources table. See Rule 2.1"

    if not "DataSources_ID" in [f.name for f in db_dict["DataSources"]["fields"]]:
        return "Could not find DataSources_ID field in DataSources. See Rule 2.1"

    # found table and filed, proceeed
    # decide which tables to check
    if level == 2:
        # just required fc and tables
        tables = [
            t for t in gdef.rule2_1_elements if not t in ("GeologicMap", "DataSources")
        ]
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

    gems_sources = list(set(values("DataSources", "DataSources_ID", "list")))
    missing = []
    for table in tables:
        ds_fields = [
            f.name for f in db_dict[table]["fields"] if f.name.endswith("SourceID")
        ]
        for ds_field in ds_fields:
            d_sources = values(table, ds_field, "dictionary")
            for oid, val in d_sources.items():
                if not guf.empty(val):
                    for el in val.split("|"):
                        # el_html = f'<span class="value">{el}</span>, field <span class="field">{ds_field}</span>, table <span class="table">{table}</span>'
                        all_sources.append(el)
                        if not el.strip() in gems_sources:
                            missing.append(
                                f'<span class="value">{el}</span>, field <span class="field">{ds_field}</span>, table <span class="table">{table}</span>'
                            )
                # else:
                #     missing.append(
                #         f'table <span class="table">{table}</span>, field <span class="field">{ds_field}</span>, OBJECTID {oid} has no value'
                #     )

    missing_source_ids.extend(list(set(missing)))

    return missing_source_ids, all_sources


def rule3_3(db_dict):
    """all NoNulls fields in all GeMS tables should be filled"""
    # find all gems_equivalent tables
    tables = [
        k
        for k, v in db_dict.items()
        if not v["gems_equivalent"] == "" and not v["dataType"] == "FeatureDataset"
    ]

    missing_required_values = [
        "missing required value(s)",
        "3.3 Fields that are missing required values",
        "MissingReqValues",
    ]

    for table in tables:
        # collect all NoNulls fields
        gems_eq = db_dict[table]["gems_equivalent"]
        def_fields = gdef.startDict[gems_eq]
        no_nulls = [n[0] for n in def_fields if n[2] == "NoNulls"]
        fields = [f.name for f in db_dict[table]["fields"] if f.name in no_nulls]
        oid = [f.name for f in db_dict[table]["fields"] if f.type == "OID"][0]
        for field in fields:
            vals = values(table, field, "dictionary")
            for k, v in vals.items():
                if guf.empty(v) or guf.is_bad_null(v):
                    missing_required_values.append(
                        f'<span class="table">{table}</span>, field <span class="field">{field}</span>, {oid} {k}'
                    )

    return missing_required_values


def rule3_5_and_7(table, all_vals):
    """3.5 No unnecessary terms in Glossary
    3.7 No unnecessary sources in DataSources"""
    if table == "glossary":
        terms = set(values("Glossary", "Term", "list"))
        unused_header = "3.5 Terms in Glossary that are not used in geodatabase"
    elif table == "datasources":
        terms = set(values("DataSources", "DataSources_ID", "list"))
        unused_header = (
            "3.7 DataSources_IDs in DataSources that are not used in geodatabase"
        )

    unused_terms = [
        "unnecessary term(s) in Glossary",
        unused_header,
        "ExcessGlossary",
    ]
    unused_terms.extend(list(terms - set(all_vals)))

    return unused_terms


def rule3_10():
    """HierarchyKey values in DescriptionOfMapUnits are unique and well formed"""
    ap("Checking DescriptionOfMapUnits HKey values")
    # hkey_err_list = []
    # all_dmu_key_values = []
    hkey_errors = [
        "HierarchyKey error(s) in DMU",
        "3.10 HierarchyKey errors",
        "hkey_errors",
    ]

    hks = values("DescriptionOfMapUnits", "HierarchyKey", "dictionary")
    # return early if HKs is empty
    if not hks:
        hkey_errors.append("No HierarchyKey values")
        return hkey_errors

    for k, v in hks.items():
        if guf.empty(v):
            hkey_errors.append(f"OID {k} has no HierarchyKey value")

    # find the delimiter
    # make a list of all non-alphanumeric characters found in all hkeys
    # if the length of the list is not 1, there are multiple delimiters.
    # we'll look for non-numeric characters below
    delims = []
    for hkey in hks.values():
        if not guf.empty(hkey):
            for c in hkey:
                delims.extend([c for c in hkey if c.isalnum() == False])

    delims = set(delims)
    if delims:
        # dealing with a list of character-delimited keys
        if len(delims) > 1:
            formatted = [f"<code>{c}</code>" for c in delims]
            hkey_errors.append(f'Multiple delimiters found: {", ".join(formatted)}')

        # replace all occurrences of the multiple delimiters with pipes
        # look for duplicate values at the same time
        # want to find duplicated numeric values, eg; 001-002 should be seen as a duplicate of 001|002
        # so look for duplicates in the formatted hkeys (where all delimiters are replaced by pipe) not the original hkey
        # but report the original hkey since that is what will be in the table
        seen = set()
        dupes = []

        # new_keys dictionary has entries of [pipe delimited hkey] = original hkey
        new_keys = {}
        for hkey in hks.values():
            if hkey:
                f_key = hkey
                # make a new pipe-delimited key
                # and the dictionary entry
                for delim in delims:
                    if delim != "|":
                        f_key = f_key.replace(delim, "|")
                new_keys[f_key] = hkey

                # look for duplicates
                if f_key in seen:
                    dupes.append(hkey)
                else:
                    seen.add(f_key)

        # get the length of the first fragment of the first dictionary value
        entry1 = next(iter(new_keys))
        fragment_length = len(new_keys[entry1].split("|")[0])

        # iterate through formatted hkeys
        sort_keys = list(new_keys.keys())
        sort_keys.sort()
        for hkey in sort_keys:
            elems = hkey.split("|")
            for e in elems:
                if e.isnumeric() == False:
                    hkey_errors.append(f"{new_keys[hkey]} --non-numeric fragment: {e}")

                # inconsistent fragment length
                if len(e) != fragment_length:
                    hkey_errors.append(f"{new_keys[hkey]} --bad fragment length: {e}")
            # lastHK = hkey

    else:
        # dealing with a list of integers, that is, hkey values are not materialized paths, just numbers; 1,2,3,4...
        hks.sort()
        seen = set()
        dupes = []
        for hkey in hks:
            for c in hkey:
                if c.isnumeric == False:
                    hkey_errors.append(f"{hkey} --non-numeric character: {c}")

            # look for duplicates
            if hkey in seen:
                dupes.append(hkey)
            else:
                seen.add(hkey)

    if dupes:
        s_dupes = set(dupes)
        for dupe in s_dupes:
            hkey_errors.append(f"{dupe} --duplicate hierarchy key")

    return hkey_errors


def rule3_11():
    """All values of GeoMaterial are defined in GeoMaterialDict."""
    errors = ["GeoMaterial error(s)", "3.11 GeoMaterial Errors", "gmErrors"]
    geomat_tables = []
    db_tables = [
        k
        for k, v in db_dict.items()
        if any(v["concat_type"].endswith(n) for n in ("Table", "Feature Class"))
        and not k == "GeoMaterialDict"
        and not "Annotation" in v["concat_type"]
    ]
    for table in db_tables:
        for f in [f.name for f in db_dict[table]["fields"]]:
            if "GeoMaterial" in f:
                geomat_tables.append(table)

    all_geomat_vals = []
    for table in geomat_tables:
        all_geomat_vals.extend(list(set(values(table, "GeoMaterial", "list"))))

    ref_geomats = values("GeoMaterialDict", "GeoMaterial", "list")
    unused_geomats = list(set(all_geomat_vals) - set(ref_geomats))

    if unused_geomats != [None]:
        errors.extend(unused_geomats)

    return errors


def rule3_12():
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
        table_ids = [
            (r[0], table)
            for r in arcpy.da.SearchCursor(table_path, f"{table}_ID")
            if r[0]
        ]
        all_ids.extend(table_ids)
        dup_ids = list(set([id for id in all_ids if all_ids.count(id) > 1]))

    if dup_ids:
        duplicate_ids.extend(dup_ids)

    return duplicate_ids


def rule3_13():
    """No zero-length or whitespace-only strings"""
    zero_length_strings = [
        "zero-length or whitespace string(s)",
        '3.13 Zero-length, whitespace-only, or "&ltNull&gt" text values that probably should be &lt;Null&gt;',
        "zero_length_strings",
    ]

    leading_trailing_spaces = ["Text values with leading or trailing spaces:"]
    # oxxft = """'<span class="table">{table}</span>, field <span class="field">
    # {field_names[i]}</span>, {field_names[obj_id_index]} {str(row[obj_id_index])}"""

    tables = [
        k
        for k, v in db_dict.items()
        if any(v["concat_type"].endswith(n) for n in ("Table", "Feature Class"))
        and not k == "GeoMaterialDict"
        and not "Annotation" in v["concat_type"]
    ]
    for table in tables:
        text_fields = [f.name for f in db_dict[table]["fields"] if f.type == "String"]
        for field in text_fields:
            val_dict = values(table, field, "dictionary")
            for k, v in val_dict.items():
                if v:
                    if v == "" or v.isspace() or v == "&ltNull&gt":
                        html = f'<span class="table">{table}</span>, field <span class="field"> {field}</span>, OID: {str(k)}'
                        zero_length_strings.append(html)

            # also collect leading_trailing_spaces for 'other stuff' report
            for n in [
                k for k, v in val_dict.items() if v and (len(v.strip()) != len(v))
            ]:
                html = f'<span class="tab"></span><span class="table">{table}</span>, field <span class="field"> {field}</span>, OID: {str(n)}'
                leading_trailing_spaces.append(html)

    return zero_length_strings, leading_trailing_spaces


def validate_online(metadata_file):
    """validate the xml metadata against the USGS metadata validation service API"""

    metadata_name = metadata_file.stem
    metadata_dir = metadata_file.parent
    metadata_errors = metadata_dir / f"{metadata_name}_errors.txt"

    passes_mp = False
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
        if not "errors" in summary:
            passes_mp = True
            message = (
                'The database-level FGDC metadata are formally correct. The <a href="'
                + metadata_file
                + '">metadata record</a> should be examined by a human to verify that it is meaningful.<br>\n'
            )
        else:
            message = (
                'The <a href="'
                + metadata_file
                + '">FGDC metadata record</a> for this database has <a href="'
                + metadata_errors
                + '">formal errors</a>. Please fix! <br>\n'
            )
            ap(message)

    else:
        message = (
            "There was a problem with the connection to the metadata validation service:<br>/n"
            + r.reason
        )
        ap(message)

    return passes_mp, message


def write_html(template, out_file):
    environment = Environment(loader=FileSystemLoader(scripts_dir))
    validation_template = environment.get_template(template)
    with open(out_file, mode="w", encoding="utf-8") as results:
        results.write(validation_template.render(val=val))


def determine_level(val):
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
    extras = [
        k
        for k, v in db_dict.items()
        if v["gems_equivalent"] == ""
        and not "Annotation" in v["concat_type"]
        and any(n in v["concat_type"] for n in ("Feature Class", "Table"))
    ]
    if extras:
        for table in extras:
            schema_extensions.append(
                f'{db_dict[table]["dataType"]} <span class="table">{table}</span>'
            )

    return schema_extensions


def sort_fds_units(fds_map_units):
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
        '<div class="report">',
        f'<h4><a name="{tb}"></a>{tb}</h4>',
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
    for t in [
        k
        for k, v in db_dict.items()
        if v["concat_type"] == "Nonspatial Table" and not k == "GeoMaterialDict"
    ]:
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


##############start here##################
# get inputs

guf.checkVersion(version_string, rawurl, "gems-tools-pro")
args_len = len(sys.argv)

# we already know sys.argv[1] exists, no check
gdb_path = Path(sys.argv[1])
# gdb_path = Path(r"C:\_AAA\gems\testing\testbed\dummy.gdb")
gdb_name = gdb_path.name
val["db_path"] = gdb_path
val["db_name"] = gdb_name

# bail early if we don't have a gdb or gpkg
if gdb_path.suffix not in [".gdb", ".gpkg"]:
    ap("This tool can only validate File Geodatabases or Geopackages.")
    guf.forceExit()

# are we working with a geopackage?
if gdb_path.suffix == ".gpkg":
    is_gpkg = True
else:
    is_gpkg = False

# output folder
if 2 < args_len:
    if Path(sys.argv[2]).exists():
        workdir = Path(sys.argv[2])
    else:
        workdir = gdb_path.parent / "validate"
        workdir.mkdir(exist_ok=True)
else:
    workdir = gdb_path.parent / "validate"
    workdir.mkdir(exist_ok=True)

# path to metadata file
if 3 < args_len:
    if Path(sys.argv[3]).suffix == ".xml" and Path(sys.argv[3]).exists():
        metadata_file = Path(sys.argv[3])
    else:
        metadata_file = None
else:
    metadata_file = None
val["metadata_file"] = str(metadata_file)
val["metadata_name"] = metadata_file.name if metadata_file else "valid metadata"
val["md_errors_name"] = (
    f"{metadata_file.name}_errors.txt"
    if metadata_file
    else "a metadata summary from mp"
)

# skip topology?
if 4 < args_len:
    skip_topology = guf.eval_bool(sys.argv[4])
else:
    skip_topology = False

# refresh GeoMaterialDict?
if 5 < args_len:
    refresh_gmd = guf.eval_bool(sys.argv[5])
else:
    refresh_gmd = False

# delete extra rows in Glossary and Data Sources?
if 6 < args_len:
    delete_extra = guf.eval_bool(sys.argv[6])
else:
    delete_extra = False

# compact database?
if 7 < args_len:
    compact_db = guf.eval_bool(sys.argv[7])
else:
    compact_db = False

val["report_path"] = workdir / f"{gdb_name}-Validation.html"
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
geo_material_errors = ["Errors associated with GeoMaterialDict and GeoMaterial values"]
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
        arcpy.conversion.TableToTable(ref_gmd, str(gdb_path), "GeoMaterialDict")

        if not is_gpkg:
            ap("Replacing GeoMaterial domain")
            arcpy.management.TableToDomain(
                ref_gmd,
                "GeoMaterial",
                "IndentedName",
                gdb_path,
                "GeoMaterials",
                "",
                "REPLACE",
            )

            ap("Assigning domain to GeoMaterial")
            dmu_path = db_dict["DescriptionOfMapUnits"]["catalogPath"]
            dmu_fields = db_dict["DescriptionOfMapUnits"]["fields"]
            for f in dmu_fields:
                if not f.domain == "GeoMaterials":
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
ap("Looking at level 2 compliance")
# check 2.1
ap(
    """Rule 2.1 - Has required elements: nonspatial tables DataSources, 
    DescriptionOfMapUnits, GeoMaterialDict; feature dataset GeologicMap with 
    feature classes ContactsAndFaults and MapUnitPolys"""
)
rule2_1_results = rule2_1(db_dict)
val["rule2_1"] = rule2_1_results[0]
val["sr_warnings"] = rule2_1_results[2]

# rule 2.2
# Required fields within required elements are present and correctly defined
ap(
    "Rule 2.2 - Required fields within required elements are present and correctly defined"
)
schema_extensions = [
    '<h3><a name="Extensions"></a>Content not specified in GeMS schema</h3>\n'
]
val["rule2_2"], schema_extensions = check_fields(db_dict, 2, schema_extensions)

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
    topo_results = check_topology(rule2_1_results[1])
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
ap("2.5 No duplicate MapUnit values in DescriptionOfMapUnit table")
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
ap("2.6 Certain field values within required elements have entries in Glossary table")
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
ap("2.8 All xxxSourceID values in required elements have entries in DataSources table")
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


ap("Looking at Level 3 compliance")
# rule 3.1
# Table and field definitions conform to GeMS schema
ap("3.1 Table and field definitions conform to GeMS schema")
val["rule3_1"], schema_extensions = check_fields(db_dict, 3, schema_extensions)

# rule 3.2
ap(
    """3.2 All MapUnitPolys and ContactsAndFaults based feature classes obey Level 3 topology rules: 
    no ContactsAndFaults overlaps, self-overlaps, or self-intersections."""
)
val["rule3_2"] = level_3_errors

# rule 3.3
# No missing required values
ap("3.3 No missing required values")
val["rule3_3"] = rule3_3(db_dict)

# rule 3.4
# No missing terms in Glossary
ap("3.4 No missing terms in Glossary")
val["rule3_4"], all_gloss_terms = glossary_check(db_dict, 3, all_gloss_terms)

# rule 3.5
# No unnecessary terms in Glossary
ap("3.5 No unnecessary terms in Glossary")
val["rule3_5"] = rule3_5_and_7("glossary", all_gloss_terms)

# rule 3.6
# No missing sources in DataSources
ap("3.6 No missing sources in DataSources")
val["rule3_6"], all_sources = sources_check(db_dict, 3, all_sources)

# rule 3.7
# No unnecessary sources in DataSources
ap("3.7 No unnecessary sources in DataSources")
val["rule3_7"] = rule3_5_and_7("datasources", all_sources)

# rule 3.8
# No map units without entries in DescriptionOfMapUnits
# rule 3.9
# No unnecessary map units in DescriptionOfMapUnits
ap("3.8 No map units without entries in DescriptionOfMapUnits")
ap("3.9 No unnecessary map units in DescriptionOfMapUnits")
val["rule3_8"], val["rule3_9"], all_map_units, fds_map_units = check_map_units(
    db_dict, 3, all_map_units, fds_map_units
)

# rule 3.10
# HierarchyKey values in DescriptionOfMapUnits are unique and well formed
ap("3.10 HierarchyKey values in DescriptionOfMapUnits are unique and well formed")
val["rule3_10"] = rule3_10()

# 3.11
# All values of GeoMaterial are defined in GeoMaterialDict.
ap(
    "3.11 All values of GeoMaterial are defined in GeoMaterialDict. GeoMaterialDict is as specified in the GeMS standard"
)
val["rule3_11"] = rule3_11()

# 3.12
# No duplicate _ID values
ap("3.12 No duplicate _ID values")
val["rule3_12"] = rule3_12()

# 3.13
# No zero-length or whitespace-only strings
val["rule3_13"], val["end_spaces"] = rule3_13()

passes_mp = False
if metadata_checked:
    ap("Checking metadata")
    if val["metadata_file"]:
        passes_mp, md_summary = validate_online(metadata_file)
    else:
        md_summary = f"{metadata_file} does not exist."
else:
    ap("Check Metadata option was skipped")
    md_summary = "Check Metadata option was skipped. Be sure to have prepared valid metadata and check this option to produce a complete report."

# now that rules have been checked, prepare some summary entries
val["passes_mp"] = passes_mp
val["metadata_summary"] = md_summary
val["level"] = determine_level(val)

# other stuff
# find extensions to schema
ap("Looking for extensions to GeMS schema")
val["extras"] = extra_tables(db_dict, schema_extensions)

# prepare lists of units for Occurrence table
ap("Finding occurrences of map units")
all_map_units.sort()
val["all_units"] = list(set(all_map_units))
fds_map_units = sort_fds_units(fds_map_units)
val["fds_units"] = fds_map_units

# prepare contents of non-spatial tables
ap("Storing contents of non-spatial tables")
val["non_spatial"] = dump_tables(db_dict)

# build inventory
ap("Building database inventory")
val["inventory"] = inventory(db_dict)

write_html("report_template.jinja", val["report_path"])
write_html("errors_template.jinja", val["errors_path"])
os.startfile(val["report_path"])
sys.exit()

### Compact DB option
if compact_db == "true":
    ap("  Compacting " + os.path.basename(gdb_path))
    arcpy.Compact_management(gdb_path)
else:
    pass
summary.close()
errors.close()
ap("DONE")
