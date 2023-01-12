"""Create empty GeMS submission directory tree.

Create an empty directory tree based on the naming and file organiation
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
    basedata (boolean): should a basedata directory be created?

"""

import arcpy
import GeMS_utilityFunctions as guf
import subprocess

version_string = "GeMS_SubmissionTree.py, version of 10 January 2023"
rawurl = "https://raw.githubusercontent.com/usgs/gems-tools-pro/master/Scripts/GeMS_SubmissionTree.py"
guf.checkVersion(version_string, rawurl, "gems-tools-pro")


def make_tree(parent_dir, postal_code, year, mapped_area, abbname, version, basedata):

    if version != "":
        name = f"{postal_code}_{year}_{mapped_area}_{version}"
    else:
        name = f"{postal_code}_{year}_{mapped_area}"

    # if basedata:
    #     bd = 'yes'
    # else:
    #     bd = 'no'
    subprocess.run(["gems_mkdir.bat", parent_dir, name, abbname, basedata], shell=True)
    arcpy.AddMessage("Done")


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

    if arcpy.GetParameterAsText(5) != "#":
        abbname = arcpy.GetParameterAsText(5)
        if len(abbname) > 5:
            abbname = abbname[:5]
    else:
        abbname = mapped_area[:5]

    basedata = guf.convert_bool(arcpy.GetParameterAsText(5))

    make_tree(parent_dir, postal_code, year, mapped_area, abbname, version, basedata)
