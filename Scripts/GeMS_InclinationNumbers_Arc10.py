import arcpy, os.path, sys, math, shutil
from GeMS_utilityFunctions import *

versionString = 'GeMS_InclinationNumbers_Arc10.py, version of 30 October 2017'

debug1 = False
OPLName = 'OrientationPointLabels'

#########Stuff for placing dip/plunge numbers########
def showInclination(oType):
    if 'horizontal' in oType.lower() or 'vertical' in oType.lower() or len(oType) < 2:
        return False
    else:
        return True

def findLyr(lname):
    if debug1: addMsgAndPrint('lname = '+lname)
    mxd = arcpy.mapping.MapDocument('CURRENT')
    for df in arcpy.mapping.ListDataFrames(mxd):
        lList = arcpy.mapping.ListLayers(mxd, '*', df)
        if debug1:
            for lyr in lList:
                writeLayerNames(lyr)
        for lyr in lList:
            # either layer is a group, datasetName is not supported, and we match lyr.name
            # or (and) we match datasetName, which cannot be aliased as lyr.name may be
            if (lyr.supports('dataSource') and (lyr.dataSource == lname or lyr.dataSource == lname.replace('/','\\') )) \
                    or (not lyr.supports('dataSource') and lyr.name == lname):
                pos = lList.index(lyr)
                if pos == 0:
                    refLyr = lList[pos + 1]
                    insertPos = "BEFORE"
                else:
                    refLyr = lList[pos - 1]
                    insertPos = "AFTER"
                return [lyr, df, refLyr, insertPos]

def writeLayerNames(lyr):
    if lyr.supports('datasetName'): addMsgAndPrint('datasetName: '+lyr.datasetName)
    if lyr.supports('dataSource'):  addMsgAndPrint(' dataSource: '+lyr.dataSource)
    if lyr.supports('longName'):    addMsgAndPrint('   longName: '+lyr.longName)
    if lyr.supports('name'):        addMsgAndPrint('       name: '+lyr.name)

##main routine from DipNumbers2.py
def dipNumbers(gdb,mapScaleDenominator):
    if not arcpy.Exists(gdb+'/GeologicMap/OrientationPoints'):
        addMsgAndPrint('  Geodatabase '+os.path.basename(gdb)+' lacks feature class OrientationPoints.')
        return

    desc = arcpy.Describe(gdb+'/GeologicMap/OrientationPoints')
    mapUnits = desc.spatialReference.linearUnitName
    if 'meter' in mapUnits.lower():
        mapUnitsPerMM = float(mapScaleDenominator)/1000.0
    else:
        mapUnitsPerMM = float(mapScaleDenominator)/1000.0 * 3.2808

    if numberOfRows(gdb+'/GeologicMap/OrientationPoints') == 0:
        addMsgAndPrint('  0 rows in OrientationPoints.')
        return

    ## MAKE ORIENTATIONPOINTLABELS FEATURE CLASS
    arcpy.env.workspace = gdb+'/GeologicMap'
    OPL = gdb+'/GeologicMap/'+OPLName
    if arcpy.TestSchemaLock(OPL) == False:
        addMsgAndPrint('    TestSchemaLock('+OPLName+') = False.')
        #raise arcpy.ExecuteError
        #return
        #pass
       
    testAndDelete(OPL)
    arcpy.CreateFeatureclass_management(gdb+'/GeologicMap',OPLName,'POINT')
    arcpy.AddField_management(OPL,'OrientationPointsID','TEXT',"","",50)
    arcpy.AddField_management(OPL,'Inclination','TEXT',"","",3)
    arcpy.AddField_management(OPL,'PlotAtScale','FLOAT')

    ## ADD FEATURES FOR ROWS IN ORIENTATIONPOINTS WITHOUT 'HORIZONTAL' OR 'VERTICAL' IN THE TYPE VALUE
    OPfields = ['SHAPE@XY','OrientationPoints_ID','Type','Azimuth','Inclination','PlotAtScale']
    attitudes = arcpy.da.SearchCursor(gdb+'/GeologicMap/OrientationPoints',OPfields)
    OPLfields = ['SHAPE@XY','OrientationPointsID','Inclination','PlotAtScale']
    inclinLabels = arcpy.da.InsertCursor(OPL,OPLfields)
    for row in attitudes:
        oType = row[2]
        if showInclination(oType):
            x = row[0][0]
            y = row[0][1]
            OP_ID = row[1]
            azi = row[3]
            inc = int(round(row[4]))
            paScale = row[5]
            if isPlanar(oType):
                geom = ' S '
                inclinRadius = 2.4 * mapUnitsPerMM
                azir = math.radians(azi)
            else: # assume linear
                geom = ' L '
                inclinRadius = 7.4 * mapUnitsPerMM
                azir = math.radians(azi - 90)
            ix = x + math.cos(azir)*inclinRadius
            iy = y - math.sin(azir)*inclinRadius

            addMsgAndPrint( '    inserting '+oType+geom+str(int(round(azi)))+'/'+str(inc))
            inclinLabels.insertRow(([ix,iy],OP_ID,inc,paScale))
            
    del inclinLabels
    del attitudes

    ## INSTALL NEWLY-MADE FEATURE CLASS USING .LYR FILE. SET DATA SOURCE. SET DEFINITION QUERY    

    #make copy of .lyr file
    newLyr = os.path.dirname(gdb)+'/NewOrientationPointLabels.lyr'
    shutil.copy(os.path.dirname(sys.argv[0])+'/../Resources/OrientationPointLabels.lyr',newLyr)
    OPLyr = arcpy.mapping.Layer(newLyr)
    ## reset data source
    addMsgAndPrint('   gdb = '+gdb)
    if gdb[-3:].lower() == 'gdb':
        wsType = 'FILEGDB_WORKSPACE'
    elif gdb[-3:].lower() == 'mdb':
        wsType = 'ACCESS_WORKSPACE'
    else:
        addMsgAndPrint('Workspace type not recognized.')
        forceExit()
    #### note how we don't include the feature dataset in the workspace 
    OPLyr.replaceDataSource(gdb,wsType,'OrientationPointLabels' )
    ## set definition query
    pasName = arcpy.AddFieldDelimiters(gdb,'PlotAtScale')
    defQuery = pasName+' >= '+str(mapScaleDenominator)
    OPLyr.definitionQuery = defQuery

    # Insert new OrientationPointLabels.lyr
    try:
        lyr,df,refLyr,insertPos = findLyr(gdb+'\GeologicMap\OrientationPoints')
        arcpy.mapping.InsertLayer(df,lyr,OPLyr,'BEFORE')
    except:
        addMsgAndPrint('  Unable to insert OrientationPointLabels.lyr.')

    
#####################################################
addMsgAndPrint('  '+versionString)

# get inputs
inFds = sys.argv[1]
mapScale = float(sys.argv[2])
 
caf = getCaf(inFds)
orp = caf.replace('ContactsAndFaults','OrientationPoints')
fields = ['Type','IsConcealed','LocationConfidenceMeters','ExistenceConfidence','IdentityConfidence','Symbol']

#addMsgAndPrint('  Feature dataset '+inFds+': isLocked = '+str(arcpy.TestSchemaLock(inFds)))

if os.path.basename(inFds) == 'GeologicMap':
    dipNumbers(os.path.dirname(inFds),mapScale)
else:
    addMsgAndPrint('Not GeologicMap feature class, OrientationPointLabels not (re)created.')
    

