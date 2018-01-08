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

hide_fields = ['MapUnitPolys.DataSourceID',
               'DescriptionOfMapUnits.OBJECTID',
               'DescriptionOfMapUnits.MapUnit',
               'DescriptionOfMapUnits.Label',
               'DescriptionOfMapUnits.Symbol',
               'DescriptionOfMapUnits.DescriptionOfMapUnits_ID',               
               'DataSources.OBJECTID',
               'DataSources.DataSourcesID',
               'DataSources.Notes']        

        
def dataPathDict(gdb, d_type, f_type):
    """dictionary of objects in a gdb with their names as keys and their paths
    as values using da.Walk"""
    dictionary = {}
    walk = arcpy.da.Walk(gdb, datatype=d_type, type=f_type)
    
    for dirpath, dirnames, filenames in walk:
        if d_type == 'FeatureDataset':
            for dirname in dirnames:
                object_path = os.path.join(dirpath, dirname)
                dictionary[dirname] = object_path
        else:
            for filename in filenames:
                object_path = os.path.join(dirpath, filename)
                dictionary[filename] = object_path

    return dictionary
      
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
    
def dumpTable(lyr, outName, isSpatial, outputDir, logfile, isOpen, srcName):
    """Takes in-memory feature or table layers, shortens field names if necessary, 
    writes feature classes to shapefiles, writes tables to dbf. If any field in
    the layer is longer than 255 characters, the entire table is also written
    out to csv. Note that the CopyRows tool used to write to csv results in
    OBJECTID being exported, even when being set to hidden in a field info object
    and all values get written to -1."""
    out_path = os.path.join(outputDir, outName)
    dumpString = '  Dumping {}...'.format(outName)
    if isSpatial: dumpString = '  {}'.format(dumpString)
    addMsgAndPrint(dumpString)
    if isSpatial:
        logfile.write('  feature class {} dumped to shapefile {}\n'.format(srcName, outName))
    else:
        logfile.write('  table {} dumped to table {}\n'.format(srcName, outName))
    logfile.write('    field name remapping: \n')

    if debug:
        printFieldNames(lyr)
        print
   
    #build a field info object for resetting field names and visibility property
    desc = arcpy.Describe(lyr)
    field_info = desc.fieldInfo
    
    #go through the fields one at a time
    longFields = []
    shortFieldName = {}
    fields = arcpy.ListFields(lyr)
    for field in fields:
        #translate field names
        #first, parse the qualified name in case there is a join
        #we are no longer working with joined tables that have been written to disk
        #so we don't have to catch <table>_<field> strings, ie. with '_' in name
        parsed_name = arcpy.ParseFieldName(field.name)
        field_name = parsed_name.split(", ")[3]
        index = field_info.findFieldByName (field.name)
        
        #hide fields we don't want exported at all
        #hide_fields is a list defined at the top
        if field.name in hide_fields:
            field_info.setVisible(index, "HIDDEN")
        else:
            #deal with long field names. If they are long, shorten them
            if len(field_name) > 10:
                short_name = remapFieldName(field_name)
                # write field name translation to logfile
                logfile.write('      '+field_name+' > '+short_name+'\n')
            #otherwise, they are ok.
            else:
                short_name = field_name
            field_info.setNewName(index, short_name)
            field_info.setVisible(index, 'VISIBLE')
            
            #if this is a long field, keep track of it. It will be written to a 
            #text file if we are processing the open version
            if field.length > 254:
                longFields.append(field.name)

    if debug:
        print field_name, short_name
    
    #export to shapefile or dbf (named prefix+name)
    if isSpatial:
        if debug:  print 'dumping ',objPath,outputDir,outName
        try:
            arcpy.MakeFeatureLayer_management(lyr, "lyr2", "", "", field_info)
            arcpy.CopyFeatures_management("lyr2", out_path)
        except:
            addMsgAndPrint('failed to translate feature class {}'.format(srcName))
    else:
        try:
            arcpy.MakeTableView_management(lyr, "lyr2", "", "", field_info)
            arcpy.CopyRows_management ("lyr2", out_path)
        except:
            addMsgAndPrint('failed to translate table {}'.format(srcName))
         
    #if any field lengths > 254, write .txt file
    if isOpen and len(longFields) > 0:
        logfile.write('    table {} has long fields, thus dumped to file {}\n'
                       .format(srcName, srcName+".csv"))
        txt_hide_fields = ['OBJECTID', 'Shape', 'SHAPE']
        out_path = os.path.join(outputDir, srcName+".csv")
        
        for index in range(0, field_info.count):
            field_name = field_info.getfieldname(index)
            if field_name in txt_hide_fields:
                field_info.setVisible(index, 'HIDDEN')
            else:
                field_info.setNewName(index, field_name)
                field_info.setVisible(index, 'VISIBLE')
                
        arcpy.MakeTableView_management(lyr, "layerastable", "", "", field_info)
        arcpy.CopyRows_management("layerastable", out_path)
    addMsgAndPrint('    Finished dump\n')
    
    testAndDelete(lyr)
    testAndDelete('lyr2')
    testAndDelete('layerastable')
        
def makeOutputDir(gdb,outWS,isOpen):
    outputDir = os.path.join(outWS, os.path.basename(gdb)[0:-4])
    if isOpen:
        outputDir = outputDir+'-open'
    else:
        outputDir = outputDir+'-simple'
    addMsgAndPrint('  Making {}\...'.format(outputDir))
    if os.path.exists(outputDir):
        shutil.rmtree(outputDir) 

    os.mkdir(outputDir)
    logPath = os.path.join(outputDir, 'logfile.txt')
    logfile = open(logPath,'w')
    logfile.write('file written by '+versionString+'\n\n')
    return outputDir, logfile
    
def removeJoins(fc):
    addMsgAndPrint('    Testing {} for joined tables'.format(fc))
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
        addMsgAndPrint('      removed joined tables {}'.format(jts))
        
def remove_rc(gdb):
    """ET - added this function to check for and remove all relationship 
    classes from the copy of the geodatabase. You can't delete or change the 
    names of fields that are involved in relationship classes"""
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

def makeStdLithDict(slPath):
    """Updated this to use the explicit path to StandardLithology table and 
        da.SearchCursor"""
    addMsgAndPrint('  Making StdLith dictionary...')
    stdLithDict = {}
    rows = arcpy.da.SearchCursor(slPath,["MapUnit","ProportionTerm","ProportionValue"
                                         "PartType","Lithology"])
    row = rows.next()
    unit = row[0]
    unitDesc = []
    pTerm = row[1]; pVal = row[2]
    val = dummyVal(pTerm,pVal)
    unitDesc.append([val,row[3],row[4],pTerm,pVal])
    while row:
        #print row.getValue('MapUnit')+'  '+row.getValue('Lithology')
        newUnit = row[0]
        if newUnit <> unit:
            stdLithDict[unit] = description(unitDesc)
            unitDesc = []
            unit = newUnit
        pTerm = row[1]; pVal = row[2]
        val = dummyVal(pTerm,pVal)
        unitDesc.append([val,row[3],row[4],pTerm,pVal])
        row = rows.next()
    del row, rows
    stdLithDict[unit] = description(unitDesc)
    
    return stdLithDict       

def mup2shp(fcMUP, tbDMU, stdLithDict, dsPath, outputDir, logfile):
    """Updated to work with the explicit path to the copies of MapUnitPolys and 
    DescriptionOfMapUnits instead of setting workspace and calling the objects 
    by name only"""
    addMsgAndPrint('  Translating GeologicMap\MapUnitPolys...')
    
    try:
        arcpy.MakeTableView_management(tbDMU, 'DMU')
        #copy StandardLithology information to table
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
        
        #join DMU and DataSources
        arcpy.MakeFeatureLayer_management(fcMUP, 'MUP')
        arcpy.AddJoin_management('MUP', 'MapUnit', 'DMU', 'MapUnit')
        arcpy.AddJoin_management('MUP', 'DataSourceID', dsPath, 'DataSources_ID')
        dumpTable('MUP', 'MapUnitPolys.shp', True, outputDir, logfile, False, 'MapUnitPolys')

        testAndDelete('DMU')
        testAndDelete('MUP')
  
    except:
        addMsgAndPrint(arcpy.GetMessages())
        addMsgAndPrint('  Failed to translate MapUnitPolys')
    
def fc2shp(fcName, fcPath, glosPath, dsPath, outputDir, logfile):
    """Joins feature class with the Glossary and DataSources tables and
    calculates values to new fields. The joins are removed before the layer
    is sent off to dumpTable"""
    fcInFD = os.path.join('GeologicMap', fcName)
    addMsgAndPrint('  Translating {}...'.format(fcInFD))
     
    if debug:
        print 1
        printFieldNames(fcPath)
    
    fcShp = fcName + '.shp'
    LIN = 'xx' + fcName
    LIN2 = fcName + '2'
    removeJoins(fcPath)
    
    addMsgAndPrint('    Making layer {} from {}'.format(LIN, fcInFD))
    arcpy.MakeFeatureLayer_management(fcPath, LIN)
    fieldNames = fieldNameList(LIN)
    if 'Type' in fieldNames:
        arcpy.AddField_management(LIN, 'Definition', 'TEXT', '#', '#', '254')
        arcpy.AddJoin_management(LIN, 'Type', glosPath, 'Term')
        arcpy.CalculateField_management(LIN, 'Definition', '!Glossary.Definition![0:254]', 'PYTHON')
        arcpy.RemoveJoin_management(LIN, 'Glossary')
    # command below are 9.3+ specific
    sourceFields = arcpy.ListFields(fcPath, '*SourceID')
    for sField in sourceFields:
        nFieldName = sField.name[:-2]
        arcpy.AddField_management(LIN, nFieldName, 'TEXT', '#', '#', '254')
        arcpy.AddJoin_management(LIN, sField.name, dsPath, 'DataSources_ID')
        arcpy.CalculateField_management(LIN, nFieldName, '!DataSources.Source![0:254]', 'PYTHON')
        arcpy.RemoveJoin_management(LIN, 'DataSources')
        arcpy.DeleteField_management(LIN, sField.name)
    arcpy.MakeFeatureLayer_management(LIN, "feature_layer")
    dumpTable("feature_layer", fcShp, True, outputDir, logfile, False, fcName)
    arcpy.Delete_management(LIN)
    
def main(gdbCopy,outWS,gdbSrc):
    """Collects dictionaries of objects in the gdb and their paths to avoid
    problems with env.workspace. Iterating through the
    dictionaries, the objects are sent off to be exported"""
    #make a dictionary of table names and their catalog paths in gdbCopy
    tables = dataPathDict(gdbCopy, 'Table', None)
    
    #make a dictionaty of feature classes and their catalog paths in gdbCopy
    feature_classes = dataPathDict(gdbCopy, 'FeatureClass', ['Point', 'Polyline', 'Polygon'])
    
    #make a list of dictionary feature datasets and their catalog paths in gdbCopy
    feature_datasets = dataPathDict(gdbCopy, 'FeatureDataset', None)  
    #
    # Simple version
    #
    isOpen = False
    addMsgAndPrint('')
    outputDir, logfile = makeOutputDir(gdbSrc,outWS,isOpen)
    
    #first dump MapUnitPolys beacause it requires special joins
    if 'StandardLithology' in tables:
        stdLithDict = makeStdLithDict(tables['StandardLithology'])
    else:
        stdLithDict = 'None'
    mup2shp(feature_classes['MapUnitPolys'], tables['DescriptionOfMapUnits'],
            stdLithDict, tables['DataSources'], outputDir, logfile)
    
    #now dump everything else
    #translate to shapefiles any feature classes not named MapUnitPolys
    for fc in feature_classes:
        if fc <> 'MapUnitPolys':
            fc2shp(fc, feature_classes[fc], tables['Glossary'], 
                   tables['DataSources'], outputDir, logfile)
    logfile.close()
    #
    # Open version
    #
    isOpen = True
    addMsgAndPrint('')
    outputDir, logfile = makeOutputDir(gdbSrc,outWS,isOpen)

    for fd in feature_datasets:
        fdPath = feature_datasets[fd]
        addMsgAndPrint( '  Processing feature data set {}...'.format(fdPath))
        logfile.write('Feature data set {} \n'.format(fd))
        try:
            spatialRef = arcpy.Describe(fdPath).SpatialReference
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
        
        if feature_classes <> None:
            for fc in feature_classes:
                #if the feature class is in the current feature dataset:
                if fdPath in feature_classes[fc]:
                    #don't need to check for annotation feature classes
                    #because these are excluded during the creation of the 
                    #feature_classes dictionary
                    outName = pfx+'_'+fc+'.shp'
                    arcpy.MakeFeatureLayer_management(feature_classes[fc], "feature_layer")
                    dumpTable("feature_layer", outName, True, outputDir, logfile, isOpen, fc)
                    testAndDelete("feature_layer")

        else:
            addMsgAndPrint('   No feature classes in this dataset!')
        logfile.write('\n')
        
    #process the tables
    for table in tables:
        #GeMS doc says open version will consist of shapefiles and dbf files
        #with tables with long names converted to txt.
        #why don't we just export all tables to text?
        outName = table+'.dbf'
        arcpy.MakeTableView_management(tables[table], "table_view")
        dumpTable("table_view", outName, False, outputDir, logfile, isOpen, table)
        testAndDelete("table_view")
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
    
    # fix the new workspace name so it is guaranteed to be novel, no overwrite
    gdbCopy = os.path.join(ows, 'xx' + os.path.basename(gdbSrc))
    testAndDelete(gdbCopy)
    addMsgAndPrint('  Copying {} to temporary geodatabase...'.format(os.path.basename(gdbSrc))) 
    arcpy.Copy_management(gdbSrc,gdbCopy)
    
    #if relationships exist in the source gdb, remove them in the copy
    #Cannot make changes to fields (delete or rename) if they are involved in a relationship
    #addMsgAndPrint('  Looking for and removing relationships from {}'.format(gdbCopy))
    remove_rc(gdbCopy) 
    
    #gdbCopy is deletable after removing relationship classes..
    
    main(gdbCopy,ows,gdbSrc)
    addMsgAndPrint('\n  Deleting temporary geodatabase...')
    arcpy.env.workspace = ows
    time.sleep(5)
    try:
        #shutil.rmtree(gdbCopy)
        testAndDelete(gdbCopy)
    except:
        addMsgAndPrint('    As usual, failed to delete temporary geodatabase')
        addMsgAndPrint('    Please delete {}\n'.format(gdbCopy))
        
        
