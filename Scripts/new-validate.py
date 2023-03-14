# -*- coding: utf-8 -*-
"""Validate Database

Audits a geodatabase for conformance with the GeMS schema and reports compliance 
as “may be LEVEL 1 COMPLIANT”, “is LEVEL 2 COMPLIANT”, or “is LEVEL 3 COMPLIANT”. 
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

import arcpy
import os
import sys
import time
from pathlib import Path
import GeMS_utilityFunctions as guf
import GeMS_Definition as gdef
import validate_html as vh


version_string = "GeMS_ValidateDatabase_AGP2.py, version of 18 April 2022"
rawurl = "https://raw.githubusercontent.com/usgs/gems-tools-pro/master/Scripts/GeMS_ValidateDatabase_AGP2.py"

py_path = __file__
scripts_dir = Path.cwd()
toolbox_path = scripts_dir.parent
resources_path = toolbox_path / "Resources"

metadata_suffix = "-vFgdcMetadata.txt"
metadata_errors_suffix = "-vFgdcMetadataErrors.txt"

space6 = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp"
space4 = "&nbsp;&nbsp;&nbsp;&nbsp;"
space2 = "&nbsp;&nbsp;"

ap = guf.addMsgAndPrint

geologic_names_disclaimer = """, pending completion of a peer-reviewed Geologic 
Names report that includes identification of any suggested modifications to 
<a href="https://ngmdb.usgs.gov/Geolex/">Geolex</a>. '
"""

lc_standard_fields = []
for f in gdef.standard_fields:
    lc_standard_fields.append(f.lower())

metadata_checked = False  # script will set to True if metadata record is checked

schema_extensions = [
    """<i>Some of the extensions to the GeMS schema identified here may be 
    necessary to capture geologic content and are entirely appropriate. 
    <b>Please document these extensions in metadata for the database, any 
    accompanying README file, and (if applicable) any transmittal letter that 
    accompanies the dataset.</b> Other extensions may be intermediate datasets, 
    fields, or files that should be deleted before distribution of the database.</i><br>
    """
]


topology_errors = ["Feature datasets with bad basic topology"]
topology_error_note = """
<i>Note that the map boundary commonly gives an unavoidable "Must Not Have Gaps" line error.
Other errors should be fixed. Level 2 errors are also Level 3 errors. Errors are
identified in feature classes within XXX-Validation.gdb</i><br><br>
"""


other_warnings = []


def check_sr(db_obj):
    sr_warnings = []
    sr = db_dict[db_obj]["spatialReference"]

    # check for NAD83 or WGS84
    if sr.type == "Geographic":
        pcsd = srf.datumName
    else:  # is projected
        pcsd = srf.PCSName
    if pcsd.find("World_Geodetic_System_1984") < 0 and pcsd.find("NAD_1983") < 0:
        sr_warnings.append(
            f"Spatial reference framework of {db_obj} is {pcsd}. Consider reprojecting this dataset to NAD83 or WGS84"
        )

    if sr_warnings:
        return sr_warnings


def values(table, field, what):
    """list or dictionary {[oid]: value} of values found in a field in a table
    dictionary is {oid: value}"""
    vals = None
    if table in db_dict:
        fields = db_dict[table]["fields"]
        if what == "dict":
            oid = [f.name for f in fields if f.type == "objectid"][0]
            vals = [
                {r[0]: r[1]}
                for r in arcpy.da.SearchCursor(
                    db_dict[table]["catalogPath"], [oid, field]
                )
            ]
        else:
            vals = [
                r[0]
                for r in arcpy.da.SearchCursor(db_dict[table]["catalogPath"], field)
            ]
    return vals


def n_or_missing(n, l):
    if n in l:
        return n
    else:
        return f"__missing__{n}"


def find_topology_pairs(fcs):
    # collect prefix, suffix tuple pairs
    fd_tags = []
    for fc in fcs:
        for s in (("MapUnitPolys", 12), ("ContactsAndFaults", 17)):
            if s[0] in fc:
                i = fc.find(s[0])
                prefix = fc[0:i]
                suffix = fc[i + s[1] :]
                fd_tags.append((prefix, suffix))

    req = ("MapUnitPolys", "ContactsAndFaults")
    pairs = []
    for fd_tag in tuple(set(fd_tags)):
        mup = f"{fd_tag[0]}{req[0]}{fd_tag[1]}"
        caf = f"{fd_tag[0]}{req[1]}{fd_tag[1]}"
        pairs.append(n_or_missing(mup, fcs), n_or_missing(caf, fcs))

    return pairs


def rule2_1(db_dict):
    """Has required elements: nonspatial tables DataSources, DescriptionOfMapUnits,
    GeoMaterialDict; feature dataset GeologicMap with feature classes ContactsAndFaults
    and MapUnitPolys"""
    schema_errors_missing_elements = ["Missing required elements"]
    db_tables = set(
        [k for k, v in db_dict.items() if v["gems_equivalent"] in gdef.rule2_1_elements]
    )
    req_els = set(gdef.rule2_1_elements)

    if not (db_tables == req_els):
        for el in list(req_els - db_tables):
            schema_errors_missing_elements.append(
                f'Table <span class="table">{el}</span>'
            )

    # evaluate the existence of and the spatial reference of the
    # 'GeologicMap' feature datasets.
    topology_fds = []
    topology_pairs = []
    if not is_gpkg:
        # look for GeologicMap feature datasets
        gmaps = [k for k, v in db_dict.items() if v["gems_equivalent"] == "GeologicMap"]
        if not gmaps:
            schema_errors_missing_elements.append(
                'Feature dataset <span class="table">GeologicMap</span>'
            )
        else:
            for gmap in gmaps:
                # check the spatial reference
                sr_warnings = check_sr(gmap)
                if sr_warnings:
                    schema_errors_missing_elements.extend(sr_warnings)

                # in each GeologicMap feature dataset, there needs to be
                # ContactsAndFaults and MapUnitPolys
                is_map = False
                children = gmap["children"]
                gems_fc = [c["gems_equivalent"] for c in children]
                if set(gdef.required_geologic_map_feature_classes).issubset(gems_fc):
                    is_map = True
                    topology_fds.append(gmap)

                if not is_map:
                    for fc in gems_fc:
                        if not fc in gdef.required_geologic_map_feature_classes:
                            schema_errors_missing_elements.append(
                                f'Feature class <span class="table">{gmap}/{fc}</span>'
                            )
    else:
        # in geopackages MapUnitPolys and ContactsAndFaults pairs must have the same prefix
        # suffix; eg, Bedrock_MapUnitPolys_Map1. I don't care what those are, and there may be
        # multiple pairs, but they must match
        # these pairs will be tested for topology
        fcs = [
            k
            for k, v in db_dict.items()
            if v["gems_equivalent"] in gdef.required_geologic_map_feature_classes
        ]
        topology_pairs = find_topology_pairs(fcs)

        # evaluate pairs
        if topology_pairs:
            for pair in topology_pairs:
                for n in pair:
                    if "_missing_" in n:
                        schema_errors_missing_elements.append(
                            f'Feature class <span class="table">{n}</span>'
                        )

    return (schema_errors_missing_elements, topology_fds, topology_pairs)


def check_fields(db_dict, level):
    """controlled fields are present and correctly defined
    right now this only looks at controlled fields in tables that have been tagged
    with a gems_equivalent.
    """
    schema_errors_missing_fields = ["Missing or mis-defined fields"]
    if level == 2:
        # only required tables and fcs
        req_tables = [t for t in gdef.rule2_1_elements if t != "GeologicMap"]
        tables = [k for k, v in db_dict.items() if v["gems_equivalent"] in req_tables]
    elif level == 3:
        # all other tables and fcs
        tables = [
            k
            for k, v in db_dict.items()
            if not k in req_tables
            and not v["gems_equivalent"] == ""
            and not v["dataType"] == "FeatureDataset"
        ]

    for table in tables:
        gems_eq = db_dict[table]["gems_equivalent"]
        req_fields = gdef.startDict[gems_eq]
        found_fields = db_dict[table]["fields"]
        f_field_names = [f.name for f in found_fields]
        for field in req_fields:
            if not field[0] in f_field_names:
                schema_errors_missing_fields.append(
                    f'<span class="table">{table}</span>, field <span class="field">{field}</span> is missing'
                )
            else:
                req_type = field[1]
                req_null = field[2]
                if len(field) == 4:
                    req_length = field[3]
                else:
                    req_length = None

                if req_type != found_fields[field].type:
                    schema_errors_missing_fields.append(
                        f'<span class="table">{table}</span>, field <span class="field">{field}</span> should be type {req_type}'
                    )
                if req_null != found_fields[field].nulls:
                    schema_errors_missing_fields.append(
                        f'<span class="table">{table}</span>, field <span class="field">{field}</span> should  be {req_null}'
                    )
                if req_length:
                    if found_fields[field].length < req_length:
                        schema_errors_missing_fields.append(
                            f'<span class="table">{table}</span>, field <span class="field">{field}</span> should be at least {req_length} long'
                        )

    return schema_errors_missing_fields


def check_topology(gmap_fds, topo_pairs, level):
    """2.3 GeologicMap topology: no internal gaps or overlaps in MapUnitPolys, boundaries of
    MapUnitPolys are covered by ContactsAndFaults 3.2 All map-like feature datasets obey
    topology rules. No MapUnitPolys gaps or overlaps. No ContactsAndFaults overlaps, self-overlaps,
    or self-intersections. MapUnitPoly boundaries covered by ContactsAndFaults"""
if 

    # checking for topology
    if is_map:
        if not skip_topology:
            children = db_dict[gmap]["children"]
            tops = [c["name"] for c in children if c["dataType"] == "Topology"]
            if tops:
                n_topo_errors = check_topology(
                    workdir,
                    gdb_path,
                    gmap,
                    2,
                )
                if n_topo_errors > 0:
                    topology_errors.append(
                        str(n_topo_errors)
                        + ' Level 2 errors in <span class="table">GeologicMap</span>'
                    )
        else:
            ap("  skipping topology check")
            topology_errors.append("Level 2 topology check was skipped")


def check_map_units(db_dict, level):
    """All MapUnits entries can be found in DescriptionOfMapUnits table
    Rules 2.4 and 3.8"""
    missing_dmu_map_units = [
        "MapUnits missing from DMU. Only one reference to each missing unit is cited"
    ]

    unused_dmu_map_units = [
        "MapUnits in DMU that are not present on map, in CMU, or elsewhere"
    ]

    dmu_units = list(set(values("DescriptionOfMapUnits", "MapUnit", "list")))

    if level == 2:
        # just checking MapUnitPolys
        mu_tables = [
            k for k, v in db_dict.items() if v["gems_equivalent"] == "MapUnitPolys"
        ]
        mu_fields = ["MapUnit"]
    else:
        # checking all tables that have a 'MapUnit' field
        mu_tables = []
        mu_fields = []
        for table in [
            k
            for k, v in db_dict.items()
            if not k in ["DescriptionOfMapUnits", "MapUnitPolys"]
            and not v["featureType"] == "Annotation"
            and not v["dataType"] == "FeatureDataset"
        ]:
            for f in [f.name for f in db_dict[table]["fields"]]:
                if "MapUnit" in f.name:
                    mu_tables.append(table)
                    mu_fields.append(f.name)

    mu_tables = list(set(mu_tables))
    if mu_tables:
        for mu_table in mu_tables:
            units = [
                row
                for row in arcpy.da.SearchCursor(
                    db_dict[mu_table]["catalogPath"], mu_fields
                )
            ]
            all_map_units.extend(units)
            all_map_units = list(set(all_map_units))

    if not set(all_map_units).issubset(set(dmu_units)):
        missing_dmu_map_units.extend(list(set(all_map_units) - set(dmu_units)))
    else:
        missing_dmu_map_units = None

    if set(dmu_units).issubset(set(all_map_units)):
        unused_dmu_map_units.extend(list(set(dmu_units) - set(all_map_units)))
    else:
        missing_dmu_map_units = None

    if level == 2:
        return missing_dmu_map_units
    else:
        return [missing_dmu_map_units, unused_dmu_map_units]


def glossary_check(db_dict, level):
    """Certain field values within required elements have entries in Glossary table"""
    missing_glossary_terms = [
        "Missing terms in Glossary. Only one reference to each missing term is cited"
    ]

    # decide which tables to check
    if level == 2:
        tables = [t for t in gdef.rule2_1_elements if t != "GeologicMap"]
        term_fields = gdef.defined_term_fields_list
    else:
        tables = [
            k
            for k, v in db_dict.items()
            if not v["dataType"] in ("FeatureDataset", "Annotation")
        ]
        tables = [t for t in tables if not t in gdef.rule2_1_elements]
        term_suffixes = ["Type", "Method", "Confidence"]

    # compare Term fields in the tables with the Glossary
    glossary_terms = values("Glossary", "Term", "list")
    all_glossary_refs = []
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
                fields.append(more_fields)

        missing = []
        for field in fields:
            vals = values(table, field, "list")
            field_vals = list(set(vals.values()))

            # put all of these glossary terms in all_glossary_refs list
            all_glossary_refs.extend(field_vals)

            missing_vals = [val for val in field_vals if not val in glossary_terms]
            for val in missing_vals:
                missing.append(
                    f'<span class="value">{val}</span>, field <span class="field">{field}</span>, table <span class="table">{table}</span>'
                )

    missing_glossary_terms.extend(list(set(missing)))

    if level == 2:
        return missing_glossary_terms
    else:
        return (missing_glossary_terms, all_glossary_refs)


def sources_check(db_dict, level, all_sources):
    missing_source_ids = [
        "Missing DataSources entries. Only one reference to each missing entry is cited"
    ]

    # decide which tables to check
    if level == 2:
        # just required fc and tables
        tables = [t for t in gdef.rule2_1_elements if t != "GeologicMap"]
    if level == 3:
        # all other tables and fcs in the database
        tables = [
            k
            for k, v in db_dict.items()
            if not v["dataType"] in ["FeatureDataset", "Annotation"]
        ]
        tables = [t for t in tables if not t in gdef.rule2_1_elements]

    gems_sources = list(set(values("DataSources", "DataSource_ID", "list")))
    missing = []
    for table in tables:
        ds_fields = [
            f.name for f in db_dict[table][ds_fields] if f.name.endswith("SourceID")
        ]
        for ds_field in ds_fields:
            atomic_sources = []
            d_sources = list(set(values(table, ds_field, "dict")))
            for d_source in d_sources:
                for el in d_source[1].split("|"):
                    atomic_sources.append(el)
                    all_sources.append((table, ds_field, el, d_source[0]))
                    if not el.strip() in gems_sources:
                        missing.append(
                            f'<span class="value">{el}</span>, field <span class="field">{ds_field}</span>,table <span class="table">{table}</span>'
                        )

    missing_source_ids.extend(list(set(missing)))
    if level == 2:
        return missing_source_ids
    else:
        return (None, all_sources)


def rule3_3(db_dict):
    """all NoNulls fields in all GeMS tables should be filled"""
    # find all gems_equivalent tables
    tables = [
        k
        for k in db_dict
        if not db_dict[k]["gems_equivalent"] == ""
        and not db_dict[k]["dataType"] == "FeatureDataset"
    ]
    missing_required_values = ["Fields that are missing required values"]
    for table in tables:
        # collect all NoNulls fields
        gems_eq = db_dict[table]["gems_equivalent"]
        def_fields = gdef.startDict[gems_eq]["fields"]
        no_nulls = [n[0] for n in def_fields if n[2] == "NoNulls"]
        fields = [f.name for f in db_dict[table]["fields"] if f.name in no_nulls]
        oid = [f.name for f in db_dict[table]["fields"] if f.type == "objectid"]
        for field in fields:
            vals = values(table, field, "list")
            for k, v in vals.items():
                if guf.empty(v) or guf.is_bad_null(v):
                    missing_required_values.append(
                        f'<span class="table">{table}</span>, field <span class="field">{field}</span>, {oid} {v}'
                    )

        return missing_required_values


def rule3_5_and_7(terms, table):
    """3.5 No unnecessary terms in Glossary
    3.7 No unnecessary sources in DataSources"""
    if table == "glossary":
        terms = set(values("Glossary", "Term", "list"))
        unused_terms = ["Terms in Glossary that are not otherwise used in geodatabase"]
    elif table == "datasources":
        terms = set(values("Glossary", "Term", "list"))
        unused_terms = [
            "DataSource_IDs in DataSources that are not otherwise used in geodatabase"
        ]

    all_vals = set(terms)
    unused_terms.extend(list(unused_terms - all_vals))

    return unused_terms


def rule3_10():
    """HierarchyKey values in DescriptionOfMapUnits are unique and well formed"""
    ap("Checking DescriptionOfMapUnits HKey values")
    # hkey_err_list = []
    # all_dmu_key_values = []
    hkey_errors = ["HierarchyKey errors, DescriptionOfMapUnits"]

    dmu_path = db_dict["DescriptionOfMapUnits"]["catalogPath"]
    hks = [r[0] for r in arcpy.da.SearchCursor(dmu_path, "HierarchyKey")]

    # return early if HKs is empty
    if not hks:
        hkey_errors.append("No HierarchyKey values?!")
        return hkey_errors

    # find the delimiter
    # make a list of all non-alphanumeric characters found in all hkeys
    # if the length of the list is not 1, there are multiple delimiters.
    # we'll look for non-numeric characters below
    delims = []
    for hkey in hks:
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
        for hkey in hks:
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
    geomat_tables = []
    db_tables = [
        k
        for k, v in db_dict.items()
        if not k == "GeoMaterialDict"
        and not v["featureType"] == "Annotation"
        and not v["dataType"] == "FeatureDataset"
    ]
    for table in db_tables:
        for f in [f.name for f in db_dict[table]["fields"]]:
            if "GeoMaterial" in f.name:
                geomat_tables.append(table)

    all_geomat_vals = []
    for table in geomat_tables:
        all_geomat_vals.extend(list(set(values(table, "GeoMaterial", "list"))))

    ref_geomats = values("GeoMaterialDict", "GeoMaterial", "list")
    unused_geomats = list(set(all_geomat_vals) - set(ref_geomats))

    return unused_geomats


def rule3_12():
    """No duplicate _ID values"""
    duplicate_ids = ["Duplicated _ID values"]
    id_tables = []
    db_tables = [
        k
        for k, v in db_dict.items()
        if not v["featureType"] == "Annotation"
        and not v["dataType"] == "FeatureDataset"
    ]
    for table in db_tables:
        for f in [f.name for f in db_dict[table]["fields"]]:
            if f.name == f"{table}_ID":
                id_tables.append(table)

    all_ids = []
    for table in id_tables:
        table_path = db_dict[table]["catalogPath"]
        # need a tuple here because duplicated keys added to a dictionary
        # are ignored. need to look for duplicate (_ID Value: table) pairs.
        table_ids = [
            (r[0], table) for r in arcpy.da.SearchCursor(table_path, f"{table}_ID")
        ]
        all_ids.extend(table_ids)
        dup_ids = list(set([id for id in all_ids if all_ids.count(id) > 1]))

    return duplicate_ids.extend(dup_ids)


def rule3_13():
    """No zero-length or whitespace-only strings"""
    zero_length_strings = [
        'Zero-length, whitespace-only, or "&ltNull&gt" text values that probably should be &lt;Null&gt;'
    ]

    leading_trailing_spaces = ["Text values with leading or trailing spaces:"]
    # oxxft = """'<span class="table">{table}</span>, field <span class="field">
    # {field_names[i]}</span>, {field_names[obj_id_index]} {str(row[obj_id_index])}"""

    tables = [
        k
        for k in db_dict
        if not db_dict[k]["dataType"] in ["FeatureDataset", "Annotation"]
    ]
    for table in tables:
        text_fields = [f.name for f in db_dict[table["fields"]] if f.type == "String"]
        for field in text_fields:
            val_dict = values(table, field, "dict")
            possible_empty = [
                (k, v) for k, v in val_dict.items() if v.isspace() or v == "&ltNull&gt"
            ]
            zero_length_strings.extend(possible_empty)

            # also collect leading_trailing_spaces for 'other stuff' report
            for n in [
                k for k, v in val_dict.items() if v[0].isspace() or v[-1].isspace()
            ]:
                html = f'<span class="table">{table}</span>, field <span class="field"> {field}</span>, OID: {str(n)}'
                leading_trailing_spaces.append(html)

    return leading_trailing_spaces


##############start here##################
# get inputs

guf.checkVersion(version_string, rawurl, "gems-tools-pro")
args_len = len(sys.argv)

# we already know sys.argv[1] exists, no check
# gdb_path = Path(sys.argv[1])
gdb_path = Path(r"C:\_AAA\gems\testing\testbed\dummy.gdb")
gdb_name = gdb_path.name

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

errors_name = f"{gdb_name}-ValidationErrors.html"

# make the database dictionary
db_dict = guf.gdb_object_dict(str(gdb_path))

# make a list of MapUnits found in the DMU
dmu_units = values("DescriptonOfMapUnits", "MapUnit", "list")

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

# look for geodatabase version
# not implemented yet
if "PublicationTable" in db_dict.keys():
    ver_table = db_dict["Version"]["catalogPath"]
    result = arcpy.GetCount_management(ver_table)
    if result[0] == 1:
        gdb_ver = f" version {[row[0] for row in arcpy.da.SearchCursor(ver_table, 'Version')]}"
    else:
        gdb_ver = ""

# md_txt_file = workdir / f'{gdb_name}{metadata_suffix}'
# md_err_file = workdir / f'{gdb_name}{metadata_errors_suffix}'
# md_xml_file = str(md_txt_file)[:-3] + "xml"

# delete errors gdb if it exists and make a new one
# gdb_val = f"{gdb_name[:-4]}_Validation.gdb"
# out_errors_gdb = workdir / gdb_val
# if not arcpy.Exists(str(out_errors_gdb)):
#     arcpy.management.CreateFileGDB(str(workdir), gdb_val)

# level 2 compliance
ap("Looking at level 2 compliance")
# check 2.1
"""Has required elements: nonspatial tables DataSources, DescriptionOfMapUnits, GeoMaterialDict; feature dataset GeologicMap with feature classes ContactsAndFaults and MapUnitPolys"""
txt_1 = """2.1 Has required elements: nonspatial tables DataSources, 
    DescriptionOfMapUnits, GeoMaterialDict; feature dataset GeologicMap with 
    feature classes ContactsAndFaults and MapUnitPolys"""
# rule 2_1 returns schema_errors_missing_elements (list),
# topology_fds (list of names of Geologic map feature datasets), and
# topology_pairs (list of pairs (MapUnitPolys, ContactsAndFaults) of
# geologic map feature classes in geopackages that need to be checked for topology
rule2_1_results = rule2_1(db_dict)
schema_errors_missing_elements = rule2_1_results[0]

# rule 2.2
# Required fields within required elements are present and correctly defined
schema_errors_missing_fields = check_fields(db_dict, 2)

# rule 2.3 topology
check_topology(rule2_1_results[1], rule2_1_results[2], 2)

# rule 2.4
# All map units in MapUnitPolys have entries in DescriptionOfMapUnits table
mup_results = check_map_units(db_dict, dmu_units, 2)

# rule 2.5
# No duplicate MapUnit values in DescriptionOfMapUnit table
dmu_map_units_duplicates = ["Duplicated MapUnit values in DescriptionOfMapUnits"]
dmu_path = db_dict["DescriptionOfMapUnits"]["catalogPath"]
dmu_map_units_duplicates.extend(guf.get_duplicates(dmu_path, "MapUnit"))

# rule 2.6
# Certain field values within required elements have entries in Glossary table
results = glossary_check(db_dict, 2)
missing_glossary_terms = results[0]

# rule 2.7
# No duplicate Term values in Glossary table
glossary_term_duplicates = ["Duplicated terms in Glossary"]
gloss_path = db_dict["Glossary"]["catalogPath"]
glossary_term_duplicates.extend(guf.get_duplicates(gloss_path, "Term"))

# rule 2.8
# All xxxSourceID values in required elements have entries in DataSources table
all_sources = []
sources_results = sources_check(db_dict, 2, all_sources)
missing_source_ids = sources_results[0]
all_sources = sources_results[1]

# rule 2.9
# No duplicate DataSources_ID values in DataSources table
duplicated_source_ids = ["Duplicated source_IDs in DataSources"]
ds_path = db_dict["DataSources"]["catalogPath"]
duplicated_source_ids.extend(guf.get_duplicates(ds_path, "DataSources_ID"))

ap("Looking at Level 3 compliance")
# rule 3.1
# Table and field definitions conform to GeMS schema
schema_errors_missing_fields = check_fields(db_dict, 3)

# rule 3.2
# Topology

# rule 3.3
# No missing required values
missing_required_values = rule3_3(db_dict)

# rule 3.4
# No missing terms in Glossary
gloss_results = glossary_check(db_dict, 3)
missing_glossary_terms = gloss_results[0]

# rule 3.5
# No unnecessary terms in Glossary
unused_glossary_terms = rule3_5_and_7("glossary", results[1])

# rule 3.6
# No missing sources in DataSources
sources_results = sources_check(db_dict, 3, all_sources)
missing_source_ids = sources_results[1]

# rule 3.7
# No unnecessary sources in DataSources
unused_source_ids = rule3_5_and_7("datasources", sources_results[1])

# rule 3.8
# No map units without entries in DescriptionOfMapUnits
results = check_map_units(db_dict, 3)
missing_dmu_map_units = results[0]

# rule 3.9
# No unnecessary map units in DescriptionOfMapUnits
unused_dmu_map_units = results[1]

# rule 3.10
# HierarchyKey values in DescriptionOfMapUnits are unique and well formed
hkey_errors = rule3_10()

# 3.11
# All values of GeoMaterial are defined in GeoMaterialDict.
geo_material_errors.extend(rule3_11())

# 3.12
# No duplicate _ID values
duplicate_ids = rule3_12()

# 3.13
# No zero-length or whitespace-only strings
zero_length_strings = rule3_13()


# arcpy.env.workspace = gdb_path
ap("  getting unused, missing, and duplicated key values")

unused, missing, plain_used = match_refs(data_sources_ids, all_data_sources_refs)
append_values(missing_source_ids, missing)

for d in get_duplicates(data_sources_ids):
    duplicated_source_ids.append(f'<span class="value">{d}</span>')
unused, missing, plain_used = match_refs(glossary_terms, all_glossary_refs)
append_values(missing_glossary_terms, missing)

for d in get_duplicates(glossary_terms):
    glossary_term_duplicates.append(f'<span class="value">{d}</span>')
unused, missing, plain_used = match_refs(dmu_map_units, hkey_index)
append_values(missing_dmu_map_units, missing)

for d in get_duplicates(dmu_map_units):
    dmu_map_units_duplicates.append(f'<span class="value">{d}</span>')
is_level_2, summary_2, errors_2 = write_output_level_2(errors_name)

# reset some stuff
topology_errors = ["Feature datasets with bad basic topology"]
missing_source_ids = [
    "Missing DataSources entries. Only one reference to each missing entry is cited"
]
missing_glossary_terms = [
    "Missing terms in Glossary. Only one reference to each missing term is cited"
]
missing_dmu_map_units = [
    "MapUnits missing from DMU. Only one reference to each missing unit is cited"
]

# level 3 compliance
ap("Looking at level 3 compliance")
tables = arcpy.ListTables()
for tb in tables:
    if tb not in gdef.required_tables:
        map_units = scan_table(tb)
# check for other stuff at top level of gdb
find_other_stuff(gdb_path, tables)
fds_mapunits = []
# change fds below to a list or dictionary of catalogPaths to feature datasets
fds = arcpy.ListDatasets("*", "Feature")
for fd in fds:
    fd_srf = arcpy.Describe(fd).spatialReference.name
    if fd_srf != gmap_srf:
        srf_warnings.append(
            f"Spatial reference framework of {fd} does not match that of GeologicMap"
        )
    arcpy.env.workspace = fd
    fcs = arcpy.ListFeatureClasses()
    find_other_stuff(gdb_path + "/" + fd, fcs)
    if fd == "GeologicMap":
        fd_map_unit_list = gmap_mapunits
    else:
        fd_map_unit_list = []
    for fc in fcs:
        if not fc in gdef.required_geologic_map_feature_classes:
            dsc = arcpy.Describe(fc)
            if dsc.featureType == "Simple":
                map_units = scan_table(fc, fd)
                append_values(fd_map_unit_list, map_units)
            else:
                ap(
                    "  ** skipping data set "
                    + fc
                    + ", featureType = "
                    + dsc.featureType
                )
    is_map, mup, caf = is_feature_dataset_a_map(fd)
    if is_map:
        if skip_topology == "false":
            n_topo_errors = check_topology(
                workdir, gdb_path, out_errors_gdb, fd, mup, caf, 3
            )
            if n_topo_errors > 0:
                topology_errors.append(
                    str(n_topo_errors)
                    + ' Level 3 errors in <span class="table">'
                    + fd
                    + "</span>"
                )
        else:
            ap("  skipping topology check")
            topology_errors.append("Level 3 topology check was skipped")
    fds_mapunits.append([fd, fd_map_unit_list])
    arcpy.env.workspace = gdb_path
check_geo_material_dict(gdb_path)

ap("  getting unused, missing, and duplicated key values")

unused, missing, plain_used = match_refs(data_sources_ids, all_data_sources_refs)
if delete_extra == "true":
    delete_extra_rows("DataSources", "DataSources_ID", plain_used)
else:
    append_values(unused_source_ids, unused)
append_values(missing_source_ids, missing)

unused, missing, plain_used = match_refs(glossary_terms, all_glossary_refs)
if delete_extra == "true":
    delete_extra_rows("Glossary", "Term", plain_used)
else:
    append_values(unused_glossary_terms, unused)
append_values(missing_glossary_terms, missing)

unused, missing, plain_used = match_refs(dmu_map_units, hkey_index)
append_values(unused_dmu_map_units, unused)
append_values(missing_dmu_map_units, missing)

append_values(duplicate_ids, get_duplicate_ids(all_ids))
append_values(
    hkey_errors, get_hkey_errors(all_dmu_key_values)
)  # getHKeyErrors collects values with bad separators, bad element sizes, duplicates, and missing sequential values

if metadata_file:
    metadata_checked, passes_mp = check_metadata(workdir, metadata_file)
else:
    metadata_checked = False

check_for_lock_files(gdb_path)

is_level_3, summary_3, errors_3 = write_output_level_3()

metadataTxt = os.path.basename(gdb_path + metadata_suffix)
metadataErrs = os.path.basename(gdb_path + metadata_errors_suffix)

### assemble output
ap("Writing output")
ap("  writing summary header")

# output files

errors_file = workdir / errors_name
errors = open(errors_file, "w")

summary_name = f"{gdb_name}-Validation.html"
sum_file = workdir / summary_name
summary = open(sum_file, "w", errors="xmlcharrefreplace")
summary.write(vh.style)
summary.write(
    """<h2><a name="overview"><i>GeMS validation of </i> '
    {gdb_name}{gdb_ver}</a></h2>\n"""
)

summary.write('<div class="report">Database path: ' + gdb_path + "<br>\n")
summary.write("File written by <i>" + version_string + "</i><br>\n")
summary.write(time.asctime(time.localtime(time.time())) + "<br><br>\n")
summary.write(
    "This file should be accompanied by "
    + errors_name
    + ", "
    + metadataTxt
    + ", and "
    + metadataErrs
    + ", all in the same directory.<br><br>\n"
)
if is_level_3 and is_level_2:
    summary.write(
        'This database is <a href=#Level3><font size="+1"><b>LEVEL 3 COMPLIANT</b></a></font>'
        + geologic_names_disclaimer
        + "\n"
    )
elif is_level_2:
    summary.write(
        'This database is <a href=#Level2><font size="+1"><b>LEVEL 2 COMPLIANT</b></a></font>'
        + geologic_names_disclaimer
        + "\n"
    )
else:  # is level 1
    summary.write(
        'This database may be <a href=#Level1><font size="+1"><b>LEVEL 1 COMPLIANT</b></a>. </font>\n'
    )
if metadata_checked:
    if passes_mp:
        summary.write(
            'The database-level FGDC metadata are formally correct. The <a href="'
            + metadataTxt
            + '">metadata record</a> should be examined by a human to verify that it is meaningful.<br>\n'
        )
    else:  # metadata fails mp
        summary.write(
            'The <a href="'
            + metadataTxt
            + '">FGDC metadata record</a> for this database has <a href="'
            + metadataErrs
            + '">formal errors</a>. Please fix! <br>\n'
        )
else:  # metadata not checked
    summary.write("FGDC metadata for this database have not been checked. <br>\n")

###ERRORS HEADER
ap("  writing errors header")
errors.write(vh.style)
errors.write(
    '<h2><a name="overview">'
    + os.path.basename(gdb_path)
    + "-ValidationErrors</a></h2>\n"
)
errors.write('<div class="report">Database path: ' + gdb_path + "<br>\n")
errors.write("This file written by <i>" + version_string + "</i><br>\n")
errors.write(time.asctime(time.localtime(time.time())) + "<br>\n")
errors.write(
    """
    </div>
    <div id="back-to-top"><a href="#overview">Back to Top</a></div>
"""
)
errors.write(vh.color_codes)

###CONTENTS
anchorRoot = os.path.basename(summary_name) + "#"
summary.write(
    """
    </div>
    <div id="back-to-top"><a href="#overview">Back to Top</a></div>
    <h3>Contents</h3>
    <div class="report" id="contents">
"""
)
summary.write(
    '          <a href="'
    + anchorRoot
    + 'Compliance_Criteria">Compliance Criteria</a><br>\n'
)
summary.write(
    '          <a href="'
    + anchorRoot
    + 'Extensions">Content not specified in GeMS schema</a><br>\n'
)
summary.write(
    '          <a href="'
    + anchorRoot
    + 'MapUnits_Match">MapUnits in DescriptionOfMapUnits table, GeologicMap feature dataset, and other feature datasets</a><br>\n'
)
summary.write(
    '          <a href="'
    + anchorRoot
    + 'Contents_Nonspatial">Contents of Nonspatial Tables</a><br>\n'
)
tables.sort()
for tb in tables:
    if tb != "GeoMaterialDict":
        summary.write(
            '&nbsp;&nbsp;&nbsp;&nbsp;<a href="'
            + anchorRoot
            + tb
            + '">'
            + tb
            + "</a><br>\n"
        )
summary.write(
    '    <a href="' + anchorRoot + 'Database_Inventory">Database Inventory</a><br>\n'
)
summary.write("        </div>\n")

###COMPLIANCE CRITERIA
summary.write('<h3><a name="Compliance_Criteria"></a>Compliance Criteria</h3>\n')
summary.write(vh.rdiv)
summary.write('<h4><a name="Level1">LEVEL 1</a></h4>\n')
summary.write(
    """
<i>Criteria for a LEVEL 1 GeMS database are:</i>
<ul>
<li>No overlaps or internal gaps in map-unit polygon layer</li>
<li>Contacts and faults in single feature class</li>
<li>Map-unit polygon boundaries are covered by contacts and faults lines</li>
</ul>
<i>Databases with a variety of schema may meet these criteria. This script cannot confirm LEVEL 1 compliance.</i>\n"""
)
ap("  writing Level 2")
summary.write('<h4><a name="Level2">LEVEL 2--MINIMALLY COMPLIANT</a></h4>\n')
summary.write(
    "<i>A LEVEL 2 GeMS database is accompanied by a peer-reviewed Geologic Names report, including identification of suggested modifications to Geolex, and meets the following criteria:</i><br><br>\n"
)
for aln in summary_2:
    summary.write(aln + "\n")
errors.write("<h3>Level 2 errors</h3>\n")
for aln in errors_2:
    errors.write(aln + "\n")
ap("  writing Level 3")
summary.write('<h4><a name="Level3">LEVEL 3--FULLY COMPLIANT</a></h4>\n')
summary.write("<i>A LEVEL 3 GeMS database meets these additional criteria:</i><br>\n")
for aln in summary_3:
    summary.write(aln + "\n")
errors.write("<h3>Level 3 errors</h3>\n")
for aln in errors_3:
    errors.write(aln + "\n")
###Warnings
summary.write("<br>\n")
nWarnings = -1  # leading_trailing_spaces has a header line
for w in srf_warnings, leading_trailing_spaces, other_warnings:
    for aw in w:
        nWarnings = nWarnings + 1
summary.write(
    '<a href="'
    + os.path.basename(errors_name)
    + '#Warnings">There are '
    + str(nWarnings)
    + " warnings<br></a>\n"
)
errors.write('<h3><a name="Warnings">Warnings</a></h3>\n')
errors.write(vh.rdiv)
for w in srf_warnings, other_warnings:
    for aw in w:
        errors.write(aw + "<br>\n")
if len(leading_trailing_spaces) > 1:
    for aw in leading_trailing_spaces:
        errors.write(aw + "<br>\n")
errors.write(vh.divend)
summary.write(vh.divend)

###EXTENSIONS TO SCHEMA
ap("  listing schema extensions")
summary.write(
    '<h3><a name="Extensions"></a>Content not specified in GeMS schema</h3>\n'
)
summary.write(vh.rdiv)
if len(schema_extensions) > 1:
    summary.write(schema_extensions[0] + "<br>\n")
    for i in schema_extensions[1:]:
        summary.write(space4 + i + "<br>\n")
else:
    summary.write("None<br>\n")
summary.write(vh.divend)

###MAPUNITS MATCH
ap("  writing table of MapUnit presence/absence")
summary.write(
    '<h3><a name="MapUnits_Match"></a>MapUnits in DescriptionOfMapUnits table, GeologicMap feature dataset, and other feature datasets</h3>\n'
)
fds_mapunits.sort()  # put feature datasets in alphabetical order
# fds_mapunits = [ [dataset name [included map units]],[dsname, [incMapUnit]] ]
summary.write(vh.rdiv)
summary.write(
    '<table class="ess-tables"; style="text-align:center"><tr><th>MapUnit</th><th>&nbsp; DMU &nbsp;</th>'
)
for f in fds_mapunits:
    summary.write("<th>" + f[0] + "</th>")
summary.write("</tr>\n")
# open search cursor on DMU sorted by HKey
sql = (None, "ORDER BY HierarchyKey")
with arcpy.da.SearchCursor(
    "DescriptionOfMapUnits", ("MapUnit", "HierarchyKey"), None, None, False, sql
) as cursor:
    for row in cursor:
        mu = row[0]
        if guf.not_empty(mu):
            summary.write(
                "<tr><td>" + mu + "</td><td>X</td>"
            )  #  2nd cell: value is, by definition, in DMU
            for f in fds_mapunits:
                if mu in f[1]:
                    summary.write("<td>X</td>")
                else:
                    summary.write("<td>---</td>")
            summary.write("</tr>\n")
# for mapunits not in DMU
for aline in missing_dmu_map_units[1:]:
    mu = aline.split(",")[0]
    summary.write("<tr><td>" + str(mu) + "</td><td>---</td>")
    for f in fds_mapunits:
        if mu in f[1]:
            summary.write("<td>X</td>")
        else:
            summary.write("<td>---</td>")
    summary.write("</tr>\n")
summary.write("</table>\n")
summary.write(vh.divend)

###CONTENTS OF NONSPATIAL TABLES
ap("  dumping contents of nonspatial tables")
summary.write(
    '<h3><a name="Contents_Nonspatial"></a>Contents of Nonspatial Tables</h3>\n'
)
for tb in tables:
    if tb != "GeoMaterialDict":
        summary.write(vh.rdiv)
        summary.write('<h4><a name="' + tb + '"></a>' + tb + "</h4>\n")
        vh.table_to_html(tb, summary)
        summary.write(vh.divend)
###DATABASE INVENTORY
ap("  writing database inventory")
summary.write('<h3><a name="Database_Inventory"></a>Database Inventory</h3>\n')
summary.write(vh.rdiv)
summary.write(
    "<i>This summary of database content is provided as a convenience to GIS analysts, reviewers, and others. It is not part of the GeMS compliance criteria.</i><br><br>\n"
)
for tb in tables:
    summary.write(
        tb + ", nonspatial table, " + str(guf.numberOfRows(tb)) + " rows<br>\n"
    )
fds.sort()
for fd in fds:
    summary.write(fd + ", feature dataset <br>\n")
    arcpy.env.workspace = fd
    fcs = arcpy.ListFeatureClasses()
    fcs.sort()
    for fc in fcs:
        dsc = arcpy.Describe(fc)
        if dsc.featureType == "Annotation":
            shp = "annotation"
        elif dsc.featureType != "Simple":
            shp = dsc.featureType
        else:
            shp = dsc.shapeType.lower()
        summary.write(
            space4
            + fc
            + ", "
            + shp
            + " feature class, "
            + str(guf.numberOfRows(fc))
            + " rows<br>\n"
        )
    arcpy.env.workspace = gdb_path
summary.write(vh.divend)

### Compact DB option
if compact_db == "true":
    ap("  Compacting " + os.path.basename(gdb_path))
    arcpy.Compact_management(gdb_path)
else:
    pass
summary.close()
errors.close()
ap("DONE")


"""
To be done:

    eliminate hard-coded path to ref_gmd (GeoMaterialDict as shipped with GeMS tool kit)

    Also:
      Maybe check for incorrectly-set up relationship classes?
"""
