"""Compacts and/or backs up a database. 
Compact calls ArcGIS Compact tool.
Backup is a copy with the date ( _yyyy-mm-dd)
appended to the file name.

If a db with this name already exists
in the output directory, a letter (b, c, d, ...)
is appended until a unique name is obtained"""

#
# 4 March 2018  added optional message to log file
# 16 May 2019: updated for Python 3 with 2to3. No other edits.
#   Tested against a gdb and it ran with no errors.

import arcpy, sys, os.path
import GeMS_utilityFunctions as guf

versionString = "GeMS_CompactAndBackup.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_CompactAndBackup.py"
guf.checkVersion(versionString, rawurl, "gems-tools-pro")


def backupName(inDb):
    # returns name for a backup copy of a geodatabase where
    #    backup matches inDb in type (.gdb or .mdb)
    #    name is of form inDb_yyyy-mm-dd[x].gdb/.mdb
    #      where x is '', then 'a', 'b', 'c', ...
    #    and backupName doesn't yet exist
    import datetime

    nameRoot = inDb[:-4]
    nameSfx = inDb[-4:]
    nameInc = " bcdefghijklmnopqrstuvwxyz"
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    i = 0
    newName = nameRoot + "_" + date + nameSfx
    while arcpy.Exists(newName):
        i = i + 1
        newName = nameRoot + "_" + date + nameInc[i] + nameSfx
        if i > 25:
            return ""
    return newName


inDb = sys.argv[1]
compact = sys.argv[2]
backup = sys.argv[3]
message = sys.argv[4]

if message != "#":
    guf.writeLogfile(inDb, message)

if compact == "true":
    guf.addMsgAndPrint(f"Compacting {os.path.basename(inDb)}")
    arcpy.Compact_management(inDb)

if backup == "true":
    guf.addMsgAndPrint("Getting name of backup copy")
    copyName = backupName(inDb)

    if len(copyName) > 4:
        guf.addMsgAndPrint(
            f"Copying {os.path.basename(inDb)} to {os.path.basename(copyName)}"
        )
        arcpy.Copy_management(inDb, copyName)
    else:
        guf.addMsgAndPrint(
            "Cannot get a valid name for a backup copy. Forcing an exit."
        )
        guf.forceExit()
