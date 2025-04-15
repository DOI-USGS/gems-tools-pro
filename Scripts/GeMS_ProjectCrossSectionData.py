"""
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
"""

# 10 June 2019: Updated to work with Python 3 in ArcGIS Pro. -Evan Thoms
# Ran script through 2to3 and it work754ed with no other edits necessary.
# Consider re-writing some sections to work with new Python modules, but none of the
# 'older' code causes any errors.

# extensive edits in March and April 2022 - ET. Updated to data access cursors, new f string formatting,
# management of intermediate feature classes in the Default.gdb (which might be problem if the script is ever run
# from the console or another script).

import arcpy, sys, os, math
from GeMS_Definition import tableDict
import GeMS_utilityFunctions as guf

versionString = "GeMS_ProjectCrossSectionData_Arc10.py, version of 20 April 2022"
rawurl = "https://raw.githubusercontent.com/usgs/gems-tools-pro/master/Scripts/GeMS_ProjectCrossSectionData_AGP2.py"
guf.checkVersion(versionString, rawurl, "gems-tools-pro")

##inputs
#  gdb          geodatabase with GeologicMap feature dataset to be projected
#  project_all
#  fcToProject
#  dem
#  xs_path       cross-section line: _single-line_ feature class or layer
#  startQuadrant start quadrant (NE, SE, SW, NW)
#  token   output feature dataset. Input value is appended to 'CrossSection', pre-prended (CS{token})to feature classes.
#  vert_ex       vertical exaggeration; a number
#  buffer_distance  a number
#  forcExit
#  scratchWS
#  saveIntermediate (boolean)

lineCrossingLength = (
    500  # length (in map units) of vertical line drawn where arcs cross section line
)
exemptedPrefixes = (
    "errors_",
    "ed_",
)  # prefixes that flag a feature class as not to be projected

transDict = {
    "String": "TEXT",
    "Single": "FLOAT",
    "Double": "DOUBLE",
    "NoNulls": "NON_NULLABLE",
    "NullsOK": "NULLABLE",
    "Date": "DATE",
}

# idRootDict comes from GeMS_relID_AGP2.py
idRootDict = {
    "CartographicLines": "CAL",
    "ContactsAndFaults": "CAF",
    "CMULines": "CMULIN",
    "CMUMapUnitPolys": "CMUMUP",
    "CMUPoints": "CMUPNT",
    "CMUText": "CMUTXT",
    "DataSources": "DAS",
    "DataSourcePolys": "DSP",
    "DescriptionOfMapUnits": "DMU",
    "ExtendedAttributes": "EXA",
    "FossilPoints": "FSP",
    "GenericPoints": "GNP",
    "GenericSamples": "GNS",
    "GeochemPoints": "GCM",
    "GeochronPoints": "GCR",
    "GeologicEvents": "GEE",
    "GeologicLines": "GEL",
    "Glossary": "GLO",
    "IsoValueLines": "IVL",
    "MapUnitPoints": "MPT",
    "MapUnitPolys": "MUP",
    "MapUnitOverlayPolys": "MUO",
    "MiscellaneousMapInformation": "MMI",
    "OrientationPoints": "ORP",
    "OtherLines": "OTL",
    "OverlayPolys": "OVP",
    "PhotoPoints": "PHP",
    "RepurposedSymbols": "RPS",
    "Stations": "STA",
    "StandardLithology": "STL",
    "MapUnitPointAnno24k": "ANO",
}

##### UTILITY FUNCTIONS ############################


def cartesianToGeographic(angle):
    ctg = -90 - angle
    if ctg < 0:
        ctg = ctg + 360
    return ctg


def isAxial(ptType):
    m = False
    for s in ("axis", "lineation", " L"):
        if ptType.upper().find(s.upper()) > -1:
            m = True
    return m


def obliq(b1, b2):
    # from old Cross Section tool
    return 180 - abs(abs(b1 - b2) - 180)


def symbol_rotation(inclination_direction, local_xs_azi, app_inc_VE):
    # results in a rotation angle that can be used with geographic rotation
    # of symbols in cross-section view.
    azDiff = obliq(local_xs_azi, inclination_direction)
    if azDiff >= 0 and azDiff <= 90:
        return 90 + app_inc_VE
    else:
        return 270 - app_inc_VE


def apparentPlunge(azi, inc, thetaXS):
    obliquity = obliq(azi, thetaXS)
    appInc = math.degrees(
        math.atan(
            vert_ex * math.tan(math.radians(inc)) * math.cos(math.radians(obliquity))
        )
    )
    return appInc, obliquity


def apparentDip(azi, inc, cs_azi):
    # From older Cross Section tool,
    alpha = obliq(azi, cs_azi)
    complement = 180 - alpha
    if alpha < complement:
        obliquity = alpha
    else:
        obliquity = complement

    # appIncVE for debugging
    # APPARENT PLUNGE - change 'math.sin' of last term to math.cos, eg
    # appInc = math.degrees(math.atan(vertEx * math.tan(math.radians(inc)) *
    # math.cos(math.radians(obliquity)))
    appIncVE = math.degrees(
        math.atan(
            vert_ex * math.tan(math.radians(inc)) * math.sin(math.radians(obliquity))
        )
    )
    appInc = math.degrees(
        math.atan(math.tan(math.radians(inc)) * math.sin(math.radians(obliquity)))
    )
    return appInc, appIncVE, obliquity


#  copied from NCGMP09v1.1_CreateDatabase_Arc10.0.py, version of 20 September 2012
def createFeatureClass(thisDB, featureDataSet, featureClass, shapeType, fieldDefs):
    try:
        arcpy.env.workspace = thisDB
        arcpy.CreateFeatureclass_management(featureDataSet, featureClass, shapeType)
        thisFC = os.path.join(thisDB, featureDataSet, featureClass)
        for fDef in fieldDefs:
            try:
                if fDef[1] == "String":
                    arcpy.management.AddField(
                        thisFC,
                        fDef[0],
                        transDict[fDef[1]],
                        "#",
                        "#",
                        fDef[3],
                        "#",
                        transDict[fDef[2]],
                    )
                else:
                    arcpy.management.AddField(
                        thisFC,
                        fDef[0],
                        transDict[fDef[1]],
                        "#",
                        "#",
                        "#",
                        "#",
                        transDict[fDef[2]],
                    )
            except:
                guf.addMsgAndPrint(
                    "failed to add field "
                    + fDef[0]
                    + " to feature class "
                    + featureClass
                )
                guf.addMsgAndPrint(arcpy.GetMessages(2))
    except:
        guf.addMsgAndPrint(arcpy.GetMessages())
        guf.addMsgAndPrint(
            "failed to create feature class "
            + featureClass
            + " in dataset "
            + featureDataSet
        )


# def locateevent_tbl(gdb, fc_name, pts, dem, sel_distance, event_props, zType, isLines = False):


def locateevent_tbl(pts, sel_distance, event_props, z_type, is_lines=False):
    desc = arcpy.da.Describe(pts)

    if not desc["hasZ"]:
        guf.addMsgAndPrint("adding Z values")
        arcpy.ddd.AddSurfaceInformation(pts, dem, z_type, "LINEAR")

    # working around duplicate features in LocateFeaturesAlongRoutes
    # add special field for duplicate detection
    # possibly explained here:
    # https://community.esri.com/t5/geoprocessing-questions/locate-features-along-route-returns-duplicate/td-p/229422
    dupDetectField = "xDupDetect"
    arcpy.management.AddField(pts, dupDetectField, "LONG")

    # and calc this field = OBJECTID
    OID = arcpy.Describe(pts).OIDFieldName
    expr = f"'{OID}'"
    arcpy.management.CalculateField(pts, dupDetectField, expr, "PYTHON3")

    # locate line_pts along route
    guf.addMsgAndPrint("making event table")
    event_tbl = os.path.join(scratch, f"CS{token}{fc_name}_evtbl")
    guf.testAndDelete(event_tbl)
    arcpy.lr.LocateFeaturesAlongRoutes(
        pts, zm_line, id_field, sel_distance, event_tbl, event_props
    )
    nRows = guf.numberOfRows(event_tbl)
    nPts = guf.numberOfRows(pts)
    if (
        nRows > nPts and not is_lines
    ):  # if LocateFeaturesAlongRoutes has made duplicates
        guf.addMsgAndPrint("removing duplicate entries in event table")
        arcpy.management.DeleteIdentical(event_tbl, dupDetectField)
    arcpy.management.DeleteField(event_tbl, dupDetectField)
    return event_tbl


def field_none(fc, field):
    try:
        with arcpy.da.SearchCursor(fc, field) as rows:
            if rows.next()[0] in [None, ""]:
                return False
            else:
                return True
    except:
        return False


def round2int(x, base):
    return base * round(x / base)


def alter_id(fc_name, field_names, xs_fc_path):
    # when a map fc has been translated to a xs fc,
    # it still carries the original GeMS primary _ID field, which
    # needs to be changed to a GeMS foreign key that just ends in ID
    # orig_name needs to be {feature class}_ID
    orig_name = f"{fc_name}_ID"
    if orig_name in field_names:
        new_name = orig_name.replace("_ID", "ID")
        # AlterField(path, field name to be changed, new name, new alias)
        arcpy.management.AlterField(xs_fc_path, orig_name, new_name, new_name)


def add_id(out_name, field_names, out_path, fc_name):
    # add a suitable _ID primary field and work out
    # a prefix to prepend to _ID values
    id_name = f"{out_name}_id"
    if not id_name in field_names:
        arcpy.management.AddField(out_path, id_name, "TEXT", field_length=50)

    if fc_name in idRootDict:
        pref = f"CS{token}{idRootDict[fc_name]}"
    else:
        letters = []
        for s in out_name:
            if s.isalpha():
                if s.isupper():
                    letters.append(s)

        if letters:
            pref = "".join(letters)
        else:
            pref = out_name[len(token) + 1 : len(token) + 4]

    return id_name, pref


###############################################################
guf.addMsgAndPrint(f"{versionString}")

nulls = ["", "#", None, 0, "0"]
trues = [True, "True", "true"]

gdb = sys.argv[1]
project_all = True if sys.argv[2] in trues else False
fcToProject = sys.argv[3]
dem = sys.argv[4]
xs_path = sys.argv[5]
startQuadrant = sys.argv[6]
token = sys.argv[7]
vert_ex = 1 if sys.argv[8] in nulls else int(sys.argv[8])
buffer_distance = 1000 if sys.argv[9] in nulls else int(sys.argv[9])
scratchws = sys.argv[10]

if arcpy.Exists(scratchws):
    scratch = scratchws
else:
    scratch = arcpy.mp.ArcGISProject("CURRENT").defaultGeodatabase
guf.addMsgAndPrint(f"intermediate data directory is {scratch}")

saveIntermediate = True if sys.argv[11] in trues else False
# EXTRAS
add_profile = True if sys.argv[12] in trues else False
add_frame = True if sys.argv[13] in trues else False
height = 0 if sys.argv[14] in nulls else int(sys.argv[14])
depth = 0 if sys.argv[15] in nulls else int(sys.argv[15])
x_int = 0 if sys.argv[16] in nulls else int(sys.argv[16])
y_int = 0 if sys.argv[17] in nulls else int(sys.argv[17])

try:
    arcpy.CheckOutExtension("3D")
except:
    arcpy.AddError("Extension not found!")
    guf.addMsgAndPrint("Cannot check out 3D-analyst extension.")
    sys.exit()

arcpy.env.overwriteOutput = True

# Checking section line
guf.addMsgAndPrint("checking section line")
# does xs_path have 1-and-only-1 arc? if not, bail
# can this be added to the validation class?
i = guf.numberOfRows(xs_path)
if i > 1:
    guf.addMsgAndPrint(f"more than one line in {xs_path} or selected", 2)
    guf.addMsgAndPrint(
        "if your feature class has more than one line in it, select just one before running the tool"
    )
    sys.exit()
elif i == 0:
    guf.addMsgAndPrint(f"OOPS! No lines in {xs_path}", 2)
    sys.exit()

# create an 'UNKNOWN' spatial reference we can use for final outputs
SR = arcpy.FromWKT("POINT EMPTY").spatialReference
SR_str = SR.exportToString()
unknown = arcpy.SpatialReference()
unknown.loadFromString(SR_str)

# make feature dataset in input GDB for final outputs
# set output fds in input GDB spatial reference to unknown
new_fd = f"CrossSection{token}"
out_fds = os.path.join(gdb, new_fd)
if not arcpy.Exists(out_fds):
    guf.addMsgAndPrint(
        f"making final output feature data set {os.path.basename(out_fds)} in {gdb}"
    )
    arcpy.CreateFeatureDataset_management(gdb, os.path.basename(out_fds), unknown)

# make a feature dataset in Default/Scratch gdb for intermediate outputs
# delete if one already exists. This makes name management easier
scratch_fd = os.path.join(scratch, new_fd)
if arcpy.Exists(scratch_fd):
    guf.testAndDelete(scratch_fd)
xs_sr = arcpy.da.Describe(xs_path)["spatialReference"]
guf.addMsgAndPrint(
    f"making intermediate feature data set {os.path.basename(scratch_fd)} in {scratch_fd}"
)
arcpy.CreateFeatureDataset_management(scratch, os.path.basename(scratch_fd), xs_sr)

guf.addMsgAndPrint("Prepping section line")
# make a copy of the cross section line feature class in default/scratch gdb
# Initially tried to save intermediate files to "memory\" but running Intersect
# on a line in memory produced an empty feature class whereas a copy of the line
# in Default worked fine.
# I think the only reason we make a copy of the cross section line feature class
# is to be able to add a field and write a route_id if necessary without restrictions.
xs_name = os.path.basename(xs_path)
guf.addMsgAndPrint(f"copying {xs_name} to {scratch_fd}")
xs_copy = f"CS{token}_{xs_name}"
arcpy.conversion.FeatureClassToFeatureClass(xs_path, scratch_fd, xs_copy)

# find the _ID field of the feature class to use as a route id
copy_xs_path = os.path.join(scratch_fd, xs_copy)
temp_fields = [f.name for f in arcpy.ListFields(copy_xs_path)]
check_field = f"{xs_name}_ID"
id_field = next((f for f in temp_fields if f == check_field), None)
id_exists = field_none(copy_xs_path, check_field)

# and if there isn't one, make one.
if id_field is None or id_exists == False:
    id_field = "ROUTEID"
    arcpy.AddField_management(copy_xs_path, id_field, "TEXT")
    arcpy.management.CalculateField(copy_xs_path, id_field, "'01'", "PYTHON3")

# check for Z and M values
# desc = arcpy.da.Describe(xs_path)
# hasZ = desc["hasZ"]
# hasM = desc["hasM"]

# if hasZ and hasM:
#     zm_line = copy_xs_path
#     guf.addMsgAndPrint(f"cross section in {zm_line} already has M and Z values")
# else:
# add Z values
guf.addMsgAndPrint(f"getting elevation values for cross section in CS{token}_{xs_name}")
z_line = os.path.join(scratch_fd, f"CS{token}_z")
arcpy.InterpolateShape_3d(dem, copy_xs_path, z_line)

# add M values
guf.addMsgAndPrint(f"measuring {os.path.basename(z_line)}")
zm_line = os.path.join(scratch_fd, f"CS{token}_zm")
arcpy.CreateRoutes_lr(z_line, id_field, zm_line, "LENGTH", "#", "#", startQuadrant)

guf.addMsgAndPrint(
    f"""Z and M attributed version of cross section line CS{token} 
                    has been saved to {os.path.basename(zm_line)}"""
)

# get lists of feature classes to be projected
line_fcs = []
poly_fcs = []
point_fcs = []
if project_all:
    in_fds = os.path.join(gdb, "GeologicMap")
    guf.addMsgAndPrint(f"building a dictionary of the contents of {in_fds}")
    fd_dict = guf.gdb_object_dict(in_fds)

    # remove any feature classes from dictionary beginning with the exemptedPrefixes
    # use list(dict.keys() in the for loop instead of k in fd_dict
    # because you can't change the size of a dictionary during iteration
    for k, v in list(fd_dict.items()):
        if any(k.startswith(pref) for pref in exemptedPrefixes):
            del fd_dict[k]

        # also remove anything that is not a feature class
        if v["dataElementType"] != "DEFeatureClass":
            del fd_dict[k]

    line_fcs = [
        v["catalogPath"]
        for v in fd_dict.values()
        if v["shapeType"] == "Polyline" and v["baseName"] != xs_name
    ]
    poly_fcs = [
        v["catalogPath"]
        for v in fd_dict.values()
        if v["shapeType"] == "Polygon" and v["featureType"] != "Annotation"
    ]
    point_fcs = [
        v["catalogPath"] for v in fd_dict.values() if v["shapeType"] == "Point"
    ]
else:
    featureClassesToProject = fcToProject.split(";")
    for fc in featureClassesToProject:
        desc = arcpy.da.Describe(fc)
        fc_name = os.path.basename(fc)
        if desc["shapeType"] == "Polyline":
            line_fcs.append(desc["catalogPath"])
        if desc["shapeType"] == "Polygon" and desc["featureType"] != "Annotation":
            poly_fcs.append(desc["catalogPath"])
        if desc["shapeType"] == "Point":
            point_fcs.append(desc["catalogPath"])
### LINES
if line_fcs:
    guf.addMsgAndPrint("projecting line feature classes:")
for fc_path in line_fcs:
    fc_name = os.path.basename(fc_path)
    guf.addMsgAndPrint(f"{fc_name}")

    # intersect fc_name with zm_line to get points where arcs cross section line
    intersect_pts = os.path.join(scratch_fd, f"CS{token}{fc_name}_intersections")
    arcpy.analysis.Intersect([zm_line, fc_path], intersect_pts, "ALL", None, "POINT")

    if guf.numberOfRows(intersect_pts) == 0:
        guf.addMsgAndPrint(f"{fc_name} does not intersect section line")
    else:
        # locate the points on the cross section route
        event_props = "rkey POINT M fmp"
        event_tbl = locateevent_tbl(intersect_pts, 10, event_props, "Z_MEAN", True)

        # create event layer from the events table
        guf.addMsgAndPrint("placing events on section line")
        event_lyr = f"CS{token}{fc_name}_events"
        arcpy.lr.MakeRouteEventLayer(
            zm_line, id_field, event_tbl, event_props, event_lyr
        )

        # save a copy to the scratch feature
        # this is still in SR of the original fc
        loc_lines = os.path.join(scratch_fd, f"CS{token}{fc_name}_located")
        guf.addMsgAndPrint("copying point event layer")
        arcpy.management.CopyFeatures(event_lyr, loc_lines)

        # make new feature class in output feature dataset using old as template
        out_name = f"CS{token}_{fc_name}"
        out_path = os.path.join(out_fds, out_name)
        guf.addMsgAndPrint(
            f"creating feature class {out_name} in {os.path.basename(out_fds)}"
        )
        guf.testAndDelete(out_path)
        arcpy.management.CreateFeatureclass(
            out_fds,
            out_name,
            "POLYLINE",
            loc_lines,
            "DISABLED",
            "SAME_AS_TEMPLATE",
            spatial_reference=unknown,
        )

        # open search cursor on located events, open insert cursor on out_path
        # get a list of all fields from the original feature class that do not have the
        # property required = True. Except that we do want to interrogate and then write
        # to the shape field so add that back on.
        fld_obj = arcpy.ListFields(loc_lines)
        flds = [f.name for f in fld_obj if f.type != "Geometry"]
        flds.append("SHAPE@")

        # add a GeMS-style primary key named {out_name}_ID
        gems_id, id_pref = add_id(out_name, flds, out_path, fc_name)

        # prepare the cursors
        # for in_rows, use flds as listed based on the template feature class
        in_rows = arcpy.da.SearchCursor(loc_lines, flds)

        # but for out_rows, append a {out_name}_ID field
        flds.append(gems_id)
        out_rows = arcpy.da.InsertCursor(out_path, flds)

        # get the index of the objectid field
        oid_name = [f.name for f in fld_obj if f.type == "OID"][0]
        oid_i = in_rows.fields.index(oid_name)

        # initialize an integer counter for appending to the gems-style prefix
        # returned by add_id above
        i = 0
        guf.addMsgAndPrint("creating new features and moving attributes")
        for in_row in in_rows:
            i = i + 1
            # do the shape
            geom = in_row[-1]
            pnt = geom[0]
            X = pnt.M
            Y = pnt.Z
            array = []
            array.append((X, Y * vert_ex))
            array.append((X, (Y + lineCrossingLength) * vert_ex))
            vals = list(in_row).copy()

            # gems_id was added to flds before insert cursor on out_path
            # so extend vals one more index to make room for the _ID value
            vals.append("")

            # SHAPE@ token is second to last item
            vals[-2] = array

            # {out_name}_ID is last item
            vals[-1] = f"{id_pref}{i}"
            try:
                out_rows.insertRow(vals)
            except Exception as e:
                guf.addMsgAndPrint(
                    f"could not create feature from objectid {in_row[oid_i]} in {loc_lines}",
                    1,
                )
                guf.addMsgAndPrint(e)

        # change _ID field to ID field
        alter_id(fc_name, flds, out_path)

### POINTS
# buffer line to get selection polygon
if point_fcs:
    guf.addMsgAndPrint("projecting point feature classes:")
    # guf.addMsgAndPrint(f'buffering {xs_name} to get selection polygon')
    temp_buffer = os.path.join(scratch_fd, f"CS{token}_buffer")
    guf.testAndDelete(temp_buffer)
    arcpy.Buffer_analysis(zm_line, temp_buffer, buffer_distance, "FULL", "FLAT")

# for each input point feature class:
for fc_path in point_fcs:
    fc_name = os.path.basename(fc_path)
    guf.addMsgAndPrint(f"{fc_name}")

    # clip inputfc with selection polygon to make clip_points
    guf.addMsgAndPrint("clipping with selection polygon")
    clip_points = os.path.join(scratch_fd, f"{fc_name}_{str(int(buffer_distance))}")
    guf.testAndDelete(clip_points)
    arcpy.AddMessage(f"fc_path = {fc_path}")
    arcpy.AddMessage(f"temp_buffer = {temp_buffer}")
    arcpy.AddMessage(f"clip_points = {clip_points}")
    arcpy.analysis.Clip(fc_path, temp_buffer, clip_points)

    # check to see if nonZero number of rows and not in excluded feature classes
    nPts = guf.numberOfRows(clip_points)
    guf.addMsgAndPrint(f"{str(nPts)} points within selection polygon")
    if nPts > 0:
        # locate the set of clipped points on the cross section line
        event_props = "rkey POINT M fmp"
        event_tbl = locateevent_tbl(
            clip_points, buffer_distance + 200, event_props, "Z"
        )

        # make an event layer from the event table. "Snaps" points tangentially to the
        # line of cross section.
        guf.addMsgAndPrint("placing events on section line")
        event_lyr = f"CS{token}{fc_name}_events"
        arcpy.lr.MakeRouteEventLayer(
            zm_line,
            id_field,
            event_tbl,
            event_props,
            event_lyr,
            "#",
            "#",
            "ANGLE_FIELD",
            "TANGENT",
        )

        # save a copy to the scratch feature
        # this is still in SR of the original fc
        loc_points = os.path.join(scratch_fd, f"CS{token}{fc_name}_located")
        guf.addMsgAndPrint("copying event layer ")
        arcpy.management.CopyFeatures(event_lyr, loc_points)
        guf.addMsgAndPrint("adding fields")

        # add fields
        # add DistanceFromSection and LocalXsAzimuth
        arcpy.AddField_management(loc_points, "DistanceFromSection", "FLOAT")
        arcpy.AddField_management(loc_points, "LocalCSAzimuth", "FLOAT")

        # with all fields set, collect a list of the names for the cursors below
        fld_obj = arcpy.ListFields(loc_points)
        flds = [f.name for f in fld_obj if f.type != "Geometry"]

        # set isOrientationData
        guf.addMsgAndPrint("checking for Azimuth and Inclination fields")
        if "Azimuth" in flds and "Inclination" in flds:
            isOrientationData = True
            for n in (
                "DipDirection",
                "ApparentInclination",
                "ApparentInclinationVE",
                "Obliquity",
                "PlotRotation",
            ):
                arcpy.management.AddField(loc_points, n, "FLOAT")
                flds.append(n)
        else:
            isOrientationData = False

        # create empty feature class, with unknown SR, in the original gdb
        out_name = f"CS{token}_{fc_name}"
        out_path = os.path.join(out_fds, out_name)
        guf.addMsgAndPrint(f"creating feature class {out_path} in {out_fds}")
        arcpy.management.CreateFeatureclass(
            out_fds, out_name, "POINT", loc_points, spatial_reference=unknown
        )

        # add a GeMS-style primary key named {out_name}_ID
        gems_id, id_pref = add_id(out_name, flds, out_path, fc_name)

        # prepare cursors
        # for in_rows, use flds as listed based on the template feature class
        # append the geometry token SHAPE@ so it is at the end of the list of field names
        flds.append("SHAPE@")
        in_rows = arcpy.da.SearchCursor(loc_points, flds)

        # but for out_rows, append a {out_name}_ID field
        flds.append(gems_id)
        out_rows = arcpy.da.InsertCursor(out_path, flds)

        # the objectid field might not always be named OBJECTID
        # get the right name by interrogating the field type
        # and then find the index of that name in the list of fields
        n = in_rows.fields.index
        oid_name = [f.name for f in fld_obj if f.type == "OID"][0]
        oid_i = n(oid_name)

        guf.addMsgAndPrint("creating new features and moving attributes")
        # initialize an integer counter for appending to the gems-style prefix
        # returned by add_id above
        i = 0
        for in_row in in_rows:
            i = i + 1
            # get a list of the values from the located points feature class
            vals = list(in_row).copy()

            # gems_id was added to flds before insert cursor on out_path
            # so extend vals one more index to make room for the _ID value
            vals.append("")

            # create the new shape
            geom = in_row[-1]
            pnt = geom[0]
            X = pnt.M
            if pnt.Z is None:
                Y = -999
            else:
                Y = pnt.Z * vert_ex
            new_pnt = arcpy.Point(X, Y)

            # SHAPE@ token is second to last item
            vals[-2] = new_pnt

            # convert from cartesian to geographic angle
            csAzi = cartesianToGeographic(in_row[n("LOC_ANGLE")])
            vals[n("LocalCSAzimuth")] = csAzi
            vals[n("DistanceFromSection")] = in_row[n("Distance")]
            if isOrientationData:
                # vals[n("MapAzimuth")] = in_row[n("Azimuth")]
                if isAxial(in_row[n("Type")]):
                    appInc, oblique = apparentPlunge(
                        in_row[n("Azimuth")], in_row[n("Inclination")], csAzi
                    )
                    dip_direction = in_row[n("Azimuth")]
                else:
                    appInc, appIncVE, oblique = apparentDip(
                        in_row[n("Azimuth")], in_row[n("Inclination")], csAzi
                    )
                    dip_direction = in_row[n("Azimuth")] + 90
                    # inclination_direction = bearing_sum(in_row[n("Azimuth")], 90)
                    if dip_direction > 360:
                        dip_direction = dip_direction - 360
                # plotAzi = plotAzimuth(inclinationDirection, csAzi, appInc)
                plotAzi = symbol_rotation(dip_direction, csAzi, appIncVE)

                rowObliquity = round(oblique, 2)
                vals[n("DipDirection")] = round(dip_direction, 2)
                vals[n("ApparentInclination")] = round(appInc, 2)
                vals[n("ApparentInclinationVE")] = round(appIncVE, 2)
                vals[n("PlotRotation")] = round(plotAzi, 2)
                vals[n("Obliquity")] = rowObliquity

            # {out_name}_ID is last item
            vals[-1] = f"{id_pref}{str(i)}"
            try:
                out_rows.insertRow(vals)
            except Exception as e:
                guf.addMsgAndPrint(
                    f"9could not create feature from objectid {in_row[oid_i]} in {loc_points}",
                    1,
                )
                guf.addMsgAndPrint(e)

        # change _ID field to ID field
        alter_id(fc_name, flds, out_path)

### POLYGONS
for fc_path in poly_fcs:
    guf.addMsgAndPrint("projecting polygon feature classes:")
    fc_name = os.path.basename(fc_path)
    guf.addMsgAndPrint(f"{fc_name}")

    # locate features along routes
    guf.addMsgAndPrint("making event table")
    event_tbl = os.path.join(os.path.join(scratch, f"{fc_name}_evtble"))
    # guf.addMsgAndPrint(event_tbl)
    guf.testAndDelete(event_tbl)
    event_props = "rkey LINE FromM ToM"
    arcpy.lr.LocateFeaturesAlongRoutes(
        fc_path, zm_line, id_field, "#", event_tbl, event_props
    )

    if guf.numberOfRows(event_tbl) == 0:
        guf.addMsgAndPrint(f"{fc_name} does not intersect section line")
    else:
        guf.addMsgAndPrint("placing events on section line")
        # make route event layer
        event_lyr = f"CS{token}{fc_name}_events"
        arcpy.lr.MakeRouteEventLayer(
            zm_line, id_field, event_tbl, event_props, event_lyr
        )

        # save a copy to the scratch feature dataset
        # this is still in SR of the original fc
        loc_polys = os.path.join(scratch_fd, f"CS{token}{fc_name}_located")
        guf.addMsgAndPrint(f"copying event layer to {loc_polys}")
        arcpy.management.CopyFeatures(event_lyr, loc_polys)

        # create empty feature class, with unknown SR, in the original gdb
        out_name = f"CS{token}_{fc_name}"
        out_path = os.path.join(out_fds, out_name)
        guf.addMsgAndPrint(f"creating feature class {out_name} in {out_fds}")
        guf.testAndDelete(out_path)
        arcpy.management.CreateFeatureclass(
            out_fds,
            out_name,
            "POLYLINE",
            loc_polys,
            "DISABLED",
            "SAME_AS_TEMPLATE",
            spatial_reference=unknown,
        )

        # get field names
        # but exclude Shape and shape_length
        fld_obj = arcpy.ListFields(loc_polys)
        flds = [
            f.name
            for f in fld_obj
            if f.type != "Geometry" and f.name.lower() != "shape_length"
        ]
        flds.append("SHAPE@")

        # prepare cursors
        # for in_rows, use flds as listed based on the template feature class
        in_rows = arcpy.da.SearchCursor(loc_polys, flds)

        # but for out_rows, append a {out_name}_ID field
        # add a GeMS-style primary key named {out_name}_ID
        gems_id, id_pref = add_id(out_name, flds, out_path, fc_name)
        flds.append(gems_id)
        out_rows = arcpy.da.InsertCursor(out_path, flds)

        # get the index of the objectid field
        oid_name = [f.name for f in fld_obj if f.type == "OID"][0]
        oid_i = in_rows.fields.index(oid_name)

        guf.addMsgAndPrint("creating new features and moving attributes")
        # initialize an integer counter for appending to the gems-style prefix
        # returned by add_id above
        i = 0
        for in_row in in_rows:
            i = i + 1
            vals = list(in_row).copy()
            vals.append("")
            # flip shape
            array = []
            for part in in_row[-1]:
                for pnt in part:
                    X = pnt.M
                    Y = pnt.Z * vert_ex
                    array.append((X, Y))
            vals[-2] = array
            vals[-1] = f"{id_pref}{str(i)}"
            try:
                out_rows.insertRow(vals)
            except Exception as e:
                guf.addMsgAndPrint(
                    f"could not create feature from objectid {in_row[oid_i]} in {loc_polys}",
                    1,
                )
                guf.addMsgAndPrint(e)

        alter_id(fc_name, flds, out_path)
# EXTRAS
if add_profile:
    guf.addMsgAndPrint("creating surface profile")
    profile_name = f"CS{token}_SurfaceProfile"
    profile_path = os.path.join(out_fds, profile_name)
    guf.testAndDelete(profile_path)
    arcpy.management.CreateFeatureclass(
        out_fds, profile_name, "POLYLINE", zm_line, spatial_reference=unknown
    )
    arcpy.management.AddField(
        profile_path,
        f"{profile_name}_ID",
        "TEXT",
        field_length=50,
        field_is_nullable="NON_NULLABLE",
    )

    # list of fields comes originally from zm_line
    fld_objs = arcpy.ListFields(zm_line)
    flds = [f.name for f in fld_objs if f.type != "Geometry"]
    flds.append("SHAPE@")

    # search cursor on zm_line with zm_line list of fields
    in_rows = arcpy.da.SearchCursor(zm_line, flds)

    # extend list of fields to include the new _ID field in the output
    # this is now at the end of the list, index = -1
    flds.append(f"{profile_name}_ID")
    out_rows = arcpy.da.InsertCursor(profile_path, flds)

    oid_name = [f.name for f in fld_objs if f.type == "OID"][0]
    oid_i = out_rows.fields.index(oid_name)

    i = 0
    for in_row in in_rows:
        i = i + 1
        vals = list(in_row).copy()
        # extend vals by one more element to make room for _ID value
        vals.append("")
        array = []
        # try:
        line = in_row[-1]
        for pnt in line[0]:
            X = pnt.M
            Y = pnt.Z
            array.append((X, Y * vert_ex))

        vals[-2] = array  # SHAPE is second from the end of the flds list
        vals[-1] = f"{token}SP{str(i)}"  # _ID is at the end of the flds list
        out_rows.insertRow(vals)
        # except:
        # guf.addMsgAndPrint(f"could not create feature from objectid {in_row[oid_i]} in {loc_lines}", 1)

    new_name = id_field.replace("_ID", "ID")
    arcpy.management.AlterField(profile_path, id_field, new_name, new_name)

if add_frame:
    guf.addMsgAndPrint("creating cross section frame")
    # get the min and max M on the measured cross section line.
    with arcpy.da.SearchCursor(zm_line, ["SHAPE@"]) as cursor:
        line = cursor.next()[0]
        Xmin = line.firstPoint.M
        Xmax = line.lastPoint.M
        Yleft = line.firstPoint.Z
        Yright = line.lastPoint.Z

    # make a new feature class and add a label field
    frame_name = f"CS{token}_Frame"
    frame_path = os.path.join(out_fds, frame_name)
    guf.testAndDelete(frame_path)
    arcpy.management.CreateFeatureclass(
        out_fds, frame_name, "POLYLINE", spatial_reference=unknown
    )
    arcpy.management.AddField(frame_path, "type", "TEXT", field_length=100)
    arcpy.management.AddField(frame_path, "label", "TEXT", field_length=100)
    arcpy.management.AddField(frame_path, f"{frame_name}_ID", "TEXT", field_length=50)
    id_pref = f"{token}FM"
    in_rows = arcpy.da.SearchCursor(zm_line, "SHAPE@")
    out_rows = arcpy.da.InsertCursor(
        frame_path, ["type", "label", "SHAPE@", f"{frame_name}_ID"]
    )

    # build the frame
    array = []
    top_left_y = height * vert_ex
    array.append((Xmin, top_left_y))

    bottom_left_y = depth * vert_ex
    array.append((Xmin, bottom_left_y))

    bottom_right_y = depth * vert_ex
    array.append((Xmax, bottom_right_y))

    top_right_y = height * vert_ex
    array.append((Xmax, top_right_y))

    out_rows.insertRow(["frame", "", array, f"{id_pref}1"])

    i = 1
    # if a y tick interval was included,
    # build ticks
    if y_int != 0:
        tickmin = round2int(depth, y_int)
        tickmax = round2int(height, y_int)
        y_list = range(tickmin, tickmax + 1, y_int)

        for y in y_list:
            y_ve = y * vert_ex
            # left side
            pnt1 = (Xmin, y_ve)
            pnt2 = (Xmin - 250, y_ve)
            i = i + 1
            out_rows.insertRow(
                ["elevation tick", str(y), [pnt1, pnt2], f"{id_pref}{i}"]
            )
            # right side
            pnt1 = (Xmax, y_ve)
            pnt2 = (Xmax + 250, y_ve)
            i = i + 1
            out_rows.insertRow(
                ["elevation tick", str(y), [pnt1, pnt2], f"{id_pref}{i}"]
            )

    # if a x tick interval was included
    # build ticks
    if x_int != 0:
        tickmin = round2int(Xmin, x_int)
        tickmax = round2int(Xmax, x_int)
        x_list = range(tickmin, tickmax, x_int)
        y = bottom_left_y

        # build along bottom of the frame
        for x in x_list:
            pnt1 = (x, y)
            pnt2 = (x, y - 250)
            i = i + 1
            out_rows.insertRow(["distance tick", str(x), [pnt1, pnt2], f"{id_pref}{i}"])

arcpy.CheckInExtension("3D")
if not saveIntermediate:
    guf.addMsgAndPrint("deleting intermediate data sets")
    guf.testAndDelete(scratch_fd)
else:
    guf.addMsgAndPrint(f"intermediate data saved in {scratch_fd}")

guf.addMsgAndPrint("finished successfully.")
