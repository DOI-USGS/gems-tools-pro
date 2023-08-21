# GeMS_InclinationNumbers_AGP2.py
# Creates a point feature class called OrientationPointLabels with dip and plunge
# number labels for appropriate features within OrientationPoints. The location
# of the label is offset based on characteristics of the rotated symbol and the map scale.

# Adds the new annotation feature class to your map composition.

# If this script fails because of locking issues, try (a) Stop Editing, or (b)
# save any edits and save the map composition, exit ArcMap, and restart ArcMap.
# Maybe this script will then run satisfactorily.

# Create 17 October 2017 by Ralph Haugerud
# Edits 21 May 2019 by Evan Thoms:
#   Upgraded to work with Python 3 and ArcGIS Pro 2
#   Ran script through 2to3 to find and fix simple syntactical differences
#   Manually debugged remaining issues mostly to do with to with methods
#   which are no longer available in arcpy.

import arcpy, os.path, sys, math, shutil
from GeMS_utilityFunctions import *

versionString = "GeMS_InclinationNumbers.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_InclinationNumbers.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

debug1 = True
OPLName = "OrientationPointLabels"


#########Stuff for placing dip/plunge numbers########
def showInclination(oType):
    if "horizontal" in oType.lower() or "vertical" in oType.lower() or len(oType) < 2:
        return False
    else:
        return True


def insert_layer(lsource, new_lyr_file):
    if debug1:
        addMsgAndPrint("lsource = {}".format(lsource))
    p = arcpy.mp.ArcGISProject("CURRENT")
    mlist = p.listMaps()
    for m in mlist:
        lList = m.listLayers()
        for lyr in lList:
            # for some reason, you have to find out if the layer even allows you to
            # ask if it is a feature layer or not. Topology group layers don't support
            # isFeatureLayer
            if lyr.supports("isFeatureLayer"):
                if lyr.isFeatureLayer:
                    if debug1:
                        writeLayerNames(lyr)
                    if lyr.dataSource == lsource:
                        m.insertLayer(lyr, new_lyr_file, "BEFORE")


def writeLayerNames(lyr):
    if lyr.supports("name"):
        addMsgAndPrint("       name: {}".format(lyr.name))
    if lyr.supports("connectionProperties"):
        arcpy.AddMessage(lyr.connectionProperties)


##main routine from DipNumbers2.py
def dipNumbers(gdb, mapScaleDenominator):
    OPfc = os.path.join(gdb, "GeologicMap", "OrientationPoints")
    if not arcpy.Exists(OPfc):
        addMsgAndPrint(
            "  Geodatabase {} lacks feature class OrientationPoints.".format(
                os.path.basename(gdb)
            )
        )
        return

    desc = arcpy.Describe(OPfc)
    mapUnits = desc.spatialReference.linearUnitName
    if "meter" in mapUnits.lower():
        mapUnitsPerMM = float(mapScaleDenominator) / 1000.0
    else:
        mapUnitsPerMM = float(mapScaleDenominator) / 1000.0 * 3.2808

    if numberOfRows(OPfc) == 0:
        addMsgAndPrint("  0 rows in OrientationPoints.")
        return

    ## MAKE ORIENTATIONPOINTLABELS FEATURE CLASS
    arcpy.env.workspace = os.path.join(gdb, "GeologicMap")
    OPL = os.path.join(gdb, "GeologicMap", "OrientationPointLabels")
    if arcpy.TestSchemaLock(OPL) == False:
        addMsgAndPrint("    TestSchemaLock({}) = False.".format(OPLName))
        addMsgAndPrint("Cannot get a schema lock!")
        forceExit()

    testAndDelete(OPL)
    arcpy.CreateFeatureclass_management(fds, "OrientationPointLabels", "POINT")
    arcpy.AddField_management(OPL, "OrientationPointsID", "TEXT", "", "", 50)
    arcpy.AddField_management(OPL, "Inclination", "TEXT", "", "", 3)
    arcpy.AddField_management(OPL, "PlotAtScale", "FLOAT")

    ## ADD FEATURES FOR ROWS IN ORIENTATIONPOINTS WITHOUT 'HORIZONTAL' OR 'VERTICAL' IN THE TYPE VALUE
    OPfields = [
        "SHAPE@XY",
        "OrientationPoints_ID",
        "Type",
        "Azimuth",
        "Inclination",
        "PlotAtScale",
    ]
    attitudes = arcpy.da.SearchCursor(OPfc, OPfields)
    OPLfields = ["SHAPE@XY", "OrientationPointsID", "Inclination", "PlotAtScale"]
    inclinLabels = arcpy.da.InsertCursor(OPL, OPLfields)
    for row in attitudes:
        oType = row[2]
        if showInclination(oType):
            x = row[0][0]
            y = row[0][1]
            OP_ID = row[1]
            azi = row[3]
            inc = int(round(row[4]))
            paScale = row[5]
            if isPlanar(oType):
                geom = " S "
                inclinRadius = 2.4 * mapUnitsPerMM
                azir = math.radians(azi)
            else:  # assume linear
                geom = " L "
                inclinRadius = 7.4 * mapUnitsPerMM
                azir = math.radians(azi - 90)
            ix = x + math.cos(azir) * inclinRadius
            iy = y - math.sin(azir) * inclinRadius

            addMsgAndPrint(
                "    inserting " + oType + geom + str(int(round(azi))) + "/" + str(inc)
            )
            inclinLabels.insertRow(([ix, iy], OP_ID, inc, paScale))

    del inclinLabels
    del attitudes

    # INSTALL NEWLY-MADE FEATURE CLASS USING .LYR FILE. SET DATA SOURCE. SET DEFINITION QUERY

    # make a copy of OrientationPointsLabels.lyrx in \Resources. ArcGIS Pro cannot write to lyr files
    newLyr = os.path.join(os.path.dirname(gdb), "OrientationPointsLabels.lyrx")
    shutil.copy(lyrx_path, newLyr)

    # create a LayerFile object based on the copy in order to get a handle on the labels layer
    OPLyrFile = arcpy.mp.LayerFile(newLyr)
    # reset data source through the updateConnectionProperties method
    current_connect = OPLyrFile.listLayers()[0].connectionProperties
    current_workspace = current_connect["connection_info"]["database"]
    OPLyrFile.updateConnectionProperties(current_workspace, gdb)

    # find the layer in the layer file object
    OPLyr = OPLyrFile.listLayers()[0]
    # set definition query
    pasName = arcpy.AddFieldDelimiters(gdb, "PlotAtScale")
    defQuery = pasName + " >= " + str(mapScaleDenominator)
    OPLyr.definitionQuery = defQuery
    OPLyrFile.save()

    # Insert new OrientationPointLabels.lyr
    # try:
    OPfc = os.path.join(gdb, "GeologicMap", "OrientationPoints")
    insert_layer(OPfc, OPLyr)
    # except:
    # addMsgAndPrint('  Unable to insert OrientationPointLabels.lyr.')


#####################################################
addMsgAndPrint("  " + versionString)

# get inputs
inFds = sys.argv[1]
mapScale = float(sys.argv[2])

gdb = os.path.dirname(inFds)
fds = os.path.join(gdb, "GeologicMap")
scripts = os.path.dirname(sys.argv[0])
tools = os.path.dirname(scripts)
lyrx_path = os.path.join(tools, "Resources", "OrientationPointsLabels.lyrx")

if os.path.basename(inFds) == "GeologicMap":
    dipNumbers(gdb, mapScale)
else:
    addMsgAndPrint(
        "Not GeologicMap feature class, OrientationPointLabels not (re)created."
    )
