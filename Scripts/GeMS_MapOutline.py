# MapOutline.py
#   generates rectangular (in lat-long) map outline and
#   appropriate tics in projection of user's choosing. Result is
#   stored in an existing geodatabase
#
#   For complex map outlines, try several runs and intersect the results.
#
# Ralph Haugerud, U.S. Geological Survey
#   rhaugerud@usgs.gov
#
# July 23, 2019: updated to work with Python 3 in ArcGIS Pro 2
#  Only had to make some syntax edits.
#  Renamed from mapOutline_Arc10.py to mapOutline_AGP2.py
#  Evan Thoms

import arcpy, sys, os
from GeMS_utilityFunctions import *

versionString = "GeMS_MapOutline.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/usgs/gems-tools-pro/master/Scripts/GeMS_MapOutline.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

"""
INPUTS
maxLongStr  # in D M S, separated by spaces. Decimals OK.
            #   Note that west values must be negative
            #   -122.625 = -122 37 30
            #   if value contains spaces it should be quoted
minLatStr   # DITTO
dLong       # in decimal degrees OR decimal minutes
            #   values <= 5 are assumed to be degrees
            #   values  > 5 are assumed to be minutes
dLat        # DITTO
            # default values of dLong and dLat are 7.5
ticInterval # in decimal minutes! Default value is 2.5
isNAD27     # NAD27 or NAD83 for lat-long locations
outgdb      # existing geodatabase to host output feature classes
outSpRef    # output spatial reference system
scratch     # scratch folder, must be writable
"""

c = ","
degreeSymbol = "°"
minuteSymbol = "'"
secondSymbol = '"'


def addMsgAndPrint(msg, severity=0):
    # prints msg to screen and adds msg to the geoprocessor (in case this is run as a tool)
    # print msg
    try:
        for string in msg.split("\n"):
            # Add appropriate geoprocessing message
            if severity == 0:
                arcpy.AddMessage(string)
            elif severity == 1:
                arcpy.AddWarning(string)
            elif severity == 2:
                arcpy.AddError(string)
    except:
        pass


def dmsStringToDD(dmsString):
    dms = dmsString.split()
    dd = abs(float(dms[0]))
    if len(dms) > 1:
        dd = dd + float(dms[1]) / 60.0
    if len(dms) > 2:
        dd = dd + float(dms[2]) / 3600.0
    if dms[0][0] == "-":
        dd = 0 - dd
    return dd


def ddToDmsString(dd):
    dd = abs(dd)
    degrees = int(dd)
    minutes = int((dd - degrees) * 60)
    seconds = int(round((dd - degrees - (minutes / 60.0)) * 3600))
    if seconds == 60:
        minutes = minutes + 1
        seconds = 0
    dmsString = str(degrees) + degreeSymbol
    dmsString = dmsString + str(minutes) + minuteSymbol
    if seconds != 0:
        dmsString = dmsString + str(seconds) + secondSymbol
    return dmsString


addMsgAndPrint(versionString)

## MAP BOUNDARY
# get and check inputs
SELongStr = sys.argv[1]
SELatStr = sys.argv[2]
dLong = float(sys.argv[3])
dLat = float(sys.argv[4])
ticInterval = float(sys.argv[5])
if sys.argv[6] == "true":
    isNAD27 = True
else:
    isNAD27 = False

if isNAD27:
    xycs = 'GEOGCS["GCS_North_American_1927",DATUM["D_North_American_1927",SPHEROID["Clarke_1866",6378206.4,294.9786982]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433],AUTHORITY["EPSG",4267]]'
else:
    xycs = 'GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433],AUTHORITY["EPSG",4269]]'

outgdb = sys.argv[7]
outSpRef = sys.argv[8]
scratch = sys.argv[9]

# set workspace
arcpy.env.workspace = outgdb
arcpy.env.scratchWorkspace = scratch

# calculate maxLong and minLat, dLat, dLong, minLong, maxLat
maxLong = dmsStringToDD(SELongStr)
minLat = dmsStringToDD(SELatStr)
if dLong > 5:
    dLong = dLong / 60.0
if dLat > 5:
    dLat = dLat / 60.0
minLong = maxLong - dLong
maxLat = minLat + dLat

# test for and delete any feature classes to be created
for xx in ["xxMapOutline", "MapOutline", "xxTics", "Tics"]:
    if arcpy.Exists(xx):
        arcpy.Delete_management(xx)
        addMsgAndPrint("  deleted feature class {}".format(xx))

## MAP OUTLINE
# make XY file for map outline
addMsgAndPrint("  writing map outline file")
genf = open(os.path.join(scratch, "xxxbox.csv"), "w")
genf.write("LONGITUDE,LATITUDE\n")
genf.write("{},{}\n".format(str(minLong), str(maxLat)))
genf.write("{},{}\n".format(str(maxLong), str(maxLat)))
genf.write("{},{}\n".format(str(maxLong), str(minLat)))
genf.write("{},{}\n".format(str(minLong), str(minLat)))
genf.write("{},{}\n".format(str(minLong), str(maxLat)))
genf.close()

# convert XY file to .dbf table
boxdbf = arcpy.CreateScratchName("xxx", ".dbf", "", scratch)
boxdbf = os.path.basename(boxdbf)
arcpy.TableToTable_conversion(os.path.join(scratch, "xxxbox.csv"), scratch, boxdbf)

# make XY event layer from .dbf table
arcpy.MakeXYEventLayer_management(
    os.path.join(scratch, boxdbf), "LONGITUDE", "LATITUDE", "boxlayer", xycs
)

# convert event layer to preliminary line feature class with PointsToLine_management
arcpy.PointsToLine_management("boxlayer", "xxMapOutline")

# densify MapOutline
arcpy.Densify_edit("xxMapOutline", "DISTANCE", 0.0001)

# project to correct spatial reference
### THIS ASSUMES THAT OUTPUT COORDINATE SYSTEM IS HARN AND WE ARE IN OREGON OR WASHINGTON!!
if isNAD27:
    geotransformation = "NAD_1927_To_NAD_1983_NADCON;NAD_1983_To_HARN_OR_WA"
else:
    geotransformation = "NAD_1983_To_HARN_OR_WA"

geotransformation = ""

arcpy.Project_management(
    "xxMapOutline", "MapOutline", outSpRef, geotransformation, xycs
)

## TICS
# calculate minTicLong, minTicLat, maxTicLong, maxTiclat
ticInterval = ticInterval / 60.0  # convert minutes to degrees
minTicLong = int(round(0.1 + minLong // ticInterval))
maxTicLong = int(round(1.1 + maxLong // ticInterval))
minTicLat = int(round(0.1 + minLat // ticInterval))
maxTicLat = int(round(1.1 + maxLat // ticInterval))
if minTicLong < 0:
    minTicLong = minTicLong + 1
if maxTicLong < 0:
    maxTicLong = maxTicLong + 1

# make xy file for tics
addMsgAndPrint("  writing tic file")
genf = open(os.path.join(scratch, "xxxtics.csv"), "w")
genf.write("ID,LONGITUDE,LATITUDE\n")
nTic = 1
for y in range(minTicLat, maxTicLat):
    ticLat = y * ticInterval
    for x in range(minTicLong, maxTicLong):
        ticLong = x * ticInterval
        genf.write(str(nTic) + c + str(ticLong) + c + str(ticLat) + "\n")
        nTic = nTic + 1
genf.close()

# convert to dbf
ticdbf = arcpy.CreateScratchName("xxx", ".dbf", "", scratch)
print(ticdbf)
ticdbf = os.path.basename(ticdbf)
print(ticdbf)
arcpy.TableToTable_conversion(os.path.join(scratch, "xxxtics.csv"), scratch, ticdbf)

# make XY event layer from table
arcpy.MakeXYEventLayer_management(
    os.path.join(scratch, ticdbf), "LONGITUDE", "LATITUDE", "ticlayer", xycs
)

# copy to point featureclass
arcpy.FeatureToPoint_management("ticlayer", "xxtics")

# project to correct coordinate system
arcpy.Project_management("xxtics", "tics", outSpRef, geotransformation, xycs)

# add attributes
for fld in ["Easting", "Northing"]:
    arcpy.AddField_management("tics", fld, "DOUBLE")
for fld in ["LatDMS", "LongDMS"]:
    arcpy.AddField_management("tics", fld, "TEXT", "", "", 20)
arcpy.AddXY_management("tics")

# calc Easting = Point_X, Northing = Point_Y
arcpy.CalculateField_management("tics", "Easting", "!Point_X!", "PYTHON")
arcpy.CalculateField_management("tics", "Northing", "!Point_Y!", "PYTHON")

# create update cursor, cycle through tics, and add LatDMS and LongDMS
addMsgAndPrint("  adding lat-long text strings")
rows = arcpy.UpdateCursor("tics")
for row in rows:
    row.LatDMS = ddToDmsString(row.LATITUDE)
    row.LongDMS = ddToDmsString(row.LONGITUDE)
    rows.updateRow(row)
del row
del rows

# delete csv files, dbf files, and preliminary featureclasses
addMsgAndPrint("  cleaning up scratch workspace")
for xx in [
    boxdbf,
    boxdbf + ".xml",
    ticdbf,
    ticdbf + ".xml",
]:  # ,'xxxbox.csv','xxxtics.csv']:
    os.remove(os.path.join(scratch, xx))
addMsgAndPrint("  deleting temporary feature classes")
arcpy.Delete_management("xxtics")
arcpy.Delete_management("xxMapOutline")

# sys.exit()   # force exit with failure
