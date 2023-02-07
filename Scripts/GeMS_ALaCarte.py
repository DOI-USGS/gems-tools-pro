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
from pathlib import Path

gdb_dict = {
    "CMULines": "line",
    "CMUMapUnitPolys": "polygon",
    "CMUPoints": "point",
    "CartographicLines": "line",
    "ContactsAndFaults": "line",
    "DataSourcePolys": "polygon",
    "DataSources": "table",
    "DescriptionOfMapUnits": "table",
    "FossilPoints": "point",
    "GenericPoints": "point",
    "GenericSamples": "point",
    "GeoMaterialDict": "table",
    "GeochronPoints": "point",
    "GeologicLines": "line",
    "Glossary": "table",
    "IsoValueLines": "line",
    "LayerList": "table",
    "MapUnitLines": "line",
    "MapUnitOverlayPolys": "polygon",
    "MapUnitPoints": "point",
    "MapUnitPolys": "polygon",
    "MiscellaneousMapInformation": "table",
    "OrientationPoints": "point",
    "OverlayPolys": "polygon",
    "PhotoPoints": "point",
    "RepurposedSymbols": "table",
    "StandardLithology": "table",
    "Stations": "point",
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

        if not fd == "#":
            fd_path = Path(gdb) / fd
            if not arcpy.Exists(str(fd_path)):
                arcpy.CreateFeatureDataset_management(gdb, fd, sr)
                out_path = str(fd_path)


if __name__ == "__main__":
    gdb = sys.argv[1]
    # gdb_items = sys.argv[2]
    value_table = arcpy.GetParameter(1)
    process(gdb, value_table)
