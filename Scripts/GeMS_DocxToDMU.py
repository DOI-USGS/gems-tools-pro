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
from pathlib import Path
import copy
import arcpy
import GeMS_utilityFunctions as guf
import docx

versionString = "GeMS_DocxToDMU.py, version of 1/18/24"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_DocxToDMU.py"
guf.checkVersion(versionString, rawurl, "gems-tools-pro")

debug = False

# the document.xml file in the .docx archive saves the style id value, not name which is more like
# an alias. Either works for building a word file, but when going from docx to dmu table, we'll save the
# the name to be consistent with what is seen in Word.
# style_dict = {
#     "DMU-Heading1": "DMUHead1Back",
#     "DMU-Heading2": "DMUHead2",
#     "DMU-Heading3": "DMUHead3",
#     "DMU-Heading4": "DMUHead4",
#     "DMU-Heading5": "DMUHead5",
#     "DMU Headnote": "DMUBodyPara",
#     "DMUParagraph": "DMUBodyPara",
#     "DMU Unit 1": "DMU1",
#     "DMU Unit 1 (1st after heading)": "DMU1",
#     "DMUUnit11stafterheading": "DMU1",
#     "DMU Unit 2": "DMU2",
#     "DMU Unit 3": "DMU3",
#     "DMU Unit 4": "DMU4",
#     "DMU Unit 5": "DMU5",
#     "DMUUnit1": "DMU1",
#     "DMUUnit2": "DMU2",
#     "DMUUnit3": "DMU3",
#     "DMUUnit4": "DMU4",
#     "DMUUnit5": "DMU5",
# }

# styles from MapManuscript_v3-1_06-22.dotx
style_dict = {
    "DMU - List Bullet": "bullet",
    "DMU Headnote - 1 Line": "headnote",
    "DMU Headnote - More Than 1 Line": "headnote",
    "DMU Headnote Paragraph": "headnote",
    "DMU NoIndent": "unit text",
    "DMU Paragraph": "unit text",
    "DMU Quotation": "unit text",
    "DMU Unit 1": "unit",
    "DMU Unit 2": "unit",
    "DMU Unit 3": "unit",
    "DMU Unit 4": "unit",
    "DMU Unit 5": "unit",
    "DMU Unit Label (type style)": "label",
    "DMU Unit Name/Age (type style)": "age",
    "DMU-Heading1": "heading",
    "DMU-Heading2": "heading",
    "DMU-Heading3": "heading",
    "DMU-Heading4": "heading",
    "DMU-Heading5": "heading",
    "Run-inHead": "headnote",
}


def parse_text(p_object, doc_list):
    label = None
    name = None
    age = None
    description = None

    style = p_object.style.name
    text = p_object.text

    # parse the text
    # heading text goes into Name
    if style_dict[style] == "heading":
        name = text

    # headnote text goes into Description
    elif style_dict[style] == "headnote":
        description = text

    # only DMU unit paragraph style names are 10 characters long and end in a number
    elif len(style) == 10 and style[-1].isnumeric():
        label = text_runs(p_object, "DMU Unit Label (type style)")
        name_age = text_runs(p_object, "DMU Unit Name/Age (type style)")

        # if there are parantheses, we have an age,
        # partition on the first one to get the unit name
        if name_age.find("(") > 0:
            name, x, age = name_age.partition("(")

            # and strip the final ")" character
            age = age.rstrip(")")
        else:
            # there is only a name
            age = None
            name = name_age

        description = text.lstrip(label).strip().lstrip(name_age)

        if label:
            name_age_desc = text.lstrip(label).strip()

        # try to partition the unit name(unit age) from the description
        # for this, we are counting on the description starting after an emdash
        # or double hyphens
        dashes = ("\u2014", "\u002d\u002d")
        if name_age_desc.find("\u2014") > 0:
            name_age, x, description = name_age_desc.partition("\u2014")
        elif name_age_desc.find("\u002d\u002d") > 0:
            name_age, x, description = name_age_desc.partition("\u002d\u002d")
        else:
            # if there are no dashes, there is only a name(age) string
            name_age = name_age_desc

    elif style == "DMUParaCont":
        # append this paragraph to the previous entry's description
        doc_list[-1][5] = f"{doc_list[-1][5]}\n{p_object.text}"
    else:
        pass

    return label, name, age, description, doc_list


def text_runs(p, style_name):
    # build a single text string from the text of sequential runs
    # that all share the same character style
    text_runs = []
    for run in p.runs:
        if run.style.name == style_name:
            text_runs.append(run.text)

    return "".join(text_runs)


def child_hkey(hkey):
    this_hkey = copy.deepcopy(hkey)
    this_hkey.append(1)
    return this_hkey


def sibling_hkey(hkey):
    # increment the last item in the previous hkey
    last_element = int(copy.copy(hkey[-1])) + 1
    # remove the last item in the previous hkey
    this_key = hkey[0:-1]
    # append the incremented item
    this_key.append(last_element)

    return this_key


def para_props(p_style):
    if p_style in style_dict:
        p_style = style_dict[p_style]

    if len(p_style) == 4:
        p_type = "unit"
        rank = p_style[-1]

    if p_style.startswith("DMUHead"):
        p_type = "heading"

        if p_style.endswith("back"):
            rank = 1
        else:
            rank = p_style[7:8]

    if p_style in ("DMUAuthors", "DMUBodyPara"):
        p_type = "text"
        rank = 0

    return p_type, rank


def main(params):
    manuscript_file = params[0]
    gdb = params[1]
    zero_pad = 3
    if len(params) > 2:
        zero_pad = int(params[2])

    guf.addMsgAndPrint(versionString)
    guf.addMsgAndPrint("Parsing file " + manuscript_file)

    dmu_table = str(Path(gdb) / "DescriptionOfMapUnits")
    if not arcpy.Exists(dmu_table):
        try:
            import GeMS_ALaCarte as gacl

            vt = arcpy.ValueTable(3)
            vt.loadFromString("# # DescriptionOfMapUnits")
            gacl.process(gdb, vt)
        except:
            arcpy.AddError(
                f"DescriptionOfMapUnits table could not be found and could not be created in {gdb}"
            )

    document = docx.Document(manuscript_file)
    paras = document.paragraphs

    if paras[0].text.lower() == "description of map units":
        paras = paras[1:]

    hkeys = [[1]]
    hkey_dict = {}
    if paras[0].style.name in style_dict:
        style_1 = style_dict[paras[0].style.name]
    else:
        style_1 = p.style.name

    hkey_dict[str(hkeys[0])] = style_1

    # doc_list items
    # [hkey, style, label, name, age, description]
    doc_list = []
    label, name, age, description, doc_list = parse_text(paras[0], doc_list)
    doc_list.append([[1], style_1, label, name, age, description])

    # last_head_level = 1
    for p in paras[1:]:
        # translate between pre-v5.4 and v5.4 manuscript styles
        if p.style.name in style_dict:
            style = style_dict[p.style.name]
        else:
            style = p.style.name

        if not style == "DMUParaCont":
            # determine the HierarchyKey
            last_hkey = hkeys[-1]
            current_type, current_rank = para_props(p.style.name)
            last_type, last_rank = para_props(hkey_dict[str(last_hkey)])

            # paragraph types are the same, rank is the same
            # current is sibling to previous
            if (current_type, current_rank) == (last_type, last_rank):
                this_hkey = sibling_hkey(last_hkey)

            # paragraph types are the same, the current rank is lower
            # than previous (trailing number is > than previous); current is child to previous
            if current_type == last_type and current_rank > last_rank:
                this_hkey = child_hkey(last_hkey)

            # current paragraph is unit, previous is heading
            # unit is always child to heading
            if current_type == "unit" and last_type == "heading":
                this_hkey = child_hkey(last_hkey)

            # current paragraph is unit, previous is some text
            # unit is always sibling to text
            if current_type == "unit" and last_type == "text":
                this_hkey = sibling_hkey(last_hkey)

            # current paragraph is text and prevous is a heading
            # text is always child to heading
            if current_type == "text" and last_type in ("unit", "heading"):
                this_hkey = child_hkey(last_hkey)

            # paragraph types are the same but the current is one rank higher than the
            # previous (trailing number is lower than previous); current is sibling to an
            # unknown sibling back in the list. Should only be true for unit paragraphs.
            # Text paragraphs are all the same rank and there should never be a higher rank
            # heading that immediately follows a lower rank heading
            if current_type == last_type and current_rank < last_rank:
                for n in reversed(hkeys):
                    n_type, n_rank = para_props(hkey_dict[str(n)])
                    if current_type == n_type and current_rank == n_rank:
                        this_hkey = sibling_hkey(n)
                        break

            # more complex case where the current paragraph is a heading and the
            # previous is a unit. The two will be siblings only if the last heading seen
            # is of a higher rank
            if current_type == "heading" and last_type in ("unit", "text"):
                heading_above_unit = False
                for n in reversed(hkeys):
                    n_style, n_rank = para_props(hkey_dict[str(n)])
                    # Special case where DMUHead2 follows DMUHead1Back
                    # though numerically of different ranks, they are siblings
                    if (
                        hkey_dict[str(n)] == "DMUHead1Back"
                        and p.style.name == "DMUHead2"
                    ):
                        this_hkey = [2]
                        heading_above_unit = True
                        break

                    # case where the last heading seen is the same rank as current
                    if n_style == "heading" and current_rank == n_rank:
                        this_hkey = sibling_hkey(n)
                        heading_above_unit = True
                        break

                    # case where the last heading seen is less than rank of current
                    if n_style == "heading" and current_rank > n_rank:
                        # there is no younger sibling heading before getting back to a
                        # parent heading, so now look for the first DMU1 above the current heading
                        heading_above_unit = True
                        for n in reversed(hkeys):
                            if hkey_dict[str(n)] == "DMU1":
                                this_hkey = sibling_hkey(n)
                                break
                        break
                # case where there is no younger heading in the document,
                # that is, no Description of Map Units heading
                if heading_above_unit == False:
                    for n in reversed(hkeys):
                        if hkey_dict[str(n)] == "DMU1":
                            this_hkey = sibling_hkey(n)
                            break

                # last_head_level = current_rank

                # append this hkey to the hkeys list
                hkeys.append(this_hkey)
                # add this hkey and style to the dictionary
                hkey_dict[str(this_hkey)] = p.style.name

            # append this hkey to the hkeys list
            hkeys.append(this_hkey)
            hkey_dict[str(this_hkey)] = style

            label, name, age, desc, doc_list = parse_text(p, doc_list)
            doc_list.append([this_hkey, style, label, name, age, desc])

    for line in doc_list:
        hkey_list = [str(i).zfill(int(zero_pad)) for i in line[0]]
        line[0] = "-".join(hkey_list)

    # doc_list items
    # [hkey, style, label, name, age, description]
    cursor_fields = [
        "HierarchyKey",
        "ParagraphStyle",
        "MapUnit",
        "Name",
        "Age",
        "Description",
    ]

    table_list = [list(row) for row in arcpy.da.SearchCursor(dmu_table, cursor_fields)]

    # eval_list is every row in the document that does not have an EXACT match in the table list
    # we know these are different, but do they need to update an only partially different row
    # or are they brand new and need to be inserted? Each action requires a different cursor
    mod_list = [row for row in doc_list if not row in table_list]

    insert_list = []
    update_list = []
    for row in mod_list:
        update_row = False
        hkey = row[0]
        mu = row[2]
        name = row[3]
        description = row[5]

        if name:
            name = name.replace("'", "''")
        if description:
            description = description.replace("'", "''")

        wheres = [
            f"MapUnit = '{mu}' AND MapUnit IS NOT NULL",  # MapUnit is primary key
            f"MapUnit IS NOT NULL AND MapUnit <> '{mu}' AND Name = '{name}'",  # name is primary key when MapUnits are not the same
            f"MapUnit IS NULL AND Name = '{name}'",  # Name is primary key when MapUnit is null (heading)
            f"MapUnit IS NULL AND Name IS NOT NULL AND Name <> '{name}' AND HierarchyKey = '{hkey}'",  # heading has been changed but not re-ordered
            f"MapUnit IS NULL AND Name IS NULL and Description <> '{description}' AND HierarchyKey = '{hkey}'",  # description (headnote) is primary key
        ]

        for where in wheres:
            updates = [
                row
                for row in arcpy.da.SearchCursor(
                    dmu_table, cursor_fields, where_clause=where
                )
            ]
            if len(updates) > 0:
                row.append(where)
                update_list.append(row)
                update_row = True
                break

        if not update_row:
            insert_list.append(row)

    if update_list:
        for r in update_list:
            where = r[6]
            vals = r[0:6]
            with arcpy.da.UpdateCursor(
                dmu_table, cursor_fields, where_clause=where
            ) as cursor:
                for row in cursor:
                    cursor.updateRow(vals)

    if insert_list:
        with arcpy.da.InsertCursor(dmu_table, cursor_fields) as cursor:
            for r in insert_list:
                cursor.insertRow(r)


if __name__ == "__main__":
    main(sys.argv[1:])
