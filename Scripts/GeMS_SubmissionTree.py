"""Create empty GeMS submission directory tree.

Create an empty directory tree based on the naming and file organization
convention described in the GeMS Submission Requirements document.

Arguments supplied to this python script are sent to gems_mdkir.bat which
can be run from the command line. To run the batch file, copy it to the 
directory where the tree should be created and provide two arguments:
the full name of the publication (postalcode_year_mappedarea_version) and
whether a basedata folder should be created.

Args:
    parent_dir: (str): path to directory in which to create the tree
    postal_code (str): two-letter state postal code
    year (str): year of award
    mapped_area (str): state, quad, region, etc. of mapped area
    version (str): major-minor
    basedata (boolean): should a basedata directory be created? y or n.

"""

import arcpy
import GeMS_utilityFunctions as guf
import subprocess
from pathlib import Path

version_string = "GeMS_SubmissionTree.py, version of 20 March 2023"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_SubmissionTree.py"
guf.checkVersion(version_string, rawurl, "gems-tools-pro")


sub_readme = [
    "Add the following files to this folder:\n",
    "  fullname_transmittalletter.docx\n",
    "  fullname_Validation.html\n",
    "  fullname_ValidationErrors.html\n",
    "  fullname_namescheck.xls",
]

map_readme = [
    "Add the following files to this folder:\n",
    "  Required:\n",
    "    mapXYZ-browse.(jpg, pdf, png, etc.) map graphic\n",
    "    mapXYZ-metadata.xml\n",
    "  As-needed:\n",
    "    mapXYZ.pdf publication pamphlet\n",
    "  Optional:\n",
    "    Folder of the map data in an open source format, e.g.,\n",
    "    fullname-geopaackage, fullname-spatialite, etc.",
]

db_readme = [
    "Add the following files to this folder:\n",
    "  Required:\n",
    "    .gdb file geodatabase\n",
    "    .mapx or .mxd (preferred)\n",
    "  As-needed:\n",
    "    mapXYZ.pdf publication pamphlet\n",
    "  Optional:\n",
    "    files for viewing the data with free software, e.g., QGIS project, KML files, etc.",
]

resources_readme = [
    "Add the following files to this folder:\n",
    "  Required:\n",
    "    symbology as style file, layer file, etc.\n",
    "  As-needed:\n",
    "    CMU graphic if not present in any other element\n",
    "    Figures as editable graphics files, e.g., PDF, AI, EPS, etc."
    "    Tables as editable Excel, CSV, etc.\n",
    "  Optional:\n",
    "    Formatted DMU or LMU document",
]

shp_readme = [
    "Run the Translate to Shapefiles tool from the GeMS Toolbox and put the results here.\n",
    "  Shapefile for each feature class\n",
    "  .dbf for each nonspatial table\n",
    "  text file (CSV) for each table with contents over 254 characters in length\n",
    "  README-like text file describin file and field names",
]

readme_dict = {
    "fullname-submittal": sub_readme,
    "fullname-submittal/fullname": map_readme,
    "fullname-submittal/fullname/fullname-database": db_readme,
    "fullname-submittal/fullname/fullname-database/resources": resources_readme,
    "fullname-submittal/fullname/fullname-shapefile": shp_readme,
}


def make_tree(parent_dir, postal_code, year, mapped_area, version, basedata):
    if version != "":
        name = f"{postal_code}_{year}_{mapped_area}_{version}"
    else:
        name = f"{postal_code}_{year}_{mapped_area}"

    if basedata:
        bd = "y"
    else:
        bd = "n"

    arcpy.AddMessage(f"Creating tree in {parent_dir}")
    arcpy.AddMessage(subprocess.list2cmdline(["gems_mkdir.bat", parent_dir, name, bd]))
    subprocess.run(["gems_mkdir.bat", parent_dir, name, bd], shell=True)

    crawl_readmes(parent_dir, name)

    arcpy.AddMessage("Done")


def crawl_readmes(parent_dir, name):
    for k, v in readme_dict.items():
        folder = k.replace("fullname", name)
        folder_path = Path(parent_dir) / folder
        if folder_path.exists():
            readme_path = folder_path / "add these files.txt"
            write_readme(readme_path, [n.replace("fullname", name) for n in v])


def write_readme(f_path, readme_list):
    with open(f_path, "w") as f:
        f.writelines(readme_list)
        f.write("\n\nDelete this file before submission.")


# This is used to execute code if the file was run but not imported
if __name__ == "__main__":
    # Tool parameter accessed with GetParameter or GetParameterAsText
    parent_dir = arcpy.GetParameterAsText(0)
    postal_code = arcpy.GetParameterAsText(1)
    year = arcpy.GetParameterAsText(2)
    mapped_area = arcpy.GetParameterAsText(3)

    if arcpy.GetParameterAsText(4) != "#":
        version = arcpy.GetParameterAsText(4)
    else:
        version = ""

    basedata = guf.convert_bool(arcpy.GetParameterAsText(5))

    make_tree(parent_dir, postal_code, year, mapped_area, version, basedata)
