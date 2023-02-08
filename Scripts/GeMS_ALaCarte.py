"""Add GeMS objects a la carte to a geodatabase

    Create or augment a GeMS or GeMS-like file geodatabase by adding one or more
    objects as needed

    Attributes:
        gdb (string): path to an existing file geodatbase. Use the new file
        geodatabase context menu option when browsing to a folder to create 
        an new empty geodatabase

        gdb_items (list): a list of new GeMS ojbects to add to the gdb. Each list
        can have three items;
        [[new or existing feature dataset, spatial reference of fd, table]]
"""

import arcpy
import GeMS_Definition as gdef
import GeMS_CreateDatabase_AGP2 as cd
from pathlib import Path

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
        sr_empty = arcpy.FromWKT("POINT EMPTY").spatialReference
        sr_str = sr_empty.exportToString()
        sr = arcpy.SpatialReference()
        sr.loadFromString(sr_str)
    else:
        sr = arcpy.SpatialReference()
        sr.loadFromString(prj_str)

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


def process(gdb, value_table):
    # if gdb doesn't exist, make it
    if not Path(gdb).exists:
        folder = Path(gdb).parent
        name = Path(gdb).stem
        arcpy.CreateFileGDB_management(folder, name)

    out_path = gdb
    # collect the values from the valuetable
    for i in range(0, value_table.rowCount):
        fd = value_table.getValue(i, 0)
        sr_prj = value_table.getValue(i, 1)
        sr = eval_prj(sr_prj, fd)
        fc = value_table.getValue(i, 2)

        # feature dataset
        if not fd == "":
            fd_path = Path(gdb) / fd
            if arcpy.Exists(str(fd_path)):
                arcpy.AddMessage(f"Found existing {fd} feature dataset")
            else:
                arcpy.CreateFeatureDataset_management(gdb, fd, sr)
                arcpy.AddMessage(f"New feature dataset {fd} created")
            out_path = str(fd_path)

        # feature class or table
        if not fc == "":
            fc_path = Path(out_path) / fc
            if arcpy.Exists(str(fc_path)):
                arcpy.AddWarning(f"{fc} already exists")
            else:
                arcpy.AddMessage(f"Creating {fc}")
                if fc == "GeoMaterialDict":
                    geomat_csv = str(Path(__file__).parent / "GeoMaterialDict.csv")
                    arcpy.TableToTable_conversion(
                        geomat_csv, out_path, "GeoMaterialDict"
                    )
                else:
                    template, shape = find_temp(fc)
                    if template:
                        if shape == "table":
                            arcpy.CreateTable_management(out_path, fc, template)
                        else:
                            arcpy.CreateFeatureclass_management(
                                out_path, fc, shape, spatial_reference=sr
                            )

                        # add fields as defined in GeMS_Definition
                        field_defs = gdef.startDict[template]
                        for fDef in field_defs:
                            try:
                                arcpy.AddMessage(f"Adding field {fDef[0]}")
                                if fDef[1] == "String":
                                    # note that we are ignoring fDef[2], NullsOK or NoNulls
                                    arcpy.AddField_management(
                                        str(fc_path),
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
                                        str(fc_path),
                                        fDef[0],
                                        transDict[fDef[1]],
                                        "#",
                                        "#",
                                        "#",
                                        "#",
                                        "NULLABLE",
                                    )
                            except:
                                arcpy.AddMessage(
                                    f"Failed to add field {fDef[0]} to feature class {fc}"
                                )

                        # add a _ID field
                        arcpy.AddMessage(f"Adding field {fc}_ID")
                        arcpy.AddField_management(
                            str(fc_path), f"{fc}_ID", "TEXT", field_length=50
                        )

            # add domains


if __name__ == "__main__":
    gdb = sys.argv[1]
    # gdb_items = sys.argv[2]
    value_table = arcpy.GetParameter(1)
    process(gdb, value_table)
