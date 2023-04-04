# Substantially revised version of GeMS validation script, April 2020
# Significant changes include:
#   * Structuring of output into 3 levels of compliance with GeMS schema
#   * Check, via mp.exe, of formal .gdb-level metadata. Note that metadata
#        for constituent tables, datasets, and feature classes remain the users responsibility
#   * Inclusion of basic topology check
#
# Edited 7/15/20 to work in ArcGIS Pro 2.5 with Python 3
# Evan Thoms
# 10/8/20 updates from Ralph's version '7 October 2020'
# 1/27/21 added all of the following updates from the ArcMap version - ET
#
# 22 December 2020: Edited output text to correctly identify XXX_Validation.gdb. Added option to delete unused rows in Glossary and DataSources - RH
# 23 December 2020: Refreshing GeoMaterialDict now also refreshes the domain associated with GeoMaterial field in DescriptionOfMapUnits - RH
# 28 December 2020: Added warning if active edit session on input GDB - RH
# 15 January 2021: Added warning if SRF not in (NAD83, WGS84)
#    Added reminder to document any schema extensions
#    Added feature dataset SRF names to database inventory     - RH
# 2/26/21: added copy.deepcopy to checkFieldDefinitions when building requiredFieldDefs
# 7/6/2: changed functions notEmpty and empty to evaluate str(x) instead of just x so that we could look for value of x.strip() when x is an integer.
#        Will converting x to string ever return an unexpected value? - ET
#      : added try/except block when checking for editor tracking because there's a chance the method didn't exist for pre 2.6 versions of AGPro -  ET
# 7/8/21: user reported error from checkMetadata. First, the Resources folder and mp.exe paths were not getting built properly when starting from
#       : sys.argv[0] when the file GDB was placed inside the toolbox folder. Weird, yes, but the tool should handle it. __file__ and using path.dirname
#       : is a more robust way to get the path of the script file and parent folders.
#       : Second, spaces in paths were not getting handled correctly when calling mp.exe through os.system(command). Switched to subprocess.
# 1/27/22: added clause to parse DataSourceIDs that might take the form of 'DAS1 | DAS2 | DAS3', etc. That is, allows for multiple datasources
#        to be related to a table row. in def ScanTable under 'for i in dataSourceIndices:'
# 4/18/22: fixed problems related to failing to find a field called 'OBJECTID'. Instead, we now find the name where field.type == 'OID'. Object ID fields can
#         take a few names; FID (possibly only shapefiles?), OBJECTID_ID, ATTACHMENTID, etc. Issue 20 at repo.

import arcpy, os, os.path, sys, time, glob
import copy
from arcpy import metadata as md
from GeMS_utilityFunctions import *
from GeMS_Definition import *
import subprocess

versionString = "GeMS_ValidateDatabase_AGP2.py, version of 18 April 2022"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_ValidateDatabase_AGP2.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

py_path = __file__
scripts_path = os.path.dirname(py_path)
toolbox_path = os.path.dirname(scripts_path)
resources_path = os.path.join(toolbox_path, "Resources")

metadataSuffix = "-vFgdcMetadata.txt"
metadataErrorsSuffix = "-vFgdcMetadataErrors.txt"

space6 = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp"
space4 = "&nbsp;&nbsp;&nbsp;&nbsp;"
space2 = "&nbsp;&nbsp;"

#######GLOBAL VARIABLES#######################################################
geologicNamesDisclaimer = ', pending completion of a peer-reviewed Geologic Names report that includes identification of any suggested modifications to <a href="https://ngmdb.usgs.gov/Geolex/">Geolex</a>. '

# fields we don't want listed or described when inventorying dataset:
standardFields = (
    "OBJECTID",
    "SHAPE",
    "Shape",
    "SHAPE_Length",
    "SHAPE_Area",
    "ZOrder",
    "AnnotationClassID",
    "Status",
    "TextString",
    "FontName",
    "FontSize",
    "Bold",
    "Italic",
    "Underline",
    "VerticalAlignment",
    "HorizontalAlignment",
    "XOffset",
    "YOffset",
    "Angle",
    "FontLeading",
    "WordSpacing",
    "CharacterWidth",
    "CharacterSpacing",
    "FlipAngle",
    "Override",
    "Shape_Length",
    "Shape_Area",
    "last_edited_date",
    "last_edited_user",
    "created_date",
    "created_user",
)
lcStandardFields = []
for f in standardFields:
    lcStandardFields.append(f.lower())

# fields whose values must be defined in Glossary
definedTermFieldsList = (
    "Type",
    "ExistenceConfidence",
    "IdentityConfidence",
    "ParagraphStyle",
    "GeoMaterialConfidence",
    "ErrorMeasure",
    "AgeUnits",
    "LocationMethod",
    "ScientificConfidence",
)

metadataChecked = False  # script will set to True if metadata record is checked

requiredTables = ["DataSources", "DescriptionOfMapUnits", "Glossary", "GeoMaterialDict"]
requiredFeatureDataSets = ["GeologicMap"]
requiredGeologicMapFeatureClasses = ["ContactsAndFaults", "MapUnitPolys"]

schemaExtensions = [
    "<i>Some of the extensions to the GeMS schema identified here may be necessary to capture geologic content and are entirely appropriate. <b>Please document these extensions in metadata for the database, any accompanying README file, and (if applicable) any transmittal letter that accompanies the dataset.</b> Other extensions may be intermediate datasets, fields, or files that should be deleted before distribution of the database.</i><br>"
]
schemaErrorsMissingElements = ["Missing required elements"]
schemaErrorsMissingFields = ["Missing or mis-defined fields"]


missingRequiredValues = [
    "Fields that are missing required values"
]  #  entries are [field, table]

all_IDs = []  #  entries are [_IDvalue, table]
duplicate_IDs = ["Duplicated _ID values"]  # entries are [value, table]

dataSources_IDs = []  # _IDs from DataSources
allDataSourcesRefs = (
    []
)  # list of all references to DataSources. Entries are [value, table]
missingSourceIDs = [
    "Missing DataSources entries. Only one reference to each missing entry is cited"
]
unusedSourceIDs = [
    "Entries in DataSources that are not otherwise referenced in database"
]
duplicatedSourceIDs = ["Duplicated source_IDs in DataSources"]

glossaryTerms = []  # Terms from Glossary
allGlossaryRefs = []  # list of all references to Glossary. Entries are [value, table]
missingGlossaryTerms = [
    "Missing terms in Glossary. Only one reference to each missing term is cited"
]
unusedGlossaryTerms = ["Terms in Glossary that are not otherwise used in geodatabase"]
glossaryTermDuplicates = ["Duplicated terms in Glossary"]

dmuMapUnits = []
allMapUnits = []  # list of all MapUnit references. Entries are [value, table]
missingDmuMapUnits = [
    "MapUnits missing from DMU. Only one reference to each missing unit is cited"
]
unusedDmuMapUnits = [
    "MapUnits in DMU that are not present on map, in CMU, or elsewhere"
]
dmuMapUnitsDuplicates = ["Duplicated MapUnit values in DescriptionOfMapUnits"]

allGeoMaterialValues = []  # values of GeoMaterial cited in DMU or elsewhere
geoMaterialErrors = ["Errors associated with GeoMaterialDict and GeoMaterial values"]

allDMUHKeyValues = []
hKeyErrors = ["HierarchyKey errors, DescriptionOfMapUnits"]
#  values are [value, errorType].  Return both duplicates

topologyErrors = ["Feature datasets with bad basic topology"]
topologyErrorNote = """
<i>Note that the map boundary commonly gives an unavoidable "Must Not Have Gaps" line error.
Other errors should be fixed. Level 2 errors are also Level 3 errors. Errors are
identified in feature classes within XXX-Validation.gdb</i><br><br>
"""

zeroLengthStrings = [
    'Zero-length, whitespace-only, or "&ltNull&gt" text values that probably should be &lt;Null&gt;'
]

SRFWarnings = []
otherWarnings = []
leadingTrailingSpaces = ["Text values with leading or trailing spaces:"]

#######END GLOBAL VARIABLESS###################

#######HTML STUFF##############################
rdiv = '<div class="report">\n'
divend = "</div>\n"

tableStart = """<table class="ess-tables">
  <tbody>
"""

tableEnd = """  </tbody>
</table>
"""

style = """ 
    <style>
        .report {
            font-family: Courier New, Courier, monospace;
            margin-left: 20px;
            margin-right: 20px;
        }
        h2,
        h3 {
            background-color: lightgray;
            padding: 5px;
            border-radius: 4px;
            font-family: "Century Gothic", CenturyGothic, AppleGothic, sans-serif;
        }
        h4 {
        margin-bottom: 4px;
        font-size: larger;
        }
        .ess-tables {
            width: 95%;
            margin-left: 20px;
        }
        .table-header:hover {
            cursor:pointer;
        }
        table,
        th,
        td {
            border: 1px solid gray;
            border-collapse: collapse;
            padding: 3px;
        }
        .table {
            color:darkorange;
            font-weight:bold;
        }
        .field {
            color: darkblue;
            font-weight:bold;
        }
        .value {
            color:darkgreen;
            font-weight:bold;
        }
        .highlight{
            background-color:#f2fcd6;
            padding:0 2px;
            border-radius:3px;
            border-bottom:1px solid gray;
        }
        li {
            list-style: disc;
            margin-top: 1px;
            margin-bottom: 1px;
        }
        #back-to-top {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 10px;
            margin: 10px;
            background-color: rgba(250,250,250,0.7);
            border-radius:5px;
        }
    </style>
"""

colorCodes = """
    <div class="report">
        <h4>Color Codes</h4>
        <span class="table">Orange</span> are tables, feature classes, or feature datasets in the geodatabase<br>
        <span class="field">Blue</span> are fields in a table</br>
        <span class="value">Green</span> are values in a field</br>
    </div>
    """

##########END HTML STUFF####################


def getHKeyErrors(HKs):
    # getHKeyErrors collects values with bad separators, bad element sizes, duplicates, and missing sequential values
    addMsgAndPrint("Checking DescriptionOfMapUnits HKey values")
    hKeyErrs = []
    splitKeys = []
    if len(HKs) == 0:
        hKeyErrs.append("No HierarchyKey values?!")
        return hKeyErrs
    fragmentLength = len(HKs[0].split("-")[0])
    lastHK = ""
    HKs.sort()
    for hk in HKs:
        # duplicate values
        if hk == lastHK:
            hKeyErrs.append(hk + " --duplicate value")
        else:
            ii = hk.split("-")
            key = []
            for fragment in ii:
                # non-numeric fragment
                try:
                    key.append(int(fragment))
                except:  # fails, probably because frag can't be translated to an integer
                    hKeyErrs.append(hk + " --probable non-numeric fragment")
                # inconsistent fragment length or bad separator
                if len(fragment) != fragmentLength:
                    hKeyErrs.append(hk + " --bad fragment length")
            splitKeys.append(key)
            lastHK = hk
    return hKeyErrs


def isFeatureDatasetAMap(fd):
    #  examines fd to see if it is a geologic map:
    #    does it have a poly feature class named xxxMapUnitPolysxxx?
    #    does it have a polyline feature class named xxxContactsAndFaultsxxx?
    addMsgAndPrint("  checking " + fd + " to see if it has MUP and CAF feature classes")
    isMap = True
    CAF = ""
    MUP = ""
    fcs = arcpy.ListFeatureClasses()
    for fc in fcs:
        if fc.find("ContactsAndFaults") > -1 and fc.lower().find("anno") == -1:
            CAF = fc
        if fc.find("MapUnitPolys") > -1 and fc.lower().find("anno") == -1:
            MUP = fc
    if CAF == "" or MUP == "":
        isMap = False
    return isMap, MUP, CAF


def checkTopology(workdir, inGdb, outGdb, fd, MUP, CAF, level=2):
    # checks geologic-map topology of featureclasses MUP and CAF in feature dataset fd
    # results (# of errors - 1) are appended to global variable topologyErrors
    # inGdb. outGdb = full path.  fd, MUP, CAF = basename only
    # level is flag for how much topology to check -- level2 or level3
    addMsgAndPrint(f"  checking topology of {fd}")

    # make errors fd
    outFd = os.path.join(outGdb, fd)
    if not arcpy.Exists(outFd):
        arcpy.CreateFeatureDataset_management(outGdb, fd, inGdb + "/" + fd)

    # delete any existing topology, CAF, MUP and copy MUP and CAF to errors fd
    outCaf = os.path.join(outFd, CAF)
    outMup = os.path.join(outFd, MUP)
    outTop = os.path.join(outFd, f"{fd}_topology")
    for i in outTop, outMup, outCaf:
        testAndDelete(i)
    arcpy.Copy_management(os.path.join(inGdb, fd, MUP), outMup)
    arcpy.Copy_management(os.path.join(inGdb, fd, CAF), outCaf)

    # create topology
    addMsgAndPrint("    creating " + outTop)
    arcpy.CreateTopology_management(outFd, os.path.basename(outTop))

    # add feature classes to topology
    arcpy.AddFeatureClassToTopology_management(outTop, outCaf, 1, 1)
    arcpy.AddFeatureClassToTopology_management(outTop, outMup, 2, 2)

    # add rules
    addMsgAndPrint("    adding level 2 rules to topology:")
    if arcpy.Exists(outMup):
        for aRule in ("Must Not Overlap (Area)", "Must Not Have Gaps (Area)"):
            addMsgAndPrint(f"      {aRule}")
            arcpy.AddRuleToTopology_management(outTop, aRule, outMup)
        addMsgAndPrint("      " + "Boundary Must Be Covered By (Area-Line)")
        arcpy.AddRuleToTopology_management(
            outTop, "Boundary Must Be Covered By (Area-Line)", outMup, "", outCaf
        )
    if level == 3:
        addMsgAndPrint("    adding level 3 rules to topology:")
        for aRule in (
            "Must Not Overlap (Line)",
            "Must Not Self-Overlap (Line)",
            "Must Not Self-Intersect (Line)",
        ):
            addMsgAndPrint(f"      {aRule}")
            arcpy.AddRuleToTopology_management(outTop, aRule, outCaf)

    # validate topology
    addMsgAndPrint("    validating topology")
    arcpy.ValidateTopology_management(outTop)
    nameToken = os.path.basename(outCaf).replace("ContactsAndFaults", "")
    if nameToken == "":
        nameToken = "GeologicMap"
    nameToken = f"errors_{nameToken}Topology"

    for sfx in ("_point", "_line", "_poly"):
        testAndDelete(os.path.join(outFd, nameToken + sfx))

    # export topology errors
    addMsgAndPrint("    exporting topology errors")
    arcpy.ExportTopologyErrors_management(outTop, outFd, nameToken)
    nErrs = 0
    for sfx in ("_point", "_line", "_poly"):
        fc = os.path.join(outFd, nameToken + sfx)
        nErrs = nErrs + numberOfRows(fc)
        if numberOfRows(fc) == 0:
            testAndDelete(fc)
    return nErrs - 1  # subtract the perimeter "Must not have gaps" error


def removeDuplicates(alist):
    nodupList = []
    for i in alist:
        if not i in nodupList:
            nodupList.append(i)
    return nodupList


def matchRefs(definedVals, allRefs):
    # for references to/from Glossary and DataSources
    # allrefs are [value, field, table]
    used = removeDuplicates(allRefs)
    usedVals = []
    unused = []
    missing = []
    plainUnused = []
    for i in used:
        ### problem here with values in Unicode. Not sure solution will be generally valid
        # if not i[0].encode("ascii",'xmlcharrefreplace') in definedVals and not i[0] in usedVals:
        if not i[0] in definedVals and not i[0] in usedVals:
            missing.append(
                '<span class="value">'
                + str(i[0])
                + '</span>, field <span class="field">'
                + i[1]
                + '</span>, table <span class="table">'
                + i[2]
                + "</span>"
            )
        usedVals.append(i[0])
    missing.sort()
    for i in definedVals:
        if not i in usedVals:
            unused.append('<span class="value">' + str(i) + "</span>")
            plainUnused.append(i)
    unused.sort()
    return unused, missing, plainUnused


def getDuplicateIDs(all_IDs):
    addMsgAndPrint("Getting duplicate _ID values")
    # get values that are duplicates
    all_IDs.sort()
    lastID = ["", ""]
    duplicateIDs = []
    for ID in all_IDs:
        if ID[0] == lastID[0]:
            duplicateIDs.append(ID)
        lastID = ID
    # remove duplicates
    dupIDs = removeDuplicates(duplicateIDs)
    dupIDs.sort()
    dups = []
    # convert to formatted HTML
    for ID in dupIDs:
        dups.append(
            '<span class="value">'
            + ID[0]
            + '</span> in table <span class="table">'
            + ID[1]
            + "</span>"
        )
    return dups


def getDuplicates(termList):
    termList.sort()
    dups1 = []
    lastTerm = ""
    for t in termList:
        if t == lastTerm:
            dups1.append(t)
        lastTerm = t
    dups = removeDuplicates(dups1)
    dups.sort()
    return dups


def appendValues(globalList, someValues):
    for v in someValues:
        globalList.append(v)


def tableCell(contents):
    return '<td valign="top">' + contents + "</td>"


def tableRow(cells):
    row = "  <tr>\n"
    for cell in cells:
        row = row + "    " + tableCell(cell) + "\n"
    row = row + "  </tr>"
    return row


def criterionStuff(
    errorsName, summary2, errors2, txt1, errList, anchorName, linkTxt, isLevel
):
    if len(errList) == 1:
        txt2 = "PASS"
    else:
        txt2 = (
            '<font color="#ff0000">FAIL &nbsp;</font><a href="'
            + errorsName
            + "#"
            + anchorName
            + '">'
            + str(len(errList) - 1)
            + " "
            + linkTxt
            + "</a>"
        )
        isLevel = False
        errors2.append('<h4><a name="' + anchorName + '">' + errList[0] + "</a></h4>")
        if errList == topologyErrors:
            errors2.append(topologyErrorNote)
        if len(errList) == 1:
            errors2.apppend(space4 + "None<br>")
            addMsgAndPrint("appending None")
        for i in errList[1:]:
            errors2.append(space4 + i + "<br>")
    summary2.append(tableRow([txt1, txt2]))
    return isLevel


def writeOutputLevel2(errorsName):  # need name of errors.html file for anchors
    isLevel2 = True  # set to false in Criterion
    summary2 = []
    errors2 = [rdiv]
    summary2.append(tableStart)
    txt1 = "2.1 Has required elements: nonspatial tables DataSources, DescriptionOfMapUnits, GeoMaterialDict; feature dataset GeologicMap with feature classes ContactsAndFaults and MapUnitPolys"
    isLevel2 = criterionStuff(
        errorsName,
        summary2,
        errors2,
        txt1,
        schemaErrorsMissingElements,
        "MissingElements",
        "missing element(s)",
        isLevel2,
    )
    txt1 = (
        "2.2 Required fields within required elements are present and correctly defined"
    )
    isLevel2 = criterionStuff(
        errorsName,
        summary2,
        errors2,
        txt1,
        schemaErrorsMissingFields,
        "MissingFields",
        "missing or mis-defined field(s)",
        isLevel2,
    )
    txt1 = "2.3 GeologicMap topology: no internal gaps or overlaps in MapUnitPolys, boundaries of MapUnitPolys are covered by ContactsAndFaults"
    isLevel2 = criterionStuff(
        errorsName,
        summary2,
        errors2,
        txt1,
        topologyErrors,
        "Topology",
        "feature dataset(s) with bad topology",
        isLevel2,
    )
    txt1 = (
        "2.4 All map units in MapUnitPolys have entries in DescriptionOfMapUnits table"
    )
    isLevel2 = criterionStuff(
        errorsName,
        summary2,
        errors2,
        txt1,
        missingDmuMapUnits,
        "dmuComplete",
        "map unit(s) missing in DMU",
        isLevel2,
    )
    txt1 = "2.5 No duplicate MapUnit values in DescriptionOfMapUnit table"
    isLevel2 = criterionStuff(
        errorsName,
        summary2,
        errors2,
        txt1,
        dmuMapUnitsDuplicates,
        "NoDmuDups",
        "duplicated map unit(s) missing in DMU",
        isLevel2,
    )
    txt1 = "2.6 Certain field values within required elements have entries in Glossary table"
    isLevel2 = criterionStuff(
        errorsName,
        summary2,
        errors2,
        txt1,
        missingGlossaryTerms,
        "MissingGlossary",
        "term(s) missing in Glossary",
        isLevel2,
    )
    txt1 = "2.7 No duplicate Term values in Glossary table"
    isLevel2 = criterionStuff(
        errorsName,
        summary2,
        errors2,
        txt1,
        glossaryTermDuplicates,
        "NoGlossaryDups",
        "duplicated term(s) in Glossary",
        isLevel2,
    )
    txt1 = "2.8 All xxxSourceID values in required elements have entries in DataSources table"
    isLevel2 = criterionStuff(
        errorsName,
        summary2,
        errors2,
        txt1,
        missingSourceIDs,
        "MissingDataSources",
        "entry(ies) missing in DataSources",
        isLevel2,
    )
    txt1 = "2.9 No duplicate DataSources_ID values in DataSources table"
    isLevel2 = criterionStuff(
        errorsName,
        summary2,
        errors2,
        txt1,
        duplicatedSourceIDs,
        "NoDataSourcesDups",
        "duplicated source(s) in DataSources",
        isLevel2,
    )
    summary2.append(tableEnd)
    errors2.append(divend)
    return isLevel2, summary2, errors2


def writeOutputLevel3():
    isLevel3 = True  # set to false if ...
    summary3 = []
    errors3 = [rdiv]
    summary3.append(tableStart)
    txt1 = "3.1 Table and field definitions conform to GeMS schema"
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        schemaErrorsMissingFields,
        "Missingfields3",
        "missing or mis-defined element(s)",
        isLevel3,
    )
    txt1 = "3.2 All map-like feature datasets obey topology rules. No MapUnitPolys gaps or overlaps. No ContactsAndFaults overlaps, self-overlaps, or self-intersections. MapUnitPoly boundaries covered by ContactsAndFaults"
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        topologyErrors,
        "Topology3",
        "feature dataset(s) with bad topology",
        isLevel3,
    )
    txt1 = "3.3 No missing required values"
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        missingRequiredValues,
        "MissingReqValues",
        "missing required value(s)",
        isLevel3,
    )
    txt1 = "3.4 No missing terms in Glossary"
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        missingGlossaryTerms,
        "MissingGlossary",
        "missing term(s) in Glossary",
        isLevel3,
    )
    txt1 = "3.5 No unnecessary terms in Glossary"
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        unusedGlossaryTerms,
        "ExcessGlossary",
        "unnecessary term(s) in Glossary",
        isLevel3,
    )
    txt1 = "3.6 No missing sources in DataSources"
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        missingSourceIDs,
        "MissingDataSources",
        "missing source(s) in DataSources",
        isLevel3,
    )
    txt1 = "3.7 No unnecessary sources in DataSources"
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        unusedSourceIDs,
        "ExcessDataSources",
        "unnecessary source(s) in DataSources",
        isLevel3,
    )
    txt1 = "3.8 No map units without entries in DescriptionOfMapUnits"
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        missingDmuMapUnits,
        "MissingMapUnits",
        "missing map unit(s) in DMU",
        isLevel3,
    )
    txt1 = "3.9 No unnecessary map units in DescriptionOfMapUnits"
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        unusedDmuMapUnits,
        "ExcessMapUnits",
        "unnecessary map unit(s) in DMU",
        isLevel3,
    )
    txt1 = (
        "3.10 HierarchyKey values in DescriptionOfMapUnits are unique and well formed"
    )
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        hKeyErrors,
        "hKeyErrors",
        "HierarchyKey error(s) in DMU",
        isLevel3,
    )
    txt1 = "3.11 All values of GeoMaterial are defined in GeoMaterialDict. GeoMaterialDict is as specified in the GeMS standard"
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        geoMaterialErrors,
        "GM_Errors",
        "GeoMaterial error(s)",
        isLevel3,
    )
    txt1 = "3.12 No duplicate _ID values"
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        duplicate_IDs,
        "duplicate_IDs",
        "duplicated _ID value(s)",
        isLevel3,
    )
    txt1 = "3.13 No zero-length or whitespace-only strings"
    isLevel3 = criterionStuff(
        errorsName,
        summary3,
        errors3,
        txt1,
        zeroLengthStrings,
        "zeroLengthStrings",
        "zero-length or whitespace string(s)",
        isLevel3,
    )
    summary3.append(tableEnd)
    errors3.append(divend)
    return isLevel3, summary3, errors3


def findOtherStuff(wksp, okStuff):
    # finds files, feature classes, ... in a workspace
    #  that are not in okStuff and writes them to schemaExtensions
    addMsgAndPrint("  checking " + os.path.basename(wksp) + " for other stuff")
    walk = arcpy.da.Walk(wksp)
    for dirpath, dirnames, filenames in walk:
        if os.path.basename(dirpath) == os.path.basename(wksp):
            for fn in filenames:
                if fn not in okStuff:
                    dsc = arcpy.Describe(fn)
                    schemaExtensions.append(
                        dsc.dataType + ' <span class="table">' + fn + "</span>"
                    )


def checkMetadata(inGdb, txtFile, errFile, xmlFile):
    addMsgAndPrint("Checking metadata")
    passesMP = True
    metadataChecked = False
    try:
        if os.path.exists(xmlFile):
            os.remove(xmlFile)
        # export metadata
        src_item_md = md.Metadata(inGdb)
        src_item_md.exportMetadata(xmlFile, "FGDC_CSDGM")
    except:
        addMsgAndPrint("Failed to delete " + xmlFile)
        addMsgAndPrint("Delete it manually and re-run validation tool.")
    # run it through mp
    args = [mp_path, "-t", txtFile, "-e", errFile, xmlFile]
    subprocess.call(args)
    mpErrors = open(errFile).readlines()
    for aline in mpErrors:
        if aline.split()[0] == "Error":
            passesMP = False
    metadataChecked = True
    # except:
    #   addMsgAndPrint('  processing metadata failed')
    return metadataChecked, passesMP


def checkForLockFiles(inGdb):
    oldDir = os.getcwd()
    os.chdir(inGdb)
    lockFiles = glob.glob("*.lock")
    nLockFiles = len(lockFiles)
    if nLockFiles > 0:
        otherWarnings.append(str(nLockFiles) + " lock files in database")
    os.chdir(oldDir)
    return


def checkFieldDefinitions(def_table, compare_table=None):
    """Compares the fields in a compare_table to those in a controlled def_table
    There are two arguments, one optional, to catch the case where, for example
    we want to compare the fields in CSAMapUnitPolys with MapUnitPolys.
    tableDict will not have the key 'CSAMapUnitPolys'. The key MapUnitPolys is derived in
    def ScanTable from CSAMapUnitPolys as the table to which it should be compared.
    If the compare_table IS the name of a table in the GeMS definition; it doesn't need to be derived,
    it does not need to be supplied.
    """

    # build dictionary of required fields
    requiredFields = {}
    optionalFields = {}
    requiredFieldDefs = copy.deepcopy(tableDict[def_table])

    if compare_table:
        # update the definition of the _ID field to include a 'CSX' prefix
        prefix = compare_table[:3]
        id_item = [n for n in requiredFieldDefs if n[0] == def_table + "_ID"]
        new_id = prefix + id_item[0][0]
        i = requiredFieldDefs.index(id_item[0])
        requiredFieldDefs[i][0] = new_id
    else:
        compare_table = def_table
    for fieldDef in requiredFieldDefs:
        if fieldDef[2] != "Optional":
            requiredFields[fieldDef[0]] = fieldDef
        else:
            optionalFields[fieldDef[0]] = fieldDef
    # build dictionary of existing fields
    try:
        existingFields = {}
        fields = arcpy.ListFields(compare_table)
        for field in fields:
            existingFields[field.name] = field
        # now check to see what is excess / missing
        for field in requiredFields.keys():
            if field not in existingFields:
                schemaErrorsMissingFields.append(
                    '<span class="table">'
                    + compare_table
                    + '</span>, field <span class="field">'
                    + field
                    + "</span> is missing"
                )
        for field in existingFields.keys():
            if (
                not (field.lower() in lcStandardFields)
                and not (field in requiredFields.keys())
                and not (field in optionalFields.keys())
            ):
                schemaExtensions.append(
                    '<span class="table">'
                    + compare_table
                    + '</span>, field <span class="field">'
                    + field
                    + "</span>"
                )
            # check field definition
            fType = existingFields[field].type
            if field in requiredFields.keys() and fType != requiredFields[field][1]:
                schemaErrorsMissingFields.append(
                    '<span class="table">'
                    + compare_table
                    + '</span>, field <span class="field">'
                    + field
                    + "</span>, type should be "
                    + requiredFields[field][1]
                )
            if field in optionalFields.keys() and fType != optionalFields[field][1]:
                schemaErrorsMissingFields.append(
                    '<span class="table">'
                    + compare_table
                    + '</span>, field <span class="field">'
                    + field
                    + "</span>, type should be "
                    + optionalFields[field][1]
                )
    except:
        schemaErrorsMissingFields.append(
            '<span class="table">'
            + compare_table
            + "</span> could not get field list. Fields not checked."
        )

    del requiredFieldDefs


def notEmpty(x):
    # will converting x to string ever return an unexpected value?
    if x != None and str(x).strip() != "":
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


def isBadNull(x):
    try:
        if str(x).lower() == "<null>" or str(x) == "" or str(x).strip() == "":
            return True
    except:
        return False
    else:
        return False


def fixNull(x):
    # x = x.encode('ascii','xmlcharrefreplace')
    if x.lower() == "<null>":
        return "&lt;Null&gt;"
    else:
        return x


def scanTable(table, fds=None):
    if fds is None:
        fds = ""
    addMsgAndPrint("  scanning " + table)
    dsc = arcpy.Describe(table)
    ### check table and field definition against GeMS_Definitions
    if table == "GeoMaterialDict":
        return ""
    elif table in tableDict:  # table is defined in GeMS_Definitions
        isExtension = False
        fieldDefs = tableDict[table]
        checkFieldDefinitions(table)
    elif (
        fds[:12] == "CrossSection"
        and table[:3] == "CS" + fds[12]
        and table[3:] in tableDict
    ):
        isExtension = False
        fieldDefs = tableDict[table[3:]]
        checkFieldDefinitions(table[3:], table)

    else:  # is an extension
        isExtension = True
        schemaExtensions.append(
            dsc.dataType + ' <span class="table">' + table + "</span>"
        )
    ### check for edit tracking
    try:
        if dsc.editorTrackingEnabled:
            otherWarnings.append(
                'Editor tracking is enabled on <span class="table">' + table + "</span>"
            )
    except:
        warn_text = f"""Cannot determine if Editor Tracking is enabled on <span class="table">'{table}'</span>' or not;  
                        probably due to an older version of ArcGIS Pro being used. Check for this manually."""
        otherWarnings.append(warn_text)
    ### assign fields to categories:
    fields = arcpy.ListFields(table)
    fieldNames = fieldNameList(table)
    # HKeyfield
    if table == "DescriptionOfMapUnits" and "HierarchyKey" in fieldNames:
        hasHKey = True
        hKeyIndex = fieldNames.index("HierarchyKey")
    else:
        hasHKey = False
    # idField
    idField = table + "_ID"
    if idField in fieldNames:
        hasIdField = True
        idIndex = fieldNames.index(idField)
    else:
        hasIdField = False
        # we don't care that ArcGIS-controlled tables do not have _ID fields. What is the point?
        # Attachment tables are one kind but add others here as necessary
        # not the best logic to depend on the name, but there is no table type that identifies
        # these kinds of tables.
        if not "__ATTACH" in table:
            if isExtension:
                schemaErrorsMissingFields.append(
                    '<span class="table">' + table + "</span> lacks an _ID field"
                )
        else:
            pass
    # Term field
    if table == "Glossary" and "Term" in fieldNames:
        hasTermField = True
        termFieldIndex = fieldNames.index("Term")
    else:
        hasTermField = False
    dataSourceIndices = []
    glossTermIndices = []
    noNullsFieldIndices = []
    stringFieldIndices = []
    mapUnitFieldIndex = []
    geoMaterialFieldIndex = []
    specialDmuFieldIndices = []

    # find objectid field, which might not be called OBJECTID
    # have also seen FID, OBJECTID_1, ATTACHMENTID
    oid_name = [f.name for f in fields if f.type == "OID"][0]
    objIdIndex = fieldNames.index(oid_name)

    # continue cataloging the field names
    for f in fieldNames:
        # dataSource fields
        if f.find("SourceID") > -1:
            dataSourceIndices.append(fieldNames.index(f))
        # Glossary term fields
        if f in definedTermFieldsList:
            glossTermIndices.append(fieldNames.index(f))
        # MapUnit fields
        if f == "MapUnit":
            mapUnitFieldIndex.append(fieldNames.index(f))
        fUpper = f.upper()

        # GeoMaterial fields
        if f == "GeoMaterial":
            geoMaterialFieldIndex.append(fieldNames.index(f))
        # NoNulls fields
        if not isExtension:
            for fdef in fieldDefs:
                if f == fdef[0] and fdef[2] == "NoNulls":
                    noNullsFieldIndices.append(fieldNames.index(f))
        # String fields
        for ff in fields:
            if f == ff.baseName and ff.type == "String":
                stringFieldIndices.append(fieldNames.index(f))
        # special DMU fields, cannot be null if MapUnit is non-mull
        if table == "DescriptionOfMapUnits" and f in (
            "FullName",
            "Age",
            "GeoMaterial",
            "GeoMaterialConfidence",
            "DescriptionSourceID",
        ):
            specialDmuFieldIndices.append(fieldNames.index(f))

    mapUnits = []
    ### open search cursor and run through rows
    with arcpy.da.SearchCursor(table, fieldNames) as cursor:
        for row in cursor:
            if hasHKey and row[hKeyIndex] != None:
                allDMUHKeyValues.append(row[hKeyIndex])
            if hasTermField:
                xx = row[termFieldIndex]
                if notEmpty(xx):
                    # addMsgAndPrint(xx)
                    glossaryTerms.append(fixNull(xx))
            if hasIdField:
                xx = row[idIndex]
                if notEmpty(xx):
                    all_IDs.append([xx, table])
                    if table == "DataSources":
                        dataSources_IDs.append(fixNull(xx))
            for i in mapUnitFieldIndex:
                xx = row[i]
                if notEmpty(xx):
                    if table == "DescriptionOfMapUnits":
                        dmuMapUnits.append(fixNull(xx))
                    else:
                        if not xx in mapUnits:
                            mapUnits.append(fixNull(xx))
                        xxft = [row[i], "MapUnit", table]
                        if not xxft in allMapUnits:
                            allMapUnits.append(xxft)
            for i in noNullsFieldIndices:
                xx = row[i]
                if empty(xx) or isBadNull(xx):
                    missingRequiredValues.append(
                        '<span class="table">'
                        + table
                        + '</span>, field <span class="field">'
                        + fieldNames[i]
                        + "</span>, "
                        + fieldNames[objIdIndex]
                        + " "
                        + str(row[objIdIndex])
                    )
            for i in stringFieldIndices:
                xx = row[i]
                oxxft = (
                    '<span class="table">'
                    + table
                    + '</span>, field <span class="field">'
                    + fieldNames[i]
                    + "</span>, "
                    + fieldNames[objIdIndex]
                    + " "
                    + str(row[objIdIndex])
                )
                if (
                    i not in noNullsFieldIndices
                    and xx != None
                    and (xx.strip() == "" or xx.lower() == "<null>")
                ):
                    zeroLengthStrings.append(oxxft)
                if xx != None and xx.strip() != "" and xx.strip() != xx:
                    leadingTrailingSpaces.append(space4 + oxxft)
            for i in geoMaterialFieldIndex:
                if notEmpty(row[i]):
                    if not row[i] in allGeoMaterialValues:
                        allGeoMaterialValues.append(row[i])
            for i in glossTermIndices:
                if notEmpty(row[i]):
                    xxft = [row[i], fieldNames[i], table]
                    if not xxft in allGlossaryRefs:
                        allGlossaryRefs.append(xxft)

            for i in dataSourceIndices:
                xx = row[i]
                if notEmpty(xx):
                    ids = [e.strip() for e in xx.split("|") if e.strip()]
                    for xxref in ids:
                        xxft = [xxref, fieldNames[i], table]
                        if not xxref in allDataSourcesRefs:
                            allDataSourcesRefs.append(xxft)

            if mapUnitFieldIndex != [] and row[mapUnitFieldIndex[0]] != None:
                for i in specialDmuFieldIndices:
                    xx = row[i]
                    if empty(xx) or isBadNull(xx):
                        missingRequiredValues.append(
                            '<span class="table">'
                            + table
                            + '</span>, field <span class="field">'
                            + fieldNames[i]
                            + "</span>, ObjectID "
                            + str(row[objIdIndex])
                        )

    return mapUnits


def tableToHtml(table, html):
    # table is input table, html is output html file
    addMsgAndPrint("    " + str(table))
    fields = arcpy.ListFields(table)
    html.write('<table class="ess-tables">\n')
    # write header row
    html.write("<thead>\n  <tr>\n")

    # initialize a list on the objectid field
    fieldNames = [f.name for f in fields if f.type == "OID"]

    html.write(f"<th>{fieldNames[0]}</th>\n")
    for field in fields:
        if not field.name in standardFields:
            if field.name.find("_ID") > 1:
                token = "_ID"
            else:
                token = field.name
            html.write("<th>" + token + "</th>\n")
            fieldNames.append(field.name)
    html.write("  </tr>\n</thead")
    html.write("<tbody>")
    # write rows
    if table == "DescriptionOfMapUnits":
        sql = (None, "ORDER BY HierarchyKey")
    elif table == "Glossary":
        sql = (None, "ORDER BY Term")
    elif table == "DataSources":
        sql = (None, "ORDER BY DataSources_ID")
    else:
        sql = (None, None)
    with arcpy.da.SearchCursor(table, fieldNames, None, None, False, sql) as cursor:
        for row in cursor:
            html.write("<tr>\n")
            for i in range(0, len(fieldNames)):
                # if isinstance(row[i],unicode):
                #    html.write('<td>'+row[i].encode('ascii','xmlcharrefreplace')+'</td>\n')
                # else:
                try:
                    if str(row[i]) == "None":
                        html.write("<td>---</td>\n")
                    else:
                        html.write("<td>" + str(row[i]) + "</td>\n")
                except:
                    html.write("<td>***</td>\n")
                    addMsgAndPrint(str(type(row[i])))
                    addMsgAndPrint(row[i])
            html.write("</tr>\n")
    # finish table
    html.write("  </tbody>\n</table>\n")


# allGeoMaterialValues = []  # values of GeoMaterial cited in DMU or elsewhere
# geoMaterialErrors = ['Errors associated with GeoMaterialDict and GeoMaterial values']


def checkGeoMaterialDict(inGdb):
    addMsgAndPrint("  checking GeoMaterialDict")
    gmd = inGdb + "/GeoMaterialDict"
    refgmDict = {}
    gmDict = {}
    if arcpy.Exists(gmd):
        with arcpy.da.SearchCursor(gmd, ["GeoMaterial", "Definition"]) as cursor:
            for row in cursor:
                gmDict[row[0]] = row[1]
        geoMaterials = gmDict.keys()
        # check that all used values of GeoMaterial are in geoMaterials
        for i in allGeoMaterialValues:
            if not i in gmDict.keys():
                geoMaterialErrors.append(
                    '<span class="value">'
                    + str(i)
                    + '</span> not defined in <span class="table">GeoMaterialDict</span>'
                )
        with arcpy.da.SearchCursor(refgmd, ["GeoMaterial", "Definition"]) as cursor:
            for row in cursor:
                refgmDict[row[0]] = row[1]
        # check for equivalence with standard GeoMaterialDict
        refGeoMaterials = refgmDict.keys()
        for i in gmDict.keys():
            if i not in refGeoMaterials:
                geoMaterialErrors.append(
                    'Term **<span class="value">'
                    + i
                    + '</span>** is not in standard <span class="table">GeoMaterialDict</span> table'
                )
            else:
                if gmDict[i] != refgmDict[i]:
                    geoMaterialErrors.append(
                        'Definition of <span class="value">'
                        + i
                        + '</span> in <span class="table">GeoMaterialDict</span> does not match GeMS standard'
                    )
    else:
        addMsgAndPrint("Table " + gmd + " is missing.")
    return


def deleteExtraRows(table, field, vals):
    # deleteExtraRows('Glossary','Term',unused)
    if len(vals) == 0:
        return
    addMsgAndPrint("    removing extra rows from " + table)
    with arcpy.da.UpdateCursor(table, [field]) as cursor:
        for row in cursor:
            if row[0] in vals:
                addMsgAndPrint("      " + row[0])
                cursor.deleteRow()
    return


##############start main##################
##get inputs
inGdb = sys.argv[1]
if sys.argv[2] != "#":
    workdir = sys.argv[2]
else:
    workdir = os.path.dirname(inGdb)
gdbName = os.path.basename(inGdb)
refreshGeoMaterialDict = sys.argv[3]
skipTopology = sys.argv[4]
deleteExtraGlossaryDataSources = sys.argv[5]
compactDB = sys.argv[6]

refgmd = os.path.join(resources_path, "GeMS_lib.gdb", "GeoMaterialDict")
mp_path = os.path.join(resources_path, "mp.exe")

##validate inputs

if not arcpy.Exists(refgmd):
    addMsgAndPrint("Cannot find reference GeoMaterialDict table at " + refgmd)
    forceExit()
try:
    arcpy.env.workspace = inGdb
except:
    # is not ESRI database
    addMsgAndPrint("This does not appear to be an ESRI database. Halting here.")
    forceExit()
else:
    # write starting messages
    addMsgAndPrint(versionString)

    if editSessionActive(inGdb):
        arcpy.AddWarning(
            "\nDatabase is being edited. Results may be incorrect if there are unsaved edits\n"
        )

    if refreshGeoMaterialDict == "true":
        addMsgAndPrint("Refreshing GeoMaterialDict")
        gmd = inGdb + "/GeoMaterialDict"
        testAndDelete(gmd)
        arcpy.management.Copy(refgmd, gmd)
        addMsgAndPrint("Replacing GeoMaterial domain")
        ## remove domain from field
        arcpy.management.RemoveDomainFromField(
            inGdb + "/DescriptionOfMapUnits", "GeoMaterial"
        )
        ## DeleteDomain
        if "GeoMaterials" in arcpy.da.ListDomains(inGdb):
            arcpy.management.DeleteDomain(inGdb, "GeoMaterials")
        ##   make GeoMaterials domain
        arcpy.management.TableToDomain(
            inGdb + "/GeoMaterialDict",
            "GeoMaterial",
            "IndentedName",
            inGdb,
            "GeoMaterials",
            "",
            "REPLACE",
        )
        ##   attach it to DMU field GeoMaterial
        arcpy.management.AssignDomainToField(
            inGdb + "/DescriptionOfMapUnits", "GeoMaterial", "GeoMaterials"
        )

    # open output files
    summaryName = f"{gdbName}-Validation.html"
    sumFile = os.path.join(workdir, summaryName)
    summary = open(sumFile, "w", errors="xmlcharrefreplace")

    errorsName = f"{gdbName}-ValidationErrors.html"
    errorsFile = os.path.join(workdir, errorsName)
    errors = open(errorsFile, "w")

    # mdTxtFile = workdir+'/'+os.path.basename(inGdb)+metadataSuffix
    mdTxtFile = os.path.join(workdir, gdbName + metadataSuffix)
    mdErrFile = os.path.join(workdir, gdbName + metadataErrorsSuffix)
    mdXmlFile = mdTxtFile[:-3] + "xml"

    # delete errors gdb if it exists and make a new one
    gdbVal = f"{gdbName[:-4]}_Validation.gdb"
    outErrorsGdb = os.path.join(workdir, gdbVal)
    if not arcpy.Exists(outErrorsGdb):
        arcpy.CreateFileGDB_management(workdir, gdbVal)

    # level 2 compliance
    addMsgAndPrint("Looking at level 2 compliance")
    for tb in requiredTables:
        if arcpy.Exists(tb):
            scanTable(tb)
        else:
            schemaErrorsMissingElements.append(f'Table <span class="table">{tb}</span>')
    gMap_MapUnits = []
    if not arcpy.Exists("GeologicMap"):
        gMapSRF = ""
        schemaErrorsMissingElements.append(
            'Feature dataset <span class="table">GeologicMap</span>'
        )
    else:
        srf = arcpy.Describe("GeologicMap").spatialReference
        gMapSRF = srf.name

        # check for NAD83 or WGS84
        if srf.type == "Geographic":
            pcsd = srf.datumName
        else:  # is projected
            pcsd = srf.PCSName
        if pcsd.find("World_Geodetic_System_1984") < 0 and pcsd.find("NAD_1983") < 0:
            SRFWarnings.append(
                f"Spatial reference framework is {pcsd}. Consider reprojecting this dataset to NAD83 or WGS84"
            )
        arcpy.env.workspace = "GeologicMap"
        gMap_MapUnits = []
        for fc in requiredGeologicMapFeatureClasses:
            if arcpy.Exists(fc):
                mapUnits = scanTable(fc)
                appendValues(gMap_MapUnits, mapUnits)
            else:
                schemaErrorsMissingElements.append(
                    f'Feature class <span class="table">GeologicMap/{fc}</span>'
                )
        isMap, MUP, CAF = isFeatureDatasetAMap("GeologicMap")
        if isMap:
            if skipTopology == "false":
                nTopoErrors = checkTopology(
                    workdir, inGdb, outErrorsGdb, "GeologicMap", MUP, CAF, 2
                )
                if nTopoErrors > 0:
                    topologyErrors.append(
                        str(nTopoErrors)
                        + ' Level 2 errors in <span class="table">GeologicMap</span>'
                    )
            else:
                addMsgAndPrint("  skipping topology check")
                topologyErrors.append("Level 2 topology check was skipped")
        arcpy.env.workspace = inGdb

    addMsgAndPrint("  getting unused, missing, and duplicated key values")
    unused, missing, plainUnused = matchRefs(dataSources_IDs, allDataSourcesRefs)
    appendValues(missingSourceIDs, missing)
    for d in getDuplicates(dataSources_IDs):
        duplicatedSourceIDs.append(f'<span class="value">{d}</span>')

    unused, missing, plainUnused = matchRefs(glossaryTerms, allGlossaryRefs)
    appendValues(missingGlossaryTerms, missing)
    for d in getDuplicates(glossaryTerms):
        glossaryTermDuplicates.append(f'<span class="value">{d}</span>')

    unused, missing, plainUnused = matchRefs(dmuMapUnits, allMapUnits)
    appendValues(missingDmuMapUnits, missing)
    for d in getDuplicates(dmuMapUnits):
        dmuMapUnitsDuplicates.append(f'<span class="value">{d}</span>')

    isLevel2, summary2, errors2 = writeOutputLevel2(errorsName)

    # reset some stuff
    topologyErrors = ["Feature datasets with bad basic topology"]
    missingSourceIDs = [
        "Missing DataSources entries. Only one reference to each missing entry is cited"
    ]
    missingGlossaryTerms = [
        "Missing terms in Glossary. Only one reference to each missing term is cited"
    ]
    missingDmuMapUnits = [
        "MapUnits missing from DMU. Only one reference to each missing unit is cited"
    ]

    # level 3 compliance
    addMsgAndPrint("Looking at level 3 compliance")
    tables = arcpy.ListTables()
    for tb in tables:
        if tb not in requiredTables:
            mapUnits = scanTable(tb)
    # check for other stuff at top level of gdb
    findOtherStuff(inGdb, tables)
    fds_MapUnits = []
    fds = arcpy.ListDatasets("*", "Feature")
    for fd in fds:
        fdSRF = arcpy.Describe(fd).spatialReference.name
        if fdSRF != gMapSRF:
            SRFWarnings.append(
                f"Spatial reference framework of {fd} does not match that of GeologicMap"
            )
        arcpy.env.workspace = fd
        fcs = arcpy.ListFeatureClasses()
        findOtherStuff(inGdb + "/" + fd, fcs)
        if fd == "GeologicMap":
            fdMapUnitList = gMap_MapUnits
        else:
            fdMapUnitList = []
        for fc in fcs:
            if not fc in requiredGeologicMapFeatureClasses:
                dsc = arcpy.Describe(fc)
                if dsc.featureType == "Simple":
                    mapUnits = scanTable(fc, fd)
                    appendValues(fdMapUnitList, mapUnits)
                else:
                    addMsgAndPrint(
                        "  ** skipping data set "
                        + fc
                        + ", featureType = "
                        + dsc.featureType
                    )
        isMap, MUP, CAF = isFeatureDatasetAMap(fd)
        if isMap:
            if skipTopology == "false":
                nTopoErrors = checkTopology(
                    workdir, inGdb, outErrorsGdb, fd, MUP, CAF, 3
                )
                if nTopoErrors > 0:
                    topologyErrors.append(
                        str(nTopoErrors)
                        + ' Level 3 errors in <span class="table">'
                        + fd
                        + "</span>"
                    )
            else:
                addMsgAndPrint("  skipping topology check")
                topologyErrors.append("Level 3 topology check was skipped")
        fds_MapUnits.append([fd, fdMapUnitList])
        arcpy.env.workspace = inGdb

    checkGeoMaterialDict(inGdb)

    addMsgAndPrint("  getting unused, missing, and duplicated key values")

    unused, missing, plainUnused = matchRefs(dataSources_IDs, allDataSourcesRefs)
    if deleteExtraGlossaryDataSources == "true":
        deleteExtraRows("DataSources", "DataSources_ID", plainUnused)
    else:
        appendValues(unusedSourceIDs, unused)
    appendValues(missingSourceIDs, missing)

    unused, missing, plainUnused = matchRefs(glossaryTerms, allGlossaryRefs)
    if deleteExtraGlossaryDataSources == "true":
        deleteExtraRows("Glossary", "Term", plainUnused)
    else:
        appendValues(unusedGlossaryTerms, unused)
    appendValues(missingGlossaryTerms, missing)

    unused, missing, plainUnused = matchRefs(dmuMapUnits, allMapUnits)
    appendValues(unusedDmuMapUnits, unused)
    appendValues(missingDmuMapUnits, missing)

    appendValues(duplicate_IDs, getDuplicateIDs(all_IDs))
    appendValues(
        hKeyErrors, getHKeyErrors(allDMUHKeyValues)
    )  # getHKeyErrors collects values with bad separators, bad element sizes, duplicates, and missing sequential values

    metadataChecked, passesMP = checkMetadata(inGdb, mdTxtFile, mdErrFile, mdXmlFile)
    checkForLockFiles(inGdb)

    isLevel3, summary3, errors3 = writeOutputLevel3()

    ### assemble output
    addMsgAndPrint("Writing output")
    addMsgAndPrint("  writing summary header")

    metadataTxt = os.path.basename(inGdb + metadataSuffix)
    metadataErrs = os.path.basename(inGdb + metadataErrorsSuffix)
    ###SUMMARY HEADER
    summary.write(style)
    summary.write(
        '<h2><a name="overview"><i>GeMS validation of </i> '
        + os.path.basename(inGdb)
        + "</a></h2>\n"
    )
    summary.write('<div class="report">Database path: ' + inGdb + "<br>\n")
    summary.write("File written by <i>" + versionString + "</i><br>\n")
    summary.write(time.asctime(time.localtime(time.time())) + "<br><br>\n")
    summary.write(
        "This file should be accompanied by "
        + errorsName
        + ", "
        + metadataTxt
        + ", and "
        + metadataErrs
        + ", all in the same directory.<br><br>\n"
    )
    if isLevel3 and isLevel2:
        summary.write(
            'This database is <a href=#Level3><font size="+1"><b>LEVEL 3 COMPLIANT</b></a></font>'
            + geologicNamesDisclaimer
            + "\n"
        )
    elif isLevel2:
        summary.write(
            'This database is <a href=#Level2><font size="+1"><b>LEVEL 2 COMPLIANT</b></a></font>'
            + geologicNamesDisclaimer
            + "\n"
        )
    else:  # is level 1
        summary.write(
            'This database may be <a href=#Level1><font size="+1"><b>LEVEL 1 COMPLIANT</b></a>. </font>\n'
        )

    if metadataChecked:
        if passesMP:
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
    addMsgAndPrint("  writing errors header")
    errors.write(style)
    errors.write(
        '<h2><a name="overview">'
        + os.path.basename(inGdb)
        + "-ValidationErrors</a></h2>\n"
    )
    errors.write('<div class="report">Database path: ' + inGdb + "<br>\n")
    errors.write("This file written by <i>" + versionString + "</i><br>\n")
    errors.write(time.asctime(time.localtime(time.time())) + "<br>\n")
    errors.write(
        """
        </div>
        <div id="back-to-top"><a href="#overview">Back to Top</a></div>
"""
    )
    errors.write(colorCodes)

    ###CONTENTS
    anchorRoot = os.path.basename(summaryName) + "#"
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
        '    <a href="'
        + anchorRoot
        + 'Database_Inventory">Database Inventory</a><br>\n'
    )
    summary.write("        </div>\n")

    ###COMPLIANCE CRITERIA
    summary.write('<h3><a name="Compliance_Criteria"></a>Compliance Criteria</h3>\n')
    summary.write(rdiv)
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
    addMsgAndPrint("  writing Level 2")
    summary.write('<h4><a name="Level2">LEVEL 2--MINIMALLY COMPLIANT</a></h4>\n')
    summary.write(
        "<i>A LEVEL 2 GeMS database is accompanied by a peer-reviewed Geologic Names report, including identification of suggested modifications to Geolex, and meets the following criteria:</i><br><br>\n"
    )
    for aln in summary2:
        summary.write(aln + "\n")
    errors.write("<h3>Level 2 errors</h3>\n")
    for aln in errors2:
        errors.write(aln + "\n")

    addMsgAndPrint("  writing Level 3")
    summary.write('<h4><a name="Level3">LEVEL 3--FULLY COMPLIANT</a></h4>\n')
    summary.write(
        "<i>A LEVEL 3 GeMS database meets these additional criteria:</i><br>\n"
    )
    for aln in summary3:
        summary.write(aln + "\n")
    errors.write("<h3>Level 3 errors</h3>\n")
    for aln in errors3:
        errors.write(aln + "\n")

    ###Warnings
    summary.write("<br>\n")
    nWarnings = -1  # leadingTrailingSpaces has a header line
    for w in SRFWarnings, leadingTrailingSpaces, otherWarnings:
        for aw in w:
            nWarnings = nWarnings + 1
    summary.write(
        '<a href="'
        + os.path.basename(errorsName)
        + '#Warnings">There are '
        + str(nWarnings)
        + " warnings<br></a>\n"
    )
    errors.write('<h3><a name="Warnings">Warnings</a></h3>\n')
    errors.write(rdiv)
    for w in SRFWarnings, otherWarnings:
        for aw in w:
            errors.write(aw + "<br>\n")
    if len(leadingTrailingSpaces) > 1:
        for aw in leadingTrailingSpaces:
            errors.write(aw + "<br>\n")
    errors.write(divend)
    summary.write(divend)

    ###EXTENSIONS TO SCHEMA
    addMsgAndPrint("  listing schema extensions")
    summary.write(
        '<h3><a name="Extensions"></a>Content not specified in GeMS schema</h3>\n'
    )
    summary.write(rdiv)
    if len(schemaExtensions) > 1:
        summary.write(schemaExtensions[0] + "<br>\n")
        for i in schemaExtensions[1:]:
            summary.write(space4 + i + "<br>\n")
    else:
        summary.write("None<br>\n")
    summary.write(divend)

    ###MAPUNITS MATCH
    addMsgAndPrint("  writing table of MapUnit presence/absence")
    summary.write(
        '<h3><a name="MapUnits_Match"></a>MapUnits in DescriptionOfMapUnits table, GeologicMap feature dataset, and other feature datasets</h3>\n'
    )
    fds_MapUnits.sort()  # put feature datasets in alphabetical order
    # fds_MapUnits = [ [dataset name [included map units]],[dsname, [incMapUnit]] ]
    summary.write(rdiv)
    summary.write(
        '<table class="ess-tables"; style="text-align:center"><tr><th>MapUnit</th><th>&nbsp; DMU &nbsp;</th>'
    )
    for f in fds_MapUnits:
        summary.write("<th>" + f[0] + "</th>")
    summary.write("</tr>\n")
    # open search cursor on DMU sorted by HKey
    sql = (None, "ORDER BY HierarchyKey")
    with arcpy.da.SearchCursor(
        "DescriptionOfMapUnits", ("MapUnit", "HierarchyKey"), None, None, False, sql
    ) as cursor:
        for row in cursor:
            mu = row[0]
            if notEmpty(mu):
                summary.write(
                    "<tr><td>" + mu + "</td><td>X</td>"
                )  #  2nd cell: value is, by definition, in DMU
                for f in fds_MapUnits:
                    if mu in f[1]:
                        summary.write("<td>X</td>")
                    else:
                        summary.write("<td>---</td>")
                summary.write("</tr>\n")
    # for mapunits not in DMU
    for aline in missingDmuMapUnits[1:]:
        mu = aline.split(",")[0]
        summary.write("<tr><td>" + str(mu) + "</td><td>---</td>")
        for f in fds_MapUnits:
            if mu in f[1]:
                summary.write("<td>X</td>")
            else:
                summary.write("<td>---</td>")
        summary.write("</tr>\n")
    summary.write("</table>\n")
    summary.write(divend)

    ###CONTENTS OF NONSPATIAL TABLES
    addMsgAndPrint("  dumping contents of nonspatial tables")
    summary.write(
        '<h3><a name="Contents_Nonspatial"></a>Contents of Nonspatial Tables</h3>\n'
    )
    for tb in tables:
        if tb != "GeoMaterialDict":
            summary.write(rdiv)
            summary.write('<h4><a name="' + tb + '"></a>' + tb + "</h4>\n")
            tableToHtml(tb, summary)
            summary.write(divend)

    ###DATABASE INVENTORY
    addMsgAndPrint("  writing database inventory")
    summary.write('<h3><a name="Database_Inventory"></a>Database Inventory</h3>\n')
    summary.write(rdiv)
    summary.write(
        "<i>This summary of database content is provided as a convenience to GIS analysts, reviewers, and others. It is not part of the GeMS compliance criteria.</i><br><br>\n"
    )
    for tb in tables:
        summary.write(
            tb + ", nonspatial table, " + str(numberOfRows(tb)) + " rows<br>\n"
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
                + str(numberOfRows(fc))
                + " rows<br>\n"
            )
        arcpy.env.workspace = inGdb
    summary.write(divend)


### Compact DB option
if compactDB == "true":
    addMsgAndPrint("  Compacting " + os.path.basename(inGdb))
    arcpy.Compact_management(inGdb)
else:
    pass

summary.close()
errors.close()
addMsgAndPrint("DONE")

"""
To be done:

    eliminate hard-coded path to refgmd (GeoMaterialDict as shipped with GeMS tool kit)

    Also:
      Maybe check for incorrectly-set up relationship classes?
"""
