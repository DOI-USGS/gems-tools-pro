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
import glob
import time
from pathlib import Path
import copy
import GeMS_utilityFunctions as guf
import GeMS_Definition as gdef
import validate_html as vh
import requests


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
schema_errors_missing_elements = ["Missing required elements"]
schema_errors_missing_fields = ["Missing or mis-defined fields"]

missing_required_values = [
    "Fields that are missing required values"
]  #  entries are [field, table]

all_ids = []  #  entries are [_IDvalue, table]
duplicate_ids = ["Duplicated _ID values"]  # entries are [value, table]

data_sources_ids = []  # _IDs from DataSources
# list of all references to DataSources. Entries are [value, table]
all_data_sources_refs = []
missing_source_ids = [
    "Missing DataSources entries. Only one reference to each missing entry is cited"
]
unused_source_ids = [
    "Entries in DataSources that are not otherwise referenced in database"
]
duplicated_source_ids = ["Duplicated source_IDs in DataSources"]

glossary_terms = []  # Terms from Glossary
all_glossary_refs = []  # list of all references to Glossary. Entries are [value, table]
missing_glossary_terms = [
    "Missing terms in Glossary. Only one reference to each missing term is cited"
]
unused_glossary_terms = ["Terms in Glossary that are not otherwise used in geodatabase"]
glossary_term_duplicates = ["Duplicated terms in Glossary"]

dmu_map_units = []
all_map_units = []  # list of all MapUnit references. Entries are [value, table]
missing_dmu_map_units = [
    "MapUnits missing from DMU. Only one reference to each missing unit is cited"
]
unused_dmu_map_units = [
    "MapUnits in DMU that are not present on map, in CMU, or elsewhere"
]
dmu_map_units_duplicates = ["Duplicated MapUnit values in DescriptionOfMapUnits"]

all_geo_material_values = []  # values of GeoMaterial cited in DMU or elsewhere
geo_material_errors = ["Errors associated with GeoMaterialDict and GeoMaterial values"]

all_dmu_key_values = []
hkey_errors = ["HierarchyKey errors, DescriptionOfMapUnits"]
#  values are [value, errorType].  Return both duplicates

topology_errors = ["Feature datasets with bad basic topology"]
topology_error_note = """
<i>Note that the map boundary commonly gives an unavoidable "Must Not Have Gaps" line error.
Other errors should be fixed. Level 2 errors are also Level 3 errors. Errors are
identified in feature classes within XXX-Validation.gdb</i><br><br>
"""

zero_length_strings = [
    'Zero-length, whitespace-only, or "&ltNull&gt" text values that probably should be &lt;Null&gt;'
]

srf_warnings = []
other_warnings = []
leading_trailing_spaces = ["Text values with leading or trailing spaces:"]

#######END GLOBAL VARIABLESS###################
def check_for_lock_files(gdb_path):
    old_dir = os.getcwd()
    os.chdir(gdb_path)
    lock_files = glob.glob("*.lock")
    n_lock_files = len(lock_files)
    if n_lock_files > 0:
        other_warnings.append(f"{str(n_lock_files)} lock files in database")
    os.chdir(old_dir)
    return


def check_sr(db_obj):
    srf = db_dict[db_obj]["spatialReference"]

    # check for NAD83 or WGS84
    if srf.type == "Geographic":
        pcsd = srf.datumName
    else:  # is projected
        pcsd = srf.PCSName
    if pcsd.find("World_Geodetic_System_1984") < 0 and pcsd.find("NAD_1983") < 0:
        srf_warnings.append(
            f"Spatial reference framework is {pcsd}. Consider reprojecting this dataset to NAD83 or WGS84"
        )


def get_hkey_errors(hks):
    # getHKeyErrors collects values with bad separators, bad element sizes, duplicates, and missing sequential values
    ap("Checking DescriptionOfMapUnits HKey values")
    hkey_errs = []

    # return early if HKs is empty
    if len(hks) == 0:
        hkey_errs.append("No HierarchyKey values?!")
        return hkey_errs

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
            hkey_errs.append(f'Multiple delimiters found: {", ".join(formatted)}')

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
                    hkey_errs.append(f"{new_keys[hkey]} --non-numeric fragment: {e}")

                # inconsistent fragment length
                if len(e) != fragment_length:
                    hkey_errs.append(f"{new_keys[hkey]} --bad fragment length: {e}")
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
            hkey_errs.append(f"{dupe} --duplicate hierarchy key")

    return hkey_errs


def is_feature_dataset_a_map(test_fd):
    #  examines fd to see if it is a geologic map:
    #    does it have a poly feature class named xxxMapUnitPolysxxx?
    #    does it have a polyline feature class named xxxContactsAndFaultsxxx?
    ap(f"  checking {test_fd} to see if it has MUP and CAF feature classes")
    map_bool = True
    caf = ""
    mup = ""
    fcs = [child["baseName"] for child in test_fd["children"]]
    for fc in fcs:
        if fc.find("ContactsAndFaults") > -1 and fc.lower().find("anno") == -1:
            caf = fc
        if fc.find("MapUnitPolys") > -1 and fc.lower().find("anno") == -1:
            mup = fc
    if caf == "" or mup == "":
        map_bool = False
    return map_bool, mup, caf


def check_topology(workdir, gdb_path, out_gdb, fd, req_fcs, level=2):
    # checks geologic-map topology of featureclasses mup and caf in feature dataset fd
    # results (# of errors - 1) are appended to global variable topologyErrors
    # gdb_path. out_gdb = full path.  fd, mup, caf = basename only
    # level is flag for how much topology to check -- level2 or level3
    ap(f"  checking topology of {fd}")

    # make errors fd
    out_fd = os.path.join(out_gdb, fd)
    if not arcpy.Exists(out_fd):
        arcpy.CreateFeatureDataset_management(out_gdb, fd, gdb_path + "/" + fd)

    # delete any existing topology, caf, mup and copy mup and caf to errors fd
    out_caf = os.path.join(out_fd, caf)
    out_mup = os.path.join(out_fd, mup)
    out_top = os.path.join(out_fd, f"{fd}_topology")
    for i in out_top, out_mup, out_caf:
        guf.testAndDelete(i)
    arcpy.Copy_management(os.path.join(gdb_path, fd, mup), out_mup)
    arcpy.Copy_management(os.path.join(gdb_path, fd, caf), out_caf)

    # create topology
    ap(f"    creating {out_top}")
    arcpy.CreateTopology_management(out_fd, os.path.basename(out_top))

    # add feature classes to topology
    arcpy.AddFeatureClassToTopology_management(out_top, out_caf, 1, 1)
    arcpy.AddFeatureClassToTopology_management(out_top, out_mup, 2, 2)

    # add rules
    ap("    adding level 2 rules to topology:")
    if arcpy.Exists(out_mup):
        for rule in ("Must Not Overlap (Area)", "Must Not Have Gaps (Area)"):
            ap(f"      {rule}")
            arcpy.AddRuleToTopology_management(out_top, rule, out_mup)
        ap("      " + "Boundary Must Be Covered By (Area-Line)")
        arcpy.AddRuleToTopology_management(
            out_top, "Boundary Must Be Covered By (Area-Line)", out_mup, "", out_caf
        )
    if level == 3:
        ap("    adding level 3 rules to topology:")
        for top_rule in (
            "Must Not Overlap (Line)",
            "Must Not Self-Overlap (Line)",
            "Must Not Self-Intersect (Line)",
        ):
            ap(f"      {top_rule}")
            arcpy.AddRuleToTopology_management(out_top, top_rule, out_caf)
    # validate topology
    ap("    validating topology")
    arcpy.ValidateTopology_management(out_top)
    name_token = os.path.basename(out_caf).replace("ContactsAndFaults", "")
    if name_token == "":
        name_token = "GeologicMap"
    name_token = f"errors_{name_token}Topology"

    for sfx in ("_point", "_line", "_poly"):
        guf.testAndDelete(os.path.join(out_fd, name_token + sfx))
    # export topology errors
    ap("    exporting topology errors")
    arcpy.ExportTopologyErrors_management(out_top, out_fd, name_token)
    n_errs = 0
    for sfx in ("_point", "_line", "_poly"):
        fc = os.path.join(out_fd, name_token + sfx)
        n_errs = n_errs + guf.numberOfRows(fc)
        if guf.numberOfRows(fc) == 0:
            guf.testAndDelete(fc)
    return n_errs - 1  # subtract the perimeter "Must not have gaps" error


def remove_duplicates(alist):
    no_dup_list = []
    for i in alist:
        if not i in no_dup_list:
            no_dup_list.append(i)
    return no_dup_list


def match_refs(defined_vals, all_refs):
    # for references to/from Glossary and DataSources
    # allrefs are [value, field, table]
    used = remove_duplicates(all_refs)
    used_vals = []
    unused = []
    missing = []
    plain_used = []
    for i in used:
        ### problem here with values in Unicode. Not sure solution will be generally valid
        # if not i[0].encode("ascii",'xmlcharrefreplace') in defined_vals and not i[0] in used_vals:
        if not i[0] in defined_vals and not i[0] in used_vals:
            missing.append(
                f"""<span class="value">{str(i[0])}</span>,  
                           field <span class="field">{i[1]}</span>,  
                           table <span class="table">{[2]}</span>"""
            )
        used_vals.append(i[0])
    missing.sort()
    for i in defined_vals:
        if not i in used_vals:
            unused.append(f'<span class="value">{str(i)}</span>')
            plain_used.append(i)
    unused.sort()

    return unused, missing, plain_used


def get_duplicate_ids(all_ids):
    ap("Getting duplicate _ID values")
    # get values that are duplicates
    all_ids.sort()
    last_id = ["", ""]
    duplicate_ids = []
    for ID in all_ids:
        if ID[0] == last_id[0]:
            duplicate_ids.append(ID)
        last_id = ID
    # remove duplicates
    dup_ids = remove_duplicates(duplicate_ids)
    dup_ids.sort()
    dups = []
    # convert to formatted HTML
    for ID in dup_ids:
        dups.append(
            f"""<span class="value">{ID[0]}</span> in 
                    table <span class="table">{ID[1]}</span>"""
        )
    return dups


def get_duplicates(term_list):
    term_list.sort()
    dups_list = []
    last_term = ""
    for t in term_list:
        if t == last_term:
            dups_list.append(t)
        last_term = t
    dups = remove_duplicates(dups_list)
    dups.sort()
    return dups


def append_values(global_list, some_values):
    for v in some_values:
        global_list.append(v)


def criterion_stuff(
    errors_name, summary_2, errors_2, txt_1, err_list, anchor_name, link_txt, is_level
):
    if len(err_list) == 1:
        txt_2 = "PASS"
    else:
        txt_2 = f"""<font color="#ff0000">FAIL &nbsp;</font><a href="{errors_name}
                   #{anchor_name}">{str(len(err_list)-1)} {link_txt}</a>"""
        is_level = False
        errors_2.append(
            '<h4><a name="' + anchor_name + '">' + err_list[0] + "</a></h4>"
        )
        if err_list == topology_errors:
            errors_2.append(topology_error_note)
        if len(err_list) == 1:
            errors_2.apppend(f"{space4}None<br>")
            ap("appending None")
        for i in err_list[1:]:
            errors_2.append(f"{space4}{i}<br>")
    summary_2.append(vh.table_row([txt_1, txt_2]))
    return is_level


def write_output_level_2(errors_name):  # need name of errors.html file for anchors
    is_level_2 = True  # set to false in Criterion
    summary_2 = []
    errors_2 = [vh.rdiv]
    summary_2.append(vh.table_start)

    txt_1 = """2.1 Has required elements: nonspatial tables DataSources, 
       DescriptionOfMapUnits, GeoMaterialDict; feature dataset GeologicMap with 
       feature classes ContactsAndFaults and MapUnitPolys"""
    is_level_2 = criterion_stuff(
        errors_name,
        summary_2,
        errors_2,
        txt_1,
        schema_errors_missing_elements,
        "MissingElements",
        "missing element(s)",
        is_level_2,
    )
    txt_1 = (
        "2.2 Required fields within required elements are present and correctly defined"
    )
    is_level_2 = criterion_stuff(
        errors_name,
        summary_2,
        errors_2,
        txt_1,
        schema_errors_missing_fields,
        "MissingFields",
        "missing or mis-defined field(s)",
        is_level_2,
    )
    txt_1 = """2.3 GeologicMap topology: no internal gaps or overlaps in MapUnitPolys, 
        boundaries of MapUnitPolys are covered by ContactsAndFaults"""
    is_level_2 = criterion_stuff(
        errors_name,
        summary_2,
        errors_2,
        txt_1,
        topology_errors,
        "Topology",
        "feature dataset(s) with bad topology",
        is_level_2,
    )
    txt_1 = (
        "2.4 All map units in MapUnitPolys have entries in DescriptionOfMapUnits table"
    )
    is_level_2 = criterion_stuff(
        errors_name,
        summary_2,
        errors_2,
        txt_1,
        missing_dmu_map_units,
        "dmuComplete",
        "map unit(s) missing in DMU",
        is_level_2,
    )
    txt_1 = "2.5 No duplicate MapUnit values in DescriptionOfMapUnit table"
    is_level_2 = criterion_stuff(
        errors_name,
        summary_2,
        errors_2,
        txt_1,
        dmu_map_units_duplicates,
        "NoDmuDups",
        "duplicated map unit(s) in DMU",
        is_level_2,
    )
    txt_1 = "2.6 Certain field values within required elements have entries in Glossary table"
    is_level_2 = criterion_stuff(
        errors_name,
        summary_2,
        errors_2,
        txt_1,
        missing_glossary_terms,
        "MissingGlossary",
        "term(s) missing in Glossary",
        is_level_2,
    )
    txt_1 = "2.7 No duplicate Term values in Glossary table"
    is_level_2 = criterion_stuff(
        errors_name,
        summary_2,
        errors_2,
        txt_1,
        glossary_term_duplicates,
        "NoGlossaryDups",
        "duplicated term(s) in Glossary",
        is_level_2,
    )
    txt_1 = "2.8 All xxxSourceID values in required elements have entries in DataSources table"
    is_level_2 = criterion_stuff(
        errors_name,
        summary_2,
        errors_2,
        txt_1,
        missing_source_ids,
        "MissingDataSources",
        "entry(ies) missing in DataSources",
        is_level_2,
    )
    txt_1 = "2.9 No duplicate DataSources_ID values in DataSources table"
    is_level_2 = criterion_stuff(
        errors_name,
        summary_2,
        errors_2,
        txt_1,
        duplicated_source_ids,
        "NoDataSourcesDups",
        "duplicated source(s) in DataSources",
        is_level_2,
    )
    summary_2.append(vh.table_end)
    errors_2.append(vh.divend)
    return is_level_2, summary_2, errors_2


def write_output_level_3(errors_name):
    is_level_3 = True  # set to false if ...
    summary_3 = []
    errors_3 = [vh.rdiv]
    summary_3.append(vh.table_start)
    txt_1 = "3.1 Table and field definitions conform to GeMS schema"
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        schema_errors_missing_fields,
        "Missingfields3",
        "missing or mis-defined element(s)",
        is_level_3,
    )
    txt_1 = """3.2 All map-like feature datasets obey topology rules. No  
        MapUnitPolys gaps or overlaps. No ContactsAndFaults overlaps,  
        self-overlaps, or self-intersections. MapUnitPoly boundaries covered by 
        ContactsAndFaults"""
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        topology_errors,
        "Topology3",
        "feature dataset(s) with bad topology",
        is_level_3,
    )
    txt_1 = "3.3 No missing required values"
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        missing_required_values,
        "MissingReqValues",
        "missing required value(s)",
        is_level_3,
    )
    txt_1 = "3.4 No missing terms in Glossary"
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        missing_glossary_terms,
        "MissingGlossary",
        "missing term(s) in Glossary",
        is_level_3,
    )
    txt_1 = "3.5 No unnecessary terms in Glossary"
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        unused_glossary_terms,
        "ExcessGlossary",
        "unnecessary term(s) in Glossary",
        is_level_3,
    )
    txt_1 = "3.6 No missing sources in DataSources"
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        missing_source_ids,
        "MissingDataSources",
        "missing source(s) in DataSources",
        is_level_3,
    )
    txt_1 = "3.7 No unnecessary sources in DataSources"
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        unused_source_ids,
        "ExcessDataSources",
        "unnecessary source(s) in DataSources",
        is_level_3,
    )
    txt_1 = "3.8 No map units without entries in DescriptionOfMapUnits"
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        missing_dmu_map_units,
        "MissingMapUnits",
        "missing map unit(s) in DMU",
        is_level_3,
    )
    txt_1 = "3.9 No unnecessary map units in DescriptionOfMapUnits"
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        unused_dmu_map_units,
        "ExcessMapUnits",
        "unnecessary map unit(s) in DMU",
        is_level_3,
    )
    txt_1 = (
        "3.10 HierarchyKey values in DescriptionOfMapUnits are unique and well formed"
    )
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        hkey_errors,
        "hkey_errors",
        "HierarchyKey error(s) in DMU",
        is_level_3,
    )
    txt_1 = """3.11 All values of GeoMaterial are defined in GeoMaterialDict. 
        GeoMaterialDict is as specified in the GeMS standard"""
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        geo_material_errors,
        "GM_Errors",
        "GeoMaterial error(s)",
        is_level_3,
    )
    txt_1 = "3.12 No duplicate _ID values"
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        duplicate_ids,
        "duplicate_ids",
        "duplicated _ID value(s)",
        is_level_3,
    )
    txt_1 = "3.13 No zero-length or whitespace-only strings"
    is_level_3 = criterion_stuff(
        errors_name,
        summary_3,
        errors_3,
        txt_1,
        zero_length_strings,
        "zero_length_strings",
        "zero-length or whitespace string(s)",
        is_level_3,
    )
    summary_3.append(vh.table_end)
    errors_3.append(vh.divend)
    return is_level_3, summary_3, errors_3


def find_other_stuff(wksp, ok_stuff):
    # finds files, feature classes, ... in a workspace
    #  that are not in ok_stuff and writes them to schema_extensions
    ap(f"  checking {os.path.basename(wksp)} for other stuff")
    walk = arcpy.da.Walk(wksp)
    for dirpath, dirnames, filenames in walk:
        if os.path.basename(dirpath) == os.path.basename(wksp):
            for fn in filenames:
                if fn not in ok_stuff:
                    dsc = arcpy.Describe(fn)
                    schema_extensions.append(
                        f'{dsc.dataType} <span class="table">{fn}</span>'
                    )


def check_metadata(val_dir, md_file):
    """
    Validate standalone metadata file.

    Args:
        val_dir (Path) : Path object to validation directory
        md_record (Path): Path object to XML metadata file

    Returns:
        metadata_checked (boolean): indicates whether the metadata were successfully checked
        passes_mp (booelan): indicates whether the metadata were validated with/out errors

        Writes re-ordered xml, error file, and text version of metadata to

    """
    # get a basename for the metadata file for naming output files
    md_name = md_file.stem
    val_xml = val_dir / f"{md_name}-validated.xml"
    err_txt = val_dir / f"{md_name}-metadata-errors.txt"
    md_txt = val_dir / f"{md_name}-metadata-text.txt"

    # send the metadata file to the API
    url = r"https://www1.usgs.gov/mp/service.php"
    with open(md_file, "rb") as f:
        r = requests.post(url, files={"input_file": f})

    if r.ok:
        # collect the 'link' array
        links = r.json()["output"]["link"]

        # save the output xml to disk
        req = requests.get(links["xml"])
        with open(str(val_xml), "wb") as f:
            f.write(req.content)

        # the intermediate xml sent to the API likely had some out-of-order
        # elements, but mp corrects those mistakes so the output xml doesn't have
        # them but the error file reports them. Instead of sending the
        # XML output to the API to be validated only to get a new error file,
        # just edit the error file to remove out-of-order warnings
        err_name = f"{str(md_file.stem)}-errors.txt"
        err_path = val_dir / err_name
        req = requests.get(links["error_txt"])
        with open(err_path, "wt") as f:
            for line in req.iter_lines():
                if not b"appears in unexpected order within" in line:
                    f.write(f"{line.decode('utf-8')}\n")

        # write the text version of the metadata?
        req = requests.get(links["txt"])
        with open(md_txt, "wt") as f:
            f.write(req.text)

        # print the error file contents to the geoprocessing window
        # and check for passing
        with open(err_txt, "r") as f:
            ap(f.read())
            for l in f:
                if l.split()[0] == "Error":
                    passes_mp = False
                else:
                    passes_mp = True

        # final report
        ap(f"Output files have been saved to {val_dir}")
        ap(f"Open {val_xml} in a xml or metadata editor to complete the record")

        metadata_checked = True

    else:
        ap("Could not write metadata to disk!", 1)
        ap(r.reason)
        metadata_checked = False
        passes_mp = False

    return metadata_checked, passes_mp


def check_field_definitions(def_table, compare_table=None):
    """Compares the fields in a compare_table to those in a controlled def_table
    There are two arguments, one optional, to catch the case where, for example
    we want to compare the fields in CSAMapUnitPolys with MapUnitPolys.
    gdef.tableDict will not have the key 'CSAMapUnitPolys'. The key MapUnitPolys is derived in
    def ScanTable from CSAMapUnitPolys as the table to which it should be compared.
    If the compare_table IS the name of a table in the GeMS definition; it doesn't need to be derived,
    it does not need to be supplied.
    """

    # build dictionary of required fields
    required_fields = {}
    optional_fields = {}
    required_field_defs = copy.deepcopy(gdef.tableDict[def_table])
    if compare_table:
        # update the definition of the _ID field to include a 'CSX' prefix
        prefix = compare_table[:3]
        id_item = [n for n in required_field_defs if n[0] == def_table + "_ID"]
        new_id = prefix + id_item[0][0]
        i = required_field_defs.index(id_item[0])
        required_field_defs[i][0] = new_id
    else:
        compare_table = def_table
    for field_def in required_field_defs:
        if field_def[2] != "Optional":
            required_fields[field_def[0]] = field_def
        else:
            optional_fields[field_def[0]] = field_def
    # build dictionary of existing fields
    try:
        existing_fields = {}
        fields = arcpy.ListFields(compare_table)
        for field in fields:
            existing_fields[field.name] = field
        # now check to see what is excess / missing
        for field in required_fields.keys():
            if field not in existing_fields:
                schema_errors_missing_fields.append(
                    '<span class="table">'
                    + compare_table
                    + '</span>, field <span class="field">'
                    + field
                    + "</span> is missing"
                )
        for field in existing_fields.keys():
            if (
                not (field.lower() in lc_standard_fields)
                and not (field in required_fields.keys())
                and not (field in optional_fields.keys())
            ):
                schema_extensions.append(
                    '<span class="table">'
                    + compare_table
                    + '</span>, field <span class="field">'
                    + field
                    + "</span>"
                )
            # check field definition
            f_type = existing_fields[field].type
            if field in required_fields.keys() and f_type != required_fields[field][1]:
                schema_errors_missing_fields.append(
                    '<span class="table">'
                    + compare_table
                    + '</span>, field <span class="field">'
                    + field
                    + "</span>, type should be "
                    + required_fields[field][1]
                )
            if field in optional_fields.keys() and f_type != optional_fields[field][1]:
                schema_errors_missing_fields.append(
                    '<span class="table">'
                    + compare_table
                    + '</span>, field <span class="field">'
                    + field
                    + "</span>, type should be "
                    + optional_fields[field][1]
                )
    except:
        schema_errors_missing_fields.append(
            '<span class="table">'
            + compare_table
            + "</span> could not get field list. Fields not checked."
        )
    del required_field_defs


def scan_table(table, fds=None):
    """
    Compare table against GeMS definition.

    Args:
        table (str): Name of table. Retrieved from db_dict keys.
        fds (str, optional): Name of feature dataset, optional. Defaults to None.

    Returns:
        map_units (list): List of MapUnit values found in table.

        Also writes to some global variables retrieved later

    """
    if fds is None:
        fds = ""
    ap(f"  scanning {table}")

    # check table and field definition against GeMS_Definitions
    if (
        db_dict[table]["gems_equivalent"] in gdef.tableDict
    ):  # table is defined in GeMS_Definitions
        is_extension = False
        field_defs = gdef.tableDict[table]
        check_field_definitions(table)
    elif (
        fds[:12] == "CrossSection"
        and table[:3] == "CS" + fds[12]
        and table[3:] in gdef.tableDict
    ):
        is_extension = False
        field_defs = gdef.tableDict[table[3:]]
        check_field_definitions(table[3:], table)
    else:  # is an extension
        is_extension = True
        d_type = db_dict[table]["dataType"]
        schema_extensions.append(f'{d_type} <span class="table">{table}</span>')

    # check for edit tracking
    try:
        if db_dict[table]["editorTrackingEnabled"]:
            other_warnings.append(
                f'Editor tracking is enabled on <span class="table">{table}</span>'
            )
    except:
        warn_text = f"""Cannot determine if Editor Tracking is enabled on 
            <span class="table">'{table}'</span>' or not;  
            probably due to an older version of ArcGIS Pro being used. 
            Check for this manually."""
        other_warnings.append(warn_text)

    ### assign fields to compliance categories:
    fields = db_dict[table]["fields"]
    field_names = [f.name for f in fields]

    # HKeyfield
    if table == "DescriptionOfMapUnits" and "HierarchyKey" in field_names:
        has_hkey = True
        hkey_index = field_names.index("HierarchyKey")
    else:
        has_hkey = False
        hkey_index = None

    # idField
    id_field = f"{table}_ID"
    if id_field in field_names:
        id_index = field_names.index(id_field)
        has_id_field = True
    else:
        has_id_field = False
        # we don't care that ArcGIS-controlled tables do not have _ID fields. What is the point?
        # Attachment tables are one kind but add others here as necessary
        # not the best logic to depend on the name, but there is no table type that identifies
        # these kinds of tables.
        if not "__ATTACH" in table:
            if is_extension:
                schema_errors_missing_fields.append(
                    f'<span class="table">{table}</span> lacks an _ID field'
                )
        else:
            pass

    # Term field
    if table == "Glossary" and "Term" in field_names:
        has_term_field = True
        term_field_index = field_names.index("Term")
    else:
        has_term_field = False
        term_field_index = None

    data_sources_indices = []
    gloss_term_indices = []
    no_nulls_field_indices = []
    string_field_indices = []
    map_unit_field_index = []
    geo_material_field_index = []
    special_dmu_field_indices = []

    # find objectid field, which might not be called OBJECTID
    # have also seen FID, OBJECTID_1, ATTACHMENTID
    oid_name = [f.name for f in fields if f.type == "OID"][0]
    obj_id_index = field_names.index(oid_name)

    # continue cataloging the field names
    for f in field_names:
        # dataSource fields
        if f.find("SourceID") > -1:
            data_sources_indices.append(field_names.index(f))

        # Glossary term fields
        if f in gdef.defined_term_fields_list:
            gloss_term_indices.append(field_names.index(f))

        # MapUnit fields
        if f == "MapUnit":
            map_unit_field_index.append(field_names.index(f))

        # GeoMaterial fields
        if f == "GeoMaterial":
            geo_material_field_index.append(field_names.index(f))

        # NoNulls fields
        if not is_extension:
            for fdef in field_defs:
                if f == fdef[0] and fdef[2] == "NoNulls":
                    no_nulls_field_indices.append(field_names.index(f))

        # String fields
        for ff in fields:
            if f == ff.baseName and ff.type == "String":
                string_field_indices.append(field_names.index(f))

        # special DMU fields, cannot be null if MapUnit is non-mull
        if table == "DescriptionOfMapUnits" and f in (
            "FullName",
            "Age",
            "GeoMaterial",
            "GeoMaterialConfidence",
            "DescriptionSourceID",
        ):
            special_dmu_field_indices.append(field_names.index(f))
    map_units = []

    ### open search cursor and run through rows
    with arcpy.da.SearchCursor(db_dict[table]["catalogPath"], field_names) as cursor:
        for row in cursor:
            if has_hkey and row[hkey_index] != None:
                all_dmu_key_values.append(row[hkey_index])

            if has_term_field:
                xx = row[term_field_index]
                if guf.not_empty(xx):
                    # ap(xx)
                    glossary_terms.append(guf.fix_null(xx))

            if has_id_field:
                xx = row[id_index]
                if guf.not_empty(xx):
                    all_ids.append([xx, table])
                    if table == "DataSources":
                        data_sources_ids.append(guf.fix_null(xx))

            for i in map_unit_field_index:
                xx = row[i]
                if guf.not_empty(xx):
                    if table == "DescriptionOfMapUnits":
                        dmu_map_units.append(guf.fix_null(xx))
                    else:
                        if not xx in map_units:
                            map_units.append(guf.fix_null(xx))
                        xxft = [row[i], "MapUnit", table]

                        if not xxft in all_map_units:
                            all_map_units.append(xxft)

            for i in no_nulls_field_indices:
                xx = row[i]
                if guf.empty(xx) or guf.is_bad_null(xx):
                    missing_required_values.append(
                        """f<span class="table">{table}</span>, field <span class="field">
                        {field_names[i]}</span>, {field_names[obj_id_index]} {str(row[obj_id_index])}"""
                    )

            for i in string_field_indices:
                xx = row[i]
                oxxft = """'<span class="table">{table}</span>, field <span class="field">
                    {field_names[i]}</span>, {field_names[obj_id_index]} {str(row[obj_id_index])}"""

                if (
                    i not in no_nulls_field_indices
                    and xx != None
                    and (xx.strip() == "" or xx.lower() == "<null>")
                ):
                    zero_length_strings.append(oxxft)
                if xx != None and xx.strip() != "" and xx.strip() != xx:
                    leading_trailing_spaces.append(space4 + oxxft)
            for i in geo_material_field_index:
                if guf.not_empty(row[i]):
                    if not row[i] in all_geo_material_values:
                        all_geo_material_values.append(row[i])
            for i in gloss_term_indices:
                if guf.not_empty(row[i]):
                    xxft = [row[i], field_names[i], table]
                    if not xxft in all_glossary_refs:
                        all_glossary_refs.append(xxft)
            for i in data_sources_indices:
                xx = row[i]
                if guf.not_empty(xx):
                    ids = [e.strip() for e in xx.split("|") if e.strip()]
                    for xxref in ids:
                        xxft = [xxref, field_names[i], table]
                        if not xxref in all_data_sources_refs:
                            all_data_sources_refs.append(xxft)
            if map_unit_field_index != [] and row[map_unit_field_index[0]] != None:
                for i in special_dmu_field_indices:
                    xx = row[i]
                    if guf.empty(xx) or guf.is_bad_null(xx):
                        missing_required_values.append(
                            """<span class="table">
                            {table}</span>, field <span class="field">{field_names[i]}
                            {field_names[i]} {str(row[obj_id_index])}"""
                        )

    return map_units


# all_geo_material_values = []  # values of GeoMaterial cited in DMU or elsewhere
# geo_material_errors = ['Errors associated with GeoMaterialDict and GeoMaterial values']
def check_geo_material_dict(gdb_path):
    ap("  checking GeoMaterialDict")
    gmd = gdb_path + "/GeoMaterialDict"
    ref_gm_dict = {}
    gm_dict = {}
    if arcpy.Exists(gmd):
        with arcpy.da.SearchCursor(gmd, ["GeoMaterial", "Definition"]) as cursor:
            for row in cursor:
                gm_dict[row[0]] = row[1]
        # geoMaterials = gm_dict.keys()  flagged as never used
        # check that all used values of GeoMaterial are in geoMaterials
        for i in all_geo_material_values:
            if not i in gm_dict.keys():
                geo_material_errors.append(
                    '<span class="value">'
                    + str(i)
                    + '</span> not defined in <span class="table">GeoMaterialDict</span>'
                )
        with arcpy.da.SearchCursor(ref_gmd, ["GeoMaterial", "Definition"]) as cursor:
            for row in cursor:
                ref_gm_dict[row[0]] = row[1]
        # check for equivalence with standard GeoMaterialDict
        ref_geo_materials = ref_gm_dict.keys()
        for i in gm_dict.keys():
            if i not in ref_geo_materials:
                geo_material_errors.append(
                    'Term **<span class="value">'
                    + i
                    + '</span>** is not in standard <span class="table">GeoMaterialDict</span> table'
                )
            else:
                if gm_dict[i] != ref_gm_dict[i]:
                    geo_material_errors.append(
                        'Definition of <span class="value">'
                        + i
                        + '</span> in <span class="table">GeoMaterialDict</span> does not match GeMS standard'
                    )
    else:
        ap("Table " + gmd + " is missing.")
    return


def delete_extra_rows(table, field, vals):
    # delete_extra_rows('Glossary','Term',unused)
    if len(vals) == 0:
        return
    ap("    removing extra rows from " + table)
    with arcpy.da.UpdateCursor(table, [field]) as cursor:
        for row in cursor:
            if row[0] in vals:
                ap("      " + row[0])
                cursor.deleteRow()
    return


##############start here##################
# get inputs

guf.checkVersion(version_string, rawurl, "gems-tools-pro")
args_len = len(sys.argv)

# we already know sys.argv[1] exists, no check
# gdb_path = Path(sys.argv[1])
gdb_path = Path(r"C:\AAA\gems\testing\testbed\dummy.gdb")
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

# edit session?
if guf.editSessionActive(gdb_path):
    arcpy.AddWarning(
        """\nDatabase is being edited. Results may be incorrect if there are 
        unsaved edits\n"""
    )

# appear to have a good database, proceed
# refresh geomaterial
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
# slice required_tables to ignore GeoMaterialDict
# required_tables should not have customized names; prefixes or suffixes of
# any kind. They might be snake_case, but the gdb_object_dict considers that
# required_tables = ["DataSources","DescriptionOfMapUnits","Glossary","GeoMaterialDict"]
for g_name in gdef.required_tables[0:3]:
    # look for the table name that has the gems_equivalent name
    tab_list = [k for k, v in db_dict.items() if v["gems_equivalent"] == g_name]
    if tab_list:
        scan_table(tab_list[0])
    else:
        schema_errors_missing_elements.append(
            f'Table <span class="table">{g_name}</span>'
        )

# evaluate the existence of and the spatial reference of at least one
# 'GeologicMap' feature dataset.
# but first bail if this is a geopackage which don't use feature datasets
if not is_gpkg:
    gmap_mapunits = []

    # look for GeologicMap feature datasets
    gmaps = [k for k, v in db_dict.items() if v["gems_equivalent"] == "GeologicMap"]
    if not gmaps:
        gmap_srf = ""
        schema_errors_missing_elements.append(
            'Feature dataset <span class="table">GeologicMap</span>'
        )
    else:
        for gmap in gmaps:
            # check the spatial reference
            check_sr(gmap)

            # in each GeologicMap feature dataset, there needs to be
            # ContactsAndFaults and MapUnitPolys
            is_map = False
            req_fcs = []
            children = gmap["children"]
            gems_fc = [c["gems_equivalent"] for c in children]
            if set(gdef.required_geologic_map_feature_classes).issubset(gems_fc):
                is_map = True

            if is_map:
                schema_errors_missing_elements.append(
                    f'Feature class <span class="table">{gmap}/{fc}</span>'
                )
                is_map = False

            # scan table for each entry in req_fcs. Should, at most, be two
            if req_fcs:
                for fc_name in req_fcs:
                    map_units = scan_table(fc_name)
                    append_values(gmap_mapunits, map_units)

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
else:
    # need evaluation of topology of paired geologic map feature classes here

    arcpy.env.workspace = gdb_path
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
