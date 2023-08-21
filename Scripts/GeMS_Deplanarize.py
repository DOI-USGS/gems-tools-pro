"""
assumptions
    Nodes have 2, 3, or 4 arcs
        if 4 arcs, one is concealed
    Nodes have sufficiently distinct positions that they can be identified as string(x)+string(y)
    all arcs that bound water have unique (not-contact, not-fault) types

***
IDENTITY copyCAF with MapUnitPolys to get copy2CAF

make list of nodes-arcIDs in copy2CAF
sort list on XY
if 3 arcs at node:
   figure out which two arcs have lowest hKey values for leftMapUnit or RightMapUnit
   set youngArcsDict[nodeID] = [youngArcID, youngArcID]

if >3 arcs at nodeL
    raise an error flag

NOTE: this has us figuring out youngArcsDict for ALL 3-arc nodes, and we will only use
youngArcsDict for some nodes. Instead of a list of nodes-arcIDS, we could make a dictionary
and only figure out youngArcsDict for those nodes where we will use the information

***
Make list of nodes-arcIDs in copyCAF
sort list on XY

if 2 arcs at node
    if arcsIdentical(), assign same mergeNumber to each
       (and if one already has a mergeNumber, assign this number to the other and to all other arcs with same mergeNumber
    else
       assign unique mergeNUMBER to any unnumbered arc
       
if 3 arcs at node
    if all have same types
       look up youngArcsDict[nodeID] and assign same mergeNumber to youngest arcs
       (and if one already has a mergeNumber, assign this number to the other and to all other arcs with same mergeNumber
    elif only two are arcsIdentical(), assign same mergeNumber to each
       (and if one already has a mergeNumber, assign this number to the other and to all other arcs with same mergeNumber
    else
       assign unique mergeNUMBER to any unMergeNumbered arc

    
if >3 arcs at node, raise an error flag


Goal: dictionary of mergeNumbers, with arcIDs as keys
    mergeNumberDict[arcID] = integer

Then, rename CAF to oldCAF
Add field mergeNumber to oldCAF
with updateCursor on oldCAF, set mergeNumber = mergeNumberDict[arcID]
dissolve oldCAF on fields type, isConcealed, ExConf, IdConf, LCM, DataSourceID, mergeNumber
  toget new CAF
drop field mergeNumber and add any unconserved fields (Notes, Label, Symbol, ...)
"""

# updated May 20 2019 to work with Python 3 in ArcGIS Pro: Evan thoms
# No debugging necessary after running through 2to3.
# The script ran with no errors.

import arcpy, os.path, sys
from GeMS_utilityFunctions import *

versionString = "GeMS_Deplanarize.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_Deplanarize.py"
checkVersion(versionString, rawurl, "gems-tools-pro")


# globals
debug1 = False
mergeNumber2ArcsDict = (
    {}
)  # key is mergeNumber, value is list of arcFIDs with this mergeNumber
arc2MergeNumberDict = {}  # key is arcFID, value is mergeNumber
nodeName2ArcsDict = (
    {}
)  # key is nodeName, value is list [ [arcFID,rMapUnit,lMapUnit],[arcFID,rMapUnit,lMapUnit],...]
hKeyDict = {}  # key is MapUnit, value is HierarchyKey


compareFields = [
    "Type",
    "IsConcealed",
    "ExistenceConfidence",
    "IdentityConfidence",
    "LocationConfidenceMeters",
    "DataSourceID",
    "Label",
    "Notes",
]
statFields = [["ContactsAndFaults_ID", "FIRST"], ["Symbol", "FIRST"]]
compareFieldsTypeIndex = 0
compareFieldsIsConcealedIndex = 1

searchRadius = 0.01

mergeNumber = 1  # counter values used to define which arcs to merge: we dissolve on fields AND mergeNumber
################################


def smallerOf(a, b):
    if a < b:
        return a
    else:
        return b


def pointPairGeographicAzimuth(pt1, pt2):
    dx = pt2[0] - pt1[0]
    dy = pt2[1] - pt1[1]
    azi = math.atan2(dy, dx)
    azi = 90 - math.degrees(azi)
    if azi < 0:
        azi = azi + 360
    return azi


def startGeogDirection(lineSeg):
    firstPoint = [lineSeg[0].X, lineSeg[0].Y]
    secondPoint = [lineSeg[1].X, lineSeg[1].Y]
    return pointPairGeographicAzimuth(firstPoint, secondPoint)


def endGeogDirection(lineSeg):
    lpt = len(lineSeg) - 1
    ntlPoint = [lineSeg[lpt - 1].X, lineSeg[lpt - 1].Y]
    lastPoint = [lineSeg[lpt].X, lineSeg[lpt].Y]
    return pointPairGeographicAzimuth(lastPoint, ntlPoint)


def nodeName(x, y):
    xstr = str(int(round(x * 100)))
    ystr = str(int(round(y * 100)))
    return xstr + "_" + ystr


def makeNodeName2ArcsDict(caf, fields):
    # takes arc fc, list of fields (e.g. [Left_MapUnit, Right_MapUnit] )
    #   makes to and from node fcs, concatenates, sorts, finds arc-ends
    #   that share common XY values
    # returns dictionary of arcs at each node, keyed to nodename
    #    i.e., dict[nodename] = [[arc1 fields], [arc2 fields],...]
    fv1 = os.path.dirname(caf) + "/xxxNfv1"
    fv2 = os.path.dirname(caf) + "/xxxNfv12"

    lenFields = len(fields)
    addMsgAndPrint("  making endpoint feature classes")
    testAndDelete(fv1)
    arcpy.FeatureVerticesToPoints_management(caf, fv1, "BOTH_ENDS")
    addMsgAndPrint("  adding XY values and sorting by XY")
    arcpy.AddXY_management(fv1)
    testAndDelete(fv2)
    arcpy.Sort_management(
        fv1, fv2, [["POINT_X", "ASCENDING"], ["POINT_Y", "ASCENDING"]]
    )
    ##fix fields statement and following field references
    fields.append("SHAPE@XY")
    indexShape = len(fields) - 1

    isFirst = True
    nArcs = 0
    nodeList = []
    with arcpy.da.SearchCursor(fv2, fields) as cursor:
        for row in cursor:
            x = row[indexShape][0]
            y = row[indexShape][1]
            arcFields = row[0:lenFields]
            if isFirst:
                isFirst = False
                lastX = x
                lastY = y
                arcs = [arcFields]
            elif abs(x - lastX) < searchRadius and abs(y - lastY) < searchRadius:
                arcs.append(arcFields)
            else:
                nodeList.append([nodeName(lastX, lastY), arcs])
                lastX = x
                lastY = y
                arcs = [arcFields]
        nodeList.append([nodeName(lastX, lastY), arcs])

    addMsgAndPrint("  " + str(len(nodeList)) + " distinct nodes")
    addMsgAndPrint("  cleaning up")
    for fc in fv1, fv2:
        testAndDelete(fc)

    nodeDict = {}
    for n in nodeList:
        nodeDict[n[0]] = n[1]
    return nodeDict


def makeNodeList(caf, fields1, arcDirs=False):
    # takes arc fc, list of fields (e.g. [FID, Type, LocConfM] )
    #   makes to and from node fcs, concatenates, sorts, finds arc-ends
    #   that share common XY values
    # returns list of arcs at each node, keyed to nodename
    #    i.e., list of [nodename, [[arc1 fields], [arc2 fields],...] ]
    #  and, if arcDirs == True, includes initial direction for each arc
    tempCaf = os.path.dirname(caf) + "/xxxtempCaf"
    fv1 = os.path.dirname(caf) + "/xxxfv1"
    fv1a = os.path.dirname(caf) + "/xxxfv1a"
    fv2 = os.path.dirname(caf) + "/xxxfv12"

    fields = list(fields1)  # make a copy of fields1, so that we don't modify it
    lenFields = len(fields)
    if not arcDirs:
        xCaf = caf
    else:
        addMsgAndPrint("  calculating line directions at line ends")
        fields.append("LineDir")
        lineDirIndex = len(fields) - 1
        testAndDelete(tempCaf)
        arcpy.Copy_management(caf, tempCaf)
        xCaf = tempCaf
        arcpy.AddField_management(tempCaf, "LineDir", "FLOAT")
        arcpy.AddField_management(tempCaf, "EndDir", "FLOAT")
        dirFields = ["SHAPE@", "LineDir", "EndDir"]
        with arcpy.da.UpdateCursor(tempCaf, dirFields) as cursor:
            for row in cursor:
                lineSeg = row[0].getPart(0)
                row[1] = startGeogDirection(lineSeg)
                row[2] = endGeogDirection(lineSeg)
                cursor.updateRow(row)
        xcaf = tempCaf
        lenFields = lenFields + 1
    addMsgAndPrint("  making endpoint feature classes")
    testAndDelete(fv1)
    testAndDelete(fv1a)
    arcpy.FeatureVerticesToPoints_management(xCaf, fv1, "START")
    arcpy.FeatureVerticesToPoints_management(xCaf, fv1a, "END")
    if arcDirs:
        arcpy.CalculateField_management(fv1a, "LineDir", "!EndDir!", "PYTHON")
    arcpy.Append_management(fv1a, fv1)
    addMsgAndPrint("  adding XY values and sorting by XY")
    arcpy.AddXY_management(fv1)
    testAndDelete(fv2)
    arcpy.Sort_management(
        fv1, fv2, [["POINT_X", "ASCENDING"], ["POINT_Y", "ASCENDING"]]
    )

    ##fix fields statement and following field references
    fields.append("SHAPE@XY")
    indexShape = len(fields) - 1
    FID = "ORIG_FID"
    fields.append(FID)
    indexFID = len(fields) - 1

    isFirst = True
    nArcs = 0
    nodeList = []
    with arcpy.da.SearchCursor(fv2, fields) as cursor:
        for row in cursor:
            x = row[indexShape][0]
            y = row[indexShape][1]
            origFID = row[indexFID]
            arcFields = row[0:lenFields]
            if isFirst:
                lastX = x
                lastY = y
                isFirst = False
                arcs = []
            if abs(x - lastX) < searchRadius and abs(y - lastY) < searchRadius:
                arcs.append([origFID, arcFields])
            else:
                nodeList.append([nodeName(lastX, lastY), arcs])
                arcs = [[origFID, arcFields]]
                lastX = x
                lastY = y
        nodeList.append([nodeName(lastX, lastY), arcs])

    addMsgAndPrint("  " + str(len(nodeList)) + " distinct nodes")
    addMsgAndPrint("  cleaning up")
    for fc in tempCaf, fv1, fv1a, fv2:
        testAndDelete(fc)
    return nodeList


def threeArcsMeet(nodeName, arcs):
    # takes list of 3 as argument.
    # if number of not concealed arcs <> 3, writes an error message, sets
    #  sets oddArcs = [arcs], mergeArcs = [] and returns
    # if 3 arcs not concealed
    #   finds pair that bound youngest poly
    #   if pair are same:
    #       sets mergeArcs = this pair, oddArcs = other
    #   else
    #       sets mergeArcs = [], oddArcs = arcs
    mergeArcs = []
    oddArcs = []
    if len(arcs) != 3:
        addMsgAndPrint("  Problem in adjoinYoungestPoly, " + str(len(arcs)) + " arcs")
        addMsgAndPrint(str(arcs))
        return [], arcs
    try:
        arcPolyList = nodeName2ArcsDict[nodeName]
    except:
        addMsgAndPrint("  " + nodeName + " has no entry in nodeName2ArcDict")
        return [], arcs
    ay = []
    for arc in arcPolyList:
        ay.append([smallerOf(hKeyDict[arc[1]], hKeyDict[arc[2]]), arc[0]])
    ay.sort()

    pairArcs = []
    for arc in arcs:
        if arc[0] in (ay[0][1], ay[1][1]):
            pairArcs.append(arc)
        try:
            if arc[0] == ay[2][1]:
                oddArcs.append(arc)
        except:
            addMsgAndPrint("threeArcsMeet, problem ...")
            addMsgAndPrint(str(ay))
            addMsgAndPrint(str(arcPolyList))
            addMsgAndPrint(str(arcs))
            return [], arcs

    if arcAttribsSame(pairArcs):
        mergeArcs = pairArcs
    else:
        for arc in pairArcs:
            oddArcs.append(arc)
    return mergeArcs, oddArcs


def arcAttribsSame(arcs):
    if len(arcs) == 1:
        return True
    else:
        arcsSame = True
        for i in range(1, len(arcs)):
            if arcs[i][1] != arcs[0][1]:
                arcsSame = False
        return arcsSame


def setUniqueMergeNumbers(arcs):
    global mergeNumber
    if arcs != [None]:
        try:
            for anArc in arcs:
                if not anArc[0] in list(arc2MergeNumberDict.keys()):
                    mergeNumber += 1
                    arc2MergeNumberDict[anArc[0]] = mergeNumber
                    mergeNumber2ArcsDict[mergeNumber] = [anArc[0]]
        except:
            addMsgAndPrint("  setUniqueMergeNumbers failed")
            addMsgAndPrint(str(arcs))
            pass
    return


def setMatchingMergeNumbers(arcs):
    global mergeNumber
    # test that len(arcs) >= 2 else print error message and return
    otherArcs = None
    if arcs != None:
        if len(arcs) >= 2:
            mn = 0
            arcIDs = []
            for anArc in arcs:
                arcIDs.append(anArc[0])
                if anArc[0] in list(arc2MergeNumberDict.keys()):
                    mn = arc2MergeNumberDict[anArc[0]]
                    otherArcs = mergeNumber2ArcsDict[mn]
            if mn == 0:  # no arc yet tagged with mergeNumber
                mergeNumber += 1
            else:  # got some arcs with this mn already
                for oa in otherArcs:
                    if not oa in arcIDs:
                        arcIDs.append(oa)
            for anArc in arcs:
                arc2MergeNumberDict[anArc[0]] = mergeNumber
            mergeNumber2ArcsDict[mergeNumber] = arcIDs
        else:
            addMsgAndPrint(
                "  Got an error in setMatchingMergeNumbers. Only "
                + str(len(arcs))
                + " arcs!"
            )
            for anArc in arcs:
                addMsgAndPrint(str(anArc))
            return
    else:
        addMsgAndPrint("  setMatchingMergeNumbers, arcs = None")
    return


#################################
inGdb = sys.argv[1]
inFds = inGdb + "/GeologicMap"
inCaf = inFds + "/ContactsAndFaults"
tempCaf = inFds + "/xxxTempCaf"
inMup = inFds + "/MapUnitPolys"
inDMU = os.path.dirname(inFds) + "/DescriptionOfMapUnits"

addMsgAndPrint(versionString)

# build hKeyDict[mapUnit] = hKey
addMsgAndPrint("Building hKeyDict")
fields = ["MapUnit", "HierarchyKey"]
with arcpy.da.SearchCursor(inDMU, fields) as cursor:
    for row in cursor:
        if row[0] != None:
            if not row[0].isspace():
                hKeyDict[row[0]] = row[1]
# and, for arcs that adjoin nothing (map boundaries!)
hKeyDict[""] = "0"

copyCaf = inFds + "/xxxCopyCAF"
copy2Caf = inFds + "/xxxCopy2CAF"
# copy CAF to copyCAF
addMsgAndPrint("Copying ContactsAndFaults to " + copyCaf)
addMsgAndPrint("  and deleting concealed arcs")
testAndDelete(copyCaf)
arcpy.Copy_management(inCaf, copyCaf)

# delete all concealed arcs in copyCAF
isCon = arcpy.AddFieldDelimiters(copyCaf, "IsConcealed")
testAndDelete("notConcealedCaf")
arcpy.MakeFeatureLayer_management(copyCaf, "notConcealedCaf", isCon + " = 'N' ")

# IDENTITY notConcealedCAF with MapUnitPolys to get copy2CAF
addMsgAndPrint("Copying ContactsAndFaults to " + copy2Caf)
addMsgAndPrint("  and IDENTITYing with MapUnitPolys")
testAndDelete(copy2Caf)
arcpy.Identity_analysis(
    "notConcealedCaf", inMup, copy2Caf, "ALL", "", "KEEP_RELATIONSHIPS"
)
# make dictionary Dict[nodeName] = [[arcFID,lMapUnit,rMapUnit],[arcFID,lMapUnit,rMapUnit],...] of arcs at each node
addMsgAndPrint("Building nodeName2ArcsDict")
nodeName2ArcsDict = makeNodeName2ArcsDict(
    copy2Caf, ["FID_" + os.path.basename(copyCaf), "LEFT_MapUnit", "RIGHT_MapUnit"]
)

addMsgAndPrint("Building allNodeList")

allNodeList = makeNodeList(inCaf, compareFields)

addMsgAndPrint("Iterating through nodes to find arcs to be unsplit")
for node in allNodeList:
    nodeName = node[0]
    arcs = node[1]
    oddArcs = []
    mergeArcs = []
    # remove concealed arcs
    ## note that removing all concealed arcs leaves the possibility of fragmented concealed arcs
    ## that should be merged and are not.
    ## need better code!
    newArcs = []
    if len(arcs) > 4:
        for arc in arcs:
            oddArcs.append(arc)
    elif len(arcs) == 4:  # should be one and onlye one arc that is concealed
        if debug1:
            addMsgAndPrint("got 4 arcs, removing those that are concealed")
        if debug1:
            addMsgAndPrint("  " + str(arcs))
        for arc in arcs:
            if arc[1][compareFieldsIsConcealedIndex] == "Y":
                oddArcs.append(arc)
            else:
                newArcs.append(arc)
        arcs = newArcs
        if debug1:
            addMsgAndPrint("  " + str(arcs))
    if len(arcs) == 1:
        oddArcs = arcs
    elif len(arcs) == 2:
        if arcAttribsSame(arcs):  # We assume all faults have correct directions,
            # and if two faults of same type meet and shouldn't be merged (change in UP direction), one has a different NOTE value
            mergeArcs = arcs
        else:
            oddArcs = arcs
    elif len(arcs) == 3:
        j = compareFieldsTypeIndex
        arcTypes = set(
            [arcs[0][1][j], arcs[1][1][j], arcs[2][1][j]]
        )  # Note that we assume Type is first of fields
        j = compareFieldsIsConcealedIndex
        concealedStatus = arcs[0][1][j] + arcs[1][1][j] + arcs[2][1][j]
        # all arcs are contacts
        if len(arcTypes) == 1 and "contact" in arcTypes and concealedStatus == "NNN":
            if debug1:
                addMsgAndPrint("3 arcs, all are contacts")
            mergeArcs, newOddArcs = threeArcsMeet(nodeName, arcs)
            for arc in newOddArcs:
                oddArcs.append(arc)
        # if only two arcs have same type (contact, normal fault, map boundary, waterline, ...)
        elif len(arcTypes) == 2:
            if debug1:
                addMsgAndPrint("3 arcs, 2 of same type")
            # need to find two that are same
            if arcAttribsSame([arcs[0], arcs[1]]):
                mergeArcs = [arcs[0], arcs[1]]
                oddArcs.append(arcs[2])
            elif arcAttribsSame([arcs[0], arcs[2]]):
                mergeArcs = [arcs[0], arcs[2]]
                oddArcs.append(arcs[1])
            elif arcAttribsSame([arcs[2], arcs[1]]):
                mergeArcs = [arcs[2], arcs[1]]
                oddArcs.append(arcs[0])
            else:  # no arcs have same attributes
                for arc in arcs:
                    oddArcs.append(arc)

        else:  # in particular, if three faults of same kind meet, need to have a human involved
            # do nothing, append all arcs to oddArcs
            if debug1:
                addMsgAndPrint("3 arcs, hit the else clause")
            for arc in arcs:
                oddArcs.append(arc)
        if debug1:
            addMsgAndPrint("  " + str(arcTypes))

    if oddArcs != None:
        if len(oddArcs) > 0:
            setUniqueMergeNumbers(oddArcs)
    if mergeArcs != None:
        if len(mergeArcs) > 0:
            setMatchingMergeNumbers(mergeArcs)

# copy CAF to savedCaf
savedCaf = getSaveName(inCaf)
addMsgAndPrint("Copying ContactsAndFaults to " + savedCaf)
arcpy.Copy_management(inCaf, savedCaf)
# copy CAF to tempCaf
addMsgAndPrint("Copying ContactsAndFaults to " + tempCaf)
testAndDelete(tempCaf)
arcpy.Copy_management(inCaf, tempCaf)
# delete CAF
testAndDelete(inCaf)
## now, need to add mergeNumber field
addMsgAndPrint("Updating arcs with MergeNumber values")
arcpy.AddField_management(tempCaf, "MergeNumber", "LONG")
# open update cursor
with arcpy.da.UpdateCursor(tempCaf, ["OBJECTID", "MergeNumber"]) as cursor:
    for row in cursor:
        if row[0] in list(arc2MergeNumberDict.keys()):
            row[1] = arc2MergeNumberDict[row[0]]
        else:
            mergeNumber += 1
            row[1] = mergeNumber
            addMsgAndPrint(
                "  OBJECTID = " + str(row[0]) + " not in arc2MergeNumberDict"
            )
        cursor.updateRow(row)
## merge tempCaf to CAF (and keep other fields!)
addMsgAndPrint("Unsplitting " + tempCaf + " to ContactsAndFaults")
arcpy.UnsplitLine_management(tempCaf, inCaf, compareFields, statFields)
## drop mergeNumber field
arcpy.DeleteField_management(inCaf, "MergeNumber")

addMsgAndPrint(
    str(numberOfRows(tempCaf))
    + " rows in old CAF, "
    + str(numberOfRows(inCaf))
    + " rows in new CAF"
)

addMsgAndPrint("Cleaning up")
addMsgAndPrint("  but not deleting tempCaf = " + tempCaf)
for fc in copyCaf, copy2Caf:  # ,tempCaf:
    testAndDelete(fc)


"""
Possibilities:
1 arc at a node: Do nothing
2 arcs at a node:
    If arcs have same attributes, merge
    Else don't merge
>4 arcs at a node:
    Something is wrong. Do nothing (set all arcs to not merge)
4 arcs at a node:
    at least one arc should be concealed
    remove concealed arc, pass remainder to 3-arc code
3 arcs at a node:
    If all 3 arcs are Type = contact and Not concealed:
        pass to 3-arc code
    elif 2 and only 2 arcs have same attributes
        merge
        don't merge other arc
    else: all arcs different OR arcs==same and not (all arcs contact and not concealed)
        don't merge any arcs
"""
