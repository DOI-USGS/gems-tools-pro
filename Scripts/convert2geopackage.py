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
"""

import arcpy, os

# Set up input and output paths
input_gdb = r"path\to\input\geodatabase.gdb"
output_gpkg = os.path.join(
    os.path.dirname(input_gdb), f"{os.path.basename(input_gdb)}.gpkg"
)

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
