"""
  GeMS_TranslateToShape_Arc10.5.py

 Converts a GeMS-style ArcGIS geodatabase to
   simple shapefile format - 
     basic map information in flat shapefiles, with much repetition of attribute 
     information, long fields truncated, and much information lost. Field 
     renaming is documented in output file logfile.txt
   open/complete file format - 
     to avoid the limitations of dbf files, feature classes attributes are exported
     as csv files while feature geometries are exported as shapefiles where the
     attribute table contains only the FID, SHAPE, and '_ID' fields. Within 
     a GIS, the shapefiles can be joined to the csv files via the '_ID' field 
     to reconstruct the complete geodatabase with no loss of information. 
     Check the logfile for possible renaming of the key '_ID' field.
 Ralph Haugerud, USGS, Seattle
   rhaugerud@usgs.gov
 Evan Thoms, USGS, Anchorage
   ethoms@usgs.gov
"""

# stdlib
import sys
import os
import glob
import time
import shutil

# 3rd party
import arcpy

# custom class
import GeMS_utilityFunctions as gems

versionString = 'GeMS_TranslateToShape_Arc10.5.py, version of 29 January 2018'

debug = False

def usage():
	gems.addMsgAndPrint( """
USAGE: GeMS_TranslateToShp_Arc10.5.py  <geodatabase> <outputWorkspace>

  where <geodatabase> must be an existing ArcGIS geodatabase.
  <geodatabase> may be a personal or file geodatabase, and the 
  .gdb or .mdb extension must be included.
  Output is written to directories <geodatabase (no extension)>-simple
  and <geodatabase (no extension)>-open in <outputWorkspace>. Output 
  directories, if they already exist, will be overwritten.
""")

# equivalentFraction is used to rank ProportionTerms from most 
# abundant to least
equivalentFraction = {
    'all': 1.0,
    'only part': 1.0,
    'dominant': 0.6,
    'major': 0.5,
    'significant': 0.4,
    'subordinate': 0.3,
    'minor': 0.25,
    'trace': 0.05,
    'rare': 0.02,
    'variable': 0.01,
    'present': 0.0
}

def dummyVal(p_term,p_val):
    if p_val == None:
        if p_term in equivalentFraction:
            return equivalentFraction[p_term]
        else:
            return 0.0
    else:
        return p_val

shortFieldNameDict = {
    'IdentityConfidence': 'IdeConf',
    'MapUnitPolys_ID': 'MUPs_ID',
    'Description': 'Descr',
    'HierarchyKey': 'HKey',
    'ParagraphStyle': 'ParaSty',
    'AreaFillRGB': 'RGB',
    'AreaFillPatternDescription': 'PatDes',
    'GeoMaterial': 'GeoMat',
    'GeoMaterialConfidence': 'GeoMatConf',
    'IsConcealed': 'IsCon',
    'LocationConfidenceMeters': 'LocConfM',
    'ExistenceConfidence': 'ExiConf',
    'ContactsAndFaults_ID': 'CAFs_ID',
    'PlotAtScale': 'PlotAtSca'
}

hide_fields = [
   'MapUnitPolys.DataSourceID',
   'DescriptionOfMapUnits.OBJECTID',
   'DescriptionOfMapUnits.MapUnit',
   'DescriptionOfMapUnits.Label',
   'DescriptionOfMapUnits.Symbol',
   'DescriptionOfMapUnits.DescriptionOfMapUnits_ID',               
   'DataSources.OBJECTID',
   'DataSources.DataSourcesID',
   'DataSources.Notes'
]        

def fds_and_name(path):
    """
    Finds the string in the path that follows '.gdb' which include the feature
    dataset if there is one, otherwise, it will be equivalent to basename
    """
    i = path.find('.gdb')
    return path[i + 5:]    

def fds_prefix(fd):
    pfx = ''
    for i in range(0,len(fd)-1):
        if fd[i] == fd[i].upper():
            pfx = pfx + fd[i] 
    
    return pfx

def remove_rc(gdb):
    """
    Check for and remove all relationship classes from the copy of the 
    geodatabase. You can't delete or change the names of fields that are 
    involved in relationship classes, even in in-memory feature layers 
    and table views
    """
    
    origWS = arcpy.env.workspace
    relclass_list = arcpy.da.Walk(gdb, datatype = "RelationshipClass",
                    followlinks = True)
    for wkspc, path, relclasses in relclass_list:
        arcpy.env.workspace = wkspc
        for relclass in relclasses:
            arcpy.Delete_management(relclass)  
    arcpy.env.workspace = origWS 

def remove_joins(fc):
    """
    Check for and remove joins from layers. It's never called because I don't
    think it will ever be necessary, but let's leave it in in case we encounter 
    a situation where it is.
    """
    
    gems.addMsgAndPrint('      Testing {} for joined tables'.format(fc))
    joinedTables = []
    # list fields
    fields = arcpy.ListFields(fc)
    for field in fields:
        # look for fieldName that indicates joined table, and remove join
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
        gems.addMsgAndPrint('      removed joined tables {}'.format(jts))

def data_path_dict(gdb, d_type, f_type):
    """
    Dictionary of objects in a gdb with their names as keys and their paths
    as values using da.Walk
    """

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

def make_output_dir(gdb, out_ws, suffix):
    output_dir = os.path.join(out_ws, os.path.basename(gdb)[0:-4]) + suffix

    gems.addMsgAndPrint('  Making output directory {}'.format(output_dir))
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir) 

    os.mkdir(output_dir)
    logPath = os.path.join(output_dir, 'logfile.txt')
    logfile = open(logPath, 'w')
    logfile.write('file written by ' + versionString + '\n\n')
    
    return output_dir, logfile
    
def make_std_lith_dict(sl_path):
    """
    Makes a dictionary of StandardLithology terms and their defintions
    """
    
    gems.addMsgAndPrint('  Making StdLith dictionary...')
    std_lith_dict = {}
    rows = arcpy.da.SearchCursor(sl_path,
      ['MapUnit', 'ProportionTerm', 'ProportionValue', 'PartType', 'Lithology'])
    row = rows.next()
    unit = row[0]
    unitDesc = []
    p_term = row[1]; p_val = row[2]
    val = dummyVal(p_term, p_val)
    unitDesc.append([val, row[3], row[4], p_term, p_val])
    while row:
        #print row.getValue('MapUnit')+'  '+row.getValue('Lithology')
        newUnit = row[0]
        if newUnit <> unit:
            std_lith_dict[unit] = description(unitDesc)
            unitDesc = []
            unit = newUnit
        p_term = row[1]; p_val = row[2]
        val = dummyVal(p_term, p_val)
        unitDesc.append([val, row[3], row[4], p_term, p_val])
        row = rows.next()
    del row, rows
    std_lith_dict[unit] = description(unitDesc)
    
    return std_lith_dict 

def mup_joins(fc_mup, tb_dmu, std_lith_dict, ds_path):
    """
    Copies StandardLithololgy information, if available, to MapUnitPolys, 
    joins MapUnitPolys to the DescriptionOfMapUnits and DataSources tables.
    Returns a feature layer with the joins
    """
    
    # reporting
    gems.addMsgAndPrint('    Preparing GeologicMap\MapUnitPolys...')
    
    try:
        arcpy.MakeTableView_management(tb_dmu, 'DMU')
        #copy StandardLithology information to table
        if std_lith_dict <> 'None':
            gems.addMsgAndPrint('      Adding StandardLithology information')
            arcpy.AddField_management('DMU',"StdLith","TEXT",'','','255')
            rows = arcpy.UpdateCursor('DMU'  )
            row = rows.next()
            while row:
                if row.MapUnit in std_lith_dict:
                    row.StdLith = std_lith_dict[row.MapUnit]
                    rows.updateRow(row)
                row = rows.next()
            del row, rows
        
        #join DMU and DataSources
        arcpy.MakeFeatureLayer_management(fc_mup, 'MUP')
        gems.addMsgAndPrint('      Joining DescriptionOfMapUnits and DataSources...')
        arcpy.AddJoin_management('MUP', 'MapUnit', 'DMU', 'MapUnit')
        arcpy.AddJoin_management('MUP', 'DataSourceID', ds_path, 'DataSources_ID')

        # cleanup
        gems.testAndDelete('DMU')
        
        return 'MUP'
  
    except:
        gems.addMsgAndPrint(arcpy.GetMessages())
        gems.addMsgAndPrint('  COULD NOT CREATE JOINS FOR GeologicMap\MapUnitPolys!')
        
def fc_joins(fcName, fcPath, glosPath, ds_path):
    """
    Joins feature class with the Glossary and DataSources tables and
    calculates values to new fields. Returns a feature layer with the joins
    """
    
    # reporting
    fc_in_fds = fds_and_name(fcPath)
    gems.addMsgAndPrint('    Joining {} to Glossary and DataSources...'
      .format(fc_in_fds))
     
    if debug:
        print 1
        print_field_names(fcPath)
    
    try:
        fcShp = fcName + '.shp'
        LIN = 'xx' + fcName
        #remove_joins(fcPath)
        
        arcpy.MakeFeatureLayer_management(fcPath, LIN)
        fieldNames = gems.fieldNameList(LIN)
        if 'Type' in fieldNames:
            arcpy.AddField_management(LIN, 'Definition', 'TEXT', '#', '#', '254')
            arcpy.AddJoin_management(LIN, 'Type', glosPath, 'Term')
            arcpy.CalculateField_management(LIN, 'Definition', 
              '!Glossary.Definition![0:254]', 'PYTHON')
            arcpy.RemoveJoin_management(LIN, 'Glossary')
        # command below are 9.3+ specific
        sourceFields = arcpy.ListFields(fcPath, '*SourceID')
        for sField in sourceFields:
            nFieldName = sField.name[:-2]
            arcpy.AddField_management(LIN, nFieldName, 'TEXT', '#', '#', '254')
            arcpy.AddJoin_management(LIN, sField.name, ds_path, 'DataSources_ID')
            arcpy.CalculateField_management(LIN, nFieldName, 
              '!DataSources.Source![0:254]', 'PYTHON')
            arcpy.RemoveJoin_management(LIN, 'DataSources')
            arcpy.DeleteField_management(LIN, sField.name)
        arcpy.MakeFeatureLayer_management(LIN, 'feature_layer')
        
        # cleanup
        gems.testAndDelete(LIN)
        arcpy.DeleteField_management(fcPath, ['Definition', nFieldName])
        
        return 'feature_layer'
        
    except:
        gems.addMsgAndPrint(arcpy.GetMessages())
        gems.addMsgAndPrint('  COULD NOT CREATE JOINS FOR {}'.format(fc_in_fds))
      
def simple_fc(lyr, src_path, output_dir, logfile):
    """
    Takes in-memory feature layers, shortens field names if necessary and
    writes features to shapefiles
    """

    # get the string in the path after '.gdb', which will include the feature
    # dataset if there is one
    fc_in_fds = fds_and_name(src_path)
    
    src_name = os.path.basename(src_path)
    out_name = src_name + '.shp'
    out_path = os.path.join(output_dir, out_name)
    dumpString = '  Dumping {}...'.format(out_name)
    
    # reporting 
    gems.addMsgAndPrint('      Converting {} with joins to {}'.
      format(fc_in_fds, out_name))
    logfile.write('  preparing feature class {} for dumping to shapefile {}\n'.
      format(src_name, out_name))
    logfile.write('    field name remapping: \n')

    if debug:
        print_field_names(lyr)
        print
   
    # build a field info object for resetting field names and visibility property
    desc = arcpy.Describe(lyr)
    field_info = desc.fieldInfo
    
    # go through the fields one at a time, setting visibility, shorten name,
    shortFieldName = {}
    fields = arcpy.ListFields(lyr)
    for field in fields:
        # translate field names
        # first, parse the qualified name in case there is a join
        parsed_name = arcpy.ParseFieldName(field.name)
        field_name = parsed_name.split(", ")[3]
        index = field_info.findFieldByName (field.name)
        
        # hide fields we don't want exported at all
        # hide_fields is a list defined at the top
        # this only applies to the layer based on MapUnitPolys
        if field.name in hide_fields:
            field_info.setVisible(index, "HIDDEN")
        else:
            # deal with long field names. If they are long, shorten them
            if len(field_name) > 10:
                short_name = remap_field_name(field_name)
                # write field name translation to logfile
                logfile.write('      '+field_name+' > '+short_name+'\n')
            # otherwise, they are ok.
            else:
                short_name = field_name
            field_info.setNewName(index, short_name)
            field_info.setVisible(index, 'VISIBLE')
   
    if debug:
        print field_name, short_name
    
    # export to shapefile
    if debug:  print 'dumping ',objPath,output_dir,out_name
    try:
        arcpy.MakeFeatureLayer_management(lyr, 'lyr2', '', '', field_info)
        arcpy.CopyFeatures_management('lyr2', out_path)
    except:
        gems.addMsgAndPrint('FAILED TO TRANSLATE FEATURE CLASS {}'.format(src_name))
    
    gems.testAndDelete(lyr)
    gems.testAndDelete('lyr2')

def open_fc_fieldinfo(fc_path, pfx, logfile):
    """
    Prepares a fieldinfo object for the complete version of the feature class
    to be exported where all fields are set to hidden unless it is the 
    '_ID' field. The SHAPE field will be exported regardless of this setting 
    so we don't care about it's visible property.
    """

    id_flag = False
    related_csv = pfx + "_" + os.path.basename(fc_path) + '.csv'
    arcpy.MakeFeatureLayer_management(fc_path, 'lyr')
    desc = arcpy.Describe('lyr')
    field_info = desc.fieldInfo
    for index in range(0, field_info.count):
        field_name = field_info.getFieldName(index)
        if field_name.find('_ID') == -1:
            field_info.setvisible(index, 'HIDDEN')
        else:
            id_flag = True
            field_info.setNewName(index, remap_field_name(field_name))
            logfile.write('  The primary field in this shapefile is {}\n'.
              format(remap_field_name(field_name)))
            logfile.write('  Join this field to {} in {}\n'.
              format(field_name, related_csv))
    
    if not id_flag:
        logfile("  {} does not have a '_ID' primary field!".format(fc_path))
        
    gems.testAndDelete('lyr')
    return field_info
    
def remap_field_name(name):
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
            gems.addMsgAndPrint('      '+ name + '  ' + newName)
        return newName	

def print_field_names(fc):
    for f in gems.fieldNameList(fc):
        print f
    print

def write_csv_file(obj_path, output_dir, out_name, logfile):
    """Writes a csv in the same way that ArcMap does from the Table 
    view > Export process. There is no standard arcpy tool that does this (I think)
    1) field values are separated by commas
    2) numbers are not enclosed within double quotes
    3) strings are only enclosed within double quotes if they contain commas
    """ 
    
    # get the name of the object including, if appropriate, the feature 
    # dataset it's in
    obj_in_fds = fds_and_name(obj_path)
    
    out_file = out_name + '.csv'
    text_path = os.path.join(output_dir, out_file)
    text_file = open(text_path, 'w')
    #remove_joins(obj_path)
    error_flag = 0
    
    # reporting
    logfile.write('    Writing attributes of {} to {}\n'.format(obj_in_fds, out_file))
        
    # remove blob or geometry fields before writing to text and construct a list
    # of field names
    # start with a list of acceptable field types, excluding Geometry and Blob
    type_list = ['Date', 'Double', 'GlobalID', 'GUID', 'Integer', 'OID', 'Single',
                 'SmallInteger', 'String']
    fields = arcpy.ListFields(obj_path, type_list)
    field_names = [f.name for f in fields if f.type in type_list]
    
    # write the first row
    text_file.write(",".join(field_names) + "\n")    
    
    oid_index = field_names.index('OBJECTID')
    cursor = arcpy.da.SearchCursor(obj_path, field_names)
    for row in cursor:
        val_list = []
        for i in range(0, len(field_names)):
            try:
                row_value = row[i]
                #gems.addMsgAndPrint('{}: {}'.format(field_names[i], row_value))
                if isinstance(row_value, basestring):
                    if row_value.find(",") > -1:
                        row_value = row[i].replace('"', '""')
                        val_list.append('"{}"'.format(row_value.encode
                          ('ascii','xmlcharrefreplace')))
                    else:
                        val_list.append('{}'.format(row_value.encode
                          ('ascii','xmlcharrefreplace')))
                elif row_value is None:
                    val_list.append("")
                else:
                    val_list.append(str(row[i]))
            except:
                field_name = field_names[i]
                logfile.write('  Could not parse {} for OBJECTID = {}'
                  .format(field_name, row[oid_index]))
                val_list.append("")
                error_flag = 1
        text_file.write(",".join(val_list) + "\n")
    text_file.close()
    
    # reporting
    if error_flag == 0:
        logfile.write('  No errors to report.\n')
    
def main(gdbCopy,out_ws,gdbSrc):
    """Collects dictionaries of objects in the gdb and their paths to avoid
    problems with env.workspace. Iterating through the
    dictionaries, the objects are sent off to be exported"""
    # make a dictionary of table names and their catalog paths in gdbCopy
    tables = data_path_dict(gdbCopy, 'Table', None)
    
    # make a dictionaty of feature classes and their catalog paths in gdbCopy
    feature_classes = data_path_dict(gdbCopy, 'FeatureClass', 
      ['Point', 'Polyline', 'Polygon'])
    
    # make a list of dictionary feature datasets and their catalog paths in gdbCopy
    feature_datasets = data_path_dict(gdbCopy, 'FeatureDataset', None)  
 
    # SIMPLE VERSION
    gems.addMsgAndPrint(' ')
    gems.addMsgAndPrint('Making simple version of shapefiles with joined tables')
    output_dir, logfile = make_output_dir(gdbSrc, out_ws, '-simple')
    
    # first deal with MapUnitPolys beacause it requires special joins
    if 'StandardLithology' in tables:
        std_lith_dict = make_std_lith_dict(tables['StandardLithology'])
    else:
        std_lith_dict = 'None'
    # get a feature layer
    mup_lyr = mup_joins(feature_classes['MapUnitPolys'], tables['DescriptionOfMapUnits'],
            std_lith_dict, tables['DataSources'])
    
    # send the feature layer to have names shortened and the exported
    simple_fc(mup_lyr, feature_classes['MapUnitPolys'], output_dir, logfile)
    gems.testAndDelete(mup_lyr)
    
    # now dump everything else
    # translate to shapefiles any feature classes not named MapUnitPolys
    for fc in feature_classes:
        if fc <> 'MapUnitPolys':
            fc_lyr = fc_joins(fc, feature_classes[fc], tables['Glossary'], 
                   tables['DataSources'])
            simple_fc(fc_lyr, feature_classes[fc], output_dir, logfile)
            gems.testAndDelete(fc_lyr)
    logfile.close()
    gems.addMsgAndPrint('  Check {} for field name remapping.'.
      format(logfile.name))

    # OPEN VERSION
    gems.addMsgAndPrint(' ')
    gems.addMsgAndPrint('Making complete version with decoupled shapefiles ' +
      'and csv files')
    output_dir, logfile = make_output_dir(gdbSrc, out_ws, '-open')

    for fd in feature_datasets:
        fdPath = feature_datasets[fd]
        gems.addMsgAndPrint( '  Processing feature dataset {}...'.format(fd))
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
        pfx = fds_prefix(fd)
        
        if feature_classes <> None:
            for fc in feature_classes:
                # if the feature class is in the current feature dataset:
                if fdPath in feature_classes[fc]:
                    out_name = pfx + '_' + fc
                    shp_path = os.path.join(output_dir, out_name + '.shp')
                    fc_in_fds = fds_and_name(feature_classes[fc])
                    
                    logfile.write('\n')
                    # couldn't get line continuation to work with the following
                    # long line
                    logfile.write('  Converting {} to {} with no attributes except a primary key field\n'.format(fc_in_fds, out_name + '.shp'))
                    
                    # get a fieldInfo object that hides all the fields except
                    # for the <fc>_ID field
                    field_info = open_fc_fieldinfo(feature_classes[fc], pfx, logfile)
                    
                    # make a feature layer, apply the fieldInfo, and write the
                    # "decoupled" shapefile
                    arcpy.MakeFeatureLayer_management(feature_classes[fc], 
                      'feature_layer', '', '', field_info)

                    gems.addMsgAndPrint('    Writing features from {} to {}'.
                      format(fc_in_fds, out_name + '.shp'))
                    arcpy.CopyFeatures_management('feature_layer', shp_path)
                    gems.testAndDelete('feature_layer')
                    
                    # write the accompanying csv attribute table 
                    gems.addMsgAndPrint('      Writing attributes from {} to {}'.
                      format(fc_in_fds, out_name + '.csv'))                    
                    write_csv_file(feature_classes[fc], output_dir, out_name, 
                      logfile)

        else:
            gems.addMsgAndPrint('    No feature classes in this dataset!')
    
    logfile.write('\n')
        
    # process the tabless
    gems.addMsgAndPrint('  Converting non-spatial tables...')
    for table in tables:
        # export tables to csv
        gems.addMsgAndPrint('    Writing records from {} to {}'.
          format(table, table + '.csv'))

        logfile.write('Non-spatial tables\n')
        write_csv_file(tables[table], output_dir, table, logfile)
    logfile.close()
 
    gems.addMsgAndPrint('  Check {} for key field names in the converted shapefiles'.
      format(logfile.name))

### START HERE ###
if len(sys.argv) <> 3 or not os.path.exists(sys.argv[1]) \
    or not os.path.exists(sys.argv[2]):
    usage()
else:
    gems.addMsgAndPrint('  {}'.format(versionString))
    gdbSrc = os.path.abspath(sys.argv[1])
    ows = os.path.abspath(sys.argv[2])
    arcpy.env.QualifiedFieldNames = False
    arcpy.env.overwriteoutput = True
    
    # fix the new workspace name so it is guaranteed to be novel, no overwrite
    gdbCopy = os.path.join(ows, 'xx' + os.path.basename(gdbSrc))
    gems.testAndDelete(gdbCopy)
    gems.addMsgAndPrint('  Copying {} to temporary geodatabase {}'.format
      (os.path.basename(gdbSrc), gdbCopy)) 
    arcpy.Copy_management(gdbSrc, gdbCopy)
    
    # if relationships exist in the source gdb, remove them in the copy
    # Cannot make changes to fields (delete or rename) if they are involved in 
    # a relationship
    remove_rc(gdbCopy) 

    main(gdbCopy,ows,gdbSrc)
    
    gems.addMsgAndPrint('Deleting temporary geodatabase...')
    
    #gdbCopy should be deletable after in-memory feature and table layers
    #have been deleted.
    try:
        gems.testAndDelete(gdbCopy)
    except:
        gems.addMsgAndPrint('  Could not delete temporary geodatabase')
        gems.addMsgAndPrint('  Please manually delete {}\n'.format(gdbCopy))
        
        
