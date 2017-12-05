# script to re-assign ID numbers to an NCGMP09-stype geodatabase
# Ralph Haugerud, USGS, Seattle WA, rhaugerud@usgs.gov
#

import arcpy, sys, time, os.path, math, uuid
from string import whitespace
from GeMS_utilityFunctions import *

versionString = 'GeMS_reID_Arc10.py, version of 2 September 2017'
# modified to not work on a copy of the input database. Backup first!
# 15 Sept 2016: modified to, by default, not reset DataSource_ID values

idRootDict = {
        'CartographicLines':'CAL',
        'ContactsAndFaults':'CAF',
        'CMULines':'CMULIN',
        'CMUPolys':'CMUPLY',
        'CMUPoints':'CMUPNT',
        'CMUText':'CMUTXT',
        'DataSources':'DAS',
        'DataSourcePolys':'DSP',
        'DescriptionOfMapUnits':'DMU',
        'ExtendedAttributes':'EXA',
        'FossilPoints':'FSP',
        'GeochemPoints':'GCM',
        'GeochronPoints':'GCR',
        'GeologicEvents':'GEE',
        'GeologicLines':'GEL',
        'Glossary':'GLO',
        'IsoValueLines':'ISL',
        'MapUnitPoints':'MUP',
        'MapUnitPolys':'MUP',
        'OrientationPoints':'ORP',
        'OtherLines':'OTL',
        'OtherPolys':'OTP',
        'PhotoPoints':'PHP',
        'RepurposedSymbols':'RPS',
        'StandardLithology':'STL',
               }

idDict = {}
fctbs = []  # feature class and table inventory
exemptedPrefixes = ('errors_','ed_')  # prefixes that flag a feature class as not permanent data

def usage():
	print """
  Usage:  prompt> ncgmp09_reID.py <inGeodatabaseName> <outGeodatabaseName>
                  <UseGUID>
  
	<inGeodatabaseName> can be either a personal geodatabase or a file 
	geodatabase, .mdb or .gdb. The filename extension must be included.
	<outGeodatabaseName> must be of the same type and must not exist.

	ncgmp09_reID.py re-casts all ID values into form XXXnnnn. ID values 
	that are not primary keys within the database are left unaltered and 
	a record is written to file <outputGeodatabaseName>.txt.

	If <useGUID> (boolean) is True, GUIDs are created for ID values.
	Otherwise ID values are short character strings that identify tables
        (e.g., MUP for MapUnitPolys) followed by consecutive zero-padded
        integers.
"""

def doReID(fc):
    doReID = True
    for exPfx in exemptedPrefixes:
        if fc.find(exPfx) == 0:
            doReID = False
    return doReID

def elapsedTime(lastTime):
	thisTime = time.time()
	addMsgAndPrint('    %.1f sec' %(thisTime - lastTime))
	return thisTime


def idRoot(tb,rootCounter):
	if tb in idRootDict:
		return idRootDict[tb],rootCounter
	else:
		rootCounter = rootCounter + 1
		return 'X'+str(rootCounter)+'X',rootCounter

def getPFKeys(table):
    addMsgAndPrint(table)
    fields2 = arcpy.ListFields(table)
    fKeys = []
    pKey = ''
    for field in fields2:
        ### this assumes only 1 _ID field!
        if field.name == table+'_ID':
            pKey = field.name
        else: 
            if field.name.find('ID') > 0 and field.type == 'String':
                fKeys.append(field.name)
    return pKey,fKeys

def inventoryDatabase(dbf,noSources):
    arcpy.env.workspace = dbf
    tables = arcpy.ListTables()
    if noSources:  # then don't touch DataSource_ID values 
        for tb in tables:
            if tb == 'DataSources':     
                tables.remove(tb)
                addMsgAndPrint('    skipping DataSources')
    for table in tables:
        pKey,fKeys = getPFKeys(table)
        fctbs.append([dbf,'',table,pKey,fKeys])		
    fdsets = arcpy.ListDatasets()
    for fdset in fdsets:
        arcpy.env.workspace = dbf+'/'+fdset
        fcs = arcpy.ListFeatureClasses()
        for fc in fcs:
            if doReID(fc):
                pKey,fKeys = getPFKeys(fc)
                fctbs.append([dbf,fdset,fc,pKey,fKeys])

def buildIdDict(table,sortKey,keyRoot,pKey,lastTime,useGUIDs):
    addMsgAndPrint('  Setting new _IDs for '+table)
    result = arcpy.GetCount_management(table)
    nrows = int(result.getOutput(0))
    width = int(math.ceil(math.log10(nrows+1)))
    rows = arcpy.UpdateCursor(table,"","","",sortKey)
    n = 1
    for row in rows:
        oldID = row.getValue(pKey)
        # calculate newID
        if useGUIDs: 
            newID = str(uuid.uuid4())
        else: 
            newID = keyRoot+str(n).zfill(width)
        try:
            row.setValue(pKey,newID)
            rows.updateRow(row)
        except:
            print 'ERROR'
            print 'pKey = '+str(pKey)+'  newID = '+str(newID)
        n = n+1
        #print oldID, newID
        #add oldID,newID to idDict
        if oldID <> '' and oldID <> None:
            idDict[oldID] = newID
    return elapsedTime(lastTime)
	

def reID(table,keyFields,lastTime,outfile):
	addMsgAndPrint('  resetting IDs for '+table)
	rows = arcpy.UpdateCursor(table)
	n = 1
	row = rows.next()
	while row:
		for field in keyFields:
			oldValue = row.getValue(field)
			if oldValue in idDict:
				row.setValue(field,idDict[oldValue])
			else:
				#print table, field, oldValue
				outfile.write(table+' '+field+' '+str(oldValue)+'\n')
		# update row
		rows.updateRow(row)
		n = n+1
		row = rows.next()
	return elapsedTime(lastTime)



def main(lastTime, dbf, useGUIDs, noSources):
    rootCounter = 0
    addMsgAndPrint('Inventorying database')
    inventoryDatabase(dbf, noSources)
    lastTime = elapsedTime(lastTime)
    arcpy.env.workspace = dbf
    for fctb in fctbs:
            #addMsgAndPrint(fctb)
            arcpy.env.workspace = fctb[0]+fctb[1]
            tabName = tableName = fctb[2]
            pKey,fKeys = getPFKeys(tableName)
            if tableName == 'MapUnitPoints':
                pKey = 'MapUnitPolys_ID'
            if tableName == 'Glossary': sortKey = 'Term A'
            elif tableName == 'DescriptionOfMapUnits': sortKey = 'HierarchyKey A'
            elif tableName == 'StandardLithology': sortKey = 'MapUnit A'
            else: sortKey = 'OBJECTID A'
            # deal with naming of CrossSection tables as CSxxTableName
            if fctb[1].find('CrossSection') == 0:
                    csSuffix = fctb[1][12:]
                    tabName = tableName[2+len(csSuffix):]
            idRt,rootCounter = idRoot(tabName,rootCounter)
            if tabName <> tableName:
                    prefix = 'CS'+csSuffix+idRt
            else:
                    prefix = idRt
            if pKey <> '':
                if sortKey[:-2] in fieldNameList(tableName):
                    lastTime = buildIdDict(tableName,sortKey,prefix,pKey,lastTime,useGUIDs)
                else:
                    addMsgAndPrint('Skipping '+tableName+', no field '+sortKey[:-2])
                

    # purge IdDict of quasi-null keys
    addMsgAndPrint('Purging idDict of quasi-null keys')
    idKeys = idDict.keys()
    for key in idKeys:
            if len(key.split()) == 0:
                    print 'NullKey', len(key)
                    del idDict[key]
                          
    outfile = open(dbf+'.txt','w')
    outfile.write('Database '+dbf+'. \nList of ID values that do not correspond to any primary key in the database\n')
    outfile.write('--table---field----field value---\n')
    for fctb in fctbs:
            arcpy.env.workspace = fctb[0]+fctb[1]
            keyFields = fctb[4]
            #keyFields.append(fctb[3])
            if fctb[3] <> '':  # primary key is identified as '' (i.e., doesn't exist, so not an NCGMP09 feature class)
                lastTime = reID(fctb[2],keyFields,lastTime,outfile)
    outfile.close()
    return lastTime

### START HERE ###

startTime = time.time()
lastTime = time.time()
useGUIDs = False
addMsgAndPrint(versionString)

if not os.path.exists(sys.argv[1]):
	usage()
else:
        lastTime = elapsedTime(lastTime)
        if len(sys.argv) >= 3:
                if sys.argv[2].upper() == 'TRUE':
                        useGUIDs = True
                else:
                        useGUIDs = False
        if len(sys.argv) >=4:
                if sys.argv[3].upper() == 'TRUE':
                        noSources = True
                else:
                        noSources = False

        dbf = os.path.abspath(sys.argv[1])
        arcpy.env.workspace = ''
        lastTime = elapsedTime(lastTime)
        lastTime = main(lastTime, dbf, useGUIDs, noSources)
        lastTime = elapsedTime(startTime)



