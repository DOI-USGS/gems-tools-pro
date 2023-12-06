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
        self.definitions = definitions
        self.history = history
        self.sources = sources
        self.glossary = glossary
        self.dom = None

        # from the table path, figure out the database it's in
        # and make a dictionary of the objects so we have paths
        # to Glossary, DataSources, and DMU
        desc = arcpy.da.Describe(self.table)
        w_path = Path(desc["path"])
        if w_path.suffix in (".gdb", ".gpkg"):
            db_path = str(w_path)
        else:
            db_path = str(w_path.parent)
        self.db_dict = guf.gdb_object_dict(str(db_path))

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

        if self.definitions:
            self._add_csv_metadata()
        # self._add_data_dictionary_metadata()
        #
        return self.dom

    def _export_embedded(self):
        # export the embedded metadata to a temporary file
        # parse it and return the xml dom
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

        for child in child_nodes:
            if self.dom.find(child[1]) is None:
                el = etree.Element(child[1])
                self.dom.insert(child[0], el)

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
        # read the csv of
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

        # fields are different
        # table name:[[field1 name, definition, definition source],
        #             [field2 name, definition, definition source], etc.]
        fields = [row for row in defs_csv[i:] if row[0] and row[1]]
        field_defs = {}
        for field in fields:
            if field[0] in field_defs:
                field_defs[field[0]].append([field[1], field[2], field[3]])
            else:
                field_defs[field[0]] = [[field[1], field[2], field[3]]]

        # find and update entity and attribute nodes
        for table in table_defs:
            enttyps = self.dom.xpath(
                f"eainfo/detailed/enttyp/enttypl[text()='{table}']/parent"
            )
            for enttyp in enttyps:
                # update the table definition and definition source
                self._def_and_source(enttyp, "enttypd", "enttypds", table)

                # get the detailed (parent node) of this enttyp, attributes are siblings
                detailed = self.dom.xpath(
                    f"eainfo/detailed/enttyp/enttypl[text()='{table}']/parent::*/parent::*"
                )[0]
                attrs = detailed.findall("attr")

                # and get the field definitions for this table from table_defs dictionary
                table_fields = field_defs[table]

                for field in table_fields:
                    attrs = self.dom.xpath(
                        f"eainfo/detailed/attr/attrlabl/[text()='{field[0]}']/parent"
                    )
                    for attr in attrs:
                        self._def_and_source(
                            attr, "attrdef", "attrdefs", [field[1], field[2]]
                        )

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

    def _remove_node(tree, xpath):
        remove = tree.xpath(xpath)[0]
        remove.getparent().remove(remove)

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
