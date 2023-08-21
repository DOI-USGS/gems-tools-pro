# sets PlotAtScale values for a point eature class

# September 2017: now invokes edit session before setting values (line 135)

# June 2019: updated to work with Python 3 in ArcGIS Pro.
# Ran script through 2to3. Only incidental debugging required after.
# November 2021: reordered linew 9-14

import arcpy, os.path, sys
from GeMS_utilityFunctions import *

versionString = "GeMS_SetPlotAtScales.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_SetPlotAtScales.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

# global dictionaries
OPTypeDict = {}
OPLCMDict = {}
OPOCDDict = {}

#############################


def plotScale(separation, minSeparationMapUnits):
    return int(round(separation / minSeparationMapUnits))


def makeDictsOP(inFc):
    fields = [
        "OBJECTID",
        "Type",
        "LocationConfidenceMeters",
        "OrientationConfidenceDegrees",
    ]
    with arcpy.da.SearchCursor(inFc, fields) as cursor:
        for row in cursor:
            OPTypeDict[row[0]] = row[1]
            OPLCMDict[row[0]] = row[2]
            OPOCDDict[row[0]] = row[3]


def lessSignificantOP(fid1, fid2):
    if OPTypeDict[fid1] != OPTypeDict[fid2]:
        # if one is overturned or upright and other is not
        if (
            "upright" in OPTypeDict[fid1].lower()
            or "overturned" in OPTypeDict[fid1].lower()
        ) and not (
            "upright" in OPTypeDict[fid2].lower()
            or "overturned" in OPTypeDict[fid2].lower()
        ):
            return fid2
        elif (
            "upright" in OPTypeDict[fid2].lower()
            or "overturned" in OPTypeDict[fid2].lower()
        ) and not (
            "upright" in OPTypeDict[fid1].lower()
            or "overturned" in OPTypeDict[fid1].lower()
        ):
            return fid1
        # if one is bedding and one is not
        elif (
            "bedding" in OPTypeDict[fid1].lower()
            and not "bedding" in OPTypeDict[fid2].lower()
        ):
            return fid2
        elif (
            "bedding" in OPTypeDict[fid2].lower()
            and not "bedding" in OPTypeDict[fid1].lower()
        ):
            return fid1
    else:
        # if one has better OrientationConfidenceDegrees
        if OPOCDDict[fid1] < OPOCDDict[fid2]:
            return fid2
        elif OPOCDDict[fid2] < OPOCDDict[fid1]:
            return fid1
        else:
            return fid1


##############################
# args
#   inFc = featureClass
#   minSeparation (in mm on map)
#   maxPlotAtScale  = 500000

inFc = sys.argv[1]
minSeparation_mm = float(sys.argv[2])
maxPlotAtScale = float(sys.argv[3])

addMsgAndPrint(versionString)

# test for valid input:
# inFc exists and has item PlotAtScale
if not arcpy.Exists(inFc):
    forceExit()
fields = arcpy.ListFields(inFc)
fieldNames = []
for field in fields:
    fieldNames.append(field.name)
if not "PlotAtScale" in fieldNames:
    arcpy.AddField_management(inFc, "PlotAtScale", "FLOAT")
    addMsgAndPrint("Adding field PlotAtScale to {}".format(inFc))

gdb = os.path.dirname(inFc)
if arcpy.Describe(gdb).dataType == "FeatureDataset":
    gdb = os.path.dirname(gdb)

if os.path.basename(inFc) == "OrientationPoints":
    addMsgAndPrint("Populating OrientationPointsDicts")
    makeDictsOP(inFc)
    isOP = True
else:
    isOP = False

outTable = gdb + "/xxxPlotAtScales"
testAndDelete(outTable)
mapUnits = "meters"
minSeparationMapUnits = minSeparation_mm / 1000.0
searchRadius = minSeparationMapUnits * maxPlotAtScale
if not "meter" in arcpy.Describe(inFc).spatialReference.linearUnitName.lower():
    # units are feet of some flavor
    mapUnits = "feet"
    searchRadius = searchRadius * 3.2808
    minSeparationMapUnits = minSeparationMapUnits * 3.2808
addMsgAndPrint("Search radius is " + str(searchRadius) + " " + mapUnits)
addMsgAndPrint("Building near table")
arcpy.PointDistance_analysis(inFc, inFc, outTable, searchRadius)

inPoints = []
outPointDict = {}

# read outTable into Python list inPoints, with each list component = [distance, fid1, fid2]
fields = ["DISTANCE", "INPUT_FID", "NEAR_FID"]
with arcpy.da.SearchCursor(outTable, fields) as cursor:
    for row in cursor:
        inPoints.append([row[0], row[1], row[2]])
addMsgAndPrint("   " + str(len(inPoints)) + " rows in initial near table")

# step through inPoints, smallest distance first, and write list of FID, PlotAtScale (outPoints)
addMsgAndPrint("   Sorting through near table and calculating PlotAtScale values")
inPoints.sort()
lastLenInPoints = 0
while len(inPoints) > 1 and lastLenInPoints != len(inPoints):
    lastLenInPoints = len(inPoints)
    pointSep = inPoints[0][0]
    if isOP:  # figure out the most significant point
        pt = lessSignificantOP(inPoints[0][1], inPoints[0][2])
    else:  # take the second point
        pt = inPoints[0][2]
    outPointDict[pt] = plotScale(pointSep, minSeparationMapUnits)
    inPoints.remove(inPoints[0])
    j = len(inPoints)
    for i in range(1, j + 1):
        # addMsgAndPrint(str(i)+', '+str(j))
        aPt = inPoints[j - i]
        if aPt[1] == pt or aPt[2] == pt:
            inPoints.remove(aPt)
            # addMsgAndPrint( 'removing '+str(aPt))
    addMsgAndPrint("   # inPoints = " + str(len(inPoints)))

for i in range(0, len(inPoints)):
    addMsgAndPrint("      " + str(inPoints[i]))


# attach plotScale values from outPoints to inFc
addMsgAndPrint("Updating " + os.path.basename(inFc))
with arcpy.da.Editor(gdb) as edit:
    fields = ["OBJECTID", "PlotAtScale"]
    with arcpy.da.UpdateCursor(inFc, fields) as cursor:
        for row in cursor:
            if row[0] in list(outPointDict.keys()):
                row[1] = outPointDict[row[0]]
            else:
                row[1] = maxPlotAtScale
            cursor.updateRow(row)

# get rid of xxxPlotAtScales
addMsgAndPrint("Deleting " + outTable)
testAndDelete(outTable)
