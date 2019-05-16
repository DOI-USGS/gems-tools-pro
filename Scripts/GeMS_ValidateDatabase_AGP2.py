# GeMS_ValidateDatabase_AGP2.py 
#   Python script to inventory tables, feature datasets
#   and feature classes in a geodatabase and to check
#   for conformance with NCGMP09 geodatabase schema.
#   For more information, see tail of this file. 
#   Assumes ArcGIS 10 or higher.
#   Ralph Haugerud, USGS
#
#   Takes two arguments: <geodatabaseName> <outputWorkspace>
#     and writes a file named <geodatabaseName>-NCGMP09conformance.txt.
#   At present only works on a geodatabase in the local directory.
#   Requires that ncgmp09_definition.py be present in the local directory 
#     or in the appropriate Python library directory.
#   Incomplete error trapping and no input checking. 
#
# NOTE: THIS CODE HAS NOT BEEN THOROUGHLY TESTED
#   If you find problems, or think you see errors, please let me know.
#   Zip up the database, the conformance report (if one is written), 
#   a brief discussion of what's wrong, and email zip file to me at
#       rhaugerud@usgs.gov
#   Please include "GeMS" in the subject line.
#   Thanks!

print('  importing arcpy...')
import arcpy, sys, time, os.path, glob
from GeMS_Definition import tableDict, fieldNullsOKDict
from GeMS_utilityFunctions import *


versionString = 'GeMS_ValidateDatabase_AGP2.py, version of 16 May 2019'
# modified to have output folder default to folder hosting input database
# modified for HTML output
# 15 Sept 2016  tableToHtml modified to better handle special characters
# 15 Sept 2016  removed check for nullable vs non-nullable field definitions
# 15 Sept 2016  removed DataSourcePolys from required feature classes
# 16 Sept 2016  Inventoried disallowed null values. Check for zero-length strings
# 19 Oct 2016   Changed search for 'Source' fields to look for "SourceID" instead of "Source" in field name
# 19 Dec 2016   Added check for null fields within DMU
# 19 Dec 2016   Deleted requirement that GenLith and GenLithConf be defined in Glossary
# 17 Mar 2017   Added MiscellaneousMapInformation and StandardLithology to tables listed to output HTML
# 13 August 2017  Cleaned up required table and feature class definition; added GeoMaterialDict to required elements
# 6 December 2017   Did a re-vamp on html, added style, tables, etc. - Tanner Arrington
# 4 March 2018  Added check for .txt files in gdb
# May 16 2019 GeMS_ValidateDatabase_Arc10.py for Python 2.7 ported to Python 3 - Evan Thoms       

## need to check for and flag zero-length strings: should be '#', '#null' or None

debug = False
space6 = '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp'
space4 = '&nbsp;&nbsp;&nbsp;&nbsp;'
space2 = '&nbsp;&nbsp;'

rdiv = '<div class="report">\n'
divend = '</div>\n'    

style = """ 
    <style>
        .report {
            font-family: Courier New, Courier, monospace;
            margin-left: 20px;
            margin-right: 20px;
        }
        h3, .tablediv h4 {
            margin-left:15px;
        }
        h2,
        h3 {
            background-color: lightgray;
            padding: 5px;
            border-radius: 4px;
            font-family: "Century Gothic", CenturyGothic, AppleGothic, sans-serif;
        }
        .ess-tables {
            width: 95%;
            margin-left: 15px;
        }
        .table-header:hover {
            cursor:pointer;
        }
        table,
        th,
        td {
            border: 1px solid gray;
            border-collapse: collapse;
            padding: 10px;
        }
        .fields {
            color: darkblue;
            font-weight:bold;
        }
        .tables {
            color:darkorange;
            font-weight:bold;
        }
        .values {
            color:darkgreen;
            font-weight:bold;
        }
        .highlight{
            background-color:#f2fcd6;
            padding:0 2px;
            border-radius:3px;
            border-bottom:1px solid gray;
        }
        li {
            list-style: none;
            margin-top: 5px;
            margin-bottom: 5px;
        }
        #back-to-top {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 10px;
            margin: 10px;
            background-color: rgba(250,250,250,0.7);
            border-radius:5px;
        }
    </style>"""

overviewhtml = """
    <h2>Contents</h2>\n
    <div class="report" id="contents">
        <a href="#schema-errors">Schema Errors</a><br>
        <a href="#extensions">Extensions to Schema</a><br>
        <a href="#content-errors">Content Errors</a><br>
        <a href="#match">MapUnits Match across map, DMU, CMU, and cross-sections</a><br>
        <a href="#essential">Essential Tables</a><br>
        <a href="#gdb-desc">Geodatabase Description</a><br>
    </div>
    <div class="report">
        <h4>Color Codes</h4>
        <span class="tables">Orange</span> are tables, feature classes, or feature datasets in the geodatabase.<br>
        <span class="fields">Blue</span> are fields in a table.</br>
        <span class="values">Green</span> are values in a field.</br>
    </div>
    <div id="back-to-top"><a href="#overview">Back to Top</a></div>
    """

# fields we don't want listed or described when inventorying dataset:
standardFields = ('OBJECTID','SHAPE','Shape','SHAPE_Length','SHAPE_Area','ZOrder',
                  'AnnotationClassID','Status','TextString','FontName','FontSize','Bold',
                  'Italic','Underline','VerticalAlignment','HorizontalAlignment',
                  'XOffset','YOffset','Angle','FontLeading','WordSpacing','CharacterWidth',
                  'CharacterSpacing','FlipAngle','Override','Shape_Length','Shape_Area',
                  'last_edited_date','last_edited_user','created_date','created_user') 

# fields whose values must be defined in Glossary
gFieldDefList = ('Type','TypeModifier','LocationMethod','Lithology','ProportionTerm','TimeScale',
                 'Qualifier','ExistenceConfidence','IdentityConfidence','Property',
                 'ScientificConfidence','ParagraphStyle','AgeUnits')

requiredTables = ['DataSources','DescriptionOfMapUnits','Glossary','GeoMaterialDict']
requiredFeatureDataSets = ['GeologicMap']
requiredMapFeatureClasses = ['ContactsAndFaults','MapUnitPolys']

tables = []
fdsfc = []
all_IDs = []        # list of should-be unique identifiers
allMapUnitRefs = []    # list of MapUnit references (from various Poly feature data sets)
allGlossaryRefs = []    # list of all references to Glossary
allDataSourcesRefs = [] # list of all references to DataSources
missingRequiredValues = ['<span class="highlight">Fields that are missing required values</span>']

gdbDescription = []
schemaErrors = []
schemaExtensions = []

duplicateIDs = ['<span class="highlight">Duplicate _ID values</span>']
unreferencedIds = ['<span class="highlight">OwnerIDs and ValueLinkIDs in ExtendedAttributes that are absent elsewhere in the database</span>']
extendedAttribIDs = []
missingSourceIDs = ['<span class="highlight">Missing DataSources entries. Only one reference to each missing source is cited</span>']
unusedDataSources = ['<span class="highlight">Entries in DataSources that are not otherwise referenced in database</span>']
dataSourcesIDs = []
missingDmuMapUnits = ['<span class="highlight">MapUnits missing from DMU. Only one reference to each missing unit is cited</span>']
missingStandardLithMapUnits = ['<span class="highlight">MapUnits missing from StandardLithology. Only one reference to each missing unit is cited</span>']
unreferencedDmuMapUnits = ['<span class="highlight">MapUnits in DMU that are not present on map or in CMU</span>']
unreferencedStandardLithMapUnits = ['<span class="highlight">MapUnits in StandardLithology that are not present on map</span>']
equivalenceErrors = ['<table style="text-align:center"><tr><th>MapUnit</th><th>map</th><th>DMU</th><th>CMU</th><th>cross sections</th></tr>']
dmuMapUnits = []
cmuMapUnits = []
gmapMapUnits = []
csMapUnits = []
standardLithMapUnits = []
missingGlossaryTerms = ['<span class="highlight">Missing terms in Glossary. Only one reference to each missing term is cited</span>']
unusedGlossaryTerms = ['<span class="highlight">Terms in Glossary that are not otherwise used in geodatabase</span>']
glossaryTerms = []
unusedGeologicEvents = ['<span class="highlight">Events in GeologicEvents that are not cited in ExtendedAttributes</span>']
hKeyErrors = ['<span class="highlight">HierarchyKey errors, DescriptionOfMapUnits</span>']
zeroLengthStrings = ['<span class="highlight">Zero-length strings</span>']

def listDataSet(dataSet):
    addMsgAndPrint('    '+dataSet)
    startTime = time.time()
    try:
        nrows = arcpy.GetCount_management(dataSet)
        elapsedTime = time.time() - startTime
        if debug: addMsgAndPrint('      '+str(nrows)+' rows '+ "%.1f" % elapsedTime +' sec')
        gdbDescription.append('<h4><span class="tables">'+dataSet+'</span>, '+str(nrows)+' records</h4>\n<ul>\n')
    except:
        addMsgAndPrint('Could not get number of rows for '+dataSet)
        gdbDescription.append('<h4><span class="tables">'+dataSet+'</span>, unknown # of records</h4>')
    startTime = time.time()
    try:
        fields = arcpy.ListFields(dataSet)
        if debug: addMsgAndPrint('      '+str(len(fields))+' fields '+ "%.1f" % elapsedTime +' sec')
        for field in fields:
            if not (field.name in standardFields):
                gdbDescription.append('<li><span class="fields">'+field.name+'</span> - '+field.type+':'+str(field.length)+' - Required: '+str(field.required) + '</li>\n')
        gdbDescription.append('</ul>')
    except:
        addMsgAndPrint('Could not inventory fields in '+dataSet)
        gdbDescription.append(space6+'no field inventory for '+dataSet)
        elapsedTime = time.time() - startTime
            

def checkMapFeatureClasses(fds,prefix,fcs):
    addMsgAndPrint('  Checking for required feature classes...')
    reqFeatureClasses = []
    for fc in requiredMapFeatureClasses:
        reqFeatureClasses.append(prefix+fc)
    for fc in reqFeatureClasses:
        if not (fc in fcs): 
            schemaErrors.append('Feature data set <span class="tables">'+fds+'</span>, feature class <span class="tables">'+fc+'</span> is missing')

def checkTableFields(dBTable,defTable):
  dBtable = str(dBTable)
  # build dictionary of required fields 
  requiredFields = {}
  requiredFieldDefs = tableDict[defTable]
  for fieldDef in requiredFieldDefs:
    requiredFields[fieldDef[0]] = fieldDef
  # build dictionary of existing fields
  try:
    existingFields = {}
    fields = arcpy.ListFields(dBtable)
    for field in fields:
      existingFields[field.name] = field
    # now check to see what is excess / missing
    for field in list(requiredFields.keys()):
      if field not in existingFields:
        schemaErrors.append('<span class="tables">'+dBTable+'</span>, field <span class="fields">'+field+'</span> is missing')
    for field in list(existingFields.keys()):
      if not (field in standardFields) and not (field in requiredFields):
        schemaExtensions.append('<span class="tables">'+dBTable+'</span>, field <span class="fields">'+field+'</span>')
      # check field definition
      if field in list(requiredFields.keys()):
        # field type
        if existingFields[field].type != requiredFields[field][1]:
          schemaErrors.append('<span class="tables">'+dBTable+'</span>, field <span class="fields">'+field+'</span>, type should be '+requiredFields[field][1])
        # Using Arc field properties to enforce non-nullability is a bad idea
        ### need to use part of code below to check for illicit null values in nullable fields
        ###    and null or empty values in fields that are non-nullable
        #if existingFields[field].isNullable:
        # # nullStatus = 'NullsOK'
        #else:
        #  nullStatus = 'NoNulls'
        #if nullStatus <> requiredFields[field][2]:
        #  schemaErrors.append(dBTable+', field '+field+' should be '+requiredFields[field][2])
  except:
    schemaErrors.append(dBTable+' could not get field list. Fields not checked.')
    
def loadTableValues(tableName,fieldName,valueList):
    try:
        rows = arcpy.SearchCursor(tableName,'','',fieldName)
    except:
        loadValuesFlag = False
    else: 
        row = next(rows)
        while row:
            if row.getValue(fieldName) != None:
                valueList.append(row.getValue(fieldName))
            row = next(rows) 
        loadValuesFlag = True
    return loadValuesFlag

def isNullValue(val):
    if val == None:
        return True
    elif isinstance(val,(str)):
        if val == '' or val.isspace():  # second clause checks for strings that are all spaces
            return True
        elif val == '#' or val.upper() == '#NULL':
            return True
        else:
            return False
    else:
        return False

    
def inventoryValues(thisDatabase,table):
    # build list of fields in this table that must have values defined in Glossary
    # build list of fields that point at DataSources (name cn 'Source'
    # note if MapUnit field is present
    # calculate value of _ID field
    tableName = os.path.basename(table)
    tableFields = arcpy.ListFields(os.path.join(thisDatabase,table))
    fields = []
    mapUnitExists = False
    if debug: addMsgAndPrint('      Listing fields')
    for field in tableFields:
        fields.append(field.name)
        if field.name == 'MapUnit':
            mapUnitExists = True
    if debug: addMsgAndPrint('      mapUnitExists='+str(mapUnitExists))
    glossFields = []
    sourceFields = []
    idField = table+'_ID'
    hasIdField = False
    if debug: addMsgAndPrint('      Getting glossary and source fields')
    for field in fields:
        if field in gFieldDefList:
            glossFields.append(field)
        if field.find('SourceID') >= 0 and field.find('_ID') < 0 and table != 'DataSources':
            sourceFields.append(field)
        if field == idField:
            hasIdField = True
    # get rows from table of interest
    if debug: addMsgAndPrint('      Getting rows')
    try:
        rows = arcpy.SearchCursor(thisDatabase+'/'+table)
    except:
            addMsgAndPrint('failed to set rows')
    # step through rows and inventory values in specified fields
    row = next(rows)
    while row:
        if hasIdField:
            all_IDs.append([row.getValue(idField),table])
        if table != 'Glossary':
            for field in glossFields:
              try:
                if row.getValue(field) != '' and row.getValue(field) != None:
                                    allGlossaryRefs.append([str(row.getValue(field)),field,table])
              except:
                errString = 'Table '+table+', OBJECTID = '+str(row.getValue('OBJECTID'))
                errString = errString+', field '+field+' caused an error'
                addMsgAndPrint(errString)
                addMsgAndPrint('Field value is <'+str(row.getValue(field))+'>')
                pass
        if mapUnitExists:
            mu = str(row.getValue('MapUnit'))
            if mu != '':
                if table != 'DescriptionOfMapUnits' and table != 'StandardLithology':
                        allMapUnitRefs.append([mu,table])
                if table == 'MapUnitPolys':
                        gmapMapUnits.append(mu)
                if table[0:2] == 'CS' and table[3:] == 'MapUnitPolys':
                        csMapUnits.append(mu)                                       
                if table == 'CMUMapUnitPolys' or table == 'CMUMapUnitPoints':
                        cmuMapUnits.append(mu)
                if table == 'DescriptionOfMapUnits':
                        if mu != 'None':
                                dmuMapUnits.append(mu)
                                        
        for field in sourceFields:
            try:
                allDataSourcesRefs.append([row.getValue(field),field,table])
            except:
                addMsgAndPrint('Failed to append to allDataSourcesRefs:')
                addMsgAndPrint('  table '+table+', field = '+str(field))
        tableRow = space4+'<span class="tables">'+table+'</span>, OBJECTID='+str(row.getValue('OBJECTID'))
        # check for impermissible Null values        
        for field in fields:
            tableField = tableName+' '+field
            if tableField in fieldNullsOKDict:
                if not fieldNullsOKDict[tableField]:
                    if isNullValue(row.getValue(field)):
                        missingRequiredValues.append(tableRow+', <span class="fields">'+field+'</span>')
        # check for zero-length strings
        for field in tableFields:
            if field.type == 'String':
                stringVal = row.getValue(field.name)
                if stringVal != None and ( stringVal == '' or stringVal.isspace() ):
                    zeroLengthStrings.append(tableRow+', <span class="fields">'+field.name+'</span>')
         
        row = next(rows)
    addMsgAndPrint('    Finished '+table)
            
def inventoryWorkspace(tables,fdsfc):
    addMsgAndPrint('  Inventorying geodatabase...')
    featureDataSets = arcpy.ListDatasets()
    gdbDescription.append('<h3>Tables: </h3>')
    for table in tables:
        listDataSet(table)
    for featureDataSet in featureDataSets:
        gdbDescription.append('<h3>Feature data set: '+featureDataSet+'</h3>')
        arcpy.env.workspace = thisDatabase
        arcpy.env.workspace = featureDataSet
        featureClasses = arcpy.ListFeatureClasses()
        featureClassList = []
        if debug:
            addMsgAndPrint(str(featureDataSet)+'-'+str(featureClasses))
        if featureClasses != None:
            for featureClass in featureClasses:
                listDataSet(featureClass)
                featureClassList.append(featureClass)
        fdsfc.append([featureDataSet,featureClassList])

def checkFieldsAndFieldDefinitions():
    addMsgAndPrint( '  Checking fields and field definitions, inventorying special fields...')
    for table in tables:
        if debug: addMsgAndPrint('    Table = '+table)
        arcpy.env.workspace = thisDatabase
        if not ( table in tableDict or table == 'GeoMaterialDict'): 
            schemaExtensions.append('Table <span class="tables">'+table+'</span>')
        else:
          if table != 'GeoMaterialDict':
            checkTableFields(table,table)
        inventoryValues(thisDatabase,table)
    for fds in fdsfc:
        if not fds[0] in ('GeologicMap','CorrelationOfMapUnits') and fds[0:12] != 'CrossSection':
            schemaExtensions.append('Feature dataset <span class="tables">'+fds[0]+'</span>')
        arcpy.env.workspace = thisDatabase
        arcpy.env.workspace = fds[0]
        for featureClass in fds[1]:
            if debug: addMsgAndPrint('    Feature class = '+featureClass)
            if featureClass not in tableDict: 
                schemaExtensions.append('Feature class <span class="tables">'+featureClass+'</span>')
            else: 
              try:
                checkTableFields(featureClass,featureClass)
              except:
                addMsgAndPrint('Failed to check fields in '+featureClass)
            try:
              inventoryValues(thisDatabase,featureClass)
            except:
              addMsgAndPrint('Failed to inventory values in '+featureClass)
    # check for .txt files that maybe should be deleted before the gdb is released
    txtfiles = glob.glob(thisDatabase+'/*.txt')
    for f in txtfiles:
        schemaExtensions.append('File '+os.path.basename(f))

def checkRequiredElements():
    addMsgAndPrint( '  Checking for required elements...')
    for tb1 in requiredTables:
        isPresent = False
        for tb2 in tables:
            if tb1 == tb2:
                isPresent = True
        if not isPresent:
            schemaErrors.append('Table <span class="tables">'+tb1+'</span> is missing')
    for fds1 in requiredFeatureDataSets:
        isPresent = False
        for fds2 in fdsfc:
            if fds2[0] == fds1: 
                isPresent = True
        if not isPresent:
            schemaErrors.append('Feature dataset <span class="tables">'+fds1+'</span> is missing')
    for xx in fdsfc:
        fds = xx[0]
        fcs = xx[1]
        if fds[0:12] == 'CrossSection':
            checkMapFeatureClasses(fds,'CS'+fds[12:],fcs)
        if fds == 'GeologicMap':
            checkMapFeatureClasses(fds,'',fcs)
        if fds == 'CorrelationOfMapUnits':
            if not ('CMULines' in fcs):
                schemaErrors.append('Feature data set <span class="tables">'+fds+'</span>, feature class <span class="tables">CMULines</span> is missing')
            if not ('CMUMapUnitPolys' in fcs):
                schemaErrors.append('Feature data set <span class="tables">'+fds+'</span>, feature class <span class="tables">CMUMapUnitPolys</span> is missing')
            if not ('CMUText' in fcs):
                schemaErrors.append('Feature data set <span class="tables">'+fds+'</span>, feature class <span class="tables">CMUText</span> is missing')

def checkContent():
    addMsgAndPrint( '  Checking content...')
    arcpy.env.workspace = thisDatabase
    # Check for uniqueness of _ID values
    addMsgAndPrint('    Checking uniqueness of ID values')
    all_IDs.sort()
    for n in range(1,len(all_IDs)):
        if all_IDs[n-1][0] == all_IDs[n][0]:
            duplicateIDs.append(space4+'<span class="values">'+str(all_IDs[n][0])+'</span>, tables <span class="tables">'+str(all_IDs[n-1][1])+' '+str(all_IDs[n][1])+'</span>')
    
    # Check for OwnerIDs and ValueLinkIDs in ExtendedAttributes that don't match an existing _ID
    if not loadTableValues('ExtendedAttributes','OwnerID',extendedAttribIDs):
        unreferencedIds.append(space4+'Error: did not find field OwnerID in table ExtendedAttributes')
    if not loadTableValues('ExtendedAttributes','ValueLinkID',extendedAttribIDs):
        unreferencedIds.append(space4+'Error: did not find field ValueLinkID in table ExtendedAttributes')
    #compare
    extendedAttribIDs.sort()
    all_IDs0 = []
    for anID in all_IDs:
        all_IDs0.append(str(anID[0]))
    for anID in extendedAttribIDs:
        if anID != None and not anID in all_IDs0:
            unreferencedIds.append('    '+ anID)
    
    # Check allDataSourcesRefs against DataSources
    addMsgAndPrint('    Comparing DataSources_IDs with DataSources')    
    if loadTableValues('DataSources','DataSources_ID',dataSourcesIDs):
        # compare 
        allDataSourcesRefs.sort()
        lastID = ''
        for anID in allDataSourcesRefs:
            if anID[0] != None and anID[0] != lastID:
                lastID = anID[0]
                if anID[0] not in dataSourcesIDs:
                    missingSourceIDs.append(space4 + '<span class="values">'+ str(anID[0])+'</span>, cited in field <span class="fields">'+str(anID[1])+'</span> of table <span class="tables">'+str(anID[2])+'</span>')
        
        # compare other way
        allSourceRefIDs = []
        for ref in allDataSourcesRefs:
            allSourceRefIDs.append(ref[0])
        for anID in dataSourcesIDs:
            if anID != None and not anID in allSourceRefIDs:
                unusedDataSources.append(space4 + '<span class="values">' + anID + '</span>')
    else:
        missingSourceIDs.append(space4 + 'Error: did not find field <span class="fields">DataSources_ID</span> in table <span class="tables">DataSources</span>')
        unusedDataSources.append(space4 + 'Error: did not find field <span class="fields">DataSources_ID</span> in table <span class="tables">DataSources</span>')
    
    # Check MapUnits against DescriptionOfMapUnits and StandardLithology
    addMsgAndPrint('    Checking MapUnits against DMU and StandardLithology')
    if not loadTableValues('DescriptionOfMapUnits','MapUnit',dmuMapUnits):
        missingDmuMapUnits.append(space4 + 'Error: did not find field <span class="fields">MapUnit</span> in table <span class="tables">DescriptionOfMapUnits</span>')
        unreferencedDmuMapUnits.append(space4 + 'Error: did not find field <span class="fields">MapUnit</span> in table <span class="tables">DescriptionOfMapUnits</span>')
    if not loadTableValues('StandardLithology','MapUnit',standardLithMapUnits):
        missingStandardLithMapUnits.append(space4 + 'Error: did not find field <span class="fields">MapUnit</span> in table <span class="tables">StandardLithology</span>') 
        unreferencedStandardLithMapUnits.append(space4 + 'Error: did not find <span class="fields">field MapUnit</span> in table <span class="tables">StandardLithology</span>')
    
    # compare 
    allMapUnitRefs.sort()
    lastMU = ''
    allMapUnitRefs2 = []
    addMsgAndPrint('    Checking for missing map units in DMU and StandardLithology')
    for mu in allMapUnitRefs:
            if mu[0] != lastMU:
                lastMU = mu[0]
                allMapUnitRefs2.append(lastMU)
                if mu[0] not in dmuMapUnits:
                    missingDmuMapUnits.append(space4 + '<span class="values">' +str(mu[0])+'</span>, cited in <span class="tables">'+str(mu[1])+'</span>')
                if mu[0] not in standardLithMapUnits:
                    missingStandardLithMapUnits.append(space4 + '<span class="values">' + str(mu[0])+'</span>, cited in ' + str(mu[1])+'</span>')
    # compare map, DMU, CMU, and cross-sections
    addMsgAndPrint('    Comparing units present in map, DMU, CMU, and cross sections')
    dmuMapUnits2 = list(set(dmuMapUnits))
    cmuMapUnits2 = list(set(cmuMapUnits))
    gmapMapUnits2 = list(set(gmapMapUnits))
    csMapUnits2 = list(set(csMapUnits))
    if debug: addMsgAndPrint('cmuMapUnits2='+str(cmuMapUnits2))
    allMapUnits = []
    muSets = [gmapMapUnits2,dmuMapUnits2,cmuMapUnits2,csMapUnits2]
    for muSet in muSets:
        for mu in muSet:
            if not mu in allMapUnits:
                allMapUnits.append(mu)
    allMapUnits.sort()
    if debug: addMsgAndPrint('allMapUnits='+str(allMapUnits))
    #                         1234567890123456789012345678901234567890
    #equivalenceErrors.append('    Unit       Map  DMU  CMU  XS')
    for mu in allMapUnits:
        line = '<td>'+mu+'</td>'
        for muSet in muSets:
            if mu in muSet:
                line = line+'<td> X </td>'
            else:
                line = line+'<td> --- </td>'
        equivalenceErrors.append('<tr>'+line+'</tr>')                
        
    # look for excess map units in StandardLithology
    addMsgAndPrint('    Checking for excess map units in StandardLithology')
    lastMu = ''
    standardLithMapUnits.sort()
    for mu in standardLithMapUnits:
        if mu != lastMu and not mu in allMapUnitRefs2:
            lastMu = mu
            unreferencedStandardLithMapUnits.append(space4 + mu)
    # look for unreferenced map units in DMU
    addMsgAndPrint('    Checking for excess map units in DMU')
    for mu in dmuMapUnits:
        if mu not in allMapUnitRefs2 and mu != '':
            unreferencedDmuMapUnits.append(space4 + mu)
    # Check allGlossaryRefs against Glossary
    addMsgAndPrint('    Checking glossary references')
    if loadTableValues('Glossary','Term',glossaryTerms):
        # compare 
        allGlossaryRefs.sort()
        lastTerm = ''
        for term in allGlossaryRefs:
            if str(term[0]) != 'None' and term[0] != lastTerm:
                lastTerm = term[0]
                if term[0] not in glossaryTerms:
                    if len(term[0]) < 40:
                        thisTerm = term[0]
                    else:
                        thisTerm = term[0][0:37]+'...'
                    missingGlossaryTerms.append(space4 + '<span class="values">'+thisTerm+'</span>, cited in field <span class="fields">'+term[1]+'</span> of table <span class="tables"> '+term[2] + '</span>')
        # compare other direction
        glossaryRefs = []
        for ref in allGlossaryRefs:
            glossaryRefs.append(str(ref[0]))
        for term in glossaryTerms:
            if term not in glossaryRefs:
                unusedGlossaryTerms.append(space4 + '<span class="values">'+ term + '</span>')
    else:
        missingGlossaryTerms.append(space4+'Error: did not find field Term in table Glossary')
        unusedGlossaryTerms.append(space4+'Error: did not find field Term in table Glossary')
    # Check GeologicEvents against ValueLinkID in ExtendedAttributes
    geologicEvents = []
    if not loadTableValues('GeologicEvents','GeologicEvents_ID',geologicEvents):
        unusedGeologicEvents.append(space4+'Error: did not find field GeologicEvents_ID in table GeologicEvents')
    valueLinks = []
    if not loadTableValues('ExtendedAttributes','ValueLinkID',valueLinks):
        unusedGeologicEvents.append(space4+'Error: did not find field ValueLink in table ExtendedAttributes')
    #compare
    geologicEventRefs = []
    for ve in valueLinks:
        if ve in geologicEvents:
            geologicEventRefs.append(ve)

    # Check formatting of HierarchyKey in DescriptionOfMapUnits
    if numberOfRows('DescriptionOfMapUnits') > 0:
            addMsgAndPrint('    Checking HierarchyKey (DMU) formatting')
            hKeys = []
            if loadTableValues('DescriptionOfMapUnits','HierarchyKey',hKeys):
                partLength = len(hKeys[0].split('-')[0])
                for hKey in hKeys:
                    hKeyParts = hKey.split('-')
                    keyErr = False
                    for hKeyPart in hKeyParts:
                        if len(hKeyPart) != partLength:
                                keyErr = True
                    if keyErr:
                        hKeyErrors.append('    '+hKey)  
            else:
                hKeyErrors.append(space4+'Error: did not find field HierarchyKey in table DescriptionOfMapUnits')

def dmuRequiredValues():
    addMsgAndPrint('  Checking for required values in DMU...')
    dmu = 'DescriptionOfMapUnits'
    addMsgAndPrint('    '+str(numberOfRows(dmu))+' rows in DMU')
    if numberOfRows(dmu) > 0:
        # open searchcursor on dmu
        fields = ['OBJECTID','MapUnit','Name','FullName','Age','Description','GeoMaterial','GeoMaterialConfidence',
                  'HierarchyKey','ParagraphStyle','Symbol','AreaFillRGB','DescriptionSourceID']
        try:
            with arcpy.da.SearchCursor(dmu,fields) as cursor:
                for row in cursor:
                    if isNullValue(row[2]):
                        missingRequiredValues.append('<span class="tables">DescriptionOfMapUnits</span>, OBJECTID='+str(row[0])+' Name')
                    if not isNullValue(row[1]):   # if MapUnit is set
                        for i in range(3,len(fields)):
                            if isNullValue(row[i]):
                                missingRequiredValues.append('<span class="tables">DescriptionOfMapUnits</span>, OBJECTID='+str(row[0])+', <span class="fields">'+fields[i]+'</span>')
        except:
            addMsgAndPrint('    Cannot examine DMU table for required values. Perhaps some fields are missing?')
            missingRequiredValues.append('DescriptionOfMapUnits not checked for required values')

def tableToHtml(html,table):
    # html is output html file
    # table is input table
    fields = arcpy.ListFields(table)
    for field in fields:
        print(field.name)
    # start table
    html.write('<div class="tablediv">\n')
    html.write('<table class="ess-tables">\n')
    # write header row
    html.write('<tr>\n')
    fieldNames = []
    for field in fields:
        if not field.name in ('OBJECTID','Shape_Length','created_user','created_date','last_edited_user','last_edited_date'):
            if field.name.find('_ID') > 1:
                token = '_ID'
            else:
                token = field.name
            html.write('<th>'+token+'</th>\n')
            fieldNames.append(field.name)
    html.write('</tr>\n')
    # write rows
    with arcpy.da.SearchCursor(table,fieldNames) as cursor:
        for row in cursor:
            html.write('<tr>\n')
            for i in range(0,len(fieldNames)):
                if isinstance(row[i],str):
                    html.write('<td>'+row[i]+'</td>\n')
                    #html.write('<td>'+row[i].encode('ascii','xmlcharrefreplace')+'</td>\n')
                else:
                    try:
                        if str(row[i]) == 'None':
                            html.write('<td>---</td>\n')
                        else:
                            html.write('<td>'+ str(row[i])+'</td>\n')
                    except:
                        html.write('<td>***</td>\n')
                        addMsgAndPrint(str(type(row[i])))
                        addMsgAndPrint(row[i])
            html.write('</tr>\n')    
    # finish table
    html.write('</table>\n'+divend)

def writeContentErrors(outfl,errors,noErrorString,outFile,htmlFileCount):
    if debug: addMsgAndPrint(errors[len(errors)-1])
    if len(errors) == 1:
        outfl.write(noErrorString+'<br><br>\n')
        return htmlFileCount
    # find duplicates
    errors2 = errors[1:]
    errors2.sort()
    errors3 = []
    i = 0
    n = 1
    oldLine = errors2[0]
    for i in range(1,len(errors2)):
        if errors2[i] == oldLine:
            n = n+1
        else:
            errors3.append([oldLine,n])
            oldLine = errors2[i]
            n = 1
    errors3.append([oldLine,n])
    # write results
    if len(errors) < 10:
        writefl = outfl
    else:
        # set writefl to external file
        fName = outFile.replace('.html',str(htmlFileCount)+'.html')
        htmlFileCount += 1                                
        writefl = open(fName,'w')
        writefl.write(style)
        writefl.write(rdiv)
        # write link to outfl
        outfl.write(errors[0]+'<a href ="'+'file://'+fName+'"><br>'+space4+'View ('+str(len(errors)-1)+') Errors. (Link to New File)</a><br><br>\n') 
    writefl.write(errors[0]+'<br>\n')
    for aline in errors3:
        try:
            writefl.write(aline[0])
        except:
            addMsgAndPrint(str(aline[0]))
        if aline[1] > 1:
            writefl.write('--'+str(aline[1]+1)+' duplicates<br>\n')
        else:
            writefl.write('<br>\n')
    writefl.write('<br>\n')
    if writefl != outfl:
        writefl.close()
    return htmlFileCount

def writeOutput(outFile,tables,thisDatabase):
    addMsgAndPrint( '  Writing output...')
    # Python 3 open builtin takes optional errors parameter 'xmlcharrefreplace' to escape
    # XML/HTML characters. Don't need to specify this at write(str.encode)
    outfl = open(outFile,'w', errors='xmlcharrefreplace')
    #write the style and overview html
    outfl.write(style+"""
    <h2 id="overview">Geodatabase</h2>
    <div class="report">
    """)
    outfl.write('Testing for compliance with GeMS database schema<br>\n')
    outfl.write('Geodatabase path: '+thisDatabase+'<br>\n')
    outfl.write('This file written by '+versionString+'<br>\n')
    outfl.write(time.asctime(time.localtime(time.time()))+'<br></div>\n')
    
    #write the html
    outfl.write(overviewhtml)
    
    #  Schema errors
    outfl.write('<h2 id="schema-errors">Schema Errors</h2>\n'+rdiv)
    if len(schemaErrors) == 0:
        outfl.write('None<br>\n')
    else: 
        for aline in schemaErrors:
            outfl.write(aline+'<br>\n')
    outfl.write(divend)        
            
    # Extensions to schema
    outfl.write('<h2 id="extensions">Extensions to Schema</h2>\n'+rdiv)
    outfl.write('<h4> The items below have been found in the geodatabase, but are not required for a valid GeMS Database.</h4>')
    if len(schemaExtensions) == 0:
        outfl.write('None<br>\n')
    else: 
        for aline in schemaExtensions:
            outfl.write(aline+'<br>\n')
    outfl.write(divend)
    
    
    # CONTENT ERRORS
    hFC = 1  # counter for external HTML files
    outfl.write('<h2 id="content-errors">Content Errors</h2>\n')
    outfl.write(rdiv)
    hFC = writeContentErrors(outfl,duplicateIDs,'No duplicate _IDs',outFile,hFC)
    hFC = writeContentErrors(outfl,missingSourceIDs,'No missing entries in DataSources',outFile,hFC)
    hFC = writeContentErrors(outfl,unusedDataSources,'No unreferenced entries in DataSources',outFile,hFC)
    hFC = writeContentErrors(outfl,missingDmuMapUnits,'No missing MapUnits in DescriptionOfMapUnits',outFile,hFC)
    if 'StandardLithology' in tables:
        hFC = writeContentErrors(outfl,missingStandardLithMapUnits,'No missing MapUnits in StandardLithology',outFile,hFC)
        hFC = writeContentErrors(outfl,unreferencedStandardLithMapUnits,'No unreferenced MapUnits in StandardLithology',outFile,hFC)
    #writeContentErrors(outfl,unreferencedDmuMapUnits,'No unreferenced MapUnits in Description of MapUnits')
    hFC = writeContentErrors(outfl,missingGlossaryTerms,'No missing terms in Glossary',outFile,hFC)
    hFC = writeContentErrors(outfl,unusedGlossaryTerms,'No unreferenced terms in Glossary',outFile,hFC)
    if 'ExtendedAttributes' in tables:
        hFC = writeContentErrors(outfl,unreferencedIds,'No rows in ExtendedAttributes that reference nonexistent OwnerIDs or ValueLinkIDs',outFile,hFC)
        if 'GeologicEvents' in tables:
            hFC = writeContentErrors(outfl,unusedGeologicEvents,'No rows in GeologicEvents not referenced in ExtendedAttributes',outFile)
    hFC = writeContentErrors(outfl,hKeyErrors,'No format errors in HierarchyKeys',outFile,hFC)
    #writeContentErrors(outfl,allBadNulls,'No pseudonulls or trailing spaces')
    hFC = writeContentErrors(outfl,missingRequiredValues,'No fields without required values',outFile,hFC)
    hFC = writeContentErrors(outfl,zeroLengthStrings,'No zero-length strings',outFile,hFC)
    outfl.write(divend)
    
    
    # units match in map, DMU, CMU, and cross sections
    outfl.write('<h2 id="match">MapUnits match across map, DMU, CMU, and cross-sections</h2>\n')
    outfl.write(rdiv)
    outfl.write(equivalenceErrors[0])
    for i in range(1,len(equivalenceErrors)):
        outfl.write(equivalenceErrors[i])
    outfl.write('</table>'+divend)    
    
    
    # listing of essential tables
    ## make tempGdb
    tempGdb = os.path.dirname(thisDatabase)+'/xxxTemp.gdb'
    testAndDelete(tempGdb)
    arcpy.CreateFileGDB_management(os.path.dirname(thisDatabase),'xxxTemp.gdb')  
    outfl.write('<h2 id="essential">Essential Tables</h2>\n')
    for eTable in 'DataSources','DescriptionOfMapUnits','Glossary','MiscellaneousMapInformation','StandardLithology':
        if arcpy.Exists(thisDatabase+'/'+eTable):
            outfl.write('<h3 class="table-header">'+eTable+'</h3>\n')
            if eTable == 'DescriptionOfMapUnits':
                sortField = 'HierarchyKey'
            else:
                sortField = eTable+'_ID'
            arcpy.Sort_management(thisDatabase+'/'+eTable,tempGdb+'/xxx'+eTable,sortField)
            tableToHtml(outfl,tempGdb+'/xxx'+eTable)
    outfl.write(divend)
    
    ## delete tempGdb
    testAndDelete(tempGdb)
    
    # Database description
    outfl.write('<h2 id="gdb-desc" class="table-header">Geodatabase Description</h2>\n<div class="tablediv">')
    for aline in gdbDescription:
        outfl.write(aline+'\n')
    outfl.write(divend)

    outfl.close()

def validInputs(thisDatabase,outFile):
    # does input database exist? Is it plausibly a geodatabase?
    if os.path.exists(thisDatabase) and thisDatabase[-4:].lower() in ('.gdb','.mdb'):
        # is output workspace writable?
        try:
            outfl = open(outFile,'w')
            outfl.write('A test')
            outfl.close()
            return True
        except:
            addMsgAndPrint('  Cannot open and write file '+outFile)
            return False
    else:
        addMsgAndPrint('  Object '+thisDatabase+' does not exist or is not a geodatabase')
        return False


#thisDatabase = sys.argv[1]
thisDatabase = os.path.abspath(sys.argv[1])
outputWorkspace = sys.argv[2]
addMsgAndPrint('  Starting...')
if not arcpy.Exists(outputWorkspace):
    outputWorkspace = os.path.dirname(thisDatabase)
if not outputWorkspace[-1:] in ('/','\\'):
    outputWorkspace = outputWorkspace+'/'
outFile = outputWorkspace + os.path.basename(thisDatabase)+'-Validation.html'
for hFC in range(1,15):
    fName = outFile.replace('.html',str(hFC)+'.html')
    if os.path.exists(fName):
        os.remove(fName)
arcpy.QualifiedFieldNames = False
if validInputs(thisDatabase,outFile):
    try:
        arcpy.env.workspace = thisDatabase
    except:
        addMsgAndPrint('  Unable to load workspace '+thisDatabase+'. Not an ESRI geodatabase?')
    else:
        addMsgAndPrint('  '+versionString)
        addMsgAndPrint('  geodatabase '+thisDatabase+' loaded')
        addMsgAndPrint('  output will be written to file '+outFile)
        tables = list(arcpy.ListTables())
        inventoryWorkspace(tables,fdsfc)
        checkRequiredElements()
        checkFieldsAndFieldDefinitions()
        checkContent()
        dmuRequiredValues()
        writeOutput(outFile,tables,thisDatabase)
        addMsgAndPrint('  DONE')

##raise arcpy.ExecuteError

# Things to be done:
#    Inventory data set   DONE
#    Check for required tables, featuredatasets, featureclasses    DONE 
#    For optional featuredatasets, check for required featureclasses   DONE
#    For required and optional tables, 
#        check for required fields   DONE
#        check field definitions    DONE
#     Accumulate list of all must-be-globally-unique (_ID) values  DONE
#    Accumulate list of all ToBeDefined values (references to Glossary)   DONE
#       see gFieldDefList, above
#       what about StandardLithology:Lithology?
#    Accumulate list of all MapUnit references  DONE
#     Accumulate list of all DataSources references  DONE
#    Check that must-be-globally-unique values are unique  DONE
#    Check that all values of fields name cn 'Source' correspond to values of DataSources_ID  DONE
#    Check that MapUnits referenced by StandardLithology and any fClass whose name cn 'Poly' 
#        are present in DMU  DONE
#    Check for definitions of ToBeDefined values  DONE
#        EXCEPT PropertyValue values that are numeric (in part)  STILL TO BE DONE!
#    In DMU, check HierarchyKey format  DONE
#    Check for illegal null values: ' ' (null-equivalent) created when loading data into tables  DONE
#    Check that all MapUnits have StandardLithology entries  DONE
#    Check for unreferenced entries in DataSources (DONE), Glossary (DONE), StandardLithology (DONE),
#        DMU (DONE), Geologic Events (DONE),
#     DOES NOT CHECK THAT GeologicEvents REFERENCED BY ValueLinkID IN ExtendedAttributes ARE PRESENT
#    Error trapping:
#        So it doesn't fail with bad input  DONE, somewhat
#        So it doesn't fail with bad field names. e.g. _ID field  DONE, I think

# check for consistency between CMU, DMU, MapUnitPolys, and any cross-sections:
#     Do units in DMU and CMU match?
#     are all units shown in map and sections listed in CMU and DMU?
#     are all units in DMU present in map and (or) at least one section?
