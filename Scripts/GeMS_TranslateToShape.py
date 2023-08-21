#  GeMS_TranslateToShape_AGP2.py
#
#  Converts an GeMS-style ArcGIS geodatabase to
#    open file format
#      shape files, .csv files, and pipe-delimited .txt files,
#      without loss of information.  Field renaming is documented in
#      output file logfile.txt
#    simple shapefile format
#      basic map information in flat shapefiles, with much repetition
#      of attribute information, long fields truncated, and much
#      information lost. Field renaming is documented in output file
#      logfile.txt
#
#  Ralph Haugerud, USGS, Seattle
#    rhaugerud@usgs.gov

# 10 Dec 2017. Fixed bug that prevented dumping of not-GeologicMap feature datasets to OPEN version
# 27 June 2019. Many fixes when investigating Issue 30 (described at master github repo)
# 18 July 2019. Just a few syntax edits to make it usable in ArcGIS Pro with Python 3
#  renamed to GeMS_TranslateToShape_AGP2.py

import arcpy
import sys, os, glob, time
import datetime
import glob
from GeMS_utilityFunctions import *
from numbers import Number

versionString = "GeMS_TranslateToShape.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_TranslateToShape.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

debug = False

# equivalentFraction is used to rank ProportionTerms from most
#  abundant to least
equivalentFraction = {
    "all": 1.0,
    "only part": 1.0,
    "dominant": 0.6,
    "major": 0.5,
    "significant": 0.4,
    "subordinate": 0.3,
    "minor": 0.25,
    "trace": 0.05,
    "rare": 0.02,
    "variable": 0.01,
    "present": 0.0,
}


def usage():
    addMsgAndPrint(
        """
USAGE: GeMS_TranslateToShp_Arc10.5.py  <geodatabase> <outputWorkspace>
  where <geodatabase> must be an existing ArcGIS geodatabase.
  <geodatabase> may be a personal or file geodatabase, and the 
  .gdb or .mdb extension must be included.
  Output is written to directories <geodatabase (no extension)>-simple
  and <geodatabase (no extension)>-open in <outputWorkspace>. Output 
  directories, if they already exist, will be overwritten.
"""
    )


shortFieldNameDict = {
    "IdentityConfidence": "IdeConf",
    "MapUnitPolys_ID": "MUPs_ID",
    "Description": "Descr",
    "HierarchyKey": "HKey",
    "ParagraphStyle": "ParaSty",
    "AreaFillRGB": "RGB",
    "AreaFillPatternDescription": "PatDes",
    "GeoMaterial": "GeoMat",
    "GeoMaterialConfidence": "GeoMatConf",
    "IsConcealed": "IsCon",
    "LocationConfidenceMeters": "LocConfM",
    "ExistenceConfidence": "ExiConf",
    "ContactsAndFaults_ID": "CAFs_ID",
    "PlotAtScale": "PlotAtSca",
}

forget = ["objectid", "shape", "ruleid", "ruleid_1", "override"]

joinTablePrefixDict = {
    "DescriptionOfMapUnits_": "DMU",
    "DataSources_": "DS",
    "Glossary_": "GL",
}


def lookup_prefix(f_name):
    for table in joinTablePrefixDict.keys():
        if f_name.find(table) == 0:
            return joinTablePrefixDict[table]
    else:
        return ""


def remapFieldName(name):
    if name in shortFieldNameDict:
        return shortFieldNameDict[name]
    elif len(name) <= 10:
        return name
    else:
        name2 = name.replace("And", "")
        name2 = name2.replace("Of", "")
        name2 = name2.replace("Unit", "Un")
        name2 = name2.replace("Source", "Src")
        name2 = name2.replace("Shape", "Shp")
        name2 = name2.replace("shape", "Shp")
        name2 = name2.replace("SHAPE", "Shp")
        name2 = name2.replace("Hierarchy", "H")
        name2 = name2.replace("Description", "Descript")
        name2 = name2.replace("AreaFill", "")
        name2 = name2.replace("Structure", "Struct")
        name2 = name2.replace("STRUCTURE", "STRUCT")
        name2 = name2.replace("user", "Usr")
        name2 = name2.replace("created_", "Cre")
        name2 = name2.replace("edited_", "Ed")
        name2 = name2.replace("date", "Dt")
        name2 = name2.replace("last_", "Lst")

        newName = ""
        for i in range(0, len(name2)):
            if name2[i] == name2[i].upper():
                newName = newName + name2[i]
                j = 1
            else:
                j = j + 1
                if j < 4:
                    newName = newName + name2[i]
        if len(newName) > 10:
            if newName[1:3] == newName[1:3].lower():
                newName = newName[0] + newName[3:]
        if len(newName) > 10:
            if newName[3:5] == newName[3:5].lower():
                newName = newName[0:2] + newName[5:]
        if len(newName) > 10:
            # as last resort, just truncate to 10 characters
            # might be a duplicate, but exporting to shapefile will add numbers to the
            # duplicates. Those names just won't match what will be recorded in the logfile
            newName = newName[:10]
        return newName


def check_unique(fieldmappings):
    out_names = [fm.outputField.name for fm in fieldmappings]
    dup_names = set([x for x in out_names if out_names.count(x) > 1])
    for dup_name in dup_names:
        i = 0
        for fm in fieldmappings:
            if fm.outputField.name == dup_name:
                prefix = lookup_prefix(fm.getInputFieldName(0))
                new_name = remapFieldName(prefix + dup_name)
                out_field = fm.outputField
                out_field.name = new_name
                fm.outputField = out_field
                fieldmappings.replaceFieldMap(i, fm)
            i = i + 1


def dumpTable(fc, outName, isSpatial, outputDir, logfile, isOpen, fcName):
    dumpString = "  Dumping {}...".format(outName)
    if isSpatial:
        dumpString = "  " + dumpString
    addMsgAndPrint(dumpString)
    if isSpatial:
        logfile.write("  feature class {} dumped to shapefile {}\n".format(fc, outName))
    else:
        logfile.write("  table {} dumped to table\n".format(fc, outName))
    logfile.write("    field name remapping: \n")

    longFields = []
    fieldmappings = arcpy.FieldMappings()
    fields = arcpy.ListFields(fc)
    for field in fields:
        # get the name string and chop off the joined table name if necessary
        fName = field.name
        for prefix in ("DescriptionOfMapUnits", "DataSources", "Glossary", fcName):
            if fc != prefix and fName.find(prefix) == 0 and fName != fcName + "_ID":
                fName = fName[len(prefix) + 1 :]

        if not fName.lower() in forget:
            # make the FieldMap object based on this field
            fieldmap = arcpy.FieldMap()
            fieldmap.addInputField(fc, field.name)
            out_field = fieldmap.outputField

            # go back to the FieldMap object and set up the output field name
            out_field.name = remapFieldName(fName)
            fieldmap.outputField = out_field
            # logfile.write('      '+field.name+' > '+out_field.name+'\n')

            # save the FieldMap in the FieldMappings
            fieldmappings.addFieldMap(fieldmap)

        if field.length > 254:
            longFields.append(fName)

    check_unique(fieldmappings)
    for fm in fieldmappings:
        logfile.write(
            "      {} > {}\n".format(fm.getInputFieldName(0), fm.outputField.name)
        )

    if isSpatial:
        if debug:
            addMsgAndPrint("dumping ", fc, outputDir, outName)
        try:
            arcpy.FeatureClassToFeatureClass_conversion(
                fc, outputDir, outName, field_mapping=fieldmappings
            )
        except:
            addMsgAndPrint("failed to translate table " + fc)
    else:
        arcpy.TableToTable_conversion(
            fc, outputDir, outName, field_mapping=fieldmappings
        )

    if isOpen:
        # if any field lengths > 254, write .txt file
        if len(longFields) > 0:
            outText = outName[0:-4] + ".txt"
            logfile.write(
                "    table "
                + fc
                + " has long fields, thus dumped to file "
                + outText
                + "\n"
            )
            csv_path = os.path.join(outputDir, outText)
            csvFile = open(csv_path, "w")
            fields = arcpy.ListFields(fc)
            f_names = [
                f.name for f in fields if f.type not in ["Blob", "Geometry", "Raster"]
            ]

            col_names = "|".join(f_names)
            csvFile.write("{}\n|".format(col_names))
            # addMsgAndPrint("FC name: "+ fc)
            with arcpy.da.SearchCursor(fc, f_names) as cursor:
                for row in cursor:
                    rowString = str(row[0])
                    for i in range(1, len(row)):  # use enumeration here?
                        # if debug: addMsgAndPrint("Index: "+str(i))
                        # if debug: addMsgAndPrint("Current row is: " + str(row[i]))
                        if row[i] != None:
                            xString = str(row[i])
                            if isinstance(row[i], Number) or isinstance(
                                row[i], datetime.datetime
                            ):
                                xString = str(row[i])
                            else:
                                # if debug: addMsgAndPrint("Current row type is: " + str(type(row[i])))
                                xString = row[i].encode("ascii", "xmlcharrefreplace")
                            # rowString = rowString+'|'+xString
                        else:
                            rowString = rowString + "|"
                    csvFile.write(rowString + "\n")
            csvFile.close()
    addMsgAndPrint("    Finished dump\n")


def makeOutputDir(gdb, outWS, isOpen):
    outputDir = os.path.join(outWS, os.path.basename(gdb)[0:-4])
    if isOpen:
        outputDir = outputDir + "-open"
    else:
        outputDir = outputDir + "-simple"
    addMsgAndPrint("  Making {}...".format(outputDir))
    if os.path.exists(outputDir):
        arcpy.Delete_management(outputDir)
    os.mkdir(outputDir)
    logfile = open(os.path.join(outputDir, "logfile.txt"), "w")
    logfile.write("file written by " + versionString + "\n\n")
    return outputDir, logfile


def dummyVal(pTerm, pVal):
    if pVal == None:
        if pTerm in equivalentFraction:
            return equivalentFraction[pTerm]
        else:
            return 0.0
    else:
        return pVal


def description(unitDesc):
    unitDesc.sort()
    unitDesc.reverse()
    desc = ""
    for uD in unitDesc:
        if uD[3] == "":
            desc = desc + str(uD[4]) + ":"
        else:
            desc = desc + uD[3] + ":"
        desc = desc + uD[2] + "; "
    return desc[:-2]


def makeStdLithDict():
    addMsgAndPrint("  Making StdLith dictionary...")
    stdLithDict = {}
    rows = arcpy.searchcursor("StandardLithology", "", "", "", "MapUnit")
    row = rows.next()
    unit = row.getValue("MapUnit")
    unitDesc = []
    pTerm = row.getValue("ProportionTerm")
    pVal = row.getValue("ProportionValue")
    val = dummyVal(pTerm, pVal)
    unitDesc.append(
        [val, row.getValue("PartType"), row.getValue("Lithology"), pTerm, pVal]
    )
    while row:
        newUnit = row.getValue("MapUnit")
        if newUnit != unit:
            stdLithDict[unit] = description(unitDesc)
            unitDesc = []
            unit = newUnit
        pTerm = row.getValue("ProportionTerm")
        pVal = row.getValue("ProportionValue")
        val = dummyVal(pTerm, pVal)
        unitDesc.append(
            [val, row.getValue("PartType"), row.getValue("Lithology"), pTerm, pVal]
        )
        row = rows.next()
    del row, rows
    stdLithDict[unit] = description(unitDesc)
    return stdLithDict


def mapUnitPolys(stdLithDict, outputDir, logfile):
    addMsgAndPrint(
        "  Translating {}...".format(os.path.join("GeologicMap", "MapUnitPolys"))
    )
    try:
        arcpy.MakeTableView_management("DescriptionOfMapUnits", "DMU")
        if stdLithDict != "None":
            arcpy.AddField_management("DMU", "StdLith", "TEXT", "", "", "255")
            rows = arcpy.UpdateCursor("DMU")
            row = rows.next()
            while row:
                if row.MapUnit in stdLithDict:
                    row.StdLith = stdLithDict[row.MapUnit]
                    rows.updateRow(row)
                row = rows.next()
            del row, rows

        arcpy.MakeFeatureLayer_management("GeologicMap/MapUnitPolys", "MUP")
        arcpy.AddJoin_management("MUP", "MapUnit", "DMU", "MapUnit")
        arcpy.AddJoin_management("MUP", "DataSourceID", "DataSources", "DataSources_ID")

        arcpy.CopyFeatures_management("MUP", "MUP2")
        DM = "descriptionofmapunits_"
        DS = "datasources_"
        MU = "mapunitpolys_"
        delete_fields = [
            MU + "datasourceid",
            MU + MU + "id",
            DM + "mapunit",
            DM + "objectid",
            DM + DM + "id",
            DM + "label",
            DM + "symbol",
            DM + "descriptionsourceid",
            DS + "objectid",
            DS + DS + "id",
            DS + "notes",
        ]
        for f in arcpy.ListFields("MUP2"):
            if f.name.lower() in delete_fields:
                arcpy.DeleteField_management("MUP2", f.name)

        dumpTable(
            "MUP2", "MapUnitPolys.shp", True, outputDir, logfile, False, "MapUnitPolys"
        )
    except:
        addMsgAndPrint(arcpy.GetMessages())
        addMsgAndPrint("  Failed to translate MapUnitPolys")

    for lyr in ["DMU", "MUP", "MUP2"]:
        if arcpy.Exists(lyr):
            arcpy.Delete_management(lyr)


def linesAndPoints(fc, outputDir, logfile):
    addMsgAndPrint("  Translating {}...".format(fc))
    cp = fc.find("/")
    fcShp = fc[cp + 1 :] + ".shp"
    LIN2 = fc[cp + 1 :] + "2"
    LIN = "xx" + fc[cp + 1 :]

    # addMsgAndPrint('    Copying features from {} to {}'.format(fc, LIN2))
    arcpy.CopyFeatures_management(fc, LIN2)
    arcpy.MakeFeatureLayer_management(LIN2, LIN)
    fieldNames = fieldNameList(LIN)
    if "Type" in fieldNames:
        arcpy.AddField_management(LIN, "Definition", "TEXT", "#", "#", "254")
        arcpy.AddJoin_management(LIN, "Type", "Glossary", "Term")
        arcpy.CalculateField_management(
            LIN, "Definition", "!Glossary.Definition![0:254]", "PYTHON"
        )
        arcpy.RemoveJoin_management(LIN, "Glossary")

    # command below are 9.3+ specific
    sourceFields = arcpy.ListFields(fc, "*SourceID")
    for sField in sourceFields:
        nFieldName = sField.name[:-2]
        arcpy.AddField_management(LIN, nFieldName, "TEXT", "#", "#", "254")
        arcpy.AddJoin_management(LIN, sField.name, "DataSources", "DataSources_ID")
        arcpy.CalculateField_management(
            LIN, nFieldName, "!DataSources.Source![0:254]", "PYTHON"
        )
        arcpy.RemoveJoin_management(LIN, "DataSources")
        arcpy.DeleteField_management(LIN, sField.name)

    dumpTable(LIN2, fcShp, True, outputDir, logfile, False, fc[cp + 1 :])
    arcpy.Delete_management(LIN)
    arcpy.Delete_management(LIN2)


def main(gdbCopy, outWS, oldgdb):
    #
    # Simple version
    #
    isOpen = False
    addMsgAndPrint("")
    outputDir, logfile = makeOutputDir(oldgdb, outWS, isOpen)
    arcpy.env.workspace = gdbCopy

    if "StandardLithology" in arcpy.ListTables():
        stdLithDict = makeStdLithDict()
    else:
        stdLithDict = "None"
    mapUnitPolys(stdLithDict, outputDir, logfile)

    arcpy.env.workspace = os.path.join(gdbCopy, "GeologicMap")
    pointfcs = arcpy.ListFeatureClasses("", "POINT")
    linefcs = arcpy.ListFeatureClasses("", "LINE")
    arcpy.env.workspace = gdbCopy
    for fc in linefcs:
        linesAndPoints(fc, outputDir, logfile)
    for fc in pointfcs:
        linesAndPoints(fc, outputDir, logfile)
    logfile.close()
    #
    # Open version
    #
    isOpen = True
    outputDir, logfile = makeOutputDir(oldgdb, outWS, isOpen)

    # list featuredatasets
    arcpy.env.workspace = gdbCopy
    fds = arcpy.ListDatasets()

    # for each featuredataset
    for fd in fds:
        addMsgAndPrint("  Processing feature data set {}...".format(fd))
        logfile.write("Feature data set {}\n".format(fd))
        try:
            spatialRef = arcpy.Describe(fd).SpatialReference
            logfile.write("  spatial reference framework\n")
            logfile.write("    name = {}\n".format(spatialRef.Name))
            logfile.write("    spheroid = {}\n".format(spatialRef.SpheroidName))
            logfile.write("    projection = {}\n".format(spatialRef.ProjectionName))
            logfile.write("    units = {}\n".format(spatialRef.LinearUnitName))
        except:
            logfile.write("  spatial reference framework appears to be undefined\n")

        # generate featuredataset prefix
        pfx = ""
        for i in range(0, len(fd) - 1):
            if fd[i] == fd[i].upper():
                pfx = pfx + fd[i]

        arcpy.env.workspace = os.path.join(gdbCopy, fd)
        fcList = arcpy.ListFeatureClasses()
        if fcList != None:
            arcpy.AddMessage(fc)
            for fc in fcList:
                # don't dump Anno classes
                if arcpy.Describe(fc).featureType != "Annotation":
                    outName = "{}_{}.shp".format(pfx, fc)
                    dumpTable(fc, outName, True, outputDir, logfile, isOpen, fc)
                else:
                    addMsgAndPrint(
                        "    Skipping annotation feature class {}\n".format(fc)
                    )
        else:
            addMsgAndPrint("   No feature classes in this dataset!")
        logfile.write("\n")

    # list tables
    arcpy.env.workspace = gdbCopy
    for tbl in arcpy.ListTables():
        outName = tbl + ".csv"
        dumpTable(tbl, outName, False, outputDir, logfile, isOpen, tbl)
    logfile.close()


### START HERE ###
if (
    len(sys.argv) != 3
    or not os.path.exists(sys.argv[1])
    or not os.path.exists(sys.argv[2])
):
    usage()
else:
    addMsgAndPrint("  " + versionString)
    gdb = os.path.abspath(sys.argv[1])
    gdb_name = os.path.basename(gdb)
    ows = os.path.abspath(sys.argv[2])

    arcpy.env.qualifiedFieldNames = False
    arcpy.env.overwriteOutput = True

    # fix the new workspace name so it is guaranteed to be novel, no overwrite
    newgdb = os.path.join(ows, "xx{}".format(gdb_name))
    if arcpy.Exists(newgdb):
        arcpy.Delete_management(newgdb)
    addMsgAndPrint(
        "  Copying {} to temporary geodatabase".format(os.path.basename(gdb))
    )
    arcpy.Copy_management(gdb, newgdb)
    main(newgdb, ows, gdb)

    # cleanup
    addMsgAndPrint("\n  Deleting temporary geodatabase")
    try:
        arcpy.Delete_management(newgdb)
    except:
        addMsgAndPrint("    As usual, failed to delete temporary geodatabase")
        addMsgAndPrint("    Please delete " + newgdb + "\n")
