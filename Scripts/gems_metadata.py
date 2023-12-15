import arcpy
import csv
from lxml import etree
import tempfile
from pathlib import Path
import sys

toolbox_folder = Path(__file__).parent.parent
scripts_folder = toolbox_folder / "Scripts"
metadata_folder = toolbox_folder / "Resources" / "metadata"
templates_folder = metadata_folder / "metadata"

sys.path.append(scripts_folder)
import GeMS_utilityFunctions as guf
import GeMS_Definition as gdef

# sources_choice = {
#     "save only DataSources": 1,
#     "save only embedded sources": 2,
#     "save only template sources": 3,
#     "save DataSources and embedded sources": 4,
#     "save DataSources and template sources": 5,
#     "save embedded and template sources": 6,
#     "save all sources": 7,
#     "save no sources": 8,
# }

# history_choices = {
#     "clear all history": 1,
#     "save only template history": 2,
#     "save only embedded history": 3,
#     "save all history": 4,
# }

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


class CollateFGDCMetadata:
    def __init__(
        self,
        table,
        embedded_only=False,
        arc_md=True,
        template=None,
        definitions=None,
        history=3,
        sources=1,
        glossary=None,
    ):
        self.table = table
        self.embedded_only = embedded_only
        self.arc_md = arc_md
        self.template = template
        if definitions:
            self.table_defs = self._table_defs_from_csv(definitions)
            self.field_defs = self._field_defs_from_csv(definitions)
        self.history = history
        self.sources = sources
        self.glossary = glossary
        self.dom = None
        self.is_db = False

        # from the table path, figure out the database it's in
        # and make a dictionary of the objects so we have paths
        # to Glossary, DataSources, and DMU
        desc = arcpy.da.Describe(self.table)
        w_path = Path(desc["path"])
        if w_path.suffix in (".gdb", ".gpkg"):
            db_path = str(w_path)
            self.is_db = True
        else:
            db_path = str(w_path.parent)
        self.db_dict = guf.gdb_object_dict(str(db_path))

        # make python dictionaries of the data dictionary tables
        sources_dict = self._term_dict("DataSources", ["DataSources_ID", "Source"])
        self.dds = {
            "sources_dict": sources_dict,
            "units_dict": self._term_dict(
                "DescriptionOfMapUnits",
                ["MapUnit", "Name", "Fullname", "DescriptionSourceID"],
            ),
            "geomat_dict": self._term_dict(
                "GeoMaterialDict", ["GeoMaterial", "Definition"]
            ),
            "gloss_dict": self._term_dict(
                "Glossary", ["Term", "Definition", "DefinitionSourceID"]
            ),
        }

    def build_metadata(self):
        if self.embedded_only or self.arc_md:
            # this will set self.dom to the dom of the exported metadata
            # lineage/srcinfo will be removed if sources in (1, 3, 5, 8)
            # lineage/procstep will be removed if history in (1, 2)
            self._export_embedded()
        else:
            # this will set self.dom to a mostly empty dom built from scratch
            self._md_from_scratch()

        if self.template:
            # lineage/srcinfo will be removed if sources in (1, 2, 4, 8)
            # lineage/procstep will be removed if history in (1, 3)
            self._add_template_metadata()

        if self.sources in (1, 4, 5, 7):
            # choices 1, 4, 5, 7 include DataSources
            self._add_datasources()

        if self.table_defs or self.field_defs:
            self._add_csv_metadata()

        self._ESRI_fields()

        # any other tables to exclude from domain descriptions?
        if (
            not self.db_dict[self.table]["concat_type"]
            == "Annotation Polygon FeatureClass"
        ):
            self._add_domains()

        return self.dom

    def _export_embedded(self):
        # export the embedded metadata to a temporary file
        # parse it and return the xml dom
        # synchronizing ensures that there will be eainfo/detailed nodes for every field
        temp_dir = tempfile.TemporaryDirectory()
        temp_xml = Path(temp_dir.name) / "temp.xml"
        src_md = arcpy.metadata.Metadata(self.table)
        src_md.synchronize("ALWAYS")
        src_md.exportMetadata(str(temp_xml), "FGDC_CSDGM")

        # make an lxml etree
        self.dom = etree.parse(str(temp_xml)).getroot()

        # check for removing embedded sources and history (process steps)
        # but don't proceed if there is no lineage node
        if self.dom.xpath("dataqual/lineage"):
            lineage = self.dom.xpath("dataqual/lineage")[0]
            if self.sources in (1, 3, 5, 8):
                for srcinfo in lineage.findall("srcinfo"):
                    lineage.remove(srcinfo)

            if self.history in (1, 2):
                for procstep in lineage.findall("procstep"):
                    lineage.remove(procstep)

        # add all top-level child nodes in case they are not exported
        for child in child_nodes:
            if self.dom.find(child[1]) is None:
                el = etree.Element(child[1])
                self.dom.insert(child[0], el)

        # if this is a table and has a detailed node
        # find the attr nodes and add the required children
        detailed = self.dom.find("eainfo", "detailed")
        if not detailed is None:
            attrs = detailed.findall("attr")
            for attr in attrs:
                for n in ("attrdef", "attrdefs", "attrdomv"):
                    self._extend_branch(attr, n)

    def _md_from_scratch(self):
        # write out the top-level children and the eainfo/detailed node from the actual
        # list of fields in the table

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
            for n in ("attrdef", "attrdefs", "attrdomv"):
                etree.SubElement(attr, n)

        self.dom = etree.ElementTree(metadata).getroot()

    def _add_template_metadata(self):
        template_tree = etree.parse(self.template)
        # remove nodes specified by source and history choices
        # first check for lineage node
        if self.dom.xpath("dataqual/lineage"):
            lineage = template_tree.xpath("dataqual/lineage")[0]
            # make a copy of the sources nodes
            # for choices 5, 6, and 7 they will be added back but with
            # other sources (from either embedded or DataSources)
            # a the entire list will be sorted
            if self.sources in (5, 6, 7):
                self.temp_sources = template_tree.xpath("dataqual/lineage/srcinfo")

            # make a copy of the process steps for history choice 4
            # for same reason as above
            if self.history == 4:
                self.temp_history = template_tree.xpath("dataqual/lineage/procstep")

            if self.sources in (1, 2, 4, 8):
                for srcinfo in lineage.findall("srcinfo"):
                    lineage.remove(srcinfo)

            if self.history in (1, 3):
                for procstep in lineage.findall("procstep"):
                    lineage.remove(procstep)

        # the number and order of entities in the template file may not be the
        # same as in the table we are writing metadata for.
        # copy and then delete that information from the template
        # the dictionary will be used below when writing out the detailed node
        detailed_dict = {}
        template_detailed = template_tree.find("eainfo/detailed")
        if not template_detailed is None:
            for attr in template_detailed.findall("attr"):
                label = attr.find("attrlabl").text
                detailed_dict[label] = attr
            template_detailed.getparent().remove(template_detailed)

        # add any remaining nodes from the template
        for el in template_tree.iter():
            el_path = template_tree.getelementpath(el)
            el_text = template_tree.xpath(el_path)[0].text

            if el_text and el_text != "None" and el_text.isprintable():
                self._extend_branch(self.dom, el_path)
                node = self.dom.xpath(el_path)[0]
                node.text = el_text

        # add the attribute definitions
        detailed = self.dom.find("eainfo/detailed")
        for attr in detailed.findall("attr"):
            label = attr.find("attrlabl").text

            # look for the field name in the attribute definition dictionary from the template
            if label in detailed_dict:
                # the dictionary value is an etree element
                copy_attr = detailed_dict[label]

                # "attrdef", "attrdefs" are in all template attr elements
                for n in ("attrdef", "attrdefs"):
                    # use extend_branch to create them if they don't exist in the source detailed node
                    self._extend_branch(attr, n)
                    # and set the text to the text in the template
                    attr.find(n).text = copy_attr.find(n).text

                # attrdomv is only in some template attr elements
                if copy_attr.find("attrdomv") is not None:
                    etree.SubElement(attr, "attrdomv")
                    attr.find("attrdomv").text = copy_attr.find("attrdomv").text

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
        field_list = None
        for field in self.db_dict[self.table].fields:
            fname = field.name
            # look for a field definition for this field in field_defs
            # priority goes to a field in this specific table

            if self.table in self.field_defs:
                field_list = [n for n in self.field_defs[self.table] if n[0] == fname]
            # backup looking for a definition that can be in __any_table__
            if not field_list:
                field_list = [
                    n for n in self.field_defs["__any_table__"] if n[0] == fname
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
            if attrlabl.lower() in esri_attribs:
                self._def_and_source(
                    attr,
                    "attrdef",
                    "attrdefs",
                    [esri_attribs[attrlabl.lower()], "ESRI"],
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
        """Fills in domain information"""
        # get the detailed node for this table
        detailed = self.dom.xpath(
            f"eainfo/detailed/enttyp/enttypl[text()='{self.table}']/parent::*/parent::*"
        )[0]

        # collect the fields for this table
        for f in self.db_dict[self.table].fields:
            fname = f.name

            # find the attribute node for this field
            attrs = detailed.xpath(f"attr/attrlabl[text()='{fname}]/parent::*")

            # although this is a for loop, it should only run through once
            for attr in attrs:
                # should be guaranteed by this point that every attr node has an attrdomv node
                attrdomv = attr.find("attrdomv")

                # look for a field definition for this field in field_defs
                # priority goes to a field in this specific table
                # finding a field properties list that is longer than 4 means
                # there is domain information
                field_list = None
                if self.table in self.field_defs:
                    field_list = [
                        n
                        for n in self.field_defs[self.table]
                        if n[0] == fname and len(n) > 4
                    ]
                # backup looking for a definition that can be in __any_table__
                if not field_list:
                    field_list = [
                        n
                        for n in self.field_defs["__any_table__"]
                        if n[0] == fname and len(n) > 4
                    ]

                # if field_list then we have domain information
                if field_list:
                    field = field_list[0]
                    d_type = field[4]

                    # there is not necessarily a 'domain_values' entry
                    if len(field) > 4:
                        d_vals = field[5]
                    else:
                        d_vals = None

                    tuples = None
                    if d_type == "rdom":
                        rdom = etree.SubElement(attrdomv, "rdom")
                        if d_vals:
                            nodes = ("rdommin", "rdomax", "attrunit", "attrmres")
                            vals = d_vals.split(",")
                            tuples = [(nodes[i], vals[i]) for i in range(len(vals))]
                            self._domain_nodes(rdom, d_type, tuples)

                    if d_type == "codsetd":
                        codesetd = etree.SubElement(attrdomv, "codesetd")
                        if d_vals:
                            nodes = ("codesetn", "codesets")
                            vals = d_vals.split(",")
                            tuples = [(nodes[i], vals[i]) for i in range(len(vals))]
                            self._domain_nodes(codesetd, d_type, tuples)

                    if d_type == "udom":
                        udom = etree.SubElement(attrdomv, "udom")
                        if d_vals:
                            udom.text = d_vals
                        else:
                            udom.text = "Unrepresentable domain"

                    if d_type == "edom":
                        # delete the single childless attrdomv so that we can add multiple with
                        # children in a loop
                        attr.remove(attrdomv)
                        if d_vals:
                            nodes = ("edomv", "edomvd", "edmovds")
                            edoms = d_vals.split("|")
                            for edom in edoms:
                                vals = edom.split(",")
                                tuples = [(nodes[i], vals[i]) for i in range(len(vals))]
                                attrdomv = etree.SubElement(attr, "attrdomv")
                                edom = etree.SubElement(attrdomv, "edom")
                                self._domain_nodes(edom, d_type, tuples)

                # if this field is in the list of gems-defined enumerated domain fields
                elif fname.lower in [n.lower() for n in gems_edom] or fname.lower in [
                    guf.camel_to_snake(n).lower() for n in gems_edom
                ]:
                    # delete the single childless attrdomv so that we can add multiple with
                    # children in a loop
                    attr.remove(attrdomv)

                    # collect a unique set of all the values in this field
                    with arcpy.da.SearchCursor(
                        self.db_dict[self.table]["catalogPath"], field
                    ) as cursor:
                        fld_vals = set([row[0] for row in cursor if not row[0] is None])

                    for val in fld_vals:
                        attrdomv = etree.SubElement(attr, "attrdomv")
                        edom = etree.SubElement(attrdomv, "edom")

                        if field.lower().endswith("sourceid"):
                            val_text = self._catch_m2m(self.dds["sources_dict"], val)
                            val_source = "This report"

                        # otherwise, find the appropriate dictionary and put the definition
                        # and definition source into def_text and def_source
                        else:
                            val_dict = self._which_dict(self.dds, self.table, fname)
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
                    udom = etree.SubElement(
                        attrdomv, "udom"
                    ).text = "Unrepresentable domain"

    def _def_and_source(parent, def_xpath, source_xpath, text_list):
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
        if def_node.text is None:
            def_node.text = text_list[0]
            # and update the definition source regardless
            parent.find(source_xpath).text = text_list[1]

    def _term_dict(self, table, fields):
        """sources_dict needs to be built first"""
        # always supply field to be the dictionary key as fields[0]
        # and the 'ID' field as fields[-1]
        if table in self.db_dict:
            table_path = self.db_dict[table]["catalogPath"]
            data_dict = {}
            cursor = arcpy.da.SearchCursor(table_path, fields)
            for row in cursor:
                if table == "DataSources":
                    if not row[1] is None:
                        data_dict[row[0]] = row[1]
                # elif table == "GeoMaterialDict":
                #     data_dict[row[0]] = [row[1]]
                #     data_dict[row[0]].append(gems)
                if table == "DescriptionOfMapUnits":
                    print("DescriptionOfMapUnits")
                    print(fields)
                    if row[0]:
                        if not row[2] is None:
                            data_dict[row[0]] = [row[2]]
                        else:
                            if not row[1] is None:
                                data_dict[row[0]] = [row[1]]
                        data_dict[row[0]].append(
                            self._catch_m2m(self.dds["sources_dict"], row[-1])
                        )
                    else:
                        data_dict[row[0]] = list(row[1:-1])
                        print(row[-1])
                        data_dict[row[0]].append(
                            self._catch_m2m(self.dds["sources_dict"], row[-1])
                        )
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

    def _catch_m2m(dictionary, field_value):
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
        with open(self.definitions, mode="r") as file:
            defs_csv = list(csv.reader(file))

        # check for header line
        if defs_csv[0] == ["table", "field", "definition", "definition_source"]:
            i = 1
        else:
            i = 0

        # csv definitions file can hold definitions for both tables and fields
        # parse the csv into two dictionaries
        # table name: [definition, definition source]
        table_defs = {
            row[0]: [row[2], row[3]] for row in defs_csv[i:] if row[0] and not row[1]
        }

        return table_defs

    def _field_defs_from_csv(self):
        # read the csv of definitions. Each line has:
        # table, field, definition, definition_source, domain_type, domain_values
        # if table is blank in CSV, that field is defined the same everywhere it is found
        with open(self.definitions, mode="r") as file:
            defs_csv = list(csv.reader(file))

        # fields are different
        # table name:[[field1 name, definition, definition source, domain_type, domain_values],
        #             [field2 name, definition, definition source, domain_type, domain_values], etc.]
        fields = [row for row in defs_csv[i:] if row[1]]
        field_defs = {}
        for field in fields:
            if not field[0] or field[0].isspace() or field[0] == "#":
                table = "__any_table__"
            else:
                table = field[0]

            if table in field_defs:
                field_defs[table].append([field[1:]])
            else:
                field_defs[table] = [[field[1:]]]

        return field_defs

    def _domain_nodes(parent, d_type, tuples):
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

    def _add_data_dictionary_metadata(self):
        # Add metadata from the data dictionary tables as needed
        pass

    def export_to_xml(self, output_file_path):
        tree = et.ElementTree(self.metadata_tree)
        tree.write(output_file_path)


# # Example Usage
# template_path = "template.xml"
# csv_path = "metadata.csv"
# data_dict = {"data_source": "source_table", "domain_values": "domain_table"}

# metadata_builder = FGDCMetadataBuilder(template_path, csv_path, data_dict)
# metadata_builder.build_metadata()
# metadata_builder.export_to_xml("output_metadata.xml")
