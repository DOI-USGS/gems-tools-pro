"""Collate FGDC metadata class

Args:
    table: name of the table
    gdb_dict: dictionary built by guf.gdb_object_dict
    arc_md: True or False start with embedded metadata and add nodes to them. True by default
    template: Path to xml template file. None by default.
    definitions: Path to CSV file of table and field definitions, definition sources,
        and attribute domains. None by default
    history: How will history (process step) nodes be dealt with? Options 1-7 in table below.
        2 by default (only process steps from embedded metadata will be saved).
    sources: How will data sources (lineage) nodes be dealt with? Options 1-4 in table below.
        1 by default (only sources from DataSources table will be saved).
"""

import arcpy
from lxml import etree
import tempfile
from pathlib import Path
import sys
import copy

toolbox_folder = Path(__file__).parent.parent
scripts_folder = toolbox_folder / "Scripts"
metadata_folder = toolbox_folder / "Resources" / "metadata"
templates_folder = metadata_folder / "templates"

sys.path.append(scripts_folder)
import GeMS_utilityFunctions as guf
import GeMS_Definition as gdef
import spatial_utils as su
import metadata_utilities as mu
from importlib import reload

for n in guf, mu, gdef, su, mu:
    reload(n)

# sources_choices = {
#     1: "Save DataSources only",
#     2: "Save embedded sources only",
#     3: "Save template sources only",
#     4: "Save DataSources and embedded sources",
#     5: "Save DataSources and template sources",
#     6: "Save embedded and template sources",
#     7: "Save all sources",
#     8: "Save no sources",
# }

# history_choices = {
#     1: "Delete all history",
#     2: "Save embedded history only",
#     3: "Save template history only",
#     4: "Save both embedded and template history",
# }

gems_edom = gdef.enumeratedValueDomainFieldList

# the following xpaths are to single (non-repeatable) elements that have text
# and no children. The text will be used to replace the final xml text or be appended to it.

ap = guf.addMsgAndPrint

# print(inspect.currentframe().f_lineno)

# NOTE - xpath for finding the parent of nodes with mulitple tags
# attrdomv = attr.xpath("attrdomv/*[self::udom or self::rdom or self::codesetd]/parent::*")

ver_string = "gems_metadata.py 8/21/24"


class CollateTableMetadata:
    def __init__(
        self,
        table,
        gdb_dict,
        arc_md=True,
        template=None,
        temp_directive="replace",
        definitions=None,
        history=2,
        sources=2,
    ):
        self.table = table
        self.db_dict = gdb_dict
        self.arc_md = arc_md
        self.template = template
        self.template_tree = None
        self.temp_directive = temp_directive
        self.template_applied = False
        self.definitions = definitions
        self.history = history
        self.sources = sources
        # self.dtype = mu.find_type(self.db_dict, self.table)

        self.table_defs = {}
        self.field_defs = {}
        if definitions:
            self.table_defs = mu.table_defs_from_csv(self.definitions)
            self.field_defs = mu.field_defs_from_csv(self.definitions)

        parts = Path(gdb_dict[table]["catalogPath"]).parts
        gdb_folder = parts[0]
        for part in parts:
            if not part.endswith(".gdb") and not part.endswith(".gpkg"):
                gdb_folder = Path(gdb_folder) / part
            else:
                break

        # make python dictionaries of the data dictionary tables
        sources_dict = mu.term_dict(
            self.db_dict, "DataSources", ["DataSources_ID", "Source"]
        )
        self.dds = {
            "sources_dict": sources_dict,
            "units_dict": mu.term_dict(
                self.db_dict,
                "DescriptionOfMapUnits",
                ["MapUnit", "Name", "Fullname", "DescriptionSourceID"],
                sources_dict,
            ),
            "geomat_dict": mu.term_dict(
                self.db_dict,
                "GeoMaterialDict",
                ["GeoMaterial", "Definition"],
                sources_dict,
            ),
            "gloss_dict": mu.term_dict(
                self.db_dict,
                "Glossary",
                ["Term", "Definition", "DefinitionSourceID"],
                sources_dict,
            ),
        }

        self.mp_errors = None
        self.build_metadata()

    def build_metadata(self):
        """Entry function to begin collating metadata sources into one record"""
        if self.arc_md:
            # this will set self.dom to the dom of the exported metadata
            # lineage/srcinfo will be removed if sources in (1, 3, 5, 8)
            # lineage/procstep will be removed if history in (1, 2)
            obj_path = self.db_dict[self.table]["catalogPath"]
            self.dom = mu.export_embedded(obj_path, self.history, self.sources)

        # # to import template metadata where it overwrites everything
        # # call this class with a template and setting arc_md to False
        else:
            # this will set self.dom to a mostly empty dom built from scratch
            self.dom = mu.md_from_scratch(self.db_dict, self.table)

        # only attempt to collect spatial data organization information if
        # we are working with a feature class
        if self.db_dict[self.table]["dataType"] in ("FeatureClass", "RasterDataset"):
            if not self.dom.xpath("spdoinfo"):
                self._add_spdoinfo()

        # only attempt to build a spatial reference node if the object has a spatial reference
        # but feature datasets can't be interrogated by ogr, so filter those
        if (
            self.db_dict[self.table].get("spatialReference")
            and not self.db_dict[self.table]["dataType"] == "FeatureDataset"
        ):
            # add spref info, not exported from ArcGIS Pro into FGDC CSDGM
            # ESRI BUG-000124294 https://support.esri.com/en-us/bug/in-arcgis-pro-when-an-extensible-markup-language-xml-fi-bug-000124294
            if not self.dom.xpath("spref"):
                mu.add_spref(self.db_dict, self.table, self.dom)

        # at this point metadata will have everything verbatim from the embedded metadata plus
        # spdom, spdoinfo, and spref - things that should be calculated each time from inherent spatial properties
        # note that spdom is only calculated by ArcGIS when metadata are exported if the values are empty or there
        # is an error in the embedded metadata.
        # If they have been filled out and are valid, they will be exported, though they might not be relevant to or
        # correct for the data.
        # double-check that self.dom has the necessary elements for the rest of the functions
        if self.arc_md:
            self._check_children()

        # add the <geoform> presentation form
        self._geoform()

        # if there is a template, make an XML dom out of it
        # this needs to be done before dealing with history and sources
        # because for some choices, those elements, if they exist, are removed
        # from the template before the template is applied
        if self.template:
            self.template_tree = etree.parse(self.template)

        # decide how to deal with the history choice
        mu.history_wizard(self.dom, self.history, self.template_tree)

        # decide how to deal with the data sources choice
        mu.sources_wizard(
            self.dom, self.sources, self.db_dict, False, self.template_tree, self.table
        )

        # if a template is being used, apply add those elements now
        if self.template_tree:
            self._add_template_metadata()

        # special case for dealing with raster datasets,
        # add some made-up attributes for some raster properties
        if self.db_dict[self.table]["dataType"] == "RasterDataset":
            self._add_raster_attr()

        if self.table_defs or self.field_defs:
            if any(n in self.table_defs for n in (self.table, "ANY_TABLE")) or any(
                n in self.field_defs for n in (self.table, "ANY_TABLE")
            ):
                self._ea_defs_from_csv()

        if not self.table == "GeoMaterialDict" and "fields" in self.db_dict[self.table]:
            self._add_domains()

        if "fields" in self.db_dict[self.table]:
            self._ESRI_fields()

        self.dom, self.mp_errors = mu.mp_upgrade(self.dom)

    def _export_embedded(self):
        """Export the embedded metadata from a geodatabase object"""

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

    def _check_children(self):
        """Write out the top-level children in a metadata xml
        if they don't exist and the eainfo/detailed node from the actual list of fields in the table.
        """

        for child in mu.CHILD_NODES:
            mu.extend_branch(self.dom, child[1])

        # extend_branch to eainfo/detailed
        detailed = mu.extend_branch(self.dom, "eainfo/detailed")
        # extend_branch to eainfo/detailed/enttyp/enttypl and check there is text
        enttypl = mu.extend_branch(self.dom, "eainfo/detailed/enttyp/enttypl")
        if not enttypl.text:
            enttypl.text = Path(self.table).name

        # make one attr/attrlabl per field
        if "fields" in self.db_dict[self.table]:
            for field in self.db_dict[self.table]["fields"]:
                if not len(
                    self.dom.xpath(
                        f"eainfo/detailed/attr/attrlabl[text()='{field.name}']"
                    )
                ):
                    attr = etree.SubElement(detailed, "attr")
                    attrlabl = etree.SubElement(attr, "attrlabl")
                    attrlabl.text = field.name

    def _geoform(self):
        # prepare a geospatial data presentation form string
        data_type = mu.find_type(self.db_dict, self.table)

        geoform_text = None
        # presentation form string
        if "raster" in data_type:
            geoform_text = "raster digital data"
        if "table" in data_type:
            geoform_text = "tabular digital data"
        if "feature class" in data_type:
            geoform_text = "vector digital data"
        if not data_type:
            geoform_text = "vector digital data"

        # get the node and set the text
        if geoform_text:
            geoform = mu.extend_branch(self.dom, "idinfo/citation/citeinfo/geoform")
            geoform.text = geoform_text

    def _add_spdoinfo(self):
        """Create a spatial data information element for the object. If raster, use
        method here, if vector, use the MW spatial utilities methods"""
        # at this time, no RasterDatsets are sent to this function because the
        # spdoinfo element cannot accommodate cataloging both vector features and rasters but
        # I will leave the first part of the if statement uncommented
        # raster properties will get logged as entity attributes
        d = self.db_dict
        if d[self.table]["datasetType"] == "RasterDataset":
            spdoinfo = etree.Element("spdoinfo")
            rastinfo = etree.SubElement(spdoinfo, "rastinfo")
            rasttype = etree.SubElement(rastinfo, "rasttype")
            rasttype.text = "Grid Cell"
            rowcount = etree.SubElement(rastinfo, "rowcount")
            rowcount.text = str(d[self.table]["height"])
            colcount = etree.SubElement(rastinfo, "colcount")
            colcount.text = str(d[self.table]["width"])
        else:
            wksp = d[self.table]["workspace"]
            db_path = wksp.connectionProperties.database
            try:
                spdoinfo = su.get_spdoinfo(str(db_path), self.table)
            except Exception as e:
                arcpy.AddWarning(
                    f"""Could not collect spatial data organization information"""
                )
                arcpy.AddWarning(e)
                spdoinfo = None
        if spdoinfo:
            self.dom.insert(2, spdoinfo)

    def _add_template_metadata(self):
        """Add information from the template file"""
        # First, Entity - Attribute information
        # the number and order of entities in the template file may not be the
        # same as in the table for which we are writing metadata.
        # copy that information from the template into a dictionary.
        # the dictionary will be used below when writing out the detailed node
        # detailed_dict[field name] = attr node with all children

        # make a dictionary from the template file where
        # attribute label (field name) = attr xml node
        temp_detailed_dict = {}

        # first look for a single detailed node and assume the template
        # was assigned correctly
        temp_dets_list = self.template_tree.xpath("eainfo/detailed")
        temp_detailed = None
        if len(temp_dets_list) == 1:
            temp_detailed = temp_dets_list[0]
        else:
            # if there are multiple detailed nodes, as in a single template file describinh
            # many tables, look for the detailed/enttyp/enttypl label that matches the current table name
            xpath_search = self.template_tree.xpath(
                f"eainfo/detailed/enttyp/enttypl[text()='{self.table}']/parent::*/parent::*"
            )
            if xpath_search:
                temp_detailed = xpath_search[0]

        # if temp_detailed is still empty, do one more search trying to match enttypl with the table's
        # gems_equivalant
        if not temp_detailed:
            gems_eq = self.db_dict[self.table]["gems_equivalent"]
            xpath_search = self.template_tree.xpath(
                f"eainfo/detailed/enttyp/enttypl[text()='{gems_eq}']/parent::*/parent::*"
            )
            if xpath_search:
                temp_detailed = xpath_search[0]

        # finally, make the dictionary and look for matches in the self.dom attributes
        if temp_detailed:
            # apply entity definition and definition source. Regardless of template directive, this will replace
            # anything in the embedded
            # definition node
            temp_def = mu.extend_branch(temp_detailed, "enttyp/enttypd")
            if temp_def.text:
                enttypd = mu.extend_branch(self.dom, "eainfo/detailed/enttyp/enttypd")
                enttypd.text = temp_def.text

            # definition source node
            temp_def_src = mu.extend_branch(temp_detailed, "enttyp/enttypds")
            if temp_def_src.text:
                enttypds = mu.extend_branch(self.dom, "eainfo/detailed/enttyp/enttypds")
                enttypds.text = temp_def_src.text

            # move on to attributes
            for attr in temp_detailed.findall("attr"):
                label = attr.find("attrlabl").text
                temp_detailed_dict[label] = attr

            # get the detailed node of the self.dom
            detailed = mu.extend_branch(self.dom, "eainfo/detailed")
            for attr in detailed.findall("attr"):
                label = attr.find("attrlabl").text

                # look for the field name in the attribute definition dictionary from the template
                # and make a copy
                if label in temp_detailed_dict:
                    temp_attr = temp_detailed_dict[label]

                    # "attrdef", "attrdefs" are in all template attr elements
                    for n in ("attrdef", "attrdefs"):
                        # use extend_branch to create them if they don't exist in the self.dom detailed node
                        el = mu.extend_branch(attr, n)

                        # and set the text to the text in the template
                        el.text = temp_attr.find(n).text

                    # if there are any attrdomv elements in the template, delete the one in
                    if (
                        self.temp_directive == "replace"
                        or self.table == "GeoMaterialDict"
                    ):
                        els = temp_attr.findall("attrdomv")
                        if len(els):
                            # try/except block rather than testing first for existence of attrdomv
                            # in self.dom
                            try:
                                attr.remove(attr.find("attrdomv"))
                            except:
                                pass

        # Second, append or replace text at the end of text_xpaths
        for text_xpath in mu.TEXT_XPATHS:
            # determine if there is actually text at the end of text_xpath
            el = self.template_tree.xpath(text_xpath)
            if el:
                temp_text = None
                # template files, by use of SINGLE or REPORT token, can be used for individual object metadata
                # or report-level metadata (where the entire db is described in one file)
                # in the template, there will be one node that starts with [[DATABASE]] and one that starts with [[SINGLE]]
                # this class only deals with metadata for single objects, so filter the REPORT elements
                if len(el) > 1:
                    for node in el:
                        if not node.text.startswith("[[DATABASE]]"):
                            temp_text = node.text
                else:
                    temp_text = el[0].text

                # check for an empty string at the template node being evaluated
                if temp_text:
                    if temp_text.strip():
                        # prepare the string from the template to put into the self.dom node
                        temp_text = temp_text.replace("[[SINGLE]]", "").strip()
                        dom_el = mu.extend_branch(self.dom, text_xpath)
                        temp_text = mu.tokens(
                            temp_text, self.db_dict, ver_string, self.table
                        )

                        # consider the temp_directive
                        if self.temp_directive == "append":
                            # look for existing text
                            if dom_el.text:
                                if dom_el.text.strip():
                                    # and try to make the addition grammatically correct; add a period if necessary.
                                    if dom_el.text.endswith("."):
                                        dom_el.text = f"{dom_el.text} {temp_text}"
                                    else:
                                        dom_el.text = f"{dom_el.text}. {temp_text}"
                                else:
                                    dom_el.text = temp_text
                            # otherwise temp_directive is "replace"
                            else:
                                dom_el.text = temp_text

        # Third, add nodes from single_nodes
        # check for the node in the template
        # always replace regardless of temp_directive
        for node_xpath in mu.SINGLE_NODES:
            temp_el = self.template_tree.xpath(node_xpath)
            if temp_el:
                if len(temp_el[0]):
                    # return the node in self.dom, creating it from scratch if necessary with _extend_branch
                    dom_el = mu.extend_branch(self.dom, node_xpath)
                    # check for children
                    if dom_el:
                        if list(dom_el[0]):
                            for n in dom_el[0]:
                                dom_el[0].remove(n)
                        # append the children from the template
                        for n in temp_el[0]:
                            dom_el[0].append(copy.deepcopy(n))

        # Fourth, add nodes that can be repeated x-many times.
        # Look for a list of elements at each of the xpaths in xmany_nodes
        for node_xpath in mu.XMANY_NODES:
            add_nodes = self.template_tree.xpath(node_xpath)
            if add_nodes:
                parent = add_nodes[0].getparent()
                dom_parent = mu.extend_branch(
                    self.dom, self.template_tree.getpath(parent)
                )
                if self.temp_directive == "replace":
                    for child in dom_parent:
                        dom_parent.remove(child)
                for add_node in add_nodes:
                    dom_parent.append(add_node)

        # adding keywords is a special case
        # 'replace' only replaces keywords from matching thesaurus
        # 'append' collects list of ALL keywords, sorts alphabetically, and appends
        #
        # xpaths for reference:
        # idinfo/keywords/theme
        #     idinfo/keywords/theme/themekt
        #     idinfo/keywords/theme/themekey
        #
        # make a dictionary of {(theme/place/stratum/temporal, keyword thesaurus): [keyword nodes]]} from the template
        temp_kw_dict = mu.keyword_dict(self.template_tree)
        if temp_kw_dict:
            found_kw = []

            # first look for keyword sections in the self.dom to add template keywords to
            dom_kw_dict = mu.keyword_dict(self.dom)
            if dom_kw_dict:
                for k in dom_kw_dict:
                    # remember k is a tuple of (keyword type, thesaurus name)
                    if k in temp_kw_dict:
                        # get the parent of the relevant <*kt> element from self.dom and the template
                        dom_kt = self.dom.xpath(
                            f"idinfo/keywords/{k[0]}/*[name() = '{k[0]}kt' and text() = '{k[1]}']"
                        )[0]
                        dom_kwtype = dom_kt.getparent()

                        temp_kt = self.template_tree.xpath(
                            f"idinfo/keywords/{k[0]}/*[name() = '{k[0]}kt' and text() = '{k[1]}']"
                        )[0]
                        temp_kwtype = temp_kt.getparent()

                        # replace or append the keywords
                        if self.temp_directive == "replace":
                            keywords = dom_kwtype.getparent()
                            # remove the existing keyword type node
                            keywords.remove(dom_kwtype)

                            # replace with copy of the one from the template
                            copy_type = copy.deepcopy(temp_kwtype)
                            keywords.append(copy_type)
                        else:
                            # make a list of all keyword nodes from self.dom and template using the dictionaries
                            node_list = []
                            for n in dom_kw_dict[k]:
                                node_list.append(n)
                            for n in temp_kw_dict[k]:
                                node_list.append(n)

                            # remove all keywords from self.dom
                            for n in dom_kt.itersiblings():
                                if n.tag.endswith("key"):
                                    dom_kwtype.remove(n)

                            # sort keywords alphabetically and append to the keyword type node
                            for sort_key in sorted(node_list, key=lambda x: x.text):
                                dom_kwtype.append(sort_key)

                        # flag that this k has been found
                        found_kw.append(k)

            # add any keyword sections in the template that do not exist in the self.dom
            # if the temp_directive is append, ignore otherwise
            if self.temp_directive == "append":
                # filter the keywords to add based on the flag list found_kw
                add_kws = {k: v for k, v in temp_kw_dict.items() if not k in found_kw}
                # get or create the keywords node
                keywords = mu.extend_branch(self.dom, "idinfo/keywords")
                # iterate
                for k, v in add_kws.items():
                    kw_type = etree.SubElement(keywords, k[0])

                    # figure out the name of the *kt and key nodes
                    match k[0]:
                        case "stratum":
                            kt_tag = "stratkt"
                        case "temporal":
                            kt_tag = "tempkt"
                        case _:
                            kt_tag = f"{k[0]}kt"

                    # make the <theme/place/strat/tempkt> node and the keywords
                    kt = etree.SubElement(kw_type, kt_tag)
                    kt.text = k[1]
                    for kw in v:
                        kw_type.append(kw)

    def _ea_defs_from_csv(self):
        """Add entity and attribute definition and definition sources for custom fields
        or override fields already defined by template. CSV definitions take the cake"""

        # get the detailed node for this table
        detailed = self.dom.xpath(
            f"eainfo/detailed/enttyp/enttypl[text()='{self.table}']/parent::*/parent::*"
        )[0]

        # if we have a definition in table_defs from the CSV, add it
        if self.table in self.table_defs:
            enttyp = mu.extend_branch(detailed, "enttyp")
            self._def_and_source(
                enttyp, "enttypd", "enttypds", self.table_defs[self.table]
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

            # backup looking for a definition that can be in ANY TABLE
            if not field_list:
                if "ANY TABLE" in self.field_defs:
                    field_list = [
                        n for n in self.field_defs["ANY TABLE"] if n and n[0] == fname
                    ]

            if field_list:
                field = field_list[0]
                attrs = detailed.xpath(f"attr/attrlabl[text()='{fname}']/parent::*")
                for attr in attrs:
                    self._def_and_source(
                        attr, "attrdef", "attrdefs", [field[1], field[2]]
                    )

    def _ESRI_fields(self):
        """Add definitions for ESRI-controlled fields"""

        # get the detailed node for this table
        detailed = self.dom.xpath(
            f"eainfo/detailed/enttyp/enttypl[text()='{self.table}']/parent::*/parent::*"
        )[0]

        # find all child attr nodes
        attrs = detailed.findall("attr")
        for attr in attrs:
            attrlabl = attr.find("attrlabl")
            # if this field is a regular ESRI controlled field
            if attrlabl.text.lower() in mu.ESRI_ATTRIBS:
                self._def_and_source(
                    attr,
                    "attrdef",
                    "attrdefs",
                    [mu.ESRI_ATTRIBS[attrlabl.text.lower()], "ESRI"],
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
        """Fills in domain (field values) information from the csv definitions file"""

        # get the detailed node for this table
        detailed = self.dom.xpath("eainfo/detailed")[0]

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
                # finding a field properties list that is longer than 4 means there is domain information
                if self.field_defs.get(self.table):
                    field_w_dom = [
                        n
                        for n in self.field_defs[self.table]
                        if n[0] == fname and len(n) > 3
                    ]

                # backup looking for a definition that can be in ANY TABLE
                field_w_dom = None
                if not field_w_dom:
                    if self.field_defs:
                        field_w_dom = [
                            n
                            for n in self.field_defs["ANY_TABLE"]
                            if n[0] == fname and len(n) > 3
                        ]

                # if field_w_dom, then we have domain information from the csv file
                if field_w_dom:
                    # but first determine if there is an attrdomv node that will be overwritten
                    if attr.find("attrdomv") is not None:
                        arcpy.AddWarning(
                            f"Attribute domain information for field {fname} will be overwritten with information from definitions CSV file"
                        )

                        print(
                            f"Attribute domain information for field {fname} will be overwritten with information from definitions CSV file"
                        )

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
                        # delete the single childless attrdomv so that we can add multiple
                        # children in a loop
                        if attr.find("attrdomv") is not None:
                            attr.remove(attr.find("attrdomv"))

                        if d_vals:
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

                    # if statement below means pipe-delimited values in GeMS enumerated domain
                    # attributes can be concatenated
                    if any("|" in val for val in fld_vals):
                        fld_vals = set(
                            [n.strip() for val in fld_vals for n in val.split("|")]
                        )

                    # iterate through the values
                    for val in list(sorted(fld_vals)):
                        attrdomv = etree.SubElement(attr, "attrdomv")
                        edom = etree.SubElement(attrdomv, "edom")

                        if fname.lower().endswith("sourceid"):
                            val_text = mu.catch_m2m(self.dds["sources_dict"], val)
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

    def _add_raster_attr(self):
        # make a dictionary of raster properties to turn into attributes
        props = {
            "bandCount": ["The number of bands in the raster dataset."],
            "height": ["The number of rows."],
            "isInteger": ["Indicates whether the raster band has integer type."],
            "format": ["The raster format"],
            "meanCellHeight": ["The cell size in y direction."],
            "meanCellWidth": ["The cell size in the x direction"],
            "noDataValue": ["The NoData value of the raster band."],
            "pixelType": ["The pixel type"],
            "spatialReference": [
                "The ESRI-standardized name of the spatial reference used by the raster"
            ],
            "width": ["The number of columns."],
        }
        desc_props = self.db_dict[self.table]
        for k, v in props.items():
            if k == "spatialReference":
                v.append(desc_props[k].name)
            else:
                v.append(str(desc_props[k]))

        detailed = mu.extend_branch(self.dom, "eainfo/detailed")

        # add an entity element if one is missing - most likely for rasters added ad-hoc to a gdb
        if detailed.find("enttyp") is None:
            enttyp = etree.SubElement(detailed, "enttyp")
            enttypl = etree.SubElement(enttyp, "enttypl")
            enttypl.text = self.table

            if self.table_defs:
                if self.table in self.table_defs:
                    ras_def = self.table_defs[self.table][2]
                    ras_def_src = self.table_defs[self.table][2]
            else:
                ras_def = "PROVIDE A DEFINITION FOR THIS RASTER"
                ras_def_src = "PROVIDE A SOURCE FOR THIS DEFINITION"

            enttypd = etree.SubElement(enttyp, "enttypd")
            enttypd.text = ras_def
            enttypds = etree.SubElement(enttypd, "enttypds")
            enttypds.text = ras_def_src

        for ras_attr, def_val in props.items():
            attr = etree.SubElement(detailed, "attr")
            attrlabl = etree.SubElement(attr, "attrlabl")
            attrlabl.text = ras_attr
            self._def_and_source(attr, "attrdef", "attrdefs", [def_val[0], "ESRI"])
            # attrdef = etree.SubElement(attr, "attrdef")
            # attrdef.text = def_val[0]
            # attrdefs = etree.SubElement(attr, "attrdefs")
            # attrdefs.text = "ESRI"
            attrdomv = etree.SubElement(attr, "attrdomv")
            edom = etree.SubElement(attrdomv, "edom")
            edomv = etree.SubElement(edom, "edomv")
            edomv.text = def_val[1]
            edomvd = etree.SubElement(edom, "edomvd")
            edomvd.text = f"Value from the ArcGIS Describe object of the raster"
            edomvds = etree.SubElement(edom, "edomvds")
            edomvds.text = "ESRI"

    def _def_and_source(self, parent, def_xpath, source_xpath, text_list):
        """Helper function for building definition and definition source elements"""
        # whether missing or blank add node and/or definition and definition source text
        # to an entity or attribute node
        # if def_xpath == "attrdef":
        #     arcpy.AddMessage(text_list)
        if parent.find(def_xpath) is None:
            # it doesn't make sense if definition is blank when there exists a
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

    def _which_dict(self, tbl, fld):
        """Determine the correct term dictionary to use based on field name"""

        if fld.lower() in ("mapunit", "map_unit"):
            return self.dds["units_dict"]
        elif fld.lower() in ("geomaterialconfidence", "geo_material_confidence"):
            if tbl.lower() in ("descriptionofmapunits", "description_of_map_units"):
                return gdef.GeoMatConfDict
        elif fld.lower() in ("geomaterial", "geo_material"):
            return self.dds["geomat_dict"]
        elif fld.lower().find("sourceid") > -1:
            return self.dds["sources_dict"]
        else:
            return self.dds["gloss_dict"]

    def _domain_nodes(self, parent, d_type, tuples):
        """Helper function to build domv nodes"""
        child = etree.SubElement(parent, d_type)
        for t in tuples:
            etree.SubElement(child, t[0]).text = t[1]


class CollateDatabaseMetadata:
    def __init__(
        self,
        db_path,
        db_dict,
        embedded=False,
        arc_md=True,
        md_dict={},
        temp_path=None,
        temp_directive="replace",
        history=2,
        sources=1,
    ):
        self.db_path = db_path
        self.db_name = Path(self.db_path).stem
        self.db_dict = db_dict
        self.embedded = embedded
        self.arc_md = arc_md
        self.md_dict = md_dict
        self.temp_path = temp_path
        self.template_tree = None
        self.temp_directive = temp_directive
        self.template_applied = False
        self.history = history
        self.sources = sources
        self.mp_errors = None
        self.build_metadata()

    def build_metadata(self):
        """Entry function for collecting sources for a single database-level
        metadata record"""

        if self.embedded or self.arc_md:
            # this will set self.dom to the dom of the exported metadata
            # lineage/srcinfo will be removed if sources in (1, 3, 5, 8)
            # lineage/procstep will be removed if history in (1, 2)
            self.dom = mu.export_embedded(self.db_path, self.history, self.sources)

        # to import template metadata where it overwrites everything
        # call this class with a template and setting arc_md to False
        else:
            # this will set self.dom to a mostly empty dom built from scratch
            self.dom = mu.md_from_scratch(self.db_dict)

        # add a geoform string
        self._geoform()

        # add spdom/bounding and spdoinfo if they don't exist
        self._spatial_nodes()

        # Always add a spatial reference element
        for k, v in self.db_dict.items():
            # first, look for MapUnitPolys or ContactsAndFauts equivalent feature classes that are not in
            # cross section feature datasets, if those can be identified
            gems_eq = v["gems_equivalent"]
            if (
                gems_eq in ["MapUnitPolys", "ContactsAndFaults"]
                and "spatialReference" in v
                and not any(
                    k.lower().startswith(s) for s in ("cs", "crosssection", "xs")
                )
            ):
                if not v["spatialReference"].name.lower() == "unknown":
                    if mu.add_spref(self.db_dict, k, self.dom):
                        break
            # second, any GeMS-equivalant fc in startDict if the same other conditions apply
            elif (
                gems_eq in gdef.startDict
                and "spatialReference" in v
                and not any(
                    k.lower().startswith(s) for s in ("cs", "crosssection", "xs")
                )
            ):
                if not v["spatialReference"].name.lower() == "unknown":
                    if mu.add_spref(self.db_dict, k, self.dom):
                        break

        # exit early if embedded only = True
        if self.embedded:
            # validate with upgrade flag to re-order out-of-order elements and write a valid error log
            self.dom, self.mp_errors = mu.mp_upgrade(self.dom)
            return (self.dom, self.mp_errors)

        # if continuing, double-check that self.dom has the necessary elements for
        # the rest of the functions
        if self.arc_md:
            for child in mu.CHILD_NODES:
                mu.extend_branch(self.dom, child[1])

        if self.temp_path:
            self.template_tree = etree.parse(self.temp_path)

        # history
        mu.history_wizard(self.dom, self.history, self.template_tree)

        # data sources/source info nodes
        mu.sources_wizard(
            self.dom, self.sources, self.db_dict, True, self.template_tree
        )

        # add detailed entity_attribute nodes from all of the previously built metadata records
        # for each table
        self._add_detailed_nodes()

        # add template language from the generic
        if self.template_tree:
            self._add_template_metadata()

        # validate with upgrade flag to re-order out-of-order elements and write a valid error log
        self.dom, self.mp_errors = mu.mp_upgrade(self.dom)

    def _geoform(self):
        """build up a geoform string based on the metadata already in md_dict"""
        geoforms = []

        # iterate through the metadata records, we don't care what the names are
        for v in self.md_dict.values():
            gf_node = v.xpath("idinfo/citation/citeinfo/geoform")
            if not len(gf_node) == 0:
                geoforms.append(gf_node[0].text)

        geoforms = set(geoforms)
        if geoforms:
            geoform_text = ", ".join(geoforms)

        # get a geoform node in self.dom
        geoform = mu.extend_branch(self.dom, "idinfo/citation/citeinfo/geoform")
        geoform.text = geoform_text

    def _spatial_nodes(self):
        """Add max bounding box (info/spdom) and spatial data organization (spdoinfo)"""
        # max bounding box
        if self.dom.find("idinfo/spdom/bounding") is None:
            spdom = etree.Element("spdom")
            bounding = mu.max_bounding(self.db_path)
            spdom.append(bounding)
            self.dom.find("idinfo").append(spdom)

        # add spdoinfo nodes
        # verify a spdoinfo node and remove any children, which is just easier than
        # snooping to find out what might be there. Shouldn't be anything but one
        # <direct> element anyway.
        spdoinfo = mu.extend_branch(self.dom, "spdoinfo")
        for el in spdoinfo.getchildren():
            spdoinfo.remove(el)

        # add a <direct> node and name it
        direct = etree.SubElement(spdoinfo, "direct")
        direct.text = "Vector"

        # add a <ptvctinf> node
        ptvctinf = etree.SubElement(spdoinfo, "ptvctinf")

        # run through the metadata records that have already been created for the db and add any
        # ptvctinf/sdtsterms nodes
        # filter out md_dict records that are not for Feature Classes
        # it doesn't appear to be possible to put information for both vector and raster data in the
        # spoinfo element, so for now, we'll just catalog the vector data
        fc_entries = {
            k: v
            for k, v in self.md_dict.items()
            if self.db_dict[k]["dataType"] == "FeatureClass"
        }

        # iterate through the records
        for v in fc_entries.values():
            # find the sdtsterm node and add it to spdoinfo/ptvctinf
            if v.find("spdoinfo/ptvctinf") is not None:
                ptvctinf = mu.extend_branch(spdoinfo, "ptvctinf")
                sdtsterm = v.find("spdoinfo/ptvctinf/sdtsterm")
                ptvctinf.append(sdtsterm)

    def _add_detailed_nodes(self):
        """Sync eainfo/detailed nodes between templates and the database"""
        # build a dictionaries of {table: eainfo/detailed nodes} from the dictionaries of
        # md_dict (built by CollateTableMetadata). This assumes the detailed nodes there
        # already have the desired entity-attribute definitions.
        eainfo = self.dom.xpath("eainfo")

        # unlikely though possible that this record has eainfo/detailed nodes, but
        # remove them if that's the case.
        for detailed in eainfo[0].xpath("detailed"):
            eainfo.remove(detailed)

        # build the {table name: detailed node} dictionary
        detailed_nodes = {}
        for k, v in self.md_dict.items():
            found_detail = self._get_detailed(v, k)
            if found_detail:
                detailed_nodes[k] = found_detail

        arcpy.AddMessage(
            f"  Adding detailed entity-attribute nodes from individual metadata files:"
        )

        # sort the names of the tables in self.db_dict into a list to organize the detailed nodes
        add_list = sorted(list(self.db_dict.keys()))

        # filter out db_dict entries that do not have fields
        add_list = [n for n in add_list if "fields"]

        # get the eainfo node
        eainfo = self.dom.xpath("eainfo")[0]

        # iterate through the already-built detailed nodes
        for add_detailed in add_list:
            # print(add_detailed)
            if add_detailed in detailed_nodes:
                arcpy.AddMessage(f"    {add_detailed}")
                eainfo.append(detailed_nodes[add_detailed])

    def _get_detailed(self, xml_dom, entity_label):
        """Find the eainfo/detailed node in the XML file"""
        detailed = xml_dom.xpath(
            f"eainfo/detailed/enttyp/enttypl[text()='{entity_label}']/parent::*/parent::*"
        )

        if not len(detailed) == 0:
            return detailed[0]

    def _add_template_metadata(self):
        # Append or replace text at the end of text_xpaths
        for text_xpath in mu.TEXT_XPATHS:
            # determine if there is actually text at the end of text_xpath
            el = self.template_tree.xpath(text_xpath)
            if el:
                temp_text = None
                # template files, by use of SINGLE or REPORT token, can be used for individual object metadata
                # or report-level metadata (where the entire db is described in one file)
                # in the template, there will be one node that starts with [[DATABASE]] and one that starts with [[SINGLE]]
                # this class only deals with metadata for databases, so filter the SINGLE elements
                if len(el) > 1:
                    for node in el:
                        if not node.text.startswith("[[SINGLE]]"):
                            temp_text = node.text
                else:
                    temp_text = el[0].text

                # check for an empty string at the template node being evaluated
                if temp_text:
                    if temp_text.strip():
                        # prepare the string from the template to put into the self.dom node
                        temp_text = temp_text.replace("[[DATABASE]]", "").strip()
                        dom_el = mu.extend_branch(self.dom, text_xpath)
                        temp_text = mu.tokens(temp_text, self.db_dict, ver_string)

                        # consider the temp_directive
                        if self.temp_directive == "append":
                            # look for existing text
                            if dom_el.text:
                                if dom_el.text.strip():
                                    # and try to make the addition grammatically correct; add a period if necessary.
                                    if dom_el.text.endswith("."):
                                        dom_el.text = f"{dom_el.text} {temp_text}"
                                    else:
                                        dom_el.text = f"{dom_el.text}. {temp_text}"
                                else:
                                    dom_el.text = temp_text
                            # otherwise temp_directive is "replace"
                            else:
                                dom_el.text = temp_text

        # Third, add nodes from single_nodes
        # check for the node in the template
        # always replace regardless of temp_directive
        for node_xpath in mu.SINGLE_NODES:
            temp_el = self.template_tree.xpath(node_xpath)
            if temp_el:
                if len(temp_el[0]):
                    # return the node in self.dom, creating it from scratch if necessary with _extend_branch
                    dom_el = mu.extend_branch(self.dom, node_xpath)
                    # check for children
                    if dom_el:
                        if list(dom_el[0]):
                            for n in dom_el[0]:
                                dom_el[0].remove(n)
                        # append the children from the template
                        for n in temp_el[0]:
                            dom_el[0].append(copy.deepcopy(n))

        # Fourth, add nodes that can be repeated x-many times.
        # Look for a list of elements at each of the xpaths in xmany_nodes
        for node_xpath in mu.XMANY_NODES:
            add_nodes = self.template_tree.xpath(node_xpath)
            if add_nodes:
                parent = add_nodes[0].getparent()
                dom_parent = mu.extend_branch(
                    self.dom, self.template_tree.getpath(parent)
                )
                if self.temp_directive == "replace":
                    for child in dom_parent:
                        dom_parent.remove(child)
                for add_node in add_nodes:
                    dom_parent.append(add_node)

        # adding keywords is a special case
        # 'replace' only replaces keywords from matching thesaurus
        # 'append' collects list of ALL keywords, sorts alphabetically, and appends
        #
        # xpaths for reference:
        # idinfo/keywords/theme
        #     idinfo/keywords/theme/themekt
        #     idinfo/keywords/theme/themekey
        #
        # make a dictionary of {(theme/place/stratum/temporal, keyword thesaurus): [keyword nodes]]} from the template
        temp_kw_dict = mu.keyword_dict(self.template_tree)
        if temp_kw_dict:
            found_kw = []

            # first look for keyword sections in the self.dom to add template keywords to
            dom_kw_dict = mu.keyword_dict(self.dom)
            if dom_kw_dict:
                for k in dom_kw_dict:
                    # remember k is a tuple of (keyword type, thesaurus name)
                    if k in temp_kw_dict:
                        # get the parent of the relevant <*kt> element from self.dom and the template
                        dom_kt = self.dom.xpath(
                            f"idinfo/keywords/{k[0]}/*[name() = '{k[0]}kt' and text() = '{k[1]}']"
                        )[0]
                        dom_kwtype = dom_kt.getparent()

                        temp_kt = self.template_tree.xpath(
                            f"idinfo/keywords/{k[0]}/*[name() = '{k[0]}kt' and text() = '{k[1]}']"
                        )[0]
                        temp_kwtype = temp_kt.getparent()

                        # replace or append the keywords
                        if self.temp_directive == "replace":
                            keywords = dom_kwtype.getparent()
                            # remove the existing keyword type node
                            keywords.remove(dom_kwtype)

                            # replace with copy of the one from the template
                            copy_type = copy.deepcopy(temp_kwtype)
                            keywords.append(copy_type)
                        else:
                            # make a list of all keyword nodes from self.dom and template using the dictionaries
                            node_list = []
                            for n in dom_kw_dict[k]:
                                node_list.append(n)
                            for n in temp_kw_dict[k]:
                                node_list.append(n)

                            # remove all keywords from self.dom
                            for n in dom_kt.itersiblings():
                                if n.tag.endswith("key"):
                                    dom_kwtype.remove(n)

                            # sort keywords alphabetically and append to the keyword type node
                            for sort_key in sorted(node_list, key=lambda x: x.text):
                                dom_kwtype.append(sort_key)

                        # flag that this k has been found
                        found_kw.append(k)

            # add any keyword sections in the template that do not exist in the self.dom
            # if the temp_directive is append, ignore otherwise
            if self.temp_directive == "append":
                # filter the keywords to add based on the flag list found_kw
                add_kws = {k: v for k, v in temp_kw_dict.items() if not k in found_kw}
                # get or create the keywords node
                keywords = mu.extend_branch(self.dom, "idinfo/keywords")
                # iterate
                for k, v in add_kws.items():
                    kw_type = etree.SubElement(keywords, k[0])

                    # figure out the name of the *kt and key nodes
                    match k[0]:
                        case "stratum":
                            kt_tag = "stratkt"
                        case "temporal":
                            kt_tag = "tempkt"
                        case _:
                            kt_tag = f"{k[0]}kt"

                    # make the <theme/place/strat/tempkt> node and the keywords
                    kt = etree.SubElement(kw_type, kt_tag)
                    kt.text = k[1]
                    for kw in v:
                        kw_type.append(kw)
