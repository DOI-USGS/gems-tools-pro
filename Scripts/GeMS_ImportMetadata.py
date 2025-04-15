"""
GeMS_ImportMetadata documentation

This script will import metadata contained in XML files provided by the user into a GeMS file geodatabase provided by
the user. This tool may be used at any point following execution of the 'A La Carte GeMS' tool or the 'Create New
Database' tool, or at any equivalent stage of GeMS geodatabase development arrived at through other means.

Usage:
    Either 1) run the Import Metadata tool in the GeMS_Tools.tbx > Metadata toolset; 2) execute this script from the
     command line, using the description of the tool/script parameters below to provide runtime input; or 3) import this
     script in another module and call the functions below from it.

Tool/script parameters:
    0) A GeMS file geodatabase.
    1) A parameter selected in the tool to control whether metadata is 'embedded' versus imported and upgraded to the
    ArcGIS metadata format. Embedded metadata is not viewable or editable in ArcGIS Pro, though it can be upgraded to do
    so at any point after embedding.
    2) A parameter selected in the tool to that is the system path to either a folder of template XML files or
    a single database-level template XML file.
    3) A boolean parameter selected in the tool to specify whether a database-level XML file will be used to propagate
    metadata to child objects in the geodatabase. Only relevant if parameter 2 is a path to a single XML file.

"""

import arcpy
import copy
from lxml import etree
from pathlib import Path
import os
import tempfile
import datetime
import sys
from lxml import etree
from dataclasses import dataclass
import GeMS_Definition as gdef
import spatial_utils as su
import metadata_utilities as mu
import GeMS_utilityFunctions as guf

from importlib import reload

reload(mu)
reload(guf)

arcprint = guf.addMsgAndPrint
mtime = os.path.getmtime(__file__)
formatted_mtime = datetime.date.fromtimestamp(mtime).strftime("%m/%d/%y")
filename = os.path.basename(__file__)
versionString = f"{filename}, version of {formatted_mtime}"
rawurl = f"https://raw.githubusercontent.com/DOI-USGS/gems-tools-pro/add-metadata-import/Scripts/{filename}"

# From the ToolValidator of the Import Metadata tool in the GeMS toolbox. It would be good to see if these constants
# can be captured programmatically instead of hard-coded in two places.
EMBED_ONLY = "Embed only"
IMPORT_AND_UPGRADE = "Import and upgrade to ArcGIS metadata format"
INPUT_PATH = "Select a folder of template files or a single template file"

im_dict = {
    "Embed only": "embed",
    "Import and upgrade to ArcGIS metadata format": "upgrade",
}


@dataclass
class MetadataHelper:
    gems = "GeMS"
    deez_nodes = {
        "idinfo_nodes": {
            "suppl": {
                "xpath": "idinfo/descript/supplinf",
                "text": "[[OBJECT]] is a composite geodataset that conforms to [[GEMS]]. Metadata records associated with each element within the geodataset contain more detailed descriptions of their purposes, constituent entities, and attributes.). These metadata were prepared with the aid of script [[SCRIPT]].",
            },
            "spdom": {"xpath": "idinfo/spdom"},
        },
        "dataqual_nodes": {
            "attraccr": {
                "xpath": "dataqual/attracc/attraccr",
                "text_exid": "Confidence that a feature exists and confidence that a feature is correctly identified are described in per-feature attributes ExistenceConfidence and IdentityConfidence.",
                "text_id": "Confidence that a feature is correctly identified is described in per-feature attribute IdentityConfidence.",
                "text_nonspatial": "This nonspatial table has been populated according to the guidelines specified in the GeMS documentation.",
                "text": "This feature attribute table has been populated according to the guidelines specified in the GeMS documentation.",
            },
            "horizpar": {
                "xpath": "dataqual/posacc/horizpa/horizpar",
                "text_lcm": "Estimated accuracy of horizontal location is given on a per-feature basis by attribute LocationConfidenceMeters. Values are expected to be correct within a factor of 2. A LocationConfidenceMeters value of -9 or -9999 indicates that no value has been assigned.",
                "text_nonspatial": "Not applicable.",
                "text": "Horizontal positional accuracy statement must be edited to complete the record.",
            },
            "logic": {
                "xpath": "dataqual/logic",
                "text": "",
                # "text": "Logic text must be edited to complete the record.",
            },
            "complete": {
                "xpath": "dataqual/complete",
                "text": "",
                # "text": "Complete text must be edited to complete the record.",
            },
            "lineage": {
                "xpath": "dataqual/lineage",
                "procstep": {"xpath": "dataqual/lineage/procstep"},
                "procdesc": {"xpath": "dataqual/lineage/procstep/procdesc"},
                "procdate": {"xpath": "dataqual/lineage/procstep/procdate"},
            },
        },
    }
    missing = False
    esri_attribs = {
        "objectid": "Internal feature number",
        "shape": "Internal geometry object",
        "shape_length": "Internal feature length, double",
        "shape_area": "Internal feature area, double",
        "ruleid": "Integer field that stores a reference to the representation rule for each feature.",
        "override": "BLOB field that stores feature-specific overrides to the cartographic representation rules.",
    }
    objects_with_exid = [
        "ContactsAndFaults",
        "GeologicLines",
        "MapUnitLines",
        "MapUnitPoints",
    ]
    objects_with_id = [
        "ContactsAndFaults",
        "GeologicLines",
        "MapUnitLines",
        "MapUnitOverlayPolys",
        "MapUnitPoints",
        "MapUnitPolys",
        "OrientationPoints",
        "OverlayPolys",
    ]
    objects_with_lcm = [
        "ContactsAndFaults",
        "FossilPoints",
        "GenericPoints",
        "GeochronPoints",
        "GeologicLines",
        "MapUnitLines",
        "MapUnitPoints",
        "OrientationPoints",
        "Stations",
    ]


def backup_existing_metadata(obj_name, db_dict, db_name):
    """Save a copy of the existing embedded metadata
    obj_name: name of the object
    v: the dictionary of Describe properties from the dictionary made bu guf.gdb_object_dict()
    db_name: the name of the database
    """
    # scratch_path = arcpy.env.scratchFolder
    # database name, find folder, make backup folder
    v = db_dict[obj_name]
    db_path = [
        v["catalogPath"] for v in db_dict.values() if v["dataType"] == "Workspace"
    ][0]
    bkp_folder = Path(db_path).parent / f"{db_name}_metadata_backup"
    bkp_folder.mkdir(exist_ok=True)

    # figure out the export name for the file
    if v["dataType"] == "Workspace":
        export_name = db_name
    elif v["feature_dataset"]:
        export_name = f"{db_name}_{v['feature_dataset']}_{obj_name}"
    else:
        export_name = f"{db_name}_{obj_name}"

    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    xml_name = f"{export_name}-metadata_{timestamp}.xml"
    backup_abspath = Path(bkp_folder) / xml_name
    style = "FGDC_CSDGM"
    arcprint(
        f"  Backing up existing metadata using '{style}' style to\n  '{backup_abspath}'."
    )
    removal_option = "EXACT_COPY"
    md_object = arcpy.metadata.Metadata(v["catalogPath"])
    md_object.exportMetadata(backup_abspath, style, removal_option)


def import_metadata(obj_xml_dict, db_dict, import_method_par, db_name):
    """Script code goes below"""

    def import_xml_file(obj_catalog_path, xml_file_path, import_method_par):
        """Embed simply or import and upgrade a metadata file into the geodatabase object"""
        md_object = arcpy.metadata.Metadata(obj_catalog_path)
        if import_method_par == "embed":
            arcprint(
                f"  Embedding metadata without upgrading to ArcGIS metadata format.\n\n"
            )
            md_xml = arcpy.metadata.Metadata(xml_file_path)
            md_object.copy(md_xml)
        else:
            arcprint(f"  Importing and upgrading to ArcGIS metadata format.\n\n")
            md_object.importMetadata(xml_file_path, "FGDC_CSDGM")
        md_object.save()

    # run through the object: metadata-file-to-import dictionary
    arcprint("Database objects:")
    for k, v in obj_xml_dict.items():
        arcprint(f"{k}")

        # first, backup the existing embedded metadata
        backup_existing_metadata(k, db_dict, db_name)

        # and import the metadata
        import_xml_file(db_dict[k]["catalogPath"], v, import_method_par)

    return


def propagate_metadata_to_xml(obj_dict, db_dict, db_xml):
    """Remove and update elements as necessary from a report-level xml file for each
    for each object in the database"""

    def update_elements(object_name, object_props, object_int_xml, db_xml):

        #  idinfo
        def update_idinfo():
            def update_citation():
                citeinfo_el = root.find("idinfo").find("citation").find("citeinfo")

                # Remove any existing lworkcit elements from the original citeinfo element
                lworkcit_tag = "lworkcit"
                for child in citeinfo_el.findall(lworkcit_tag):
                    arcprint(
                        f"  Removing '{lworkcit_tag}' from original 'citeinfo' element"
                    )
                    citeinfo_el.remove(child)

                # Make a shallow copy of citeinfo to append original lworkcit to (minus any existing lworkcit)
                # Deep copy shouldn't be necessary.
                citeinfo_el_shallowcopy = copy.copy(citeinfo_el)
                # citeinfo_el_deepcopy = copy.deepcopy(citeinfo_el)

                # create lworkcit child to append the shallow copy of citeinfo to
                lworkcit_el = etree.Element(lworkcit_tag)
                lworkcit_el.append(citeinfo_el_shallowcopy)

                # Append lworkcit element to the original citeinfo element
                citeinfo_el.append(lworkcit_el)

                # Modify the title in citeinfo to reflect the current object
                # instead of the title of the larger work, which is now in lworkcit
                citeinfo_el.find("title").text = object_name

            def update_descript():
                descript_el = root.find("idinfo").find("descript")

                # abstract element
                abstract_el = mu.extend_branch(descript_el, "abstract")
                if db_dict[object_name]["gems_equivalent"] in gdef.entityDict:
                    abstract_el.text = "[[SINGLE]] [[GEMS DEF]] [[FEATURE DATASET]]"
                else:
                    abstract_el.text = ""
                    abstract_el.append(
                        etree.Comment(
                            "'abstract' text must be populated to complete the record."
                        )
                    )
                    arcprint(
                        f"""The object '{object_name}' is not part of the standard GeMS schema. Consequently, 'abstract' text could not be populated automatically. 'abstract' text must be populated to complete the record.""",
                        1,
                    )

                # supplemental element
                supplinf = mu.extend_branch(descript_el, "supplinf")
                if not supplinf.text:
                    if not supplinf.text.startswith("[[SINGLE]]"):
                        supplinf_text = (
                            f"""[[OBJECT]] is a [[DTYPE]] in [[DB NAME]], a composite geospatial database that conforms to [[GEMS]]. This database contains [[CONTENTS]]. These metadata were prepared with the aid of script [[SCRIPT]].""",
                        )
                        supplinf.text = supplinf_text

                # purpose element
                purpose_el = mu.extend_branch(descript_el, "purpose")
                arcprint(f"{purpose_el.tag}")
                purpose_el.text = "purpose_text"
                purpose_el.append(
                    etree.Comment(
                        "'purpose' text must be populated to complete the record."
                    )
                )
                arcprint(
                    f"""'purpose' text for the object '{object_name}' was not propagated from the top-level record. 'purpose' text must be populated to complete the record.""",
                    1,
                )

            idinfo_citation_tag = "idinfo/citation"
            arcprint(
                f"Propagating and updating '{idinfo_citation_tag}' element to metadata of '{object_name}'..."
            )
            update_citation()
            idinfo_descript_tag = "idinfo/descript"
            arcprint(
                f"Propagating and updating '{idinfo_descript_tag}' element to metadata of '{object_name}'..."
            )
            update_descript()

        # dataqual
        def update_dataqual():
            dataqual_tag = "dataqual"
            arcprint(
                f"Propagating and updating '{dataqual_tag}' element to metadata of '{object_name}'..."
            )
            # dataqual_el = root.find(dataqual_tag)

            dataqual_nodes = MetadataHelper.deez_nodes["dataqual_nodes"]

            def get_element_text(key):
                """Determines the appropriate text for the element based on the object type."""
                node = dataqual_nodes[key]

                def get_attraccr_text():
                    """Get appropriate text for 'attraccr' based on object type definition."""
                    # If ExistenceConfidence and IdentifyConfidence are not part of the feature class schema or the
                    # object is an extension to the GeMS schema, execution will continue and return generic feature
                    # attribute accuracy text
                    if any(
                        obj in object_name for obj in MetadataHelper.objects_with_exid
                    ):
                        return node.get("text_exid", "")
                    elif any(
                        obj in object_name for obj in MetadataHelper.objects_with_id
                    ):
                        return node.get("text_id", "")
                    elif object_props["dataType"] == "Table":
                        return node.get("text_nonspatial", "")
                    else:
                        return node.get("text", "")

                def get_horizpar_text():
                    """Get appropriate text for 'horizpar' based on object type definition."""
                    if any(
                        obj in object_name for obj in MetadataHelper.objects_with_lcm
                    ):
                        return node.get("text_lcm", "")
                    elif object_props["dataType"] == "Table":
                        return node.get("text_nonspatial", "")
                    else:
                        return node.get("text", "")

                if key == "attraccr":
                    return get_attraccr_text()
                elif key == "horizpar":
                    return get_horizpar_text()
                else:
                    return node.get("text", "undefined")

            for n in dataqual_nodes:
                xpath = dataqual_nodes[n]["xpath"]

                # Extend branch if it doesn't exist
                if root.find(xpath) is None:
                    mu.extend_branch(root, xpath)

                # Determine the appropriate text based on object type
                element_text = get_element_text(n)

                # Update the XML element text
                element = root.find(xpath)
                if element_text != "undefined":
                    if element_text == "":
                        element.append(
                            etree.Comment(
                                f"'{n}' text must be populated to complete the record."
                            )
                        )
                    element.text = element_text

                # Remove any existing procstep elements
                if n == "lineage":
                    procstep_tag = "procstep"
                    procdesc_tag = "procdesc"
                    procdate_tag = "procdate"

                    # Remove existing process steps
                    for child in element.findall(procstep_tag):
                        arcprint(f"  Removing '{procstep_tag}' element")
                        element.remove(child)

                    # Create new process steps
                    def create_process_step():
                        # Document the creation of this record by the Import Metadata tool in a procstep
                        new_procstep = etree.SubElement(element, procstep_tag)
                        new_procdesc = etree.SubElement(new_procstep, procdesc_tag)
                        new_procdesc.text = (
                            f"This metadata record was created by {versionString}."
                        )
                        new_procdate = etree.SubElement(new_procstep, procdate_tag)
                        new_procdate.text = datetime.datetime.now().strftime("%Y%m%d")

                        # Create an empty procstep with comments noting that additional procsteps may need to be
                        # populated.
                        new_procstep = etree.SubElement(element, procstep_tag)
                        new_procstep.append(
                            etree.Comment(
                                "Existing process steps from the top-level record were removed. A new process step may be necessary to complete the record. If a new process step is not necessary, this process step must be removed."
                            )
                        )
                        new_procdesc = etree.SubElement(new_procstep, procdesc_tag)
                        new_procdesc.append(
                            etree.Comment(
                                "A new description for this processing step must be populated to complete the record."
                            )
                        )
                        new_procdate = etree.SubElement(new_procstep, procdate_tag)
                        new_procdate.append(
                            etree.Comment(
                                "A new date for this processing step must be populated to complete the record."
                            )
                        )

                    # Create and append the new process step with comments
                    create_process_step()

        # spdoinfo
        def update_spdoinfo():
            spdoinfo_tag = "spdoinfo"
            arcprint(f"Evaulating spdoinfo element for '{object_name}'...")
            spdoinfo_el = root.find(spdoinfo_tag)

            if spdoinfo_el is not None:
                # Remove existing spdoinfo regardless of object_type because it will be rebuilt for feature classes
                arcprint("  Removing spdoinfo element")
                root.remove(spdoinfo_el)
            else:
                arcprint(
                    "  The input record does not have an spdoinfo element to remove."
                )

            if obj_dict[object_name]["dataType"] in ("FeatureClass", "RasterDataset"):
                arcprint("  Calculating and adding spoinfo element")
                mu.get_spdoinfo(obj_dict, object_name, root)

        # spref should be the same between top-level and each child object in the database, though it should not
        # appear in nonspatial tables. Though it should remain the same, there's a chance it is incorrect in the
        # top-level record, so it will be rebuilt.
        def update_spref():
            spref_tag = "spref"
            arcprint(
                f"Propagating and updating '{spref_tag}' element to metadata of '{object_name}'..."
            )
            spref_el = root.find(spref_tag)

            if spref_el is not None:
                # Remove existing spref regardless of object_type because it will be rebuilt for feature classes
                arcprint(f"  Removing '{spref_tag}' element")
                root.remove(spref_el)
            else:
                arcprint(
                    f"  The input record does not have an '{spref_tag}' element to remove."
                )

            object_type = obj_dict[object_name]["dataType"]
            if object_type == "FeatureDataset":
                arcprint(f"  Populating '{spref_tag}' element")

                # can't send feature datasets to su.get_spref so get the first child of the feature dataset
                # that is a feature class and send that
                children = obj_dict[object_name]["children"]
                first_child = [
                    c["baseName"] for c in children if c["dataType"] == "FeatureClass"
                ][0]
                spref_el = su.get_spref(
                    obj_dict[first_child]["catalogPath"], object_name
                )
                if spref_el is not None:
                    # spref is in position 2 for feature datasets because they have no spdoinfo element
                    root.insert(2, spref_el)
                else:
                    arcprint(
                        f"    The '{object_name}' feature dataset has an unknown coordinate system that "
                        f"will not be propagated into the '{spref_tag}' element of the metadata "
                        f"object-level metadata.",
                        1,
                    )
            elif object_type == "FeatureClass":
                arcprint(f"  Populating '{spref_tag}' element")
                # noinspection PyBroadException
                try:
                    spref_el = su.get_spref(db_path, object_name, object_type)
                    for plandu_el in spref_el.xpath(
                        "horizsys/planar/planci/plandu[text()='metre']"
                    ):
                        plandu_el.text = "meters"
                    # spref is in position 3 for feature classes because they have a spdoinfo element
                    root.insert(3, spref_el)
                except Exception:
                    e = sys.exc_info()[1]
                    arcprint(
                        f"Could not determine the coordinate system of '{object_name}'. Check in Catalog "
                        f"that it is valid.\n    Error: {e.args[0]}",
                        1,
                    )

        # eainfo
        def update_eainfo():
            eainfo_tag = "eainfo"
            arcprint(
                f"Propagating '{eainfo_tag}' element to metadata of '{object_name}'..."
            )
            eainfo_el = root.find(eainfo_tag)

            # Create a shallow copy of detailed element if applies to the current object_name
            xpath_search = f".//detailed/enttyp[enttypl='{object_name}']"
            matching_elements = eainfo_el.findall(xpath_search)
            detailed_elements = []
            for element in matching_elements:
                detailed_el = element.getparent()
                detailed_el_shallow_copy = copy.copy(detailed_el)
                detailed_elements.append(detailed_el_shallow_copy)

            # Remove existing detailed elements
            arcprint(f"  Clearing '{eainfo_tag}' element")
            eainfo_el.clear()

            # Append the detailed_shallow_copy reflecting the current object
            if not detailed_elements:
                eainfo_el.append(
                    etree.Comment(
                        "Existing entity attribute information from the top-level record was "
                        "removed and no 'detailed/enttyp/enttypl' elements matched this object. "
                        "New entity attribute information must be populated to complete the "
                        "record."
                    )
                )
            else:
                for element in detailed_elements:
                    arcprint(f"  Populating '{eainfo_tag}' element")
                    eainfo_el.append(element)

            return detailed_elements

        # distinfo should be the same between top-level and each child object in the database
        def update_distinfo():
            distinfo_tag = "distinfo"
            arcprint(
                f"Propagating '{distinfo_tag}' element to metadata of '{object_name}'..."
            )
            # distinfo_el = root.find(distinfo_tag)

        # metainfo should be the same between top-level and each child object in the database.
        def update_metainfo():
            metainfo_tag = "metainfo"
            arcprint(
                f"Propagating '{metainfo_tag}' element to metadata of '{object_name}'..."
            )
            # metainfo_el = root.find(metainfo_tag)

        # read in the database-level xml (xml_file) and pass it to several functions to remove elements that
        # don't describe the current object
        parser = etree.XMLParser(remove_blank_text=True)
        et = etree.parse(db_xml, parser)
        root = et.getroot()

        update_idinfo()
        update_dataqual()
        update_spdoinfo()
        update_spref()
        inner_detailed_els = update_eainfo()
        update_distinfo()
        update_metainfo()
        replace_tokens(root, db_dict, object_name)

        # Write out the object level XML file after updating the elements
        et = etree.ElementTree(root)

        with open(object_int_xml, "wb") as f:
            et.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)

        # Return a list of the detailed elements that were propagated into the child-object metadata. Because they
        # were copied into the child-object metadata, they will be removed from the top-level record.
        return inner_detailed_els

    def update_top_level_record(propagated_detaileds):
        """Create a copy of the input top-level record and modify it to remove what's been propagated to the
        child objects and save the modified top-level record to the output folder so it can be imported to
        the top-level of the database."""

        def update_idinfo():
            idinfo_tag = "idinfo"
            arcprint(
                f"No changes to '{idinfo_tag}' element in metadata of '{db_name}'..."
            )
            # idinfo_el = root.find(idinfo_tag)

        def update_dataqual():
            dataqual_tag = "dataqual"
            arcprint(f"Updating '{dataqual_tag}' element in metadata of '{db_name}'...")
            dataqual_el = root.find(dataqual_tag)

            # Append a procstep element documenting the changes made by this script.
            lineage_tag = "lineage"
            procstep_tag = "procstep"
            procdesc_tag = "procdesc"
            procdate_tag = "procdate"

            # Extend branch if it doesn't exist
            lineage_el = dataqual_el.find(lineage_tag)
            if lineage_el is None:
                arcprint(f"  extending branch")
                mu.extend_branch(dataqual_el, lineage_tag)

            new_procstep = etree.SubElement(lineage_el, procstep_tag)
            new_procdesc = etree.SubElement(new_procstep, procdesc_tag)
            new_procdesc.text = (
                f"This metadata record has been modified from its original version by "
                f"{versionString}. Elements and text may have been removed from this record and "
                f"populated in object-level records."
            )
            new_procdate = etree.SubElement(new_procstep, procdate_tag)
            new_procdate.text = datetime.datetime.now().strftime("%Y%m%d")

        def update_spdoinfo():
            spdoinfo_tag = "spdoinfo"
            arcprint(
                f"No changes to '{spdoinfo_tag}' element in metadata of '{db_name}'..."
            )
            # spdoinfo_el = root.find(spdoinfo_tag)

        def update_spref():
            spref_tag = "spref"
            arcprint(
                f"No changes to '{spref_tag}' element in metadata of '{db_name}'..."
            )
            # spref_el = root.find(spref_tag)

        def update_eainfo():
            """Remove all entity attribute elements (detailed nodes) that don't correspond to
            objects in the database"""
            arcprint(f"Updating 'eainfo' element in metadata of '{db_name}'...")

            propagated = [
                el.find(".//enttyp/enttypl").text
                for el in propagated_detaileds
                if el.find(".//enttyp/enttypl") is not None
            ]
            detaileds = root.xpath("eainfo/detailed")
            for element in detaileds:
                enttypl = element.find(".//enttyp/enttypl")
                if enttypl is not None:
                    if enttypl.text not in propagated:
                        element.getparent().remove(element)

        def update_distinfo():
            distinfo_tag = "distinfo"
            arcprint(
                f"No changes to '{distinfo_tag}' element in metadata of '{db_name}'..."
            )
            # distinfo_el = root.find(distinfo_tag)

        def update_metainfo():
            metainfo_tag = "metainfo"
            arcprint(
                f"No changes to '{metainfo_tag}' element in metadata of '{db_name}'..."
            )
            # metainfo_el = root.find(metainfo_tag)

        parser = etree.XMLParser(remove_blank_text=True)
        et = etree.parse(db_xml, parser)
        root = et.getroot()

        # Modify the top-level record
        update_idinfo()
        update_dataqual()
        update_spdoinfo()
        update_spref()
        update_eainfo()
        update_distinfo()
        update_metainfo()
        replace_tokens(root, db_dict, db_name)

        # Write out the modified top-level record to the output folder
        et = etree.ElementTree(root)
        with open(gdb_xml_abspath, "wb") as f:
            et.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)

    # get the name and catalog path of the database
    db_match = [v["baseName"] for v in obj_dict.values() if v["dataType"] == "Workspace"]
    if db_match:
        # case where the database is a selected object to import into
        db_name = db_match[0]
        db_path = obj_dict[db_name]["catalogPath"]
    else:
        # case where the database is NOT a selected object to import into
        any_layer = next((v for v in obj_dict.values() if "workspace" in v))
        wksp = any_layer["workspace"]
        db_path = wksp.connectionProperties.database
        db_name = Path(db_path).stem
    # get the gdb_folder
    gdb_folder = Path(db_path).parent

    # Create a copy of the top-level XML file for each object in the database. The child object XML files will then be
    # edited to remove/add tags and content.
    # make or check for an intermediate_files folder
    int_parent = gdb_folder / "ImportMetadata_intermediate_files"
    int_parent.mkdir(parents=True, exist_ok=True)
    int_folder = arcpy.CreateUniqueName(db_name, str(int_parent))
    Path(int_folder).mkdir(parents=True, exist_ok=True)
    int_folder = Path(int_folder)
    arcprint(f"intermediate {int_folder}")

    # Keep track of all detailed elements of eainfo that were propagated from the top-level record into the
    # child-object metadata. The elements that were propagated into child-object metadata will be removed from the
    # top-level record.
    outer_detailed_els = []
    for k, v in obj_dict.items():
        if not v["dataType"] == "Workspace":
            int_path = int_folder / f"{k}.xml"
            outer_detailed_els += update_elements(k, v, str(int_path), db_xml)

    gdb_xml_name = f"{db_name}-metadata.xml"
    gdb_xml_abspath = int_folder / gdb_xml_name
    update_top_level_record(outer_detailed_els)
    return int_folder


def replace_tokens(root, db_dict, object_name):
    """Replace [[TOKENS]] in each child element of an element"""
    for elem in root.getiterator():
        if elem.text:
            new_text = mu.tokens(elem.text, db_dict, versionString, object_name)
            if new_text:
                if new_text == "REMOVE NODE":
                    elem.getparent().remove(elem)
                    next
                else:
                    elem.text = new_text


def sync_labels(root, object_name, db_dict):
    """Make sure elements enttypl and attrlabl for the _ID field match the table name.
    If the the xml to import is chosen (in metadata_utilities.object_template_dict()) by any
    method other than an exact match, the values of enttypl and attrlabl (TableName_ID)
    will not match the table name"""

    # sync the enttypl element
    enttypl = root.xpath("eainfo/detailed/enttyp/enttypl")
    for ent in enttypl:
        ent.text = object_name

    # sync the attrlabl element for the _ID field
    # find the _ID fields as it is stored in the database itself. It SHOULD always be
    # the same as the TableName, but who knows? Better to report what is in the db rather than presume.
    fields = db_dict[object_name]["fields"]
    matches = [f.name for f in fields if f.name.endswith("_ID")]
    if matches:
        id_field = matches[0]
    else:
        id_field = None

    if id_field:
        attrlabls = root.xpath(
            "eainfo/detailed/attr/attrlabl[substring(text(), string-length(text()) - string-length('_ID') + 1) = '_ID']"
        )
        if attrlabls:
            attrlabl = attrlabls[0]
            attrlabl.text = id_field


if __name__ == "__main__":
    # TODO: When pushed to the GitHub repo, implement version checking
    # guf.checkVersion(versionString, rawurl, "gems-tools-pro")

    gdb_par = arcpy.GetParameterAsText(0)
    db_name = Path(gdb_par).stem

    objects_par = arcpy.GetParameterAsText(1)
    if not type(objects_par) is list:
        objects_par = objects_par.split(";")

    import_method_par = arcpy.GetParameterAsText(2)
    if not import_method_par in ("embed", "upgrade"):
        import_method_par = im_dict.get(import_method_par)
    if import_method_par is None:
        import_method_par = "upgrade"

    metadata_input_path = arcpy.GetParameterAsText(3)
    propagate_metadata_par = arcpy.GetParameterAsText(4).lower() == "true"

    # make Describe-like dictionary of all objects in the database,
    # including the database itself
    db_dict = guf.gdb_object_dict(gdb_par)

    # process everything in database if a list of objects was not supplied
    if not objects_par:
        objects_par = db_dict.keys()
    else:
        # The objects parameter list the database with its .gdb extension to distinguish from
        # an object in the database with the name of the database.
        # The database dictionary does not use the .gdb extension as a key, so it must be
        # removed for subsequent processing to work with the expected keys.
        objects_par = [s[:-4] if s.endswith('.gdb') else s for s in objects_par]

    # if import files are in a directory
    if Path(metadata_input_path).is_dir():
        # make a dictionary of xml file: file path in the folder
        xml_dict = mu.md_dict_from_folder(metadata_input_path)

        # make a dictionary of object_name: matching xml to import
        obj_xml_dict = mu.object_template_dict(db_dict, xml_dict, objects_par)

        # replace [[TOKENS]] in the xml files
        # tokenized_xml returns a temporary file, rebuild the object: xml-file dictionary
        xml_tmp_dict = {}
        for k, v in obj_xml_dict.items():
            # make a temporary file to edit and then import
            temp_xml = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{k}.xml")
            tree = etree.parse(v)
            root = tree.getroot()

            # run through a couple editing functions
            replace_tokens(root, db_dict, k)
            if k != db_name:
                sync_labels(root, k, db_dict)

            # set the object name and xml to import dictionary entry
            tree.write(temp_xml)
            xml_tmp_dict[k] = temp_xml.name
            temp_xml.close()

        import_metadata(xml_tmp_dict, db_dict, import_method_par, db_name)

    # if a single XML was supplied
    elif Path(metadata_input_path).suffix == ".xml":
        # # assess the propagate directive
        # obj_dict = {k: tmp_xml for k in db_dict.keys() if k in objects_par}
        obj_dict = {k: v for k, v in db_dict.items() if k in objects_par}
        if propagate_metadata_par:
            # md_helper = MetadataHelper(gdb_par)
            metadata_input_folder = propagate_metadata_to_xml(
                obj_dict, db_dict, metadata_input_path
            )

            # Intermediate XML files have now been created for all objects in the database.
            xml_dict = mu.md_dict_from_folder(metadata_input_folder)
        else:
            xml_dict = {}
            # Allow importing of a single metadata file into multiple objects
            # Warning is shown in tool when multiple objects are selected.
            for obj in objects_par:
                xml_dict[obj] = metadata_input_path

        # Now import the XML files into each object of the database.
        import_metadata(xml_dict, db_dict, import_method_par, db_name)
