# utility functions for scripts that work with GeMS geodatabase schema

import arcpy
import os
import time
from pathlib import Path
import GeMS_Definition as gdef


editPrefixes = ("xxx", "edit_", "errors_", "ed_")
debug = False
import requests

## CONSTANT LISTS, DICTIONARIES, AND STRINGS
DTYPE_ORDER = [
    "feature dataset",
    "feature class",
    "table",
    "topology",
    "raster dataset",
]

GEMS_FULL_REF = """GeMS (Geologic Map Schema)--a standard format for the digital publication of geologic maps", available at http://ngmdb.usgs.gov/Info/standards/GeMS/"""

GEMS = "GeMS"

EA_OVERVIEW = """
In a GeMS-compliant database: all feature classes ending in ContactsAndFaults share a topologic relationship with an identically-prefixed MapUnitPolys feature class, all values in fields ending in Type, Method, and Confidence are defined in the Glossary table, all values in fields ending in MapUnit are defined in the DescriptionOfMapUnits table, all values in fields ending in SourceID are defined in the DataSources table, and all values in GeoMaterial fields are defined within the GeoMaterialDict table; a GeMS-controlled vocabulary. Other feature classes and non-spatial tables are required on an as-needed basis and others are optional. Extensions to the schema are acceptable. For more information see GeMS (Geologic Map Schema)--a standard format for the digital publication of geologic maps", available at http://ngmdb.usgs.gov/Info/standards/GeMS/.
"""


# I. General utilities
def eval_bool(boo):
    # converts boolean-like strings to Type boolean
    if boo in [True, "True", "true", "Yes", "yes", "Y", "y", 1]:
        return True
    else:
        return False


def empty(x):
    if x == None:
        return True
    try:
        if str(x).strip() == "":
            return True
        else:
            return False
    except:  # Fail because we tried to strip() on a non-string value
        return False


def is_bad_null(x):
    try:
        if str(x).lower() == "<null>" or str(x) == "" or str(x).strip() == "":
            return True
    except:
        return False
    else:
        return False


def get_duplicates(table_path, field):
    vals = [r[0] for r in arcpy.da.SearchCursor(table_path, field) if not r[0] is None]
    dups = list(set([n for n in vals if vals.count(n) > 1]))
    dups.sort()

    return dups


def pluralize(i, s):
    """Add 's', 'es', 'ies' as appropriate to a plural noun"""
    if int(i) > 1:
        if s.endswith("ss"):
            return f"{s}es"

        if s.endswith("y"):
            return f"{s[:-1]}ies"

        return f"{s}s"
    else:
        return s


def contents(db_dict):
    """Create a string that summarizes the contents of the database.
    Lists the numbers of different data types of objects but no names"""

    # Remove the entry for the database itself
    db_dict = {k: v for k, v in db_dict.items() if not v["dataType"] == "Workspace"}
    d_types = [
        camel_to_space(v["datasetType"]).lower()
        for v in db_dict.values()
        if "datasetType" in v
    ]
    type_d = {d_type: d_types.count(d_type) for d_type in set(d_types)}
    obj_list = []
    for n in DTYPE_ORDER:
        if n in type_d:
            t = f"{type_d[n]} {pluralize(type_d[n], n)}"
            obj_list.append(t)
    for n in type_d:
        if not n in DTYPE_ORDER:
            t = f"{type_d[n]} {pluralize(type_d[n], n)}"
            obj_list.append(t)

    if len(obj_list) == 1:
        return obj_list[0]
    elif len(obj_list) == 2:
        return f"{obj_list[0]} and {obj_list[1]}"
    else:
        return f"{', '.join(obj_list[:-1])}, and {obj_list[-1]}"


def verbose_contents(db_dict, db_name):
    """Create a string that enumerates the objects in the database
    Lists feature datasets, their children, and then all objects
    outside of feature datasets. When table is included, lists everything
    BUT the table - for use in metadata file describing that table so it is
    not listed redundantly"""

    # Remove the entry for the database itself
    db_dict = {k: v for k, v in db_dict.items() if not v["dataType"] == "Workspace"}

    # filter on Feature Datasets
    fds = {k: v for k, v in db_dict.items() if v["dataType"] == "FeatureDataset"}
    verbose = []
    if fds:
        # list the feature datasets
        fds = {k: fds[k] for k in sorted(fds.keys())}
        if len(fds) == 1:
            verbose = f"{db_name} contains one feature dataset: {list(fds.keys())[0]}."
        elif len(fds) == 2:
            verbose = f"{db_name} contains two feature datasets:  {list(fds.keys())[0]}  {list(fds.keys())[1]}."
        else:
            verbose = f"{db_name} contains {convertToWords(len(fds)).lower()} feature datasets: {', '.join(list(fds.keys())[:-1])}, and {list(fds.keys())[-1]}."
        verbose = [verbose]

        # list the contents of the feature datasets
        all_fds = []
        for k, v in fds.items():
            if v["children"]:
                this_fd = f"Feature dataset {k} contains"
                fd_items = []
                for child in sorted(v["children"], key=lambda x: x["baseName"]):
                    type_str = f"{child['concat_type'].lower()} {child['baseName']}"
                    fd_items.append(type_str)
                if len(fd_items) == 1:
                    this_fd = f"{this_fd} one object: {fd_items[0]}."
                elif len(fd_items) == 2:
                    this_fd = f"{this_fd} two objects: {fd_items[0]} and {fd_items[1]}."
                else:
                    this_fd = f"{this_fd} {convertToWords(len(fd_items)).lower()} objects: {', '.join(fd_items[:-1])}, and {fd_items[-1]}."
                all_fds.append(this_fd)

        verbose.extend(all_fds)

    # look for stand-alone objects. These are objects that have no "feature_dataset" value
    # and are not also feature datasets
    alones = {
        k: v
        for k, v in db_dict.items()
        if not v["feature_dataset"] and not v["dataType"] == "FeatureDataset"
    }

    if alones:
        alones = {k: alones[k] for k in sorted(alones.keys())}
        if fds:
            begin_str = f"The database also contains"
        else:
            begin_str = f"{db_name} contains"

        db_items = []
        for k in sorted(alones.keys()):
            type_str = f"{alones[k]['concat_type'].lower()} {k}"
            db_items.append(type_str)

        if len(db_items) == 1:
            db_contents = f"{begin_str} one stand-alone object: {db_items[0]}."
        elif len(db_items) == 2:
            db_contents = f"{begin_str } two stand-alone objects: {db_items[0]} and {db_items[1]}."
        else:
            db_contents = f"{begin_str} {convertToWords(len(db_items)).lower()} stand-alone objects: {', '.join(db_items[:-1])}, and {db_items[-1]}."

    verbose.append(db_contents)

    return " ".join(verbose)


# tests for null string values and <Null> numeric values
# Does not test for numeric nulls -9, -9999, etc.
def stringIsGeMSNull(val):
    if val == None:
        return True
    elif isinstance(val, (str)) and val in ("#", "#null"):
        return True
    else:
        return False


def addMsgAndPrint(msg, severity=0):
    # prints msg to screen and adds msg to the geoprocessor (in case this is run as a tool)
    print(msg)

    # noinspection PyBroadException
    try:
        # Add appropriate geoprocessing message
        if severity == 0:
            arcpy.AddMessage(msg)
        elif severity == 1:
            arcpy.AddWarning(msg)
        elif severity == 2:
            arcpy.AddError(msg)
    except Exception:
        pass


def forceExit():
    addMsgAndPrint("Forcing exit by raising ExecuteError")
    raise arcpy.ExecuteError


def numberOfRows(aTable):
    return int(str(arcpy.GetCount_management(aTable)))


def testAndDelete(fc):
    if arcpy.Exists(fc):
        arcpy.Delete_management(fc)


def fieldNameList(aTable):
    """Send this a catalog path to avoid namespace confusion"""
    return [f.name for f in arcpy.ListFields(aTable)]


def writeLogfile(gdb, msg):
    timeUser = "[" + time.asctime() + "][" + os.environ["USERNAME"] + "] "
    logfileName = Path(gdb) / "00log.txt"
    try:
        log_path = Path(gdb) / logfileName
        logfile = open(log_path, "a")
        logfile.write(timeUser + msg + "\n")
        logfile.close()
    except:
        addMsgAndPrint("Failed to write to " + logfileName)
        addMsgAndPrint("  maybe file is already open?")


def getSaveName(fc):
    # fc is entire pathname
    # builds new, unused name in form oldNameNNN
    oldWS = arcpy.env.workspace
    arcpy.env.workspace = Path(fc).parent
    shortFc = Path(fc).stem
    pfcs = arcpy.ListFeatureClasses(shortFc + "*")
    if debug:
        addMsgAndPrint(str(pfcs))
    maxN = 0
    for pfc in pfcs:
        try:
            n = int(pfc.replace(shortFc, ""))
            if n > maxN:
                maxN = n
        except:
            pass
    saveName = fc + str(maxN + 1).zfill(3)
    arcpy.env.workspace = oldWS
    if debug:
        addMsgAndPrint("fc = " + fc)
        addMsgAndPrint("saveName = " + saveName)
    return saveName


# dictionary of translations from field types (as described) to field types as
#  needed for AddField
typeTransDict = {
    "String": "TEXT",
    "Single": "FLOAT",
    "Double": "DOUBLE",
    "NoNulls": "NON_NULLABLE",
    "NullsOK": "NULLABLE",
    "Date": "DATE",
}


# II. Functions that presume extensions to naming scheme
## getCaf needs to be recoded to use a prefix value
def getCaf(inFds, prefix=""):
    arcpy.env.workspace = inFds
    fcs = arcpy.ListFeatureClasses()
    cafs = []
    for fc in fcs:
        if fc.find("ContactsAndFaults") > -1 or (
            inFds.find("CorrelationOfMapUnits") > -1 and fc.find("Lines") > -1
        ):
            cafs.append(fc)
    for fc in cafs:
        for pfx in editPrefixes:
            if fc.find(pfx) > -1:  # no prefix
                cafs.remove(fc)
    cafs2 = []
    for fc in cafs:
        if fc[-17:] == "ContactsAndFaults" or (
            inFds.find("CorrelationOfMapUnits") > -1 and fc[-5:] == "Lines"
        ):
            cafs2.append(fc)
    # addMsgAndPrint(str(cafs))
    if len(cafs2) != 1:
        addMsgAndPrint(
            "  Cannot resolve ContactsAndFaults feature class in feature dataset"
        )
        addMsgAndPrint("    " + inFds)
        addMsgAndPrint("    " + str(cafs2))
        raise arcpy.ExecuteError
    return Path(inFds) / cafs2[0]


def getMup(fds):
    caf = getCaf(fds)
    return caf.replace("ContactsAndFaults", "MapUnitPolys")


def getNameToken(fds):
    if Path(fds).stem == "CorrelationOfMapUnits":
        return "CMU"
    else:
        caf = Path(getCaf(fds))
        return caf.replace("ContactsAndFaults", "")


# III. Functions that presume Type (vocabulary) values
def isFault(lType):
    if lType.upper().find("FAULT") > -1:
        return True
    else:
        return False


def isContact(lType):
    uType = lType.upper()
    if uType.find("CONTACT") > -1:
        val = True
    elif uType.find("FAULT") > -1:
        val = False
    elif uType.find("SHORE") > -1 or uType.find("WATER") > -1:
        val = True
    elif uType.find("SCRATCH") > -1:
        val = True
    elif uType.find("MAP") > -1 or uType.find("NEATLINE") > -1:  # is map boundary?
        val = False
    elif (
        uType.find("GLACIER") > -1 or uType.find("SNOW") > -1 or uType.find("ICE") > -1
    ):
        val = True
    else:
        addMsgAndPrint("function isContact, lType not recognized, lType = " + lType)
        val = False
    if debug:
        addMsgAndPrint(lType + "  " + uType + "  " + str(val))
    return val


# evaluates values of ExistenceConfidence and IdentifyConfidence
#   to see if a feature should be queried
def isQuestionable(confidenceValue):
    if confidenceValue != None:
        if (
            confidenceValue.lower() != "certain"
            and confidenceValue.lower() != "unspecified"
        ):
            return True
        else:
            return False
    else:
        return False


# returns True if orientationType is a planar (not linear) feature
def isPlanar(orientationType):
    planarTypes = ["joint", "bedding", "cleavage", "foliation", "parting"]
    isPlanarType = False
    for pT in planarTypes:
        if pT in orientationType.lower():
            isPlanarType = True
    return isPlanarType


def editSessionActive(gdb):
    if Path(gdb).glob("*.ed.lock"):
        edit_session = True
    else:
        edit_session = False

    return edit_session


def checkVersion(vString, rawurl, toolbox):
    # compares versionString of tool script to the current script at the repo
    try:
        page = requests.get(rawurl)
        raw = page.text
        if vString in raw:
            pass
            arcpy.AddMessage(f"This version of the tool is up to date: {vString}")
        else:
            repourl = "https://github.com/DOI-USGS/{}/releases".format(toolbox)
            arcpy.AddWarning(
                "You are using an obsolete version of this tool!\n"
                + "Please download the latest version from {}".format(repourl)
            )
    except:
        arcpy.AddWarning(
            "Could not connect to Github to determine if this version of the tool is the most recent.\n"
        )


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

    # and sanitize names that come from geopackages that start with "main."
    # trying to modify the children dictionary in-place wasn't producing expected results
    # we'll build a new dictionary with modified names
    if gdb_path.endswith(".gpkg"):
        dict_1 = {}
        for child in children:
            if "." in child:
                new_name = child.split(".")[1]
                dict_1[new_name] = children[child]
    else:
        dict_1 = children

    # remove anything we don't want that came through
    dict_2 = {k: v for k, v in dict_1.items() if not v["dataType"] == "RasterBand"}

    # add an entry for the database itself
    db_name = Path(gdb_path).stem
    # leave out "children" because they are serialized in the dictionary
    dict_2[db_name] = {k: v for k, v in desc.items() if not k == "children"}

    # adding an entry for 'concatenated type' that will concatenate
    # featureType, shapeType, and dataType. eg
    # Simple Polygon FeatureClass
    # Simple Polyline FeatureClass
    # Annotation Polygon FeatureClass
    # this will go into Entity_Type_Definition
    for k, v in dict_2.items():
        if "dataType" in v:
            d_type = camel_to_space(v["dataType"])
            match v["dataType"]:
                case "Table":
                    v["concat_type"] = "Non-spatial Table"
                case "FeatureClass":
                    v["concat_type"] = f"{v['featureType']} {v['shapeType']} {d_type}"
                case _:
                    v["concat_type"] = d_type

        # for objects that are based on a GeMS object but have a
        # prefix or suffix, record the name of the required GeMS object
        # on which they are based
        # initialize gems_equivalent key to nothing
        v["gems_equivalent"] = ""
        tableDict_keys = list(gdef.tableDict.keys())
        tableDict_keys.append("GeoMaterialDict")
        if not any(el in v["concat_type"] for el in ("Topology", "Annotation")):
            for a in tableDict_keys:
                # if the CamelCase or snake_case version of a gems object
                # is found in the table name
                if (
                    any(n in k.lower() for n in (a.lower(), camel_to_snake(a)))
                    and gdef.shape_dict[a] in v["concat_type"].lower()
                    # and not "cmu" in a.lower()
                ):
                    # set the gems_equivalent key to the GeMS CamelCase name
                    v["gems_equivalent"] = a

            # caveats
            if k.lower().endswith("points") and v["gems_equivalent"] == "":
                v["gems_equivalent"] = "GenericPoints"

            if k.lower().endswith("samples") and v["gems_equivalent"] == "":
                v["gems_equivalent"] = "GenericSamples"

            if (
                any(k.lower().endswith(n) for n in ("geologicmap", "geologic_map"))
            ) and v["concat_type"] == "Feature Dataset":
                v["gems_equivalent"] = "GeologicMap"

            if any(k.lower().endswith(l) for l in ("label", "labels")):
                v["gems_equivalent"] = ""

            if "mapunitoverlaypolys" in k.lower():
                v["gems_equivalent"] = "MapUnitOverlayPolys"

            if v["dataType"] == "Workspace":
                v["gems_equivalent"] = "GeMS Database"

    return dict_2


def camel_to_snake(s):
    if "CMU" in s:
        s = s[3:]
        return f"cmu_{''.join(['_'+c.lower() if c.isupper() else c for c in s]).lstrip('_')}"
    else:
        return "".join(["_" + c.lower() if c.isupper() else c for c in s]).lstrip("_")


def convert_bool(boo):
    # converts boolean-like strings to Type boolean
    if boo in [True, "True", "true", "Yes", "yes", "Y", "y", 1]:
        return True
    else:
        return False


def camel_to_space(s):
    return "".join([" " + c.upper() if c.isupper() else c for c in s]).lstrip(" ")


def fix_null(x):
    # x = x.encode('ascii','xmlcharrefreplace')
    if x.lower() == "<null>":
        return "&lt;Null&gt;"
    else:
        return x


def not_empty(x):
    # will converting x to string ever return an unexpected value?
    if x != None and str(x).strip() != "":
        return True
    else:
        return False

        return None


def convertToWords(n):
    """Convert integer numbers to numerals"""
    if n == 0:
        return "Zero"

    # Words for numbers 0 to 19
    units = [
        "",
        "One",
        "Two",
        "Three",
        "Four",
        "Five",
        "Six",
        "Seven",
        "Eight",
        "Nine",
        "Ten",
        "Eleven",
        "Twelve",
        "Thirteen",
        "Fourteen",
        "Fifteen",
        "Sixteen",
        "Seventeen",
        "Eighteen",
        "Nineteen",
    ]

    # Words for numbers multiple of 10
    tens = [
        "",
        "",
        "Twenty",
        "Thirty",
        "Forty",
        "Fifty",
        "Sixty",
        "Seventy",
        "Eighty",
        "Ninety",
    ]

    multiplier = ["", "Thousand", "Million", "Billion"]

    res = ""
    group = 0

    # Process number in group of 1000s
    while n > 0:
        if n % 1000 != 0:

            value = n % 1000
            temp = ""

            # Handle 3 digit number
            if value >= 100:
                temp = units[value // 100] + " Hundred "
                value %= 100

            # Handle 2 digit number
            if value >= 20:
                temp += tens[value // 10] + " "
                value %= 10

            # Handle unit number
            if value > 0:
                temp += units[value] + " "

            # Add the multiplier according to the group
            temp += multiplier[group] + " "

            # Add the result of this group to overall result
            res = temp + res
        n //= 1000
        group += 1

    # Remove trailing space
    return res.strip()


def is_db(db_dict, name):
    """Is the object in the dictionary a database or not"""
    if db_dict[name]["dataType"] == "Workspace":
        return True
    else:
        return False
