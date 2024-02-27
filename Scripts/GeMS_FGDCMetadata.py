#!/usr/bin/env python
# coding: utf-8
"""
GeMS_FGDCMetadata_AGP2.py
Automates the creation of many FGDC CSDGM required metadata elements from information in the 
database. Some GeMS-related text is inserted in a few free-text elements to describe
the schema, boilerplate information can be added from an optional template xml file, 
spatial information nodes are built and inserted as a workaround for the bug in 
ArcGIS Pro where spatial reference information is not exported into FGDC metadata, Entity-Attribute
sections are filled-in based on dictionaries in GeMS_Definition.py and my_definitions.py, and extraneous
process steps (created by ArcGIS every time a geoprocessing step is performed) can be removed.
"""
import arcpy  # arcpy needed for da.Describe(gdb) and exporting metadata')
from pathlib import Path
from lxml import etree
import sys
import GeMS_Definition as gDef
import GeMS_utilityFunctions as guf
from osgeo import ogr  # only used in def max_bounding
import spatial_utils as su
import copy
import requests

versionString = "GeMS_FGDCMetadata.py, version of 2/27/24"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_FGDCMetadata.py"
guf.checkVersion(versionString, rawurl, "gems-tools-pro")

gems_full_ref = """GeMS (Geologic Map Schema)--a standard format for the digital publication of geologic maps", available at http://ngmdb.usgs.gov/Info/standards/GeMS/"""

gems = "GeMS"

esri_attribs = {
    "objectid": "Internal feature number",
    "shape": "Internal geometry object",
    "shape_length": "Internal feature length, double",
    "shape_area": "Internal feature area, double",
    "ruleid": "Integer field that stores a reference to the representation rule for each feature.",
    "override": "BLOB field that stores feature-specific overrides to the cartographic representation rules.",
}


###### FUNCTIONS
def gdb_object_dict(gdb_path):
    """Returns a dictionary of table_name: da.Describe_table_properties
    when used on a geodatabase. GDB's will have tables, feature classes,
    and feature datasets listed under GDB['children']. But feature
    datasets will also have a 'children' key with their own children.
    gdb_object_dict() finds ALL children, regardless of how they are nested,
    and puts the information into a dictionary value retrieved by the name
    of the table.
    Works on geodatabases and geopackages!
    da.Describe is pretty fast (faster for gpkg, why?) and verbose
    """
    desc = arcpy.da.Describe(gdb_path)
    if desc["children"]:
        children = {child["name"]: child for child in desc["children"]}
        for child, v in children.items():
            # adding an entry for the feature dataset the item is in, if there is one
            v["feature_dataset"] = ""
            if children[child]["children"]:
                fd = children[child]["name"]
                more_children = {n["name"]: n for n in children[child]["children"]}
                for k, v in more_children.items():
                    v["feature_dataset"] = fd
                children = {**children, **more_children}

    # delete entries for feature datasets if any were found
    children = {
        k: v
        for (k, v) in children.items()
        if not children[k]["dataType"] == "FeatureDataset"
    }

    # and sanitize names that come from geopackages that start with "main."
    # trying to modify the children dictionary in-place wasn't producing expected results
    # we'll build a new dictionary with modified names
    if gdb_path.endswith(".gpkg"):
        new_dict = {}
        for child in children:
            if "." in child:
                new_name = child.split(".")[-1]
                new_dict[new_name] = children[child]
    else:
        new_dict = children

    # adding an entry for 'concatenated type' that will concatenate
    # featureType, shapeType, and dataType. eg
    # Simple Polygon FeatureClass
    # Simple Polyline FeatureClass
    # Annotation Polygon FeatureClass
    # this will go into Entity_Type_Definition
    for k, v in new_dict.items():
        if v["dataType"] == "Table":
            v["concat_type"] = "Nonspatial Table"
        elif v["dataType"] == "FeatureClass":
            v["concat_type"] = f"{v['featureType']} {v['shapeType']} {v['dataType']}"
        else:
            v["concat_type"] = v["dataType"]

    return new_dict


def max_bounding(db_path):
    north = []
    south = []
    west = []
    east = []
    for layer in ogr.Open(db_path):
        # if layer.GetGeomType() != 100:
        if "MapUnitPolys" in layer.GetName() or "ContactsAndFaults" in layer.GetName():
            if layer.GetSpatialRef():
                bounding = su.get_bounding(str(db_path), layer.GetName())
                north.append(bounding.find("northbc").text)
                south.append(bounding.find("southbc").text)
                west.append(bounding.find("westbc").text)
                east.append(bounding.find("eastbc").text)

    bounding.find("northbc").text = max(north)
    bounding.find("southbc").text = min(south)
    bounding.find("westbc").text = max(west)
    bounding.find("eastbc").text = min(east)

    return bounding


def catch_m2m(dictionary, field_value):
    """DataSourceIDs could be concatenated, eg., "DAS03 | DAS05"
    To list these values properly when writing out enumerated domains,
    look here for a delimiter, split the foreign keys, look them up, and
    return a concatenated string of sources
    or just return the dictionary entry if field_value is not concatenated
    """
    if not field_value is None:
        if "|" in field_value:
            defs = []
            src_ids = field_value.split("|")
            for src_id in src_ids:
                src_id = src_id.strip()
                if src_id in dictionary:
                    defs.append(dictionary[src_id][0])
                else:
                    defs.append(f"PROVIDE A DEFINITION FOR {src_id}")
            def_str = " | ".join(defs)
            return def_str
        else:
            if field_value in dictionary:
                return dictionary[field_value]
            else:
                return f"PROVIDE A DEFINITION FOR {field_value}"
    else:
        return


def which_dict(tbl, fld):
    if fld == "MapUnit":
        return units_dict
    elif fld == "GeoMaterialConfidence" and tbl == "DescriptionOfMapUnits":
        return gDef.GeoMatConfDict
    elif fld == "GeoMaterial":
        return geomat_dict
    elif fld.find("SourceID") > -1:
        return sources_dict
    else:
        return gloss_dict


def term_dict(obj_dict, table, fields):
    """sources_dict needs to be built first"""
    # always supply field to be the dictionary key as fields[0]
    # and the 'ID' field as fields[-1]
    if table in obj_dict:
        arcpy.AddMessage(f"Building dictionary for {table}")
        table_path = obj_dict[table]["catalogPath"]
        data_dict = {}
        cursor = arcpy.da.SearchCursor(table_path, fields)
        for row in cursor:
            if table == "DataSources":
                if not row[1] is None:
                    data_dict[row[0]] = row[1]
            elif table == "GeoMaterialDict":
                data_dict[row[0]] = [row[1]]
                data_dict[row[0]].append(gems)
            elif table == "DescriptionOfMapUnits":
                if not row[2] is None:
                    data_dict[row[0]] = [row[2]]
                else:
                    if not row[1] is None:
                        data_dict[row[0]] = [row[1]]
                data_dict[row[0]].append(catch_m2m(sources_dict, row[-1]))
            else:
                data_dict[row[0]] = list(row[1:-1])
                data_dict[row[0]].append(catch_m2m(sources_dict, row[-1]))
        return data_dict
    else:
        return None


def clear_children(element, child_tag):
    for child in element.findall(child_tag):
        element.remove(child)


def extend_branch(node, xpath):
    """function to test for full xpath and if only partially exists,
    builds it out the rest of the way"""
    # search for nodes on the xpath, building them from the list, delimited by /
    path_nodes = xpath.split("/")
    for nibble in path_nodes:
        search_node = node.find(nibble)
        if search_node is not None:
            node = search_node
        else:
            e = etree.Element(nibble)
            node.append(e)
            node = node.find(nibble)


def remove_node(node, xpath):
    """remove a node from the given node using an xpath"""
    child = node.find(xpath)
    parent = child.getparent()
    parent.remove(child)


def add_entity(fc_name, elem_dict):
    ##metadata
    ##  entity
    ##    detailed
    ##      enttyp
    ##        enttypl
    ##        enttypd
    ##        enttypds
    ##
    ## return the detailed node
    # print(fc_name)
    # add a note about which feature dataset the entity is in
    # when a dataset contents dictionary is built using ogr_db_contents, no feature datasets are
    # detected, the following conditional might not ever get called. Have to see if people care about
    # documenting which feature dataset a feature class is found in. Feature datasets are meaningless outside
    # of ArcGIS products.
    if elem_dict["feature_dataset"]:
        fd_name = elem_dict["feature_dataset"]
        append = f"In the original file geodatabase, this dataset is found within the {fd_name} feature dataset."
    else:
        append = ""

    # add a detailed node for each database object
    detailed = etree.Element("detailed")

    # create enttyp node, but append to it before appending to the detailed node
    enttyp = etree.Element("enttyp")

    # create entity label node and add name
    enttypl = etree.Element("enttypl")
    enttypl.text = elem_dict["name"]

    # if the table name is in the GeMS entityDict, this is a GeMS controlled table
    # no annotation feature classes are described in entityDict
    if fc_name in gDef.entityDict:
        desc = f"{gDef.entityDict[fc_name]} {append}".strip()
        desc_source = gems

    # users might have their own tables defined in myEntityDict
    # these entries take the form of
    # 'name of table': ['definition', 'definition source'] so index the value
    elif fc_name in myEntityDict:
        desc = myEntityDict[fc_name][0].strip()
        desc_source = myEntityDict[fc_name][1]

    # if this is an annotation feature class, this is an ESRI controlled table
    elif elem_dict["concat_type"] == "Annotation Polygon FeatureClass":
        desc = "ArcGIS annotation feature class"
        desc_source = "ESRI"

    else:
        # print('not found')
        # add logging here for report if a description cannot be found
        arcpy.AddWarning(f"No definition found for {fc_name}")
        if not missing:
            desc = ""
            desc_source = ""
        else:
            desc = "MISSING"
            desc_source = "MISSING"

    # create entity description and add description
    enttypd = etree.Element("enttypd")
    enttypd.text = desc

    # create entity description source and add source
    enttypds = etree.Element("enttypds")
    enttypds.text = desc_source

    for n in [enttypl, enttypd, enttypds]:
        enttyp.append(n)

    # append the entity node to the detailed node
    detailed.append(enttyp)

    # append the detailed node to the dataqual node
    base_md.find("eainfo").append(detailed)

    return detailed


def add_attributes(fc_name, detailed_node):
    arcpy.AddMessage(f"Adding attribute and value definitions for {fc_name}")
    ##metadata
    ##  eainfo
    ##    detailed
    ##    attr
    ##      attrlabl
    ##      attrdef
    ##      attrdefs
    ##      attrdomv
    ##        domain (udom, edom, rdom)
    ##      attrdomv
    ##        domain (udom, edom, rdom), etc each domain range must be child to an attrdomv node

    # print(fc_name)

    # check for attrdefs = annotation class and set all attrdefs to ESRI
    # and unrepresentable domain

    # check for whether this is an annotation feature class
    describe = obj_dict[fc_name]

    if describe["concat_type"] == "Annotation Polygon FeatureClass":
        anno_bool = True
    else:
        anno_bool = False

    fc_fields = [f.name for f in obj_dict[fc_name]["fields"]]
    for field in fc_fields:
        # create Attribute node
        attr = etree.Element("attr")

        # create Attribute_Label node and fill it out
        attrlabl = etree.Element("attrlabl")
        attrlabl.text = field

        # attribute definition, source, and domain nodes, empty for now
        attrdef = etree.Element("attrdef")
        attrdefs = etree.Element("attrdefs")

        # first, look for a key in attribDict
        # using endswith() catches cases where key is at the END of the field name
        # this allows people to customize the name of their GeMS-controlled field, ie
        # MySpecialTable_ID, SurficialMapUnit, lowerBoundingAge
        # might not be used much, but is also inexpensive to implement and
        # is, at least partially, useful to catch _ID field names
        found_attrib = False
        res = [key for key in gDef.attribDict if field.endswith(key)]
        key = None
        if res:
            key = res[0]
            def_text = gDef.attribDict[
                key
            ]  # assuming here that if res isn't empty, there is only one key!
            source_text = gems
            found_attrib = True
            del res

        # look for a key myAttribDict
        try:
            res = [key for key in myDef.myAttribDict if field.endswith(key)]
        except:
            res = None
        if res:
            key = res[0]
            def_text = myDef.myAttribDict[key][0]
            source_text = myDef.myAttribDict[key][1]
            found_attrib = True
            del res

        # second, check for fields in an annotation feature class
        # should be defined as ESRI and have unrepresentable domains
        if anno_bool:
            def_text = "Value controls placement or representation of annotation"
            source_text = "ESRI"
            found_attrib = True

        # third, check for ESRI fields
        # after anno_bool so fields like OBJECTID, SHAPE, etc. can get changed back from
        # how they were set above
        if field.lower() in esri_attribs:
            def_text = esri_attribs[field.lower()]
            source_text = "ESRI"
            found_attrib = True

        # fourth, if the attribute has not been found
        if found_attrib == False:
            if missing:
                def_text = "MISSING"
                source_text = "MISSING"
            else:
                def_text = ""
                source_text = ""

            # add warnings if no definition and source were found
            arcpy.AddWarning(f"Cannot find definition for {field} in {fc_name}")
            arcpy.AddWarning(f"Cannot find definition source for {field} in {fc_name}")

        # append the nodes above before evaluating the value domain
        attrdef.text = def_text
        attrdefs.text = source_text
        for n in [attrlabl, attrdef, attrdefs]:
            attr.append(n)

        # UNREPRESENTABLE DOMAINS
        # value might be found in unrepresentableDomainDict
        if key in gDef.unrepresentableDomainDict:
            attrdomv = etree.Element("attrdomv")
            udom = etree.Element("udom")
            udom.text = gDef.unrepresentableDomainDict[key]
            attrdomv.append(udom)
            attr.append(attrdomv)

        # # value might be found in myUnrepresentableDomainDict
        # if key in myunrepresentableDomainDict:
        # arcpy.AddMessage("        Author-defined unrepresentable value domain")
        # attrdomv = etree.Element('attrdomv')
        # udom = etree.Element('udom')
        # udom.text = myUnrepresentableDomainDict[key]
        # attrdomv.append(udom)
        # attr.append(attrdomv)

        # look for fields that have range domains
        elif key in gDef.rangeDomainDict:
            arcpy.AddMessage("        Range value domain definition found")
            attrdomv = etree.Element("attrdomv")
            rdom = etree.Element("rdom")
            for n, i in [["rdommin", 0], ["rdommax", 1], ["attrunit", 2]]:
                range_attr = etree.Element(n)
                range_attr.text = gDef.rangeDomainDict[key][i]
                rdom.append(range_attr)
            attrdomv.append(rdom)
            attr.append(attrdomv)

        # look for fields that have enumerated domains
        elif key in gDef.enumeratedValueDomainFieldList:
            # collect a unique set of all the values of this attribute
            with arcpy.da.SearchCursor(
                obj_dict[fc_name]["catalogPath"], field
            ) as cursor:
                fld_vals = set([row[0] for row in cursor if not row[0] is None])

            # special case for listing the values in *SourceID fields
            # with other tables, the value of Source in DataSources would
            # go into edomvds, the value definition source, but when enumerating
            # the values of DataSourceID, we will put Source into edomvd,
            # the value definition
            for val in fld_vals:
                # if enumerated values, have to build an attrdomv node for each value
                attrdomv = etree.Element("attrdomv")
                if field.endswith("SourceID"):
                    val_text = catch_m2m(sources_dict, val)
                    val_source = "This report"

                # otherwise, find the appropriate dictionary and put the definition
                # and definition source into def_text and def_source
                else:
                    val_dict = which_dict(fc_name, field)
                    if val in val_dict:
                        val_text = val_dict[val][0]
                        val_source = val_dict[val][1]
                    else:
                        if missing:
                            val_text = ""
                            val_source = ""
                        else:
                            val_text = "MISSING"
                            val_source = "MISSING"

                    # report the missing values
                    if val_text in ["", "MISSING"]:
                        arcpy.AddWarning(
                            f'Cannot find domain value definition for value "{val}", field {field}'
                        )
                    if val_source in ["", "MISSING"]:
                        arcpy.AddWarning(
                            f'Cannot find domain value definition source for value "{val}", field {field}'
                        )

                # build the nodes and append
                edom = etree.Element("edom")
                edomv = etree.Element("edomv")
                edomv.text = str(val)
                edomvd = etree.Element("edomvd")
                edomvd.text = val_text
                edomvds = etree.Element("edomvds")
                edomvds.text = val_source

                for n in [edomv, edomvd, edomvds]:
                    edom.append(n)
                attrdomv.append(edom)
                attr.append(attrdomv)

        else:
            attrdomv = etree.Element("attrdomv")
            udom = etree.Element("udom")
            udom.text = "Unrepresentable domain"
            attrdomv.append(udom)
            attr.append(attrdomv)

        detailed_node.append(attr)


def validate_online(md_record):
    """validate the xml metadata against the USGS metadata validation service API"""
    # first write out the xml dom that is in memory to a file on disk
    temp_path = db_dir / "temp.xml"
    et = etree.ElementTree(md_record)
    with open(temp_path, "wb") as f:
        et.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)

    # send the temp file to the API
    url = r"https://www1.usgs.gov/mp/service.php"
    with open(temp_path, "rb") as f:
        r = requests.post(url, files={"input_file": f})

    if r.ok:
        # collect the 'link' array
        links = r.json()["output"]["link"]

        # save the output xml to disk
        req = requests.get(links["xml"])
        with open(mr_xml, "wb") as f:
            f.write(req.content)

        # the intermediate xml sent to the API likely had some out-of-order
        # elements, but mp corrects those mistakes so the output xml doesn't have
        # them but the error file reports them. Instead of sending the
        # XML output to the API to be validated only to get a new error file,
        # just edit the error file to remove out-of-order warnings
        err_name = f"{str(mr_xml.stem)}-errors.txt"
        err_path = db_dir / err_name
        req = requests.get(links["error_txt"])
        report = [n.decode("utf-8") for n in req.iter_lines()]
        n_warn = 0
        with open(err_path, "wt") as f:
            for line in report[0:-1]:
                if not "appears in unexpected order within" in line:
                    f.write(f"{line}\n")
                else:
                    n_warn += 1

            # edit the number of warnings since we just removed n_warn number
            last_line = report[-1]
            if "warnings" in last_line:
                parts = last_line.split(", ")
                e = []
                for c in parts[1]:
                    if c.isdigit():
                        e.append(c)
                a = "".join(e)
                b = int(a) - n_warn
                if b == 0:
                    new_line = parts[0]
                else:
                    new_line = f"{parts[0]}, {b} warnings"
                f.write(new_line)
            else:
                f.write(last_line)

        # collect the text version of the metadata?
        if text_bool:
            text_name = f"{str(mr_xml.stem)}.txt"
            text_path = db_dir / text_name
            req = requests.get(links["txt"])
            with open(text_path, "wt") as f:
                f.write(req.text)

        # print the error file contents to the geoprocessing window
        with open(err_path, "r") as f:
            arcpy.AddMessage(f.read())

        # final report
        arcpy.AddMessage(f"Output files have been saved to {db_dir}")
        arcpy.AddMessage(
            f"Open {mr_xml} in a xml or metadata editor to complete the record"
        )

        # cleanup
        # temp_path.unlink()
        return True
    else:
        arcpy.AddError("Could not write metadata to disk!")
        arcpy.AddWarning(r.reason)


# #### ARGUMENTS
# Ways to run this tool
# 1. the path to the dataset
# 2. optional template xml with producer content, that is, elements filled out by the producer that cannot be automated
# 3. if not selected, boolean whether to export the metadata from ArcGIS format file or start a brand new xml file that is filled out as much as possible with automated content, but will still need to have producer content added.
# 4. optional entity attribute data dictionary
# 5. flag for whether to have process steps erased, left as exported from arcpy, or replaced with steps from the optional template. 'remove', 'remain', 'replace', default='remain'
#
# About my_definitions.py
#
# myEntityDict and myAttribDict take a slightly different form from their similar dictionaries in GeMS_Definition.py. We want to be able to save a definition source for each entry there rather than hardcode it in the tool script, eg., 'This publication' or 'GeMS'. Each entry in those dictionaries takes the form
#
# 'object name': ['definition', 'definition source']
#
# But unrepresentable and range domains do not have definition sources so just update the GeMS Definitions dictionaries with the custom ones.
#
# Enumerated domain values DO have value sources but those come from the Glossary

# the database
db_path = Path(sys.argv[1])
arcpy.AddMessage("Building dictionary of database contents")
obj_dict = gdb_object_dict(str(db_path))

# export embedded metadata? concert string to boolean
if sys.argv[2].lower() in ["true", "yes"]:
    arc_md = True
else:
    arc_md = False

# my_definitions.py
my_defs_path = Path(sys.argv[3])
if my_defs_path.is_file():
    mod_name = my_defs_path.stem
    import importlib.util

    spec = importlib.util.spec_from_file_location(mod_name, my_defs_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["my_definitions"] = module
    spec.loader.exec_module(module)
    import my_definitions as myDef

    if "myEntityDict" in dir(myDef):
        myEntityDict = myDef.myEntityDict

    # try updating the GeMS dictionaries, but if the custom ones do not exist don't throw an
    # error, just pass
    try:
        gDef.unrepresentableDomainDict.update(myDef.myUnrepresentableDomainDict)
    except:
        pass

    try:
        gDef.rangeDomainDict.update(myDef.myRangeDomainDict)
    except:
        pass
else:
    myEntityDict = {}

# path to template file
template_path = sys.argv[4]

# what to do with data sources.
# True - remove any existing first
sources_choice = {
    "save only DataSources": 1,
    "save only embedded sources": 2,
    "save only template sources": 3,
    "save DataSources and embedded sources": 4,
    "save DataSources and template sources": 5,
    "save embedded and template sources": 6,
    "save all sources": 7,
    "save no sources": 8,
}

sources_param = sources_choice[sys.argv[5]]

# what to do with process steps, dataqual/lineage/procstep
history_choices = {
    "clear all history": 1,
    "save only template history": 2,
    "save only embedded history": 3,
    "save all history": 4,
}

history_param = history_choices[sys.argv[6]]

# convert the 'missing definitions' argument to boolean
if "MISSING" in sys.argv[7]:
    missing = True
else:
    missing = False

# convert text file choice to boolean
# export embedded metadata? concert string to boolean
if sys.argv[8].lower() in ["true", "yes"]:
    text_bool = True
else:
    text_bool = False

# dictionaries of some tables
# term_dict returns [term]:[definition, sourceid]
sources_dict = term_dict(obj_dict, "DataSources", ["DataSources_ID", "Source"])
units_dict = term_dict(
    obj_dict,
    "DescriptionOfMapUnits",
    ["MapUnit", "Name", "Fullname", "DescriptionSourceID"],
)
geomat_dict = term_dict(obj_dict, "GeoMaterialDict", ["GeoMaterial", "Definition"])
gloss_dict = term_dict(
    obj_dict, "Glossary", ["Term", "Definition", "DefinitionSourceID"]
)

# name of gdb
db_name = db_path.stem

# path to the parent folder
db_dir = db_path.parent

# a dictionary of all xml nodes we will be working with in this script
deez_nodes = {
    "gems_nodes": {
        "suppl": {
            "xpath": "idinfo/descript/supplinf",
            "text": f"{db_name} is a composite geodataset that conforms to {gems_full_ref}. Metadata records associated with each element within the geodataset contain more detailed descriptions of their purposes, constituent entities, and attributes.). An OPEN shapefile versions of the dataset is also available. It consists of shapefiles, DBF files, and delimited text files and retains all information in the native geodatabase, but some programming will likely be necessary to assemble these components into usable formats. These metadata were prepared with the aid of script {versionString}.",
        },
        "attraccr": {
            "xpath": "dataqual/attracc/attraccr",
            "text": "Confidence that a feature exists and confidence that a feature is correctly identified are described in per-feature attributes ExistenceConfidence and IdentityConfidence.",
        },
        "horizpar": {
            "xpath": "dataqual/posacc/horizpa/horizpar",
            "text": "Estimated accuracy of horizontal location is given on a per-feature basis by attribute LocationConfidenceMeters. Values are expected to be correct within a factor of 2. A LocationConfidenceMeters value of -9 or -9999 indicates that no value has been assigned.",
        },
    },
    "source_nodes": {
        "lineage": {"xpath": "dataqual/lineage"},
        "title": {"xpath": "srccite/citeinfo/title"},
        "onlink": {"xpath": "srccite/citeinfo/onlink"},
    },
    "spatial_nodes": {
        "spdom": {"xpath": "idinfo/spdom"},
        "spdoinfo": {"xpath": "spdoinfo"},
        "spref": {"xpath": "spref"},
    },
    "entity_nodes": {"eainfo": {"xpath": "eainfo"}},
}

# export master record
mr_xml = db_dir / f"{db_name}-metadata.xml"

# remove the output file if it already exists
if mr_xml.exists():
    mr_xml.unlink()

if arc_md:
    arcpy.AddMessage("Exporting embedded ArcGIS metadata to FGDC")
    # export the metadata from Arc
    # for now, assuming that metadata have been added to GDB itself.
    # This is different from Ralph's ArcMap FGDC tools which presume metadata
    # were added to GeologicMap - I don't think that's a good idea.
    src_md = arcpy.metadata.Metadata(str(db_path))
    src_md.exportMetadata(str(mr_xml), "FGDC_CSDGM")
    # make an lxml etree
    base_md = etree.parse(str(mr_xml)).getroot()

    # sources_param 1, 3, 5, 8 call for no embedded data sources
    if sources_param in [1, 3, 5, 8]:
        extend_branch(base_md, "dataqual/lineage")
        base_lineage = base_md.find(".//lineage")
        arcpy.AddMessage("removing sources - arc_md")
        clear_children(base_lineage, "srcinfo")

    if history_param < 3:
        extend_branch(base_md, "dataqual/lineage")
        base_lineage = base_md.find(".//lineage")
        clear_children(base_lineage, "procstep")

else:
    # we have to make a metadata document from scratch
    # make the root
    arcpy.AddMessage("Building database metadata from scratch")
    base_md = etree.Element("metadata")

# make the required elements
# spdom and spref (indices 2 and 3, respectively) will be added in another function)
child_nodes = [
    ["idinfo", 0],
    ["dataqual", 1],
    ["eainfo", 4],
    ["distinfo", 5],
    ["metainfo", 6],
]
arcpy.AddMessage("Creating the following elements:")
for child in child_nodes:
    if base_md.find(child[0]) is None:
        arcpy.AddMessage(f"  {child[0]}")
        elem = etree.Element(child[0])
        i = child[1]
        base_md.insert(i, elem)

# use spatial_utils from Metadata Wizard tools to add spatial stuff
# An option here is to include `spdom` and `spref` in the routine above, to check that all 1st level children exist, and then ask if they should be updated in a user-supplied template xml. They might already exist in that case and the user may know they want to use their own, rather than have them calculated here.

# find the bounding box that covers the extent of all features
try:
    if base_md.find("idinfo/spdom/bounding") is None:
        arcpy.AddMessage("  spdom")
        spdom = etree.Element("spdom")
        bounding = max_bounding(str(db_path))
        spdom.append(bounding)
        base_md.find("idinfo").append(spdom)
except Exception as error:
    e = """Could not calculate a bounding box.
    Set environment variable PROJ_LIB to location of proj.db and try again.
    See the ArcGIS Pro wiki for more information - https://github.com/usgs/gems-tools-pro/wiki/GeMS-Tools-Documentation#BuildMetadata"""
    arcpy.AddError(e)
    arcpy.AddError(error)
    sys.exit()

# collect the feature classes and inspect the sdtsterm
if base_md.find("spdoinfo") is None:
    fcs = [k for k in obj_dict if "FeatureClass" in obj_dict[k]["concat_type"]]
    arcpy.AddMessage("  spdoinfo")
    spdoinfo = su.get_spdoinfo(str(db_path), fcs[0])
    ptvctinf = spdoinfo.find("ptvctinf")
    for fc in fcs[1:]:
        arcpy.AddMessage(f"\rspdoinfo/sdtsterm for {fc}")
        lyr_spdo = su.get_spdoinfo(str(db_path), fc)
        sdtsterm = lyr_spdo.find("ptvctinf/sdtsterm")
        ptvctinf.append(sdtsterm)
    spdoinfo.append(ptvctinf)
    base_md.insert(2, spdoinfo)

if base_md.find("spref") is None:
    arcpy.AddMessage("spref")
    try:
        spref_node = su.get_spref(str(db_path), "MapUnitPolys")
    except Exception as e:
        arcpy.AddError(
            """Could not determine the coordinate system of MapUnitPolys.
        Check in ArcCatalog that it is valid"""
        )
        arcpy.AddError(e)
        sys.exit()
    base_md.insert(3, spref_node)

# add the rest of the gems_nodes
g_nodes = deez_nodes["gems_nodes"]
arcpy.AddMessage("Adding GeMS language in the following elements...")
for n in g_nodes:
    arcpy.AddMessage(f"  {g_nodes[n]['xpath']}")
    if base_md.find(g_nodes[n]["xpath"]) is not None:
        e = base_md.find(g_nodes[n]["xpath"])
        if len(e.text) > 1:
            e.text = e.text + f"\n{g_nodes[n]['text']}"
        else:
            e.text = f"{g_nodes[n]['text']}"
    else:
        extend_branch(base_md, g_nodes[n]["xpath"])
        e = base_md.find(g_nodes[n]["xpath"])
        e.text = g_nodes[n]["text"]

## add data sources; srcinfo nodes
## for each row in dataSources, create
##   srcinfo
##      srccite
##         citeinfo
##            title  Source
##            onlink URL
##      srccitea DataSourceID
extend_branch(base_md, deez_nodes["source_nodes"]["lineage"]["xpath"])
if sources_param in [1, 4, 5, 7]:
    if "DataSources" in obj_dict:
        arcpy.AddMessage("Adding DataSources")
        source_nodes = deez_nodes["source_nodes"]
        lineage = base_md.find(source_nodes["lineage"]["xpath"])

        ds_path = obj_dict["DataSources"]["catalogPath"]
        fields = ["Source", "URL", "DataSources_ID"]
        cursor = arcpy.da.SearchCursor(ds_path, fields)
        for row in cursor:
            # make a srcinfo node
            srcinfo = etree.Element("srcinfo")

            # add three child nodes to the srcinfo
            # title node
            extend_branch(srcinfo, source_nodes["title"]["xpath"])
            title = srcinfo.find(source_nodes["title"]["xpath"])
            title.text = row[0]
            # title.text = row.GetField(get_real_name('DataSources', 'Source'))

            # onlink node
            if row[1]:
                extend_branch(srcinfo, source_nodes["onlink"]["xpath"])
                onlink = srcinfo.find(source_nodes["onlink"]["xpath"])
                onlink.text = row[1]

            # source citation abbreviation
            srccitea = etree.Element("srccitea")
            srccitea.text = row[2]
            srcinfo.append(srccitea)

            # add this srcinfo to the lineage node
            lineage.append(srcinfo)
    else:
        arcpy.AddError("There are no data sources to add!")

# add Entity Attributes
arcpy.AddMessage("Adding metadata for the following feature classes:")
for k, v in obj_dict.items():
    detailed = add_entity(k, v)
    if "fields" in obj_dict[k]:
        add_attributes(k, detailed)

# merge with template
# If no template specified, just write out the metadata as generated here which could include embedded metadata.
#
# If template specified:
# From the `deez_nodes` dictionary:
# * `gems_nodes` text will be appended to any existing node text
# * `source_nodes` will be appended or replace existing, depending on choice
# * `spatial_nodes` will always replace any existing
# * `entity_nodes` will always replace any existing. Add definitions later in an editor or prepare a `my_definitions.py` type file for runtime additions.
#
# In any case:
# `dataqual/lineage/procstep` process steps removed if user says so. Replace with one process step; 'this script'?

if Path(template_path).is_file():
    arcpy.AddMessage(f"Migrating database metadata to {template_path}")
    template_root = etree.parse(template_path).getroot()

    # adding text for GeMS nodes
    # if the xpaths already exist in the template metadata,
    # append the GeMS text to the end. Otherwise,
    # add the node and the text
    for elem in deez_nodes["gems_nodes"]:
        check_path = deez_nodes["gems_nodes"][elem]["xpath"]

        # find the node in the automated metadata
        add_node = base_md.find(check_path)

        # look for the node in the template metadata
        check_node = template_root.find(check_path)

        if check_node is not None:
            if check_node.text is not None:
                check_node.text = check_node.text + f"\n {add_node.text}"
        else:
            extend_branch(template_root, check_path)
            new_node = template_root.find(check_path)
            new_node.text = add_node.text

    # adding the spatial node information gathered through this tool
    for elem in deez_nodes["spatial_nodes"]:
        check_path = deez_nodes["spatial_nodes"][elem]["xpath"]
        # find the node in the automated metadata
        add_node = copy.deepcopy(base_md.find(check_path))

        # if we run extend_branch on template_root we, can be certain the node exists,
        # then replace it
        extend_branch(template_root, check_path)

        # look for the node in the template metadata
        check_node = template_root.find(check_path)

        parent_node = check_node.getparent()
        parent_node.remove(check_node)
        parent_node.append(add_node)

    # building sources depending on sources_param
    extend_branch(template_root, deez_nodes["source_nodes"]["lineage"]["xpath"])
    template_lineage = template_root.find(
        deez_nodes["source_nodes"]["lineage"]["xpath"]
    )

    # choices 1 and 2 are equal to removing all template sources
    if sources_param in [1, 2, 4, 8]:
        template_sources = template_lineage.findall("srcinfo")
        for elem in template_sources:
            template_lineage.remove(elem)

    # most source choices are equal to adding all base_md sources
    # whether these are from DataSources only, embedded only, or a combination
    # is determined above
    if sources_param in [1, 2, 4, 5, 6, 7]:
        basemd_lineage = base_md.find(deez_nodes["source_nodes"]["lineage"]["xpath"])
        base_sources = basemd_lineage.findall("srcinfo")
        if len(base_sources) > 1:
            for child in base_sources:
                child_copy = copy.deepcopy(child)
                template_lineage.append(child_copy)

    # add all entity attribute nodes
    ea_nodes = base_md.find("eainfo").findall("detailed")

    # default for now will be to remove all detailed nodes and replace with those
    # generated from the attribute dictionaries
    extend_branch(template_root, "eainfo")
    temp_eainfo = template_root.find("eainfo")
    temp_detailed = temp_eainfo.findall("detailed")
    for elem in temp_detailed:
        temp_eainfo.remove(elem)

    for elem in ea_nodes:
        temp_eainfo.append(copy.deepcopy(elem))

    # history
    if history_param == 1:
        proc_steps = template_lineage.findall("procstep")
        for step in proc_steps:
            template_lineage.remove(step)

    if history_param in [3, 4]:
        base_md_proc = base_md.findall("dataqual/lineage/procstep")
        for child in base_md_proc:
            child_copy = copy.deepcopy(child)
            template_lineage.append(child_copy)

    base_md = template_root

arcpy.AddMessage("Validating")
validate_online(base_md)
