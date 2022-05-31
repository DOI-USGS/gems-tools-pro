##New, improved make polys

import arcpy, sys, os
from pathlib import Path
from GeMS_utilityFunctions import *
from GeMS_Definition import tableDict

# 5 January 2018: Modified error message for topology that contains polys
#
# 29 May 2019: Evan Thoms
#   Replaced concatenated path strings and os.path operations
#     with Python 3 pathlib operations.
#   Replaced concatenated message strings with string.format()
#   Replaced arcpy.mapping operations with arcpy.mp operations
#   Removed all the fiddling around with layerfiles. Now, we change the 
#     contents of the datasource without removing and then adding the layer.
#   Seems to work. Didn't do extensive testing of the error reporting but did edit 
#     a contact and found that the new polygons were created correctly and additions 
#     were made to edit_ChangedPolys

versionString = 'GeMS_MakePolys3_AGP2.py, version of 15 January 2020'
rawurl = 'https://raw.githubusercontent.com/usgs/gems-tools-pro/master/Scripts/GeMS_MakePolys3_AGP2.py'
checkVersion(versionString, rawurl, 'gems-tools-pro')

debug = False

def checkMultiPts(multiPts, badPointList, badPolyList):
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
            if multiPts[i][0] != polyID:
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

##################################

addMsgAndPrint(versionString)

fds = sys.argv[1]
gdb = Path(fds).parent
save_mup = False
if sys.argv[2].lower() == 'true':
    save_mup = True

try:
    label_points = arcpy.da.Describe(sys.argv[3])['catalogPath']
except:
    label_points = ''

simple_mode = True  
if sys.argv[4].lower() in ['false', 'no']:
    simple_mode = False
    
# get caf, mup, name_token
# dictionary
fd_dict = arcpy.da.Describe(fds)
children = fd_dict['children']

# ContactsAndFaults
caf = [child['catalogPath'] for child in children if child['baseName'].lower().endswith('contactsandfaults')][0]
short_caf = Path(caf).name

# MapUnitPolys
mup = [child['catalogPath'] for child in children if child['baseName'].lower().endswith('mapunitpolys')][0]
short_mup = Path(mup).name

# feature dataset name token
fd_name = fd_dict['baseName']
if fd_name.lower().endswith('correlationofmapunits'):
    name_token = 'CMU'
else:
    name_token = fd_name

#if not simple_mode:
# get string of joined Path objects
badLabels = str(Path(fds) / f'errors_{name_token}multilabels')
badPolys = str(Path(fds) / f'errors_{name_token}multilabelPolys')
blankPolys = str(Path(fds) / f'errors_{name_token}unlabeledPolys')
centerPoints = 'xxxCenterPoints'
centerPoints2 = f'{centerPoints}2'
centerPoints3 = f'{centerPoints}3'
temporaryPolys = 'xxxTempPolys'
oldPolys = str(Path(fds).joinpath('xxxOldPolys'))
changedPolys = str(Path(fds).joinpath(f'edit_{name_token}ChangedPolys'))
cafLayer = 'caf_layer'

if simple_mode:
    # collapse polygons to points
    labels = 'memory\labels'
    arcpy.management.FeatureToPoint(mup, labels, "INSIDE")
    
    # append label points if they have been included
    if label_points:
        try:
            arcpy.management.Append(label_points, labels, "NO_TEST")
        except:
            arcpy.AddWarning(f'Could not make use of {label_points}. Check the geometry and attributes')
    
    # save a copy of MapUnitPolys
    if save_mup:
        arcpy.AddMessage("Saving MapUnitPolys")
        arcpy.management.Copy(mup, getSaveName(mup))
    
    # empty MapUnitPolys
    arcpy.management.TruncateTable(mup)
    
    # make selection set without concealed lines
    fld = arcpy.AddFieldDelimiters(caf, 'IsConcealed')
    where = f"LOWER({fld}) NOT IN ('y', 'yes')"
    contacts = arcpy.management.SelectLayerByAttribute(caf, where_clause=where)
    
    # make new polys
    new_polys = "memory\mup"
    arcpy.management.FeatureToPolygon(contacts, new_polys, label_features=labels)
    
    # append to the now empty MapUnitPolys
    arcpy.management.Append(new_polys, mup, "NO_TEST")

else:
    # make layer view of inCaf without concealed lines
    addMsgAndPrint('  Making layer view of CAF without concealed lines')
    sqlQuery = f"LOWER({arcpy.AddFieldDelimiters(caf, 'IsConcealed')}) NOT IN ('y', 'yes')"
    testAndDelete(cafLayer)
    arcpy.management.MakeFeatureLayer(caf, cafLayer, sqlQuery)

    #make temporaryPolys from layer view
    addMsgAndPrint(f'  Making {temporaryPolys}')
    testAndDelete(temporaryPolys)
    arcpy.FeatureToPolygon_management(cafLayer, temporaryPolys)
    if debug:
        addMsgAndPrint('temporaryPolys fields are {str(fieldNameList(temporaryPolys))}')

    #make center points (within) from temporarypolys
    addMsgAndPrint(f'  Making {centerPoints}')
    testAndDelete(centerPoints)       
    tempPolyPath = arcpy.Describe(temporaryPolys).catalogPath     
    arcpy.FeatureToPoint_management(temporaryPolys, centerPoints, "INSIDE")

    if debug:
        addMsgAndPrint(f'centerPoints fields are {str(fieldNameList(centerPoints))}')
        
    # get rid of ORIG_FID field
    arcpy.DeleteField_management(centerPoints, 'ORIG_FID')

    #identity center points with mup
    testAndDelete(centerPoints2)
    arcpy.Identity_analysis(centerPoints, mup, centerPoints2, 'NO_FID')

    # delete points with MapUnit = ''
    ## first, make layer view
    addMsgAndPrint("    Deleting centerPoints2 MapUnit = '' ")
    sqlQuery =  "{} = ''".format(arcpy.AddFieldDelimiters(centerPoints2, 'MapUnit'))
    testAndDelete('cP2Layer')
    arcpy.MakeFeatureLayer_management(centerPoints2, 'cP2Layer', sqlQuery)

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
            addMsgAndPrint('field {} is missing'.format(fd))
            try:
                if fDef[1] == 'String':
                    arcpy.AddField_management(thisFC, fDef[0], transDict[fDef[1]], '#', '#', fDef[3], '#', transDict[fDef[2]])
                else:
                    arcpy.AddField_management(thisFC,fDef[0], transDict[fDef[1]], '#', '#', '#', '#', transDict[fDef[2]])
                cp2Fields.append(fDef[0])
            except:
                addMsgAndPrint(f'Failed to add field {fDef[0]} to feature class {featureClass}')
                addMsgAndPrint(arcpy.GetMessages(2))        

    # if label_points specified
    ## add any missing fields to centerPoints2
    if arcpy.Exists(label_points):
        lpFields = arcpy.ListFields(label_points)
        for lpF in lpFields:
            if not lpF.name in cp2Fields:
                if lpF.type in ('Text','STRING'):
                    arcpy.AddField_management(centerPoints2, lpF.name, 'TEXT', '#', '#', lpF.length)
                else:
                    arcpy.AddField_management(centerPoints2, lpF.name, typeTransDict[lpF.type])
                    
    # append label_points to centerPoints2
    if arcpy.Exists(label_points):
        arcpy.Append_management(label_points,centerPoints2, 'NO_TEST')

    #if mup are to be saved, copy mup to savedPolys
    if save_mup:
        addMsgAndPrint('  Saving MapUnitPolys')
        arcpy.Copy_management(mup, getSaveName(mup)) 

    # make oldPolys
    addMsgAndPrint('  Making oldPolys')
    testAndDelete(oldPolys)
    if debug:
        addMsgAndPrint(' oldPolys should be deleted!')
    arcpy.Copy_management(mup, oldPolys)

    ## copy field MapUnit to new field OldMapUnit
    arcpy.AddField_management(oldPolys, 'OldMapUnit', 'TEXT', '', '', 40)
    arcpy.CalculateField_management(oldPolys, 'OldMapUnit', "!MapUnit!", "PYTHON_9.3")

    ## get rid of excess fields in oldPolys
    fields = fieldNameList(oldPolys)
    if debug:
        addMsgAndPrint('oldPoly fields = ')
        addMsgAndPrint(f'  {str(fields)}')
    for field in fields:
        if not field.lower() in ('oldmapunit', 'objectid', 'shape', 'shape_area', 'shape_length'):
            if debug:
                addMsgAndPrint(f'     deleting {field}')
            arcpy.DeleteField_management(oldPolys, field)

    #make new mup from layer view, with centerpoints2
    addMsgAndPrint('  Making new MapUnitPolys')
    # create polygons in memory
    arcpy.FeatureToPolygon_management(cafLayer, r"in_memory\mup", '', 'ATTRIBUTES', centerPoints2)
    # delete all features in mup
    arcpy.DeleteFeatures_management(mup)
    # and append the newly created features
    arcpy.Append_management(r"in_memory\mup", mup, "NO_TEST")
    arcpy.Delete_management(r"in_memory\mup")

    testAndDelete(cafLayer)

    addMsgAndPrint('  Making changedPolys')
    #intersect oldPolys with mup to make changedPolys
    if arcpy.Exists(changedPolys):
        arcpy.Identity_analysis(mup, oldPolys, r"in_memory\changedPolys")
        arcpy.DeleteFeatures_management(changedPolys)
        arcpy.Append_management(r"in_memory\changedPolys", changedPolys)
        arcpy.Delete_management(r"in_memory\changedPolys")
    else:
        arcpy.Identity_analysis(mup, oldPolys, changedPolys)

    #addMsgAndPrint('     '+str(numberOfRows(changedPolys))+' rows in changedPolys')
    ## make feature layer, select MapUnit = OldMapUnit and delete
    addMsgAndPrint('     deleting features with MapUnit = OldMapUnit')
    sqlQuery = f"{arcpy.AddFieldDelimiters(changedPolys,'MapUnit')} = {arcpy.AddFieldDelimiters(changedPolys,'OldMapUnit')}"

    testAndDelete('cpLayer')
    arcpy.MakeFeatureLayer_management(changedPolys, 'cpLayer', sqlQuery)
    arcpy.DeleteFeatures_management('cpLayer')
    addMsgAndPrint(f'     {str(numberOfRows(changedPolys))} rows in changedPolys')

    #identity centerpoints2 with mup
    addMsgAndPrint('  Finding label errors')
    testAndDelete(centerPoints3)
    arcpy.Identity_analysis(centerPoints2, mup, centerPoints3)

    if debug: addMsgAndPrint(str(fieldNameList(centerPoints3)))

    #make list from centerPoints3:  mupID, centerPoints2ID, cp2.MapUnit, mup.MapUnit
    cpList = []
    mupID = 'FID_{}'.format(Path(mup).name)
    cp2ID = 'FID_xxxcenterPoints2'
    fields = [mupID, cp2ID, 'MapUnit_1', 'MapUnit']
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
        if cpList[i][0] != lastPt[0]:  # different poly than lastPt
            badPointList, badPolyList = checkMultiPts(multiPts, badPointList, badPolyList)
            lastPt = cpList[i]
            multiPts = [lastPt]
        else: # we are looking at more points in same poly
            multiPts.append(cpList[i])
    badPointList, badPolyList = checkMultiPts(multiPts, badPointList, badPolyList)

    #from badPolyList, make badPolys
    if len(badPolyList) > 0:
        addMsgAndPrint(f'    Making {badPolys}')
        if arcpy.Exists(badPolys):
            arcpy.CopyFeatures_management(mup, r"in_memory\badPolys")
            arcpy.DeleteFeatures_management(badPolys)
            arcpy.Append_management(r"in_memory\badPolys", badPolys)
            arcpy.Delete_management(r"in_memory\badPolys")
        else:
            arcpy.CopyFeatures_management(mup, badPolys)

        with arcpy.da.UpdateCursor(badPolys,['OBJECTID']) as cursor:
            for row in cursor:
                if row[0] not in badPolyList:
                    cursor.deleteRow()

    if len(badPointList) > 0:
        #from badPointlist of badpoints, make badLabels
        if arcpy.Exists(badLabels):
            arcpy.CopyFeatures_management(centerPoints2, r"in_memory\badLabels")
            arcpy.DeleteFeatures_management(badLabels)
            arcpy.Append_management(r"in_memory\badLabels", badLabels)
            arcpy.Delete_management(r"in_memory\badLabels")
        else:
            arcpy.CopyFeatures_management(centerPoints2,badLabels)
            
        with arcpy.da.UpdateCursor(badLabels,['OBJECTID']) as cursor:
            for row in cursor:
                if row[0] not in badPointList:
                    cursor.deleteRow()
                   
    #make blankPolys
    addMsgAndPrint(f'    Making {blankPolys}')
    if arcpy.Exists(blankPolys):
        arcpy.CopyFeatures_management(mup, r"in_memory\blankPolys")
        arcpy.DeleteFeatures_management(blankPolys)
        arcpy.Append_management(r"in_memory\blankPolys", blankPolys)
        arcpy.Delete_management(r"in_memory\blankPolys")
    else:
        arcpy.CopyFeatures_management(centerPoints2, blankPolys)

    query = "{} <> ''".format(arcpy.AddFieldDelimiters(blankPolys, 'MapUnit'))
       
    testAndDelete('blankP')
    arcpy.MakeFeatureLayer_management(blankPolys, 'blankP', query)
    arcpy.DeleteFeatures_management('blankP')
    addMsgAndPrint(f'    {str(len(badPolyList))} multi-label polys')
    addMsgAndPrint(f'    {str(len(badPointList))} multiple, conflicting, label points')
    addMsgAndPrint(f'    {str(numberOfRows(blankPolys))} unlabelled polys')

    addMsgAndPrint('  Cleaning up')
    #delete oldpolys, temporaryPolys, centerPoints, centerPoints2, centerPoints3
    for fc in oldPolys, temporaryPolys, centerPoints, centerPoints2, centerPoints3, cafLayer, 'cP2Layer':
        testAndDelete(fc)
    


