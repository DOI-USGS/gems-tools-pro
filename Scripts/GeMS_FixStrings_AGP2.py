#   Script to clean up string fields in a GeMS database
##      Removes leading and trailing spaces
##      Converts "<null>", "" and similar to <null> (system nulls).
#       Ralph Haugerud, 28 July 2020
#       Updated to Python 3, 8/20/21 and added to toolbox, Evan Thoms

import arcpy, os, os.path, sys
from GeMS_utilityFunctions import *

versionString = 'GeMS_FixStrings_AGP2.py, version of 8 September 2021'
rawurl = 'https://raw.githubusercontent.com/usgs/gems-tools-pro/master/Scripts/GeMS_FixStrings_AGP2.py'
checkVersion(versionString, rawurl, 'gems-tools-pro')

def fixTableStrings(fc):
    fields1 = arcpy.ListFields(fc,'','String')
    fields = ['OBJECTID']
    for f in fields1:
        fields.append(f.name)
    with arcpy.da.UpdateCursor(fc, fields) as cursor:
        for row in cursor:
            trash = ''
            updateRowFlag = False
            row1 = [row[0]]
            for i, f in enumerate(row[1:]):
                updateFieldFlag = False
                f0 = f
                if f != None:
                    if f != f.strip():
                        f = f.strip()
                        updateFieldFlag = True
                    if f.lower() == '<null>' or f == '':
                        f = None
                        updateFieldFlag = True
                    if updateFieldFlag:
                        updateRowFlag = True
                        addMsgAndPrint(f" OID:{str(row[0])} field:{fields[i+1]} value:'{str(f0)}'")
                row1.append(f)
            if updateRowFlag:
                try:
                    cursor.updateRow(row1)
                except Exception as error:
                    addMsgAndPrint(f'Failed to update row {str(row[0])}. {error}')
    
#########################

db = sys.argv[1]

addMsgAndPrint(versionString)
arcpy.env.workspace = db

tables = arcpy.ListTables()
for tb in tables:
    addMsgAndPrint(' ')
    addMsgAndPrint(os.path.basename(tb))
    fixTableStrings(tb)

datasets = arcpy.ListDatasets(feature_type='feature')
datasets = [''] + datasets if datasets is not None else []

for ds in datasets:
    for fc in arcpy.ListFeatureClasses(feature_dataset=ds):
        path = os.path.join(arcpy.env.workspace, ds, fc)
        try:
            fixTableStrings(path)
        except:
            addMsgAndPrint('  failed to fix strings')

addMsgAndPrint('DONE')
