"""
Reports on certain aspects of geologic-map topology

Inputs:
    fds with CAF and MUP,
    HKey cutoff value for covering units
       (used to calculate whether a concealed continuation should be shown)

Outputs:
    feature class of bad nodes. Includes:
        1-arc nodes that are not faults (i.e., dangles)
        2-arc nodes at which there is a change in Type or IsConcealed 
        3-arc nodes at which:
            no two arcs have same Type
            1 or 2 arcs are concealed
            youngest map unit is not bounded by arcs of same Type
                (Note that in some maps this rule may not be applicable)
        4-arc nodes at which:
            opposite arcs don't have same Type
            0, 3, or 4 arcs are concealed
            all arcs are faults
            fault marks transition from unconcealed to concealed crossing arcs
        5+ arc nodes       
    feature class of nodes missing a continuing concealed contact or fault
        if the concealing unit has an HKey value smaller than some test value
    feature class of nodes with faultline direction changes
    deplanarized CAF feature class # still need to remove internal contacts

Significant assumptions:
    Faults have offset
    Contacts are continuous
    Improbability of coincident truncations => no 4-arc junctions unless
        one arc is concealed continuation of opposite arc
    Arcs are either faults (recognized by presence of 'fault' within Type value) or contacts
        See functions isFault, isContact in GeMS_utilityFunctions        
    HierarchyKeys correspond (mostly) to age. Lower values of HKey = younger age
    Water, permanent snow, and unmapped area (including stuff outside neatline) are youngest map units.
    Water, ice, glacier, ... thus should have LOW HKey values. Ditto "unmapped area", if it is a defined map unit. 
    Assume existence of Notes field in CAF. Code may fail if is absent.
    Also note that connectFIDs is calculated without reference to Symbol or Label fields, but
        that when arcs are unplanarized, arcs are dissolved on these fields also
"""
# 2/3/21 - ET
#   ran 2to3 on ArcMap version
#   fixed some other bugs from Python 2 syntax
#   runs with no errors, but haven't checked validity of results
# 2/4/21 - ET
#   figured out hKeyDict comparison problem in youngestMapUnit. Tool runs but haven't checked results
# 2/1/22 - ET
#   conList.sort() in def contactListWrite apparently sorted lists of [CAR_arc class object, length integer] by the first class
#   attribute (Type) in the class object. sort() in Python 3 is not so forgiving. Had to re-write that line to sort properly.
#   Should consider changing CAF_arc from a class to a dictionary. Python best practice seems to be to use a dictionary unless
#   functionality of a class is specifically needed. Also, apparently will be faster.
#   expanded all commas and plus signs with no spaces for readability (mine, at least!)
#   increased length of Type field in _Topology geodatabase from 100 to 500 to accommodate longer concatenations

import arcpy, os, sys, math, os.path, operator, time
from GeMS_utilityFunctions import *

# see gems-tools-pro version<=2.2.2 to get earlier TopologyCheck tool
versionString = "GeMS_TopologyCheck.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_TopologyCheck.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

htmlStart = """<html>\n
    <head>\n
        <meta http-equiv="content-type" content="text/html; charset=ISO-8859-1">\n
    https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_TopologyCheck_AGP2.py</head>\n
        <body>\n"""
htmlEnd = "         </body>\n   </html>\n"
ValidateTopologyNote = """Note that not all geologic-map topology errors will be identified in this report.
Some of the features identified here may not be errors. Use your judgement!"""
space4 = "&nbsp;&nbsp;&nbsp;&nbsp;"

################################

gemsFields = [
    "Type",
    "IsConcealed",
    "ExistenceConfidence",
    "IdentityConfidence",
    "LocationConfidenceMeters",
    "DataSourceID",
    "Label",
    "Symbol",
]


class CAF_arc:
    fieldList = [
        "Type",
        "IsConcealed",
        "ExistenceConfidence",
        "IdentityConfidence",
        "LocationConfidenceMeters",
        "DataSourceID",
        "Notes",
        "LineDir",
        "ToFrom",
        "RIGHT_MapUnit",
        "LEFT_MapUnit",
        "ORIG_FID",
    ]

    def __init__(self, attribs):
        self.Type = attribs[0]
        self.IsConc = attribs[1]
        self.ExConf = attribs[2]
        self.IdConf = attribs[3]
        self.LCM = attribs[4]
        self.DSID = attribs[5]
        self.Notes = attribs[6]
        self.LineDir = attribs[7]
        self.ToFrom = attribs[8]
        self.RMU = attribs[9]
        self.LMU = attribs[10]
        self.OFID = attribs[11]

    def isConcealed(self):  # returns True if IsConcealed value is 'Y'
        if self.IsConc.lower() == "y":
            return True
        else:
            return False


def sameArcAttributes(a, b):  # a and b are CAF_arc
    if (
        a.Type == b.Type
        and a.IsConc == b.IsConc
        and a.ExConf == b.ExConf
        and a.IdConf == b.IdConf
        and a.LCM == b.LCM
        and a.DSID == b.DSID
        and a.Notes == b.Notes
    ):
        return True
    else:
        return False


def sameTypeIndices(arcs):  # arcs is triplet of CAF_arc
    a = arcs[0]
    b = arcs[1]
    c = arcs[2]
    if a.Type == b.Type:
        same = [0, 1]
        diff = 2
        if b.Type == c.Type:
            same = [0, 1, 2]
            diff = None
    elif a.Type == c.Type:
        same = [0, 2]
        diff = 1
        if b.Type == c.Type:
            same = [0, 1, 2]
            diff = None
    elif b.Type == c.Type:
        same = [1, 2]
        diff = 0
    else:
        same = [0]
        diff = [0, 1, 2]
    return same, diff


def sameToFrom(a, b, c=None):
    if c == None:
        c = a
    if a.ToFrom == b.ToFrom == c.ToFrom:
        return True
    else:
        return False


def concealedArcs(arcs):  # arcs is a list of CAF_arc
    nConcealed = 0
    concealedIndices = []
    for a in arcs:
        if a.isConcealed() == True:
            nConcealed += 1
            concealedIndices.append(arcs.index(a))
    return nConcealed, concealedIndices


def adjoiningMapUnits(arcs):
    # for 3 arcs around a node, returns list ['a', 'b', 'c'] of adjoining map units
    # 'a' is map unit opposite (not adjoining) arcs[0], 'b' is map unit opposite arcs[1], ...
    mapUnits = []
    if arcs[1].ToFrom == "From":
        mapUnits.append(arcs[1].RMU)
    else:
        mapUnits.append(arcs[1].LMU)
    if arcs[2].ToFrom == "From":
        mapUnits.append(arcs[2].RMU)
    else:
        mapUnits.append(arcs[2].LMU)
    if arcs[0].ToFrom == "From":
        mapUnits.append(arcs[0].RMU)
    else:
        mapUnits.append(arcs[0].LMU)
    return mapUnits


def arcOrder(i):
    # for 4 arcs around a node, indexed 0--3, returns index of arcOpposite and indices of arcsAdjacent
    if i == 0:
        return 2, [1, 3]
    elif i == 1:
        return 3, [0, 2]
    elif i == 2:
        return 0, [1, 3]
    elif i == 3:
        return 1, [0, 2]


def ptsGeographicAzimuth(pt1, pt2):
    dx = pt2[0] - pt1[0]
    dy = pt2[1] - pt1[1]
    azi = math.atan2(dy, dx)
    azi = 90 - math.degrees(azi)
    if azi < 0:
        azi = azi + 360
    return azi


def startEndGeogDirections(lineSeg):
    firstPoint = [lineSeg[0].X, lineSeg[0].Y]
    secondPoint = [lineSeg[1].X, lineSeg[1].Y]
    lpt = len(lineSeg) - 1
    ntlPoint = [lineSeg[lpt - 1].X, lineSeg[lpt - 1].Y]
    lastPoint = [lineSeg[lpt].X, lineSeg[lpt].Y]
    return ptsGeographicAzimuth(firstPoint, secondPoint), ptsGeographicAzimuth(
        lastPoint, ntlPoint
    )


def makeNodeFC(fd, fc):
    addMsgAndPrint("Building feature class " + fc)
    fdfc = os.path.join(fd, fc)
    testAndDelete(fdfc)
    arcpy.CreateFeatureclass_management(fd, fc, "POINT")
    # add fields nArcs, ArcOIDs, ArcTypes, Note
    arcpy.AddField_management(fdfc, "nArcs", "SHORT")
    for f in ["ArcOIDs", "ArcTypes", "Note"]:
        arcpy.AddField_management(fdfc, f, "TEXT", "", "", 500)
    return fdfc


def makeNodeFCXY(fd, fc):
    addMsgAndPrint("Building feature class " + fc)
    fdfc = os.path.join(fd, fc)
    testAndDelete(fdfc)
    arcpy.CreateFeatureclass_management(fd, fc, "POINT")
    return fdfc


def buildHKeyDict(DMU):
    hKeyDict = {}
    hKeyUnits = []
    with arcpy.da.SearchCursor(DMU, ["MapUnit", "HierarchyKey"]) as cursor:
        for row in cursor:
            hKeyDict[row[0]] = row[1]
            hKeyUnits.append([row[1], row[0]])
    hKeyDict[None] = None
    hKeyDict[""] = None
    hKeyUnits.sort()
    sortedUnits = []
    for i in hKeyUnits:
        sortedUnits.append(i[1])

    return hKeyDict, sortedUnits


def youngestMapUnit(mapUnits, hKeyDict):
    # arcpy.AddMessage(f'mapUnits = {mapUnits}')
    # arcpy.AddMessage(hKeyDict)
    # returns youngest map unit in list mapUnits
    ymu = mapUnits[0]
    for mu in mapUnits[1:]:
        # in Python 2.7 None is returned if the dictionary key is not found and 'None < str', evaluates to True.
        # Python 3 is not so forgiving, this produces a TypeError
        # but the code below reproduces the Python 2.7 behavior by returning "" if the dictionary key is not found
        # Because '' and None can be be keys in hKeyDict, mu_hkey = hKeyDict.get(mu, "") was not working, returning None.
        if hKeyDict[ymu] is None:
            ymu_hkey = ""
        else:
            ymu_hkey = hKeyDict[ymu]

        if hKeyDict[mu] is None:
            mu_hkey = ""
        else:
            mu_hkey = hKeyDict[mu]

        if mu_hkey < ymu_hkey:
            ymu = mu
    return ymu


def isCoveringUnit(mu, hKeyDict):
    if mu == None or mu == "":  # stuff outside map, unmapped areas
        return False
    elif hKeyDict[mu] < hKeyTestValue:
        return True
    else:
        return False


def processNodes(nodeList, hKeyDict):
    # nodes is a list of nodes (points at which one or more arcs begins or ends)
    addMsgAndPrint("Processing nodes")
    badNodes = []
    connectFIDs = []  # pairs of OIDs denoting arcs that should be merged
    missingConcealedArcNodes = []
    faultFlipNodes = []
    count1 = 0
    count2 = 0
    count3 = 0
    count4 = 0
    count5 = 0
    for node in nodeList:
        arcs = node[2]
        nArcs = len(arcs)
        ######################
        if nArcs == 1:
            count1 += 1
            if not isFault(arcs[0].Type):  # is a contact
                if arcs[0].isConcealed():
                    node.append("dangling concealed contact")
                    badNodes.append(node)
                else:  # dangling contact
                    node.append("dangling contact")
                    badNodes.append(node)
        ######################
        elif nArcs == 2:
            count2 += 1
            if arcs[0].Type != arcs[1].Type:
                node.append("mismatched Type values")
                badNodes.append(node)
            if arcs[0].IsConc != arcs[1].IsConc:
                node.append("one arc concealed, one not")
                badNodes.append(node)
            if sameArcAttributes(arcs[0], arcs[1]):
                connectFIDs.append([arcs[0].OFID, arcs[1].OFID])
            if (
                isFault(arcs[0].Type)
                and isFault(arcs[1].Type)
                and sameToFrom(arcs[0], arcs[1])
            ):
                node.append(arcs[0].ToFrom + ", " + arcs[1].ToFrom)
                faultFlipNodes.append(node)
        ######################
        elif nArcs == 3:
            count3 += 1
            nCon, conIndx = concealedArcs(arcs)
            same, diff = sameTypeIndices(arcs)
            mapUnits = adjoiningMapUnits(
                arcs
            )  # map units are ordered by not-adjacent arcs
            if nCon in (1, 2):  # 1 or 2 arcs are concealed
                node.append("impossible number of concealed arcs")
                badNodes.append(node)
            elif len(same) < 2:  # no two arcs have same type
                node.append("at least 2 arcs must be same Type")
                badNodes.append(node)
            else:  # all arcs or none are concealed, at least two are of same type
                if nCon == 3:
                    if mapUnits[0] != mapUnits[1] or mapUnits[1] != mapUnits[2]:
                        node.append(
                            "all arcs concealed but bounding map units not all the same"
                        )
                        badNodes.append(node)
                if len(same) == 2:  # only two arcs have same Type
                    if isFault(arcs[same[0]].Type):
                        if sameToFrom(arcs[same[0]], arcs[same[1]]):
                            faultFlipNodes.append(node)
                        elif sameArcAttributes(arcs[same[0]], arcs[same[1]]):
                            connectFIDs.append([arcs[same[0]].OFID, arcs[same[1]].OFID])
                    else:  # two arcs with same Type are not-faults; their shared adjacent poly should be youngest
                        if youngestMapUnit(mapUnits, hKeyDict) == mapUnits[diff]:
                            # if same arc attributes, flag for merge
                            if sameArcAttributes(arcs[same[0]], arcs[same[1]]):
                                connectFIDs.append(
                                    [arcs[same[0]].OFID, arcs[same[1]].OFID]
                                )
                            # test to see if we could add a concealed extension
                            if isCoveringUnit(
                                youngestMapUnit(mapUnits, hKeyDict), hKeyDict
                            ):
                                missingConcealedArcNodes.append(node)
                        else:
                            node.append(
                                "# "
                                + str(mapUnits[diff])
                                + " is not youngest unit in "
                                + str(mapUnits)
                            )
                            badNodes.append(node)
                else:  # all 3 arcs have same Type
                    if isFault(arcs[same[0]].Type):
                        if sameToFrom(arcs[0], arcs[1], arcs[2]):
                            faultFlipNodes.append(node)
                    else:  # all arcs are not-faults
                        # find the arcs that bound the youngest map unit
                        ymu = youngestMapUnit(mapUnits, hKeyDict)
                        youngArcs = [0, 1, 2]
                        youngArcs.remove(mapUnits.index(ymu))
                        if sameArcAttributes(arcs[youngArcs[0]], arcs[youngArcs[1]]):
                            connectFIDs.append(
                                [arcs[youngArcs[0]].OFID, arcs[youngArcs[1]].OFID]
                            )
                        if isCoveringUnit(ymu, hKeyDict) == True:
                            missingConcealedArcNodes.append(node)
        ######################
        elif nArcs == 4:
            nCon, conIndx = concealedArcs(arcs)
            if nCon != 0:
                opp, adj = arcOrder(conIndx[0])
            if nCon > 2:
                node.append("too many concealed arcs")
                badNodes.append(node)
            elif nCon == 2:
                if (
                    arcs[conIndx[0]].Type != arcs[conIndx[1]].Type
                    or arcs[adj[0]].Type != arcs[adj[1]].Type
                ):
                    node.append("opposite arcs must have same Type")
                    badNodes.append(node)
                elif not arcs[
                    opp
                ].isConcealed():  # thus the 2nd concealed arc must be adjacent
                    node.append("adjacent arcs concealed")
                    badNodes.append(node)
                else:  #  geometry is OK. Test for arcs to be merged
                    if sameArcAttributes(arcs[adj[0]], arcs[adj[1]]):
                        connectFIDs.append([arcs[adj[0]].OFID, arcs[adj[1]].OFID])
                    if isFault(arcs[conIndx[0]].Type) and sameToFrom(
                        arcs[conIndx[0]], arcs[opp]
                    ):
                        faultFlipNodes.append(node)
                    elif sameArcAttributes(
                        arcs[conIndx[0]], arcs[opp]
                    ):  # don't merge arcs when one should be flipped
                        connectFIDs.append([arcs[conIndx[0]].OFID, arcs[opp].OFID])
            elif nCon == 1:
                # adjacent arcs must be same-type contacts and opposite arc must be of same type
                if isFault(arcs[adj[0]].Type):
                    node.append(
                        "arcs adjacent to single concealed arc must not be faults"
                    )
                    badNodes.append(node)
                elif arcs[opp].Type != arcs[conIndx[0]].Type:
                    node.append(
                        "concealed arc and unconcealed continuation must be same Type"
                    )
                    badNodes.append(node)
                else:
                    if sameArcAttributes(arcs[adj[0]], arcs[adj[1]]):
                        connectFIDs.append([arcs[adj[0]].OFID, arcs[adj[1]].OFID])
            else:  # nConc = 0
                node.append("4 unconcealed arcs")
                badNodes.append(node)
            count4 += 1
        ######################
        else:  # 5 or more arcs at this node
            count5 += 1
            node.append("too many arcs")
            badNodes.append(node)
    addMsgAndPrint("  " + str(count1) + " 1-arc nodes")
    addMsgAndPrint("  " + str(count2) + " 2-arc nodes")
    addMsgAndPrint("  " + str(count3) + " 3-arc nodes")
    addMsgAndPrint("  " + str(count4) + " 4-arc nodes")
    addMsgAndPrint("  " + str(count5) + " 5+ arc nodes")
    return badNodes, faultFlipNodes, missingConcealedArcNodes, connectFIDs


def insertNodes(ptFc, nodeList):
    # creates insertcursor in pointFc
    addMsgAndPrint("  inserting points into " + os.path.basename(ptFc))
    fields = ["SHAPE@XY", "nArcs", "ArcOIDs", "ArcTypes", "Note"]
    cursor = arcpy.da.InsertCursor(ptFc, fields)
    for node in nodeList:
        narcs = len(node[2])
        arcoids = ""
        arctypes = ""
        for a in node[2]:
            arcoids = arcoids + str(a.OFID) + ", "
            if a.isConcealed() == True:
                concealed = "concealed "
            else:
                concealed = ""
            arctypes = arctypes + concealed + a.Type + ", "
        row = [(node[0], node[1]), narcs, arcoids[:-2], arctypes[:-2], node[3]]
        cursor.insertRow(row)


def insertNodesXY(ptFc, nodeList):
    # creates insertcursor in pointFc
    addMsgAndPrint("  inserting points into " + os.path.basename(ptFc))
    fields = ["SHAPE@XY"]
    cursor = arcpy.da.InsertCursor(ptFc, fields)
    for node in nodeList:
        row = [(node[0], node[1])]
        cursor.insertRow(row)


def getNodes(arcEndPoints):
    #  sorts arcEndPoints into a Python list of nodes
    addMsgAndPrint("Sorting segment endpoints into nodes")
    addMsgAndPrint("  " + str(numberOfRows(arcEndPoints)) + " endpoints")
    nodeList = []
    # open searchCursor on arcEndPoints sorted by POINT_X and POINT_Y
    sql = (None, "ORDER BY POINT_X, POINT_Y")
    fieldNames = ["POINT_X", "POINT_Y"]
    fieldNames.extend(CAF_arc.fieldList)
    lastX = -99999
    lastY = -99999
    nodeArcs = []
    with arcpy.da.SearchCursor(
        arcEndPoints, fieldNames, None, None, False, sql
    ) as cursor:
        for row in cursor:
            x = row[0]
            y = row[1]
            thisArc = CAF_arc(row[2:])
            if abs(x - lastX) < zeroValue and abs(y - lastY) < zeroValue:
                nodeArcs.append(thisArc)
            else:
                if len(nodeArcs) > 0:
                    # note that we sort arcs by LineDir, so that they are in clockwise order
                    nodeArcs.sort(key=operator.attrgetter("LineDir"))
                    nodeList.append([lastX, lastY, nodeArcs])
                lastX = x
                lastY = y
                nodeArcs = [thisArc]
        nodeArcs.sort(key=operator.attrgetter("LineDir"))
        nodeList.append([lastX, lastY, nodeArcs])
    addMsgAndPrint("  " + str(len(nodeList)) + " nodes")
    return nodeList


def planarizeAndGetArcEndPoints(fds, caf, mup, fdsToken):
    # returns a feature class of endpoints of all caf lines, two per planarized line segment
    addMsgAndPrint(
        "Planarizing " + os.path.basename(caf) + " and getting segment endpoints"
    )
    #   add LineID (so we can recover lines after planarization)
    arcpy.AddField_management(caf, "LineID", "LONG")
    arcpy.CalculateField_management(caf, "LineID", "!OBJECTID!", "PYTHON_9.3")
    # planarize CAF by FeatureToLine
    addMsgAndPrint("  planarizing caf")
    planCaf = caf + "_xxx_plan"
    testAndDelete(planCaf)
    arcpy.FeatureToLine_management(caf, planCaf)
    #   planarize CAF (by IDENTITY with MUP)
    addMsgAndPrint("  IDENTITYing caf with mup")
    cafp = caf + "_planarized"
    testAndDelete(cafp)
    arcpy.Identity_analysis(planCaf, mup, cafp, "ALL", "", "KEEP_RELATIONSHIPS")
    # delete extra fields
    addMsgAndPrint("  deleting extra fields")
    fns = fieldNameList(cafp)
    deleteFields = []
    for f in fieldNameList(mup):
        if f != "MapUnit":
            for hf in ("RIGHT_" + f, "LEFT_" + f):
                if hf in fns:
                    deleteFields.append(hf)
    arcpy.DeleteField_management(cafp, deleteFields)
    #   calculate azimuths startDir and endDir
    addMsgAndPrint("  adding StartAzimuth and EndAzimuth")
    for f in ("LineDir", "StartAzimuth", "EndAzimuth"):
        arcpy.AddField_management(cafp, f, "FLOAT")
    arcpy.AddField_management(cafp, "ToFrom", "TEXT", "", "", 4)
    fields = ["SHAPE@", "StartAzimuth", "EndAzimuth"]
    with arcpy.da.UpdateCursor(cafp, fields) as cursor:
        for row in cursor:
            lineSeg = row[0].getPart(0)
            row[1], row[2] = startEndGeogDirections(lineSeg)
            cursor.updateRow(row)
    #   make endpoint feature class
    addMsgAndPrint("  converting line ends to points")
    arcEndPoints = (
        fds + "/" + fdsToken + "xxx_EndPoints"
    )  # will be a feature class in fds
    arcEndPoints2 = arcEndPoints + "_end"
    testAndDelete(arcEndPoints)
    arcpy.FeatureVerticesToPoints_management(cafp, arcEndPoints, "START")
    arcpy.CalculateField_management(arcEndPoints, "LineDir", "!StartAzimuth!", "PYTHON")
    arcpy.CalculateField_management(arcEndPoints, "ToFrom", '"From"', "PYTHON")
    testAndDelete(arcEndPoints2)
    arcpy.FeatureVerticesToPoints_management(cafp, arcEndPoints2, "END")
    arcpy.CalculateField_management(arcEndPoints2, "LineDir", "!EndAzimuth!", "PYTHON")
    arcpy.CalculateField_management(arcEndPoints2, "ToFrom", '"To"', "PYTHON")
    arcpy.Append_management(arcEndPoints2, arcEndPoints)
    testAndDelete(arcEndPoints2)
    #  delete some more fields
    deleteFields = [
        "EndAzimuth",
        "StartAzimuth",
        "LEFT_MapUnitPolys",
        "RIGHT_MapUnitPolys",
    ]
    arcpy.DeleteField_management(arcEndPoints, deleteFields)
    addMsgAndPrint("  adding POINT_X and POINT_Y")
    arcpy.AddXY_management(arcEndPoints)
    testAndDelete(planCaf)
    return cafp, arcEndPoints


def unplanarize(cafp, caf, connectFIDs):
    addMsgAndPrint("Unplanarizing " + os.path.basename(cafp))
    # add NewLineID to cafp
    arcpy.AddField_management(cafp, "NewLineID", "LONG")
    # go through connectFIDs to set NewLineID values
    addMsgAndPrint("  building newLineIDs dictionary")
    newLineIDs = {}
    for pair in connectFIDs:
        f1 = pair[0]
        f2 = pair[1]
        if f1 in newLineIDs:
            if f2 in newLineIDs:  # both keys in dict, set all values of f2 = f1
                for i in list(newLineIDs.keys()):
                    if newLineIDs[i] == f2:
                        newLineIDs[i] = newLineIDs[f1]
            else:  # only f1 is in newLineIDs.keys()
                newLineIDs[f2] = newLineIDs[f1]
        elif f2 in newLineIDs:  # only f2 in newLineIDs.keys()
            newLineIDs[f1] = newLineIDs[f2]
        else:  # neither f1 nor f2 in newLineIDs.keys()
            newLineIDs[f1] = f1
            newLineIDs[f2] = f1
    addMsgAndPrint("  " + str(len(newLineIDs)) + " entries in newLineIDs")
    # update cursor on cafp, if newLineIDs.has_key(caf.OFID): NewLineID = newLineIDs(caf.OFID) else NewLineID = caf.OFID
    addMsgAndPrint("  setting NewLineID values")
    with arcpy.da.UpdateCursor(cafp, ["OBJECTID", "NewLineID"]) as cursor:
        for row in cursor:
            if row[0] in newLineIDs:
                row[1] = newLineIDs[row[0]]
            else:
                row[1] = row[0]
            cursor.updateRow(row)
    # dissolve cafp on GeMS attribs and NewLineID to get cafu
    cafu = cafp.replace("planarized", "unplanarized")
    addMsgAndPrint("  dissolving to get " + os.path.basename(cafu))
    testAndDelete(cafu)
    dissolveFields = gemsFields
    if "Notes" in fieldNameList(cafp):
        dissolveFields.append("Notes")
    dissolveFields.append("NewLineID")
    arcpy.Dissolve_management(cafp, cafu, dissolveFields, "", "", "UNSPLIT_LINES")
    # delete NewLineID from caf_unplanarized. maybe add _ID field??
    arcpy.DeleteField_management(cafu, "NewLineID")
    addMsgAndPrint(str(numberOfRows(caf)) + " arcs in " + os.path.basename(caf))
    addMsgAndPrint(str(numberOfRows(cafp)) + " arcs in " + os.path.basename(cafp))
    addMsgAndPrint(str(numberOfRows(cafu)) + " arcs in " + os.path.basename(cafu))

    txtPath = os.path.join(outWksp, "connectedFIDs.txt")
    outTxt = open(txtPath, "w")
    connectFIDs.sort()
    for aline in connectFIDs:
        outTxt.write(
            str(aline)
            + "  "
            + str(newLineIDs[aline[0]])
            + " "
            + str(newLineIDs[aline[1]])
            + "\n"
        )
    outTxt.close()

    return cafu


### WRITE OUTPUT ADJACENCY TABLES
def writeLRTable(outHtml, linesDict, dmuUnits, tagRoot):
    # get mapunits that participate in linesDict
    lmus = []
    rmus = []
    for key in linesDict:
        uns = key.split("|")
        lmus.append(uns[0])
        rmus.append(uns[1])
    lMapUnits = []
    rMapUnits = []
    for unit in dmuUnits:
        if unit in lmus:
            lMapUnits.append(unit)
        if unit in rmus:
            rMapUnits.append(unit)
    for unit in lmus:  # catch units not in dmuUnits
        if not unit in lMapUnits:
            lMapUnits.append(unit)
    for unit in rmus:
        if not unit in rMapUnits:
            rMapUnits.append(unit)
    # now write table guts
    outHtml.write('<table border="1" cellpadding="2" cellspacing="2">\n  <tbody>\n')
    # write heading row
    outHtml.write("<tr>\n  <td></td>\n")
    for rmu in rMapUnits:
        outHtml.write('  <td align="center">' + rmu + "</td>\n")
    outHtml.write("</tr>\n")
    for lmu in lMapUnits:
        outHtml.write('  <tr>\n    <td align="center">' + lmu + "</td>\n")
        for rmu in rMapUnits:
            if lmu + "|" + rmu in linesDict:
                nArcs, arcLength = linesDict[lmu + "|" + rmu]
                if lmu == rmu and tagRoot == "internalContacts":
                    anchorStart = '<a href="#' + tagRoot + lmu + rmu + '">'
                    anchorEnd = "</a"
                elif lmu != rmu and tagRoot == "badConcealed":
                    anchorStart = '<a href="#' + tagRoot + lmu + rmu + '">'
                    anchorEnd = "</a"
                else:
                    anchorStart = ""
                    anchorEnd = ""
                textStr = (
                    anchorStart
                    + str(nArcs)
                    + "<br><i><small>"
                    + "%.1f" % (arcLength)
                    + "</i></small>"
                    + anchorEnd
                )
            else:
                textStr = "--"
            if lmu == rmu:
                bgColor = ' bgcolor="#ffcc99"'
            else:
                bgColor = ""
            outHtml.write(
                '      <td align="center"' + bgColor + ">" + textStr + "</td>\n"
            )
        outHtml.write("    </tr>\n")
    outHtml.write("  </tbody>\n</table>")


def writeLineAdjacencyTable(tableName, outHtml, lineDict, dmuUnits, tagRoot):
    addMsgAndPrint("  writing line-adjacency table " + tableName)
    outHtml.write("<b>" + tableName + "</b><br>\n")
    outHtml.write('<table border="1" cellpadding="2" cellspacing="2">\n  <tbody>\n')
    outHtml.write('    <tr><td></td><td align="center">right-side map unit</td></tr>\n')
    outHtml.write('    <tr><td align="center">left-<br>side<br>map<br>unit</td><td>\n')
    writeLRTable(outHtml, lineDict, dmuUnits, tagRoot)
    outHtml.write("      </td></tr>\n  </tbody>\n</table>")


def addRowToDict(lr, thisArc, arcLength, lineDict):
    if lr in lineDict:
        numArcs, sumArcLength = lineDict[lr]
        numArcs = numArcs + 1
        sumArcLength = float(sumArcLength) + float(arcLength)
        lineDict[lr] = [numArcs, sumArcLength]
    else:
        lineDict[lr] = [1, float(arcLength)]


def adjacencyTables(cafp, sortedUnits, outHtml):
    addMsgAndPrint("Building dictionaries of line adjacencies")
    concealedLinesDict = {}
    faultLinesDict = {}
    contactLinesDict = {}

    # next two lists will store lists that consist of a [CAF_arc object, the length of the line]
    internalContacts = []
    badConcealed = []

    fields = CAF_arc.fieldList
    fields.remove("ORIG_FID")
    fields.extend(["OBJECTID", "Shape_Length"])
    with arcpy.da.SearchCursor(cafp, fields) as cursor:
        for row in cursor:
            thisArc = CAF_arc(row[:-1])
            alength = row[12]
            try:
                lr = thisArc.LMU + "|" + thisArc.RMU
            except:
                addMsgAndPrint(str(row))
                lr = "--|--"
            if thisArc.isConcealed():  # IsConcealed = Y
                addRowToDict(lr, thisArc, alength, concealedLinesDict)
                if thisArc.LMU != thisArc.RMU:
                    badConcealed.append([thisArc, alength])
            elif isFault(thisArc.Type):  # it's a fault
                addRowToDict(lr, thisArc, alength, faultLinesDict)
            else:
                if isContact(thisArc.Type):
                    addRowToDict(lr, thisArc, alength, contactLinesDict)
                if thisArc.LMU == thisArc.RMU:
                    internalContacts.append([thisArc, alength])
    return (
        badConcealed,
        internalContacts,
        concealedLinesDict,
        contactLinesDict,
        faultLinesDict,
    )


def translateNone(s):
    if s == None:
        return "--"
    else:
        return s


def contactListWrite(conList, outHtml, tagRoot):
    # conList.sort()
    # sort() does not work the same way it did in 2.7. Have to be more explicit about how to sort a list
    # consisting of lists of [class object, integer]
    conlist_sorted = sorted(conList, key=lambda x: x[0].Type)

    outHtml.write('<table border="1" cellpadding="2" cellspacing="2">\n  <tbody>\n')
    outHtml.write(
        "  <tr><td>L MapUnit</td><td>R MapUnit</td><td>Type</td><td>IsConcealed</td><td>OBJECTID</td><td>Shape_Length</td></tr>\n"
    )
    lastArcLMU = ""
    lastArcRMU = ""
    anchorString = "-"
    # for arcLine in conList:
    for arcLine in conlist_sorted:
        outHtml.write("  <tr>\n")
        anArc = arcLine[0]
        alength = arcLine[1]
        if anArc.LMU != lastArcLMU or anArc.RMU != lastArcRMU:
            lastArcLMU = translateNone(anArc.LMU)
            lastArcRMU = translateNone(anArc.RMU)
            # addMsgAndPrint(str(aRow))
            anchorString = '<a name="' + tagRoot + lastArcLMU + lastArcRMU + '"></a>'
        for i in (anArc.LMU, anArc.RMU, anArc.Type, anArc.IsConc, anArc.OFID):
            if i != anArc.LMU:
                anchorString = ""
            outHtml.write("    <td>" + anchorString + str(i) + "</td>\n")
        outHtml.write(
            '    <td style="text-align:right">' + "%.1f" % (alength) + "</td>\n"
        )
        outHtml.write("  </tr>\n")
    outHtml.write("  </body></table>\n")


def findDupPts(inFds, outFds):
    addMsgAndPrint("Looking for duplicate points")
    duplicatePoints = []
    arcpy.env.workspace = os.path.dirname(inFds)
    ptFcs1 = arcpy.ListFeatureClasses("", "POINT", os.path.basename(inFds))
    ptFcs2 = []
    for fc in ptFcs1:
        notEdit = True
        for pfx in editPrefixes:
            if fc.find(pfx) > -1:
                notEdit = False
        if notEdit:
            ptFcs2.append(fc)
    for fc in ptFcs2:
        addMsgAndPrint("  finding duplicate records in " + fc)
        newTb = os.path.dirname(outFds) + "/dups_" + fc
        testAndDelete(newTb)
        dupFields = ["Shape"]
        allFields1 = arcpy.ListFields(fc)
        allFields = []
        for fld in allFields1:
            allFields.append(fld.name)
        for aF in ("Type", "Azimuth", "Inclination"):
            if aF in allFields:
                dupFields.append(aF)
        addMsgAndPrint("    fields to be compared: " + str(dupFields))
        arcpy.FindIdentical_management(
            inFds + "/" + fc, newTb, dupFields, "", "", "ONLY_DUPLICATES"
        )
        addMsgAndPrint("    dups_" + fc + ": " + str(numberOfRows(newTb)) + " rows")
        if numberOfRows(newTb) == 0:
            testAndDelete(newTb)
        else:
            duplicatePoints.append(
                "&nbsp;&nbsp; "
                + str(numberOfRows(newTb))
                + " rows in "
                + os.path.basename(newTb)
            )

    return duplicatePoints


def esriTopology(outFds, caf, mup):
    addMsgAndPrint("Checking topology of " + os.path.basename(outFds))
    # First delete any existing topology
    ourTop = os.path.basename(outFds) + "_topology"
    testAndDelete(os.path.join(outFds, ourTop))
    # create topology
    addMsgAndPrint(f"  creating topology {ourTop}")
    arcpy.CreateTopology_management(outFds, ourTop)
    ourTop = os.path.join(outFds, ourTop)
    # add feature classes to topology
    arcpy.AddFeatureClassToTopology_management(ourTop, caf, 1, 1)
    if arcpy.Exists(mup):
        arcpy.AddFeatureClassToTopology_management(ourTop, mup, 2, 2)
    # add rules to topology
    addMsgAndPrint("  adding rules to topology:")
    for aRule in (
        "Must Not Overlap (Line)",
        "Must Not Self-Overlap (Line)",
        "Must Not Self-Intersect (Line)",
        "Must Be Single Part (Line)",
    ):
        addMsgAndPrint(f"    {aRule}")
        arcpy.AddRuleToTopology_management(ourTop, aRule, caf)
    for aRule in ("Must Not Overlap (Area)", "Must Not Have Gaps (Area)"):
        addMsgAndPrint(f"    {aRule}")
        arcpy.AddRuleToTopology_management(ourTop, aRule, mup)
    addMsgAndPrint("    Boundary Must Be Covered By (Area-Line)")
    arcpy.AddRuleToTopology_management(
        ourTop, "Boundary Must Be Covered By (Area-Line)", mup, "", caf
    )
    # validate topology
    addMsgAndPrint("  validating topology")
    arcpy.ValidateTopology_management(ourTop)
    nameToken = os.path.basename(caf).replace("ContactsAndFaults", "")
    if nameToken == "":
        nameToken = "GeologicMap"
    nameToken = "errors_" + nameToken + "Topology"
    for sfx in ("_point", "_line", "_poly"):
        testAndDelete(outFds + "/" + nameToken + sfx)
    # export topology errors
    addMsgAndPrint("  exporting topology errors")
    arcpy.ExportTopologyErrors_management(ourTop, outFds, nameToken)
    topoStuff = []
    topoStuff.append(
        '<i>Note that the map boundary commonly results in one "Must Not Have Gaps" line error</i>'
    )
    for sfx in ("_point", "_line", "_poly"):
        fc = outFds + "/" + nameToken + sfx
        topoStuff.append(
            space4
            + str(numberOfRows(fc))
            + " rows in <b>"
            + os.path.basename(fc)
            + "</b>"
        )
        addMsgAndPrint(
            "    " + str(numberOfRows(fc)) + " rows in " + os.path.basename(fc)
        )
        if numberOfRows(fc) == 0:
            testAndDelete(fc)
    return topoStuff


################################

addMsgAndPrint(versionString)
#### get inputs
inFds = sys.argv[1]
hKeyTestValue = sys.argv[2]

inGdb = os.path.dirname(inFds)

outWksp = inGdb[:-4] + "_Topology"
if not os.path.exists(outWksp):
    addMsgAndPrint("Making directory " + outWksp)
    os.mkdir(outWksp)
else:
    if not os.path.isdir(outWksp):
        addMsgAndPrint("Oops, " + md + " exists but is a file")
        forceExit()

inCaf = getCaf(inFds)
fdsToken = os.path.basename(inCaf).replace("ContactsAndFaults", "")
inMup = inCaf.replace("ContactsAndFaults", "MapUnitPolys")
zeroValue = 2 * arcpy.Describe(inCaf).spatialReference.XYTolerance
# hKeyTestValue = '2'
DMU = inGdb + "/DescriptionOfMapUnits"
outGdbName = os.path.basename(inGdb)[:-4] + "_TopologyCheck.gdb"
outGdb = os.path.join(outWksp, outGdbName)
outFdsName = os.path.basename(inFds)
outFds = os.path.join(outGdb, outFdsName)
addMsgAndPrint(" ")
addMsgAndPrint(
    "Writing to "
    + outGdb
    + ". Note that nodes within "
    + str(zeroValue)
    + " map units of each other are considered identical."
)
addMsgAndPrint(" ")

outHtml = open(os.path.join(outWksp, outFdsName + ".html"), "w")
hKeyDict, sortedUnits = buildHKeyDict(DMU)

### copy inputs to new gdb/feature dataset
if not arcpy.Exists(outWksp):
    os.mkdir(outWksp)
if not arcpy.Exists(outGdb):
    arcpy.CreateFileGDB_management(outWksp, outGdbName)
if not arcpy.Exists(outFds):
    arcpy.CreateFeatureDataset_management(outGdb, outFdsName, inFds)

arcpy.env.workspace = outFds
topologies = arcpy.ListDatasets("", "Topology")
for t in topologies:
    testAndDelete(t)

for infc in (inCaf, inMup):
    outfc = os.path.join(outFds, os.path.basename(infc))
    testAndDelete(outfc)
    arcpy.Copy_management(infc, outfc)
    if infc == inCaf:
        caf = outfc
    else:
        mup = outfc

### TOPOLOGY (no mup gaps or overlaps;
#    no line overlaps, self-overlaps, or self-intersections; mup boundaries covered by CAF lines
topoStuff = esriTopology(outFds, caf, mup)

### NODES
planarizedCAF, arcEndPoints = planarizeAndGetArcEndPoints(outFds, caf, mup, fdsToken)

# sort arcEndPoints into list of nodes
nodeList = getNodes(arcEndPoints)
# assign nodes to various groups
badNodes, faultFlipNodes, missingConcealedArcNodes, connectFIDs = processNodes(
    nodeList, hKeyDict
)
addMsgAndPrint("Bad nodes: " + str(len(badNodes)))
addMsgAndPrint("Fault-flip nodes: " + str(len(faultFlipNodes)))
addMsgAndPrint("Missing concealed-arc nodes: " + str(len(missingConcealedArcNodes)))
addMsgAndPrint("ConnectFIDs: " + str(len(connectFIDs)))
testAndDelete(arcEndPoints)

### MAKE OUTPUT FEATURE CLASSES
badNodesFC = makeNodeFC(outFds, "errors_" + fdsToken + "_BadNodes")
insertNodes(badNodesFC, badNodes)

missingConcealedFC = makeNodeFCXY(outFds, fdsToken + "MissingConcealedCAF_nodes")
insertNodesXY(missingConcealedFC, missingConcealedArcNodes)
faultFlipFC = makeNodeFCXY(outFds, "errors_" + fdsToken + "_FaultFlipNodes")
insertNodesXY(faultFlipFC, faultFlipNodes)

### UNPLANARIZE
unplanarizedCAF = unplanarize(planarizedCAF, inCaf, connectFIDs)

### ARC ADJACENCY
(
    badConcealed,
    internalContacts,
    concealedLinesDict,
    contactLinesDict,
    faultLinesDict,
) = adjacencyTables(planarizedCAF, sortedUnits, outHtml)

### DUPLICATE POINTS
dupPoints = findDupPts(inFds, outFds)

### WRITE OUTPUT
addMsgAndPrint("Writing output")
outHtml.write(htmlStart)
outHtml.write("<h2>Topology Check</h2>\n")
outHtml.write(
    "<h2>"
    + os.path.basename(inGdb)
    + ", <i>feature dataset</i> "
    + outFdsName
    + "</h2>\n"
)
outHtml.write(
    "File written by " + versionString + " at " + str(time.ctime()) + "<br>\n"
)
outHtml.write("Input database: <b>" + inGdb + "</b><br>\n")
outHtml.write(
    "Output database: <b>"
    + outGdbName
    + "</b> within folder <b>"
    + outWksp
    + "</b>.<br>\n"
)
outHtml.write("<blockquote><i>" + ValidateTopologyNote + "</blockquote></i>\n")

outHtml.write("<h3>ESRI Line-Polygon Topology</h3>\n")
for a in topoStuff:
    outHtml.write(a + "<br>\n")

outHtml.write("<h3>Node Topology</h3>\n")
outHtml.write(str(len(badNodes)) + " nodes that may have bad geometry<br>\n")
outHtml.write(
    space4
    + " See <b>"
    + os.path.join(outFdsName, os.path.basename(badNodesFC))
    + "</b><br>\n"
)
outHtml.write(
    str(len(faultFlipNodes))
    + " nodes where fault direction changes. These are likely to be errors<br>\n"
)
outHtml.write(
    space4
    + " See <b>"
    + os.path.join(outFdsName, os.path.basename(faultFlipFC))
    + "</b><br>\n"
)
outHtml.write(
    str(len(missingConcealedArcNodes))
    + " nodes where a concealed contact or fault continuation could be added<br>\n"
)
outHtml.write(
    space4
    + " See <b>"
    + os.path.join(outFdsName, os.path.basename(missingConcealedFC))
    + "</b><br>\n"
)

outHtml.write("<h3>MapUnits Adjacent to CAF Lines</h3>\n")
outHtml.write(
    "See feature class <b>"
    + os.path.join(outFdsName, os.path.basename(planarizedCAF))
    + "</b> for ContactsAndFaults arcs attributed with adjacent polygon information.<br>\n"
)
outHtml.write(
    "<i>In tables below, upper cell value is number of arcs. Lower cell value is cumulative arc length in map units.</i><br><br>\n"
)
writeLineAdjacencyTable(
    "Concealed contacts and faults",
    outHtml,
    concealedLinesDict,
    sortedUnits,
    "badConcealed",
)
outHtml.write("<br>\n")
writeLineAdjacencyTable(
    "Contacts (not concealed)",
    outHtml,
    contactLinesDict,
    sortedUnits,
    "internalContacts",
)
outHtml.write("<br>\n")
writeLineAdjacencyTable(
    "Faults (not concealed)", outHtml, faultLinesDict, sortedUnits, ""
)
outHtml.write("<br><b>Bad concealed contacts and faults</b><br>\n")
if len(badConcealed) > 0:
    outHtml.write(
        space4
        + "See feature class <b>"
        + os.path.join(outFdsName, os.path.basename(planarizedCAF))
        + "</b><br>\n"
    )
    contactListWrite(badConcealed, outHtml, "badConcealed")
else:
    outHtml.write(space4 + "No bad concealed contacts or faults")
outHtml.write("<br><b>Internal Contacts</b><br>\n")
if len(internalContacts) > 0:
    outHtml.write(
        space4
        + "See feature class <b>"
        + os.path.join(outFdsName, os.path.basename(planarizedCAF))
        + "</b><br>\n"
    )
    contactListWrite(internalContacts, outHtml, "internalContacts")
else:
    outHtml.write(space4 + "No internal contacts")

outHtml.write("<h3>Duplicate Points</h3>\n")
if len(dupPoints) == 0:
    outHtml.write("No duplicate points found<br>\n")
else:
    for a in dupPoints:
        outHtml.write(a + "<br>\n")

outHtml.write(htmlEnd)
outHtml.close()
addMsgAndPrint("DONE!")
