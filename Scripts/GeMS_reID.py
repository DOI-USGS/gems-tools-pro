# script to re-assign ID numbers to an NCGMP09-stype geodatabase
# Ralph Haugerud, USGS, Seattle WA, rhaugerud@usgs.gov
#

import arcpy, sys, time, os.path, math, uuid
from string import whitespace
from GeMS_utilityFunctions import *

versionString = "GeMS_reID.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_reID.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

# modified to not work on a copy of the input database. Backup first!
# 15 Sept 2016: modified to, by default, not reset DataSource_ID values
# 26 April 2018: extended idRootDict to cover all classes defined in GeMS_Definion.py
#   with thanks to freewheelCarto!
# 16 May 2019: updated to Python 3 by using bundled auto conversion script 2to3. No other edits.
#   tested against a GeMS gdb and it ran with no errors although I did not check the output - Evan Thoms
# 10 February 2020: Added MapUnitPolys to idRootDict and changed abbreviation for MapUnitPoints from
#   MUP to MPT! With this table missing, a user reported that MUP_IDs were being written with the
#   prefix 'X3X'. I think it's absence is the reason for line "if tableName == 'MapUnitPoints'"
#   around line 215.  - Evan Thoms

idRootDict = {
    "CartographicLines": "CAL",
    "ContactsAndFaults": "CAF",
    "CMULines": "CMULIN",
    "CMUMapUnitPolys": "CMUMUP",
    "CMUPoints": "CMUPNT",
    "CMUText": "CMUTXT",
    "DataSources": "DAS",
    "DataSourcePolys": "DSP",
    "DescriptionOfMapUnits": "DMU",
    "ExtendedAttributes": "EXA",
    "FossilPoints": "FSP",
    "GenericPoints": "GNP",
    "GenericSamples": "GNS",
    "GeochemPoints": "GCM",
    "GeochronPoints": "GCR",
    "GeologicEvents": "GEE",
    "GeologicLines": "GEL",
    "Glossary": "GLO",
    "IsoValueLines": "IVL",
    "MapUnitPoints": "MPT",
    "MapUnitPolys": "MUP",
    "MapUnitOverlayPolys": "MUO",
    "MiscellaneousMapInformation": "MMI",
    "OrientationPoints": "ORP",
    "OtherLines": "OTL",
    "OverlayPolys": "OVP",
    "PhotoPoints": "PHP",
    "RepurposedSymbols": "RPS",
    "Stations": "STA",
    "StandardLithology": "STL",
    "MapUnitPointAnno24k": "ANO",
}

idDict = {}
fctbs = []  # feature class and table inventory
exemptedPrefixes = (
    "errors_",
    "ed_",
)  # prefixes that flag a feature class as not permanent data


def usage():
    print(
        """
    Usage:  prompt> ncgmp09_reID.py <inGeodatabaseName> <outGeodatabaseName>
                  <UseGUID>
  
    <inGeodatabaseName> can be either a personal geodatabase or a file 
    geodatabase, .mdb or .gdb. The filename extension must be included.
    <outGeodatabaseName> must be of the same type and must not exist.

    ncgmp09_reID.py re-casts all ID values into form XXXnnnn. ID values 
    that are not primary keys within the database are left unaltered and 
    a record is written to file <outputGeodatabaseName>.txt.

    If <useGUID> (boolean) is True, GUIDs are created for ID values.
    Otherwise ID values are short character strings that identify tables
        (e.g., MUP for MapUnitPolys) followed by consecutive zero-padded
        integers.
"""
    )


def doReID(fc):
    doReID = True
    for exPfx in exemptedPrefixes:
        if fc.find(exPfx) == 0:
            doReID = False
    return doReID


def elapsedTime(lastTime):
    thisTime = time.time()
    addMsgAndPrint("    %.1f sec" % (thisTime - lastTime))
    return thisTime


def idRoot(tb, rootCounter):
    if tb in idRootDict:
        return idRootDict[tb], rootCounter
    else:
        rootCounter = rootCounter + 1
        return "X" + str(rootCounter) + "X", rootCounter


def getPFKeys(table):
    addMsgAndPrint(table)
    fields2 = arcpy.ListFields(table)
    fKeys = []
    pKey = ""
    for field in fields2:
        ### this assumes only 1 _ID field!
        if field.name == table + "_ID":
            pKey = field.name
        else:
            if field.name.find("ID") > 0 and field.type == "String":
                fKeys.append(field.name)
    addMsgAndPrint("  pKey: " + pKey)
    addMsgAndPrint("  fKeys: " + str(fKeys))
    return pKey, fKeys


def inventoryDatabase(dbf, noSources):
    arcpy.env.workspace = dbf
    tables = arcpy.ListTables()
    if noSources:  # then don't touch DataSource_ID values
        for tb in tables:
            if tb == "DataSources":
                tables.remove(tb)
                addMsgAndPrint("    skipping DataSources")
    for table in tables:
        addMsgAndPrint(" Table: " + table)
        pKey, fKeys = getPFKeys(table)
        fctbs.append([dbf, "", table, pKey, fKeys])
    fdsets = arcpy.ListDatasets()
    for fdset in fdsets:
        arcpy.env.workspace = dbf + "/" + fdset
        fcs = arcpy.ListFeatureClasses()
        for fc in fcs:
            addMsgAndPrint(" FC: " + fc)
            if doReID(fc):  # Does a check for exempted prefixes
                pKey, fKeys = getPFKeys(fc)
                fctbs.append([dbf, fdset, fc, pKey, fKeys])


def buildIdDict(table, sortKey, keyRoot, pKey, lastTime, useGUIDs):
    addMsgAndPrint("  Setting new _IDs for " + table)
    result = arcpy.GetCount_management(table)
    nrows = int(result.getOutput(0))
    width = int(math.ceil(math.log10(nrows + 1)))
    arcpy.env.workspace = dbf
    edit = arcpy.da.Editor(arcpy.env.workspace)
    edit.startEditing(False, True)
    edit.startOperation()
    rows = arcpy.UpdateCursor(table, "", "", "", sortKey)
    n = 1
    for row in rows:
        oldID = row.getValue(pKey)
        # calculate newID
        if useGUIDs:
            newID = str(uuid.uuid4())
        else:
            newID = keyRoot + str(n).zfill(width)
        try:
            row.setValue(pKey, newID)
            rows.updateRow(row)
        except:
            print("ERROR")
            print("pKey = " + str(pKey) + "  newID = " + str(newID))
        n = n + 1
        # print oldID, newID
        # add oldID,newID to idDict
        if oldID != "" and oldID != None:
            idDict[oldID] = newID
    edit.stopOperation()
    edit.stopEditing(True)
    return elapsedTime(lastTime)


def reID(table, keyFields, lastTime, outfile):
    addMsgAndPrint("  resetting IDs for " + table)
    arcpy.env.workspace = dbf
    edit = arcpy.da.Editor(arcpy.env.workspace)
    edit.startEditing(False, True)
    edit.startOperation()
    rows = arcpy.UpdateCursor(table)
    n = 1
    row = next(rows)
    while row:
        for field in keyFields:
            oldValue = row.getValue(field)
            if oldValue in idDict:
                row.setValue(field, idDict[oldValue])
            else:
                outfile.write(table + " " + field + " " + str(oldValue) + "\n")
        rows.updateRow(row)
        n = n + 1
        row = next(rows)
    edit.stopOperation()
    edit.stopEditing(True)
    return elapsedTime(lastTime)


def main(lastTime, dbf, useGUIDs, noSources):
    rootCounter = 0
    addMsgAndPrint("Inventorying database")
    inventoryDatabase(dbf, noSources)
    addMsgAndPrint("Inventory done...")
    addMsgAndPrint("--------------------------")
    # lastTime = elapsedTime(lastTime)
    arcpy.env.workspace = dbf
    addMsgAndPrint("Cycling through inventory")
    addMsgAndPrint(str(fctbs))
    for fctb in fctbs:
        addMsgAndPrint(fctb)
        # in previous script, with Python 2.7, fctb[0]+fctb[1] was (somehow) sufficient for defining
        # workspace. With Python 3, it fails. Feature classes within feature datasets cannot be found.
        # set workspace using os.path.join and, better yet, re-write inventoryDatabase to use arcpy.da.walk and full # paths to tables
        # stop depending on setting the workspace correctly and try to always point to a table with a full path
        arcpy.env.workspace = os.path.join(fctb[0], fctb[1])
        arcpy.AddMessage(arcpy.env.workspace)
        tabName = tableName = fctb[2]
        pKey, fKeys = getPFKeys(
            tableName
        )  # Why does this have to be called again (already in inventorDatadase)
        # TODO figure out the intention behind the next two line more - creates an error for me
        # if tableName == 'MapUnitPoints':
        #     pKey = 'MapUnitPolys_ID'
        fields = arcpy.ListFields(tableName)
        fieldNames = [x.name for x in fields]
        if "OBJECTID" in fieldNames:
            case = "UPPER"
        elif "objectid" in fieldNames:
            case = "LOWER"
        if tableName == "Glossary":
            sortKey = "Term A"
        elif tableName == "DescriptionOfMapUnits":
            sortKey = "HierarchyKey A"
        elif tableName == "StandardLithology":
            sortKey = "MapUnit A"
        elif case == "UPPER":
            sortKey = "OBJECTID A"
        elif case == "LOWER":
            sortKey = "objectid A"
        else:
            addMsgAndPrint("Warning: OBJECTID field not present")
        # deal with naming of CrossSection tables as CSxxTableName
        if fctb[1].find("CrossSection") == 0:
            csSuffix = fctb[1][12:]
            tabName = tableName[2 + len(csSuffix) :]
        idRt, rootCounter = idRoot(tabName, rootCounter)
        if tabName != tableName:
            prefix = "CS" + csSuffix + idRt
        else:
            prefix = idRt
        if pKey != "":
            if sortKey[:-2] in fieldNameList(tableName):
                lastTime = buildIdDict(
                    tableName, sortKey, prefix, pKey, lastTime, useGUIDs
                )
            else:
                addMsgAndPrint("Skipping " + tableName + ", no field " + sortKey[:-2])

    # purge IdDict of quasi-null keys
    addMsgAndPrint("Purging idDict of quasi-null keys")
    idKeys = list(idDict.keys())
    for key in idKeys:
        if len(key.split()) == 0:
            print("NullKey", len(key))
            del idDict[key]

    outfile = open(dbf + ".txt", "w")
    outfile.write(
        "Database "
        + dbf
        + ". \nList of ID values that do not correspond to any primary key in the database\n"
    )
    outfile.write("--table---field----field value---\n")
    for fctb in fctbs:
        arcpy.env.workspace = fctb[0] + fctb[1]
        keyFields = fctb[4]
        # keyFields.append(fctb[3])
        if (
            fctb[3] != ""
        ):  # primary key is identified as '' (i.e., doesn't exist, so not an NCGMP09 feature class)
            lastTime = reID(fctb[2], keyFields, lastTime, outfile)
    outfile.close()
    return lastTime


### START HERE ###

startTime = time.time()
lastTime = time.time()
useGUIDs = False
addMsgAndPrint(versionString)

if not os.path.exists(sys.argv[1]):
    usage()
else:
    # lastTime = elapsedTime(lastTime)
    if len(sys.argv) >= 3:
        if sys.argv[2].upper() == "TRUE":
            useGUIDs = True
        else:
            useGUIDs = False
    if len(sys.argv) >= 4:
        if sys.argv[3].upper() == "TRUE":
            noSources = True
        else:
            noSources = False

    dbf = os.path.abspath(sys.argv[1])
    arcpy.env.workspace = ""
    # lastTime = elapsedTime(lastTime)
    lastTime = main(lastTime, dbf, useGUIDs, noSources)
    lastTime = elapsedTime(startTime)
