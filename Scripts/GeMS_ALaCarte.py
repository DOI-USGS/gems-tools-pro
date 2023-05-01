"""Add GeMS objects a la carte to a geodatabased

    Create or augment a GeMS or GeMS-like file geodatabase by adding one or more
    objects as needed

    Attributes:
        gdb (string): path to an existing file geodatbase. Use the new file
        geodatabase context menu option when browsing to a folder to create 
        a new empty geodatabase

        gdb_items (list): a list of new GeMS ojbects to add to the gdb. Each object
        can have three items:
        [[new or existing feature dataset, spatial reference of fd, table]]
    
    Returns:
        A feature dataset or a featureclass/non-spatial table either within 
        a feature dataset, if included, or within the file geodatabase if no
        feature dataset is included. 
        
        Feature dataset or table names picked from the dropdown may include 
        prefixes to customize the object. If the name of a table is being changed,
        the fields will still be based on the template name in the dropdown list.
        
        When customizing GenericPoints or GenericSamples, add a prefix but do
        not delete the word 'Generic'. This is necessary for the tool to find the
        correct template name. In the resulting feature class, 'Generic' will be
        omitted.

        DataSources and Glossary tables will be added even if not picked on the
        parameter form.
"""

import arcpy
import GeMS_Definition as gdef
import GeMS_utilityFunctions as guf
from pathlib import Path
import sys

versionString = "GeMS_ALaCarte.py, version of 1 May 2023"
rawurl = "https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/master/Scripts/GeMS_ALaCarte.py"
guf.checkVersion(versionString, rawurl, "gems-tools-pro")

geom_dict = {
    "CMULines": "Polyline",
    "CMUMapUnitPolys": "Polygon",
    "CMUPoints": "Point",
    "CartographicLines": "Polyline",
    "ContactsAndFaults": "Polyline",
    "DataSourcePolys": "Polygon",
    "DataSources": "table",
    "DescriptionOfMapUnits": "table",
    "FossilPoints": "Point",
    "GenericPoints": "Point",
    "GenericSamples": "point",
    "GeoMaterialDict": "table",
    "GeochronPoints": "point",
    "GeologicLines": "Polyline",
    "Glossary": "table",
    "IsoValueLines": "Polyline",
    "LayerList": "table",
    "MapUnitLines": "Polyline",
    "MapUnitOverlayPolys": "Polygon",
    "MapUnitPoints": "Point",
    "MapUnitPolys": "Polygon",
    "MiscellaneousMapInformation": "table",
    "OrientationPoints": "Point",
    "OverlayPolys": "Polygon",
    "PhotoPoints": "Point",
    "RepurposedSymbols": "table",
    "StandardLithology": "table",
    "Stations": "Point",
}

transDict = {
    "String": "TEXT",
    "Single": "FLOAT",
    "Double": "DOUBLE",
    "NoNulls": "NULLABLE",  # NB-enforcing NoNulls at gdb level creates headaches; instead, check while validating
    "NullsOK": "NULLABLE",
    "Optional": "NULLABLE",
    "Date": "DATE",
}


def eval_prj(prj_str, fd):
    unk_fds = [
        "CrossSection",
        "CorrelationOfMapUnits",
    ]
    if any([x in fd for x in unk_fds]):
        # create 'UNKNOWN' spatial reference
        sr = ""
        # sr_empty = arcpy.FromWKT("POINT EMPTY").spatialReference
        # sr_str = sr_empty.exportToString()
        # sr = arcpy.SpatialReference()
        # sr.loadFromString(sr_str)
    else:
        sr = arcpy.SpatialReference()
        sr.loadFromString(prj_str)
        if sr.name == "":
            sr = ""

    return sr


def find_temp(fc):
    names = geom_dict.keys()
    n = []
    for name in names:
        if name in fc:
            n = [name, geom_dict[name]]
            break
    if n:
        return n[0], n[1]
    else:
        return None, None


def conf_domain(gdb):
    l_domains = [d.name for d in arcpy.da.ListDomains(gdb)]
    if not "ExIDConfidenceValues" in l_domains:
        conf_vals = gdef.DefaultExIDConfidenceValues
        arcpy.AddMessage("adding domain ExIDConfidenceValues")
        arcpy.CreateDomain_management(gdb, "ExIDConfidenceValues", "", "TEXT", "CODED")
        for val in conf_vals:
            arcpy.AddMessage(f"adding value {val[0]}")
            arcpy.AddCodedValueToDomain_management(
                gdb, "ExIDConfidenceValues", val[0], val[0]
            )


def required(value_table):
    found = False
    # collect the values from the valuetable
    for t in ["DataSources", "Glossary"]:
        for i in range(0, value_table.rowCount):
            vals = value_table.getRow(i).split(" ")
            if t in vals:
                found = True
        if not found:
            value_table.addRow(["", "", f"{t}"])

    return value_table


def add_geomaterial(gdb, out_path, padding):
    # check for the GeoMaterialDict table and related domains and add them
    # if they are not found in gdb. The table and domain will be added if
    # 1. GeoMaterialDict is requested or
    # 2. if a version of MapUnitPolys (with GeoMaterial field) is requested
    arcpy.env.workspace = gdb
    if not "GeoMaterialDict" in arcpy.ListTables(gdb):
        arcpy.AddMessage("Creating GeoMaterialDict")
        geomat_csv = str(Path(__file__).parent / "GeoMaterialDict.csv")
        arcpy.TableToTable_conversion(geomat_csv, out_path, "GeoMaterialDict")

    # look for domains
    # GeoMaterials
    l_domains = [d.name for d in arcpy.da.ListDomains(gdb)]
    if not "GeoMaterials" in l_domains:
        arcpy.AddMessage(f"{padding}adding domain GeoMaterials")
        arcpy.TableToDomain_management(
            geomat_csv,
            "GeoMaterial",
            "GeoMaterial",
            gdb,
            "GeoMaterials",
        )

    # GeoMaterialConfidenceValues
    if not "GeoMaterialConfidenceValues" in l_domains:
        conf_vals = gdef.GeoMaterialConfidenceValues
        arcpy.AddMessage(f"{padding}adding domain GeoMaterialConfidenceValues")
        arcpy.CreateDomain_management(
            gdb, "GeoMaterialConfidenceValues", "", "TEXT", "CODED"
        )
        for val in conf_vals:
            arcpy.AddMessage(f"{padding}  adding value {val}")
            arcpy.AddCodedValueToDomain_management(
                gdb, "GeoMaterialConfidenceValues", val, val
            )


def process(gdb, value_table):
    # check for DataSources and Glossary
    value_table = required(value_table)

    # if gdb doesn't exist, make it
    if not Path(gdb).exists:
        folder = Path(gdb).parent
        name = Path(gdb).stem
        arcpy.CreateFileGDB_management(folder, name)

    # collect the values from the valuetable
    for i in range(0, value_table.rowCount):
        out_path = gdb
        fd = value_table.getValue(i, 0)
        sr_prj = value_table.getValue(i, 1)
        sr = eval_prj(sr_prj, fd)
        fc = value_table.getValue(i, 2)

        conf_domain(gdb)

        # feature dataset
        if not fd == "":
            fd_path = Path(gdb) / fd
            if arcpy.Exists(str(fd_path)):
                arcpy.AddMessage(f"Found existing {fd} feature dataset")
                sr = arcpy.da.Describe(str(fd_path))["spatialReference"]
            else:
                arcpy.CreateFeatureDataset_management(gdb, fd, sr)
                arcpy.AddMessage(f"New feature dataset {fd} created")
            out_path = str(fd_path)
            fd_tab = "  "
        else:
            fd_tab = ""

        # feature class or table
        template = None
        if not fc == "":
            fc_name = fc.replace("Generic", "")
            fc_path = Path(out_path) / fc_name
            if arcpy.Exists(str(fc_path)):
                arcpy.AddWarning(f"{fd_tab}{fc_name} already exists")
                template, shape = find_temp(fc)
            else:
                arcpy.AddMessage(f"{fd_tab}Creating {fc_name}")
                if fc == "GeoMaterialDict":
                    add_geomaterial(gdb, out_path, f"{fd_tab}  ")
                else:
                    template, shape = find_temp(fc)
                    if template:
                        if shape == "table":
                            arcpy.CreateTable_management(out_path, fc_name)
                        else:
                            arcpy.CreateFeatureclass_management(
                                out_path,
                                fc_name,
                                shape,
                                spatial_reference=sr,
                            )
                    else:
                        arcpy.AddWarning(
                            f"GeMS template for {fc_name} could not be found"
                        )
            fc_tab = "  "

            # add fields as defined in GeMS_Definition
            if template:
                fc_fields = [f.name for f in arcpy.ListFields(fc_path)]
                field_defs = gdef.startDict[template]
                for fDef in field_defs:
                    dom_spaces = ""
                    if not fDef[0] in fc_fields:
                        try:
                            arcpy.AddMessage(f"{fd_tab}{fc_tab}Adding field {fDef[0]}")
                            if fDef[1] == "String":
                                arcpy.AddField_management(
                                    str(fc_path),
                                    fDef[0],
                                    transDict[fDef[1]],
                                    field_length=fDef[3],
                                    field_is_nullable="NULLABLE",
                                )
                            else:
                                arcpy.AddField_management(
                                    str(fc_path),
                                    fDef[0],
                                    transDict[fDef[1]],
                                    field_is_nullable="NULLABLE",
                                )
                            fld_tab = " "
                        except:
                            arcpy.AddWarning(
                                f"Failed to add field {fDef[0]} to feature class {fc}"
                            )
                    else:
                        fld_tab = ""

                    # add domain for Ex, Id, Sci confidence fields
                    if fDef[0] in (
                        "ExistenceConfidence",
                        "IdentityConfidence",
                        "ScientificConfidence",
                    ):
                        try:
                            this_field = arcpy.ListFields(fc_path, fDef[0])[0]
                            if not this_field.domain == "ExIDConfidenceValues":
                                arcpy.AssignDomainToField_management(
                                    str(fc_path), fDef[0], "ExIDConfidenceValues"
                                )
                                arcpy.AddMessage(
                                    f"{fd_tab}{fc_tab}{fld_tab}Domain ExIDConfidenceValues assigned to field {fDef[0]}"
                                )
                        except:
                            arcpy.AddWarning(
                                f"Failed to assign domain ExIDConfidenceValues to field {fDef[0]}"
                            )

                    if fDef[0] == "GeoMaterial":
                        # try:
                        this_field = arcpy.ListFields(fc_path, "GeoMaterial")[0]
                        if not this_field.domain == "GeoMaterials":
                            # double-check GeoMaterialDict and related domains
                            add_geomaterial(gdb, out_path, f"{fd_tab}{fc_tab}{fld_tab}")
                            arcpy.AssignDomainToField_management(
                                str(fc_path), fDef[0], "GeoMaterials"
                            )
                            arcpy.AddMessage(
                                f"{fd_tab}{fc_tab}{fld_tab}GeoMaterials domain assigned to field GeoMaterial"
                            )
                        # except:
                        #     arcpy.AddWarning(
                        #         f"Failed to assign domain GeoMaterials to field GeoMaterial"
                        #     )

                    # add domain for GeoMaterialConfidence
                    if fDef[0] == "GeoMaterialConfidence":
                        try:
                            this_field = arcpy.ListFields(
                                fc_path, "GeoMaterialConfidence"
                            )[0]
                            if not this_field.domain == "GeoMaterialConfidenceValues":
                                # double-check GeoMaterialDict and related domains
                                add_geomaterial(
                                    gdb, out_path, f"{fd_tab}{fc_tab}{fld_tab}"
                                )
                                arcpy.AssignDomainToField_management(
                                    str(fc_path), fDef[0], "GeoMaterialConfidenceValues"
                                )
                                arcpy.AddMessage(
                                    f"{fd_tab}{fc_tab}{fld_tab}GeoMaterialConfidenceValues domain assigned to field GeoMaterialConfidenceValue"
                                )
                        except:
                            arcpy.AddWarning(
                                f"Failed to assign domain GeoMaterialConfidenceValues to field GeoMaterialConfidenceValue"
                            )

                try:
                    if not f"{fc_name}_ID" in fc_fields:
                        # add a _ID field
                        arcpy.AddMessage(f"{fd_tab}{fc_tab}Adding field {fc_name}_ID")
                        arcpy.AddField_management(
                            str(fc_path), f"{fc_name}_ID", "TEXT", field_length=50
                        )
                except:
                    arcpy.AddWarning(f"Could not add field {fc_name}_ID")


if __name__ == "__main__":
    gdb = sys.argv[1]
    # gdb_items = sys.argv[2]
    value_table = arcpy.GetParameter(1)
    process(gdb, value_table)
