"""Rename ID fields

Renames any _ID primary field in a GeMS database if the field does
not equal the name of the table + "_ID". Renames Alias as well.

Usage:
    Use parameter form in ArcGIS Pro or at command line with the arguments below. 
    
Args:
    gdb_path (str) : Path to database. Required.    
      
Returns:
    re-writes contents of gdb. If you are unsure of the output, create a backup copy first.
"""

import sys
import arcpy
import GeMS_utilityFunctions as guf

version_string = "GeMS_RenameIDFields.py, version of 8/30/2023"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_RenameIDFields.py"


def main(db):
    guf.checkVersion(version_string, rawurl, "gems-tools-pro")
    d = guf.gdb_object_dict(db)

    for k, v in d.items():
        if "fields" in v:
            fields = [f.name for f in v["fields"]]
            for field in fields:
                if field.endswith("_ID"):
                    gems_id = f"{k}_ID"

                    if not field == gems_id:
                        in_table = v["catalogPath"]
                        try:
                            arcpy.AddMessage(f"changing {field} to {gems_id}")
                            arcpy.management.AlterField(
                                in_table, field, gems_id, gems_id
                            )
                        except:
                            arcpy.AddWarning(
                                f"""Could not change {field} to {gems_id}. Check for locks on the geodatabase 
                                or relationship classes that use the field"""
                            )


if __name__ == "__main__":
    db = sys.argv[1]
    main(db)
