"""Metadata utilities

Methods shared by various metadata classes
"""

import arcpy
from lxml import etree
import tempfile
import csv
from pathlib import Path
from osgeo import ogr
import subprocess
import re
import GeMS_utilityFunctions as guf
import GeMS_Definition as gdef
import spatial_utils as su

toolbox_folder = Path(__file__).parent.parent
scripts_folder = toolbox_folder / "Scripts"
metadata_folder = toolbox_folder / "Resources" / "metadata"

## CONSTANT LISTS, DICTIONARIES, AND STRINGS
KW_DICT = {
    "place": "idinfo/keywords/place",
    "stratum": "idinfo/keywords/stratum",
    "temporal": "idinfo/keywords/temporal",
    "theme": "idinfo/keywords/theme",
}

# not used right now
XMANY_NODES = ["idinfo/ptcontac", "idinfo/crossref"]

# the following xpaths are to complex, nested elements that will be copied
# in whole from the template to the final xml if temp_directive = "replace"
# but nothing will happen if it is "append"
SINGLE_NODES = ["idinfo/status", "distinfo", "metainfo"]

TEXT_XPATHS = [
    "idinfo/citation/citeinfo/title",
    "idinfo/descript/abstract",
    "idinfo/descript/purpose",
    "idinfo/descript/supplinf",
    "idinfo/accconst",
    "idinfo/useconst",
    "dataqual/attracc/attraccr",
    "dataqual/attracc/qattracc/attraccv",
    "dataqual/attracc/qattracc/attracce",
    "dataqual/logic",
    "dataqual/complete",
    "dataqual/posacc/horizpa/horizpar",
    "dataqual/posacc/horizpa/qhorizpa/horizpav",
    "dataqual/posacc/horizpa/qhorizpa/horizpae",
    "dataqual/posacc/vertacc/vertaccr",
    "dataqual/posacc/vertacc/qvertpa/vertaccv",
    "dataqual/posacc/vertacc/qvertpa/vertacce",
    "eainfo/overview/eaover",
    "eainfo/overview/eadetcit",
]


ESRI_ATTRIBS = {
    "objectid": "Internal feature number",
    "shape": "Internal geometry object",
    "shape_length": "Internal feature length, double",
    "shape_area": "Internal feature area, double",
    "ruleid": "Integer field that stores a reference to the representation rule for each feature.",
    "override": "BLOB field that stores feature-specific overrides to the cartographic representation rules.",
}

CHILD_NODES = [
    (0, "idinfo"),
    (1, "dataqual"),
    (2, "eainfo"),
    (3, "distinfo"),
    (4, "metainfo"),
]

arcprint = guf.addMsgAndPrint


## METHODS
def find_type(db_dict, table):
    if "datasetType" in db_dict[table]:
        d_type = guf.camel_to_space(db_dict[table]["datasetType"])
        return d_type.lower()
    else:
        return ""


def md_dict_from_folder(folder):
    xml_dict = {}
    for child in Path(folder).rglob("*.xml"):
        filename = child.stem
        for s in "-metadata", "_metadata", "-template", "_template", "GeMS_", "GeMS-":
            filename = filename.replace(s, "")
        xml_dict[filename] = child

    return xml_dict


def object_template_dict(db_dict, xml_dict, filter_list=None):
    """returns a dictionary of database object: path to xml metadata file to import
    optional objects list to control the objects in the database to be processed"""

    obj_xml_dict = {}

    # redefine filter_list to all dictionary keys if not provided
    if not filter_list:
        filter_list = list(db_dict.keys())

    arcprint("Matching XML files to database objects")
    if xml_dict:
        # if there is only one XML, all objects use the same template
        if len(xml_dict) == 1:
            # redefine obj_temp_dict
            only_value = next(iter(xml_dict.values()))
            obj_xml_dict = {obj_name: only_value for obj_name in filter_list}
            for key in obj_xml_dict:
                arcprint(f"{Path(only_value).name:<30}:{key:>30}")

        else:
            # go through all objects
            for obj_name in filter_list:
                match_found = False

                # look for templates with exact name match
                exact = [k for k in xml_dict.keys() if k == obj_name]
                if exact:
                    obj_xml_dict[obj_name] = xml_dict[exact[0]]
                    xf = f"{exact[0]}.xml"
                    match_found = True
                    arcprint(f"{xf:<30}:{obj_name:>30}")

                # annotation
                if not match_found:
                    if obj_name.endswith("Anno"):
                        if "Anno" in xml_dict:
                            obj_xml_dict[obj_name] = xml_dict["Anno"]
                            match_found = True
                            arcprint(f"{'Anno.xml':<30}:{obj_name:>30}")

                # look for CS[[X]]CrossSectionFeatures
                gems_names = list(gdef.startDict.keys())
                if not match_found:
                    for n in gems_names:
                        if obj_name.startswith("CS") and n in obj_name:
                            test_xml = f"CS[[X]]{n}.xml"
                            if test_xml in xml_dict:
                                obj_xml_dict[obj_name] = test_xml
                                match_found = True
                                arcprint(f"{test_xml:<30}:{obj_name:>30}")

                # look for templates with partial matches
                if not match_found:
                    matches = [k for k in xml_dict.keys() if k in obj_name]
                    if len(matches) == 1:
                        obj_xml_dict[obj_name] = xml_dict[matches[0]]
                        xf = f"{matches[0]}.xml"
                        match_found = True
                        arcprint(f"{xf:30}:{obj_name:>30}")
                    elif len(matches) > 1:
                        if len(matches) == 2:
                            comma = ""
                        else:
                            comma = ", "
                        multiples = (
                            f"{', '.join(matches[:-1])}{comma} and {matches[-1]}"
                        )
                        arcprint(f"Multiple metadata files found for {obj_name}:", 1)
                        arcprint(multiples, 1)
                        arcprint("No metadata will be imported")

                # GenericPoints or Samples
                if not match_found:
                    for n in ("Points", "Samples"):
                        if obj_name.endswith(n) and f"Generic{n}" in xml_dict.keys():
                            obj_xml_dict[obj_name] = xml_dict[f"Generic{n}"]
                            xf = f"Generic{n}"
                            arcprint(f"{xf:<30}:{obj_name:>30}")
                            match_found = True

                # try to match by gems_equivalent
                if not match_found:
                    gems_eq = db_dict[obj_name]["gems_equivalent"]
                    if gems_eq in xml_dict:
                        obj_xml_dict[obj_name] = xml_dict[gems_eq]
                        xf = f"{gems_eq}.xml"
                        arcprint(f"{xf:<30}:{obj_name:>30}")
                        match_found = True

                # AnyTable
                if not match_found:
                    if not db_dict[obj_name]["dataType"] in (
                        "FeatureDataset",
                        "Workspace",
                    ):
                        if "AnyTable" in xml_dict:
                            obj_xml_dict[obj_name] = xml_dict["AnyTable"]
                            arcprint(f"{'ANY_TABLE.xml':<30}:{obj_name:>30}")
                            match_found = True

                # look for geodatabase match
                if not match_found:
                    db_name = [
                        v["baseName"]
                        for v in db_dict.values()
                        if v["dataType"] == "Workspace"
                    ][0]

                    # check for matches only if the object is the geodatabase
                    if obj_name == db_name:
                        # look for an xml named after the database
                        if db_name in xml_dict.keys():
                            obj_xml_dict[db_name] = xml_dict[db_name]
                            arcprint(f"{db_name:<30}:{obj_name:>30}")
                            match_found = True

                        # look for an xml named "database"
                        elif any(
                            n in xml_dict for n in ("Database", "database", "DATABASE")
                        ):
                            for n in ("Database", "database", "DATABASE"):
                                if xml_dict.get(n) and not match_found:
                                    obj_xml_dict[db_name] = xml_dict[n]
                                    xf = f"{n}.xml"
                                    match_found = True
                                    arcprint(f"{xf:<30}:{obj_name:>30}")

                # if multiple templates are found
                if not match_found:
                    arcpy.AddWarning(f"No Metadata file found for {obj_name}")

    return obj_xml_dict


def table_defs_from_csv(csv_path):
    """Build dictionary of custom definitions for tables from a csv definitions file
    {table name: [definition, definition source]}
    """

    # read the csv of definitions
    table_defs = {}
    with open(csv_path, mode="r") as file:
        defs_csv = list(csv.reader(file, skipinitialspace=True))
        table_defs = {
            row[0]: [row[2], row[3]]
            for row in defs_csv
            if len(row) > 1
            and not row[0].lower() in ("table", "any table")
            and not row[1]
        }

    return table_defs


def field_defs_from_csv(csv_path):
    """Build dictionary of custom definitions for fields from a csv definitions file
    {table name:[[field1, definition, definition source, domain type, domain values],
                [fieldn, definition, definition source, domain type, domain values]]
          }
    """

    # read the csv of definitions. Each line has:
    # table, field, definition, definition_source, domain_type, domain_values
    # if table is blank in CSV, that field is defined the same everywhere it is found
    field_defs = {}
    with open(csv_path, mode="r") as file:
        defs_csv = list(csv.reader(file, skipinitialspace=True))

        # TABLE, FIELD, DEFINITION, DEFINITION SOURCE, DOMAIN TYPE, DOMAIN VALUE
        fields = [
            row
            for row in defs_csv
            if row
            and not row[0].startswith("#")
            and not row[0].lower() == "table"
            and not row[1] == ""
        ]

        for field in fields:
            if field[0].lower() == "any table":
                table = "ANY TABLE"
            else:
                table = field[0]

            if table in field_defs:
                field_defs[table].append(field[1:])
            else:
                field_defs[table] = [field[1:]]

    return field_defs


def term_dict(db_dict, table, fields, sources_dict=None):
    """Build the following dictionaries:

    sources - {Source: DataSources_ID as str}
    geomaterial = {GeoMaterial: [Definition, "GeMS"]} as list
    map units - {Unit: [(1st choice) Name (2nd choice) FullName, DescriptionSourceID] as list}
    glossary - {Term: [Definition, DefinitionSourceID] as list}

    sources_dict needs to be built first
    """
    # always supply field to be the dictionary key as fields[0]
    # and the 'ID' field as fields[-1]
    if table in db_dict:
        table_path = db_dict[table]["catalogPath"]
        data_dict = {}
        with arcpy.da.SearchCursor(table_path, fields) as cursor:
            for row in cursor:
                if table == "DataSources":
                    if not row[1] is None:
                        data_dict[row[0]] = row[1]

                if table == "GeoMaterialDict":
                    data_dict[row[0]] = [row[1], guf.GEMS]

                if table == "DescriptionOfMapUnits":
                    # if there is a MapUnit value
                    if row[0]:
                        if not row[2] is None:
                            # if there is a FullName, that is the value of the mapunit key
                            data_dict[row[0]] = [row[2]]
                        else:
                            if not row[1] is None:
                                # otherwise use the Name
                                data_dict[row[0]] = [row[1]]
                        # append the SourceID
                        data_dict[row[0]].append(catch_m2m(sources_dict, row[-1]))
                    else:
                        data_dict[row[0]] = list(row[1:-1])
                        data_dict[row[0]].append(catch_m2m(sources_dict, row[-1]))

                if table == "Glossary":
                    data_dict[row[0]] = [row[1], row[2]]

        return data_dict
    else:
        return None


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


def clear_children(element, child_tag):
    for child in element.findall(child_tag):
        element.remove(child)


def find_prefix_suffix(table_name):
    gems_names = list(gdef.shape_dict.keys())
    pattern = r"CS(.*?)(?=" + "|".join(gems_names) + ")"
    match = re.search(pattern, table_name)
    if match:
        return match.group(1)
    return None


def tokens(node_text, db_dict, ver_string, obj=None):
    """Replace [[TOKENS]] in the string"""

    # determine if this is SINGLE or DATABASE text
    # return a flag so that when this function is being called with the text of an
    # etree element, we can notify the calling function to delete the element.
    # The Database.xml template in the toolbox contains two <title> and two <supplinfo> elements
    # because the template can be used by either single tables or databases.
    if obj:
        if db_dict[obj]["dataType"] == "Workspace":
            if node_text.startswith("[[SINGLE]]"):
                # return early
                return "REMOVE NODE"
        else:
            if node_text.startswith("[[DATABASE]]"):
                # return early
                return "REMOVE NODE"

        # finding [[X]] in CS[[X]]FeatureClasses
        # csx will usually be None
        csx = find_prefix_suffix(obj)

    # name of the database
    if db_dict[obj]["dataType"] == "Workspace":
        db_name = obj
    else:
        ws = db_dict[obj]["workspace"].connectionProperties.database
        db_name = Path(ws).stem

    # if a table was sent, look for a feature dataset
    table_definition = ""
    try:
        fd = db_dict[obj]["feature_dataset"]
        data_type = find_type(db_dict, obj)
        table = obj
        # look for a GeMS definition of this table
        if table in gdef.entityDict:
            table_definition = gdef.entityDict[table]
        elif db_dict[table]["gems_equivalent"] in gdef.entityDict:
            table_definition = gdef.entityDict[db_dict[table]["gems_equivalent"]]

    except:
        table = ""
        fd = ""
        data_type = ""
        table_definition = ""

    # feature dataset string
    if fd:
        fd_string = f"This {data_type} is found within the {fd} feature dataset"
    else:
        fd_string = ""

    t = {
        "[[CONTENTS]]": guf.contents(db_dict),
        "[[VERBOSE CONTENTS]]": guf.verbose_contents(db_dict, db_name),
        "[[EA OVERVIEW]]": guf.EA_OVERVIEW,
        "[[OBJECT]]": table,
        "[[GEMS DEF]]": table_definition,
        "[[DTYPE]]": data_type,
        "[[DB NAME]]": db_name,
        "[[GEMS]]": guf.GEMS_FULL_REF,
        "[[SCRIPT]]": ver_string,
        "[[FEATURE DATASET]]": fd_string,
        "[[DATABASE]]": "",
        "[[SINGLE]]": "",
        "[[X]]": csx,
    }

    for k, v in t.items():
        if v is not None:
            node_text = node_text.replace(k, v)

    return node_text.strip()


def keyword_dict(dom):
    """Make a dictionary of {(theme/place/stratum/temporal, keyword thesaurus): [keyword nodes]]}
    eg:
    {
    ('theme', 'ISO 19115 Topic Category'): ['biota', 'boundaries', 'elevation'],
    ('place', 'GNIS'): ['Oregon', 'Cascade Mountains', 'Portland'],
    ('stratum', 'None'): ['Waxahatchee Formation', 'Nunchucks Member'],
    ('temporal', 'None'): ['Holocenic', 'Gastrocene']
    }

    The dictionary keys need to be tuples to accommodate the use of non-unique thesaurus names, such as None.
    """
    kw_dict = {}
    keywords_nodes = dom.xpath("idinfo/keywords")
    if len(keywords_nodes):
        keywords = keywords_nodes[0]
        for kw_type in keywords:
            key_nodes = []
            for el in kw_type:
                if el.tag.endswith("kt"):
                    thesaurus = el.text
                else:
                    key_nodes.append(el)

            kw_dict[(kw_type.tag, thesaurus)] = key_nodes
    return kw_dict


def extend_branch(node, xpath):
    """Test for full xpath and if only partially exists,
    builds it out the rest of the way"""
    # search for nodes on the xpath, building them from the list, delimited by /
    path_nodes = xpath.split("/")
    for nibble in path_nodes:
        if nibble:
            search_node = node.find(nibble)
            if search_node is not None:
                node = search_node
            else:
                node = etree.SubElement(node, nibble)

    return node


def sort_attr(detailed):
    """Alphabetically sorted (ignoring case) attr nodes in a detailed node
    following the enttyp node"""
    # child_nodes = []
    new_detailed = etree.Element("detailed")
    if enttyp := detailed.xpath("enttyp"):
        new_detailed.append(enttyp[0])

    attrs = detailed.xpath("attr")
    attrs = sorted(attrs, key=lambda x: x.xpath("attrlabl")[0].text.lower())
    # child_nodes.append(attrs)

    for attr in attrs:
        new_detailed.append(attr)
    return new_detailed


def export_embedded(obj_path, history_choice, source_choice):
    """Export the embedded metadata from a geodatabase object"""

    # export the embedded metadata to a temporary file
    # parse it and return the xml dom
    # synchronizing ensures that there will be eainfo/detailed nodes for every field
    temp_dir = tempfile.TemporaryDirectory()
    temp_xml = Path(temp_dir.name) / "temp.xml"
    src_md = arcpy.metadata.Metadata(obj_path)
    src_md.synchronize("SELECTIVE")
    src_md.exportMetadata(str(temp_xml), "FGDC_CSDGM")

    # parse the output file and get the root element
    root = etree.parse(str(temp_xml)).getroot()

    # check for removing embedded sources and history (process steps)
    # but don't proceed if there is no lineage node
    if root.xpath("dataqual/lineage"):
        lineage = root.xpath("dataqual/lineage")[0]
        if source_choice in (1, 3, 5, 8):
            for srcinfo in lineage.findall("srcinfo"):
                lineage.remove(srcinfo)

        if history_choice in (1, 3):
            for procstep in lineage.findall("procstep"):
                lineage.remove(procstep)

    return root


def md_from_scratch(db_dict, obj=None):
    """Write out the top-level children and the eainfo/detailed node from the actual
    list of fields in the table.

    obj can be None in case of building metadata for a database"""

    # make all the metadata first-level children
    metadata = etree.Element("metadata")
    for child in CHILD_NODES:
        etree.SubElement(metadata, child[1])

    if obj:
        if "fields" in db_dict[obj]:
            # make a detailed node
            detailed = etree.SubElement(metadata.find("eainfo"), "detailed")

            # make an enttyp node with a enttypl (label) node
            enttyp = etree.SubElement(detailed, "enttyp")
            enttypl = etree.SubElement(enttyp, "enttypl")
            enttypl.text = obj

            # make one attr/attrlabl per field

            for field in db_dict[obj]["fields"]:
                attr = etree.SubElement(detailed, "attr")
                attrlabl = etree.SubElement(attr, "attrlabl")
                attrlabl.text = field.name

    return etree.ElementTree(metadata).getroot()


def max_bounding(db_path):
    north = []
    south = []
    west = []
    east = []
    for layer in ogr.Open(db_path):
        if layer.GetGeomType() != 100:
            # if "MapUnitPolys" in layer.GetName() or "ContactsAndFaults" in layer.GetName():
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


def get_spdoinfo(db_dict, layer, dom):
    """Create a spatial data information element for the object. If raster, use
    method here, if vector, use the MW spatial utilities methods"""
    # at this time, no RasterDatsets are sent to this function because the
    # spdoinfo element cannot accommodate cataloging both vector features and rasters but
    # I will leave the first part of the if statement uncommented
    # raster properties will get logged as entity attributes
    if db_dict[layer]["datasetType"] == "RasterDataset":
        spdoinfo = etree.Element("spdoinfo")
        rastinfo = etree.SubElement(spdoinfo, "rastinfo")
        rasttype = etree.SubElement(rastinfo, "rasttype")
        rasttype.text = "Grid Cell"
        rowcount = etree.SubElement(rastinfo, "rowcount")
        rowcount.text = str(db_dict[layer]["height"])
        colcount = etree.SubElement(rastinfo, "colcount")
        colcount.text = str(db_dict[layer]["width"])
    else:
        wksp = db_dict[layer]["workspace"]
        db_path = wksp.connectionProperties.database
        try:
            spdoinfo = su.get_spdoinfo(str(db_path), layer)
        except Exception as e:
            arcpy.AddWarning(
                f"""Could not collect spatial data organization information"""
            )
            arcpy.AddWarning(e)
            spdoinfo = None
    if spdoinfo:
        dom.insert(2, spdoinfo)


def add_spref(db_dict, layer, dom):
    """Create a spref - spatial reference information node for the resource
    based on slightly modified versions of spatial_utils.py and xml_utils.py
    from the USGS Metadata Wizard library"""
    wksp = db_dict[layer]["workspace"]
    db_path = wksp.connectionProperties.database
    spref_node = None
    try:
        spref_node = su.get_spref(db_path, layer, db_dict[layer]["datasetType"])
    except Exception as e:
        arcpy.AddWarning(
            f"""Could not determine the coordinate system of {layer}
            Check in ArcCatalog that it is valid"""
        )
        arcpy.AddWarning(e)
        print(e)

    # remove any existing spref element, empty one created in _md_from_scratch is just a placeholder
    # so that the new one can be inserted at the right index
    etree.strip_elements(dom, "spref")
    if spref_node:
        dom.insert(3, spref_node)
        return True
    else:
        return False


def mp_upgrade(dom):
    """'Upgrade' the metadata with mp.exe. Fixes a number of structural issues.
    https://geology.usgs.gov/tools/metadata/tools/doc/upgrade.html"""

    mp_path = metadata_folder / "mp.exe"
    config_path = metadata_folder / "mp_config"
    tree = etree.ElementTree(dom)

    # save self.dom in a temporary directory
    with tempfile.TemporaryDirectory() as tempdirname:
        dom_xml = Path(tempdirname) / "dom_out.xml"
        with open(dom_xml, "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)

        # send temporary file through mp.exe and collect the output
        err_out = Path(tempdirname) / "errors.txt"
        x_out = Path(tempdirname) / "xml_out.xml"
        mp_args = [
            str(mp_path),
            str(dom_xml),
            "-c",
            str(config_path),
            "-x",
            str(x_out),
        ]
        subprocess.call(mp_args)

        # now that our xml has been upgraded, check the output just written for errors
        # call mp again
        mp_args = [
            str(mp_path),
            str(x_out),
            "-e",
            str(err_out),
        ]
        subprocess.call(mp_args)

        # redefine dom as the mp-upgraded xml
        dom = etree.parse(str(x_out)).getroot()

        # read the errors into a variable
        with open(err_out, "r") as f:
            errors = f.read()

        return dom, errors


def add_datasources(dom, db_dict, table, report_bool):
    """Translate rows from the DataSources table into dataqual/lineage/srcinfo nodes"""

    # first, bail if there is no DataSources table
    if not "DataSources" in db_dict:
        arcpy.AddMessage("Could not find a DataSources table. ")
        return

    # get a list of data sources used for this table
    # first, identify SourceID fields. Could be multiple eg, DataSourceID, AnalysisSourceID, DescriptionSourceID, etc.
    src_fields = []
    if table:
        if "fields" in db_dict[table]:
            src_fields = [
                f.name
                for f in db_dict[table]["fields"]
                if f.name.lower().endswith("sourceid")
            ]

    # if there are SourceID fields, collect all the values from those fields
    sources = []
    if src_fields:
        with arcpy.da.SearchCursor(db_dict[table]["catalogPath"], src_fields) as cursor:
            for row in cursor:
                sources.extend(row)

    # continue if there are SourceID values
    if sources or report_bool:
        sources = set(sources)
        lineage = extend_branch(dom, "dataqual/lineage")
        ds_path = db_dict["DataSources"]["catalogPath"]

        # "URL" is optional field
        if "URL" in [f.name for f in db_dict["DataSources"]["fields"]]:
            fields = ["Source", "DataSources_ID", "URL"]
            url = True
        else:
            fields = ["Source", "DataSources_ID"]
            url = False

        with arcpy.da.SearchCursor(ds_path, fields) as cursor:
            for row in cursor:
                # continue only if this SourceID is found in self.table
                # SourceID fields in foreign tables should be the DataSource_ID value but sometimes
                # people use the Source value. Check for either in sources list
                if row[0] in sources or row[1] in sources or report_bool:
                    # make a srcinfo element
                    srcinfo = etree.SubElement(lineage, "srcinfo")

                    # make a title element and use the value in 'Source' field
                    extend_branch(srcinfo, "srccite/citeinfo/title")
                    title = srcinfo.find("srccite/citeinfo/title")
                    title.text = row[0]

                    # make a source abbreviation element and use the value in 'DataSourceID' field
                    srccitea = etree.SubElement(srcinfo, "srccitea")
                    srccitea.text = row[1]

                    # check for a URL value to go in onlink
                    if url:
                        onlink = extend_branch(srcinfo, "srccite/citeinfo/onlink")
                        onlink.text = row[2]


def sources_wizard(
    dom, sources_choice, db_dict, report_bool, template_tree, table=None
):
    """Decide what to do with sources"""

    # there are four sources choices where all srcinfo elements in embedded are to be removed
    if sources_choice in (1, 3, 5, 8):
        for srcinfo in dom.xpath("dataqual/lineage/srcinfo"):
            srcinfo.getparent().remove(srcinfo)

    # there are four sources choices where any template srcinfo elements are to be removed
    # if self.sources in (1, 2, 4, 8) and not self.template_applied:
    #     if self.template_tree:
    #         for srcinfo in self.template_tree.xpath("dataqual/lineage/srcinfo"):
    #             srcinfo.getparent().remove(srcinfo)

    # there are two choices where we want the existing embedded sources to follow sources from DataSources.
    # The easiest way to add subelements is to append after existing elements
    # so, remove the embedded sources and we will append them after the DataSources have been added.
    if sources_choice in (4, 7):
        dom_sources = dom.xpath("dataqual/lineage/srcinfo")
        for srcinfo in dom.xpath("dataqual/lineage/srcinfo"):
            srcinfo.getparent().remove(srcinfo)

    if sources_choice in (1, 4, 5, 7):
        # choices 1, 4, 5, 7 include DataSources
        add_datasources(dom, db_dict, table, report_bool)

    if sources_choice in (4, 7):
        # find or create the lineage element
        # there could still be a chance one does not exist yet
        if dom.xpath("dataqual/lineage"):
            lineage = dom.xpath("dataqual/lineage")[0]
        else:
            lineage = etree.SubElement(dom.xpath("dataqual")[0], "lineage")

        if dom_sources:
            for srcinfo in dom_sources:
                lineage.append(srcinfo)

    if sources_choice in (3, 5, 6, 7):
        # find or create the lineage element
        # there could still be a chance once does not exist yet
        if dom.xpath("dataqual/lineage"):
            lineage = dom.xpath("dataqual/lineage")[0]
        else:
            lineage = etree.SubElement(dom.xpath("dataqual")[0], "lineage")

        if template_tree:
            template_sources = template_tree.xpath("dataqual/lineage/srcinfo")
            # for srcinfo in self.template_tree.xpath("dataqual/lineage/srcinfo"):
            #     srcinfo.getparent().remove(srcinfo)

            for srcinfo in template_sources:
                lineage.append(srcinfo)


def history_wizard(dom, history_choice, temp_dom=None):
    """Decide what to do with history (lineate/procsteps)"""

    # there are two history choices where all process steps in embedded are to be remove
    if history_choice in (1, 3):
        for procstep in dom.xpath("dataqual/lineage/procstep"):
            procstep.getparent().remove(procstep)

    # choice 2 is embedded history only, so remove any template process steps so that
    # they do not get added in _add_template_metadata
    if history_choice == 2:
        if temp_dom:
            for procstep in temp_dom.xpath("dataqual/lineage/procstep"):
                procstep.getparent().remove(procstep)

    # choice 4 is collate both the template and the embedded metadata process steps
    # Considered sorting a list of both sets of procsteps but that means dealing with
    # missing dates, inconsistent dates, duplicate dates (sort on what next?) - too much!
    # we'll just add the template procsteps in the same order in which they appear in the
    # template at the end of the list of self.dom procsteps
    template_procsteps = []
    if history_choice in (3, 4):
        if temp_dom:  # there better be a template because that's what choice 4 implies!
            # save the process steps in a list
            template_procsteps = temp_dom.xpath("dataqual/lineage/procstep")
            # and delete them from the template so they don't get added in _add_template_metadata
            # for procstep in self.template_tree.xpath("dataqual/lineage/procstep"):
            #     procstep.getparent().remove(procstep)

        # find or create the lineage element
        if dom.xpath("dataqual/lineage"):
            lineage = dom.xpath("dataqual/lineage")[0]
        else:
            lineage = etree.SubElement(dom.xpath("dataqual")[0], "lineage")

        # iterate through template_procsteps, add one at a time with .append
        # appending will always put template procsteps under any existing embedded procsteps
        if len(template_procsteps) > 0:
            for procstep in template_procsteps:
                lineage.append(procstep)


def write_xml(dom, xml_path):
    tree = etree.ElementTree(dom)
    etree.indent(dom, level=0)
    with open(xml_path, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)
