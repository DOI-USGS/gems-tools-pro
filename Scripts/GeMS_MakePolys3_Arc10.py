##New, improved make polys

import arcpy, sys, os.path, os
from GeMS_utilityFunctions import *
from GeMS_Definition import tableDict

# 5 January 2018: Modified error message for topology that contains polys
versionString = 'GeMS_MakePolys3_Arc10.py, version of 5 January 2018'
debug = False

def checkMultiPts(multiPts,badPointList,badPolyList):
    # checks list of label points, all in same poly. If MapUnits are not all same,
    # adds mapunitID to badPolyList, adds labelPointIDs to badPointList
    # multiPts fields = [mupID,cp2ID,'MapUnit_1','MapUnit']
    if len(multiPts) > 1:
        # some tests, grow bad lists
        polyID = multiPts[0][0]
        ptIDs = [multiPts[0][1]]
        mapUnits = set()
        mapUnits.add(multiPts[0][2]); mapUnits.add(multiPts[0][3])
        for i in range(0,len(multiPts)):
            if multiPts[i][0] <> polyID:
                addMsgAndPrint('PROBLEM IN CHECKMULTIPTS!')
                addMsgAndPrint(str(multiPts))
                forceExit()
            ptIDs.append(multiPts[i][1])
            mapUnits.add(multiPts[i][2])
            mapUnits.add(multiPts[i][3])
        if len(mapUnits) > 1:  # label pts reference more than one map unit
            badPolyList.append(polyID)
            for pt in ptIDs:
                badPointList.append(pt)
    return badPointList, badPolyList

def findLyr(lname):
    lname.replace('//','_')
    if debug: addMsgAndPrint('finding layer, lname = '+lname)
    mxd = arcpy.mapping.MapDocument('CURRENT')
    for df in arcpy.mapping.ListDataFrames(mxd):
        lList = arcpy.mapping.ListLayers(mxd, '*', df)
        for lyr in lList:
            # either layer is a group, datasetName is not supported, and we match lyr.name
            # or (and) we match datasetName, which cannot be aliased as lyr.name may be
            if (lyr.supports('dataSource') and lyr.dataSource == lname) \
                    or (not lyr.supports('dataSource') and lyr.name == lname):
                pos = lList.index(lyr)
                if pos == 0:
                    refLyr = lList[pos + 1]
                    insertPos = "BEFORE"
                else:
                    refLyr = lList[pos - 1]
                    insertPos = "AFTER"
                return [lyr, df, refLyr, insertPos]
    return [-1,-1,-1,-1]

##################################

addMsgAndPrint(versionString)

fds = sys.argv[1]
saveMUP = False
if sys.argv[2] == 'true':
    saveMUP = True
if sys.argv[3] == '#':
    layerRepository = os.path.dirname(os.path.dirname(fds))
else:
    layerRepository = sys.argv[3]
labelPoints = sys.argv[4]

# check that labelPoints, if specified, has field MapUnit
if arcpy.Exists(labelPoints):
    lpFields = fieldNameList(labelPoints)
    if not 'MapUnit' in lpFields:
        addMsgAndPrint('Feature class '+labelPoints+' should have a MapUnit attribute and it does not.')
        forceExit()
  
# check for existence of fds
if not arcpy.Exists(fds):
    addMsgAndPrint('Feature dataset '+fds+ 'does not seem to exist.')
    forceExit()
## check for schema lock
#if not arcpy.TestSchemaLock(fds):
#    addMsgAndPrint('Feature dataset '+fds+' is locked!')
#    forceExit()

# get caf, mup, nameToken
caf = getCaf(fds)
shortCaf = os.path.basename(caf)
mup = getMup(fds)
shortMup = os.path.basename(mup)
nameToken = getNameToken(fds)

# check for topology class that involves polys
arcpy.env.workspace = fds
topologies = arcpy.ListDatasets('*','Topology')
for topol in topologies:
    if shortMup in arcpy.Describe(topol).featureClassNames:
        addMsgAndPrint('  ***')
        addMsgAndPrint('Cannot delete '+shortMup+' because it is part of topology class '+topol+'.')
        addMsgAndPrint('Delete topology (or remove rules that involve '+shortMup+') before running this script.')
        addMsgAndPrint('  ***')
        forceExit()

badLabels = os.path.join(fds,'errors_'+nameToken+'multilabels')
badPolys = os.path.join(fds,'errors_'+nameToken+'multilabelPolys')
blankPolys = os.path.join(fds,'errors_'+nameToken+'unlabeledPolys')
centerPoints = os.path.join(fds,'xxxCenterPoints')
centerPoints2 = centerPoints+'2'
centerPoints3 = centerPoints+'3'
inPolys = mup
temporaryPolys = 'xxxTempPolys'
oldPolys = os.path.join(fds,'xxxOldPolys')
changedPolys = os.path.join(fds,'edit_'+nameToken+'ChangedPolys')

# find and remove layers in active window that involve editLayers
addMsgAndPrint('  Saving selected layers and removing them from current data frame')
savedLayers = []
sLayerN = 1

for aLyr in [mup,badLabels,badPolys,blankPolys,changedPolys]:
    addMsgAndPrint('    looking for '+aLyr)
    lyr = 1
    while lyr <> -1:
        lyr,df,refLyr,insertPos = findLyr(aLyr)
        if lyr <> -1:
            while lyr.longName.find('\\') > 0:
                groupLyrName = lyr.longName[:lyr.longName.find('\\')]
                lyr,df,refLyr,insertPos = findLyr(groupLyrName)
            # WHY OH WHY do we let Windoze programmers build our tools?
            lyrName = lyr.name.replace('\\','_')
            lyrPath = os.path.join(layerRepository, lyrName + str(sLayerN) + '.lyr')
            #save to a layer file on disk so that customizations can be retrieved layer
            testAndDelete(lyrPath)
            #if arcpy.Exists(lyrPath):
            #    os.remove(lyrPath)
            arcpy.SaveToLayerFile_management(lyr, lyrPath, "RELATIVE")
            #and now remove the layer
            arcpy.mapping.RemoveLayer(df, lyr)
            savedLayers.append([lyrPath,df,refLyr,insertPos,lyr])
            addMsgAndPrint('     layer '+lyrName+' saved and removed from data frame')
            sLayerN = sLayerN+1
   
if debug:
    addMsgAndPrint('savedLayers ='+str(savedLayers))

cafLayer = 'cafLayer'

arcpy.env.workspace = fds

# make layer view of inCaf without concealed lines
addMsgAndPrint('  Making layer view of CAF without concealed lines')
sqlQuery = arcpy.AddFieldDelimiters(fds,'IsConcealed') + " NOT IN ('Y','y')"
testAndDelete(cafLayer)
arcpy.MakeFeatureLayer_management(caf,cafLayer,sqlQuery)

#make temporaryPolys from layer view
addMsgAndPrint('  Making '+temporaryPolys)
testAndDelete(temporaryPolys)
arcpy.FeatureToPolygon_management(cafLayer,temporaryPolys)
if debug:
    addMsgAndPrint('temporaryPolys fields are '+str(fieldNameList(temporaryPolys)))

#make center points (within) from temporarypolys
addMsgAndPrint('  Making '+centerPoints)
testAndDelete(centerPoints)               
arcpy.FeatureToPoint_management(temporaryPolys, centerPoints, "INSIDE")
if debug:
    addMsgAndPrint('centerPoints fields are '+str(fieldNameList(centerPoints)))
# get rid of ORIG_FID field
arcpy.DeleteField_management(centerPoints,'ORIG_FID')

#identity center points with inpolys
testAndDelete(centerPoints2)
arcpy.Identity_analysis(centerPoints, inPolys, centerPoints2, 'NO_FID')
# delete points with MapUnit = ''
## first, make layer view
addMsgAndPrint("    Deleting centerPoints2 MapUnit = '' ")
sqlQuery = arcpy.AddFieldDelimiters(fds,'MapUnit') + "= '' "
testAndDelete('cP2Layer')
arcpy.MakeFeatureLayer_management(centerPoints2,'cP2Layer',sqlQuery)
## then delete features
if numberOfRows('cP2Layer') > 0:
    arcpy.DeleteFeatures_management('cP2Layer')

#adjust center point fields (delete extra, add any missing. Use NCGMP09_Definition as guide)
## get list of fields in centerPoints2
cp2Fields = fieldNameList(centerPoints2)
## add fields not in MUP as defined in Definitions
fieldDefs = tableDict['MapUnitPolys']
for fDef in fieldDefs:
    if fDef[0] not in cp2Fields:
        addMsgAndPrint('field '+fd+' is missing')
        try:
            if fDef[1] == 'String':
                arcpy.AddField_management(thisFC,fDef[0],transDict[fDef[1]],'#','#',fDef[3],'#',transDict[fDef[2]])
            else:
                arcpy.AddField_management(thisFC,fDef[0],transDict[fDef[1]],'#','#','#','#',transDict[fDef[2]])
            cp2Fields.append(fDef[0])
        except:
            addMsgAndPrint('Failed to add field '+fDef[0]+' to feature class '+featureClass)
            addMsgAndPrint(arcpy.GetMessages(2))        

# if labelPoints specified
## add any missing fields to centerPoints2
if arcpy.Exists(labelPoints):
    lpFields = arcpy.ListFields(labelPoints)
    for lpF in lpFields:
        if not lpF.name in cp2Fields:
            if lpF.type in ('Text','STRING'):
                arcpy.AddField_management(centerPoints2,lpF.name,'TEXT','#','#',lpF.length)
            else:
                arcpy.AddField_management(centerPoints2,lpF.name,typeTransDict[lpF.type])
# append labelPoints to centerPoints2
if arcpy.Exists(labelPoints):
    arcpy.Append_management(labelPoints,centerPoints2,'NO_TEST')

#if inPolys are to be saved, copy inpolys to savedPolys
if saveMUP:
    addMsgAndPrint('  Saving MapUnitPolys')
    arcpy.Copy_management(inPolys,getSaveName(inPolys)) 

# make oldPolys
addMsgAndPrint('  Making oldPolys')
testAndDelete(oldPolys)
if debug:
    addMsgAndPrint(' oldPolys should be deleted!')
arcpy.Copy_management(inPolys,oldPolys)
## copy field MapUnit to new field OldMapUnit
arcpy.AddField_management(oldPolys,'OldMapUnit','TEXT','','',40)
arcpy.CalculateField_management(oldPolys,'OldMapUnit',"!MapUnit!","PYTHON_9.3")
## get rid of excess fields in oldPolys
fields = fieldNameList(oldPolys)
if debug:
    addMsgAndPrint('oldPoly fields = ')
    addMsgAndPrint('  '+str(fields))
for field in fields:
    if not field in ('OldMapUnit','OBJECTID','Shape','Shape_Area','Shape_Length'):
        if debug:
            addMsgAndPrint('     deleting '+field)
        arcpy.DeleteField_management(oldPolys,field)

#make new mup from layer view, with centerpoints2
addMsgAndPrint('  Making new MapUnitPolys')
testAndDelete(mup)
arcpy.FeatureToPolygon_management(cafLayer,mup,'','ATTRIBUTES',centerPoints2)
testAndDelete(cafLayer)

addMsgAndPrint('  Making changedPolys')
#intersect oldPolys with mup to make changedPolys
testAndDelete(changedPolys)
arcpy.Identity_analysis(mup,oldPolys,changedPolys)
#addMsgAndPrint('     '+str(numberOfRows(changedPolys))+' rows in changedPolys')
## make feature layer, select MapUnit = OldMapUnit and delete
addMsgAndPrint('     deleting features with MapUnit = OldMapUnit')
sqlQuery = arcpy.AddFieldDelimiters(changedPolys,'MapUnit') + " = " +arcpy.AddFieldDelimiters(changedPolys,'OldMapUnit')
#addMsgAndPrint('Fields in '+changedPolys+' are:')
#addMsgAndPrint(str(fieldNameList(changedPolys)))
#addMsgAndPrint('sqlQuery = '+sqlQuery)
testAndDelete('cpLayer')
arcpy.MakeFeatureLayer_management(changedPolys,'cpLayer',sqlQuery)
arcpy.DeleteFeatures_management('cpLayer')
addMsgAndPrint('     '+str(numberOfRows(changedPolys))+' rows in changedPolys')

#identity centerpoints2 with mup
addMsgAndPrint('  Finding label errors')
testAndDelete(centerPoints3)
arcpy.Identity_analysis(centerPoints2,mup,centerPoints3)
if debug: addMsgAndPrint(str(fieldNameList(centerPoints3)))
#make list from centerPoints3:  mupID, centerPoints2ID, cp2.MapUnit, mup.MapUnit
cpList = []
mupID = 'FID_'+os.path.basename(mup)
cp2ID = 'FID_'+os.path.basename(centerPoints2)
fields = [mupID,cp2ID,'MapUnit_1','MapUnit']
with arcpy.da.SearchCursor(centerPoints3, fields) as cursor:
    for row in cursor:
        cpList.append([row[0],row[1],row[2],row[3]])
#sort list on mupID
cpList.sort()
badPointList = []
badPolyList = []
#step through list. If more than 1 centerpoint with same mupID AND mapUnit1 <> MapUnit2 <>  ...:
addMsgAndPrint('    Sorting through label points')
lastPt = cpList[0]
multiPts = [lastPt]
for i in range(1,len(cpList)):
    if cpList[i][0] <> lastPt[0]:  # different poly than lastPt
        badPointList, badPolyList = checkMultiPts(multiPts,badPointList,badPolyList)
        lastPt = cpList[i]
        multiPts = [lastPt]
    else: # we are looking at more points in same poly
        multiPts.append(cpList[i])
badPointList, badPolyList = checkMultiPts(multiPts,badPointList,badPolyList)

#from badPolyList, make badPolys
addMsgAndPrint('    Making '+badPolys)
testAndDelete(badPolys)
arcpy.Copy_management(mup,badPolys)
with arcpy.da.UpdateCursor(badPolys,['OBJECTID']) as cursor:
    for row in cursor:
        if row[0] not in badPolyList:
            cursor.deleteRow()

#from badPointlist of badpoints, make badLabels
addMsgAndPrint('    Making '+badLabels)
testAndDelete(badLabels)
arcpy.Copy_management(centerPoints2,badLabels)
with arcpy.da.UpdateCursor(badLabels,['OBJECTID']) as cursor:
    for row in cursor:
        if row[0] not in badPointList:
            cursor.deleteRow()
               
#make blankPolys
addMsgAndPrint('    Making '+blankPolys)
testAndDelete(blankPolys)
arcpy.Copy_management(mup,blankPolys)
query = arcpy.AddFieldDelimiters(blankPolys,'MapUnit')+" <> ''"
testAndDelete('blankP')
arcpy.MakeFeatureLayer_management(blankPolys,'blankP',query)
arcpy.DeleteFeatures_management('blankP')
addMsgAndPrint('    '+str(len(badPolyList))+' multi-label polys')
addMsgAndPrint('    '+str(len(badPointList))+' multiple, conflicting, label points')
addMsgAndPrint('    '+str(numberOfRows(blankPolys))+' unlabelled polys')

addMsgAndPrint('  Cleaning up')
#delete oldpolys, temporaryPolys, centerPoints, centerPoints2, centerPoints3
for fc in oldPolys, temporaryPolys, centerPoints, centerPoints2, centerPoints3, cafLayer,'cP2Layer':
    testAndDelete(fc)

# restore saved layers
addMsgAndPrint('  Restoring saved layers to current data frame')
savedLayers.reverse()
for savedLayer in savedLayers:
    lyrPath,dataFrame,refLyr,insertPos,lyr = savedLayer
    addMsgAndPrint('    layer '+lyr.name)
    if debug: addMsgAndPrint('      '+str(lyrPath)+' '+str(dataFrame)+' '+str(refLyr)+' '+str(insertPos))
    addLyr = arcpy.mapping.Layer(lyrPath)
    arcpy.mapping.AddLayer(dataFrame, addLyr)
    # if refLyr is part of a layer group, substiture layer group 
    refLyrName = refLyr.longName
    if debug: addMsgAndPrint(refLyrName)
    while refLyrName.find('\\') > 0:
            groupLyrName = refLyrName[:refLyrName.find('\\')]
            if debug: addMsgAndPrint(groupLyrName)
            refLyr = findLyr(groupLyrName)[0]
            refLyrName = refLyr.longName
    try:
        addMsgAndPrint('    '+str(addLyr))
        arcpy.mapping.InsertLayer(dataFrame, refLyr, addLyr, insertPos)
        arcpy.Delete_management(lyrPath)
    except:
        addMsgAndPrint('    failed to insert '+str(addLyr)+' '+insertPos+' refLyr '+str(refLyr))
        if debug:
            mxd = arcpy.mapping.MapDocument('CURRENT')
            for df in arcpy.mapping.ListDataFrames(mxd):
                lList = arcpy.mapping.ListLayers(mxd, '*', df)
                addMsgAndPrint(' refLyr = '+str(refLyr))
                for lyr in lList:
                    addMsgAndPrint('      '+str(lyr)+', matches refLyr = '+str(lyr == refLyr))
                    if str(lyr) == str(refLyr):
                        writeLayerNames(lyr)
                        writeLayerNames(refLyr)
                        writeLayerNames(addLyr)
    """
    if lyr.dataSource == mup:
        DMU = os.path.dirname(fds)+'/DescriptionOfMapUnits'
        addMsgAndPrint('DMU = '+DMU)
        arcpy.AddJoin_management(lyr,'MapUnit',DMU,'MapUnit')
        addMsgAndPrint('DMU joined to layer '+lyr.longName)
        """



