"""
GeMS_ClearMetadataRecord documentation

This script will clear metadata from a user selection of geodatabase objects by creating an empty metadata record and
replacing the geodatabase object metadata with the empty record.

Usage:
    Either 1) run the Clear Metadata Record tool in the GeMS_Tools.tbx > Metadata toolset; 2) execute this script from
     the command line, using the description of the tool/script parameters below to provide runtime input; or 3) import
     this script in another module and call the functions below from it.

Tool/script parameters:
    0) a GeMS file geodatabase;
    1) A list of geodatabase objects selected in the tool for which metadata records will be cleared.
"""
import arcpy
import os
from datetime import datetime
import GeMS_utilityFunctions as guf

# Implement addMsgAndPrint function that does not split newlines like GeMS_utilityFunctions does.
def addMsgAndPrint(msg, severity=0):
    # prints msg to screen and adds msg to the geoprocessor (in case this is run as a tool)
    print(msg)

    # noinspection PyBroadException
    try:
        # Add appropriate geoprocessing message
        if severity == 0:
            arcpy.AddMessage(msg)
        elif severity == 1:
            arcpy.AddWarning(msg)
        elif severity == 2:
            arcpy.AddError(msg)
    except Exception:
        pass


def backup_existing_metadata(gdb_name, gdb_object_relpath=""):
    # arcpy.env.workspace has been set to the input geodatabase, so gdb object paths are relative to it.
    scratch_abspath = arcpy.env.scratchFolder
    fd, object_name = os.path.split(gdb_object_relpath)
    if len(fd):
        object_name = f"{gdb_name}_{fd}_{object_name}"
    elif len(object_name):
        object_name = f"{gdb_name}_{object_name}"
    else:
        object_name = f"{gdb_name}"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_name = f"{object_name}-metadata_{timestamp}.xml"
    backup_abspath = os.path.join(scratch_abspath, backup_name)
    style = "FGDC_CSDGM"
    addMsgAndPrint(f"  Backing up existing metadata using '{style}' style to '{backup_abspath}'.")
    removal_option = "EXACT_COPY"
    md_object = arcpy.metadata.Metadata(gdb_object_relpath)
    md_object.exportMetadata(backup_abspath, style, removal_option)

def clear_metadata_record(gdb_object_relpath):
    addMsgAndPrint(f"  Clearing metadata record for: '{gdb_object_relpath}'.\n\n")
    # arcpy.env.workspace has been set to the input geodatabase, so gdb object paths are relative to it.
    md_object = arcpy.metadata.Metadata(gdb_object_relpath)
    md_empty = arcpy.metadata.Metadata()
    md_object.copy(md_empty)
    md_object.save()

def process_metadata(gdb_abspath, metadata_to_clear):
    """Script code goes below"""
    arcpy.env.workspace = gdb_abspath

    # Get the geodatabase name to use to match to XML filenames
    gdb_folder, gdb_filename = os.path.split(gdb_abspath)
    gdb_name = gdb_filename[:-4]

    for gdb_object in metadata_to_clear:
        if gdb_object == gdb_filename:
            backup_existing_metadata(gdb_name)
            clear_metadata_record(gdb_abspath)
        else:
            backup_existing_metadata(gdb_name, gdb_object)
            clear_metadata_record(gdb_object)

    return


if __name__ == "__main__":
    # TODO: When pushed to the GitHub repo, implement version checking
    # versionString = "GeMS_ClearMetadataRecord.py, version of 4/16/24"
    # rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/add-metadata-import/Scripts/GeMS_ClearMetadataRecord.py"
    # guf.checkVersion(versionString, rawurl, "gems-tools-pro")

    # Referencing parameters by their name only works if the script is executed via a toolbox
    # because this script is otherwise unaware of the toolbox parameters.
    # gdb = arcpy.GetParameterAsText("gems_geodatabase")
    # metadata_to_clear = arcpy.GetParameter("metadata_to_clear")

    gdb = arcpy.GetParameterAsText(0)
    metadata_to_clear = arcpy.GetParameter(1)

    process_metadata(gdb, metadata_to_clear)
