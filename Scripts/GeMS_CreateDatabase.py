# GeMS_CreateDatabase_Arc10.1.py
#   Python script to create an empty NCGMP09-style
#   ArcGIS 10 geodatabase for geologic map data
#
#   Ralph Haugerud, USGS
#
# RUN AS TOOLBOX SCRIPT FROM ArcCatalog OR ArcMap

# 9 Sept 2016: Made all fields NULLABLE
# 19 Dec 2016: Added GeoMaterialsDict table, domains
# 8 March 2017: Added  ExistenceConfidence, IdentityConfidence, ScientificConfidence domains, definitions, and definitionsource
# 17 March 2017  Added optional table MiscellaneousMapInformation
# 30 Oct 2017  Moved CartoRepsAZGS and GeMS_lib.gdb to ../Resources
# 4 March 2018  changed to use writeLogfile()
# 16 May 2019 GeMS_CreateDatabase_Arc10.py Python 2.7 ported to Python 3 to work in ArcGIS Pro 2.1, Evan Thoms

# 8 June 2020 In transDict (line 31), changed 'NoNulls':'NON_NULLABLE' to 'NoNulls':'NULLABLE'
#   " "       Fixed bug with addTracking(), where EnableEditorTracking_management apparently wants in_dataset to be a full pathname
#   " "       Added MapUnitLines to list of feature classes that could be created (line 153)
# 28 Sept 2020 Now defines coordinate system for CMU and cross section feature datasets (= map coordinate system)
# 7 Oct 2020 Improved definition of cross section feature classes to match specification
# Edits 10/8/20 to update to Ralph's latest changes (above), Evan Thoms
# 23 December 2020: Changed how MapUnitPoints feature class is created, so that it follows definition in GeMS_Definitions.py - RH

import arcpy, sys, os, os.path
from GeMS_Definition import (
    tableDict,
    GeoMaterialConfidenceValues,
    DefaultExIDConfidenceValues,
    IDLength,
)
from GeMS_utilityFunctions import *
import copy

versionString = "GeMS_CreateDatabase.py, version of 9/18/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_CreateDatabase.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

debug = True

default = "#"

# cartoReps = False # False if cartographic representations will not be used

transDict = {
    "String": "TEXT",
    "Single": "FLOAT",
    "Double": "DOUBLE",
    "NoNulls": "NULLABLE",  # NB-enforcing NoNulls at gdb level creates headaches; instead, check while validating
    "NullsOK": "NULLABLE",
    "Optional": "NULLABLE",
    "Date": "DATE",
}

usage = """Usage:
   systemprompt> GeMS_CreateDatabase_Arc10.1.py <directory> <geodatabaseName> <coordSystem>
                <OptionalElements> <#XSections> <AddEditTracking> <AddRepresentations> <AddLTYPE>
   <directory> is existing directory in which new geodatabaseName is to 
      be created, use # for current directory
   <geodatabaseName> is name of gdb to be created, with extension
      .gdb causes a file geodatabase to be created
      .mdb causes a personal geodatabase to be created
   <coordSystem> is a fully-specified ArcGIS coordinate system
   <OptionalElements> is either # or a semicolon-delimited string specifying
      which non-required elements should be created (e.g.,
      OrientationPoints;CartographicLines;RepurposedSymbols )
   <#XSections> is an integer (0, 1, 2, ...) specifying the intended number of
      cross-sections
   <AddEditTracking> is either true or false (default is true). Parameter is ignored if
      ArcGIS version is less than 10.1
   <AddRepresentations> is either true or false (default is false). If true, add
      fields for Cartographic representions to all feature classes
   <AddLTYPE> is either true or false (default is false). If true, add LTYPE field
      to feature classes ContactsAndFaults and GeologicLines, add PTTYPE field
      to feature class OrientationData, and add PTTYPE field to MapUnitLabelPoints    

  Then, in ArcCatalog:
  * If you use the CorrelationOfMapUnits feature data set, note that you will 
    have to manually create the annotation feature class CMUText and add field 
    ParagraphStyle. (I haven't yet found a way to script the creation of an 
    annotation feature class.)
  * If there will be non-standard point feature classes (photos, mineral 
    occurrences, etc.), copy/paste/rename feature class GenericPoint or 
    GenericSample, as appropriate, rename the _ID field, and add necessary
    fields to the new feature class.
  * Load data, if data already are in GIS form. 
  Edit data as needed.

"""


def addMsgAndPrint(msg, severity=0):
    # prints msg to screen and adds msg to the geoprocessor (in case this is run as a tool)
    # print msg
    try:
        for string in msg.split("\n"):
            # Add appropriate geoprocessing message
            if severity == 0:
                arcpy.AddMessage(string)
            elif severity == 1:
                arcpy.AddWarning(string)
            elif severity == 2:
                arcpy.AddError(string)
    except:
        pass


def createFeatureClass(thisDB, featureDataSet, featureClass, shapeType, fieldDefs):
    addMsgAndPrint("    Creating feature class " + featureClass + "...")
    try:
        arcpy.env.workspace = thisDB
        arcpy.CreateFeatureclass_management(featureDataSet, featureClass, shapeType)
        thisFC = thisDB + "/" + featureDataSet + "/" + featureClass
        for fDef in fieldDefs:
            try:
                if fDef[1] == "String":
                    # note that we are ignoring fDef[2], NullsOK or NoNulls
                    arcpy.AddField_management(
                        thisFC,
                        fDef[0],
                        transDict[fDef[1]],
                        "#",
                        "#",
                        fDef[3],
                        "#",
                        "NULLABLE",
                    )
                else:
                    # note that we are ignoring fDef[2], NullsOK or NoNulls
                    arcpy.AddField_management(
                        thisFC,
                        fDef[0],
                        transDict[fDef[1]],
                        "#",
                        "#",
                        "#",
                        "#",
                        "NULLABLE",
                    )
            except:
                addMsgAndPrint(
                    "Failed to add field "
                    + fDef[0]
                    + " to feature class "
                    + featureClass
                )
                addMsgAndPrint(arcpy.GetMessages(2))
    except:
        addMsgAndPrint(arcpy.GetMessages())
        addMsgAndPrint(
            "Failed to create feature class "
            + featureClass
            + " in dataset "
            + featureDataSet
        )


def addTracking(tfc):
    if arcpy.Exists(tfc):
        addMsgAndPrint("    Enabling edit tracking in " + tfc)
        try:
            arcpy.EnableEditorTracking_management(
                tfc,
                "created_user",
                "created_date",
                "last_edited_user",
                "last_edited_date",
                "ADD_FIELDS",
                "DATABASE_TIME",
            )
        except:
            addMsgAndPrint(tfc)
            addMsgAndPrint(arcpy.GetMessages(2))


def cartoRepsExistAndLayer(fc):
    crPath = os.path.join(os.path.dirname(sys.argv[0]), "../Resources/CartoRepsAZGS")
    hasReps = False
    repLyr = ""
    for repFc in "ContactsAndFaults", "GeologicLines", "OrientationPoints":
        if fc.find(repFc) > -1:
            hasReps = True
            repLyr = os.path.join(crPath, repFc + ".lyr")
    return hasReps, repLyr


def rename_field(defs, start_name, end_name):
    """renames a field in a list generated from tableDict for
    special cases; CrossSections and OrientationPoints
    instead of using AlterField after creation which was throwing errors"""
    f_list = copy.deepcopy(defs)
    list_item = [
        n for n in f_list if n[0] == start_name
    ]  # finds ['MapUnitPolys_ID', 'String', 'NoNulls', 50], for instance
    i = f_list.index(list_item[0])  # finds the index of that item
    f_list[i][0] = end_name  # changes the name in the list
    arcpy.AddMessage(f_list[i][0] + " becoming " + end_name)
    arcpy.AddMessage(f_list)
    return f_list


def main(thisDB, coordSystem, nCrossSections):
    # create feature dataset GeologicMap
    addMsgAndPrint("  Creating feature dataset GeologicMap...")
    try:
        arcpy.CreateFeatureDataset_management(thisDB, "GeologicMap", coordSystem)
    except:
        addMsgAndPrint(arcpy.GetMessages(2))

    # create feature classes in GeologicMap
    # poly feature classes
    featureClasses = ["MapUnitPolys"]
    for fc in ["DataSourcePolys", "MapUnitOverlayPolys", "OverlayPolys"]:
        if fc in OptionalElements:
            featureClasses.append(fc)
    for featureClass in featureClasses:
        fieldDefs = tableDict[featureClass]
        if addLTYPE and fc != "DataSourcePolys":
            fieldDefs.append(["PTYPE", "String", "NullsOK", 50])
        createFeatureClass(thisDB, "GeologicMap", featureClass, "POLYGON", fieldDefs)

    # line feature classes
    featureClasses = ["ContactsAndFaults"]
    for fc in ["GeologicLines", "CartographicLines", "IsoValueLines", "MapUnitLines"]:
        if fc in OptionalElements:
            featureClasses.append(fc)

    for featureClass in featureClasses:
        fieldDefs = tableDict[featureClass]
        if featureClass in ["ContactsAndFaults", "GeologicLines"] and addLTYPE:
            fieldDefs.append(["LTYPE", "String", "NullsOK", 50])
        createFeatureClass(thisDB, "GeologicMap", featureClass, "POLYLINE", fieldDefs)

    # point feature classes
    featureClasses = []
    for fc in [
        "OrientationPoints",
        "GeochronPoints",
        "FossilPoints",
        "Stations",
        "GenericSamples",
        "GenericPoints",
        "MapUnitPoints",
    ]:
        if fc in OptionalElements:
            featureClasses.append(fc)
    for featureClass in featureClasses:
        """
        The following block of code was bypassing the MapUnitPoints definition now in GeMS_Definitions.py and
        appending PTYPE to the resulting feature class, along with the PTTYPE field appended in the
        next statement. I think we don't need it, but need to talk with Evan about this.
        If he concurs, will delete this block.
        Ralph Haugerud
        23 December 2020
        I agree -
                # the following if statement used to be here, but was removed at some point
                # putting it back to allow for creation of MapUnitPoints after discussion
                # with Luke Blair - Evan Thoms
                if featureClass == 'MapUnitPoints':
                    fieldDefs = tableDict['MapUnitPolys']
                    if addLTYPE:
                        fieldDefs.append(['PTYPE','String','NullsOK',50])
                else:
                    fieldDefs = tableDict[featureClass]
                    if addLTYPE and featureClass in ['OrientationPoints']:
                        fieldDefs.append(['PTTYPE','String','NullsOK',50])
                # end of re-inserted if statement
        """
        fieldDefs = tableDict[featureClass]
        if addLTYPE:
            fieldDefs.append(["PTTYPE", "String", "NullsOK", 50])
        createFeatureClass(thisDB, "GeologicMap", featureClass, "POINT", fieldDefs)

    # create feature dataset CorrelationOfMapUnits
    if "CorrelationOfMapUnits" in OptionalElements:
        addMsgAndPrint("  Creating feature dataset CorrelationOfMapUnits...")
        arcpy.CreateFeatureDataset_management(
            thisDB, "CorrelationOfMapUnits", coordSystem
        )
        fieldDefs = tableDict["CMUMapUnitPolys"]
        createFeatureClass(
            thisDB, "CorrelationOfMapUnits", "CMUMapUnitPolys", "POLYGON", fieldDefs
        )
        fieldDefs = tableDict["CMULines"]
        createFeatureClass(
            thisDB, "CorrelationOfMapUnits", "CMULines", "POLYLINE", fieldDefs
        )
        fieldDefs = tableDict["CMUPoints"]
        createFeatureClass(
            thisDB, "CorrelationOfMapUnits", "CMUPoints", "POINT", fieldDefs
        )

    # create CrossSections
    if nCrossSections > 26:
        nCrossSections = 26
    if nCrossSections < 0:
        nCrossSections = 0
    # note space in position 0
    alphabet = " ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    for n in range(1, nCrossSections + 1):
        xsLetter = alphabet[n]
        xsName = "CrossSection" + xsLetter
        xsN = "CS" + xsLetter
        addMsgAndPrint("  Creating feature data set CrossSection" + xsLetter + "...")
        arcpy.CreateFeatureDataset_management(thisDB, xsName, coordSystem)
        muDefs = rename_field(
            tableDict["MapUnitPolys"], "MapUnitPolys_ID", xsN + "MapUnitPolys_ID"
        )

        createFeatureClass(thisDB, xsName, xsN + "MapUnitPolys", "POLYGON", muDefs)
        cfDefs = rename_field(
            tableDict["ContactsAndFaults"],
            "ContactsAndFaults_ID",
            xsN + "ContactsAndFaults_ID",
        )
        createFeatureClass(
            thisDB, xsName, xsN + "ContactsAndFaults", "POLYLINE", cfDefs
        )

        if "OrientationPoints" in OptionalElements:
            opDefs = rename_field(
                tableDict["OrientationPoints"],
                "OrientationPoints_ID",
                xsN + "OrientationPoints_ID",
            )
            createFeatureClass(
                thisDB, xsName, xsN + "OrientationPoints", "POINT", opDefs
            )

    # create tables
    tables = ["DescriptionOfMapUnits", "DataSources", "Glossary"]
    for tb in [
        "RepurposedSymbols",
        "StandardLithology",
        "GeologicEvents",
        "MiscellaneousMapInformation",
    ]:
        if tb in OptionalElements:
            tables.append(tb)
    for table in tables:
        addMsgAndPrint("  Creating table " + table + "...")
        try:
            arcpy.CreateTable_management(thisDB, table)
            fieldDefs = tableDict[table]
            for fDef in fieldDefs:
                try:
                    if fDef[1] == "String":
                        arcpy.AddField_management(
                            thisDB + "/" + table,
                            fDef[0],
                            transDict[fDef[1]],
                            "#",
                            "#",
                            fDef[3],
                            "#",
                            transDict[fDef[2]],
                        )
                    else:
                        arcpy.AddField_management(
                            thisDB + "/" + table,
                            fDef[0],
                            transDict[fDef[1]],
                            "#",
                            "#",
                            "#",
                            "#",
                            transDict[fDef[2]],
                        )
                except:
                    addMsgAndPrint(
                        "Failed to add field " + fDef[0] + " to table " + table
                    )
                    addMsgAndPrint(arcpy.GetMessages(2))
        except:
            addMsgAndPrint(arcpy.GetMessages())

    ### GeoMaterials
    addMsgAndPrint("  Setting up GeoMaterialsDict table and domains...")
    #  Copy GeoMaterials table
    scripts_f = os.path.dirname(__file__)
    geomat_csv = os.path.join(scripts_f, "GeoMaterialDict.csv")
    arcpy.TableToTable_conversion(geomat_csv, thisDB, "GeoMaterialDict")

    #   make GeoMaterials domain
    arcpy.TableToDomain_management(
        thisDB + "/GeoMaterialDict",
        "GeoMaterial",
        "IndentedName",
        thisDB,
        "GeoMaterials",
    )
    #   attach it to DMU field GeoMaterial
    arcpy.AssignDomainToField_management(
        thisDB + "/DescriptionOfMapUnits", "GeoMaterial", "GeoMaterials"
    )
    #  Make GeoMaterialConfs domain, attach it to DMU field GeoMaterialConf
    arcpy.CreateDomain_management(
        thisDB, "GeoMaterialConfidenceValues", "", "TEXT", "CODED"
    )
    for val in GeoMaterialConfidenceValues:
        arcpy.AddCodedValueToDomain_management(
            thisDB, "GeoMaterialConfidenceValues", val, val
        )
    arcpy.AssignDomainToField_management(
        thisDB + "/DescriptionOfMapUnits",
        "GeoMaterialConfidence",
        "GeoMaterialConfidenceValues",
    )

    # Confidence domains, Glossary entries, and DataSources entry
    if addConfs:
        addMsgAndPrint(
            "  Adding standard ExistenceConfidence and IdentityConfidence domains"
        )
        #  create domain, add domain values, and link domain to appropriate fields
        addMsgAndPrint("    Creating domain, linking domain to appropriate fields")
        arcpy.CreateDomain_management(
            thisDB, "ExIDConfidenceValues", "", "TEXT", "CODED"
        )
        for item in DefaultExIDConfidenceValues:  # items are [term, definition, source]
            code = item[0]
            arcpy.AddCodedValueToDomain_management(
                thisDB, "ExIDConfidenceValues", code, code
            )
        arcpy.env.workspace = thisDB
        dataSets = arcpy.ListDatasets()
        for ds in dataSets:
            arcpy.env.workspace = thisDB + "/" + ds
            fcs = arcpy.ListFeatureClasses()
            for fc in fcs:
                fieldNames = fieldNameList(fc)
                for fn in fieldNames:
                    if fn in (
                        "ExistenceConfidence",
                        "IdentityConfidence",
                        "ScientificConfidence",
                    ):
                        # addMsgAndPrint('    '+ds+'/'+fc+':'+fn)
                        arcpy.AssignDomainToField_management(
                            thisDB + "/" + ds + "/" + fc, fn, "ExIDConfidenceValues"
                        )
        # add definitions of domain values to Glossary
        addMsgAndPrint("    Adding domain values to Glossary")
        ## create insert cursor on Glossary
        cursor = arcpy.da.InsertCursor(
            thisDB + "/Glossary", ["Term", "Definition", "DefinitionSourceID"]
        )
        for item in DefaultExIDConfidenceValues:
            cursor.insertRow((item[0], item[1], item[2]))
        del cursor
        # add definitionsource to DataSources
        addMsgAndPrint("    Adding definition source to DataSources")
        ## create insert cursor on DataSources
        cursor = arcpy.da.InsertCursor(
            thisDB + "/DataSources", ["DataSources_ID", "Source", "URL"]
        )
        cursor.insertRow(
            (
                "FGDC-STD-013-2006",
                "Federal Geographic Data Committee [prepared for the Federal Geographic Data Committee by the U.S. Geological Survey], 2006, FGDC Digital Cartographic Standard for Geologic Map Symbolization: Reston, Va., Federal Geographic Data Committee Document Number FGDC-STD-013-2006, 290 p., 2 plates.",
                "https://ngmdb.usgs.gov/fgdc_gds/geolsymstd.php",
            )
        )
        del cursor

    # if cartoReps, add cartographic representations to all feature classes
    # trackEdits, add editor tracking to all feature classes and tables
    if cartoReps or trackEdits:
        arcpy.env.workspace = thisDB
        tables = arcpy.ListTables()
        datasets = arcpy.ListDatasets()
        for dataset in datasets:
            addMsgAndPrint("  Dataset " + dataset)
            arcpy.env.workspace = thisDB + "/" + dataset
            fcs = arcpy.ListFeatureClasses()
            for fc in fcs:
                hasReps, repLyr = cartoRepsExistAndLayer(fc)
                if cartoReps and hasReps:
                    addMsgAndPrint("    Adding cartographic representations to " + fc)
                    try:
                        arcpy.AddRepresentation_cartography(
                            fc,
                            fc + "_rep1",
                            "RuleID1",
                            "Override1",
                            default,
                            repLyr,
                            "NO_ASSIGN",
                        )
                        """
                            Note the 1 suffix on the representation name (fc+'_rep1') and the RuleID1 and Override1 fields.
                        If at some later time we wish to add additional representations to a feature class, each will
                        require it's own RuleID and Override fields which may be identified, and tied to the appropriate
                        representation, by suffixes 2, 3, ...
                            Naming representations fc+'_rep'+str(n) should be sufficient to identify each representation in a 
                        geodatabase uniquely, and allow for multiple representations within a single feature class.
                            It appears that ArcGIS provides no means of scripting an inventory of representations within
                        feature class or geodatabase. So, the convenience of establishing a coded-value domain that ties
                        representation rule IDs (consecutive integers) to some sort of useful text identifier becomes a
                        necessity for flagging the presence of a representation: One CAN script the inventory of domains
                        in a geodatabase. Run arcpy.da.ListDomains. Check the result for names of the form
                        <featureClassName>_rep??_Rule and voila, you've got a list of representations (and their associated
                        feature classes) in the geodatabase.
                            Moral: If you add a representation, be sure to add an associated coded-value domain and name
                        it appropriately!
                        """
                    except:
                        addMsgAndPrint(arcpy.GetMessages(2))
                if trackEdits:
                    addTracking(os.path.join(thisDB, fc))
        if trackEdits:
            addMsgAndPrint("  Tables ")
            arcpy.env.workspace = thisDB
            for aTable in tables:
                if aTable != "GeoMaterialDict":
                    addTracking(os.path.join(thisDB, aTable))


def createDatabase(outputDir, thisDB):
    addMsgAndPrint("  Creating geodatabase " + thisDB + "...")
    if arcpy.Exists(outputDir + "/" + thisDB):
        addMsgAndPrint("  Geodatabase " + thisDB + " already exists.")
        addMsgAndPrint("   forcing exit with error")
        raise arcpy.ExecuteError
    try:
        # removed check for mdb. Personal geodatabases are out - ET
        if thisDB[-4:] == ".gdb":
            arcpy.CreateFileGDB_management(outputDir, thisDB)
        return True
    except:
        addMsgAndPrint("Failed to create geodatabase " + outputDir + "/" + thisDB)
        addMsgAndPrint(arcpy.GetMessages(2))
        return False


#########################################

addMsgAndPrint(versionString)

if len(sys.argv) >= 6:
    addMsgAndPrint("Starting script")

    outputDir = sys.argv[1]
    if outputDir == "#":
        outputDir = os.getcwd()
    outputDir = outputDir.replace("\\", "/")

    thisDB = sys.argv[2]
    thisDB = thisDB + ".gdb"

    coordSystem = sys.argv[3]

    if sys.argv[4] == "#":
        OptionalElements = []
    else:
        OptionalElements = sys.argv[4].split(";")
    if debug:
        addMsgAndPrint(f"Optional elements = {OptionalElements}")

    nCrossSections = int(sys.argv[5])

    try:
        if sys.argv[6] == "true":
            trackEdits = True
        else:
            trackEdits = False
    except:
        trackEdits = False

    if arcpy.GetInstallInfo()["Version"] < "10.1":
        trackEdits = False

    try:
        if sys.argv[7] == "true":
            cartoReps = True
        else:
            cartoReps = False
    except:
        cartoReps = False

    try:
        if sys.argv[8] == "true":
            addLTYPE = True
        else:
            addLTYPE = False
    except:
        addLTYPE = False

    try:
        if sys.argv[9] == "true":
            addConfs = True
        else:
            addConfs = False
    except:
        addConfs = False

    # create gdb in output directory and run main routine
    if createDatabase(outputDir, thisDB):
        thisDB = os.path.join(outputDir, thisDB)
        # Arc 10 version refreshed ArcCatalog here, but there is no equivalent with AGPro
        main(thisDB, coordSystem, nCrossSections)

    # try to write a readme within the .gdb
    if thisDB[-4:] == ".gdb":
        try:
            writeLogfile(thisDB, "Geodatabase created by " + versionString)
        except:
            addMsgAndPrint("Failed to write to" + thisDB + "/00log.txt")

else:
    addMsgAndPrint(usage)
