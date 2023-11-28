import arcpy
import csv
from lxml import etree
import copy
import tempfile
from pathlib import Path

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

toolbox_folder = Path(__file__).parent.parent
metadata_folder = toolbox_folder / "Resources" / "metadata"
templates_folder = metadata_folder / "metadata"

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
        dmu=None,
    ):
        self.table = table
        self.embedded_only = embedded_only
        self.arc_md = arc_md
        self.template = template
        self.definitions = definitions
        self.history = history
        self.sources = sources
        self.glossary = glossary
        self.dmu = dmu
        self.dom = None
        self.temp_sources = []
        self.temp_history = []

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
                # node.append(e)
                # node = node.find(nibble)

    def build_metadata(self):
        if self.embedded_only or self.arc_md:
            # this will set self.dom to the dom of the exported metadata
            self._export_embedded()
        else:
            # this will set self.dom to a mostly empty dom built from scratch
            # metadata = et.Element("metadata")
            # self.dom = et.ElementTree(metadata).getroot()
            self._md_from_scratch()

        if self.template:
            self._add_template_metadata()

        # self._add_csv_metadata()
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
            if self.dom.find(child[1] is None):
                self.dom.insert(child[0], child[1])

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

            if self.sources in (3, 8):
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

    def _remove_node(tree, xpath):
        remove = tree.xpath(xpath)[0]
        remove.getparent().remove(remove)

    def _md_from_scratch(self):
        # write out the top-level children and the eainfo/detailed node from the actual
        # list of fields in the table

        # make all the metadata first-level children
        metadata = etree.Element("metadata")
        for child in child_nodes:
            etree.SubElement(metadata, child)

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

    def _add_csv_metadata(self):
        if self.csv_file_path:
            with open(self.csv_file_path, "r") as csv_file:
                csv_reader = csv.DictReader(csv_file)
                for row in csv_reader:
                    entity_element = et.SubElement(self.metadata_tree, "entity")
                    field_element = et.SubElement(entity_element, "field")
                    field_element.text = row["field"]
                    definition_element = et.SubElement(entity_element, "definition")
                    definition_element.text = row["definition"]
                    definition_source_element = et.SubElement(
                        entity_element, "definitionsource"
                    )
                    definition_source_element.text = row["definitionsource"]

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
