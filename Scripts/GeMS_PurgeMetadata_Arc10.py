# purges metadata of geoprocessing history
versionString = 'GeMS_PurgeMetadata.py version of 2 September 2017'

import arcpy, os.path, sys
import egis
from GeMS_utilityFunctions import *

addMsgAndPrint(versionString)

inGdb = os.path.abspath(sys.argv[1])
outDir = sys.argv[2]
addMsgAndPrint('  Starting...')
if outDir == '' or not arcpy.Exists(outDir):
    outDir = os.path.dirname(inGdb)
if not outDir[-1:] in ('/','\\'):
    outDir = outDir+'/'

arcpy.env.workspace = inGdb

tables = arcpy.ListTables()
featureClasses = []
fds = arcpy.ListDatasets()
for fd in fds:
    arcpy.env.workspace = fd
    fc1 = arcpy.ListFeatureClasses()
    if fc1 != None:
      for fc in fc1:
        featureClasses.append(fd+'/'+fc)

arcpy.ImportToolbox(egis.Toolbox, "usgs")


transDir = arcpy.GetInstallInfo("desktop")["InstallDir"]
translator = os.path.join(transDir, "Metadata/Translator/ARCGIS2FGDC.xml")

def purgeGeoprocessingFGDC(table,metadataFile):
    addMsgAndPrint('  exporting metadata to '+metadataFile)
    arcpy.ExportMetadata_conversion(table,translator,metadataFile)
    addMsgAndPrint('  clearing internal metadata')
    arcpy.ClearMetadata_usgs(table)
    addMsgAndPrint('  importing metadata from '+metadataFile)
    arcpy.ImportMetadata_conversion (metadataFile,"FROM_FGDC",table)
    
# gdb as a whole
metadataFile = outDir+os.path.basename(inGdb)[:-4]+'-metadata.xml'
testAndDelete(metadataFile)
addMsgAndPrint('  ')
addMsgAndPrint(inGdb)
purgeGeoprocessingFGDC(inGdb,metadataFile)

arcpy.env.workspace = inGdb
rootName = str(os.path.basename(inGdb)[:-4])

# feature datasets
for fd in fds:
    metadataFile = outDir+'/'+rootName+'-'+os.path.basename(fd)+'-metadata.xml'
    testAndDelete(metadataFile)
    addMsgAndPrint('  ')
    addMsgAndPrint('Feature dataset '+fd)
    purgeGeoprocessingFGDC(fd,metadataFile)
    
# feature classes
for fc in featureClasses:
    metadataFile = outDir+'/'+rootName+'-'+os.path.basename(fc)+'-metadata.xml'
    testAndDelete(metadataFile)
    addMsgAndPrint('  ')
    addMsgAndPrint('Feature class '+fc)
    purgeGeoprocessingFGDC(fc,metadataFile)

"""
# tables
for table in tables:
    metadataFile = outDir+'/'+rootName+'-'+os.path.basename(table)+'-metadata.xml'
    testAndDelete(metadataFile)
    addMsgAndPrint('  ')
    addMsgAndPrint('Table '+table)
    # the next line fails!
    purgeGeoprocessingFGDC(table,metadataFile)
"""

addMsgAndPrint('  ')
addMsgAndPrint('DONE')



