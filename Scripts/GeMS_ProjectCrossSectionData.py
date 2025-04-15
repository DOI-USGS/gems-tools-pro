"""
Projects all data in GeologicMap feature dataset (inFds) to cross-section plane
Creates featureclasses with names prefixed by 'ed_'
Output feature classes have all input FC attributes. In addition, point feature
  classes are given attribute:
    DistanceFromSection 
    LocalCsAzimuth  (Trend of section line at projected point,
         0..360, measured CCW from grid N)
If points are OrientationData, we also calculate attributes:
    ApparentInclination
    Obliquity
    PlotAzimuth (= apparentInclination + 90)

Assumptions:
  Input FDS is GeologicMap
  xsLine has only ONE LINE (one row in data table)
  We don't project points that are beyond ends of xsLine,
     even though to do so is often desirable
  We don't project feature classes whose names begin with
     the strings 'errors_'  or 'ed_'

Much of this code is modeled on cross-section routines written by
Evan Thoms, USGS, Anchorage.

Ralph Haugerud
rhaugerud@usgs.gov
"""

# 10 June 2019: Updated to work with Python 3 in ArcGIS Pro. -Evan Thoms
# Ran script through 2to3 and it worked with no other edits necessary.
# Consider re-writing some sections to work with new Python modules, but none of the
# 'older' code causes any errors.

import arcpy, sys, os.path, math
from GeMS_Definition import tableDict
from GeMS_utilityFunctions import *

versionString = "GeMS_ProjectCrossSectionData.py, version of 7/3/24"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_ProjectCrossSectionData.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

##inputs
#  gdb          geodatabase with GeologicMap feature dataset to be projected
#  projectAll
#  fcToProject
#  dem
#  xsLine       cross-section line: _single-line_ feature class or layer
#  startQuadrant start quadrant (NE,SE,SW,NW)
#  outFdsTag   output feature dataset. Input value is appended to 'CrossSection'
#  vertEx       vertical exaggeration; a number
#  bufferDistance  a number
#  forcExit
#  scratchWS
#  saveIntermediate (boolean)

lineCrossingLength = (
    1000  # length (in map units) of vertical line drawn where arcs cross section line
)
exemptedPrefixes = (
    "errors_",
    "ed_",
)  # prefixes that flag a feature class as not to be projected

transDict = {
    "String": "TEXT",
    "Single": "FLOAT",
    "Double": "DOUBLE",
    "NoNulls": "NON_NULLABLE",
    "NullsOK": "NULLABLE",
    "Date": "DATE",
}

##### UTILITY FUNCTIONS ############################


def doProject(fc):
    doPrj = True
    for exPfx in exemptedPrefixes:
        if fc.find(exPfx) == 0:
            doPrj = False
    return doPrj


def shortName(obj):
    return os.path.basename(obj)


def wsName(obj):
    return os.path.dirname(obj)


def cartesianToGeographic(angle):
    ctg = -90 - angle
    if ctg < 0:
        ctg = ctg + 360
    return ctg


def isAxial(ptType):
    m = False
    for s in ("axis", "lineation", " L"):
        if ptType.upper().find(s.upper()) > -1:
            m = True
    return m


def obliq(theta1, theta2):
    obl = abs(theta1 - theta2)
    if obl > 180:
        obl = obl - 180
    if obl > 90:
        obl = 180 - obl
    return obl


def azimuthDifference(a, b):
    # a, b are two azimuths in clockwise geographic notation
    # azDiff is in range -180..180
    # if azDiff < 0, a is counterclockwise of b
    # if azDiff > 0, a is clockwise of b
    azDiff = a - b
    if azDiff > 180:
        azDiff = azDiff - 360
    if azDiff < -180:
        azDiff = azDiff + 360
    return azDiff


def plotAzimuth(inclinationDirection, thetaXS, apparentInclination):
    azDiff = azimuthDifference(thetaXS, inclinationDirection)
    if azDiff >= -90 and azDiff <= 90:
        return 270 + apparentInclination
    else:
        return 270 - apparentInclination


def apparentPlunge(azi, inc, thetaXS):
    obliquity = obliq(azi, thetaXS)
    appInc = math.degrees(
        math.atan(
            vertEx * math.tan(math.radians(inc)) * math.cos(math.radians(obliquity))
        )
    )
    return appInc, obliquity


def apparentDip(azi, inc, thetaXS):
    obliquity = obliq(azi, thetaXS)
    appInc = math.degrees(
        math.atan(
            vertEx * math.tan(math.radians(inc)) * math.sin(math.radians(obliquity))
        )
    )
    return appInc, obliquity


def getIdField(fc):
    idField = ""
    fcFields = arcpy.ListFields(fc)
    for fld in fcFields:
        if fld.name.find("_ID") > 0:
            idField = fld.name
    return idField


#  copied from NCGMP09v1.1_CreateDatabase_Arc10.0.py, version of 20 September 2012
def createFeatureClass(thisDB, featureDataSet, featureClass, shapeType, fieldDefs):
    try:
        arcpy.env.workspace = thisDB
        arcpy.CreateFeatureclass_management(featureDataSet, featureClass, shapeType)
        thisFC = thisDB + "/" + featureDataSet + "/" + featureClass
        for fDef in fieldDefs:
            try:
                if fDef[1] == "String":
                    arcpy.AddField_management(
                        thisFC,
                        fDef[0],
                        transDict[fDef[1]],
                        "#",
                        "#",
                        fDef[3],
                        "#",
                        transDict[fDef[2]],
                    )
                else:
                    arcpy.AddField_management(
                        thisFC,
                        fDef[0],
                        transDict[fDef[1]],
                        "#",
                        "#",
                        "#",
                        "#",
                        transDict[fDef[2]],
                    )
            except:
                addMsgAndPrint(
                    "Failed to add field "
                    + fDef[0]
                    + " to feature class "
                    + featureClass
                )
                addMsgAndPrint(arcpy.GetMessages(2))
    except:
        addMsgAndPrint(arcpy.GetMessages())
        addMsgAndPrint(
            "Failed to create feature class "
            + featureClass
            + " in dataset "
            + featureDataSet
        )


def locateEventTable(
    gdb, inFC, pts, dem, sDistance, eventProperties, zType, isLines=False
):
    desc = arcpy.Describe(pts)

    if not desc.hasZ:
        addMsgAndPrint("      adding Z values")
        arcpy.sa.AddSurfaceInformation(pts, dem, zType, "LINEAR")

    ## working around bug in LocateFeaturesAlongRoutes
    # add special field for duplicate detection
    dupDetectField = "xDupDetect"
    arcpy.AddField_management(pts, dupDetectField, "LONG")
    # and calc this field = OBJECTID
    OID = arcpy.Describe(pts).OIDFieldName
    expr = '"!' + OID + '!"'
    arcpy.CalculateField_management(pts, dupDetectField, expr, "PYTHON")
    # locate linePts along route
    addMsgAndPrint("      making event table")
    eventTable = gdb + "/evTb_" + inFC
    testAndDelete(eventTable)
    arcpy.LocateFeaturesAlongRoutes_lr(
        pts, ZMline, idField, sDistance, eventTable, eventProperties
    )
    nRows = numberOfRows(eventTable)
    nPts = numberOfRows(pts)
    if (
        nRows > nPts and not isLines
    ):  # if LocateFeaturesAlongRoutes has made duplicates  (A BUG!)
        addMsgAndPrint("      correcting for bug in LocateFeaturesAlongRoutes")
        addMsgAndPrint("        " + str(nRows) + " rows in event table")
        addMsgAndPrint("        removing duplicate entries in event table")
        arcpy.DeleteIdentical_management(eventTable, dupDetectField)
        addMsgAndPrint(
            "        " + str(numberOfRows(eventTable)) + " rows in event table"
        )
    arcpy.DeleteField_management(eventTable, dupDetectField)
    return eventTable


###############################################################
addMsgAndPrint("\n  " + versionString)

gdb = sys.argv[1]
projectAll = sys.argv[2]
fcToProject = sys.argv[3]
dem = sys.argv[4]
xsLine = sys.argv[5]
startQuadrant = sys.argv[6]
outFdsTag = sys.argv[7]
vertEx = float(sys.argv[8])
bufferDistance = float(sys.argv[9])
addLTYPE = sys.argv[10]
forceExit = sys.argv[11]
scratchws = sys.argv[12]
saveIntermediate = sys.argv[13]

##for arg in sys.argv:
##    addMsgAndPrint(str(arg))

if projectAll == "true":
    projectAll = True
else:
    projectAll = False

if addLTYPE == "true":
    addLTYPE = True
else:
    addLTYPE = False

if forceExit == "true":
    forceExit = True
else:
    forceExit = False

if saveIntermediate == "true":
    saveIntermediate = True
else:
    saveIntermediate = False

inFds = gdb + "/GeologicMap"
outFds = gdb + "/CrossSection" + outFdsTag

if arcpy.Exists(scratchws):
    scratch = scratchws
else:
    scratch = outFds
addMsgAndPrint("  Scratch directory is " + scratch)

arcpy.env.overwriteOutput = True

try:
    arcpy.CheckOutExtension("Spatial")
except:
    addMsgAndPrint("\nCannot check out Spatial Analyst extension.")
    sys.exit()

## Checking section line
addMsgAndPrint("  Checking section line")
idField = getIdField(xsLine)
##   does xsLine have 1-and-only-1 arc? if not, bail
i = numberOfRows(xsLine)
if i > 1:
    addMsgAndPrint("OOPS! More than one arc in " + xsLine)
    sys.exit()
elif i == 0:
    addMsgAndPrint("OOPS! Mo arcs in " + xsLine)
    sys.exit()

## make output fds if it doesn't exist
#  set output fds spatial reference to input fds spatial reference
if not arcpy.Exists(outFds):
    addMsgAndPrint("  Making feature data set " + shortName(outFds))
    arcpy.CreateFeatureDataset_management(gdb, shortName(outFds), inFds)

addMsgAndPrint("  Prepping section line")
## make copy of section line
tempXsLine = arcpy.CreateScratchName(
    "xx", outFdsTag + "xsLine", "FeatureClass", scratch
)
addMsgAndPrint("    copying " + shortName(xsLine) + " to xxxXsLine")
# addMsgAndPrint(xsLine+' '+scratch)
arcpy.FeatureClassToFeatureClass_conversion(xsLine, scratch, shortName(tempXsLine))

desc = arcpy.Describe(tempXsLine)
xslfields = fieldNameList(tempXsLine)
idField = ""
for fld in xslfields:
    if fld.find("_ID") > 0:
        idField = fld
if idField == "":
    idField = "ORIG_ID"
    arcpy.AddField_management(tempXsLine, idField, "TEXT")
    arcpy.CalculateField_management(tempXsLine, idField, "01", "PYTHON3")
specialFields = [
    desc.OIDFieldName,
    desc.shapeFieldName,
    idField,
    "Shape_Length",
    "Length",
]
addMsgAndPrint("    deleting most fields")
for nm in xslfields:
    if nm not in specialFields:
        try:
            arcpy.DeleteField_management(tempXsLine, nm)
        except:
            pass
##   check for Z and M values
desc = arcpy.Describe(tempXsLine)
if desc.hasZ and desc.hasM:
    ZMline = tempXsLine
else:
    # Add Z values
    addMsgAndPrint("    getting elevation values for " + shortName(tempXsLine))
    Zline = arcpy.CreateScratchName("xx", outFdsTag + "_Z", "FeatureClass", scratch)
    arcpy.sa.InterpolateShape(dem, tempXsLine, Zline)
    # Add M values
    addMsgAndPrint("    measuring " + shortName(Zline))
    ZMline = arcpy.CreateScratchName("xx", outFdsTag + "_ZM", "FeatureClass", scratch)
    arcpy.CreateRoutes_lr(Zline, idField, ZMline, "LENGTH", "#", "#", startQuadrant)
## buffer line to get selection polygon
addMsgAndPrint("    buffering " + shortName(tempXsLine) + " to get selection polygon")
tempBuffer = arcpy.CreateScratchName(
    "xx", outFdsTag + "xsBuffer", "FeatureClass", scratch
)
arcpy.Buffer_analysis(ZMline, tempBuffer, bufferDistance, "FULL", "FLAT")

## get lists of feature classes to be projected
lineFCs = []
polyFCs = []
pointFCs = []
if projectAll:
    oldws = arcpy.env.workspace
    arcpy.env.workspace = gdb + "/GeologicMap"
    linefc = arcpy.ListFeatureClasses("*", "Line")
    polyfc = arcpy.ListFeatureClasses("*", "Polygon")
    pointfc = arcpy.ListFeatureClasses("*", "Point")
    for fc in linefc:
        if doProject(fc) and numberOfRows(fc) > 0:
            lineFCs.append(gdb + "/GeologicMap/" + fc)
    for fc in polyfc:
        if doProject(fc) and numberOfRows(fc) > 0:
            polyFCs.append(gdb + "/GeologicMap/" + fc)
    for fc in pointfc:
        if doProject(fc) and numberOfRows(fc) > 0:
            pointFCs.append(gdb + "/GeologicMap/" + fc)
else:
    featureClassesToProject = fcToProject.split(";")
    for fc in featureClassesToProject:
        desc = arcpy.Describe(fc)
        if desc.shapeType == "Polyline":
            lineFCs.append(fc)
        if desc.shapeType == "Polygon":
            polyFCs.append(fc)
        if desc.shapeType == "Point":
            pointFCs.append(fc)

addMsgAndPrint("\n  Projecting line feature classes:")
for lineFC in lineFCs:
    inFC = shortName(lineFC)
    addMsgAndPrint("    " + inFC)
    arcpy.env.workspace = wsName(lineFC)
    if inFC == "ContactsAndFaults":
        lineCrossingLength = -lineCrossingLength
    # intersect inFC with ZMline to get points where arcs cross section line
    linePts = scratch + "/xxxLinePts" + outFdsTag
    arcpy.Intersect_analysis([inFC, ZMline], linePts, "ALL", "#", "POINT")
    if numberOfRows(linePts) == 0:
        addMsgAndPrint("      " + inFC + " does not intersect section line")
    else:  # numberOfRows > 0
        eventProperties = "rtID POINT M fmp"
        eventTable = locateEventTable(
            gdb, inFC, linePts, dem, 10, eventProperties, "Z_MEAN", True
        )
        addMsgAndPrint("      placing events on section line")
        eventLyr = "xxxLineEvents"
        arcpy.MakeRouteEventLayer_lr(
            ZMline, idField, eventTable, eventProperties, eventLyr
        )
        outFC = "ed_CS" + outFdsTag + shortName(inFC)
        addMsgAndPrint(
            "      creating feature class " + outFC + " in " + shortName(outFds)
        )
        # make new feature class using old as template
        testAndDelete(outFds + "/" + outFC)
        arcpy.CreateFeatureclass_management(
            outFds, outFC, "POLYLINE", inFC, "DISABLED", "SAME_AS_TEMPLATE"
        )
        outFC = outFds + "/" + outFC
        addMsgAndPrint("      moving and calculating attributes")
        ## open search cursor on inFC, open insert cursor on outFC
        inRows = arcpy.SearchCursor(eventLyr)
        outRows = arcpy.InsertCursor(outFC)
        # get field names
        inFieldNames = fieldNameList(eventLyr)
        outFieldNames = fieldNameList(outFC)
        # get fields to ignore
        ignoreFields = []
        desc = arcpy.Describe(eventLyr)
        ignoreFields.append(desc.ShapeFieldName)
        ignoreFields.append(desc.OIDFieldName)
        for inRow in inRows:
            outRow = outRows.newRow()
            # do shape
            X = inRow.M
            Y = inRow.Shape.firstPoint.Z
            pnt1 = arcpy.Point(X, (Y - lineCrossingLength) * vertEx)
            pnt2 = arcpy.Point(X, Y * vertEx)
            pnt3 = arcpy.Point(X, (Y + lineCrossingLength) * vertEx)
            lineArray = arcpy.Array([pnt1, pnt2, pnt3])
            outRow.Shape = lineArray
            # transfer matching fields
            for field in inFieldNames:
                if field in outFieldNames and not field in ignoreFields:
                    stuff = inRow.getValue(field)
                    outRow.setValue(field, stuff)
            outRows.insertRow(outRow)
        ## clean up
        if not saveIntermediate:
            for f in eventTable, eventLyr, linePts:
                testAndDelete(f)
        del inRows, outRows

addMsgAndPrint("\n  Projecting point feature classes:")
## for each input point feature class:
for pointClass in pointFCs:
    inFC = shortName(pointClass)
    addMsgAndPrint("    " + inFC)
    arcpy.env.workspace = wsName(pointClass)
    # clip inputfc with selection polygon to make tempPoints
    addMsgAndPrint("      clipping with selection polygon")
    tempPoints = scratch + "/xxx" + outFdsTag + inFC
    arcpy.Clip_analysis(pointClass, tempBuffer, tempPoints)
    # check to see if nonZero number of rows and not in excluded feature classes
    nPts = numberOfRows(tempPoints)
    addMsgAndPrint("      " + str(nPts) + " points within selection polygon")
    if nPts > 0:
        eventProperties = "rtID POINT M fmp"
        eventTable = locateEventTable(
            gdb, inFC, tempPoints, dem, bufferDistance + 200, eventProperties, "Z"
        )
        addMsgAndPrint("      placing events on section line")
        eventLyr = "xxxPtEvents"
        arcpy.MakeRouteEventLayer_lr(
            ZMline,
            idField,
            eventTable,
            eventProperties,
            eventLyr,
            "#",
            "#",
            "ANGLE_FIELD",
            "TANGENT",
        )
        outFC = outFds + "/ed_CS" + outFdsTag + shortName(inFC)
        outFCa = outFC + "a"
        addMsgAndPrint("      copying event layer to " + shortName(outFCa))
        arcpy.CopyFeatures_management(eventLyr, outFCa)
        addMsgAndPrint("      adding fields")
        # add DistanceFromSection and LocalXsAzimuth
        arcpy.AddField_management(outFCa, "DistanceFromSection", "FLOAT")
        arcpy.AddField_management(outFCa, "LocalCSAzimuth", "FLOAT")
        # set isOrientationData
        addMsgAndPrint("      checking for Azimuth and Inclination fields")
        inFieldNames = fieldNameList(inFC)
        if "Azimuth" in inFieldNames and "Inclination" in inFieldNames:
            isOrientationData = True
            arcpy.AddField_management(outFCa, "ApparentInclination", "FLOAT")
            arcpy.AddField_management(outFCa, "Obliquity", "FLOAT")
            arcpy.AddField_management(outFCa, "MapAzimuth", "FLOAT")
        else:
            isOrientationData = False
        arcpy.CreateFeatureclass_management(outFds, shortName(outFC), "POINT", outFCa)
        addMsgAndPrint("      calculating shapes and attributes")
        ## open update cursor on outFC
        cursor = arcpy.UpdateCursor(outFCa)
        outCursor = arcpy.InsertCursor(outFC)
        i = 0
        ii = 0
        for row in cursor:
            # keep track of how many rows are processed
            i = i + 1
            ii = ii + 1
            ####addMsgAndPrint(str(i))
            if ii == 50:
                addMsgAndPrint("       row " + str(i))
                ii = 0
            #   substitute M,Z for X,Y
            try:
                pntObj = arcpy.Point()
                pntObj.X = row.M
                if row.Z == None:
                    pntObj.Y = -999
                    addMsgAndPrint(
                        "OBJECTID = "
                        + str(row.OBJECTID)
                        + " Z missing, assigned value of -999"
                    )
                else:
                    pntObj.Y = row.Z * vertEx
                row.Shape = pntObj
            except:
                addMsgAndPrint(
                    "Failed to make shape: OBJECTID = "
                    + str(row.OBJECTID)
                    + ", M = "
                    + str(row.M)
                    + ", Z = "
                    + str(row.Z)
                )
                ## need to do something to flag rows that failed?
            #   convert from cartesian  to geographic angle
            ###addMsgAndPrint(str(pntObj.X)+'  '+str(pntObj.Y)+'  '+str(pntObj.Z))
            csAzi = cartesianToGeographic(row.LOC_ANGLE)
            row.LocalCSAzimuth = csAzi
            row.DistanceFromSection = row.Distance
            if isOrientationData:
                row.MapAzimuth = row.Azimuth
                if isAxial(row.Type):
                    appInc, oblique = apparentPlunge(
                        row.Azimuth, row.Inclination, csAzi
                    )
                    inclinationDirection = row.Azimuth
                else:
                    appInc, oblique = apparentDip(row.Azimuth, row.Inclination, csAzi)
                    inclinationDirection = row.Azimuth + 90
                    if inclinationDirection > 360:
                        inclinationDirection = inclinationDirection - 360
                plotAzi = plotAzimuth(inclinationDirection, csAzi, appInc)
                row.Obliquity = round(oblique, 2)
                row.ApparentInclination = round(appInc, 2)
                row.Azimuth = round(plotAzi, 2)
            ## print row data
            # fields = arcpy.ListFields(outFC)
            # for field in fields:
            #    addMsgAndPrint(field.name+' = '+str(row.getValue(field.name)))

            # cursor.updateRow(row)
            ##  update cursor (line above) doesn't always work, so build a new FC instead:
            outCursor.insertRow(row)

        for fld in "Distance", "LOC_ANGLE", "rtID":
            arcpy.DeleteField_management(outFC, fld)
        del row
        del cursor
        ## clean up
        if not saveIntermediate:
            for f in (tempPoints, eventTable, eventLyr, outFCa):
                testAndDelete(f)


addMsgAndPrint("\n  Projecting polygon feature classes:")
for polyFC in polyFCs:
    inFC = shortName(polyFC)
    addMsgAndPrint("    " + inFC)
    arcpy.env.workspace = wsName(polyFC)
    # locate features along routes
    addMsgAndPrint("      making event table")
    eventTable = gdb + "/evTb_" + inFC
    addMsgAndPrint(eventTable)
    testAndDelete(eventTable)
    eventProperties = "rtID LINE FromM ToM"
    arcpy.LocateFeaturesAlongRoutes_lr(
        inFC, ZMline, idField, "#", eventTable, eventProperties
    )
    addMsgAndPrint("      placing events on section line")
    eventLyr = "xxxPolyEvents"
    arcpy.MakeRouteEventLayer_lr(ZMline, idField, eventTable, eventProperties, eventLyr)
    outFC = "ed_CS" + outFdsTag + shortName(inFC)
    addMsgAndPrint("      creating feature class " + outFC + " in " + shortName(outFds))
    # make new feature class using old as template
    testAndDelete(outFds + "/" + outFC)
    addMsgAndPrint(outFds + " " + outFC + " " + inFC)
    try:
        arcpy.CreateFeatureclass_management(
            outFds, outFC, "POLYLINE", inFC, "DISABLED", "SAME_AS_TEMPLATE"
        )
    except:
        addMsgAndPrint(
            "Failed to create copy of "
            + inFC
            + ". Maybe this feature class has a join?"
        )
        raise arcpy.ExecuteError
    outFC = outFds + "/" + outFC
    addMsgAndPrint("      moving and calculating attributes")
    # get field names
    inFieldNames = fieldNameList(eventLyr)
    outFieldNames = fieldNameList(outFC)
    # get fields to ignore
    ignoreFields = []
    desc = arcpy.Describe(eventLyr)
    ignoreFields.append(desc.ShapeFieldName)
    ignoreFields.append(desc.OIDFieldName)
    ## open search cursor on inFC, open insert cursor on outFC
    inRows = arcpy.SearchCursor(eventLyr)
    outRows = arcpy.InsertCursor(outFC)
    for inRow in inRows:
        outRow = outRows.newRow()
        # flip shape
        oldLine = inRow.Shape
        newLine = arcpy.Array()
        a = 0
        while a < oldLine.partCount:
            array = oldLine.getPart(a)
            newArray = arcpy.Array()
            pnt = next(array)
            while pnt:
                pnt.X = float(pnt.M)
                pnt.Y = float(pnt.Z) * vertEx
                newArray.add(pnt)
                pnt = next(array)
            newLine.add(newArray)
            a = a + 1
        outRow.Shape = newLine
        # transfer matching fields
        for field in inFieldNames:
            if field in outFieldNames and not field in ignoreFields:
                stuff = inRow.getValue(field)
                outRow.setValue(field, stuff)
        outRows.insertRow(outRow)
    ## clean up
    if not saveIntermediate:
        for f in eventTable, eventLyr:
            testAndDelete(f)
    del inRows, outRows

arcpy.CheckInExtension("Spatial")
if not saveIntermediate:
    addMsgAndPrint("\n  Deleting intermediate data sets")
    for fc in tempXsLine, ZMline, Zline, tempBuffer:
        testAndDelete(fc)

# make NCGMP09 cross-section feature classes if they are not present in output FDS
for fc in ("MapUnitPolys", "ContactsAndFaults", "OrientationPoints"):
    fclass = "CS" + outFdsTag + fc
    if not arcpy.Exists(outFds + "/" + fclass):
        addMsgAndPrint("  Making empty feature class " + fclass)
        fieldDefs = tableDict[fc]
        fieldDefs[0][0] = fclass + "_ID"
        if fc == "MapUnitPolys":
            shp = "POLYGON"
        elif fc == "ContactsAndFaults":
            shp = "POLYLINE"
            if addLTYPE:
                fieldDefs.append(["LTYPE", "String", "NullsOK", 50])
        elif fc == "OrientationPoints":
            shp = "POINT"
            if addLTYPE:
                fieldDefs.append(["PTTYPE", "String", "NullsOK", 50])
        createFeatureClass(gdb, shortName(outFds), fclass, shp, fieldDefs)

addMsgAndPrint("\n \nFinished successfully.")
if forceExit:
    addMsgAndPrint("Forcing exit by raising ExecuteError")
    raise arcpy.ExecuteError
