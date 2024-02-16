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

# styles from MapManuscript_v3-1_06-22.dotx
style_dict = {
    "DMU - List Bullet": "unit text",
    "DMU Headnote - 1 Line": "headnote",
    "DMU Headnote - More Than 1 Line": "headnote",
    "DMU Headnote Paragraph": "headnote",
    "DMU NoIndent": "unit text",
    "DMU Paragraph": "unit text",
    "DMU Quotation": "unit text",
    "DMU Unit 1 (1st after heading)": "unit",
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


def parse_text(p_object, doc_list, reformat):
    label = None
    name = None
    age = None
    description = None

    style = p_object.style.name
    text = p_object.text

    # parse the text
    # heading text goes into Name
    if style_dict.get(style) == "heading":
        name = text

    # headnote text goes into Description
    elif style_dict.get(style) == "headnote":
        if reformat:
            description = replace_formatting(p_object.runs)
        else:
            description = text

    # only DMU unit paragraph style names are 10 characters long and end in a number
    elif (
        len(style) == 10
        and style[-1].isnumeric()
        or style == "DMU Unit 1 (1st after heading)"
    ):
        label, i = text_runs(p_object, "DMU Unit Label (type style)")
        name_age, i = text_runs(p_object, "DMU Unit Name/Age (type style)")

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

        if reformat:
            description = replace_formatting(p_object.runs[i:])
        else:
            d_list = []
            for r in p_object.runs[i:]:
                d_list.append(r.text)
            description = "".join(d_list)

    else:
        print(f"Unknown paragraph style '{style}'")

    return label, name, age, description, doc_list


def text_runs(p, style_name):
    # build a single text string from the text of sequential runs
    # that all share the same character style
    text_runs = []
    i = 0
    for n, run in enumerate(p.runs):
        if run.style.name == style_name:
            i = n
            text_runs.append(run.text)

    return "".join(text_runs), i


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
    """return a general paragraph style type based on style_dict
    and, for unit and heading paragraphs, a rank"""
    p_type = style_dict.get(p_style)

    if p_type in ("unit", "heading"):
        rank = p_style[-1]

    if p_type in ("unit text", "headnote"):
        rank = 0

    return p_type, rank


def replace_formatting(runs):
    """
    Detects formatting runs in a paragraph.

    Returns a string where Word formatted bold, italic, super/subscript and
    cases of FGDCGeoAge have been converted to HTML formatting tags
    (mostly written by ChatGPT!)
    """
    formatting_runs = []
    current_run_text = ""
    current_run_formatting = {}

    for run in runs:
        if run.text.strip():
            # Check if formatting properties have changed
            if (
                run.bold != current_run_formatting.get("bold")
                or run.italic != current_run_formatting.get("italic")
                or run.font.name != current_run_formatting.get("font")
                or run.style.name != current_run_formatting.get("style")
                or run.font.superscript != current_run_formatting.get("super")
                or run.font.subscript != current_run_formatting.get("sub")
            ):
                if current_run_text:
                    formatting_runs.append((current_run_text, current_run_formatting))
                current_run_text = run.text
                current_run_formatting = {
                    "bold": run.bold,
                    "italic": run.italic,
                    "font": run.font.name,
                    "style": run.style.name,
                    "super": run.font.superscript,
                    "sub": run.font.subscript,
                }
            else:
                current_run_text += run.text

    # Append the last run
    if current_run_text:
        formatting_runs.append((current_run_text, current_run_formatting))

    reformatted = []
    for text, formatting in formatting_runs:
        if formatting.get("bold"):
            text = f"<b>{text}</b>"
        if formatting.get("italic"):
            text = f"<em>{text}</em>"
        if formatting.get("font") == "FGDCGeoAge":
            text = f'<span style="font-family: FGDCGeoAge;">{text}</span>'
        if formatting.get("style") == "Run-inHead":
            text = f"<em>{text}</em>"
        if formatting.get("super") == True:
            text = f"<sup>{text}</sup>"
        if formatting.get("sub") == True:
            text = f"<sub>{text}</sub>"

        reformatted.append(text)

    return "".join(reformatted)


def main(params):
    """Parses a Word document of a DMU into a DMU table

    Args:
        manuscript_file (file path): MS Word document that contains only a Description of Map Units section
            based on USGS MapManuscript_v3-1_06-22.dotx.
        gdb (file path): File geodatabase that may or may not contain a DescriptionOfMapUnits table
        zero_pad (integer): How many spaces left of the number should be filled with zeros
        reformat (boolean): Attempt (or not) to translate Word character styles in descriptions to HTML format tags
    """
    manuscript_file = params[0]
    gdb = params[1]
    zero_pad = 3
    if len(params) > 2:
        zero_pad = int(params[2])

    reformat = False
    if len(params) == 4:
        reformat = guf.eval_bool(params[3])

    guf.addMsgAndPrint(versionString)

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

    guf.addMsgAndPrint(f"Parsing file {manuscript_file}")

    # open document and get a list of paragraphs
    document = docx.Document(manuscript_file)
    paras = document.paragraphs

    # build a list of doc_list items
    # [hkey, style, label, name, age, description]
    # avoid first paragraph if it is just "Description Of Map Units"
    if paras[0].text.strip().lower() == "description of map units":
        paras = paras[1:]

    # set up variables for initial entry in list
    hkeys = [[1]]
    hkey_dict = {}
    style_1 = paras[0].style.name
    hkey_dict[str(hkeys[0])] = style_1
    doc_list = []
    label, name, age, description, doc_list = parse_text(paras[0], doc_list, reformat)
    doc_list.append([[1], style_1, label, name, age, description])

    # prepare to iterate through the rest of the document paragraphs
    last_head_level = 1
    paras = [p for p in paras if not p.text.isspace()]
    for p in paras[1:]:
        style = p.style.name

        if not style_dict[style] == "unit text":
            # determine the HierarchyKey
            # each of the following cases compares the style of the current paragraph
            # to the style of the previous paragraph
            last_hkey = hkeys[-1]
            current_type, current_rank = para_props(style)
            last_type, last_rank = para_props(hkey_dict[str(last_hkey)])

            # paragraph types are the same, rank is the same
            # current is sibling to previous
            if (current_type, current_rank) == (last_type, last_rank):
                this_hkey = sibling_hkey(last_hkey)

            # paragraph types are the same, the current rank is lower
            # than previous (trailing number is > than previous); current is child to previous
            if current_type == last_type and current_rank > last_rank:
                this_hkey = child_hkey(last_hkey)

            # headnotes are children to previous headings
            if current_type == "headnote" and last_type == "heading":
                this_hkey = child_hkey(last_hkey)

            # headings are siblings to previous headnotes:
            # level2 heading
            #   headnote
            #   level3 heading
            # assuming it would never make sense to write:
            # level2 heading
            #   headnote
            # level2 heading
            # with no unit under the first level2 heading
            if current_type == "heading" and last_type == "headnote":
                this_hkey = sibling_hkey(last_hkey)

            # unit is always child to previous heading
            if current_type == "unit" and last_type == "heading":
                this_hkey = child_hkey(last_hkey)

            # unit is always sibling to previous text
            if current_type == "unit" and last_type in ("unit text", "headnote"):
                this_hkey = sibling_hkey(last_hkey)

            # text is always child to previous heading
            if current_type == "unit text" and last_type in ("unit", "heading"):
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
            if current_type == "heading" and last_type in ("unit", "unit text"):
                heading_above_unit = False
                for n in reversed(hkeys):
                    n_style, n_rank = para_props(hkey_dict[str(n)])
                    # Special case where DMUHead2 follows DMUHead1Back
                    # though numerically of different ranks, they are siblings
                    if (
                        hkey_dict[str(n)] == "DMU-Heading1"
                        and p.style.name == "DMU-Heading2"
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
                            if hkey_dict[str(n)] == "DMU Unit 1":
                                this_hkey = sibling_hkey(n)
                                break
                        break

                # case where there is no younger heading in the document,
                # that is, no Description of Map Units heading
                if heading_above_unit == False:
                    for n in reversed(hkeys):
                        if hkey_dict[str(n)] == "DMU Unit 1":
                            this_hkey = sibling_hkey(n)
                            break

                last_head_level = current_rank

                # append this hkey to the hkeys list
                hkeys.append(this_hkey)
                # add this hkey and style to the dictionary
                hkey_dict[str(this_hkey)] = p.style.name

            # append this hkey to the hkeys list
            hkeys.append(this_hkey)
            hkey_dict[str(this_hkey)] = style
            if not p.text == "":
                label, name, age, desc, doc_list = parse_text(p, doc_list, reformat)
            doc_list.append([this_hkey, style, label, name, age, desc])
        else:
            paragraph = replace_formatting(p.runs)
            doc_list[-1][5] = f"{doc_list[-1][5]}\n{paragraph}"

    for line in doc_list:
        hkey_list = [str(i).zfill(zero_pad) for i in line[0]]
        line[0] = "-".join(hkey_list)

    guf.addMsgAndPrint("Document parsed.")
    guf.addMsgAndPrint(f"Searching for changes to be made to {dmu_table}")

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
            f"MapUnit IS NULL AND Name IS NOT NULL AND Name <> '{name}' AND HierarchyKey = '{hkey}'",  # heading has not been changed but not re-ordered
            f"MapUnit IS NULL AND Name IS NULL and Description <> '{description}' AND HierarchyKey = '{hkey}'",  # description (headnote) is primary key
            f"MapUnit IS NULL AND Name IS NULL and Description = '{description}'",
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
        guf.addMsgAndPrint(f"{len(update_list)} row(s) will be updated.")
        for r in update_list:
            where = r[6]
            vals = r[0:6]
            with arcpy.da.UpdateCursor(
                dmu_table, cursor_fields, where_clause=where
            ) as cursor:
                for row in cursor:
                    cursor.updateRow(vals)

    if insert_list:
        guf.addMsgAndPrint(f"{len(insert_list)} new row(s) will be inserted.")
        with arcpy.da.InsertCursor(dmu_table, cursor_fields) as cursor:
            for r in insert_list:
                cursor.insertRow(r)

    if not update_list and not insert_list:
        guf.addMsgAndPrint(
            "Document content matches table content. No changes will be made."
        )


if __name__ == "__main__":
    main(sys.argv[1:])
