#  GeMS_TranslateToShape_Arc10.5.py
#
#  Converts an GeMS-style ArcGIS geodatabase to 
#    open file format
#      shape files, .csv files, and pipe-delimited .txt files,
#      without loss of information.  Field renaming is documented in 
#      output file logfile.txt
#    simple shapefile format
#      basic map information in flat shapefiles, with much repetition 
#      of attribute information, long fields truncated, and much 
#      information lost. Field renaming is documented in output file
#      logfile.txt
#
#  Ralph Haugerud, USGS, Seattle
#    rhaugerud@usgs.gov

import arcpy
import sys, os, glob, time, shutil
from GeMS_utilityFunctions import *
from numbers import Number

versionString = 'GeMS_TranslateToShape_Arc10.5.py, version of 2 September 2017'

debug = False

# equivalentFraction is used to rank ProportionTerms from most 
#  abundant to least
equivalentFraction =   {'all':1.0,
			'only part':1.0,
			'dominant':0.6,
			'major':0.5,
			'significant':0.4,
			'subordinate':0.3,
			'minor':0.25,
			'trace':0.05,
			'rare':0.02,
			'variable':0.01,
			'present':0.0}

def usage():
	addMsgAndPrint( """
USAGE: GeMS_TranslateToShp_Arc10.5.py  <geodatabase> <outputWorkspace>

  where <geodatabase> must be an existing ArcGIS geodatabase.
  <geodatabase> may be a personal or file geodatabase, and the 
  .gdb or .mdb extension must be included.
  Output is written to directories <geodatabase (no extension)>-simple
  and <geodatabase (no extension)>-open in <outputWorkspace>. Output 
  directories, if they already exist, will be overwritten.
""")

shortFieldNameDict = {
        'IdentityConfidence':'IdeConf',
        'MapUnitPolys_ID':'MUPs_ID',
        'Description':'Descr',
        'HierarchyKey':'HKey',
        'ParagraphStyle':'ParaSty',
        'AreaFillRGB':'RGB',
        'AreaFillPatternDescription':'PatDes',
        'GeoMaterial':'GeoMat',
        'GeoMaterialConfidence':'GeoMatConf',
        'IsConcealed':'IsCon',
        'LocationConfidenceMeters':'LocConfM',
        'ExistenceConfidence':'ExiConf',
        'ContactsAndFaults_ID':'CAFs_ID',
        'PlotAtScale':'PlotAtSca'
        }
        

def remapFieldName(name):
    if shortFieldNameDict.has_key(name):
        return shortFieldNameDict[name]
    elif len(name) <= 10:
        return name
    else:
        name2 = name.replace('And','')
        name2 = name2.replace('Of','')
        name2 = name2.replace('Unit','Un')
        name2 = name2.replace('Source','Src')
        name2 = name2.replace('Shape','Shp')
        name2 = name2.replace('Hierarchy','H')
        name2 = name2.replace('Description','Descript')
        name2 = name2.replace('AreaFill','')
        name2 = name2.replace('Structure','Struct')
        name2 = name2.replace('STRUCTURE','STRUCT')
        name2 = name2.replace('user','Usr')
        name2 = name2.replace('created_','Cre')
        name2 = name2.replace('edited_','Ed')
        name2 = name2.replace('date','Dt')
        name2 = name2.replace('last_','Lst')

        newName = ''
        for i in range(0,len(name2)):
            if name2[i] == name2[i].upper():
                newName = newName + name2[i]
                j = 1
            else:
                j = j+1
                if j < 4:
                    newName = newName + name2[i]
        if len(newName) > 10:
            if newName[1:3] == newName[1:3].lower():
                newName = newName[0]+newName[3:]
        if len(newName) > 10:
            if newName[3:5] == newName[3:5].lower():
                newName = newName[0:2]+newName[5:]
        if len(newName) > 10:
            addMsgAndPrint('      '+ name + '  ' + newName)
        return newName	

def printFieldNames(fc):
    for f in fieldNameList(fc):
        print f
    print

def dumpTable(fc,outName,isSpatial,outputDir,logfile,isOpen,fcName):
    dumpString = '  Dumping {}...'.format(outName)
    if isSpatial: dumpString = '  {}'.format(dumpString)
    addMsgAndPrint(dumpString)
    if isSpatial:
        logfile.write('  feature class {} dumped to shapefile {}\n'.format(fc, outName))
    else:
        logfile.write('  table {} dumped to table {}\n'.format(fc, outName))
    logfile.write('    field name remapping: \n')
    # describe

    if debug:
        printFieldNames(fc)
        print
    
    desc = arcpy.Describe(fc)
    #addMsgAndPrint('{}, {}'.format(desc.baseName, desc.catalogPath))
   
    fields = arcpy.ListFields(fc)
    longFields = []
    shortFieldName = {}
    for field in fields:
        # translate field names
        #  NEED TO FIX TO DEAL WITH DescriptionOfMapUnits_ and DataSources_
        fName = field.name
        for prefix in ('DescriptionOfMapUnits','DataSources','Glossary',fcName):
            if fc <> prefix and fName.find(prefix) == 0 and fName <> fcName+'_ID':
                fName = fName[len(prefix)+1:]
        if len(fName) > 10:
            shortFieldName[field.name] = remapFieldName(fName)
            # write field name translation to logfile
            logfile.write('      '+field.name+' > '+shortFieldName[field.name]+'\n')
        else:
            shortFieldName[field.name] = fName
        if field.name not in ('OBJECTID','Shape','SHAPE','Shape_Length','Shape_Area'):
            #addMsgAndPrint(field.name)
            arcpy.AlterField_management(fc,field.name,shortFieldName[field.name])
        if field.length > 254:
            longFields.append(shortFieldName[field.name])
        if debug:
            print fName, shortFieldName[field.name]   
    # export to shapefile (named prefix+name)
    if isSpatial:
        if debug:  print 'dumping ',fc,outputDir,outName
        try:
            arcpy.FeatureClassToFeatureClass_conversion(fc,outputDir,outName)
        except:
            #addMsgAndPrint(arcpy.GetMessages())
            addMsgAndPrint('failed to translate table '+fc)
    else:
        arcpy.TableToTable_conversion(fc,outputDir,outName)
    if isOpen:
        # if any field lengths > 254, write .txt file
        if len(longFields) > 0:
            outText = outName[0:-4]+'.txt'
            logPath = os.path.join(outputDir, outText)
            logfile.write('    table '+fc+' has long fields, thus dumped to file '+outText+'\n')
            csvFile = open(logPath,'w')
            fields = fieldNameList(fc)
            if isSpatial:
                try:
                    fields.remove('Shape')
                except:
                    try:
                        fields.remove('SHAPE')
                    except:
                        addMsgAndPrint('No Shape field present.')
            with arcpy.da.SearchCursor(fc,fields) as cursor:
                for row in cursor:
                    rowString = str(row[0])
                    for i in range(1,len(row)):
                        if row[i] <> None:
                            if isinstance(row[i],Number):
                                xString = str(row[i])
                            else:
                                xString = row[i].encode('ascii','xmlcharrefreplace')
                            rowString = rowString+'|'+xString
                        else:
                            rowString = rowString+'|'
                    csvFile.write(rowString+'\n')
            csvFile.close()
    addMsgAndPrint('    Finished dump\n')
              
    
def makeOutputDir(gdb,outWS,isOpen):
    outputDir = os.path.join(outWS, os.path.basename(gdb)[0:-4])
    #outputDir = outWS+'/'+os.path.basename(gdb)[0:-4]
    if isOpen:
        outputDir = outputDir+'-open'
    else:
        outputDir = outputDir+'-simple'
    addMsgAndPrint('  Making {}\...'.format(outputDir))
    if os.path.exists(outputDir):
        """ET - easier way to remove directory and 
        subdirectories, empty or not is with shutil"""
        shutil.rmtree(outputDir) 

    os.mkdir(outputDir)
    logPath = os.path.join(outputDir, 'logfile.txt')
    logfile = open(logPath,'w')
    logfile.write('file written by '+versionString+'\n\n')
    return outputDir, logfile
    
def removeJoins(fc):
    addMsgAndPrint('    Testing '+fc+' for joined tables')
    #addMsgAndPrint('Current workspace is '+arcpy.env.workspace)
    joinedTables = []
    # list fields
    fields = arcpy.ListFields(fc)
    for field in fields:
        # look for fieldName that indicates joined table, and remove jo
        fieldName = field.name
        i = fieldName.find('.')
        if i > -1:
            joinedTableName = fieldName[0:i]
            if not (joinedTableName in joinedTables) and (joinedTableName) <> fc:
                try:
                    joinedTables.append(joinedTableName)
                    arcpy.removeJoin(fc,joinedTableName)
                except:
                    pass
    if len(joinedTables) > 0:
        jts = ''
        for jt in joinedTables:
            jts = jts+' '+jt
        addMsgAndPrint('      removed joined tables '+jts)
        
def remove_rc(gdb):
    """ET - added this function to check for and remove all relationship 
    classes from the copy of the geodatabase. You can't delete fields that 
    are involved in relationship classes. Consider moving this to utility
    functions"""
    origWS = arcpy.env.workspace
    relclass_list = arcpy.da.Walk(gdb, datatype = "RelationshipClass",
                    followlinks = True)
    for wkspc, path, relclasses in relclass_list:
        arcpy.env.workspace = wkspc
        for relclass in relclasses:
            arcpy.Delete_management(relclass)  
    arcpy.env.workspace = origWS 

def dummyVal(pTerm,pVal):
    if pVal == None:
        if pTerm in equivalentFraction:
            return equivalentFraction[pTerm]
        else:
            return 0.0
    else:
        return pVal

def description(unitDesc):
    unitDesc.sort()
    unitDesc.reverse()
    desc = ''
    for uD in unitDesc:
        if uD[3] == '': desc = desc+str(uD[4])+':'
        else:  desc = desc+uD[3]+':'
        desc = desc+uD[2]+'; '
    return desc[:-2]

def makeStdLithDict():
    addMsgAndPrint('  Making StdLith dictionary...')
    stdLithDict = {}
    rows = arcpy.searchcursor('StandardLithology',"","","","MapUnit")
    row = rows.next()
    unit = row.getValue('MapUnit')
    unitDesc = []
    pTerm = row.getValue('ProportionTerm'); pVal = row.getValue('ProportionValue')
    val = dummyVal(pTerm,pVal)
    unitDesc.append([val,row.getValue('PartType'),row.getValue('Lithology'),pTerm,pVal])
    while row:
        #print row.getValue('MapUnit')+'  '+row.getValue('Lithology')
        newUnit = row.getValue('MapUnit')
        if newUnit <> unit:
            stdLithDict[unit] = description(unitDesc)
            unitDesc = []
            unit = newUnit
        pTerm = row.getValue('ProportionTerm'); pVal = row.getValue('ProportionValue')
        val = dummyVal(pTerm,pVal)
        unitDesc.append([val,row.getValue('PartType'),row.getValue('Lithology'),pTerm,pVal])
        row = rows.next()
    del row, rows
    stdLithDict[unit] = description(unitDesc)
    return stdLithDict       

def mup2shp(gdbCopy,stdLithDict,outputDir,logfile):
    addMsgAndPrint('  Translating GeologicMap\MapUnitPolys...')
    arcpy.env.workspace = gdbCopy
    try:
        arcpy.MakeTableView_management('DescriptionOfMapUnits','DMU')
        if stdLithDict <> 'None':
                arcpy.AddField_management('DMU',"StdLith","TEXT",'','','255')
                rows = arcpy.UpdateCursor('DMU'  )
                row = rows.next()
                while row:
                    if row.MapUnit in stdLithDict:
                        row.StdLith = stdLithDict[row.MapUnit]
                        rows.updateRow(row)
                    row = rows.next()
                del row, rows
        arcpy.MakeFeatureLayer_management("GeologicMap\MapUnitPolys","MUP")
        arcpy.AddJoin_management('MUP','MapUnit','DMU','MapUnit')
        arcpy.AddJoin_management('MUP','DataSourceID','DataSources','DataSources_ID')
        arcpy.CopyFeatures_management('MUP','MUP2')
        DM = 'DescriptionOfMapUnits_'
        DS = 'DataSources_'
        MU = 'MapUnitPolys_'
        for field in (MU+'DataSourceID',
                      DM+'MapUnit',DM+'OBJECTID',DM+DM+'ID',DM+'Label',DM+'Symbol',DM+'DescriptionSourceID',
                      DS+'OBJECTID',DS+DS+'ID',DS+'Notes',DS+'URL'):
            arcpy.DeleteField_management('MUP2',field)
        dumpTable('MUP2','MapUnitPolys.shp',True,outputDir,logfile,False,'MapUnitPolys')
        arcpy.Delete_management('MUP2')
        
    except:
        addMsgAndPrint(arcpy.GetMessages())
        addMsgAndPrint('  Failed to translate MapUnitPolys')
    
def fc2shp(gdbCopy, fc, outputDir, logfile):
    """Extended this, through fcList built in main() to export all feature
    classes throughout the gdb including polygons"""
    """ET -Don't understand why this function was being passed 
    'GeologicMap/<featureclass>'. I removed that from input variable
    and built it up the path with os.path.join for proper 
    delimiter only for the message"""
    fcInFD = os.path.join('GeologicMap', fc)
    addMsgAndPrint('  Translating {}...'.format(fcInFD))
    
    desc = arcpy.Describe(fc)
    glosPath = os.path.join(gdbCopy, 'Glossary')
    dsPath = os.path.join(gdbCopy, 'DataSources')  
    #ET-set workspace to GeologicMap inside this funcion instead of in main()
    #geomapFD = os.path.join(gdbCopy, 'GeologicMap')
    #arcpy.env.workspace = geomapFD
    if debug:
        print 1
        printFieldNames(fc)
    
    fcShp = fc + '.shp'
    LIN = 'xx' + fc
    LIN2 = fc + '2'
    removeJoins(fc)
    
    addMsgAndPrint('    Making layer {} from {}'.format(LIN, fcInFD))
    arcpy.MakeFeatureLayer_management(desc.catalogPath, LIN)
    fieldNames = fieldNameList(LIN)
    if 'Type' in fieldNames:
        arcpy.AddField_management(LIN, 'Definition', 'TEXT', '#', '#', '254')
        arcpy.AddJoin_management(LIN, 'Type', glosPath, 'Term')
        arcpy.CalculateField_management(LIN, 'Definition', '!Glossary.Definition![0:254]', 'PYTHON')
        arcpy.RemoveJoin_management(LIN, 'Glossary')
    # command below are 9.3+ specific
    sourceFields = arcpy.ListFields(fc, '*SourceID')
    for sField in sourceFields:
        nFieldName = sField.name[:-2]
        arcpy.AddField_management(LIN, nFieldName, 'TEXT', '#', '#', '254')
        arcpy.AddJoin_management(LIN, sField.name, dsPath, 'DataSources_ID')
        arcpy.CalculateField_management(LIN, nFieldName, '!DataSources.Source![0:254]', 'PYTHON')
        arcpy.RemoveJoin_management(LIN, 'DataSources')
        arcpy.DeleteField_management(LIN, sField.name)
    arcpy.CopyFeatures_management(LIN, LIN2)
    dumpTable(LIN2, fcShp, True, outputDir, logfile, False, fc)
    arcpy.Delete_management(LIN)
    arcpy.Delete_management(LIN2)
    
def main(gdbCopy,outWS,gdbSrc):
    arcpy.env.workspace = gdbCopy
    #
    # Simple version
    #
    isOpen = False
    addMsgAndPrint('')
    outputDir, logfile = makeOutputDir(gdbSrc,outWS,isOpen)
    
    #ET- first dump MapUnitPolys beacause it requires an extra join
    #arcpy.env.workspace = gdbCopy
    if 'StandardLithology' in arcpy.ListTables():
        stdLithDict = makeStdLithDict()
    else:
        stdLithDict = 'None'
    mup2shp(gdbCopy, stdLithDict, outputDir, logfile)
    
    #ET - now dump everything else
    #ET - arcpy.env.workspace = 'GeologicMap' is not a robust way to set the workspace
    arcpy.env.workspace = gdbCopy
    #ET- get feature classes of <ftype> not in feature datasets
    fcList = []
    ftypes = ['POINT', 'LINE', 'POLYGON']
    for ftype in ftypes:
        fcList.extend(arcpy.ListFeatureClasses('', ftype))
        
    #ET- append feature classes in any feature dataset
    for fd in arcpy.ListDatasets('', 'Feature'):
        arcpy.env.workspace = fd
        for ftype in ftypes:
            fcList.extend(arcpy.ListFeatureClasses('', ftype))
            
    #ET- translate to shapefiles any feature classes not named MapUnitPolys
    for fc in fcList:
        if fc <> 'MapUnitPolys':
            fc2shp(gdbCopy, fc, outputDir, logfile)
    logfile.close()
    #
    # Open version
    #
    isOpen = True
    addMsgAndPrint('')
    outputDir, logfile = makeOutputDir(gdbSrc,outWS,isOpen)
    # list featuredatasets
    arcpy.env.workspace = gdbCopy
    fds = arcpy.ListDatasets('', 'Feature')
    # for each featuredataset
    for fd in fds:
        arcpy.env.workspace = fd
        #fdPath = arcpy.Describe(fd).catalogPath
        addMsgAndPrint( '  Processing feature data set {}...'.format(arcpy.env.workspace))
        logfile.write('Feature data set {} \n'.format(fd))
        try:
            spatialRef = arcpy.Describe(fd).SpatialReference
            logfile.write('  spatial reference framework\n')
            logfile.write('    name = {}\n'.format(spatialRef.Name))
            logfile.write('    spheroid = {}\n'.format(spatialRef.SpheroidName))
            logfile.write('    projection = {}\n'.format(spatialRef.ProjectionName))
            logfile.write('    units = {}\n'.format(spatialRef.LinearUnitName))
        except:
            logfile.write('  spatial reference framework appears to be undefined\n')
        # generate featuredataset prefix
        pfx = ''
        for i in range(0,len(fd)-1):
            if fd[i] == fd[i].upper():
                pfx = pfx + fd[i]
        
        fcList = arcpy.ListFeatureClasses()
        if fcList <> None:
            for fc in fcList:
                #addMsgAndPrint('catalogPath: {}'.format(arcpy.Describe(fc).catalogPath))
                # don't dump Anno classes
                if arcpy.Describe(fc).featureType <> 'Annotation':
                    outName = pfx+'_'+fc+'.shp'
                    dumpTable(fc,outName,True,outputDir,logfile,isOpen,fc)
                else:
                    addMsgAndPrint('    Skipping annotation feature class '+fc+'\n')
        else:
            addMsgAndPrint('   No feature classes in this dataset!')
        logfile.write('\n')
    # list tables
    arcpy.env.workspace = gdbCopy
    for tbl in arcpy.ListTables():
        outName = tbl+'.csv'
        dumpTable(tbl,outName,False,outputDir,logfile,isOpen,tbl)
    logfile.close()

### START HERE ###
if len(sys.argv) <> 3 or not os.path.exists(sys.argv[1]) or not os.path.exists(sys.argv[2]):
    usage()
else:
    addMsgAndPrint('  {}'.format(versionString))
    gdbSrc = os.path.abspath(sys.argv[1])
    ows = os.path.abspath(sys.argv[2])
    arcpy.env.QualifiedFieldNames = False
    arcpy.env.overwriteoutput = True
    ## fix the new workspace name so it is guaranteed to be novel, no overwrite
    gdbCopy = os.path.join(ows, 'xx' + os.path.basename(gdbSrc))
    if arcpy.Exists(gdbCopy):
        arcpy.Delete_management(gdbCopy)
    addMsgAndPrint('  Copying {} to temporary geodatabase...'.format(os.path.basename(gdbSrc)))
    arcpy.Copy_management(gdbSrc,gdbCopy)
    
    #ET - if relationships exist in the source gdb, remove them in the copy
    #ET - DeleteField_management in def fc2shp cannot run if the field is involved in a relationship
    addMsgAndPrint('  Looking for and removing relationships from {}'.format(gdbCopy))
    remove_rc(gdbCopy) 
    
    main(gdbCopy,ows,gdbSrc)
    addMsgAndPrint('\n  Deleting temporary geodatabase...')
    arcpy.env.workspace = ows
    time.sleep(5)
    try:
        arcpy.Delete_management(gdbCopy)
    except:
        addMsgAndPrint('    As usual, failed to delete temporary geodatabase')
        addMsgAndPrint('    Please delete {}\n'.format(gdbCopy))
        
        
