# strings and functions related to building the validation reports.
# Moved from GeMS_ValidateDatabase for modularity
rdiv = '<div class="report">\n'
divend = "</div>\n"

table_start = """<table class="ess-tables">
  <tbody>
"""

table_end = """  </tbody>
</table>
"""

style = """ 
    <style>
        .report {
            font-family: Courier New, Courier, monospace;
            margin-left: 20px;
            margin-right: 20px;
        }
        h2,
        h3 {
            background-color: lightgray;
            padding: 5px;
            border-radius: 4px;
            font-family: "Century Gothic", CenturyGothic, AppleGothic, sans-serif;
        }
        h4 {
        margin-bottom: 4px;
        font-size: larger;
        }
        .ess-tables {
            width: 95%;
            margin-left: 20px;
        }
        .table-header:hover {
            cursor:pointer;
        }
        table,
        th,
        td {
            border: 1px solid gray;
            border-collapse: collapse;
            padding: 3px;
        }
        .table {
            color:darkorange;
            font-weight:bold;
        }
        .field {
            color: darkblue;
            font-weight:bold;
        }
        .value {
            color:darkgreen;
            font-weight:bold;
        }
        .highlight{
            background-color:#f2fcd6;
            padding:0 2px;
            border-radius:3px;
            border-bottom:1px solid gray;
        }
        li {
            list-style: disc;
            margin-top: 1px;
            margin-bottom: 1px;
        }
        #back-to-top {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 10px;
            margin: 10px;
            background-color: rgba(250,250,250,0.7);
            border-radius:5px;
        }
    </style>
"""

color_codes = """
    <div class="report">
        <h4>Color Codes</h4>
        <span class="table">Orange</span> are tables, feature classes, or feature datasets in the geodatabase<br>
        <span class="field">Blue</span> are fields in a table</br>
        <span class="value">Green</span> are values in a field</br>
    </div>
    """

geologic_names_disclaimer = """, pending completion of a peer-reviewed Geologic 
Names report that includes identification of any suggested modifications to 
<a href="https://ngmdb.usgs.gov/Geolex/">Geolex</a>. """


def table_cell(contents):
    return f'<td valign="top">{contents}</td>'


def table_row(cells):
    row = "  <tr>\n"
    for cell in cells:
        row = f"{row}{table_cell(cell)}\n"
    row = f"{row}</tr>"
    return row


def table_to_html(table, html, db_dict):
    # table is input table, html is output html file
    ap("    " + str(table))
    fields = [f.name for f in db_dict[table]['fields']]
    html.write('<table class="ess-tables">\n')
    # write header row
    html.write("<thead>\n  <tr>\n")

    # initialize a list on the objectid field
    field_names = [f.name for f in fields if f.type == "OID"]

    html.write(f"<th>{field_names[0]}</th>\n")
    for field in fields:
        if not field.name in standard_fields:
            if field.name.find("_ID") > 1:
                token = "_ID"
            else:
                token = field.name
            html.write("<th>" + token + "</th>\n")
            field_names.append(field.name)
    html.write("  </tr>\n</thead")
    html.write("<tbody>")
    # write rows
    if table == "DescriptionOfMapUnits":
        sql = (None, "ORDER BY HierarchyKey")
    elif table == "Glossary":
        sql = (None, "ORDER BY Term")
    elif table == "DataSources":
        sql = (None, "ORDER BY DataSources_ID")
    else:
        sql = (None, None)
    with arcpy.da.SearchCursor(table, field_names, None, None, False, sql) as cursor:
        for row in cursor:
            html.write("<tr>\n")
            for i in range(0, len(field_names)):
                # if isinstance(row[i],unicode):
                #    html.write('<td>'+row[i].encode('ascii','xmlcharrefreplace')+'</td>\n')
                # else:
                try:
                    if str(row[i]) == "None":
                        html.write("<td>---</td>\n")
                    else:
                        html.write("<td>" + str(row[i]) + "</td>\n")
                except:
                    html.write("<td>***</td>\n")
                    ap(str(type(row[i])))
                    ap(row[i])
            html.write("</tr>\n")
    # finish table
    html.write("  </tbody>\n</table>\n")


def criterion_stuff(
    errors_name, summary_2, errors_2, txt_1, err_list, anchor_name, link_txt, is_level
):
    if len(err_list) == 1:
        txt_2 = "PASS"
    else:
        txt_2 = f"""<font color="#ff0000">FAIL &nbsp;</font><a href="{errors_name}
                   #{anchor_name}">{str(len(err_list)-1)} {link_txt}</a>"""
        is_level = False
        errors_2.append(
            '<h4><a name="' + anchor_name + '">' + err_list[0] + "</a></h4>"
        )
        if err_list == topology_errors:
            errors_2.append(topology_error_note)
        if len(err_list) == 1:
            errors_2.apppend(f"{space4}None<br>")
            ap("appending None")
        for i in err_list[1:]:
            errors_2.append(f"{space4}{i}<br>")
    summary_2.append(vh.table_row([txt_1, txt_2]))

    return is_level

def write_summary(gdb_name, workdir, summary, errors_name, metadata_txt, metadata_errs, is_level_2, is_level_3)
    ### assemble output
    ap("Writing output")
    ap("  writing summary header")

    # output files

    errors_file = workdir / errors_name
    errors = open(errors_file, "w")

    summary_name = f"{gdb_name}-Validation.html"
    sum_file = workdir / summary_name
    summary = open(sum_file, "w", errors="xmlcharrefreplace")
    summary.write(vh.style)
    summary.write(
        """<h2><a name="overview"><i>GeMS validation of </i> '
        {gdb_name}{gdb_ver}</a></h2>\n"""
    )

    summary.write('<div class="report">Database path: ' + gdb_path + "<br>\n")
    summary.write("File written by <i>" + version_string + "</i><br>\n")
    summary.write(time.asctime(time.localtime(time.time())) + "<br><br>\n")
    summary.write(
        "This file should be accompanied by "
        + errors_name
        + ", "
        + metadata_txt
        + ", and "
        + metadata_errs
        + ", all in the same directory.<br><br>\n"
    )
    if is_level_3 and is_level_2:
        summary.write(
            'This database is <a href=#Level3><font size="+1"><b>LEVEL 3 COMPLIANT</b></a></font>'
            + geologic_names_disclaimer
            + "\n"
        )
    elif is_level_2:
        summary.write(
            'This database is <a href=#Level2><font size="+1"><b>LEVEL 2 COMPLIANT</b></a></font>'
            + geologic_names_disclaimer
            + "\n"
        )
    else:  # is level 1
        summary.write(
            'This database may be <a href=#Level1><font size="+1"><b>LEVEL 1 COMPLIANT</b></a>. </font>\n'
        )
    if metadata_checked:
        if passes_mp:
            summary.write(
                'The database-level FGDC metadata are formally correct. The <a href="'
                + metadataTxt
                + '">metadata record</a> should be examined by a human to verify that it is meaningful.<br>\n'
            )
        else:  # metadata fails mp
            summary.write(
                'The <a href="'
                + metadataTxt
                + '">FGDC metadata record</a> for this database has <a href="'
                + metadataErrs
                + '">formal errors</a>. Please fix! <br>\n'
            )
    else:  # metadata not checked
        summary.write("FGDC metadata for this database have not been checked. <br>\n")
