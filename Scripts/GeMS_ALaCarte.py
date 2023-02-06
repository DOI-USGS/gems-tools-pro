"""Add GeMS objects a la carte to a geodatabase

    Create or augment a GeMS or GeMS-like file geodatabase by adding one or more
    objects as needed

    Attributes:
        gdb (string): path to an existing file geodatbase. Use the new file
        geodatabase context menu option when browsing to a folder to create 
        an new empty geodatabase

        gdb_items (list): a list of new GeMS ojbects to add to the gdb. Each list
        can have three items;
        [[new or existing feature dataset, spatial reference of fd, table]]
"""

import arcpy
import GeMS_Definition as gdef
from pathlib import Path
import io
from osgeo import osr


def process(gdb, value_table):
    # if gdb doesn't exist, make it
    if not Path(gdb).exists:
        folder = Path(gdb).parent
        name = Path(gdb).stem
        arcpy.CreateFileGDB_management(folder, name)

    # although the parameter form collects a Coordinate System object, it is
    # converted to a prj string when saved within the ValueTable.
    # Since prj strings are not acceptable as input to arcpy.SpatialReference
    # (.prj file paths are but I could not transform the string into a file-path
    # nor is it easy to extract the display name, canonical name, or factory code
    # from the string.), we'll use osgeo.osr
    for i in range(0, value_table.rowCount):
        prj = value_table.getValue(i, 1)

        srs = osr.SpatialReference()
        srs.ImportFromWkt(prj)
        if srs.IsProjected:
            sr_name = srs.GetAttrValue("projcs")
        else:
            sr_name = srs.GetAttrValue("geogcs")

        sr = arcpy.SpatialReference(sr_name)


if __name__ == "__main__":
    gdb = sys.argv[1]
    # gdb_items = sys.argv[2]
    value_table = arcpy.GetParameter(1)
    process(gdb, value_table)
