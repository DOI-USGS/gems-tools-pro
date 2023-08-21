# Script to step through an identified subset of feature classes in GeologicMap feature dataset
# and, for specified values of independent fields, calculate values of dependent fields.
# Useful for translating Alacarte-derived data into NCGMP09 format, and for using NCGMP09
# to digitize data in Alacarte mode.
#
# Edited 30 May 2019 by Evan Thoms:
#   Updated to work with Python 3 in ArcGIS Pro2
#   Ran script through 2to3 to fix minor syntax issues
#   Manually edited the rest to make string building for messages
#   and whereClauses more pythonic
#   Added better handling of boolean to determine overwriting or not of existing values

usage = """
Usage: GeMS_AttributeByKeyValues.py <geodatabase> <file.txt> <force calculation>
  <geodatabase> is an NCGMP09-style geodatabase--with mapdata in feature
     dataset GeologicMap
  <file.txt> is a formatted text file that specifies feature classes,
     field names, values of independent fields, and values of dependent fields.
     See Dig24K_KeyValues.txt for an example and format instructions.
  <force calculation> boolean (True/False with or without quotes) that will 
     determine if existing values may be overwritten (True) or only null, 0, orgot
     otherwise empty values will be calculated (False)
     """
import arcpy, sys
from GeMS_utilityFunctions import *

versionString = "GeMS_AttributeByKeyValues.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_AttributeByKeyValues.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

separator = "|"


def makeFieldTypeDict(fds, fc):
    fdict = {}
    fields = arcpy.ListFields(fds + "/" + fc)
    for fld in fields:
        fdict[fld.name] = fld.type
    return fdict


addMsgAndPrint("  " + versionString)
if len(sys.argv) != 4:
    addMsgAndPrint(usage)
    sys.exit()

gdb = sys.argv[1]
keylines1 = open(sys.argv[2], "r").readlines()
if sys.argv[3].lower() == "true":
    forceCalc = True
else:
    forceCalc = False

# print(forceCalc)
# raise SystemError

if forceCalc:
    addMsgAndPrint("Forcing the overwriting of existing values")

arcpy.env.workspace = gdb
arcpy.env.workspace = "GeologicMap"
featureClasses = arcpy.ListFeatureClasses()
arcpy.env.workspace = gdb

# remove empty lines from keylines1
keylines = []
for lin in keylines1:
    lin = lin.strip()
    if len(lin) > 1 and lin[0:1] != "#":
        keylines.append(lin)

countPerLines = []
for line in keylines:
    countPerLines.append(len(line.split(separator)))

n = 0
while n < len(keylines):
    terms = keylines[n].split(separator)  # remove newline and split on commas
    if len(terms) == 1:
        fClass = terms[0]
        if fClass in featureClasses:
            mFieldTypeDict = makeFieldTypeDict("GeologicMap", fClass)
            n = n + 1
            mFields = keylines[n].split(separator)
            for i in range(len(mFields)):
                mFields[i] = mFields[
                    i
                ].strip()  # remove leading and trailing whitespace
                numMFields = len(mFields)
            addMsgAndPrint("  {}".format(fClass))
        else:
            if len(fClass) > 0:  # catch trailing empty lines
                addMsgAndPrint("  {} not in {}/GeologicMap".format(fClass, gdb))
                while (
                    countPerLines[n + 1] > 1
                ):  # This advances the loop till the number of items in the terms list is again one
                    # , which is when the next feature class is considered
                    # arcpy.AddMessage("loop count = " + str(n))
                    if n < len(countPerLines) - 2:
                        # arcpy.AddMessage("count per line = " + str(countPerLines[n]))
                        n = n + 1
                    elif n == len(countPerLines) - 2:
                        n = len(countPerLines)
                        break
                    else:
                        arcpy.warnings("Unexpected condition met")

    else:  # must be a key-value: dependent values line
        vals = keylines[n].split(separator)
        if len(vals) != numMFields:
            addMsgAndPrint(
                "\nline:\n  {}\nhas wrong number of values. Exiting.".format(
                    keylines[n]
                )
            )
            sys.exit()
        for i in range(len(vals)):  # strip out quotes
            vals[i] = vals[i].replace("'", "")
            vals[i] = vals[i].replace('"', "")
            # remove leading and trailing whitespace
            vals[i] = vals[i].strip()
        # iterate through mFields 0--len(mFields)
        #  if i == 0, make table view, else resel rows with NULL values for attrib[i] and calc values
        arcpy.env.overwriteOutput = True  # so we can reuse table tempT
        for i in range(len(mFields)):
            if i == 0:  # select rows with specified independent value
                whereClause = "{} = '{}'".format(
                    arcpy.AddFieldDelimiters(fClass, mFields[i]), vals[0]
                )
                arcpy.MakeTableView_management(
                    "GeologicMap/{}".format(fClass), "tempT", whereClause
                )
                nSel = int(
                    str(arcpy.GetCount_management("tempT"))
                )  # convert from Result object to integer
                if nSel == -1:
                    addMsgAndPrint(
                        "    appears to be no value named: {} in: {}".format(
                            vals[0], mFields[0]
                        )
                    )
                else:
                    addMsgAndPrint(
                        "    selected {} = {}, n = {}".format(
                            mFields[0], vals[0], str(nSel)
                        )
                    )
            else:  # reselect rows where dependent values are NULL and assign new value
                if forceCalc:
                    if nSel > 0:
                        if mFieldTypeDict[mFields[i]] == "String":
                            arcpy.CalculateField_management(
                                "tempT", mFields[i], '"{}"'.format(str(vals[i]))
                            )
                        elif mFieldTypeDict[mFields[i]] in [
                            "Double",
                            "Single",
                            "Integer",
                            "SmallInteger",
                        ]:
                            arcpy.CalculateField_management(
                                "tempT", mFields[i], vals[i]
                            )
                        addMsgAndPrint(
                            "        calculated {} = {}".format(
                                mFields[i], str(vals[i])
                            )
                        )
                elif nSel > 0:
                    addMsgAndPrint("Calculating only NULL fields")
                    whereClause = "{} IS NULL".format(
                        arcpy.AddFieldDelimiters(fClass, mFields[i])
                    )
                    if mFieldTypeDict[mFields[i]] == "String":
                        whereClause = "{0} OR {1} = '' OR {1} = ' '".format(
                            whereClause, mFields[i]
                        )
                    elif mFieldTypeDict[mFields[i]] in [
                        "Double",
                        "Single",
                        "Integer",
                        "SmallInteger",
                    ]:
                        whereClause = "{} OR {} = 0".format(whereClause, mFields[i])
                    arcpy.SelectLayerByAttribute_management(
                        "tempT", "NEW_SELECTION", whereClause
                    )
                    nResel = int(
                        str(arcpy.GetCount_management("tempT"))
                    )  # convert result object to int
                    addMsgAndPrint(
                        "      reselected {} = NULL, blank, or 0, n = {}".format(
                            mFields[i], (nResel)
                        )
                    )
                    if nResel > 0:
                        if mFieldTypeDict[mFields[i]] == "String":
                            arcpy.CalculateField_management(
                                "tempT", mFields[i], '"{}"'.format(str(vals[i]))
                            )
                        elif mFieldTypeDict[mFields[i]] in [
                            "Double",
                            "Single",
                            "Integer",
                            "SmallInteger",
                        ]:
                            arcpy.CalculateField_management(
                                "tempT", mFields[i], vals[i]
                            )
                        addMsgAndPrint(
                            "        calculated {} = {}".format(
                                mFields[i], str(vals[i])
                            )
                        )
    n = n + 1
