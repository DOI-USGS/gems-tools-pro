# Parses a well-formatted Description of Map Units document from a .docx file into a
# DescriptionOfMapUnits table in a GeMS geodatabase.
#
# Updated May 20 2019 to work with Python 3 in ArcGIS Pro 2: Evan Thoms
#   First ran the script through 2to3 which catches many syntactical differences between
#   2.7 and 3 and then manually debugged the few remaining errors having to do with the Python 3
#   management of strings and built-in UTF encoding.
#
#   Tested against a .docx made from the Description of Map Units section in
#   USGS Pubs template MapManuscript_v1-0_04-11.dotx which ran with no errors but
#   different DMU documents may still contain formatting or objects which throw errors.

import sys
import copy
import arcpy
import GeMS_utilityFunctions as guf
import docxModified as docxm

from importlib import reload

reload(docxm)

versionString = "GeMS_DocxToDMU.py, version of 1/18/24"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_DocxToDMU.py"
guf.checkVersion(versionString, rawurl, "gems-tools-pro")

debug = False

# the document.xml file in the .docx archive saves the style id value, not name which is more like
# an alias. Either works for building a word file, but when going from docx to dmu table, we'll save the
# the name to be consistent with what is seen in Word.
style_dict = {
    "DMUUnit11stafterheading": "DMU Unit 1 (1st after heading)",
    "DMU-Heading1": "DMU-Heading1",
    "DMUUnit1": "DMU Unit 1",
    "DMU-Heading2": "DMU-Heading2",
    "DMU-Heading3": "DMU-Heading3",
    "DMU-Heading4": "DMU-Heading4",
    "DMU-Heading5": "DMU-Heading5",
    "DMUUnit2": "DMU Unit 2",
    "DMUParagraph": "DMU Paragraph",
    "DMUUnit3": "DMU Unit 3",
    "DMUUnit4": "DMU Unit 4",
    "DMUUnit5": "DMU Unit 5",
    "DMUHeadnote": "DMU Headnote",
    "DMUUnitLabeltypestyle": "DMU Unit Label (type style)",
    "DMUUnitNameAgetypestyle": "DMU Unit Name/Age (type style)",
}

style_dict = {
    "DMU-Heading1": "DMUHead1Back",
    "DMU-Heading2": "DMUHead2",
    "DMU-Heading3": "DMUHead3",
    "DMU-Heading4": "DMUHead4",
    "DMU-Heading5": "DMUHead5",
    "DMU Headnote": "DMUBodyPara",
    "DMUParagraph": "DMUBodyPara",
    "DMU Unit 1": "DMU1",
    "DMU Unit 1 (1st after heading)": "DMU1",
    "DMUUnit11stafterheading": "DMU1",
    "DMU Unit 2": "DMU2",
    "DMU Unit 3": "DMU3",
    "DMU Unit 4": "DMU4",
    "DMU Unit 5": "DMU5",
    "DMUUnit1": "DMU1",
    "DMUUnit2": "DMU2",
    "DMUUnit3": "DMU3",
    "DMUUnit4": "DMU4",
    "DMUUnit5": "DMU5",
}


def styleType(paraStyle):
    if paraStyle.find("DMUUnit") > -1:
        return "Unit"
    if paraStyle.find("DMU-Heading") > -1:
        return "Heading"
    if paraStyle.find("Headnote") > -1:
        return "Headnote"
    if paraStyle.find("Paragraph") > -1:
        return "DMU Paragraph"
    else:
        return "??"


def parseUnitPara(para):
    # get the label including any formatting tags
    label, x, unit_age_desc = para.partition(" ")

    # try to partition the unit name(age) from the description
    # for this, we are counting on the description starting after an emdash or hyphen
    # if double-hyphen, the second will be stripped below
    # more delimiters can be added to this tuple
    dashes = ("\u2014", "\u002d\u002d")

    # dictionary of {character: index} in string if found
    dash_dict = {d: para.find(d) for d in dashes if para.find(d) > -1}

    # if the dictionary is empty, there are no dash delimiters
    if dash_dict:
        # but if there are, get the dash character closest to the beginning of the string (the minimum value),
        # this should be the name(age)/description delimiter
        dash = min(dash_dict, key=dash_dict.get)
        name_age, x, desc = unit_age_desc.partition(dash)

        # if it's a double hyphen, there will still be one left right now, strip it
        desc = desc.strip("-")
        # strip whitespace
        desc = desc.strip()
    else:
        # if there are no dashes, there is only a name(age) string
        name_age = unit_age_desc
        desc = None

    # if there are parantheses, we have an age
    # partition on the first one to get the unit name
    if name_age.find("(") > 0:
        name, x, age = name_age.partition("(")

        # and nothing should follow the age except the em-dash and description
        # so strip the trailing ")"
        age = age.strip(")")
    else:
        age = None
        name = name_age

    # remove formatting tags
    for fmt in ("<b>", "</b>", "<g>", "</g>", "<ul>", "</ul>"):
        if label:
            label = label.replace(fmt, "").strip()
        if name:
            name = name.replace(fmt, "").strip()
        if age:
            age = age.replace(fmt, "").strip()

    return label, name, age, desc


def main(params):
    manuscriptFile = params[0]
    gdb = params[1]
    zero_pad = 3
    if len(params) > 2:
        zero_pad = int(params[2])

    guf.addMsgAndPrint(versionString)
    guf.addMsgAndPrint("Parsing file " + manuscriptFile)

    document = docxm.opendocx(manuscriptFile)
    paragraphList = docxm.getDMUdocumenttext(document)
    msRows = []
    labels = []

    i = 0
    for paragraph in paragraphList:  # each paragraph is a list: [style name, text]
        paraStyle = paragraph[0]
        label = ""
        name = ""
        age = ""
        description = ""

        # If this is a DMU paragraph style and not "DESCRIPTION OF MAP UNITS"
        if paraStyle.startswith("DMU") and paraStyle != "DMU-Heading1":
            paraText = paragraph[1]

            if styleType(paraStyle) == "DMU Paragraph":
                msRows[i - 1][3] = msRows[i - 1][3] + " <br>" + paraText
            else:
                if styleType(paraStyle) == "Unit":
                    label, name, age, description = parseUnitPara(paraText)
                    if label and not label in labels:
                        labels.append(label)
                    elif label in labels:
                        guf.addMsgAndPrint("NON-UNIQUE VALUE OF LABEL: " + label)
                        guf.addMsgAndPrint("  Fix it and re-run!")
                        sys.exit()

                elif styleType(paraStyle) == "Heading":
                    name = paraText
                elif styleType(paraStyle) == "Headnote":
                    description = paraText[
                        1:-1
                    ]  # subtract beginning and ending brackets
                else:
                    guf.addMsgAndPrint("Unrecognized paragraph style")
                    guf.addMsgAndPrint(paraStyle)
                    guf.addMsgAndPrint(paraText)
                    sys.exit()

                msRows.append([label, name, age, description, paraStyle])
                i = i + 1

    if i == 0:
        guf.addMsgAndPrint("Did not find any paragraphs with DMU styles!")
        guf.addMsgAndPrint(" Is this the right Word document?")
        sys.exit()

    # build hKeys
    hKeys = []
    hKeys.append([1])

    # set 0th element
    # hKeyStyleDict = {hkey: style}
    hKeyStyleDict = {}
    hKeyStyleDict[str(hKeys[0])] = msRows[0][4]
    lastHKey = copy.deepcopy(hKeys[0])
    last_heading = ""
    for n in range(1, len(msRows)):
        row = msRows[n]
        # find previous row of higher rank
        while rankParaStyle2IsHigher(hKeyStyleDict[str(lastHKey)], row[4]):
            lastHKey = lastHKey[0:-1]  # remove last element

        if rankParaStylesAreEqual(
            hKeyStyleDict[str(lastHKey)], row[4]
        ):  # is sibling to lastHKey
            # increment last element in lastHKey by 1
            nLast = len(lastHKey) - 1
            lastElement = lastHKey[nLast] + 1
            lastHKey[nLast] = lastElement
            if zero_pad < len(str(lastElement)):
                zero_pad = len(str(lastElement))
        else:  # is child to lastHKey
            lastHKey.append(1)
        hKeys.append(copy.deepcopy(lastHKey))
        hKeyStyleDict[str(hKeys[n])] = row[4]
        lastHKey = copy.deepcopy(hKeys[n])

    # translate hKeys from lists of integers to zero-padded strings
    # with '-' as separator and append to row
    for n in range(len(msRows)):
        newHKey = []
        for element in hKeys[n]:
            newHKey.append(str(element).zfill(zero_pad))
        msRows[n].append("-".join(newHKey))

    # print results
    for row in msRows:
        guf.addMsgAndPrint(f"  {row[0]} | {row[1]} | {row[2]}")
        guf.addMsgAndPrint(f"    ParagraphStyle = {row[4]}")
        guf.addMsgAndPrint(f"    HierarchyKey = {row[5]}")

        guf.addMsgAndPrint("")
        guf.addMsgAndPrint(f"Updating table DescriptionOfMapUnits in {gdb}")

    #### Now, to move results into the geodatabase
    # build msRowLabelDict, msRowNameDict, msRowDescDict
    msRowLabelDict = {}
    msRowNameDict = {}
    msRowDescDict = {}
    msRowMapUnitDict = {}
    for i in range(len(msRows)):
        sType = styleType(msRows[i][4])
        if sType == "Unit":
            msRowLabelDict[msRows[i][0]] = i
            msRowMapUnitDict[msRows[i][0]] = i
        if sType == "Heading":
            msRowNameDict[msRows[i][1]] = i
        if sType == "Headnote":
            msRowDescDict[msRows[i][3][0:20]] = i

    # open updateCursor on DMU table
    msRowsMatched = []
    dmuRows = arcpy.UpdateCursor(gdb + "/DescriptionOfMapUnits")
    # step through DMU table, trying to match label or Name or Description
    # if DMU row matches msRow, append msRow number to msRowsMatched
    guf.addMsgAndPrint("Updating any matching rows in DescriptionOfMapUnits")
    i = 1
    for row in dmuRows:
        matchRow = -1
        if row.Label != "" and row.Label in msRowLabelDict:
            matchRow = msRowLabelDict[row.Label]
        elif row.Name != "" and row.Name in msRowNameDict:
            matchRow = msRowNameDict[row.Name]
        elif row.MapUnit != "" and row.MapUnit in msRowMapUnitDict:
            matchRow = msRowNameDict[row.MapUnit]
        elif (
            row.Description != None
            and row.Description != ""
            and row.Description[0:20] in msRowDescDict
        ):
            matchRow = msRowDescDict[row.Description[0:20]]
        else:
            guf.addMsgAndPrint(
                "  DMU row " + str(i) + ", label = " + str(row.Label) + " has no match"
            )
        if matchRow > -1:
            guf.addMsgAndPrint("  updating DMU row " + str(i))
            msRowsMatched.append(matchRow)
            row.Label = msRows[matchRow][0]
            if row.MapUnit == "" or row.MapUnit == None or row.MapUnit == " ":
                row.MapUnit = row.Label
            row.Name = msRows[matchRow][1]
            row.Age = msRows[matchRow][2]
            row.Description = msRows[matchRow][3]
            row.ParagraphStyle = msRows[matchRow][4]
            row.HierarchyKey = msRows[matchRow][5]
            dmuRows.updateRow(row)
        i = i + 1
    del row
    del dmuRows

    # open insertion cursor on DMU table
    # step through msRows. If msRow number not in msRowsMatched,
    # insert row in DMU
    guf.addMsgAndPrint("Adding new rows to DescriptionOfMapUnits")
    dmuRows = arcpy.InsertCursor(gdb + "/DescriptionOfMapUnits")
    for i in range(len(msRows)):
        if not i in msRowsMatched:
            guf.addMsgAndPrint("  " + str(msRows[i])[:40] + "...")
            row = dmuRows.newRow()
            row.Label = msRows[i][0]
            row.MapUnit = msRows[i][0]
            row.Name = msRows[i][1]
            row.Age = msRows[i][2]
            row.Description = msRows[i][3]
            row.ParagraphStyle = style_dict[msRows[i][4]]
            row.HierarchyKey = msRows[i][5]
            try:
                dmuRows.insertRow(row)
            except:
                row.Description = ""
                dmuRows.insertRow(row)
    del dmuRows


if __name__ == "__main__":
    main(sys.argv[1:])
