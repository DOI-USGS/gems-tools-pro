# args inGdb, validateAllFdSets, inFdSets, validateLinesAndPolys, validateNodes
#    validateLineDirs, matchMapUnits, findPointDups, smallFeatures

import arcpy, os.path, time, sys, math
from GeMS_utilityFunctions import *

# minor changes to CAF node check logic
# modified to explicitly disable M and Z values in FeatureToLine output, circa line 585
# further improved CAF node check
# fixed Fault Direction
# 11 December 2017  Improved node-check logic, added pre-clean for layer and table views, add cleanup for layer and table views
# 17 July 2019: Tool ran in ArcGIS Pro without errors after updating to Python3 with 2to3.
#   Amazing. No other edits done. Renamed to GeMS_TopologyCheck_AGP2.py

versionString = 'GeMS_TopologyCheck_AGP2.py, version of 7 July 2019'

tooSmallAreaMM2 = 12 # minimum mapunit poly area in mm2
tooSkinnyWidthMM = 2   # minimum mapunit poly "width" in mm
tooShortMM = 4           # minimum arc length in mm

searchRadius = 0.02  # distance, in map units, within which nodes are considered identical

debug1 = False
debug2 = False
debug3 = False

############# HTML file functions ####################
htmlStart = """<html>\n
    <head>\n
        <meta http-equiv="content-type" content="text/html; charset=ISO-8859-1">\n
    </head>\n
        <body>\n"""
htmlEnd = '         </body>\n   </html>\n'
ValidateTopologyNote = """Note that not all geologic-map topology errors will be identified in this report.
Some of the features identified here may not be errors. Use your judgement!"""

def writeHeader(outHtml,inGdb):
    outHtml.write(htmlStart)
    outHtml.write('<h1>Topology report, '+os.path.basename(inGdb)+'</h1>\n')
    timeStamp = str(time.ctime())
    outHtml.write(inGdb+' &nbsp;&nbsp;&nbsp;'+' last modified '+time.ctime(os.path.getmtime(inGdb))+'<br>\n')
    outHtml.write('This file created by '+versionString+', at '+timeStamp+'<br>\n')
    outHtml.write('<blockquote><i>'+ValidateTopologyNote+'</blockquote></i>\n')

def html_writeFreqTable(outHtml,fc,fields):
    # make frequency table
    fds = os.path.dirname(fc)
    freqTable = fds+'xxxFreqTable'
    testAndDelete(freqTable)
    if debug1:
        addMsgAndPrint(fc+'  '+str(fields))
    arcpy.Frequency_analysis (fc, freqTable, fields)
    fieldNames = ['FREQUENCY']
    for afield in fields:
        fieldNames.append(afield)
    if numberOfRows(freqTable) > 0:
        with arcpy.da.SearchCursor(freqTable, fieldNames) as cursor:
            for row in cursor:
                spaceString = ''
                for i in range(len(str(row[0])), 6):
                    spaceString = spaceString+'&nbsp;'
                outHtml.write('<tt>'+spaceString+' '+str(row[0])+'&nbsp;&nbsp; ')
                for i in range(1,len(row)):
                    outHtml.write(str(row[i])+'&nbsp;&nbsp; ')
                outHtml.write('</tt><br>\n')
    else:
        outHtml.write('<tt>&nbsp;&nbsp;&nbsp; no errors</tt><br>\n')
    if debug2 and numberOfRows(fc) > 0:
        addMsgAndPrint('input fc = '+fc)
        addMsgAndPrint('input fc field names = '+str(fieldNameList(fc)))
        addMsgAndPrint('# rows input fc = '+str(numberOfRows(fc)))
        addMsgAndPrint(' frequency fields = '+str(fields))
        addMsgAndPrint('frequency table = '+freqTable)
        addMsgAndPrint('freq table field names = '+str(fieldNameList(freqTable)))
        addMsgAndPrint('# rows freq table = '+str(numberOfRows(freqTable)))
        addMsgAndPrint(' ')
    testAndDelete(freqTable)

def numberMapBoundaryArcs(arcTypes):
    # we assume map boundary arcs, and only map boundary arcs, have Type values that contain 'map' or 'neatline'
    lc = arcTypes.lower()
    return lc.count('map') + lc.count('neatline')

def writeLRTable(outHtml,linesDict,dmuUnits,tagRoot):
    # get mapunits that participate in linesDict
    lmus = []
    rmus = []
    for key in linesDict:
        uns = key.split('|')
        lmus.append(uns[0])
        rmus.append(uns[1])
    lMapUnits = []
    rMapUnits = []
    for unit in dmuUnits:
        if unit in lmus:
            lMapUnits.append(unit)
        if unit in rmus:
            rMapUnits.append(unit)
    for unit in lmus:
        if not unit in lMapUnits: lMapUnits.append(unit)
    for unit in rmus:
        if not unit in rMapUnits: rMapUnits.append(unit)
    if debug3:
        addMsgAndPrint('dmuUnits = '+str(dmuUnits))
        addMsgAndPrint('lmus = '+str(lmus))
        addMsgAndPrint('rmus = '+str(rmus))
        addMsgAndPrint('rMapUnits = '+str(rMapUnits))
        addMsgAndPrint('lMapUnits = '+str(lMapUnits))
    # now write table guts
    outHtml.write('<table border="1" cellpadding="2" cellspacing="2">\n  <tbody>\n')
    # write heading row
    outHtml.write('<tr>\n  <td></td>\n')
    for rmu in rMapUnits:
        outHtml.write('  <td align="center">'+rmu+'</td>\n')
    outHtml.write('</tr>\n')
    for lmu in lMapUnits:
        outHtml.write('  <tr>\n    <td align="center">'+lmu+'</td>\n')
        for rmu in rMapUnits:
            if lmu+'|'+rmu in linesDict:
                nArcs,arcLength = linesDict[lmu+'|'+rmu]
                if lmu == rmu and tagRoot == 'internalContacts':
                    anchorStart = '<a href="#'+tagRoot+lmu+rmu+'">'
                    anchorEnd = '</a'
                elif lmu != rmu and tagRoot == 'badConcealed':
                    anchorStart = '<a href="#'+tagRoot+lmu+rmu+'">'
                    anchorEnd = '</a'
                else:
                    anchorStart = ''
                    anchorEnd = ''
                textStr = anchorStart+str(nArcs)+'<br><i><small>'+'%.1f' % (arcLength)+'</i></small>'+anchorEnd
            else:
                textStr = '--'
            if lmu == rmu: bgColor = ' bgcolor="#ffcc99"'
            else: bgColor = ''
            outHtml.write('      <td align="center"'+bgColor+'>'+textStr+'</td>\n')
        outHtml.write('    </tr>\n')
    outHtml.write('  </tbody>\n</table>')

def writeLineAdjacencyTable(tableName,outHtml,lineDict,dmuUnits,tagRoot):
    outHtml.write('<b>'+tableName+'</b><br>\n')
    outHtml.write('<table border="1" cellpadding="2" cellspacing="2">\n  <tbody>\n')
    outHtml.write('    <tr><td></td><td align="center">right-side map unit</td></tr>\n')
    outHtml.write('    <tr><td align="center">left-<br>side<br>map<br>unit</td><td>\n')
    writeLRTable(outHtml,lineDict,dmuUnits,tagRoot)
    outHtml.write('      </td></tr>\n  </tbody>\n</table>')

def translateNone(s):
    if s == None:
        return '--'
    else:
        return s

def contactListWrite(conList,outHtml,tagRoot):
    conList.sort()
    outHtml.write('<table border="1" cellpadding="2" cellspacing="2">\n  <tbody>\n')
    outHtml.write('  <tr><td>L MapUnit</td><td>R mapunit</td><td>Type</td><td>IsConcealed</td><td>OBJECTID</td><td>Shape_Length</td></tr>\n')
    lastARow0 = ''; lastARow1 = ''; anchorString = '-'
    for aRow in conList:
        outHtml.write('  <tr>\n')
        if aRow[0] != lastARow0 or aRow[1] != lastARow1:
            lastARow0 = translateNone(aRow[0])
            lastARow1 = translateNone(aRow[1])
            #addMsgAndPrint(str(aRow))
            anchorString = '<a name="'+tagRoot+lastARow0+lastARow1+'"></a>'
        for i in range(0,len(aRow)):
            if i != 0: anchorString = ''
            outHtml.write('    <td>'+anchorString+str(aRow[i])+'</td>\n')
        outHtml.write('  </tr>\n')
    outHtml.write('  </body></table>\n')

################  other functions ###################
def addRowToDict(lr,row,lineDict):
    if lr in lineDict:
        numArcs,sumArcLength = lineDict[lr]
        numArcs = numArcs+1
        sumArcLength = sumArcLength + row[4]
        lineDict[lr] = [numArcs,sumArcLength]
    else:
        lineDict[lr] = [1,row[4]]

def isFlippedNode(NodeTypes):
    # NodeTypes is a list of 'TO', 'FROM'
    nTo = 0
    nFrom = 0
    for nd in NodeTypes:
        if nd == 'TO': nTo = nTo+1
        elif nd == 'FROM': nFrom = nFrom+1
    if abs(nTo-nFrom) > 0:
        return True
    else:
        return False

def pointPairGeographicAzimuth(pt1,pt2):
    dx = pt2[0]-pt1[0]
    dy = pt2[1]-pt1[1]
    azi = math.atan2(dy,dx)
    azi = 90 - math.degrees(azi)
    if azi < 0:
        azi = azi + 360
    return azi

def startGeogDirection(lineSeg):
    firstPoint = [lineSeg[0].X,lineSeg[0].Y]
    secondPoint = [lineSeg[1].X,lineSeg[1].Y]
    return pointPairGeographicAzimuth(firstPoint,secondPoint)

def endGeogDirection(lineSeg):
    lpt = len(lineSeg) - 1
    ntlPoint = [lineSeg[lpt-1].X,lineSeg[lpt-1].Y]
    lastPoint= [lineSeg[lpt].X,lineSeg[lpt].Y]
    return pointPairGeographicAzimuth(lastPoint,ntlPoint)

def concealedArcNumber(arcs):
    # arcs is an array of arc characteristics. 5th value (index = 4)
    #   is IsConcealed (=Y or N)
    # This function returns the index number of the 1st element in arcs
    #  that has arcs[i][4] = 'Y'  (IsConcealed)
    i = 0
    while arcs[i][4].upper() == 'N':
        i = i+1
        if i > 4:
            addMsgAndPrint('Problem in routine concealedArcNumber')
            addMsgAndPrint(str(arcs))
            raise arcpy.ExecuteError
    return i
    
############ find duplicate points #########################################
def findDupPts(inFds,outFds,outHtml):
    arcpy.env.workspace = os.path.dirname(inFds)
    ptFcs1 = arcpy.ListFeatureClasses('','POINT',os.path.basename(inFds))
    ptFcs2 = []
    for fc in ptFcs1:
        notEdit = True
        for pfx in editPrefixes:
            if fc.find(pfx) > -1:
                notEdit = False
        if notEdit: ptFcs2.append(fc)
    outHtml.write('<h3>Duplicate point features</h3>\n')
    for fc in ptFcs2:
        addMsgAndPrint('  finding duplicate records in '+fc)
        newTb = os.path.dirname(outFds)+'/dups_'+fc
        testAndDelete(newTb)
        dupFields = ['Shape']
        allFields1 = arcpy.ListFields(fc)
        allFields = []
        for fld in allFields1:
            allFields.append(fld.name)
        for aF in ('Type','Azimuth','Inclination'):
            if aF in allFields:
                dupFields.append(aF)
        addMsgAndPrint('    fields to be compared: '+str(dupFields))
        arcpy.FindIdentical_management(inFds+'/'+fc,newTb,dupFields,'','','ONLY_DUPLICATES')
        addMsgAndPrint('    dups_'+fc+': '+str(numberOfRows(newTb))+' rows')
        if numberOfRows(newTb) == 0:
            testAndDelete(newTb)
        else:
            outHtml.write('&nbsp;&nbsp; '+str(numberOfRows(newTb))+' rows in '+os.path.basename(newTb)+'<br>\n')


########### find nodes where line directions change #########################
##                faults only!
def lineDirections(inFds,outFds,outHtml):
    inCaf = os.path.basename(getCaf(inFds))
    nameToken = inCaf.replace('ContactsAndFaults','')
    inCaf = inFds+'/'+inCaf
    fNodes = outFds+'/errors_'+nameToken+'FaultDirNodes'
    fNodes2 = fNodes+'2'
    ### NEXT LINE IS A PROBLEM--NEED BETTER WAY TO SELECT FAULTS
    query = """ "TYPE" LIKE '%fault%' """
    testAndDelete('xxxFaults')
    arcpy.MakeFeatureLayer_management(inCaf,'xxxFaults',query)
    testAndDelete(fNodes)
    addMsgAndPrint('  getting TO and FROM nodes')
    arcpy.FeatureVerticesToPoints_management('xxxFaults',fNodes,'START')
    arcpy.AddField_management(fNodes,'NodeType','TEXT','#','#',5)
    arcpy.CalculateField_management (fNodes, 'NodeType',"'FROM'",'PYTHON')
    testAndDelete(fNodes2)
    arcpy.FeatureVerticesToPoints_management('xxxFaults',fNodes2,'END')
    arcpy.AddField_management(fNodes2,'NodeType','TEXT','#','#',5)
    arcpy.CalculateField_management (fNodes2, 'NodeType',"'TO'",'PYTHON')
    addMsgAndPrint('  merging TO and FROM node classes')
    arcpy.Append_management(fNodes2,fNodes)
    testAndDelete(fNodes2)
    arcpy.AddXY_management(fNodes)
    arcpy.Sort_management(fNodes,fNodes2,[['POINT_X','ASCENDING'],['POINT_Y','ASCENDING']])
    testAndDelete(fNodes)
    fields = ['NodeType','POINT_X','POINT_Y']
    listOfSharedNodes = []
    with arcpy.da.SearchCursor(fNodes2, fields) as cursor:
        oldxy = None
        NodeTypes = []
        for row in cursor:
            nArcs = 0
            xy = (row[1],row[2])
            if xy == oldxy:
                NodeTypes.append(row[0])
                nArcs = nArcs+1
            else:  # is new Node
                if len(NodeTypes) > 1: listOfSharedNodes.append([oldxy,NodeTypes,nArcs])
                oldxy = xy
                NodeTypes = [row[0]]
                nArcs = 1
    addMsgAndPrint('  '+str(len(listOfSharedNodes))+' nodes in listOfSharedNodes')

    arcpy.CreateFeatureclass_management(outFds,os.path.basename(fNodes),'POINT')
    arcpy.AddField_management(fNodes,'NodeTypes','TEXT','#','#',40)
    arcpy.AddField_management(fNodes,'NArcs','SHORT')

    fields = ["SHAPE@XY","NodeTypes","NArcs"]
    d = arcpy.da.InsertCursor(fNodes,fields)
    for aRow in listOfSharedNodes:
        if isFlippedNode(aRow[1]):
            nodeList = ''
            for nd in aRow[1]:
                nodeList = nodeList+nd+','
            d.insertRow([aRow[0],nodeList[:-1],aRow[2]])
    testAndDelete(fNodes2)
    addMsgAndPrint('  '+str(numberOfRows(fNodes))+' nodes with arcs that may need flipping')
    outHtml.write('<h3>End-points of fault arcs that may need flipping</h3>\n')
    outHtml.write('&nbsp;&nbsp; '+os.path.basename(fNodes)+'<br>\n')
    if numberOfRows(fNodes) > 0:
        outHtml.write('<tt>&nbsp;&nbsp;&nbsp; '+str(numberOfRows(fNodes))+' nodes</tt><br>\n')
    else:
        outHtml.write('<tt>&nbsp;&nbsp;&nbsp; no errors</tt><br>\n')
        testAndDelete(fNodes)


############ list MapUnits adjacent to each arc in ContactsAndFaults##########
def adjacentMapUnits(inFds,outFds,outHtml,validateCafTopology,planCaf):
    # get CAF and MUP
    inCaf = getCaf(inFds)
    inMup = inCaf.replace('ContactsAndFaults','MapUnitPolys')
    if not arcpy.Exists(inMup):
        addMsgAndPrint('Cannot find MapUnitPolys feature class '+inMup)
        raise arcpy.ExecuteError
    if not validateCafTopology:
        testAndDelete(planCaf)
        arcpy.FeatureToLine_management(inCaf,planCaf)
    # IDENTITY planCAF with MUP to make idCaf
    idCaf = outFds+'/'+os.path.basename(inCaf)+'_MUPid'
    testAndDelete(idCaf)
    addMsgAndPrint('  IDENTITYing '+planCaf+'\n    with '+inMup+' to get adjoining polys')
    arcpy.Identity_analysis(planCaf,inMup,idCaf,'ALL','','KEEP_RELATIONSHIPS')
    # get ordered list of mapUnits from DMU
    addMsgAndPrint('  getting ordered list of map units from DMU table')
    sortedDMU = os.path.dirname(outFds)+'/sortedDMU'
    testAndDelete(sortedDMU)
    dmu = os.path.dirname(inFds)+'/DescriptionOfMapUnits'
    testAndDelete('dmuView')
    arcpy.MakeTableView_management(dmu,'dmuView')
    arcpy.Sort_management('dmuView',sortedDMU,[['HierarchyKey','ASCENDING']])
    dmuUnits = []
    with arcpy.da.SearchCursor(sortedDMU, ['MapUnit']) as cursor:
        for row in cursor:
            if row[0] != None and row[0] != '':
                dmuUnits.append(row[0])
    if debug3: addMsgAndPrint('dmuUnits = '+str(dmuUnits))
    testAndDelete(sortedDMU)
    # SearchCursor through idCaf
    addMsgAndPrint('  building dictionaries of line adjacencies')
    concealedLinesDict = {}
    faultLinesDict = {}
    contactLinesDict = {}
    internalContacts = []
    badConcealed = []
    fields = ['Type','IsConcealed','RIGHT_MapUnit','LEFT_MapUnit','Shape_Length','OBJECTID']
    if debug3: addMsgAndPrint(str(numberOfRows(idCaf))+' rows in '+idCaf)
    with arcpy.da.SearchCursor(idCaf, fields) as cursor:
        for row in cursor:
            if debug3: addMsgAndPrint(str(row))
            try:
                lr = row[3]+'|'+row[2]
            except:
                addMsgAndPrint(str(row))
                lr = '--|--'
            if row[1].upper() == 'Y':  # IsConcealed = Y
                if debug3: addMsgAndPrint('*** is concealed')
                addRowToDict(lr,row,concealedLinesDict)
                if row[3] != row[2]:
                    badConcealed.append([row[3],row[2],row[0],row[1],row[5],row[4]])
            elif isContact(row[0]):
                if debug3: addMsgAndPrint('*** is a contact')
                addRowToDict(lr,row,contactLinesDict)
                if row[3] == row[2]:
                    internalContacts.append([row[3],row[2],row[0],row[1],row[5],row[4]])
            elif isFault(row[0]):  # it's a fault
                addRowToDict(lr,row,faultLinesDict)
    outHtml.write('<h3>MapUnits adjacent to CAF lines</h3>\n')
    outHtml.write('See feature class '+os.path.basename(idCaf)+' for ContactsAndFaults arcs attributed with adjacent polygon information. \n')
    outHtml.write('<i>In tables below, upper cell value is number of arcs. Lower cell value is cumulative arc length in map units.</i><br><br>\n')
    writeLineAdjacencyTable('Concealed contacts and faults',outHtml,concealedLinesDict,dmuUnits,'badConcealed')
    outHtml.write('<br>\n')
    writeLineAdjacencyTable('Contacts (not concealed)',outHtml,contactLinesDict,dmuUnits,'internalContacts')
    outHtml.write('<br>\n')
    writeLineAdjacencyTable('Faults (not concealed)',outHtml,faultLinesDict,dmuUnits,'')
    testAndDelete('dmuView')
    return badConcealed,internalContacts,idCaf

############ check for too-small features ###############################
def smallFeaturesCheck(inFds,outFds,mapScaleString,outHtml,tooShortArcMM,tooSmallAreaMM2,tooSkinnyWidthMM):
    # get inputs
    inCaf = os.path.basename(getCaf(inFds))
    inMup = inCaf.replace('ContactsAndFaults','MapUnitPolys')
    nameToken = inCaf.replace('ContactsAndFaults','')
    # set mapscale and mapunits
    mapUnit1 = arcpy.Describe(inFds).spatialReference.linearUnitName
    mapUnit1 = mapUnit1.upper()
    if mapUnit1.find('FOOT') > -1:
        mapUnits = 'feet'
    else:
        mapUnits = 'meters'
    mapScale = 1.0/float(mapScaleString)


    tooShortArcLength = tooShortMM/1000.0/mapScale
    tooSmallPolyArea = tooSmallAreaMM2/1e6/mapScale/mapScale
    #addMsgAndPrint(str(tooSmallAreaMM2)+'  '+str(tooSmallPolyArea))
    tooSkinnyWidth = tooSkinnyWidthMM/1000/mapScale
    if mapUnits == 'feet':
        tooShortArcLength = tooShortArcLength * 3.28
        tooSmallPolyArea = tooSmallPolyArea * 3.28 * 3.28
        tooSkinnyWidth = tooSkinnyWidth * 3.28

    tooShortArcs = outFds+'/errors_'+nameToken+'ShortArcs'
    tooSmallPolys = outFds+'/errors_'+nameToken+'SmallPolys'
    tooSmallPolyPoints = outFds+'/errors_'+nameToken+'SmallPolyPoints'
    tooSkinnyPolys = outFds+'/errors_'+nameToken+'SkinnyPolys'
    testAndDelete(tooShortArcs)
    testAndDelete(tooSmallPolys)
    testAndDelete(tooSmallPolyPoints)
    testAndDelete(tooSkinnyPolys)

    outHtml.write('<h3>Small feature inventory</h3>\n')
    outHtml.write('&nbsp;&nbsp; map scale = 1:'+mapScaleString+'<br>\n')
    
    # short arcs
    testAndDelete('cafLayer')
    arcpy.MakeFeatureLayer_management(inFds+'/'+inCaf, 'cafLayer', 'Shape_Length < '+str(tooShortArcLength))
    arcpy.CopyFeatures_management('cafLayer',tooShortArcs)
    outHtml.write('&nbsp;&nbsp; '+str(numberOfRows(tooShortArcs))+' arcs shorter than '+str(tooShortMM)+' mm<br>\n')
    if numberOfRows(tooShortArcs) == 0:
        testAndDelete(tooShortArcs)
    if arcpy.Exists(inMup):
        # small polys
        addMsgAndPrint('  tooSmallPolyArea = '+str(tooSmallPolyArea))
        testAndDelete('mupLayer')
        arcpy.MakeFeatureLayer_management(inFds+'/'+inMup,'mupLayer','Shape_Area < '+str(tooSmallPolyArea))
        arcpy.CopyFeatures_management('mupLayer',tooSmallPolys)
        addMsgAndPrint('  '+str(numberOfRows(tooSmallPolys))+ ' too-small polygons')
        arcpy.FeatureToPoint_management(tooSmallPolys,tooSmallPolyPoints,'INSIDE')
        outHtml.write('&nbsp;&nbsp; '+str(numberOfRows(tooSmallPolys))+' polys with area less than '+str(tooSmallAreaMM2)+' mm<sup>2</sup><br>\n')
        # sliver polys
        arcpy.CopyFeatures_management(inFds+'/'+inMup,tooSkinnyPolys)
        testAndDelete('sliverLayer')
        arcpy.MakeFeatureLayer_management(tooSkinnyPolys,'sliverLayer')
        arcpy.AddField_management('sliverLayer','AreaDivLength','FLOAT')
        arcpy.CalculateField_management('sliverLayer','AreaDivLength',"!Shape_Area! / !Shape_Length!","PYTHON")
        arcpy.SelectLayerByAttribute_management('sliverLayer','NEW_SELECTION',"AreaDivLength >= "+str(tooSkinnyWidth))
        arcpy.DeleteFeatures_management('sliverLayer')
        addMsgAndPrint('  tooSkinnyPolyWidth = '+str(tooSkinnyWidth))
        addMsgAndPrint('  '+str(numberOfRows(tooSkinnyPolys))+ ' too-skinny polygons')
        
        outHtml.write('&nbsp;&nbsp; '+str(numberOfRows(tooSkinnyPolys))+' polys with area/length ratio less than '+str(tooSkinnyWidth)+' '+mapUnits+'<br>\n')
        for fc in (tooSkinnyPolys,tooSmallPolys):
            if numberOfRows(fc) == 0: testAndDelete(fc)
    else:
        outHtml.write('&nbsp;&nbsp; No MapUnitPolys feature class<br>\n')

        for xx in 'cafLayer','mupLayer','sliverLayer':
            testAndDelete(xx)

    return      

############# checking arc-defined formal topology #####################
def validateCafTopology(inFds,outFds,outHtml):
    inCaf = getCaf(inFds)
    caf = os.path.basename(inCaf)
    nameToken = caf.replace('ContactsAndFaults','')
    outCaf = outFds+'/'+caf
    inMup = inFds+'/'+nameToken+'MapUnitPolys'
    outMup = outFds+'/'+nameToken+'MapUnitPolys'
    inGel = inFds+'/'+nameToken+'GeologicLines'
    outGel = outFds+'/'+nameToken+'GeologicLines'
            
    # First delete any existing topology
    ourTop = os.path.basename(outFds)+'_topology'
    testAndDelete(outFds+'/'+ourTop)
    # copy CAF to _errors.gdb
    testAndDelete(outCaf)
    arcpy.Copy_management(inCaf,outCaf)
    # copy MUP to _errors.gdb
    testAndDelete(outMup)
    if arcpy.Exists(inMup):
        arcpy.Copy_management(inMup,outMup)
    # copy GeL to _errors.gdb
    testAndDelete(outGel)
    if arcpy.Exists(inGel):
        arcpy.Copy_management(inGel,outGel)
  
    # create topology
    addMsgAndPrint('  creating topology '+ourTop)
    arcpy.CreateTopology_management(outFds,ourTop)
    ourTop = outFds+'/'+ourTop
    # add feature classes to topology
    arcpy.AddFeatureClassToTopology_management(ourTop, outCaf,1,1)
    if arcpy.Exists(outMup):
        arcpy.AddFeatureClassToTopology_management(ourTop, outMup,2,2)
    if arcpy.Exists(outGel):
        arcpy.AddFeatureClassToTopology_management(ourTop, outGel,3,3)
    # add rules to topology
    addMsgAndPrint('  adding rules to topology:')
    for aRule in ('Must Not Overlap (Line)','Must Not Self-Overlap (Line)','Must Not Self-Intersect (Line)','Must Be Single Part (Line)'):
        addMsgAndPrint('    '+aRule)
        arcpy.AddRuleToTopology_management(ourTop, aRule, outCaf)
    if arcpy.Exists(outMup):
        for aRule in ('Must Not Overlap (Area)','Must Not Have Gaps (Area)'):
            addMsgAndPrint('    '+aRule)
            arcpy.AddRuleToTopology_management(ourTop, aRule, outMup)
        addMsgAndPrint('    '+'Boundary Must Be Covered By (Area-Line)')
        arcpy.AddRuleToTopology_management(ourTop,'Boundary Must Be Covered By (Area-Line)',outMup,'',outCaf)
    if arcpy.Exists(outGel):
        for aRule in ('Must Be Single Part (Line)','Must Not Self-Overlap (Line)','Must Not Self-Intersect (Line)'):
            addMsgAndPrint('    '+aRule)
            arcpy.AddRuleToTopology_management(ourTop, aRule, outGel)
        
    # validate topology
    addMsgAndPrint('  validating topology')
    arcpy.ValidateTopology_management(ourTop)
    if nameToken == '':
        nameToken = 'GeologicMap'
    nameToken = 'errors_'+nameToken+'Topology'
    for sfx in ('_point','_line','_poly'):
        testAndDelete(outFds+'/'+nameToken+sfx)
    # export topology errors
    addMsgAndPrint('  exporting topology errors')
    arcpy.ExportTopologyErrors_management(ourTop,outFds,nameToken)
    outHtml.write('<h3>Line and polygon topology</h3>\n')
    outHtml.write('<blockquote><i>Note that the map boundary commonly results in a "Must Not Have Gaps" error</i></blockquote>')
    for sfx in ('_point','_line','_poly'):
        fc = outFds+'/'+nameToken+sfx
        outHtml.write('&nbsp; '+nameToken+sfx+'<br>\n')
        html_writeFreqTable(outHtml,fc,['RuleDescription','RuleType'])
        addMsgAndPrint('    '+str(numberOfRows(fc))+' rows in '+os.path.basename(fc))
        if numberOfRows(fc) == 0: testAndDelete(fc)

############# checking for validity of CAF nodes #######################
def validateCafNodes(inFds,outFds,outHtml,planCaf):
    inCaf = getCaf(inFds)
    caf = os.path.basename(inCaf)
    outGdb = os.path.dirname(outFds)
    fv1 = outGdb+'/xxxLineNodes1'
    fv1a = outGdb+'/xxxLineNodes1a'
    fv2 = outGdb+'/xxxLineNodes2'
    nearTable = outGdb+'/xxxNearTable'
    badNodes = outFds+'/errors_BadNodes'

    testAndDelete(planCaf)
    arcpy.env.outputZFlag = "Disabled"
    arcpy.env.outputMFlag = "Disabled"

    arcpy.FeatureToLine_management(inCaf,planCaf)
    addMsgAndPrint('  calculating line directions at line ends')
    arcpy.AddField_management(planCaf,'LineDir','FLOAT')
    arcpy.AddField_management(planCaf,'EndDir','FLOAT')
    fields = ['SHAPE@','LineDir','EndDir']
    with arcpy.da.UpdateCursor(planCaf,fields) as cursor:
        for row in cursor:
            lineSeg = row[0].getPart(0)
            row[1] = startGeogDirection(lineSeg)
            row[2] = endGeogDirection(lineSeg)
            cursor.updateRow(row)

    addMsgAndPrint('  converting line ends to points')
    testAndDelete(fv1)
    testAndDelete(fv1a)
    arcpy.FeatureVerticesToPoints_management(planCaf,fv1, 'START')
    arcpy.FeatureVerticesToPoints_management(planCaf,fv1a,'END')
    arcpy.CalculateField_management(fv1a,'LineDir','!EndDir!','PYTHON')
    arcpy.Append_management(fv1a,fv1)

    addMsgAndPrint('  adding XY values and sorting by XY')
    arcpy.AddXY_management(fv1)
    testAndDelete(fv2)
    arcpy.Sort_management(fv1,fv2,[["POINT_X","ASCENDING"],["POINT_Y","ASCENDING"]])

    fields = ["POINT_X","POINT_Y","FID_"+caf,"Type","IsConcealed","ORIG_FID","LineDir"]
    isFirst = True
    nArcs = 0
    nodes = []
    with arcpy.da.SearchCursor(fv2, fields) as cursor:
        for row in cursor:
            x = row[0]; y = row[1]
            rFid = row[2]
            rType = row[3]
            rIsConcealed = row[4]
            rOrigFid = row[5]
            rLineDir = row[6]
            if isFirst:
                lastX = x; lastY = y
                isFirst = False
                arcs = []
            if abs(x-lastX) < searchRadius and abs(y-lastY) < searchRadius:
                arcs.append([rLineDir,rFid,rOrigFid,rType,rIsConcealed])
            else:
                nodes.append([lastX,lastY,arcs])
                arcs = [[rLineDir,rFid,rOrigFid,rType,rIsConcealed]]
                lastX = x; lastY = y
        nodes.append([lastX,lastY,arcs])

    addMsgAndPrint('  '+ str(len(nodes))+' distinct nodes' )
    
    addMsgAndPrint('  identifying node status' )
    badRows = []
    for un in nodes:
        arcs = un[2]
        numArcs = len(arcs)
        arcNumbers = ''
        arcTypes = ''
        for anArc in arcs:
            arcNumbers = arcNumbers+str(anArc[1])+','
            if anArc[3] == None:
                arcTypes = arcTypes+'-- | '
            else:
                if anArc[4] == 'Y':  # IsConcealed == Y
                    arcTypes = arcTypes+anArc[3].lower()+'#CON | '
                else:
                    arcTypes = arcTypes+anArc[3].lower()+' | '
        arcTypes = arcTypes[:-3]
        arcNumbers = arcNumbers[:-1]
        # figure out node status
        ## some assumptions about Type values:
        ##    the Type for 'map boundary' or its equivalent contains the string 'boundary'
        ##    This code is not case sensitive--all Type values are here converted to lower case
        if numArcs == 1:
            if isFault(arcs[0][3]):
                nodeStatus = 'OK dangling fault' 
            else:
                if arcs[0][4] == 'Y':
                    nodeStatus = 'CHECK  dangling concealed contact'
                else:
                    nodeStatus = 'BAD DANGLE'
        elif numArcs == 2:
            if arcs[0][2] == arcs[1][2]:  # nodes belong to same arc, i.e., a loop
                nodeStatus = 'OK loop'
            elif arcTypes.count('#CON') == 1: # one arc is concealed, other is not
                nodeStatus = 'BAD  pseudonode with 1 arc concealed, 1 not'
            elif arcs[0][3] != arcs[1][3]:   # arc Type values don't match
                if isFault(arcs[0][3]) and isFault(arcs[1][3]):
                    nodeStatus = 'CHECK  pseudonode with change in fault type'
                else:
                    nodeStatus = 'BAD  pseudonode with mismatched arc Types'
            else:  # we assume that this is a permissible pseudonode
                nodeStatus = 'OK  pseudonode'
        elif numArcs == 3:
            if numberMapBoundaryArcs(arcTypes) == 2: # any arc joining map boundary is OK
                nodeStatus = 'OK'
            elif arcTypes.count('#CON') in (0,3): # either all arcs are concealed or none are
                if arcs[0][3] != arcs[1][3] and arcs[0][3] != arcs[2][3] and arcs[1][3] != arcs[2][3]:
                    nodeStatus = 'BAD  incompatible type values'
                else:
                    nodeStatus = 'OK'
            elif arcTypes.count('#CON') == 1 and arcTypes.count('fault') >= 2:
                if (arcs[0][4] == 'Y' and arcs[1][3] == arcs[2][3]) or (arcs[1][4] == 'Y' and arcs[0][3] == arcs[2][3]) or (arcs[2][4] == 'Y' and arcs[0][3] == arcs[1][3]):
                    nodeStatus = 'OK' # concealed arc truncated by fault
                else:
                    nodeStatus = 'BAD  concealed line truncated by faults with mismatched Types'
            else: 
                nodeStatus = 'BAD  concealed line without unconcealed continuation'
                addMsgAndPrint(arcTypes+ ' '+str(numberMapBoundaryArcs(arcTypes)))
                ## this flags junctions where a concealed contact merges with a contact as BAD
                ## maybe it shouldn't?
        elif numArcs == 4:
            arcs.sort() # first element is LineDir. so arcs are now in order around point
            if arcTypes.count('#CON') == 0:
                if arcs[0][3] == arcs[2][3] and arcs[1][3] == arcs[3][3] and ( isFault(arcs[0][3]) or isFault(arcs[1][3]) ):
                    nodeStatus = 'BAD  fault with no offset'
                else:                                                                   
                    nodeStatus = 'BAD  4 arcs, none concealed'
            elif arcTypes.count('#CON') in (3,4):
                nodeStatus == 'BAD  4 arcs, too many concealed'
            # must have two "contact", unconcealed, of same type, and
            #  and two other lines of identical type, at least one of which is concealed
            elif arcTypes.count('#CON') == 2:
                if arcs[0][3] != arcs[2][3] or arcs[1][3] != arcs[3][3]:
                    nodeStatus = 'BAD  4 arcs, incompatible Type values'
                else:
                    conNumber = concealedArcNumber(arcs)
                    if conNumber == 3: nextNumber = 0
                    else: nextNumber = conNumber+1
                    if not isContact(arcs[nextNumber][3]):
                        nodeStatus = 'BAD  4 arcs, crossing arc(s) must be contact'
                    else: nodeStatus = 'OK'  # 4 arcs, contact crosses concealed concealed contact or fault'
            else:  # one of the 4 joining arcs is concealed
                if arcs[0][3] != arcs[2][3] or arcs[1][3] != arcs[3][3]:
                    nodeStatus = 'BAD  4 arcs, incompatible Type values'
                elif not isContact(arcs[0][3]) and not isContact(arcs[1][3]):
                    nodeStatus = 'BAD  4 arcs, neither crossing line is a contact'
                else:
                    conNumber = concealedArcNumber(arcs)
                    if conNumber == 3: nextNumber = 0
                    else: nextNumber = conNumber+1
                    if not isContact(arcs[nextNumber][3]):
                        nodeStatus = 'BAD  crossing arc(s) must be contact'
                    else:
                        nodeStatus = 'OK'
                        
        else:  # more than 4 arcs 
            nodeStatus = 'BAD too many lines' 
        xy = (un[0],un[1])
        thisRow = [xy,numArcs,arcNumbers,arcTypes,nodeStatus]
        if nodeStatus.find('BAD') > -1 or nodeStatus.find('CHECK') > -1:
            badRows.append(thisRow)

    testAndDelete(badNodes)
    arcpy.CreateFeatureclass_management(outFds,os.path.basename(badNodes),'POINT')
    arcpy.AddField_management(badNodes,'NumArcs','SHORT')
    arcpy.AddField_management(badNodes,'ArcNumbers','TEXT','#','#',100)
    arcpy.AddField_management(badNodes,'NodeStatus','TEXT','#','#',70)
    arcpy.AddField_management(badNodes,'ArcTypes','TEXT','#','#',300)
    fields = ["SHAPE@XY","NumArcs","ArcNumbers","ArcTypes","NodeStatus"]
    d = arcpy.da.InsertCursor(badNodes,fields)
    for aRow in badRows:
        try:
            d.insertRow(aRow)
        except:
            addMsgAndPrint('Bad value(s) in row')
            addMsgAndPrint(str(aRow))
       
    addMsgAndPrint('  '+ str(arcpy.GetCount_management(badNodes)) + ' bad or queried nodes' )

    # cleanup
    for fc in (fv1,fv1a,fv2):
        testAndDelete(fc)
    if not adjMapUnits:
        testAndDelete(planCAF)

    outHtml.write('<h3>Node topology</h3>\n')
    outHtml.write('&nbsp; '+str(arcpy.GetCount_management(badNodes)) + ' bad or queried nodes<br>\n')
    outHtml.write('&nbsp; '+os.path.basename(badNodes)+'<br>\n')
    ##html_writeFreqTable(outHtml,badNodes,['NodeStatus'])  ## this doesn't work--not sure why


######################################################
inGdb = sys.argv[1]
validateAllFdSets = sys.argv[2]
someFdSets = sys.argv[3]
validateLinesAndPolys = sys.argv[4]
validateNodes = sys.argv[5]
validateLineDirs = sys.argv[6]
adjMapUnits = sys.argv[7]
findDupPoints = sys.argv[8]
smallFeatures = sys.argv[9]
mapScaleString = sys.argv[10]
tooShortArcMM = float(sys.argv[11])
tooSmallAreaMM2 = float(sys.argv[12])
tooSkinnyWidthMM = float(sys.argv[13])
# values 11-13 used in smallFeaturesCheck
forceExit = sys.argv[14]

addMsgAndPrint(versionString)

if debug1:
  addMsgAndPrint('Echoing inputs')
  for n in range(1,len(sys.argv)):
    addMsgAndPrint('  '+sys.argv[n])
  
if not arcpy.Exists(inGdb):
    raise arcpy.ExecuteError

arcpy.env.workspace = inGdb
aDataSets = arcpy.ListDatasets()
allDataSets = []
for aDs in aDataSets:
    allDataSets.append(inGdb+'\\'+aDs)

if validateAllFdSets == 'false' and someFdSets == '#':
    inFdSets = [inGdb+'\\GeologicMap']
elif validateAllFdSets == 'true':
    inFdSets = allDataSets
    if debug1: addMsgAndPrint('allFdSets = '+str(inFdSets))
else:
    inFdSets = someFdSets.split(';')
    if debug1: addMsgAndPrint('someFdSets = '+str(inFdSets))
    for fds in inFdSets:
        if not arcpy.Exists(fds):
            raise arcpy.ExecuteError


fdsNotEval = []
for fds in allDataSets:
    if not fds in inFdSets:
        fdsNotEval.append(fds)

outHtmlName = inGdb+'-TopologyReport.html'
addMsgAndPrint('Writing output to '+outHtmlName)
outHtml = open(outHtmlName,'w')
writeHeader(outHtml,inGdb)

outGdb = inGdb[:-4]+'_errors.gdb'
if not arcpy.Exists(outGdb):
    outFolder,outName = os.path.split(outGdb)
    arcpy.CreateFileGDB_management(outFolder, outName)

if len(fdsNotEval) > 0:
    notEvalString = ''
    for fds in fdsNotEval:
        notEvalString = notEvalString+os.path.basename(fds)+', '
    notEvalString = notEvalString[:-2]
    outHtml.write('Feature datasets not evaluated: '+notEvalString+'<br>\n')
outHtml.write('Error feature classes (errors_<i>XXXX</i>) are in geodatabase '+outGdb+'<br>\n')  

for fds in inFdSets:
    addMsgAndPrint('****validating '+fds+'****')
    fdsName = os.path.basename(fds)
    outHtml.write('<h2>'+fdsName+' <i>feature dataset</i>'+'</h2>\n')
    inFds = inGdb+'/'+fdsName
    outFds = outGdb+'/'+fdsName

    caf = getCaf(inFds)
    nameToken = os.path.basename(caf).replace('ContactsAndFaults','')
    planCaf = outFds+'/'+nameToken+'PlanarizedCAF'

    if not arcpy.Exists(outFds):
        arcpy.CreateFeatureDataset_management(outGdb, fdsName, fds)
    if validateLinesAndPolys == 'true':
        addMsgAndPrint('Checking line and polygon topology')
        validateCafTopology(inFds,outFds,outHtml)
    else:
        outHtml.write('<h3>Line and polygon topology not checked</h3>\n')
    if validateNodes == 'true':
        addMsgAndPrint('Checking nodes')
        validateCafNodes(inFds,outFds,outHtml,planCaf)
    else:
        outHtml.write('<h3>Node topology not checked</h3>\n')
    if validateLineDirs == 'true':
        addMsgAndPrint('Checking for consistent fault directions')
        lineDirections(inFds,outFds,outHtml)
    else:
        outHtml.write('<h3>Line directions not checked</h3>\n')
    if adjMapUnits == 'true':
        addMsgAndPrint('Making tables of map-unit adjacency')
        badConcealed,internalContacts,idCaf = adjacentMapUnits(inFds,outFds,outHtml,validateCafTopology,planCaf)
    else:
        outHtml.write('<h3>MapUnit adjacency not checked</h3>\n')
    if findDupPoints == 'true':
        addMsgAndPrint('Finding duplicate point features')
        findDupPts(inFds,outFds,outHtml)
    else:
        outHtml.write('<h3>No check for duplicate point features</h3>\n')
    if smallFeatures == 'true':
        addMsgAndPrint('Listing short arcs, small polys, and sliver polys')
        smallFeaturesCheck(inFds,outFds,mapScaleString,outHtml,tooShortArcMM,tooSmallAreaMM2,tooSkinnyWidthMM)
    else:
        outHtml.write('<h3>No check for small polys and short lines</h3>\n')

    if adjMapUnits == 'true':
        outHtml.write('<br><h3>Bad concealed contacts and faults</h3>\n')
        if len(badConcealed) > 0:
            outHtml.write('&nbsp; see feature class '+idCaf+'<br>\n')
            contactListWrite(badConcealed,outHtml,'badConcealed')
        else:
            outHtml.write('&nbsp; no bad concealed contacts and faults')
        outHtml.write('<br><h3>Internal Contacts</h3>\n')
        if len(internalContacts) > 0:
            outHtml.write('&nbsp; see feature class '+idCaf+'<br>\n')
            contactListWrite(internalContacts,outHtml,'internalContacts')
        else:
            outHtml.write('&nbsp; no internal contacts')

outHtml.write(htmlEnd)
outHtml.close()

if forceExit == 'true':
    addMsgAndPrint(' ')
    addMsgAndPrint('COMPLETED SUCCESSFULLY, FORCING AN ERROR')
    raise arcpy.ExecuteError

