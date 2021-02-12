# compacts a database and makes a copy
# copy is .gdb or .mdb, to match input, and
# has _yyyy-mm-dd appended to filename root.
#
# if a db with this name already exists
# in the output directory, an a, or b, or ...
# is appended until a unique name is obtained.
#
# 4 March 2018  added optional message to log file
# 16 May 2019: updated for Python 3 with 2to3. No other edits.
#   Tested against a gdb and it ran with no errors.

import arcpy, sys, os.path
from GeMS_utilityFunctions import *

versionString = 'GeMS_CompactAndBackup_Arc10.py, version of 4 March 2018'
rawurl = 'https://raw.githubusercontent.com/usgs/gems-tools-pro/master/Scripts/GeMS_CompactAndBackup_Arc10.py'
checkVersion(versionString, rawurl, 'gems-tools-pro')

def backupName(inDb):
    # returns name for a backup copy of a geodatabase where
    #    backup matches inDb in type (.gdb or .mdb)
    #    name is of form inDb_yyyy-mm-dd[x].gdb/.mdb
    #      where x is '', then 'a', 'b', 'c', ...
    #    and backupName doesn't yet exist
    import datetime
    nameRoot = inDb[:-4]
    nameSfx = inDb[-4:]
    nameInc = ' bcdefghijklmnopqrstuvwxyz'
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    i = 0
    newName = nameRoot+'_'+date+nameSfx
    while arcpy.Exists(newName):
        i = i+1
        newName = nameRoot+'_'+date+nameInc[i]+nameSfx
        if i > 25:
            return ''
    return newName

inDb = sys.argv[1]

if len(sys.argv[2]) > 1:
    writeLogfile(inDb,sys.argv[2])

addMsgAndPrint( '  Compacting '+os.path.basename(inDb) )
arcpy.Compact_management(inDb)

addMsgAndPrint(  '  Getting name of backup copy' )
copyName = backupName(inDb)

if len(copyName) > 4:
    addMsgAndPrint(  '  Copying '+os.path.basename(inDb) +' to '+os.path.basename(copyName) )
    arcpy.Copy_management(inDb,copyName)
else:
    addMsgAndPrint( '  Cannot get a valid name for a backup copy. Forcing an exit.' )
    forceExit()
