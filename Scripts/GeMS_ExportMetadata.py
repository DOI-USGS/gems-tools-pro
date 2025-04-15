"""
GeMS_ExportMetadata documentation

This script will export metadata from a user selection of geodatabase objects by creating an empty metadata record and
replacing the geodatabase object metadata with the empty record.

Usage:
    Either 1) run the Clear Metadata Record tool in the GeMS_Tools.tbx > Metadata toolset; 2) execute this script from
     the command line, using the description of the tool/script parameters below to provide runtime input; or 3) import
     this script in another module and call the functions below from it.

Tool/script parameters:
    0) a GeMS file geodatabase;
    1) A list of geodatabase objects selected in the tool for which metadata records will be exported.
    2) The folder that XML records will be exported to. Files will be named based on the database name, the name of the
     object the metadata is exported from, and a timestamp in the format YYYYMMDDhhmmss.
"""

import arcpy
import os
from datetime import datetime
import GeMS_utilityFunctions as guf
from lxml import etree
import metadata_utilities as mu


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


def export_metadata_record(export_folder, gdb_name, gdb_object_relpath=""):
    # arcpy.env.workspace has been set to the input geodatabase, so gdb object paths are relative to it,
    # unless the object is the database itself, which needs to be passed to the metadata object.
    gdb_abspath = arcpy.env.workspace
    fd, object_name = os.path.split(gdb_object_relpath)
    if len(fd):
        object_name = f"{gdb_name}_{fd}_{object_name}"
    elif len(object_name):
        object_name = f"{gdb_name}_{object_name}"
    else:
        object_name = f"{gdb_name}"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    export_name = f"{object_name}-metadata_{timestamp}.xml"
    export_abspath = os.path.join(export_folder, export_name)
    style = "FGDC_CSDGM"
    addMsgAndPrint(
        f"  Exporting existing metadata using '{style}' style to '{export_abspath}'."
    )
    removal_option = "EXACT_COPY"
    if len(gdb_object_relpath):
        md_object = arcpy.metadata.Metadata(gdb_object_relpath)
    else:
        md_object = arcpy.metadata.Metadata(gdb_abspath)
    md_object.exportMetadata(export_abspath, style, removal_option)

    # add a spatial reference element if appropriate.
    # have to parse the previously saved XML, add the element, and re-save
    if len(gdb_object_relpath):
        desc = arcpy.da.Describe(gdb_object_relpath)
    else:
        desc = arcpy.da.Describe(gdb_abspath)
    layer_dict = {desc["baseName"]: desc}
    if "spatialReference" in desc:
        md_dom = etree.parse(export_abspath).getroot()
        mu.add_spref(layer_dict, desc["baseName"], md_dom)
        mu.write_xml(md_dom, export_abspath)


def process_metadata(gdb_abspath, metadata_to_export, export_folder):
    """Script code goes below"""
    arcpy.env.workspace = gdb_abspath

    # Get the geodatabase name to use to match to XML filenames
    gdb_folder, gdb_filename = os.path.split(gdb_abspath)
    gdb_name = gdb_filename[:-4]

    for gdb_object in metadata_to_export:
        if gdb_object == gdb_filename:
            export_metadata_record(export_folder, gdb_name)
        else:
            export_metadata_record(export_folder, gdb_name, gdb_object)

    return


if __name__ == "__main__":
    # TODO: When pushed to the GitHub repo, implement version checking
    # versionString = "GeMS_ClearMetadataRecord.py, version of 4/16/24"
    # rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/add-metadata-import/Scripts/GeMS_ClearMetadataRecord.py"
    # guf.checkVersion(versionString, rawurl, "gems-tools-pro")

    # Referencing parameters by their name only works if the script is executed via a toolbox
    # because this script is otherwise unaware of the toolbox parameters.
    # gdb = arcpy.GetParameterAsText("gems_geodatabase")
    # metadata_to_export = arcpy.GetParameter("metadata_to_export")
    # export_folder = arcpy.GetParameterAsText("export_folder")

    gdb = arcpy.GetParameterAsText(0)
    metadata_to_export = arcpy.GetParameter(1)
    export_folder = arcpy.GetParameterAsText(2)

    process_metadata(gdb, metadata_to_export, export_folder)
