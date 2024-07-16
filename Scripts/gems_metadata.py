from datetime import datetime

start_time = datetime.now()

import arcpy
import csv
from lxml import etree
import tempfile
from pathlib import Path
import subprocess
import time
import sys

toolbox_folder = Path(__file__).parent.parent
scripts_folder = toolbox_folder / "Scripts"
metadata_folder = toolbox_folder / "Resources" / "metadata"
# templates_folder = metadata_folder / "templates"

sys.path.append(scripts_folder)
import GeMS_utilityFunctions as guf
import GeMS_Definition as gdef
import spatial_utils as su


def print_time(func):
    end_time = datetime.now()
    print(func, f"Duration: {end_time - start_time}")


"""
sources_choice = {
    "save only DataSources": 1,
    "save only embedded sources": 2,
    "save only template sources": 3,
    "save DataSources and embedded sources": 4,
    "save DataSources and template sources": 5,
    "save embedded and template sources": 6,
    "save all sources": 7,
    "save no sources": 8,
}

history_choices = {
    "clear all history": 1,
    "save only embedded history": 2,
    "save only template history": 3,
    "save all history": 4,
}
"""

gems_edom = gdef.enumeratedValueDomainFieldList

esri_attribs = {
    "objectid": "Internal feature number",
    "shape": "Internal geometry object",
    "shape_length": "Internal feature length, double",
    "shape_area": "Internal feature area, double",
    "ruleid": "Integer field that stores a reference to the representation rule for each feature.",
    "override": "BLOB field that stores feature-specific overrides to the cartographic representation rules.",
}

child_nodes = [
    (0, "idinfo"),
    (1, "dataqual"),
    (2, "spdoinfo"),
    (3, "spref"),
    (4, "eainfo"),
    (5, "distinfo"),
    (6, "metainfo"),
]

gems_full_ref = """GeMS (Geologic Map Schema)--a standard format for the digital publication of geologic maps", available at http://ngmdb.usgs.gov/Info/standards/GeMS/"""

gems = "GeMS"

ap = guf.addMsgAndPrint


class CollateFGDCMetadata:
    def __init__(
        self,
        table,
        gdb_dict,
        embedded_only=False,
        arc_md=True,
        template=None,
        temp_directive="replace",  # options are "replace" or "append"
        definitions=None,
        history=3,
        sources=1,
    ):
        self.table = table
        self.db_dict = gdb_dict
        self.embedded_only = embedded_only
        self.arc_md = arc_md
        self.template = template
        self.temp_directive = temp_directive
        self.definitions = definitions
        self.history = history
        self.sources = sources

        self.table_defs = {}
        self.field_defs = {}
        if definitions:
            self.table_defs = self._table_defs_from_csv()
            self.field_defs = self._field_defs_from_csv()

        # self.dom = None
        self.is_db = False
        self.log_list = []
        # self.mp_errors = None

        parts = Path(gdb_dict[table]["catalogPath"]).parts
        gdb_folder = parts[0]
        for part in parts:
            if not part.endswith(".gdb") and not part.endswith(".gpkg"):
                gdb_folder = Path(gdb_folder) / part
            else:
                break
        self.log_file = str(gdb_folder / f"{table}_collate_metadata.txt")

        # make python dictionaries of the data dictionary tables
        sources_dict = self._term_dict("DataSources", ["DataSources_ID", "Source"])
        self.dds = {
            "sources_dict": sources_dict,
            "units_dict": self._term_dict(
                "DescriptionOfMapUnits",
                ["MapUnit", "Name", "Fullname", "DescriptionSourceID"],
                sources_dict,
            ),
            "geomat_dict": self._term_dict(
                "GeoMaterialDict", ["GeoMaterial", "Definition"], sources_dict
            ),
            "gloss_dict": self._term_dict(
                "Glossary", ["Term", "Definition", "DefinitionSourceID"], sources_dict
            ),
        }

        #
        md = self.build_metadata()
        self.dom = md[0]
        self.errors = md[1]

    def build_metadata(self):
        if self.embedded_only or self.arc_md:
            # this will set self.dom to the dom of the exported metadata
            # lineage/srcinfo will be removed if sources in (1, 3, 5, 8)
            # lineage/procstep will be removed if history in (1, 2)
            self._export_embedded()
        else:
            # this will set self.dom to a mostly empty dom built from scratch
            self._md_from_scratch()

        if self.db_dict[self.table].get("spatialReference"):
            # add spref info, not exported from ArcGIS Pro into FGDC CSDGM
            # ESRI BUG-000124294 https://support.esri.com/en-us/bug/in-arcgis-pro-when-an-extensible-markup-language-xml-fi-bug-000124294
            self._add_spref()

        # exit early if _export_embedded is True.
        # at this point metadata will have everything verbatim from the embedded metadata plus
        # spdom, spdoinfo, and spref - things that should be calculated each time from inherent spatial properties
        # note that spdom is only calculated by ArcGIS when metadata are exported if the values are empty or there
        # is an error in the embedded metadata.
        # If they have been filled out and are valid, they will be exported, though they might not be relevant to or
        # correct for the data.
        if self.embedded_only:
            self._mp_upgrade()
            return self.dom, self.mp_errors

        if self.template:
            # lineage/srcinfo will be removed if sources in (1, 2, 4, 8)
            # lineage/procstep will be removed if history in (1, 3)
            self._add_template_metadata()

        if self.sources in (1, 4, 5, 7):
            # choices 1, 4, 5, 7 include DataSources
            self._add_datasources()

        if (
            self.table_defs
            and self.table in self.table_defs
            or self.field_defs
            and self.table in self.field_defs
        ):
            self._add_csv_metadata()

        self._add_domains()

        self._ESRI_fields()

        self._mp_upgrade()

        return self.dom, self.mp_errors

    def _export_embedded(self):
        table_path = self.db_dict[self.table]["catalogPath"]
        # export the embedded metadata to a temporary file
        # parse it and return the xml dom
        # synchronizing ensures that there will be eainfo/detailed nodes for every field
        temp_dir = tempfile.TemporaryDirectory()
        temp_xml = Path(temp_dir.name) / "temp.xml"
        src_md = arcpy.metadata.Metadata(table_path)
        # src_md.synchronize("SELECTIVE")
        src_md.exportMetadata(str(temp_xml), "FGDC_CSDGM")

        # parse the output file and get the root element
        self.dom = etree.parse(str(temp_xml)).getroot()

        # check for removing embedded sources and history (process steps)
        # but don't proceed if there is no lineage node
        if self.dom.xpath("dataqual/lineage"):
            lineage = self.dom.xpath("dataqual/lineage")[0]
            if self.sources in (1, 3, 5, 8):
                for srcinfo in lineage.findall("srcinfo"):
                    lineage.remove(srcinfo)

            if self.history in (1, 3):
                for procstep in lineage.findall("procstep"):
                    lineage.remove(procstep)

        # add all top-level child nodes in case they are not exported
        # for child in child_nodes:
        #     if self.dom.find(child[1]) is None:
        #         el = etree.Element(child[1])
        #         self.dom.insert(child[0], el)

        # if this is a table and has a detailed node
        # find the attr nodes and add the required children
        # detailed = self.dom.find("eainfo/detailed")
        # if not detailed is None:
        #     attrs = detailed.findall("attr")
        #     for attr in attrs:
        #         for n in ("attrdef", "attrdefs"):
        #             self._extend_branch(attr, n)

    def _md_from_scratch(self):
        """write out the top-level children and the eainfo/detailed node from the actual
        list of fields in the table"""

        # make all the metadata first-level children
        metadata = etree.Element("metadata")
        for child in child_nodes:
            etree.SubElement(metadata, child[1])

        # make a detailed node
        detailed = etree.SubElement(metadata.find("eainfo"), "detailed")

        # make an enttyp node with a enttypl (label) node
        enttyp = etree.SubElement(detailed, "enttyp")
        enttypl = etree.SubElement(enttyp, "enttypl")
        enttypl.text = Path(self.table).name

        # make one attr/attrlabl per field
        for field in arcpy.ListFields(self.table):
            attr = etree.SubElement(detailed, "attr")
            attrl = etree.SubElement(attr, "attrl")
            attrl.text = field.name

        self.dom = etree.ElementTree(metadata).getroot()

    def _add_spref(self):
        """Create a spref - spatial reference information node for the resource
        based on slightly modified versions of spatial_utils.py and xml_utils.py
        from the USGS Metadata Wizard library"""
        d = self.db_dict
        wksp = d[self.table]["workspace"]
        db_path = wksp.connectionProperties.database
        try:
            spref_node = su.get_spref(db_path, self.table)
        except Exception as e:
            arcpy.AddWarning(
                f"""Could not determine the coordinate system of {self.table}.
            Check in ArcCatalog that it is valid"""
            )
            arcpy.AddWarning(e)
            print(e)
        self.dom.insert(3, spref_node)

    def _add_template_metadata(self):
        template_tree = etree.parse(self.template)
        # remove nodes specified by source and history choices
        # first check for lineage node
        if self.dom.xpath("dataqual/lineage"):
            temp_lineage = template_tree.xpath("dataqual/lineage")[0]
            # make a copy of the sources nodes
            # for choices 5, 6, and 7 they will be added back but with
            # other sources (from either embedded or DataSources)
            # and the entire list will be sorted
            if self.sources in (5, 6, 7):
                self.temp_sources = template_tree.xpath("dataqual/lineage/srcinfo")

            # make a copy of the process steps for history choice 4
            # for same reason as above
            if self.history == 4:
                self.temp_history = template_tree.xpath("dataqual/lineage/procstep")

            # if template sources and history are NOT to be added,
            # remove those nodes from the template dom
            if self.sources in (1, 2, 4, 8):
                for srcinfo in temp_lineage.findall("srcinfo"):
                    temp_lineage.remove(srcinfo)

            if self.history in (1, 2):
                for procstep in temp_lineage.findall("procstep"):
                    temp_lineage.remove(procstep)

        # the number and order of entities in the template file may not be the
        # same as in the table we are writing metadata for.
        # copy and then delete that information from the template
        # the dictionary will be used below when writing out the detailed node
        # detailed_dict[attribute label/field name] = etree Element (attr node with all children)
        temp_detailed_dict = {}
        template_detailed = template_tree.find("eainfo/detailed")
        if template_detailed is not None:
            for attr in template_detailed.findall("attr"):
                label = attr.find("attrlabl").text
                temp_detailed_dict[label] = attr
            template_detailed.getparent().remove(template_detailed)

        # add the attribute definitions from the dictionary we just made
        detailed = self.dom.find("eainfo/detailed")
        if detailed is not None:
            for attr in detailed.findall("attr"):
                label = attr.find("attrlabl").text

                # look for the field name in the attribute definition dictionary from the template
                if label in temp_detailed_dict:
                    # the dictionary value is an etree element
                    copy_attr = temp_detailed_dict[label]

                    # "attrdef", "attrdefs" are in all template attr elements
                    for n in ("attrdef", "attrdefs"):
                        # use extend_branch to create them if they don't exist in the source detailed node
                        self._extend_branch(attr, n)
                        # and set the text to the text in the template
                        attr.find(n).text = copy_attr.find(n).text

                    # if there are any attrdomv elements in the template, delete the one in
                    # self.dom and they will be added below
                    els = copy_attr.findall("attrdomv")
                    if len(els) > 0:
                        # try/except block rather than testing first for existence of attrdomv
                        # in self.dom
                        try:
                            attr.remove(attr.find("attrdomv"))
                        except:
                            pass

        # add any remaining nodes from the template
        for el in [
            n
            for n in template_tree.iter()
            if not any(
                s in template_tree.getelementpath(n) for s in ("spref", "spdoinfo")
            )
        ]:
            el_path = template_tree.getelementpath(el)
            el_text = template_tree.xpath(el_path)[0].text

            # check for printable text at the end of the template node xpath
            if el_text and el_text != "None" and el_text.isprintable():
                print(el_path)
                # make sure the same node exists in the self.dom
                self._extend_branch(self.dom, el_path)
                node = self.dom.xpath(el_path)[0]

                # check for existing text
                if node.text and node.text.isprintable():
                    # if the temp_directive is "replace", overwrite any existing text
                    if self.temp_directive == "replace":
                        node.text = el_text
                    else:
                        # otherwise, append the template text to the end of the existing text
                        node.text = f"{node.text}\n{el_text}"
                else:
                    node.text = el_text

        # NOTE - xpath for finding the parent of nodes with mulitple tags
        # attrdomv = attr.xpath("attrdomv/*[self::udom or self::rdom or self::codesetd]/parent::*")

    def _add_datasources(self):
        # translate rows from the DataSources table into dataqual/lineage/srcinfo nodes
        # first, bail if there is no DataSources table
        if not "DataSources" in self.db_dict:
            arcpy.AddMessage("Could not find a DataSources table. Skipping this step")
            return

        lineage = self.dom.find("dataqual/lineage")
        ds_path = self.db_dict["DataSources"]["catalogPath"]
        fields = ["Source", "URL", "DataSources_ID"]
        with arcpy.da.SearchCursor(ds_path, fields) as cursor:
            for row in cursor:
                srcinfo = etree.SubElement(lineage, "srcinfo")

                self._extend_branch(srcinfo, "srccite/citeinfo/title")
                title = srcinfo.find("srccite/citeinfo/title")
                title.text = row[0]

                if row[1]:
                    self._extend_branch(srcinfo, "srccite/citeinfo/onlink")
                    onlink = srcinfo.find("srccite/citeinfo/onlink")
                    onlink.text = row[0]

                srccitea = etree.SubElement(srcinfo, "srccitea")
                srccitea.text = row[2]

    def _add_csv_metadata(self):
        """Add entity and attribute definition and definition sources for custom fields
        all GeMS definitions are in template xml files"""
        # get the detailed node for this table
        detailed = self.dom.xpath(
            f"eainfo/detailed/enttyp/enttypl[text()='{self.table}']/parent::*/parent::*"
        )[0]

        # if we have a definition in the CSV, add it
        if self.table in self.table_defs:
            self._def_and_source(
                detailed, "enttypd", "enttypds", self.table_defs[self.table]
            )

        # collect the fields for this table
        # self.field_defs is a dictionary of {table: a list of one or more lists of properties for all fields described
        #   for that table in csv definitions}
        field_list = None
        for field in self.db_dict[self.table]["fields"]:
            fname = field.name

            # look for a field definition for this field in field_defs
            # priority goes to a field in this specific table
            if self.table in self.field_defs:
                field_list = [n for n in self.field_defs[self.table] if n[0] == fname]

            # backup looking for a definition that can be in __any_table__
            if not field_list:
                if "__any_table__" in self.field_defs:
                    field_list = [
                        n
                        for n in self.field_defs["__any_table__"]
                        if n and n[0] == fname
                    ]

            if field_list:
                field = field_list[0]
                attrs = detailed.xpath(f"attr/attrlabl[text()='{fname}']/parent::*")
                for attr in attrs:
                    self._def_and_source(
                        attr, "attrdef", "attrdefs", [field[1], field[2]]
                    )

    def _ESRI_fields(self):
        # get the detailed node for this table
        detailed = self.dom.xpath(
            f"eainfo/detailed/enttyp/enttypl[text()='{self.table}']/parent::*/parent::*"
        )[0]

        # find all child attr nodes
        attrs = detailed.findall("attr")
        for attr in attrs:
            attrlabl = attr.find("attrlabl")
            # if this field is a regular ESRI controlled field
            if attrlabl.text.lower() in esri_attribs:
                self._def_and_source(
                    attr,
                    "attrdef",
                    "attrdefs",
                    [esri_attribs[attrlabl.text.lower()], "ESRI"],
                )
            else:
                # first check if this is an ESRI annotation feature class
                # in that case all other fields get defined simply
                if (
                    self.db_dict[self.table]["concat_type"]
                    == "Annotation Polygon FeatureClass"
                ):
                    def_text = (
                        "Value controls placement or representation of annotation"
                    )
                    self._def_and_source(
                        attr, "attrdef", "attrdefs", [def_text, "ESRI"]
                    )

    def _add_domains(self):
        """Fills in domain (field values) information"""
        # get the detailed node for this table
        detailed = self.dom.xpath(
            f"eainfo/detailed/enttyp/enttypl[text()='{self.table}']/parent::*/parent::*"
        )[0]

        # collect the fields for this table from the database dictionary
        for f in self.db_dict[self.table]["fields"]:
            # f is an arcpy field object
            fname = f.name

            # find the attribute node for this field
            attrs = detailed.xpath(f"attr/attrlabl[text()='{fname}']/parent::*")

            # although this is a for loop, it should only run through once
            # constrained by fname above
            for attr in attrs:
                # look for a domain values for this field in field_defs
                # field_defs is built from csv definitions file
                # priority goes to a field in this specific table
                # finding a field properties list that is longer than 4 means
                # there is domain information
                field_w_dom = None

                if self.field_defs.get(self.table):
                    field_w_dom = [
                        n
                        for n in self.field_defs[self.table]
                        if n[0] == fname and len(n) > 3
                    ]
                # backup looking for a definition that can be in __any_table__
                if not field_w_dom:
                    if self.field_defs:
                        field_w_dom = [
                            n
                            for n in self.field_defs["__any_table__"]
                            if n[0] == fname and len(n) > 3
                        ]

                # if field_w_dom, then we have domain information
                if field_w_dom:
                    # but first determine if there is an attrdomv node that will be overwritten
                    if attr.find("attrdomv") is not None:
                        arcpy.AddWarning(
                            f"Attribute domain information for field {fname} will be overwritten with information from definitions CSV file. Check log file for details:\n{self.log_file}"
                        )

                        print(
                            f"Attribute domain information for field {fname} will be overwritten with information from definitions CSV file. Check log file for details:\n{self.log_file}"
                        )

                        # save some details for the log file
                        preface = f"Attribute domain information, from embedded or template metadata, has been overwritten for field {fname} in {self.table}. The original nodes and values are:"
                        self.log_list.append(preface)
                        for attrdomv in attr.findall("attrdomv"):
                            for child in attrdomv:
                                self.log_list.append(f"{child.tag}: {child.text}")
                            attr.remove(attrdomv)
                        end = "Compare with final values in output metadata.\n"
                        self.log_list.append(end)

                    # add the domain information
                    field = field_w_dom[0][0]
                    d_type = field_w_dom[0][3]

                    # there is not necessarily a 'domain_values' entry
                    if len(field_w_dom[0]) > 4:
                        d_vals = field_w_dom[0][4]
                    else:
                        d_vals = None

                    tuples = None
                    if d_type == "rdom":
                        attrdomv = etree.SubElement(attr, "attrdomv")
                        # rdom = etree.SubElement(attrdomv, "rdom")
                        if d_vals:
                            nodes = ("rdommin", "rdommax", "attrunit", "attrmres")
                            vals = d_vals.split(",")
                            tuples = [
                                (nodes[i], vals[i].strip()) for i in range(len(vals))
                            ]
                            self._domain_nodes(attrdomv, d_type, tuples)

                    if d_type == "codsetd":
                        attrdomv = etree.SubElement(attr, "attrdomv")
                        codesetd = etree.SubElement(attrdomv, "codesetd")
                        if d_vals:
                            nodes = ("codesetn", "codesets")
                            vals = d_vals.split(",")
                            tuples = [(nodes[i], vals[i]) for i in range(len(vals))]
                            self._domain_nodes(codesetd, d_type, tuples)

                    if d_type == "udom":
                        attrdomv = etree.SubElement(attr, "attrdomv")
                        udom = etree.SubElement(attrdomv, "udom")
                        if d_vals:
                            udom.text = d_vals
                        else:
                            udom.text = "Unrepresentable domain"

                    if d_type == "edom":
                        arcpy.AddMessage(
                            f"found domain values for {self.table} {field}"
                        )
                        print(f"found domain values for {self.table} {field}")
                        # delete the single childless attrdomv so that we can add multiple
                        # children in a loop
                        if attr.find("attrdomv") is not None:
                            attr.remove(attr.find("attrdomv"))

                        if d_vals:
                            print(f"d_vals {d_vals}")
                            nodes = ("edomv", "edomvd", "edomvds")
                            edoms = d_vals.split("|")
                            for edom in edoms:
                                attrdomv = etree.SubElement(attr, "attrdomv")
                                vals = edom.split(",")
                                tuples = [
                                    (nodes[i], vals[i].strip())
                                    for i in range(len(vals))
                                ]
                                self._domain_nodes(attrdomv, d_type, tuples)

                # if this field is in the list of gems-defined enumerated domain fields
                elif fname.lower() in [
                    n.lower() for n in gems_edom
                ] or fname.lower() in [
                    guf.camel_to_snake(n).lower() for n in gems_edom
                ]:
                    # delete the single childless attrdomv so that we can add multiple
                    # children in a loop
                    if attr.find("attrdomv") is not None:
                        attr.remove(attr.find("attrdomv"))

                    # collect a unique set of all the values in this field
                    with arcpy.da.SearchCursor(
                        self.db_dict[self.table]["catalogPath"], fname
                    ) as cursor:
                        fld_vals = set([row[0] for row in cursor if not row[0] is None])

                    # iterate through the values
                    for val in fld_vals:
                        attrdomv = etree.SubElement(attr, "attrdomv")
                        edom = etree.SubElement(attrdomv, "edom")

                        if fname.lower().endswith("sourceid"):
                            val_text = self._catch_m2m(self.dds["sources_dict"], val)
                            val_source = "This report"

                        # otherwise, find the appropriate dictionary and put the definition
                        # and definition source into def_text and def_source
                        else:
                            val_dict = self._which_dict(self.table, fname)
                            if val in val_dict:
                                val_text = val_dict[val][0]
                                val_source = val_dict[val][1]
                            else:
                                val_text = ""
                                val_source = ""

                        etree.SubElement(edom, "edomv").text = val
                        etree.SubElement(edom, "edomvd").text = val_text
                        etree.SubElement(edom, "edomvds").text = val_source

                else:
                    attrdomv = etree.SubElement(attr, "attrdomv")
                    udom = etree.SubElement(attrdomv, "udom").text = (
                        "Unrepresentable domain"
                    )

    def _def_and_source(self, parent, def_xpath, source_xpath, text_list):
        # whether missing or blank add node and/or definition and definition source text
        # to an entity or attribute node
        if parent.find(def_xpath) is None:
            # it doesn't make sense if definition is blank but there exists a
            # definition source node, however, don't check the text, just remove
            if parent.find(source_xpath) is not None:
                parent.remove(parent.find(source_xpath))

            # now add nodes by xpath, leave text empty for now
            etree.SubElement(parent, def_xpath)
            etree.SubElement(parent, source_xpath)

        # now we know we can find a def_xpath node, check the text
        def_node = parent.find(def_xpath)
        if text_list[0]:
            def_node.text = text_list[0]
        # and update the definition source regardless
        if text_list[1]:
            parent.find(source_xpath).text = text_list[1]

    def _term_dict(self, table, fields, sources_dict=None):
        """sources_dict needs to be built first
        returns:
        sources - {Source: DataSources_ID as str}
        geomaterial = {GeoMaterial: [Definition, "GeMS"]} as list
        map units - {Unit: [(1st choice) Name (2nd choice) FullName, DescriptionSourceID] as list}
        glossary - {Term: [Definition, DefinitionSourceID] as list}
        """
        # always supply field to be the dictionary key as fields[0]
        # and the 'ID' field as fields[-1]
        if table in self.db_dict:
            table_path = self.db_dict[table]["catalogPath"]
            data_dict = {}
            with arcpy.da.SearchCursor(table_path, fields) as cursor:
                for row in cursor:
                    if table == "DataSources":
                        if not row[1] is None:
                            data_dict[row[0]] = row[1]

                    if table == "GeoMaterialDict":
                        data_dict[row[0]] = [row[1], gems]

                    if table == "DescriptionOfMapUnits":
                        # if there is a MapUnit value
                        if row[0]:
                            if not row[2] is None:
                                # if there is a FullName, that is the value of the mapunit key
                                data_dict[row[0]] = [row[2]]
                            else:
                                if not row[1] is None:
                                    # otherwise use the Name
                                    data_dict[row[0]] = [row[1]]
                            # append the SourceID
                            data_dict[row[0]].append(
                                self._catch_m2m(sources_dict, row[-1])
                            )
                        else:
                            data_dict[row[0]] = list(row[1:-1])
                            data_dict[row[0]].append(
                                self._catch_m2m(sources_dict, row[-1])
                            )

                    if table == "Glossary":
                        data_dict[row[0]] = [row[1], row[2]]

            return data_dict
        else:
            return None

    def _which_dict(self, tbl, fld):
        if fld.lower() in ("mapunit", "map_unit"):
            return self.dds["units_dict"]
        elif fld.lower() in ("geomaterialconfidence", "geo_material_confidence"):
            if tbl.lower() in ("descriptionofmapunits", "description_of_map_units"):
                return gdef.GeoMatConfDict
        elif fld in ("geomaterial", "geo_material"):
            return self.dds["geomat_dict"]
        elif fld.lower().find("sourceid") > -1:
            return self.dds["sources_dict"]
        else:
            return self.dds["gloss_dict"]

    def _catch_m2m(self, dictionary, field_value):
        """DataSourceIDs could be concatenated, eg., "DAS03 | DAS05"
        To list these values properly when writing out enumerated domains,
        look here for a delimiter, split the foreign keys, look them up, and
        return a concatenated string of sources
        or just return the dictionary entry if field_value is not concatenated
        """
        if not field_value is None:
            if "|" in field_value:
                defs = []
                src_ids = field_value.split("|")
                for src_id in src_ids:
                    src_id = src_id.strip()
                    if src_id in dictionary:
                        defs.append(dictionary[src_id][0])
                    else:
                        defs.append(f"PROVIDE A DEFINITION FOR {src_id}")
                def_str = " | ".join(defs)
                return def_str
            else:
                if field_value in dictionary:
                    return dictionary[field_value]
                else:
                    return f"PROVIDE A DEFINITION FOR {field_value}"
        else:
            return

    def _table_defs_from_csv(self):
        # read the csv of definitions
        table_defs = {}
        with open(self.definitions, mode="r") as file:
            defs_csv = list(csv.reader(file, skipinitialspace=True))
            table_defs = {
                row[0]: [row[2], row[3]]
                for row in defs_csv
                if len(row) > 1
                and not row[0].lower() in ("table", "any table")
                and not row[1]
            }

        return table_defs

    def _field_defs_from_csv(self):
        # read the csv of definitions. Each line has:
        # table, field, definition, definition_source, domain_type, domain_values
        # if table is blank in CSV, that field is defined the same everywhere it is found
        field_defs = {}
        with open(self.definitions, mode="r") as file:
            defs_csv = list(csv.reader(file, skipinitialspace=True))

            # TABLE, FIELD, DEFINITION, DEFINITION SOURCE, DOMAIN TYPE, DOMAIN VALUE
            fields = [
                row
                for row in defs_csv
                if row and not row[0].startswith("#") and not row[0].lower() == "table"
            ]

            for field in fields:
                if field[0].lower() == "any table":
                    table = "__any_table__"
                else:
                    table = field[0]

                if table in field_defs:
                    field_defs[table].append(field[1:])
                else:
                    field_defs[table] = [field[1:]]

        return field_defs

    def _domain_nodes(self, parent, d_type, tuples):
        child = etree.SubElement(parent, d_type)
        for t in tuples:
            etree.SubElement(child, t[0]).text = t[1]

    def _remove_node(tree, xpath):
        remove = tree.xpath(xpath)[0]
        remove.getparent().remove(remove)

    def _extend_branch(self, node, xpath):
        """function to test for full xpath and if only partially exists,
        builds it out the rest of the way"""
        # search for nodes on the xpath, building them from the list, delimited by /
        path_nodes = xpath.split("/")
        for nibble in path_nodes:
            search_node = node.find(nibble)
            if search_node is not None:
                node = search_node
            else:
                node = etree.SubElement(node, nibble)

    def _mp_upgrade(self):
        """mp.exe fixes a number of structural issues through the 'upgrade' option
        https://geology.usgs.gov/tools/metadata/tools/doc/upgrade.html"""

        mp_path = metadata_folder / "mp.exe"
        config_path = metadata_folder / "mp_config"
        tree = etree.ElementTree(self.dom)

        # save self.dom in a temporary directory
        with tempfile.TemporaryDirectory() as tempdirname:
            dom_xml = Path(tempdirname) / "dom_out.xml"
            with open(dom_xml, "wb") as f:
                tree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)

            # send temporary file through mp.exe and collect the output
            err_out = Path(tempdirname) / "errors.txt"
            x_out = Path(tempdirname) / "xml_out.xml"
            mp_args = [
                str(mp_path),
                str(dom_xml),
                "-c",
                str(config_path),
                "-x",
                str(x_out),
            ]

            subprocess.call(mp_args)

            # now that our xml has been upgraded, check the output just written for errors
            # call mp again
            mp_args = [
                str(mp_path),
                str(x_out),
                "-e",
                str(err_out),
            ]

            subprocess.call(mp_args)

            # parse the mp-upgraded xml into self.dom
            self.dom = etree.parse(str(x_out)).getroot()

            # read the errors into a variable
            with open(err_out, "r") as f:
                self.mp_errors = f.read()
