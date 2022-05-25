# utility functions for scripts that work with GeMS geodatabase schema

import arcpy, os.path, time, glob
editPrefixes = ('xxx','edit_','errors_','ed_')
debug = False
import requests

# I. General utilities

# tests for null string values and <Null> numeric values
# Does not test for numeric nulls -9, -9999, etc. 
def stringIsGeMSNull(val):
    if val == None:
        return True
    elif isinstance(val,(str)) and val in ('#', '#null'):
        return True
    else:
        return False

def addMsgAndPrint(msg, severity=0): 
    # prints msg to screen and adds msg to the geoprocessor (in case this is run as a tool) 
    #print msg 

    try: 
        for string in msg.split('\n'): 
            # Add appropriate geoprocessing message 
            if severity == 0: 
                arcpy.AddMessage(string) 
            elif severity == 1: 
                arcpy.AddWarning(string) 
            elif severity == 2: 
                arcpy.AddError(string) 
    except: 
        pass

def forceExit():
    addMsgAndPrint('Forcing exit by raising ExecuteError')
    raise arcpy.ExecuteError

def numberOfRows(aTable):
    return int(str(arcpy.GetCount_management(aTable)))

def testAndDelete(fc):
    if arcpy.Exists(fc):
        arcpy.Delete_management(fc)

def fieldNameList(aTable):
    '''Send this a catalog path to avoid namespace confusion'''
    return [f.name for f in arcpy.ListFields(aTable)]

def writeLogfile(gdb,msg):
    timeUser = '['+time.asctime()+']['+os.environ['USERNAME']+'] '
    logfileName = os.path.join(gdb,'00log.txt')
    try:
        logfile = open(os.path.join(gdb,logfileName),'a')
        logfile.write(timeUser+msg+'\n')
        logfile.close()
    except:
        addMsgAndPrint('Failed to write to '+logfileName)
        addMsgAndPrint('  maybe file is already open?')

def getSaveName(fc):
    # fc is entire pathname
    # builds new, unused name in form oldNameNNN
    oldWS = arcpy.env.workspace
    arcpy.env.workspace = os.path.dirname(fc)
    shortFc = os.path.basename(fc)
    pfcs = arcpy.ListFeatureClasses(shortFc+'*')
    if debug: addMsgAndPrint(str(pfcs))
    maxN = 0
    for pfc in pfcs:
        try:
            n = int(pfc.replace(shortFc,''))
            if n > maxN:
                maxN = n
        except:
            pass
    saveName = fc+str(maxN+1).zfill(3)
    arcpy.env.workspace = oldWS
    if debug:
        addMsgAndPrint('fc = '+fc)
        addMsgAndPrint('saveName = '+saveName)
    return saveName

#dictionary of translations from field types (as described) to field types as
#  needed for AddField
typeTransDict =     { 'String': 'TEXT',
			'Single': 'FLOAT',
			'Double': 'DOUBLE',
			'NoNulls':'NON_NULLABLE',
			'NullsOK':'NULLABLE',
			'Date'  : 'DATE'  }

# II. Functions that presume extensions to naming scheme

## getCaf needs to be recoded to use a prefix value
def getCaf(inFds, prefix = ''):
    arcpy.env.workspace = inFds
    fcs = arcpy.ListFeatureClasses()
    cafs = []
    for fc in fcs:
        if fc.find('ContactsAndFaults') > -1 or (inFds.find('CorrelationOfMapUnits') > -1 and fc.find('Lines') > -1):
            cafs.append(fc)
    for fc in cafs:
        for pfx in editPrefixes:
            if fc.find(pfx) > -1:  # no prefix
                cafs.remove(fc)
    cafs2 = []
    for fc in cafs:
        if fc[-17:] == 'ContactsAndFaults' or (inFds.find('CorrelationOfMapUnits') > -1 and fc[-5:] == 'Lines'):
            cafs2.append(fc)
    #addMsgAndPrint(str(cafs))
    if len(cafs2) != 1:
        addMsgAndPrint('  Cannot resolve ContactsAndFaults feature class in feature dataset')
        addMsgAndPrint('    '+inFds)
        addMsgAndPrint('    '+str(cafs2))
        raise arcpy.ExecuteError
    return os.path.join(inFds,cafs2[0])

def getMup(fds):
    caf = getCaf(fds)
    return caf.replace('ContactsAndFaults','MapUnitPolys')

def getNameToken(fds):
    if os.path.basename(fds) == 'CorrelationOfMapUnits':
        return 'CMU'
    else:
        caf = os.path.basename(getCaf(fds))
        return caf.replace('ContactsAndFaults','')

#III. Functions that presume Type (vocabulary) values

def isFault(lType):
    if lType.upper().find('FAULT') > -1:
        return True
    else:
        return False

def isContact(lType):
    uType = lType.upper()
    if uType.find('CONTACT') > -1:
        val = True
    elif uType.find('FAULT') > -1:
        val = False
    elif uType.find('SHORE') > -1 or uType.find('WATER') > -1:
        val = True
    elif uType.find('SCRATCH') > -1:
        val = True
    elif uType.find('MAP') > -1 or uType.find('NEATLINE') > -1: # is map boundary?
        val = False
    elif uType.find('GLACIER') > -1 or uType.find('SNOW') > -1 or uType.find('ICE') > -1:
        val = True
    else:
        addMsgAndPrint('function isContact, lType not recognized, lType = '+lType)
        val = False
    if debug: addMsgAndPrint(lType+'  '+uType+'  '+str(val))
    return val


# evaluates values of ExistenceConfidence and IdentifyConfidence 
#   to see if a feature should be queried
def isQuestionable(confidenceValue):
    if confidenceValue != None:
        if confidenceValue.lower() != 'certain' and confidenceValue.lower() != 'unspecified':
            return True
        else:
            return False
    else:
        return False

# returns True if orientationType is a planar (not linear) feature
def isPlanar(orientationType):
    planarTypes = ['joint','bedding','cleavage','foliation','parting']
    isPlanarType = False
    for pT in planarTypes:
        if pT in orientationType.lower():
            isPlanarType = True
    return isPlanarType

def editSessionActive(gdb):
    # returns True if edit session active, else False
    # test for 
    if arcpy.Exists(gdb+'/GeoMaterialDict'):
        tbl = gdb+'/GeoMaterialDict'
        fld = 'GeoMaterial'
    elif arcpy.Exists(gdb+'/GeologicMap/MapUnitPolys') and numberOfRows(gdb+'/GeologicMap/MapUnitPolys') > 2:
        tbl = gdb+'/GeologicMap/MapUnitPolys'
        fld = 'MapUnit'
    else:
        # doesn't appear to be a GeMS database
        # default to no edit session active and bail
        return False 
    ## Following code modified from routine posted by Curtis Price at
    ## https://gis.stackexchange.com/questions/61708/checking-via-arcpy-if-arcmap-is-in-edit-session
    edit_session = True
    try:
        # attempt to open two cursors on the input
        # this generates a RuntimeError if no edit session is active
        with arcpy.da.UpdateCursor(tbl, fld) as rows:
            row = next(rows)
            with arcpy.da.UpdateCursor(tbl, fld) as rows2:
                row2 = next(rows2)
    except RuntimeError as e:
        if "workspace already in transaction mode" in str(e):
            # # this error means that no edit session is active
            edit_session = False
        else:
            # # # we have some other error going on, report it
            raise
    return edit_session
    
def checkVersion(vString, rawurl, toolbox):
    # compares versionString of tool script to the current script at the repo
    try:
        page = requests.get(rawurl)
        raw = page.text
        if vString in raw:
            pass
            arcpy.AddMessage("This version of the tool is up to date")
        else:
            repourl = 'https://github.com/usgs/{}/releases'.format(toolbox)
            arcpy.AddWarning('You are using an obsolete version of this tool!\n' +
                             'Please download the latest version from {}'.format(repourl))
    except:
        arcpy.AddWarning('Could not connect to Github to determine if this version of the tool is the most recent.\n')
                            

