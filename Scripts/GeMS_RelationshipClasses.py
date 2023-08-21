# script to create relationship classes in a GeMS database
#
# Somebody who uses relationship classes more than I should look at this.
# Particularly, are the Forward and Backward labels named as usefully as possible?
# Are there other issues?
#
# Note that Validate Database script can be used to maintain referential integrity,
# thus I don't suggest use of relationship classes to accomplish this.
#   Ralph Haugerud, USGS
# Use this mostly in order to see related records in Identify tool in ArcMap or in
# the feature attribute pop-up in ArcGIS Pro. Note that the related table must in the map
# in order for the related records to be displayed
#   Evan Thoms, USGS
# GeMS_RelationshipClasses_AGP2.py
# 6 June 2019: updated to work with Python 3 in ArcGIS Pro. Evan Thoms
#   ran the script through 2to3. No other edits necessary
#   renamed from GeMS_RelationshipClasses1_Arc10.py to GeMS_RelationshipClasses_AGP2.py
# 7 November 2019: In response to issue raised at repo, completely rewritten to
#   1) not create feature dataset just for the relationship classes. Found the
#      feature dataset could be written, but could not write relationship classes there.
#      Perhaps because it only had a name and no other properties, although this is probably
#      not best practices anyway. Relationship classes are now written in the workspace
#      in which the feature class is found
#   2) create relationship classes based on controlled fields, not a list of explicit
#      relationship classes. Could result in many superfluous relationship classes
#   3) attempt to work with table and field names regardless of case

import arcpy
import sys
import os
from GeMS_utilityFunctions import *

versionString = "GeMS_RelationshipClasses1.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_RelationshipClasses.py"
checkVersion(versionString, rawurl, "gems-tools-pro")


def fname_find(field_string, table):
    # finds a field name regardless of the case of the search string (field_string)
    fields = arcpy.ListFields(table)
    for field in fields:
        if field.name.lower() == field_string.lower():
            return field.name


def tname_find(table_string):
    # find a table name regardless of case of search string (table_string)
    # searches the dictionary of table name: [root, path]
    for key in tab_dict:
        if key.lower() == table_string.lower():
            return key


def rc_handler(key, value, foreign_search, primary_search, origin_search):
    try:
        # sanitize the field and table names in case everything is in lower or upper case
        origin = tname_find(origin_search)
        d_key = fname_find(foreign_search, value[1])
        o_key = fname_find(primary_search, tab_dict[origin][1])

        # check for existing relationship class
        rc_name = "{}_{}".format(key, d_key)
        if arcpy.Exists(rc_name):
            arcpy.Delete_management(rc_name)

        # create the relationship class
        addMsgAndPrint("Building {}".format(rc_name))
        # print(tab_dict[origin][1],value[1],rc_name,'SIMPLE','{} in {}'.format(o_key, key),'{} in {}'.format(d_key, origin),
        #'NONE','ONE_TO_MANY','NONE',o_key,d_key, sep=' | ')
        arcpy.CreateRelationshipClass_management(
            tab_dict[origin][1],
            value[1],
            rc_name,
            "SIMPLE",
            "{} in {}".format(o_key, key),
            "{} in {}".format(d_key, origin),
            "NONE",
            "ONE_TO_MANY",
            "NONE",
            o_key,
            d_key,
        )
    except:
        print("Could not create relationship class {}".format(rc_name))


inGdb = sys.argv[1]

# make a dictionary of feature classes: [workspace, full path]
walkfc = arcpy.da.Walk(inGdb, datatype="FeatureClass")
fc_dict = {}
for root, dirs, files in walkfc:
    for file in files:
        fc_path = os.path.join(root, file)
        if arcpy.Describe(fc_path).featureType != "Annotation":
            fc_dict[file] = [root, fc_path]

# make a dictionary of tables: [workspace, full path]
walktab = arcpy.da.Walk(inGdb, datatype="Table")
tab_dict = {}
for root, dirs, files in walktab:
    for file in files:
        if file.find(".") == -1:
            tab_dict[file] = [root, os.path.join(root, file)]

# run through the feature classes and create appropriate relationship classes
for key, value in fc_dict.items():
    arcpy.env.workspace = value[0]

    for field in arcpy.ListFields(value[1]):
        field_name = field.name.lower()
        if (
            field_name == "type"
            or field_name.find("confidence") > 0
            and field.type == "String"
        ):
            rc_handler(key, value, field.name, "Term", "Glossary")
        if field_name.find("source_id") > 0:
            rc_handler(key, value, field.name, "DataSource_ID", "DataSources")
        if field_name == "geomaterial":
            rc_handler(key, value, field.name, "GeoMaterial", "GeoMaterialDict")
        if field_name == "mapunit":
            rc_handler(key, value, field.name, "MapUnit", "DescriptionOfMapUnits")

addMsgAndPrint("Done")
