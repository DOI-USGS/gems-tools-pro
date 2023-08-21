"""Convert to geopackage

Creates a new geopackage based on a file geodatabase and then exports
all feature classe and tables to the new geopackage. Feature classes not in 
feature datasets and standalone tables not in a feature datasets retain 
the original name but feature classes inside feature datasets have the
name of the feature dataset pre-prended to the name of the feature class

Usage: 
    Provide the path to a .gdb, an optional output folder. If no output 
    directory is specified, the gpkg will be created in the parent folder
    of the input gdb. The resulting geopackage will have the same name 
    as the gdb with a .gpkg extension. Existing geopackages will be deleted 
    first and then recreated. The parameter form will warn the user about 
    an existing geopackage. They may proceed or pick a different output folder.

Args:
    input_gdb (str) : Path to database. Required.
    output_dir (str) : Path to folder in which to build the geopackage. Optional.
"""

import arcpy
from pathlib import Path
from GeMS_utilityFunctions import addMsgAndPrint as ap
import GeMS_utilityFunctions as guf

versionString = "GeMS_Convert2GPKG.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_Convert2GPKG.py"
guf.checkVersion(versionString, rawurl, "gems-tools-pro")


def convert(input_gdb, output_dir):
    # Set up input and output paths
    input_gdb = Path(input_gdb)
    if output_dir in (None, "", "#"):
        output_dir = input_gdb.parent

    output_gpkg = Path(output_dir) / f"{input_gdb.stem}.gpkg"

    if output_gpkg.exists():
        arcpy.Delete_management(str(output_gpkg))

    ap(f"Creating {input_gdb.stem}.gpkg")
    arcpy.CreateSQLiteDatabase_management(str(output_gpkg), "GEOPACKAGE_1.3")

    # Export feature classes in feature datasets
    arcpy.env.workspace = str(input_gdb)
    datasets = arcpy.ListDatasets()
    for dataset in datasets:
        fc_list = arcpy.ListFeatureClasses("", "", dataset)
        for fc in fc_list:
            fc_name = f"{dataset}_{fc}"
            ap(f"Exporting {fc} as {fc_name}")
            arcpy.ExportFeatures_conversion(
                f"{dataset}/{fc}", str(output_gpkg / fc_name)
            )

    # Export tables and feature classes outside feature datasets
    arcpy.env.workspace = str(input_gdb)
    fc_list = arcpy.ListFeatureClasses()
    table_list = arcpy.ListTables()
    for fc in fc_list:
        ap(f"Exporting {fc}")
        arcpy.ExportFeatures_conversion(fc, str(output_gpkg / fc))
    for table in table_list:
        ap(f"Exporting {table}")
        arcpy.ExportTable_conversion(table, str(output_gpkg / table))

    ap("Export complete.")


if __name__ == "__main__":
    param0 = arcpy.GetParameterAsText(0)
    param1 = arcpy.GetParameterAsText(1)

    convert(param0, param1)
