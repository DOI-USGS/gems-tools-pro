"""
Projects coordinates of a point feature class onto a cross-section plane.
Goal is to create a minimally-attributed feature class that can be joined with the source feature class
to have a full set of attributes. 

* Inputs are DEM and point feature class; must specify which CrossSection feature
dataset output will be written to, as well as name of output feature class.

* If output feature class exists, it will be overwritten.

* Allows for vertical exaggeration.

Inputs:
    SectionLine featureclass
    SectionLine Label value
    point featureclass
    DEM
    vertical exaggeration
    MaxDistanceFromSectionPlane
    Output feature dataset
    Output featureclass

Adds Elevation attribute to point featureclass, if it is not present
Calculates values of Elevation attribute

Attributes of output features are
    _IDs of input features, stored in <OutPutFeatureClassName>ID
    DistanceFromSection  (+ = toward viewer, - = away from viewer, GeologicMap units)
    If Orientation data:  (all values in degrees)
      ApparentInclination    
      Obliquity (of strike or of plunge-normal direction: 90 = at right angle, 0 = parallel)
      PlotAzimuth --assumes right-hand rule, unrotated symbols have
                    North strike/trend, and symbol rotation is geographic
"""

import arcpy, sys, os, os.path, math

versionString = 'GeMS_ProjectPtsToCrossSection_Arc10.py, version of 2 September 2017'

debug = False

def addMsgAndPrint(msg, severity=0): 
    # prints msg to screen and adds msg to the geoprocessor (in case this is run as a tool) 
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

addMsgAndPrint('  '+versionString)

if debug:
  for i in range(0,len(sys.argv)):
    addMsgAndPrint(str(i)+' '+str(sys.argv[i]))

sectionLineClass = sys.argv[1]
sectionLineLabelValue = sys.argv[2]
pointClass = sys.argv[3]
idField = sys.argv[4]
vertEx = float(sys.argv[5])
DEM = sys.argv[6]
maxDistance = sys.argv[7]
outWorkspace = sys.argv[8]
outFeatureClass = sys.argv[9]
if sys.argv[10] <> '#':
    tempWorkspace = sys.argv[10]
else:
    tempWorkspace = outWorkspace
 
tempBuff =  tempWorkspace+'/xxx1'  # temporary Poly fc created by Buffer
tempPoints = tempWorkspace+'/xxx2' # temporary Point fc created by Clip
secLine = 'xxx3'
secLinePts = tempWorkspace+'/xxx4'

if debug:
    addMsgAndPrint('idField='+str(idField))
    addMsgAndPrint('vertEx='+str(vertEx))
    addMsgAndPrint('DEM='+str(DEM))
    addMsgAndPrint('maxDistance='+str(maxDistance))

def xyTheta(x,y):
    if x <> 0.0:
        theta = math.degrees(math.atan(y/x))
    elif y > 0:
        theta = 90.0
    else:
        theta = 270.0
    if x < 0:
        theta = theta + 180
    if theta > 360:
        theta = theta - 360.0
    if theta < 0:
        theta = theta + 360
    return theta

def rThetaXY(r,theta):
    th = math.radians(theta)
    x = r*math.cos(th)
    y = r*math.sin(th)
    return x,y
          
def isAxial(ptType):
    m = False
    for s in ('axis','lineation',' L'):
        if ptType.upper().find(s.upper()) > -1:
            m = True
    return m

def obliq(theta1,theta2):
    obl = abs(theta1-theta2)
    if obl > 180:
        obl = obl-180
    if obl > 90:
        obl = 180 - obl
    return obl

def plotAzimuth(azi, thetaXS, apparentInclination):
    appAzi = 90-azi-thetaXS
    while appAzi < 0:
        appAzi = appAzi + 360
    if appAzi <= 180:
        plotAzimuth = 270 + apparentInclination
    else:
        plotAzimuth = 270 - apparentInclination
    return plotAzimuth

def apparentPlunge(azi,inc,thetaXS):
    obliquity = obliq(90-azi,thetaXS)  # 90-azi to convert from geologic to cartesian angle
    appInc = math.degrees(math.atan(vertEx * math.tan(math.radians(inc)) * math.cos(math.radians(obliquity))))
    return appInc,obliquity

def apparentDip(azi,inc,thetaXS):
    obliquity = obliq(90-azi,thetaXS) # 90-azi to convert from geologic to cartesian angle
    appInc = math.degrees(math.atan(vertEx * math.tan(math.radians(inc)) * math.sin(math.radians(obliquity))))
    return appInc,obliquity

def delArcStuff(deleteSet):
    for arcStuff in deleteSet:
        if arcpy.Exists(arcStuff):
            arcpy.Delete_management(arcStuff)

#####################

# check that 3D Analyst license is available
addMsgAndPrint('  checking for 3D Analyst license')
try:
    if arcpy.CheckExtension("3D") == "Available":
        arcpy.CheckOutExtension("3D")
    else:
        addMsgAndPrint('  No 3D Analyst license available!')
        sys.exit()
except:
    addMsgAndPrint('  Failed to check out 3D Analyst license')
    sys.exit()

## clean up any existing temporary or output entitites
delArcStuff( (tempBuff,tempPoints,secLinePts,outWorkspace+'/'+outFeatureClass) )

addMsgAndPrint('  getting cross-section line')
# make feature layer that contains single line from sectionline featureclass
whereExpr = '"Label" =\'%s\'' % sectionLineLabelValue
arcpy.MakeFeatureLayer_management(sectionLineClass,secLine,whereExpr)

# create subset of points within maxDistance of section line
arcpy.Buffer_analysis (secLine, tempBuff, maxDistance)
arcpy.Clip_analysis (pointClass, tempBuff, tempPoints)

addMsgAndPrint('  adding Z and XY to points')
# Add Z to subset of points
arcpy.AddSurfaceInformation_3d (tempPoints, DEM, 'Z', 'LINEAR')
# return 3D analyst license
arcpy.CheckInExtension("3D")
# Add XY values to subset of points
arcpy.AddXY_management(tempPoints)

addMsgAndPrint('  getting section line endpoints')
# Get coordinates of section line endpoints
### this is probably a r-e-a-l-l-l-ly clumsy way to do so
arcpy.FeatureVerticesToPoints_management(secLine,secLinePts,'BOTH_ENDS')
arcpy.AddXY_management(secLinePts)
pts = []
rows = arcpy.SearchCursor(secLinePts)
for row in rows:
    pts.append([row.POINT_X,row.POINT_Y])
startX = pts[0][0]
startY = pts[0][1]
endX = pts[1][0]
endY = pts[1][1]

thetaXS = xyTheta(endX-startX,endY-startY)

addMsgAndPrint('  getting field names')
fieldNames = []
fields = arcpy.ListFields(tempPoints)
for field in fields:
    fieldNames.append(field.name)
    ## Note: this may reset the idField as set in the tool interface
    if field.name == idField:
        idFieldType = field.type
    if field.name.find('_ID') > 0:
        idField = field.name
        idFieldType = field.type
if 'Azimuth' in fieldNames:
    isOrientationData = True
else:
    isOrientationData = False
idField2 = idField.replace('_','')

addMsgAndPrint('  making new feature class')
# make output feature class
arcpy.CreateFeatureclass_management(outWorkspace,outFeatureClass,'POINT')
newFC = outWorkspace+'/'+outFeatureClass
# add basic fields
arcpy.AddField_management(newFC,outFeatureClass+'_ID','TEXT','','',50)
arcpy.AddField_management(newFC,idField2,idFieldType,'','',50)
arcpy.AddField_management(newFC,'DistanceFromSection','FLOAT')
# If isOrientationData, add some more fields
if isOrientationData:
    arcpy.AddField_management(newFC,'Obliquity','FLOAT')
    arcpy.AddField_management(newFC,'ApparentInclination','FLOAT')
    arcpy.AddField_management(newFC,'PlotAzimuth','FLOAT')

### NOW, step through points

addMsgAndPrint('  stepping through points:')
addMsgAndPrint('    translating, rotating, collapsing, calculating')
newPoints = arcpy.InsertCursor(newFC)
points = arcpy.SearchCursor(tempPoints)
nProjected = 0
for pt in points:
    if str(pt.Z) == 'None':
        addMsgAndPrint('Skipping '+idField+'='+str(pt.getValue(idField))+'. No Z value, probably outside DEM.')
    else:
        x = pt.Point_X - startX
        y = pt.Point_Y - startY
        r = math.sqrt(x*x + y*y)
        theta = thetaXS - xyTheta(x,y)
        newX,distFromXS = rThetaXY(r,theta)
        newY = pt.Z * vertEx
        ptID = pt.getValue(idField)
        if isOrientationData:
            if isAxial(pt.Type):
                appInc,oblique = apparentPlunge(pt.Azimuth,pt.Inclination,thetaXS)
            else: # is planar feature
                appInc,oblique = apparentDip(pt.Azimuth,pt.Inclination,thetaXS)
            plotAzi = plotAzimuth(pt.Azimuth,thetaXS,appInc)
            #print 'Inc',pt.Inclination, 'Obliquity',int(round(oblique), 'ApparentDip',int(round(appInc))
            #print int(round(thetaXS)), int(pt.Azimuth), int(round(plotAzi))
            #print
        # create new point at newX,newY with attributes _ID, ptID (stored in field idField without '_'), distFromXS
        pnt = arcpy.Point()
        pnt.X = newX
        pnt.Y = newY
        newPoint = newPoints.newRow()
        newPoint.shape = pnt
        newPoint.setValue(idField2,ptID)
        newPoint.DistanceFromSection = distFromXS
        if isOrientationData:
            newPoint.Obliquity = round(oblique,2)
            newPoint.ApparentInclination = round(appInc,2)
            newPoint.PlotAzimuth = round(plotAzi,2)
        newPoints.insertRow(newPoint)
        nProjected = nProjected+1

addMsgAndPrint('  Projected '+str(nProjected)+' points.')
               
delArcStuff( (tempBuff,tempPoints,secLinePts) )
del newPoint
del newPoints
del pt
del points




 
