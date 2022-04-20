'''
Projects all data in GeologicMap feature dataset (in_fds) to cross-section plane
Creates featureclasses with names prefixed by 'ed_'
Output feature classes have all input FC attributes. In addition, point feature
  classes are given attribute:
    DistanceFromSection 
    LocalCsAzimuth  (Trend of section line at projected point,
         0..360, measured CCW from grid N)
If points are OrientationData, we also calculate attributes:
    ApparentInclination
    Obliquity
    PlotAzimuth (= apparentInclination + 90)

Assumptions:
  Input FDS is GeologicMap
  xs_line has only ONE LINE (one row in data table)
  We don't project points that are beyond ends of xs_line,
     even though to do so is often desirable
  We don't project feature classes whose names begin with
     the strings 'errors_'  or 'ed_'

Much of this code is modeled on cross-section routines written by
Evan Thoms, USGS, Anchorage.

Ralph Haugerud
rhaugerud@usgs.gov
'''

# 10 June 2019: Updated to work with Python 3 in ArcGIS Pro. -Evan Thoms
# Ran script through 2to3 and it worked with no other edits necessary.
# Consider re-writing some sections to work with new Python modules, but none of the 
# 'older' code causes any errors.

import arcpy, sys, os, math
from GeMS_Definition import tableDict
from GeMS_utilityFunctions import *

versionString = 'GeMS_ProjectCrossSectionData_Arc10.py, version of 10 June 2019'
rawurl = 'https://raw.githubusercontent.com/usgs/gems-tools-pro/master/Scripts/GeMS_ProjectCrossSectionData_AGP2.py'
checkVersion(versionString, rawurl, 'gems-tools-pro')

##inputs
#  gdb          geodatabase with GeologicMap feature dataset to be projected
#  project_all
#  fcToProject
#  dem          
#  xs_path       cross-section line: _single-line_ feature class or layer
#  startQuadrant start quadrant (NE, SE, SW, NW)
#  token   output feature dataset. Input value is appended to 'CrossSection'
#  vertEx       vertical exaggeration; a number
#  buffer_distance  a number
#  forcExit
#  scratchWS
#  saveIntermediate (boolean)

lineCrossingLength = 500   # length (in map units) of vertical line drawn where arcs cross section line
exemptedPrefixes = ('errors_', 'ed_')  # prefixes that flag a feature class as not to be projected

transDict =   { 'String': 'TEXT',
		'Single': 'FLOAT',
		'Double': 'DOUBLE',
	    	'NoNulls':'NON_NULLABLE',
    		'NullsOK':'NULLABLE',
    		'Date'  : 'DATE'  }

##### UTILITY FUNCTIONS ############################

def doProject(fc):
    doPrj = True
    for exPfx in exemptedPrefixes:
        if fc.find(exPfx) == 0:
            doPrj = False
    return doPrj

def wsName(obj):
    return os.path.dirname(obj)

def cartesianToGeographic(angle):
    ctg = -90 - angle
    if ctg < 0:
        ctg = ctg + 360
    return ctg

def isAxial(ptType):
    m = False
    for s in ('axis', 'lineation', ' L'):
        if ptType.upper().find(s.upper()) > -1:
            m = True
    return m

def obliq(theta1, theta2):
    obl = abs(theta1-theta2)
    if obl > 180:
        obl = obl-180
    if obl > 90:
        obl = 180 - obl
    return obl

def azimuthDifference(a, b):
    # a, b are two azimuths in clockwise geographic notation
    # azDiff is in range -180..180
    # if azDiff < 0, a is counterclockwise of b
    # if azDiff > 0, a is clockwise of b
    azDiff = a - b
    if azDiff > 180:
        azDiff = azDiff - 360
    if azDiff < -180:
        azDiff = azDiff + 360
    return azDiff

def plotAzimuth(inclinationDirection, thetaXS, apparentInclination):
    azDiff = azimuthDifference(thetaXS, inclinationDirection)
    if azDiff >= -90 and azDiff <= 90:
        return 270 + apparentInclination
    else:
        return 270 - apparentInclination

def apparentPlunge(azi, inc, thetaXS):
    obliquity = obliq(azi, thetaXS)  
    appInc = math.degrees(math.atan(vertEx * math.tan(math.radians(inc)) * math.cos(math.radians(obliquity))))
    return appInc, obliquity

def apparentDip(azi, inc, thetaXS):
    obliquity = obliq(azi, thetaXS) 
    appInc = math.degrees(math.atan(vertEx * math.tan(math.radians(inc)) * math.sin(math.radians(obliquity))))
    return appInc, obliquity

def getid_field(fc):
    id_field = ''
    fcFields = arcpy.ListFields(fc)
    for fld in fcFields:
        if fld.name.find('_ID') > 0:
            id_field = fld.name
    return id_field

#  copied from NCGMP09v1.1_CreateDatabase_Arc10.0.py, version of 20 September 2012
def createFeatureClass(thisDB, featureDataSet, featureClass, shapeType, fieldDefs):
    try:
        arcpy.env.workspace = thisDB
        arcpy.CreateFeatureclass_management(featureDataSet, featureClass, shapeType)
        thisFC = os.path.join(thisDB, featureDataSet, featureClass)
        for fDef in fieldDefs:
            try:
                if fDef[1] == 'String':
                    arcpy.AddField_management(thisFC, fDef[0], transDict[fDef[1]], '#', '#', fDef[3], '#', transDict[fDef[2]])
                else:
                    arcpy.AddField_management(thisFC, fDef[0], transDict[fDef[1]], '#', '#', '#', '#', transDict[fDef[2]])
            except:
                addMsgAndPrint('failed to add field ' + fDef[0] + ' to feature class ' + featureClass)
                addMsgAndPrint(arcpy.GetMessages(2))
    except:
        addMsgAndPrint(arcpy.GetMessages())
        addMsgAndPrint('failed to create feature class ' + featureClass + ' in dataset ' + featureDataSet)

#def locateevent_tbl(gdb, fc_name, pts, dem, sel_distance, event_props, zType, isLines = False):

def locateevent_tbl(pts, sel_distance, event_props, z_type, is_lines=False):
    desc = arcpy.Describe(pts)

    if not desc.hasZ:
        addMsgAndPrint('      adding Z values')
        arcpy.ddd.AddSurfaceInformation(pts, dem, z_type, 'LINEAR')

    # working around bug in LocateFeaturesAlongRoutes
    # add special field for duplicate detection
    # possibly explained here:
    # https://community.esri.com/t5/geoprocessing-questions/locate-features-along-route-returns-duplicate/td-p/229422
    dupDetectField = 'xDupDetect'
    arcpy.management.AddField(pts, dupDetectField, 'LONG')
    
    # and calc this field = OBJECTID
    OID = arcpy.Describe(pts).OIDFieldName
    expr = f"'{OID}'"
    arcpy.management.CalculateField(pts, dupDetectField, expr, "PYTHON3")
    
    # locate line_pts along route
    addMsgAndPrint('      making event table')
    event_tbl = os.path.join(scratch, f'{fc_name}_evtbl')
    arcpy.lr.LocateFeaturesAlongRoutes(pts, zm_line, id_field, sel_distance, event_tbl, event_props)
    nRows = numberOfRows(event_tbl)
    nPts = numberOfRows(pts)
    if nRows > nPts and not is_lines:  # if LocateFeaturesAlongRoutes has made duplicates  (A BUG!)
        addMsgAndPrint('      correcting for bug in LocateFeaturesAlongRoutes')
        addMsgAndPrint(f'        {str(nRows)} rows in event table')
        addMsgAndPrint('        removing duplicate entries in event table')
        arcpy.DeleteIdentical_management(event_tbl, dupDetectField)  
        addMsgAndPrint(f'        {str(numberOfRows(event_tbl))} rows in event table')
    arcpy.DeleteField_management(event_tbl, dupDetectField)
    return event_tbl

def field_none(fc, field):
    try:
        with arcpy.da.SearchCursor(fc, field) as rows:
            if rows.next()[0] in [None, '']:
                return False
            else:
                return True
    except:
        return False

###############################################################
addMsgAndPrint('\n  ' + versionString)

gdb         = sys.argv[1]
project_all  = sys.argv[2]
fcToProject = sys.argv[3]
dem         = sys.argv[4]
xs_path      = sys.argv[5]
startQuadrant = sys.argv[6]
token   = sys.argv[7]
vertEx      = float(sys.argv[8])
buffer_distance = float(sys.argv[9])
addLTYPE    = sys.argv[10]
forceExit   = sys.argv[11]
scratchws   = sys.argv[12]
saveIntermediate = sys.argv[13]

if project_all == 'true':
    project_all = True
else: project_all = False

if addLTYPE == 'true':
    addLTYPE = True
else: addLTYPE = False

if forceExit == 'true': 
    forceExit = True
else: forceExit = False

if saveIntermediate == 'true':
    saveIntermediate = True
else: saveIntermediate = False

if arcpy.Exists(scratchws):
    scratch = scratchws
else:
    scratch = arcpy.mp.ArcGISProject().defaultGeodatabase
addMsgAndPrint(f'  scratch directory is {scratch}')

try:
    arcpy.CheckOutExtension('3D')
except:
    arcpy.AddError('Extension not found!')
    addMsgAndPrint('\nCannot check out 3D-analyst extension.')
    sys.exit()

# get the object dictionary of the GeologicMap feature dataset
# never have to Describe or use ListFields from here on
in_fds = os.path.join(gdb, 'GeologicMap')
addMsgAndPrint(f'building a dictionary of the contents of {in_fds}')

fd_dict = gdb_object_dict(in_fds)

new_fd = f'CrossSection{token}'
out_fds = os.path.join(gdb, new_fd)
arcpy.env.overwriteOutput = True

# get the basename of the cross line feature class if passed a path
xs_name = os.path.basename(xs_path)

# Checking section line
addMsgAndPrint('  checking section line')

# does xs_path have 1-and-only-1 arc? if not, bail
i = numberOfRows(xs_path)
if i > 1:
    addMsgAndPrint(f'more than one line in {xs_name} or selected', 2)
    addMsgAndPrint('if your feature class has more than one line in it, select just one before running the tool')
    sys.exit()
elif i == 0:
    addMsgAndPrint(f'OOPS! No lines in {xs_name}', 2)
    sys.exit()

# create an 'UNKNOWN' spatial reference we can use for final outputs
SR = arcpy.FromWKT('POINT EMPTY').spatialReference
SR_str = SR.exportToString()
unknown = arcpy.SpatialReference()
unknown.loadFromString(SR_str)

# make output fds if it doesn't exist
# set output fds spatial reference to unknown
if not arcpy.Exists(out_fds):
    addMsgAndPrint(f'  making feature data set {os.path.basename(out_fds)} in {gdb}')
    arcpy.CreateFeatureDataset_management(gdb, os.path.basename(out_fds), unknown)
    
# make a feature dataset in Default/Scratch gdb
# delete if one already exists. This makes name management easier
xs_sr = spatial_ref = arcpy.Describe(xs_path).spatialReference
scratch_fd = os.path.join(scratch, new_fd)
if arcpy.Exists(scratch_fd):
    addMsgAndPrint(f'  making intermediate feature data set {os.path.basename(scratch_fd)} in {scratch}')
    arcpy.CreateFeatureDataset_management(scratch, os.path.basename(scratch_fd), xs_sr)
    
addMsgAndPrint('  Prepping section line')
# make a copy of the cross section line feature class in default/scratch gdb
# Initially tried to save intermediate files to "memory\" but running Intersect
# on a line in memory produced an empty feature class whereas a copy of the line
# in Default worked fine.
# I think the only reason we make a copy of the cross section line feature class
# is to be able to add a field and write a route_id if necessary without restrictions.
addMsgAndPrint(f'    copying {xs_name} to {scratch_fd}')
arcpy.conversion.FeatureClassToFeatureClass(xs_path, scratch_fd, xs_name)

# find the _ID field of the feature class to use as a route id
temp_xs_line = os.path.join(scratch_fd, xs_name)
temp_fields = [f.name for f in arcpy.ListFields(temp_xs_line)]
check_field = f"{xs_name}_ID"
id_field = next((f for f in temp_fields if f == check_field), None)
id_exists = field_none(temp_xs_line, check_field)

# and if there isn't one, make one. 
if id_field is None or id_exists == False:
    id_field = 'ROUTE_ID'
    arcpy.AddField_management(temp_xs_line, id_field, 'TEXT')
    arcpy.management.CalculateField(temp_xs_line, check_field, "'01'", 'PYTHON3')    
      
## check for Z and M values
xs_dict = fd_dict[xs_name]
if xs_dict['hasZ'] and xs_dict['hasM']:
    zm_line = temp_xs_line
    addMsgAndPrint(f'cross section in {zm_line} already has M and Z values')
else:
    #Add Z values
    addMsgAndPrint(f'    getting elevation values for cross section in {xs_name}')
    z_line = os.path.join(scratch_fd, f"{token}_z")
    arcpy.InterpolateShape_3d(dem, temp_xs_line, z_line)
    
    #Add M values
    addMsgAndPrint(f'    measuring {os.path.basename(z_line)}')
    zm_line = os.path.join(scratch_fd, f"{token}_zm")
    arcpy.CreateRoutes_lr(z_line, id_field, zm_line, 'LENGTH', '#', '#', startQuadrant)
    
    addMsgAndPrint(f"Z and M attributed version of cross section line {token}")
    addMsgAndPrint(f"has been save to {zm_line}")
   
# get lists of feature classes to be projected
line_fcs = []
poly_fcs = []
point_fcs = []
if project_all:
    line_fcs = [v['baseName'] for v in fd_dict.values() if v['shapeType'] == 'Polyline' and v['baseName'] != xs_name]
    poly_fcs = [v['baseName'] for v in fd_dict.values() if v['shapeType'] == 'Polygon' and v['featureType'] != 'Annotation']
    point_fcs = [v['baseName'] for v in fd_dict.values() if v['shapeType'] == 'Point']
else:
    featureClassesToProject = fcToProject.split(';') 
    for fc in featureClassesToProject:
        fc_name = os.path.basename(fc)
        if fd_dict[fc_name]['shapeType'] == 'Polyline':
            line_fcs.append(fc_name)
        if fd_dict[fc_name]['shapeType'] == 'Polygon' and fd_dict[fc_name]['featureType'] != 'Annotation':
            poly_fcs.append(fc_name) 
        if fd_dict[fc_name]['shapeType'] == 'Point':
            point_fcs.append(fc_name)
        
addMsgAndPrint('\n  projecting line feature classes:')
for fc_name in line_fcs:
    fc_path = fd_dict[fc_name]['catalogPath']
    addMsgAndPrint(f'    {fc_path}')

    if fc_name == 'ContactsAndFaults':
        lineCrossingLength = -lineCrossingLength
        
    # 1) intersect fc_name with zm_line to get points where arcs cross section line
    intersect_pts = os.path.join(scratch_fd, f'{fc_name}_intersections')
    arcpy.analysis.Intersect([zm_line, fc_path], intersect_pts, 'ALL', None, 'POINT')    

    if numberOfRows(intersect_pts) == 0:
        addMsgAndPrint(f'      {fc_name} does not intersect section line')
    else:
        # 2) locate the points on the cross section route
        event_props = 'rkey POINT M fmp' 
        event_tbl = locateevent_tbl(intersect_pts, 10, event_props, 'Z_MEAN', True)
        
        # 3) create event layer from the events table
        addMsgAndPrint('      placing events on section line')
        event_lyr = f'{fc_name}_events'
        arcpy.lr.MakeRouteEventLayer(zm_line, id_field, event_tbl, event_props, event_lyr)
        
        # 4) save a copy to the scratch feature 
        # this is still in SR of the original fc
        loc_lines = os.path.join(scratch_fd, f'{fc_name}_located')
        addMsgAndPrint(f'      copying event layer to {loc_lines}')
        arcpy.management.CopyFeatures(event_lyr, loc_lines)   
        
        # 5) make new feature class in output feature dataset using old as template
        out_name = f'{token}_{fc_name}'
        out_path = os.path.join(out_fds, out_name)
        addMsgAndPrint(f'      creating feature class {out_name} in {os.path.basename(out_fds)}')
        testAndDelete(out_path)
        arcpy.management.CreateFeatureclass(out_fds, out_name, 'POLYLINE', loc_lines, 'DISABLED', 'SAME_AS_TEMPLATE', spatial_reference=unknown) 
        addMsgAndPrint('      moving and calculating attributes')
        
        # 6) open search cursor on located events, open insert cursor on out_fc
        # get a list of all fields from the original feature class that do not have the 
        # property required = True. Except that we do want to interrogate and then write
        # to the shape field so add that back on.
        fld_obj = arcpy.ListFields(loc_lines)
        flds = [f.name for f in fld_obj if f.type != 'Geometry']
        flds.append('SHAPE@')
        in_rows = arcpy.da.SearchCursor(loc_lines, flds)
        out_rows = arcpy.da.InsertCursor(out_path, flds)

        oid_name = [f.name for f in fld_obj if f.type == 'OID'][0]
        oid_i = in_rows.fields.index(oid_name)
        
        for in_row in in_rows:
            #try:
            # do the shape
            geom = in_row[-1]
            pnt = geom[0]     
            X = pnt.M
            Y = pnt.Z
            pnt1 = arcpy.Point(X, (Y - lineCrossingLength) * vertEx)
            pnt2 = arcpy.Point(X, Y * vertEx)
            pnt3 = arcpy.Point(X, (Y + lineCrossingLength) * vertEx)
            line_array = arcpy.Array([pnt1, pnt2, pnt3])
            
            # insert new row with attributes of original and newly created
            # line_array as the geometry for SHAPE@
            vals = list(in_row).copy()
            vals[-1] = arcpy.Polyline(line_array)
            out_rows.insertRow(vals)
            # except:
                # addMsgAndPrint(f"could not create feature from objectid {in_row[oid_i]} in {loc_lines}", 1)
            
addMsgAndPrint('\n  projecting point feature classes:')
# buffer line to get selection polygon
if point_fcs:
    addMsgAndPrint(f'    buffering {xs_name} to get selection polygon')
    temp_buffer = os.path.join(scratch_fd, f"{token}_buffer")
    arcpy.Buffer_analysis(zm_line, temp_buffer, buffer_distance, 'FULL', 'FLAT')

# for each input point feature class:
for fc_name in point_fcs:
    fc_path = fd_dict[fc_name]['catalogPath']
    addMsgAndPrint(f'    {fc_path}')
    
    # 1) clip inputfc with selection polygon to make clip_points
    addMsgAndPrint('      clipping with selection polygon')
    clip_points = os.path.join(scratch_fd, f'{fc_name}_{str(int(buffer_distance))}')
    testAndDelete(clip_points)
    arcpy.analysis.Clip(fc_path, temp_buffer, clip_points)
    
    # check to see if nonZero number of rows and not in excluded feature classes
    nPts = numberOfRows(clip_points)
    addMsgAndPrint(f'      {str(nPts)} points within selection polygon')
    if nPts > 0:
        # 2) locate the set of clipped points on the cross section line
        event_props = 'rkey POINT M fmp' 
        event_tbl = locateevent_tbl(clip_points, buffer_distance + 200, event_props, 'Z')
        
        # 3) make an event layer from the event table. "Snaps" points tangentially to the 
        # line of cross section.
        addMsgAndPrint('      placing events on section line')
        event_lyr = f'{fc_name}_events'
        arcpy.lr.MakeRouteEventLayer(zm_line, id_field, event_tbl, event_props, 
                                     event_lyr, '#', '#', 'ANGLE_FIELD', 'TANGENT')
        
        # 4) save a copy to the scratch feature 
        # this is still in SR of the original fc
        loc_points = os.path.join(scratch_fd, f'{fc_name}_located')
        addMsgAndPrint(f'      copying event layer to {loc_points}')
        arcpy.management.CopyFeatures(event_lyr, loc_points)   
        addMsgAndPrint('      adding fields')
        
        # 5) add fields
        # add DistanceFromSection and LocalXsAzimuth
        arcpy.AddField_management(loc_points, 'DistanceFromSection', 'FLOAT')
        arcpy.AddField_management(loc_points, 'LocalCSAzimuth', 'FLOAT')
        
        # with all fields set, collect a list of the names for the cursors below
        # and append the SHAPE@ token
        fld_obj = arcpy.ListFields(loc_points)
        flds = [f.name for f in fld_obj if f.type != 'Geometry']
        flds.append('SHAPE@')
        
        # set isOrientationData
        addMsgAndPrint('      checking for Azimuth and Inclination fields')
        if 'Azimuth' in flds and 'Inclination' in iflds:
            isOrientationData = True
            for n in ('ApparentInclination', 'Obliquity', 'MapAzimuth'):
                arcpy.management.AddField(loc_points, n, 'FLOAT')
                flds.append(n)                         
        else:
            isOrientationData = False
            
        # 6) create empty feature class, with unknown SR, in the original gdb
        out_name = f'{token}_{fc_name}'
        out_path = os.path.join(out_fds, out_name)
        addMsgAndPrint(f'      creating feature class {out_path} in {out_fds}')
        arcpy.management.CreateFeatureclass(out_fds, out_name, 'POINT', loc_points, spatial_reference=unknown)
        
        # 7) swap M for X and Z for Y and other attribute calculations
        addMsgAndPrint('      calculating shapes and attributes')
        in_rows = arcpy.da.SearchCursor(loc_points, flds)
        out_rows = arcpy.da.InsertCursor(out_path, flds)
        
        # the objectid field might not always be named OBJECTID
        # get the right name by interrogating the field type
        # and then find the index of that name in the list of fields
        n = in_rows.fields.index
        oid_name = [f.name for f in fld_obj if f.type == 'OID'][0]
        oid_i = n(oid_name)

        for in_row in in_rows:
            try:
                # get a list of the values from the located points feature class
                vals = list(in_row).copy()
                
                # create the new shape
                geom = in_row[-1]
                pnt = geom[0]     
                X = pnt.M
                if pnt.Z is None:
                    Y = -999
                else:
                    Y = pnt.Z * vertEx
                new_pnt = arcpy.Point(X, Y)
                vals[-1] = new_pnt
                  
                # convert from cartesian to geographic angle
                csAzi = cartesianToGeographic(in_row[n('LOC_ANGLE')])
                vals[n('LocalCSAzimuth')] = csAzi
                vals[n('DistanceFromSection')] = in_row[n('Distance')]
                if isOrientationData:
                    vals[n('MapAzimuth')] = in_row[n('Azimuth')]
                    if isAxial(in_row[n('Type')]):
                        appInc, oblique = apparentPlunge(in_row[n('Azimuth')], in_row[n('Inclination')], csAzi)
                        inclinationDirection = in_row[n('Azimuth')]
                    else:
                        appInc, oblique = apparentDip(in_row[n('Azimuth')], in_row[n('Inclination')], csAzi)
                        inclinationDirection = in_row[n('Azimuth')] + 90
                        if inclinationDirection > 360:
                            inclinationDirection = inclinationDirection - 360
                    plotAzi = plotAzimuth(inclinationDirection, csAzi, appInc)
                    rowObliquity = round(oblique, 2)
                    vals[n('ApparentInclination')] = round(appInc, 2)
                    vals[n('Azimuth')] = round(plotAzi, 2)
       
                out_rows.insertRow(vals)
            except:
                addMsgAndPrint(f"could not create feature from objectid {in_row[oid_i]} in {loc_points}", 1)
        
        # cleanup
        for fld in 'Distance', 'LOC_ANGLE', 'rtID':
            arcpy.management.DeleteField(out_path, fld)
        del in_row, in_rows, out_rows
        
        # clean up
        if not saveIntermediate:
            testAndDelete(scratch_fd)

addMsgAndPrint('\n  projecting polygon feature classes:')
for fc_name in poly_fcs:
    fc_path = fd_dict[fc_name]['catalogPath']
    addMsgAndPrint(f'{fc_name}')
    
    # 1) locate features along routes
    addMsgAndPrint('      making event table')
    event_tbl = os.path.join(os.path.join(scratchws, f'{fc_name}_evtble'))
    addMsgAndPrint(event_tbl)
    testAndDelete(event_tbl)
    event_props = 'rkey LINE FromM ToM' 
    arcpy.lr.LocateFeaturesAlongRoutes(fc_path, zm_line, id_field, '#', event_tbl, event_props)
    
    if numberOfRows(event_tbl) == 0:
        addMsgAndPrint(f'      {fc_name} does not intersect section line')
    else:
        addMsgAndPrint('      placing events on section line')
        # 2) make route event layer
        event_lyr = f'{fc_name}_events'
        arcpy.lr.MakeRouteEventLayer(zm_line, id_field, event_tbl, event_props, event_lyr)
        
        # 3) save a copy to the scratch feature dataset
        # this is still in SR of the original fc
        loc_polys = os.path.join(scratch_fd, f'{fc_name}_located')
        addMsgAndPrint(f'      copying event layer to {loc_polys}')
        arcpy.management.CopyFeatures(event_lyr, loc_polys)   
        
        # 4) create empty feature class, with unknown SR, in the original gdb
        out_name = f'{token}_{fc_name}'
        out_fc = os.path.join(out_fds, out_name)
        addMsgAndPrint(f'      creating feature class {out_name} in {out_fds}')
        testAndDelete(out_fc)
        arcpy.management.CreateFeatureclass(out_fds, out_name, 'POLYLINE', loc_polys, 'DISABLED', 'SAME_AS_TEMPLATE', spatial_reference=unknown)

        # 5) create the new features 
        addMsgAndPrint('      moving and calculating attributes')
        
        # get field names
        # but exclude Shape and shape_length
        fld_obj = arcpy.ListFields(loc_polys)
        flds = [f.name for f in fld_obj if f.type != 'Geometry' and f.name.lower() != 'shape_length']
        flds.append('SHAPE@')
        in_rows = arcpy.da.SearchCursor(loc_polys, flds)
        outRows = arcpy.da.InsertCursor(out_fc, flds)
        
        ## open search cursor on loc_polys, open insert cursor on out_fc
        in_rows = arcpy.da.SearchCursor(loc_polys, flds)
        out_rows = arcpy.da.InsertCursor(out_fc, flds)
        
        # the objectid field might not always be named OBJECTID
        # get the right name by interrogating the field type
        # and then find the index of that name in the list of fields
        n = in_rows.fields.index
        oid_name = [f.name for f in fld_obj if f.type == 'OID'][0]
        oid_i = n(oid_name)
        for in_row in in_rows:
            try:
                vals = list(in_row).copy()

                # flip shape
                array = []
                for part in in_row[-1]:
                    for pnt in part:
                        X = float(pnt.M)
                        Y = float(pnt.Z) * vertEx
                        array.append((X,Y))
                vals[-1] = array       
                out_rows.insertRow(vals)
            except:
                addMsgAndPrint(f"could not create feature from objectid {in_row[oid_i]} in {loc_polys}", 1)
sys.exit()

arcpy.CheckInExtension('3D')
if not saveIntermediate:
    addMsgAndPrint('\n  deleting intermediate data sets')
    testAndDelete(scratch_fd)
else:
    addMsgAndPrint(f'intermdeiate data saved in {scratch_fd}')
    
# make GeMS cross-section feature classes if they are not present in output FDS
for fc in ('MapUnitPolys', 'ContactsAndFaults', 'OrientationPoints'):
    fclass = f'{token}_{fc}'
    if not arcpy.Exists(os.path.join(out_fds, fclass)):
        addMsgAndPrint(f'  making empty feature class {fclass}')
        fieldDefs = tableDict[fc]
        fieldDefs[0][0] = f'{fclass}_ID'
        if fc == 'MapUnitPolys':
            shp = 'POLYGON'
        elif fc == 'ContactsAndFaults':
            shp = 'POLYLINE'
            if addLTYPE: 
                fieldDefs.append(['LTYPE', 'String', 'NullsOK', 50])
        elif fc == 'OrientationPoints':
            shp = 'POINT'
            if addLTYPE:
                fieldDefs.append(['PTTYPE', 'String', 'NullsOK', 50]) 
        createFeatureClass(gdb, os.path.basename(out_fds), fclass, shp, fieldDefs)

addMsgAndPrint('\n \nfinished successfully.')
if forceExit:
    addMsgAndPrint('forcing exit by raising ExecuteError')
    raise arcpy.ExecuteError


