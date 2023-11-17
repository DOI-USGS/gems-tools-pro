import arcpy
import csv
from lxml import etree
import tempfile
from pathlib import Path


class CollateFGDCMetadata:
    gems_full_ref = """GeMS (Geologic Map Schema)--a standard format for the digital publication of geologic maps", available at http://ngmdb.usgs.gov/Info/standards/GeMS/"""
    nodes = {
        "gems_nodes": {
            "suppl": {
                "xpath": "idinfo/descript/supplinf",
                "text": f"""db_name is a composite geodataset that conforms to {gems_full_ref}. Metadata records associated with each 
                element within the geodataset contain more detailed descriptions of their purposes, constituent entities, and attributes.). 
                An OPEN shapefile versions of the dataset is also available. It consists of shapefiles, DBF files, and delimited text files 
                and retains all information in the native geodatabase, but some programming will likely be necessary to assemble these 
                components into usable formats.""",
            },
            "attraccr": {
                "xpath": "dataqual/attracc/attraccr",
                "text": """Confidence that a feature exists and confidence that a feature is correctly identified are described in 
                per-feature attributes ExistenceConfidence and IdentityConfidence.""",
            },
            "horizpar": {
                "xpath": "dataqual/posacc/horizpa/horizpar",
                "text": """Estimated accuracy of horizontal location is given on a per-feature basis by attribute LocationConfidenceMeters. 
                Values are expected to be correct within a factor of 2. A LocationConfidenceMeters value of -9 or -9999 indicates that no value has been assigned.""",
            },
        },
        "source_nodes": {
            "lineage": {"xpath": "dataqual/lineage"},
            "title": {"xpath": "srccite/citeinfo/title"},
            "onlink": {"xpath": "srccite/citeinfo/onlink"},
        },
        "spatial_nodes": {
            "spdom": {"xpath": "idinfo/spdom"},
            "spdoinfo": {"xpath": "spdoinfo"},
            "spref": {"xpath": "spref"},
        },
        "entity_nodes": {"eainfo": {"xpath": "eainfo"}},
    }

    def __init__(
        self,
        table,
        embedded_only=False,
        arc_md=True,
        template=None,
        definitions=None,
        sources=None,
        glossary=None,
        dmu=None,
    ):
        self.table = table
        self.embedded_only = embedded_only
        self.arc_md = arc_md
        self.template = template
        self.definitions = definitions
        self.sources = sources
        self.glossary = glossary
        self.dmu = dmu
        self.dom = None

    def build_metadata(self):
        if self.embedded_only or self.arc_md:
            # this will set self.dom to the dom of the exported metadata
            self._export_embedded()
        else:
            # this will set self.dom to a mostly empty dom built from scratch
            # metadata = et.Element("metadata")
            # self.dom = et.ElementTree(metadata).getroot()
            self._md_from_scratch()

        # self._add_gems_nodes()
        return self.dom
        # self._add_template_metadata()
        # self._add_csv_metadata()
        # self._add_data_dictionary_metadata()

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
                e = etree.Element(nibble)
                node.append(e)
                node = node.find(nibble)

    def _export_embedded(self):
        # export the embedded metadata to a temporary file
        # parse it and return the xml dom
        temp_dir = tempfile.TemporaryDirectory()
        temp_xml = Path(temp_dir.name) / "temp.xml"
        src_md = arcpy.metadata.Metadata(self.table)
        src_md.exportMetadata(str(temp_xml), "FGDC_CSDGM")
        # make an lxml etree
        self.dom = etree.parse(str(temp_xml)).getroot()

    def _md_from_scratch(self):
        child_nodes = [
            "idinfo",
            "dataqual",
            "eainfo",
            "distinfo",
            "metainfo",
        ]
        metadata = etree.Element("metadata")
        for child in child_nodes:
            etree.SubElement(metadata, child[0])
        self.dom = etree.ElementTree(metadata).getroot()

    def _add_gems_nodes(self):
        g_nodes = CollateFGDCMetadata.nodes["gems_nodes"]
        for n in g_nodes:
            # proprint(f"  {g_nodes[n]['xpath']}")
            if self.dom.find(g_nodes[n]["xpath"]) is not None:
                e = self.dom.find(g_nodes[n]["xpath"])
                if len(e.text) > 1:
                    e.text = e.text + f"\n{g_nodes[n]['text']}"
                else:
                    e.text = f"{g_nodes[n]['text']}"
            else:
                self._extend_branch(self.dom, g_nodes[n]["xpath"])
                e = self.dom.find(g_nodes[n]["xpath"])
                e.text = g_nodes[n]["text"]

    def _add_template_metadata(self):
        if self.template:
            with open(self.template, "r") as template_file:
                template_content = template_file.read()
                template_element = et.ElementTree(
                    et.ElementTree().fromstring(template_content)
                ).getroot()
                self.metadata_tree.extend(template_element)

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
