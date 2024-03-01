"""
Translates DMU table in NCGMP09-style geodatabase into a fully formatted
Microsoft Word .docx file.

Assumes formatting and style names in USGS Pubs template MapManuscript_v1-0_04-11.dotx

Arguments
    Input geodatabase
    Output workspace
    Output filename (if it doesn't end in .docx, .docx will be appended)
    UseMapUnitForUnitLabl (Boolean, either 'true' or 'false')
    
"""

# 4 June 2019: Edited to work with Python 3 in ArcGIS Pro - Evan Thoms
#   This version uses the docx module for Python 3, which is not included
#   in the miniconda distribution of python with ArcGIS Pro.
#   But it is included in the \Scripts folder of the toolbox. No need to install
#
#   Doesn't do all of the HTML conversion that Ralph's original does. So far it checks for:
#   <br> - line break/paragraph
#   <p> - paragraph, closing tag is not required and ignored if present
#   <b> - bold
#   <i> - italic
#   <sup> or <sub> super or subscri
#   <span  style="font-family: FGDCGeoAge"> write the enclosed text in FGDCGeoAge font, unit labels
#   also checks for non-printing line breaks if text with paragraphs is pasted from Word.
#
# Note - We build the Word doc here with the style names, but document.xml in the .docx archive saves
#   the style id.

import sys
import os
import arcpy
from pathlib import Path
import GeMS_utilityFunctions as guf
import docx
from bs4 import BeautifulSoup

versionString = "GeMS_DMUtoDOCX_AGP2.py, version of 2/28/24"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_DMUtoDOCX.py"
guf.checkVersion(versionString, rawurl, "gems-tools-pro")

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


def main(params):
    # PARAMETERS
    gdb = Path(params[0])
    dmu_table = str(gdb / "DescriptionOfMapUnits")

    if not arcpy.Exists(dmu_table):
        arcpy.AddError("Could not find or create DescriptionOfMapUnits table")

    out_dir = Path(params[1])
    out_name = params[2]
    if not out_name.endswith(".docx"):
        out_name = f"{out_name}.docx"
    out_file = out_dir / out_name

    # do we calculate paragraph styles based on dmu attributes or use the value in ParagraphStyle?
    calc_style = True
    if len(params) > 3:
        calc_style = guf.eval_bool(params[3])

    # do we use the value in MapUnit or Label for the unit abbreviations in the docx?
    use_label = False
    if len(params) > 4:
        use_label = guf.eval_bool(params[4])

    if use_label:
        mu = "Label"
    else:
        mu = "MapUnit"

    if calc_style:
        fields = ["HierarchyKey", mu, "Name", "Age", "Description"]
    else:
        fields = ["HierarchyKey", mu, "Name", "Age", "Description", "ParagraphStyle"]

    # are we making a DMU or an LMU?
    is_lmu = False
    if len(params) > 5:
        is_lmu = guf.eval_bool(params[5])

    # do we try to translate annotation text formatting into Word styles?
    format = True
    if len(params) > 6:
        format = guf.eval_bool(params[6])

    open_doc = True
    if len(params) > 7:
        open_doc = guf.eval_bool(params[7])

    # START
    sqlclause = (None, "ORDER by HierarchyKey ASC")
    rows = [
        list(row)
        for row in arcpy.da.SearchCursor(dmu_table, fields, sql_clause=sqlclause)
    ]

    if is_lmu == True:
        head1 = "LIST OF MAP UNITS"
    else:
        head1 = "DESCRIPTION OF MAP UNITS"

    # add LMU or DMU title to rows
    if rows[0][2]:
        if not rows[0][2].lower().strip() == head1:
            rows.insert(0, ["000", None, head1, None, None])
    else:
        rows.insert(0, ["000", None, head1, None, None])

    if not calc_style:
        rows[0].append("DMU-Heading1")

    # rows = [hkey, unit, name, age, description]
    # doc_rows = [hkey, unit, name, age, description, paragraph style]
    for i, row in enumerate(rows):
        para_type = determine_type(row[1:5])
        if not calc_style:
            para_style = row[5]
        else:
            para_style = determine_style(para_type, i, rows)
        row.append(para_style)

    # remove headnotes if this is a list of map units
    for row in rows:
        if is_lmu and style_dict[row[5]] == "headnote":
            rows.remove(row)

    # rows = [hkey, unit, name, age, description, paragraph style]
    scripts = Path.cwd()
    toolbox = scripts.parent
    resources = toolbox / "Resources"
    template = resources / "DMU_template.docx"

    document = docx.Document(template)
    document._body.clear_content()
    for p in rows:
        if style_dict[p[5]] == "heading":
            document.add_paragraph(p[2], p[5])

        if style_dict[p[5]] == "headnote":
            for para in p[4].splitlines():
                headnote = document.add_paragraph(style=p[5])
                if format:
                    format_description(headnote, para, "headnote")
                else:
                    arcpy.AddMessage(para)
                    headnote.text = para

        if style_dict[p[5]] == "unit":
            unit = document.add_paragraph(style=p[5])
            if use_label:
                format_description(unit, p[1], "unit_label")
            else:
                unit.add_run(f"{p[1]}", "DMU Unit Label (type style)")

            unit.add_run(f"\t{p[2]}({p[3]})", "DMU Unit Name/Age (type style)")

            if not is_lmu:
                paras = p[4].splitlines()
                if paras:
                    if format:
                        format_description(unit, f"—{paras[0]}")
                    else:
                        unit.add_run(para)

                for para in paras[1:]:
                    new_p = document.add_paragraph(style="DMU Paragraph")
                    if format:
                        format_description(new_p, para)
                    else:
                        new_p.add_run(para)

    try:
        document.save(out_file)
        del document
    except IOError:
        arcpy.AddError(
            f"Cannot save changes to {out_file}. If it is open. Close it and try again."
        )
        sys.exit()

    if open_doc:
        os.startfile(out_file, "edit")


def format_description(paragraph, text, special=None):
    """add html tagged text as runs in docx paragraph"""
    soup = BeautifulSoup(text, "html.parser")
    for i, child in enumerate(soup.children):
        tag = child.name
        run = paragraph.add_run(child.get_text())

        if special == "unit":
            run.style = "DMU Unit Label (type style)"

        if tag == "b":
            run.bold = True

        elif tag in ("em", "i"):
            if special == "headnote" and i == 0:
                run.style = "Run-inHead"
            else:
                run.italic = True

        elif tag == "span":
            if "font-family: FGDCGeoAge" in child.get("style"):
                # if special == "unit_label":
                run.font.name = "FGDCGeoAge"

        elif tag == "sub":
            run.font.subscript = True

        elif tag == "sup":
            run.font.superscript = True

        else:
            pass


def determine_style(para_type, i, rows):
    """determines the specific Word doc style to apply to the paragraph based
    on paragraph type and properties of the previously inserted row or rows"""
    # rows = [hkey, unit, name, age, description, paragraph style]

    # the first item in the list has already been set as Description or
    # List of Map Units and this will always be DMU-Heading1
    if i == 0:
        return "DMU-Heading1"

    # headnotes do not need to be ranked
    if para_type == "headnote":
        if rows[i][4].startswith("["):
            if len(rows[i][4]) <= 91:
                return "DMU Headnote - 1 Line"
            else:
                return "DMU Headnote - More Than 1 Line"
        else:
            return "DMU Headnote Paragraph"

    # continue for headings and units
    # hkey of this row
    i_hkey = rows[i][0]

    # properties of previous row
    p_hkey = rows[i - 1][0]
    p_para_style = rows[i - 1][5]
    p_para_type = style_dict[p_para_style]

    # unit after headnotes or headings are always DMU Unit 1
    if para_type == "unit":
        if p_para_type in ("heading", "headnote"):
            return "DMU Unit 1"

    # now go backwards through list looking for the last paragraph of the same type
    for row in reversed(rows[0:i]):
        if style_dict[row[5]] == para_type:
            # special case of discovering Heading 2 after Heading 1
            if row[5] == "DMU-Heading1":
                return "DMU-Heading2"

            # same type and same hkey length means these are siblings
            # use the same style as the older sibling
            if len(row[0]) == len(i_hkey):
                return row[5]

            # same type but current hkey is longer, the current is a child
            # of the last one found, increment the style rank by one
            if len(i_hkey) > len(row[0]):
                r_para_style = row[5]
                r_rank_i = int(r_para_style[-1])
                i_unit_rank = r_rank_i + 1
                return f"{r_para_style[0:-1]}{i_unit_rank}"

    return None


def determine_type(vals):
    """determines the general paragraph type from table field values"""
    unit = vals[0]
    name = vals[1]
    age = vals[2]
    desc = vals[3]

    if unit:
        return "unit"
    if not unit and name:
        return "heading"
    if not unit and not name and desc:
        return "headnote"

    return None


if __name__ == "__main__":
    main(sys.argv[1:])
