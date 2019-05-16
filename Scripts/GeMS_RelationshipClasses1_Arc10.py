# script to create a minimal set of relationship classes in a GeMS database
#
# Somebody who uses relationship classes more than I should look at this.
# Particularly, are the Forward and Backward labels named as usefully as possible?
# Are there other issues? 
#
# Note that Validate Database script can be used to maintain referential integrity, 
# thus I don't suggest use of relationship classes to accomplish this.
#   Ralph Haueerud, USGS

import arcpy, sys
from GeMS_utilityFunctions import *
versionString = 'GeMS_RelationshipClasses1_Arc10.py, version of 21 April 2018'

addMsgAndPrint(versionString)

inGdb = sys.argv[1]

DMU = inGdb+'/DescriptionOfMapUnits'
DataSources = inGdb+'/DataSources'
Glossary = inGdb+'/Glossary'
GeoMat = inGdb+'/GeoMaterialDict'
CAF = inGdb+'/GeologicMap/ContactsAndFaults'
MUP = inGdb+'/GeologicMap/MapUnitPolys'
ORP = inGdb+'/GeologicMap/OrientationPoints'
GEL = inGdb+'/GeologicLines'

#  OriginTable DestTable ClassName              RelType  ForLabel            BackLabel                MessageDirection Cardinality  Attributed OrigPKey  OrigFKey
someRelationshipClasses = [
    [DataSources,CAF,'CAF_DataSourceID',       'SIMPLE','arcs with same DataSourceID','DataSource',              'NONE','ONE_TO_MANY','NONE','DataSources_ID','DataSourceID'],
    [Glossary,   CAF,'CAF_ExistenceConfidence','SIMPLE','arcs with same ExConf','ExistenceConfidence definition','NONE','ONE_TO_MANY','NONE','Term','ExistenceConfidence'],
    [Glossary,   CAF,'CAF_IdentityConfidence', 'SIMPLE','arcs with same IdConf','IdentityConfidence definition', 'NONE','ONE_TO_MANY','NONE','Term','IdentityConfidence'],
    [Glossary,   CAF,'CAF_Type',               'SIMPLE','arcs with same Type','Type definition',                 'NONE','ONE_TO_MANY','NONE','Term','Type'],
    [DataSources,DMU,'DMU_DefinitionSourceID', 'SIMPLE','units with same DescriptionSourceID','Description source','NONE','ONE_TO_MANY','NONE','DataSources_ID','DescriptionSourceID'],
    [GeoMat,     DMU,'DMU_GeoMaterial',        'SIMPLE','units with same GeoMaterial','GeoMaterial definition',  'NONE','ONE_TO_MANY','NONE','GeoMaterial','GeoMaterial'],
    [DataSources,GEL,'GEL_DataSourceID',       'SIMPLE','lines with same DataSourceID','DataSource',             'NONE','ONE_TO_MANY','NONE','DataSources_ID','DataSourceID'],
    [Glossary,   GEL,'GEL_ExistenceConfidence','SIMPLE','lines with same ExConf','ExistenceConfidence definition','NONE','ONE_TO_MANY','NONE','Term','ExistenceConfidence'],
    [Glossary,   GEL,'GEL_IdentityConfidence', 'SIMPLE','lines with same IdConf','IdentityConfidence definition','NONE','ONE_TO_MANY','NONE','Term','IdentityConfidence'],
    [Glossary,   GEL,'GEL_Type',               'SIMPLE','lines with same Type','Type definition',                'NONE','ONE_TO_MANY','NONE','Term','Type'],
    [DataSources,Glossary,'Glossary_DefinitionSourceID','SIMPLE','terms with same DefinitionSourceID','DefinitionSource','NONE','ONE_TO_MANY','NONE','DataSources_ID','DefinitionSourceID'],
    [DataSources,MUP,'MUP_DataSourceID',       'SIMPLE','polys with same DataSourceID','DataSource',             'NONE','ONE_TO_MANY','NONE','DataSources_ID','DataSourceID'],
    [Glossary,   MUP,'MUP_IdentityConfidence', 'SIMPLE','polys with same IdConf', 'MapUnit1',                    'NONE','ONE_TO_MANY','NONE','Term','IdentityConfidence'],
    [DMU,        MUP,'MUP_MapUnit',            'SIMPLE','polys with same MapUnit','MapUnit2',                    'NONE','ONE_TO_MANY','NONE','MapUnit','MapUnit'],
    [Glossary,   ORP,'ORP_IdentityConfidence', 'SIMPLE','Orientation points with same IdConf', 'ORP1',           'NONE','ONE_TO_MANY','NONE','Term','IdentityConfidence'],
    [DataSources,ORP,'ORP_LocationSource',     'SIMPLE','Orientation points with same LocationSource','LocationSource','NONE','ONE_TO_MANY','NONE','DataSources_ID','LocationSourceID'],
    [DataSources,ORP,'ORP_OrientationSource',  'SIMPLE','Orientation points with same OrientationSource','OrientationSource','NONE','ONE_TO_MANY','NONE','DataSources_ID','OrientationSourceID'],
    [Glossary,   ORP,'ORP_Type',               'SIMPLE','Orientation points with same Type','Type definition',   'NONE','ONE_TO_MANY','NONE','Term','Type']
    ]

arcpy.env.workspace = inGdb

if not arcpy.Exists(inGdb+'/RelationshipClasses'):
    arcpy.CreateFeatureDataset_management(inGdb,'RelationshipClasses')

for r in someRelationshipClasses:
    testAndDelete(r[2])
    testAndDelete('RelationshipClasses/'+r[2])
    if arcpy.Exists(r[0]) and arcpy.Exists(r[1]):
        addMsgAndPrint('  adding relationship class '+r[2])
        print('  adding relationship class '+r[2])
        arcpy.CreateRelationshipClass_management(r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],r[9],r[10])

addMsgAndPrint('Done')
