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

import sys, copy, arcpy
from GeMS_utilityFunctions import *
import docxModified as docxm

versionString = "GeMS_DocxToDMU.py, version of 8/21/23"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_DocxToDMU.py"
checkVersion(versionString, rawurl, "gems-tools-pro")

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
    arcpy.AddMessage(f"para = {para}")
    # get the  first word as unit label
    label, s, text = para.partition(" ")
    # look for emdash, hyphen, or colon that separates name(age) from description
    # unicodes, respectively, '\u2014', '\u002d', '\u003a'

    emDashStart = 0
    emDashEnd = 0
    dashes = ("\u2014", "\u002d", "\u003a")
    if any((match := c) in text for c in dashes):
        emDashStart = para.find(match)

        # now we have the index of the em-dash
        # find the next non-hyphen or space character and that
        # should be the start of the description
        for i, c in enumerate(para[emDashStart]):
            if not c != "-" and not c.isspace:
                emDashEnd = emDashStart + 1 + i
                break

    if emDashStart < 0:
        emDashStart = para.find("--")
        if emDashStart > 0:
            emDashEnd = emDashStart + 2
    if emDashStart > 0:  # there is either an emdash or two hyphens (--)
        desc = para[emDashEnd:]
        nameAge = para[len(label) : emDashStart]
    else:  # there is no emdash or two hyphens
        desc = ""
        nameAge = para[len(label) :]

    lParen = nameAge.find("(")
    if lParen < 0:  # no age in parentheses (age inherited from parent)
        name = nameAge.strip()
        age = ""
    else:
        name = nameAge[0:lParen].strip()
        rParen = nameAge.find(")")
        age = nameAge[lParen + 1 : rParen]
    # print label+' | '+name+' | '+age
    # remove any bolding FGDCGeoAge font, and DMUUnitLabel style specification from
    # label
    for fmt in ("<b>", "</b>", "<g>", "</g>", "<ul>", "</ul>"):
        label = label.replace(fmt, "")
    # remove any bolding from name and age
    for fmt in ("<b>", "</b>"):
        name = name.replace(fmt, "")
        age = age.replace(fmt, "")
    if debug:
        addMsgAndPrint(label + "**" + name + "**" + age)
    if debug:
        addMsgAndPrint("    " + desc[0:20])
    return label, name, age, desc


def rankParaStyle2IsHigher(style1, style2):
    if style1.find("Heading") > -1 and style2.find("Unit") > -1:
        return False
    elif style1.find("Heading") > -1 and style2.find("Headnote") > -1:
        return False
    elif style1.find("Headnote") > -1 and style2.find("Heading") > -1:
        return False
    ##  Don't allow heading to be sibling with DMUUnit1
    # elif style1 == 'DMUUnit1' and style2.find('Heading') > -1:
    #    return False
    elif style1.find("Unit") > -1 and style2.find("Heading") > -1:
        return True
    else:  # both are Heading or both are Unit
        if style1 == "DMU Unit 1 (1st after heading)":
            return False
        elif style2 < style1:  # larger N is smaller rank
            return True
        else:
            return False


def rankParaStylesAreEqual(style1, style2):
    if debug:
        addMsgAndPrint(style1 + "  " + style2)
    if style1.find("Heading") > -1 and style2.find("Heading") > -1:
        # both are headings
        if style1[-1:] == style2[-1:]:
            return True
        else:
            return False
    elif style1.find("Unit") > -1 and style2.find("Unit") > -1:
        # print 'both are unit descriptions'
        if style1[-1:] == style2[-1:]:
            return True
        elif style1 == "DMU Unit 1 (1st after heading)" and style2 == "DMU Unit 1":
            return True
        else:
            return False
    elif style1 == "DMU Headnote" and style2.find("Heading") > -1:
        return True

    elif style1 == "DMU Unit 1" and style2.find("Heading") > -1:
        # a heading is equal rank with DMUUnit1 if they have same parent
        return True

    else:
        return False


##### - START - #####
def main(params):
    manuscriptFile = params[0]
    gdb = params[1]

    rewrite_hkey = False
    if len(params) > 2:
        rewrite_hkey = params[2]

    overwrite = False
    if len(params) > 3:
        overwrite = params[3]

    zero_pad = 3
    if len(params) > 4:
        zero_pad = int(params[4])

    addMsgAndPrint(versionString)
    addMsgAndPrint("Parsing file " + manuscriptFile)

    if debug:
        addMsgAndPrint("0")
    document = docxm.opendocx(manuscriptFile)
    if debug:
        addMsgAndPrint("00")
    paragraphList = docxm.getDMUdocumenttext(document)
    if debug:
        addMsgAndPrint("There are {} paragraphs".format(len(paragraphList)))

    msRows = []
    labels = []
    i = 0
    if debug:
        addMsgAndPrint("000")

    for paragraph in paragraphList:  # each paragraph is a list: [style name, text]
        paraStyle = paragraph[0]

        # If this is a DMU paragraph style and not "DESCRIPTION OF MAP UNITS"
        if paraStyle.startswith("DMU") and paraStyle != "DMU-Heading1":
            paraText = paragraph[1]

            if styleType(paraStyle) == "DMU Paragraph":
                msRows[i - 1][3] = msRows[i - 1][3] + " <br>" + paraText

            else:
                label = ""
                name = ""
                age = ""
                description = ""
                if styleType(paraStyle) == "Unit":
                    label, name, age, description = parseUnitPara(paraText)
                elif styleType(paraStyle) == "Heading":
                    name = paraText
                elif styleType(paraStyle) == "Headnote":
                    description = paraText[
                        1:-1
                    ]  # subtract beginning and ending brackets
                else:
                    addMsgAndPrint("Unrecognized paragraph style")
                    addMsgAndPrint(paraStyle)
                    addMsgAndPrint(paraText)
                    sys.exit()
                if label != "" and label in labels:
                    addMsgAndPrint("NON-UNIQUE VALUE OF LABEL: " + label)
                    addMsgAndPrint("  Fix it and re-run!")
                    sys.exit()
                labels.append(label)
                msRows.append([label, name, age, description, paraStyle])
                i = i + 1

    if i == 0:
        addMsgAndPrint("Did not find any paragraphs with DMU styles!")
        addMsgAndPrint(" Is this the right Word document?")
        sys.exit()

    # build hKeys
    hKeyStyleDict = {}
    hKeys = []
    hKeys.append([1])  # set 0th element
    hKeyStyleDict[str(hKeys[0])] = msRows[0][4]
    lastHKey = copy.deepcopy(hKeys[0])
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
        addMsgAndPrint("  " + row[0] + " | " + row[1] + " | " + row[2])
        addMsgAndPrint("    ParagraphStyle = " + row[4])
        addMsgAndPrint("    HierarchyKey = " + row[5])

    addMsgAndPrint("")
    addMsgAndPrint("Updating table DescriptionOfMapUnits in " + gdb)

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
    addMsgAndPrint("Updating any matching rows in DescriptionOfMapUnits")
    i = 1
    for row in dmuRows:
        matchRow = -1
        addMsgAndPrint(row.Label)
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
            addMsgAndPrint(
                "  DMU row " + str(i) + ", label = " + str(row.Label) + " has no match"
            )
        if matchRow > -1:
            addMsgAndPrint("  updating DMU row " + str(i))
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
    addMsgAndPrint("Adding new rows to DescriptionOfMapUnits")
    dmuRows = arcpy.InsertCursor(gdb + "/DescriptionOfMapUnits")
    for i in range(len(msRows)):
        if not i in msRowsMatched:
            addMsgAndPrint("  " + str(msRows[i])[:40] + "...")
            row = dmuRows.newRow()
            row.Label = msRows[i][0]
            row.MapUnit = msRows[i][0]
            # addMsgAndPrint(str(i)+'  '+str(msRows[i][0])[:20])
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
