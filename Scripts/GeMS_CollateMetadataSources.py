"""Collate metadata and export standalone XML files

Args:
    gdb (str): Path to a file geodatabase. Required.
    objects (list): List of feature classes, tables, and/or rasters in the GDB. Optional.
    embedded_only (boolean) : Export metadata from embedded only. Spatial nodes are the only elements that will be addded
    arc_md (boolean) : Start with embedded metadata. True for gdbs by default, always False for geopackages. Optional.
    templates_path (str): Path to file or folder of one or more XML template files. Optional.
    temp_directive (str): Should metadata replace existing metadata or be appended to it? "replace" or "append". Optional.
    history (str) : How should history (lineage/procsteps) steps be dealt with? Options 1-4. 1 (no history) by default. Optional.
    source (str) : How should sources (lineage/srcinfo) be dealt with? Options 1-8. 1 (DataSources table sources only) by default. Optional.
    definitions_path (str): path to a CSV file (.txt or .csv extension) of custom entity attribute definitions. Optional.
    output_dir (str): path to output folder. 'Metadata' folder created in gdb folder if empty. Optional.

Usage:
    Meant to be run in ArcGIS Pro after the collection of parameters in the Collate Metadata Sources tool.

Returns:
    An XML metadata file will be created for each object
"""

import arcpy
import sys
from lxml import etree
from pathlib import Path
import GeMS_utilityFunctions as guf
import gems_metadata as gemsmd
import metadata_utilities as mu

from importlib import reload

for m in (gemsmd, guf, mu):
    reload(m)

toolbox_folder = Path(__file__).parent.parent
templates_folder = toolbox_folder / "Resources" / "metadata" / "templates"

# versionString = "GeMS_ImportTemplate.py, version of 7/25/24"
# rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_CollateMetadataSources.py"
# guf.checkVersion(versionString, rawurl, "gems-tools-pro")

nulls = ("#", "", None)

sources_choice = {
    "save datasources only": 1,
    "save embedded sources only": 2,
    "save template sources only": 3,
    "save datasources and embedded sources": 4,
    "save datasources and template sources": 5,
    "save embedded and template sources": 6,
    "save all sources": 7,
    "save no sources": 8,
}

history_choices = {
    "delete all process steps": 1,
    "save embedded process steps only": 2,
    "save template process steps only": 3,
    "save all process steps": 4,
}


def dict_from_walk(gdb):
    """build a dictionary of {object: catalog path} from the gdb"""
    walk = arcpy.da.Walk(
        gdb, datatype=["FeatureClass", "Table", "RasterDataset", "FeatureDataset"]
    )
    obj_dict = {}

    for dirpath, dirnames, filenames in walk:
        dirname = Path(dirpath).stem
        obj_dict[str(dirname)] = dirpath
        for filename in filenames:
            obj_dict[filename] = str(Path(dirpath) / filename)

    return obj_dict


def write_xml(dom, xml_path):
    tree = etree.ElementTree(dom)
    etree.indent(dom, level=0)
    with open(xml_path, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)


def main(params):
    """Collect parameters and send to CollateFGDCMetadata"""
    # PARAMETERS
    # path to gdb
    gdb = params[0]
    if not arcpy.Exists(gdb):
        arcpy.AddError("Could not find the database. Check that the path is correct.")
        sys.exit()

    db_name = Path(gdb).stem
    db_dict = guf.gdb_object_dict(gdb)

    # only exporting a database-level metadata record?
    database_md_bool = guf.eval_bool(params[1])

    # list of database objects
    if params[2] in ("#", "", None) or database_md_bool:
        objects = list(db_dict.keys())
    else:
        objects = params[2].split(";")

    # output directory
    if not Path(params[9]).exists():
        output_dir = Path(gdb).parent / f"{Path(gdb).stem}-metadata"
        arcpy.AddWarning("Output directory is null or does not exist")
        arcpy.AddWarning(f"Files will be written to {output_dir}")
    else:
        output_dir = params[9]

    if not Path(output_dir).exists():
        Path(output_dir).mkdir()

    # error log flag
    error_log = guf.eval_bool(params[10])
    if error_log:
        error_path = Path(output_dir) / f"{Path(gdb).stem}_metadata_errors.txt"
        if Path(error_path).exists():
            Path(error_path).unlink()

    # start with embedded metadata
    if gdb.endswith(".gpkg"):
        arc_md = False
    else:
        arc_md = guf.eval_bool(params[3])

    # dictionary of template files in the templates folder
    # {template name: template file path}
    temp_dict = {}
    if params[5].endswith(".xml"):
        temp_dict = {"DATABASE": params[4]}
    else:
        temp_dict = mu.md_dict_from_folder(params[4])

    # should template language replace any existing language in embedded metadata
    # or be appended to it?
    temp_directive = "replace"
    if not params[5] in nulls:
        temp_directive = params[5]
    else:
        temp_directive == None

    # history option
    if params[6] in nulls:
        # default to embedded history
        history = 2
    else:
        history = history_choices[params[6].lower()]

    # sources option
    if params[7] in nulls:
        # default to DataSources
        sources = 1
    else:
        sources = sources_choice[params[7].lower()]

    # path to custom definitions file
    definitions_path = None
    if params[8]:
        if Path(params[8]).exists():
            definitions_path = params[8]

    # check for contents
    if list(Path(output_dir).glob("*")):
        arcpy.AddWarning(f"The contents of {output_dir} will be overwritten")

    # END PARAMETER CHECK
    # if templates are to be used, go through them and search for the template name in each
    # of the objects/tables for which we want to import metadata
    # a template called 'ContactsAndFaults' will become the template for 'BedrockContactsAndFaults' and
    # 'SurficialContactsAndFaults'
    obj_temp_dict = {}
    if temp_dict:
        # if DATABASE, all objects use the same template
        if list(temp_dict.keys()) == ["DATABASE"]:
            # redefine obj_temp_dict
            obj_temp_dict = {obj_name: temp_dict["DATABASE"] for obj_name in objects}
        else:
            # go through all objects
            for obj_name in objects:
                match_found = False

                # look for templates with exact name match
                exact = [k for k in temp_dict.keys() if k == obj_name]
                if exact:
                    obj_temp_dict[obj_name] = temp_dict[exact[0]]
                    match_found = True
                    # arcpy.AddMessage(f"Using template {exact[0]} for {obj_name}")

                # annotation
                if obj_name.endswith("Anno"):
                    if "Anno" in temp_dict:
                        obj_temp_dict[obj_name] = temp_dict["Anno"]
                        match_found = True
                        # arcpy.AddMessage(f"Using template Anno for {obj_name}")

                # look for templates with partial matches
                if not match_found:
                    matches = [k for k in temp_dict.keys() if k in obj_name]
                    if len(matches) == 1:
                        obj_temp_dict[obj_name] = temp_dict[matches[0]]
                        match_found = True
                        # arcpy.AddMessage(f"Using template {matches[0]} for {obj_name}")

                # if multiple templates are found
                if not match_found:
                    if len(matches) > 1:
                        if len(matches) == 2:
                            comma = ""
                        else:
                            comma = ", "
                        multiples = (
                            f"{', '.join(matches[:-1])}{comma} and {matches[-1]}"
                        )
                        arcpy.AddWarning(f"Multiple templates found for {obj_name}:")
                        arcpy.AddWarning(multiples)
                        if "AnyTable" in temp_dict:
                            obj_temp_dict[obj_name] = temp_dict["AnyTable"]
                            # arcpy.AddMessage(f"Using template ANY_TABLE for {obj_name}")
                            match_found = True
                        else:
                            arcpy.AddWarning(f"No template found for {obj_name}")

                # Finally, look for ANY_TABLE and use it
                if not match_found:
                    if "AnyTable" in temp_dict:
                        obj_temp_dict[obj_name] = temp_dict["AnyTable"]
                        # arcpy.AddMessage(f"Using template ANY_TABLE for {obj_name}")
                        match_found = True
                    else:
                        arcpy.AddWarning(f"No template found for {obj_name}")

    # run through the database objects
    md_dict = {}
    arcpy.AddMessage(f"Generating metadata files:")
    for obj_name in [k for k in objects if not db_dict[k]["dataType"] == "Workspace"]:
        # for obj_name in objects:
        # look for a template path in obj_temp_dict
        if obj_name in obj_temp_dict:
            temp_path = obj_temp_dict[obj_name]
            temp_string = f" using template {temp_path}."
        else:
            temp_path = None
            temp_string = ""

        arcpy.AddMessage(f"  {obj_name}{temp_string}")
        params = {
            "table": obj_name,
            "gdb_dict": db_dict,
            "arc_md": arc_md,
            "template": temp_path,
            "temp_directive": temp_directive,
            "definitions": definitions_path,
            "history": history,
            "sources": sources,
        }

        md = gemsmd.CollateTableMetadata(**params)
        md_dict[obj_name] = md.dom

        if not database_md_bool:
            out_xml = Path(output_dir) / f"{obj_name}-metadata.xml"
            mu.write_xml(md.dom, out_xml)

            if error_log:
                with open(error_path, "a") as f:
                    f.write(f"mp validation report for {obj_name}\n")
                    f.write(f"{md.mp_errors}\n")

    if database_md_bool or any(
        k for k in objects if db_dict[k]["dataType"] == "Workspace"
    ):
        # work on a database-level metadata file
        if temp_dict:
            if db_name in temp_dict.keys():
                temp_path = temp_dict[db_name]
            elif "DATABASE" in temp_dict.keys():
                temp_path = temp_dict["DATABASE"]
            else:
                temp_path = None

        params = {
            "db_path": gdb,
            "db_dict": db_dict,
            "arc_md": arc_md,
            "md_dict": md_dict,
            "temp_path": temp_path,
            "temp_directive": temp_directive,
            "history": history,
            "sources": sources,
        }

        # Build a single database-level record
        db_name = Path(gdb).stem
        arcpy.AddMessage(
            f"Generating a database-level metadata record for {Path(gdb).name} that describes all tables."
        )
        database_md = gemsmd.CollateDatabaseMetadata(**params)

        report_xml = Path(output_dir) / f"{db_name}-metadata.xml"
        mu.write_xml(database_md.dom, report_xml)

    if error_log:
        with open(error_path, "a") as f:
            f.write(f"mp validation report for {db_name}\n")
            f.write(f"{database_md.mp_errors}\n\n")


if __name__ == "__main__":
    main(sys.argv[1:])
