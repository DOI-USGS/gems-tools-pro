"""Convert to geopackage

Creates a new geopackage based on a file geodatabase and then exports
all feature classe and tables to the new geopackage. Feature classes not in 
feature datasets and standalone tables not in a feature datasets retain 
the original name but feature classes inside feature datasets have the
name of the feature dataset pre-prended to the name of the feature class

Usage: 
    Provide the path to a .gdb and an optional output folder

Args:
    input_gdb (str) : Path to database. Required.
    output_dir (str) : Path to folder in which to build the geopackage. Optional
    overwrite (boolean) : Overwrite (delete and create new) existing geopackage.
      True or False. Optional. True by default.
"""

import arcpy, os

def convert(input_gdb, output_dir, overwrite)
    # Set up input and output paths
    input_gdb = r"path\to\input\geodatabase.gdb"
    if output_dir in (None, "", "#"):
        output_dir = os.path.dirname(input_gdb)

    output_gpkg = os.path.join(
        output_dir, f"{os.path.basename(input_gdb)}.gpkg"
    )

    if arcpy.Exists(output_gpkg):
        if overwrite.lower in ("true"):
            arcpy.Delete_management(output_gpkg)
        else:
            
    

    # Convert feature classes in feature datasets
    arcpy.env.workspace = input_gdb
    datasets = arcpy.ListDatasets()
    for dataset in datasets:
        fc_list = arcpy.ListFeatureClasses("", "", dataset)
        for fc in fc_list:
            fc_name = f"{dataset}_{fc}"
            arcpy.FeatureClassToGeodatabase_conversion(
                f"{dataset}/{fc}", output_gpkg, fc_name
            )

    # Convert tables and feature classes outside feature datasets
    arcpy.env.workspace = input_gdb
    fc_list = arcpy.ListFeatureClasses()
    table_list = arcpy.ListTables()
    for fc in fc_list:
        if arcpy.Describe(fc).datasetType != "FeatureDataset":
            arcpy.FeatureClassToGeodatabase_conversion(fc, output_gpkg, fc)
    for table in table_list:
        arcpy.TableToGeodatabase_conversion(table, output_gpkg)

    print("Conversion complete.")


if __name__ == "__main__":

    param0 = arcpy.GetParameterAsText(0)
    param1 = arcpy.GetParameterAsText(1)
    param2 = arcpy.GetParameterAsText(2)

    convert(param0, param1, param2)