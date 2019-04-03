# -*- coding: cp1252 -*-
# GeMS_Definition.py
# module with definitions for GeMS geodatabase schema for 
# ArcGIS geodatabases (personal or file) for geologic map data
#  
#  Ralph Haugerud, 19 August 2016 
# 

versionString = 'GeMS_Definition.py, version of 6 October 2017'
# fixes errors in Station feature class definition
# 16 Jan 2014: added ObservedMapUnit to Station feature class definition
# 8 April 2016: Fixed ObservedMapUnit.  Put _ID field at end of each field list
# 19 August 2016: Began converting to GeMS
# 9 Sept 2016: Removed CMUText definition
# 4 March 2017: Removed ChangeLog definition. Added MapCollarInformation
# 17 Mar 2017:  Changed MapCollarInformation to MiscellaneousMapInformation, added associated entity and domain descriptions
# 27 March 2017: order of tables in startDict revised to conform with documentation. Fields reordered and amended to conform with documentation
# 20 May 2017: MapUnitOverlayPolys and OverlayPolys (new names) changed to conform to v2 draft. MapUnitLabelPoints removed.
# 6 October 2017: In IsoValueLines definition, changed LocationConfidenceMeters to ValueConfidence
# 8 October 2017: ValueConfidence and URL added to attribDict[]

# to think about: Maybe change all NoNulls to NullsOK?

defaultLength = 254
mapUnitLength = 10
IDLength = 50
memoLength = 3000
booleanLength = 1

# attributes are in order Name DataType NullStatus suggestedLength
# _ID is missing, as it is added programatically, below
startDict = {
# required tables and feature classes
               'MapUnitPolys':         [['MapUnit','String','NoNulls',mapUnitLength],
                                        ['IdentityConfidence','String','NoNulls',IDLength],
                                        ['Label','String','NullsOK',IDLength],
                                        ['Symbol','String','NullsOK',defaultLength],
                                        ['DataSourceID','String','NoNulls',IDLength],
                                        ['Notes','String','NullsOK',defaultLength]],
	'ContactsAndFaults':           [['Type','String','NoNulls',defaultLength],
					['IsConcealed','String','NoNulls',booleanLength],
					['LocationConfidenceMeters','Single','NoNulls'],
					['ExistenceConfidence','String','NoNulls',IDLength],
                                        ['IdentityConfidence','String','NoNulls',IDLength],
                                        ['Symbol','String','NullsOK',defaultLength],
					['Label','String','NullsOK',IDLength],
                                        ['DataSourceID','String','NoNulls',IDLength],
					['Notes','String','NullsOK',defaultLength]],
             'DescriptionOfMapUnits':  [['MapUnit','String','NullsOK',mapUnitLength],  
                                        ['Name','String','NullsOK',defaultLength],
					['FullName','String','NullsOK',defaultLength],
					['Age','String','NullsOK',defaultLength],
					['Description','String','NullsOK',memoLength],
                                        ['HierarchyKey','String','NoNulls',defaultLength],
					['ParagraphStyle','String','NoNulls',defaultLength],
                                        ['Label','String','NullsOK',30],
                                        ['Symbol','String','NullsOK',defaultLength],
					['AreaFillRGB','String','NullsOK',defaultLength],
                                        ['AreaFillPatternDescription','String','NullsOK',defaultLength],
					['DescriptionSourceID','String','NullsOK',IDLength],
                                        ['GeoMaterial','String','NullsOK',defaultLength],
                                        ['GeoMaterialConfidence','String','NullsOK',defaultLength]],
 		   'DataSources':      [['Source','String','NoNulls',500],
					['Notes','String','NullsOK',300],
                                        ['URL','String','NullsOK',300]],
               'Glossary':             [['Term','String','NoNulls',defaultLength],
					['Definition','String','NoNulls',memoLength],
					['DefinitionSourceID','String','NoNulls',IDLength]],
# as-needed tables and feature classes
		'GenericPoints':       [['Type','String','NoNulls',defaultLength],
					['Symbol','String','NullsOK',defaultLength],
					['Label','String','NullsOK',IDLength],
					['LocationConfidenceMeters','Single','NoNulls'],
					['PlotAtScale','Single','NoNulls'],
					['StationID','String','NullsOK',IDLength],
					['MapUnit','String','NoNulls',mapUnitLength],
					['LocationSourceID','String','NoNulls',IDLength],
					['DataSourceID','String','NoNulls',IDLength],
					['Notes','String','NullsOK',defaultLength]],
		'GenericSamples':      [['Type','String','NoNulls',defaultLength],
					['Symbol','String','NullsOK',defaultLength],
					['Label','String','NullsOK',IDLength],
					['FieldSampleID','String','NullsOK',defaultLength],
					['AlternateSampleID','String','NullsOK',defaultLength],
					['MaterialAnalyzed','String','NullsOK',defaultLength],
					['LocationConfidenceMeters','Single','NoNulls'],
					['PlotAtScale','Single','NoNulls'],
					['StationID','String','NullsOK',IDLength],
					['MapUnit','String','NoNulls',mapUnitLength],
					['LocationSourceID','String','NoNulls',IDLength],
					['DataSourceID','String','NoNulls',IDLength],
					['Notes','String','NullsOK',defaultLength]],
		'OrientationPoints':   [['Type','String','NoNulls',defaultLength],
                                        ['Azimuth','Single','NoNulls'],
					['Inclination','Single','NoNulls'],
					['Symbol','String','NullsOK',defaultLength],
					['Label','String','NullsOK',IDLength],
					['LocationConfidenceMeters','Single','NoNulls'],
					['IdentityConfidence','String','NoNulls',50],
					['OrientationConfidenceDegrees','Single','NoNulls'],
					['PlotAtScale','Single','NoNulls'],
					['StationID','String','NullsOK',IDLength],
					['MapUnit','String','NoNulls',mapUnitLength],
					['LocationSourceID','String','NoNulls',IDLength],
					['OrientationSourceID','String','NoNulls',IDLength],
					['Notes','String','NullsOK',defaultLength]],
                'GeochronPoints':      [['Type','String','NoNulls',defaultLength],
					['FieldSampleID','String','NullsOK',defaultLength],
					['AlternateSampleID','String','NullsOK',defaultLength],
					['MapUnit','String','NoNulls',mapUnitLength],
					['Symbol','String','NullsOK',defaultLength],
					['Label','String','NullsOK',IDLength],
					['LocationConfidenceMeters','Single','NoNulls'],
					['PlotAtScale','Single','NoNulls'],
					['MaterialAnalyzed','String','NullsOK',defaultLength],
					['NumericAge','Single','NoNulls'],
					['AgePlusError','Single','NullsOK'],
					['AgeMinusError','Single','NullsOK'],
					['AgeUnits','String','NoNulls',IDLength],
					['StationID','String','NullsOK',IDLength],
					['LocationSourceID','String','NoNulls',IDLength],
					['AnalysisSourceID','String','NullsOK',IDLength],
					['Notes','String','NullsOK',defaultLength]],
		   'Stations':         [['FieldID','String','NoNulls',IDLength],
                                        ['LocationConfidenceMeters','Single','NoNulls'],
					['ObservedMapUnit','String','NoNulls',mapUnitLength],
					['MapUnit','String','NoNulls',mapUnitLength],
					['Symbol','String','NullsOK',defaultLength],
					['Label','String','NullsOK',IDLength],
					['PlotAtScale','Single','NoNulls'],
					['DataSourceID','String','NoNulls',IDLength],  
					['Notes','String','NullsOK',defaultLength],
					['LocationMethod','String','NullsOK',defaultLength],
					['TimeDate','Date','NullsOK'],
					['Observer','String','NullsOK',defaultLength],
					['SignificantDimensionMeters','Single','NullsOK'],
					['GPSX','Double','NoNulls'],
					['GPSY','Double','NoNulls'],  
					['PDOP','Single','NullsOK'],
					['MapX','Double','NoNulls'],
					['MapY','Double','NoNulls']],
		   'GeologicLines':    [['Type','String','NoNulls',defaultLength],
                                        ['IsConcealed','String','NoNulls',booleanLength],
					['LocationConfidenceMeters','Single','NoNulls'],
					['ExistenceConfidence','String','NoNulls',IDLength],
                                        ['IdentityConfidence','String','NoNulls',IDLength],
                                        ['Symbol','String','NullsOK',defaultLength],
					['Label','String','NullsOK',IDLength],
                                        ['DataSourceID','String','NoNulls',IDLength],
					['Notes','String','NullsOK',defaultLength]],
	       'CartographicLines':    [['Type','String','NoNulls',defaultLength],
                                        ['Symbol','String','NullsOK',defaultLength],
					['Label','String','NullsOK',IDLength],
                                        ['DataSourceID','String','NoNulls',IDLength],
					['Notes','String','NullsOK',defaultLength]],
	        'IsoValueLines':       [['Type','String','NoNulls',defaultLength],
                                        ['Value','Single','NoNulls'],
					['ValueConfidence','Single','NoNulls'],
					['Symbol','String','NullsOK',defaultLength],
					['Label','String','NullsOK',IDLength],
                                        ['DataSourceID','String','NoNulls',IDLength],
					['Notes','String','NullsOK',defaultLength]],
                 'MapUnitOverlayPolys':[['MapUnit','String','NoNulls',defaultLength],
                                        ['IdentityConfidence','String','NoNulls',IDLength],
                                        ['Label','String','NullsOK',IDLength],
					['Symbol','String','NullsOK',defaultLength],
                                        ['DataSourceID','String','NoNulls',IDLength],
                                        ['Notes','String','NullsOK',defaultLength]],
                      'OverlayPolys':  [['Type','String','NoNulls',defaultLength],
                                        ['IdentityConfidence','String','NoNulls',IDLength],
                                        ['Label','String','NullsOK',IDLength],
                                        ['Symbol','String','NullsOK',defaultLength],
					['DataSourceID','String','NoNulls',IDLength],
                                        ['Notes','String','NullsOK',defaultLength]],
               'DataSourcePolys':      [['DataSourceID','String','NoNulls',IDLength],
                                        ['Notes','String','NullsOK',defaultLength]],
             'RepurposedSymbols':      [['FgdcIdentifier','String','NoNulls',defaultLength],
                                        ['OldExplanation','String','NoNulls',defaultLength],
                                        ['NewExplanation','String','NoNulls',defaultLength]],
# optional feature classes and tables described in GeMS specification             
        'CMUMapUnitPolys':             [['MapUnit','String','NoNulls',mapUnitLength],
					['Label','String','NullsOK',IDLength],
					['Symbol','String','NullsOK',defaultLength]],
               'CMULines':             [['Type','String','NoNulls',defaultLength],
					['Symbol','String','NullsOK',defaultLength]],
               'CMUPoints':            [['Type','String','NoNulls',defaultLength],
					['Label','String','NullsOK',IDLength],
					['Symbol','String','NullsOK',defaultLength]],
 'MiscellaneousMapInformation':        [['MapProperty','String','NoNulls',defaultLength],
                                        ['MapPropertyValue','String','NoNulls',memoLength]],
               'StandardLithology':    [['MapUnit','String','NoNulls',mapUnitLength],
					['PartType','String','NoNulls',defaultLength],
					['Lithology','String','NoNulls',defaultLength],
					['ProportionTerm','String','NullsOK',defaultLength],
					['ProportionValue','Single','NullsOK'],
					['ScientificConfidence','String','NoNulls',defaultLength],
					['DataSourceID','String','NoNulls',IDLength]],
# optional feature classes not described in GeMS specification               
		   'FossilPoints':     [['Type','String','NoNulls',defaultLength],
					['StationID','String','NullsOK',IDLength],
					['MapUnit','String','NoNulls',mapUnitLength],
					['Label','String','NullsOK',IDLength],
					['Symbol','String','NullsOK',defaultLength],
					['FieldSampleID','String','NullsOK',defaultLength],
					['AlternateSampleID','String','NullsOK',defaultLength],
					['MaterialAnalyzed','String','NullsOK',defaultLength],
					['PlotAtScale','Single','NoNulls'],
					['LocationConfidenceMeters','Single','NoNulls'],
					['FossilForms','String','NoNulls',memoLength],
					['FossilAge','String','NoNulls',defaultLength],
					['LocationSourceID','String','NoNulls',IDLength],
					['FossilFormsSourceID','String','NoNulls',IDLength],
					['FossilAgeSourceID','String','NullsOK',IDLength],
					['Notes','String','NullsOK',defaultLength]], 
		'PhotoPoints':         [['Type','String','NoNulls',defaultLength],
					['StationID','String','NullsOK',IDLength],
					['MapUnit','String','NoNulls',mapUnitLength],
					['Label','String','NullsOK',IDLength],
					['Symbol','String','NullsOK',defaultLength],
					['PlotAtScale','Single','NoNulls'],
					['LocationConfidenceMeters','Single','NoNulls'],
					['LocationSourceID','String','NoNulls',IDLength],
					['DataSourceID','String','NoNulls',IDLength],
                                        ['PhotoID','String','NoNulls',IDLength],
                                        ['PhotoSubject','String','NullsOK',defaultLength],
                                        ['ViewDirection','String','NullsOK',defaultLength],
                                        ['ViewWidth','String','NullsOK',defaultLength],                                         
					['Notes','String','NullsOK',defaultLength]]
}

GeoMaterialConfidenceValues = ["High","Medium","Low"]

GeoMatConfDict = {  'High': ['The term and definition adequately characterize the overall lithologic nature of rocks and sediments in the map unit. Regarding the subjective term "adequately characterize", we refer to context and objectives of this classification as described in the GeMS documentation.',
                             'GeMS documentation'],
                  'Medium': ['The term and definition generally characterize the overall lithology of the map unit, but there are one or more significant minor lithologies that are not adequately described by the selected term.',
                             'GeMS documentation'],
                     'Low': ['The overall lithology of this map unit is not adequately classifiable using this list of terms and definitions, but the term selected is the best available.  Or this map unit is insufficiently known to confidently assign a GeoMaterial term.',
                             'GeMS documentation']
                  }

DefaultExIDConfidenceValues = [['certain', 'Identity of a feature can be determined using relevant observations and scientific judgment; therefore, one can be reasonably confident in the credibility of this interpretation.','FGDC-STD-013-2006'],
                               ['questionable','Identity of a feature cannot be determined using relevant observations and scientific judgment; therefore, one cannot be reasonably confident in the credibility of this interpretation. For example, IdentityConfidence = questionable is appropriate when a geologist reasons "I can see some kind of planar feature that separates map units in this outcrop, but I cannot be certain if it is a contact or a fault."','FGDC-STD-013-2006']]
    


enumeratedValueDomainFieldList = [
    'Type','LocationMethod','PartType','ProportionTerm','TimeScale',
    'ExistenceConfidence','IdentityConfidence',
    'ScientificConfidence','ParagraphStyle','AgeUnits', 'MapUnit',
    'DataSourceID','DescriptionSourceID','DefinitionSourceID','LocationSourceID',
    'OrientationSourceID','AnalysisSourceID',
    'GeoMaterial','GeoMaterialConfidence'
    ]                                  
rangeDomainDict = {
    'Azimuth':['0','360','degrees (angular measure)'],
    'Inclination':['-90','90','degrees (angular measure)']
    }
unrepresentableDomainDict = {
     '_ID':'Arbitrary string. Values should be unique within this database.',
     'PlotAtScale':'Positive real number.',
     'OrientationConfidenceDegrees':'Positive real number. Value of -9, -99, or -999 indicates value is unknown.',
     'LocationConfidenceMeters':'Positive real number. Value of -9, -99, or -999 indicates value is unknown.',
     'Age':'Positive real number. Zero or negative value may indicate non-numeric (e.g., limiting) age.',
     'AgePlusError':'Positive real number. Value of -9, -99, or -999 indicates value is unknown.',
     'AgeMinusError':'Positive real number. Value of -9, -99, or -999 indicates value is unknown.',
     'Notes':'Unrepresentable domain. Free text. Values of <null> or #null indicate no entry.',
     'Value':'Real number.',
     'default':'Unrepresentable domain.',
     'MapProperty':'Unrepresentable domain. Free text.',
     'MapPropertyValue':'Unrepresentable domain. Free text.'
     }
attribDict = {
    '_ID':'Primary key.',
    'Age':'May be interpreted (preferred) age calculated from geochronological analysis, not necessarily the date calculated from a single set of measurements.',
    'AgeMinusError':'Negative (younger) age error, measured in AgeUnits. Type of error (RMSE, 1 sigma, 2 sigma, 95% confidence limit) should be stated in Notes field.',
    'AgePlusError':'Positive (older) age error, measured in AgeUnits. Type of error (RMSE, 1 sigma, 2 sigma, 95% confidence limit) should be stated in Notes field.',
    'AgeUnits':'Units for Age, AgePlusError, AgeMinusError.',
    'AlternateSampleID':'Museum #, lab #, etc.',
    'AnalysisSourceID':'Source of analysis; foreign key to table DataSources.',
    'AreaFillPatternDescription':'Text description (e.g., "random small red dashes") provided as a convenience for users who must recreate symbolization.',
    'AreaFillRGB':'{Red, Green, Blue} tuples that specify the suggested color (e.g., "255,255,255", "124,005,255") of area fill for symbolizing MapUnit. Each color value is an integer between 0 and 255, values are zero-padded to a length of 3 digits, and values are separated by commas with no space: NNN,NNN,NNN.',
    'Azimuth':'Strike or trend, measured in degrees clockwise from geographic North. Use right-hand rule (dip is to right of azimuth direction). Horizontal planar features may have any azimuth.',
    'DataSourceID':'Source of data; foreign key to table DataSources.',
    'Definition':'Plain-language definition.',
    'DefinitionSourceID':'Source of definition; foreign key to DataSources.',
    'Description':'Free-format text description of map unit. Commonly structured according to one or more accepted traditions (e.g., lithology, thickness, color, weathering and outcrop characteristics, distinguishing features, genesis, age constraints) and terse.',
    'DescriptionSourceID':'Source of map-unit description; foreign key to table Datasources.',
    'ExistenceConfidence':'Confidence that feature exists.',
    'FgdcIdentifier':'Identifier for symbol from FGDC Digital Cartographic Standard for Geologic Map Symbolization.',
    'FieldSampleID':'Sample ID given at time of collection.',
    'FullName':'Name of map unit including identification of containing higher rank unit(s), e.g., "Shnabkaib Member of Moenkopi Formation".',
    'GeoMaterial':'Categorization of map unit based on lithologic and genetic character, term selected from NGMDB standard term list defined in Appendix A of GeMS documentation, available at http://ngmdb.usgs.gov/Info/standards/GeMS..',
    'GeoMaterialConfidence':'Describes appropriateness of GeoMaterial term for describing the map unit.',
    'GPSX':'Measured GPS coordinate (easting). May differ from map coordinate because of GPS error or (more likely) base map error.',
    'GPSY':'Measured GPS coordinate (northing). May differ from map coordinate because of GPS error or (more likely) base map error.',
    'HierarchyKey':'String that records hierarchical structure. Has form nn-nn-nn, nnn-nnn, or similar. Numeric, left-padded with zeros, dash-delimited. Each HierarchyKey fragment of each row MUST be the same length to allow text-based sorting of table entries.',
    'IdentityConfidence':'Confidence that feature is correctly identified.',
    'Inclination':'Dip or plunge, measured in degrees down from horizontal. Negative values allowed when specifying vectors (not axes) that point above the horizon, e.g., paleocurrents. Types defined as horizontal (e.g., horizontal bedding) shall have Inclination=0.',
    'IndentedName':'Name with addition of leading spaces to help show rank within a hierarchical list.',
    'IsConcealed':'Flag for contacts and faults covered by overlying map unit.',
    'Label':'Plain-text equivalent of the desired annotation for a feature: for example "14 Ma", or "^c" which (when used with the FGDC GeoAge font) results in the geologic map-unit label TRc (with TR run together to make the Triassic symbol).',
    'LocationConfidenceMeters':'Estimated half-width in meters of positional uncertainty envelope; position is relative to other features in database.',
    'LocationSourceID':'Source of location; foreign key to table DataSources.',
    'MapProperty':'Name of map property. Examples include "Scale", "Authors and affiliations", "Magnetic declination".',
    'MapPropertyValue':'Value of map property. Examples = "1:24,000", "G.S. Smith1 and J. Doe2  1-Division of Geology, Some State, 2-Big University", "16.5 degrees"',
    'MapUnit':'Short plain-text identifier of the map unit. Foreign key to DescriptionOfMapUnits table.',
    'MapX':'Station coordinate (easting) as compiled on the base map; base map should be identified in the DataSources record.',
    'MapY':'Station coordinate (northing) as compiled on the base map; base map should be identified in the DataSources record.',
    'MaterialAnalyzed':'Earth-material which was analyzed, e.g., wood, shell, zircon, basalt, whole-rock.',
    'Name':'Name of map unit, as shown in boldface in traditional DMU, e.g., "Shnabkaib Member". Identifies unit within its hierarchical context.',
    'NewExplanation':'Explanation of usage of symbol in this map portrayal',
    'Notes':'Additional information specific to a particular feature or table entry.',
    'OldExplanation':'Explanatory text from FGDC standard for meaning of symbol',
    'OrientationConfidenceDegrees':'Estimated angular precision of combined azimuth AND inclination measurements, in degrees.',
    'OrientationSourceID':'Source of orientation data; foreign key to table DataSources.',
    'ParagraphStyle':'Token that identifies formatting of paragraph(s) within traditional Description of Map Units that correspond to this table entry.',
    'PlotAtScale':'At what scale (or larger) should this observation or analysis be plotted? At smaller scales, it should not be plotted. Useful to prevent crowding of display at small scales and to display progressively more data at larger and larger scales. Value is scale denominator.',
    'Source':'Plain-text short description that identifies the data source.',
    'StationID':'Foreign key to Stations point feature class.',
    'Symbol':'Reference to a point marker, line symbol, or area-fill symbol that is used on the map graphic to denote the feature: perhaps a star for a K-Ar age locality, or a heavy black line for a fault.',
    'Term':'Plain-language word for a concept. Values must be unique within database as a whole.',
    'Type':'Classifier that specifies what kind of geologic feature is represented by a database element: that a certain line within feature class ContactsAndFaults is a contact, or thrust fault, or water boundary; or that a point in GeochronPoints represents a K-Ar date.',
    'URL':'Universal Resource Locator (URL) or Document Object Identifier (DOI), identifies a document on the World Wide Web.',
    'Value':'Numeric value (e.g., elevation, concentration) associated with an isovalue (contour, isopleth) line. Units identified in feature TYPE definition.',
    'ValueConfidence':'Estimated half-width of uncertainty in numeric value (e.g., elevation, concentration) associated with an isovalue line. Units identified in feature TYPE definition. -9 indicates value is not available.'
    }
entityDict = {
    'CartographicLines':'Lines (e.g., cross-section lines) that have no real-world physical existence, such that LocationConfidenceMeters, ExistenceConfidence, and IdentityConfidence attributes are meaningless, and that are never shown as concealed beneath a covering unit.',
    'CMULines':'Lines (box boundaries, internal contacts, brackets) of the Correlation of Map Units diagram.',
    'CMUPoints':'Points (typically, representing outcrops of a map unit too small to show as polygons at map scale) of the Correlation of Map Units diagram.',
    'CMUMapUnitPolys':'Polygons (representing map units) of the Correlation of Map Units diagram.',
    'CMUText':'Text of the Correlation of Map Units diagram.',
    'ContactsAndFaults':'Contacts between map units, faults that bound map units, and associated dangling faults. Includes concealed faults and contacts, waterlines, snowfield and glacier boundaries, and map boundary.',
    'CorrelationOfMapUnits':'CorrelationOfMapUnits is a feature dataset that encodes the Correlation of Map Units (CMU) diagram found on many geologic maps. Spatial reference frame is arbitrary; units may be page inches.',
    'CrossSection':'Feature dataset equivalent to a cross section.',
    'DataSourcePolys':'Polygons that delineate data sources for all parts of the map.',
    'DataSources':'Non-spatial table of sources of all spatial features, sources of some attributes of spatial features, and sources of some attributes of non-spatial table entries.',
    'DescriptionOfMapUnits':'Non-spatial table that captures content of the Description of Map Units (or equivalent List of Map Units and associated pamphlet text) included in a traditional paper geologic map. Has an internal hierarchy expressed by attribute HierarchyKey',
    'GeochronPoints':'Point locations of samples and accompanying geochronological measurements. Type field identifies geochronological method.',
    'GeologicEvents':'Non-spatial table for closely specifying ages of geologic features. Such ages may be tied to features via entries in table ExtendedAttributes.',
    'GeologicLines':'Lines that represent dikes, coal seams, ash beds, fold hinge-surface traces, isograds, and other linear features. All have these properties: (A) They do not participate in map-unit topology. (B) They correspond to features that exist within the Earth and may be concealed beneath younger, covering, material. (C) They are located with an accuracy that likely can be estimated.',
    'GeologicMap':'GeologicMap is a feature dataset equivalent to the map graphic in a paper report: it contains all the geologic content (but not the base map) within the neatline.',
    'GeoMaterialDict':'Non-spatial table that provides values of GeoMaterial, placed in a hierarchy, and their definitions. For further information, see Appendix A in GeMS documentation, available at http://ngmdb.usgs.gov/Info/standards/GeMS.',
    'Glossary':'Non-spatial table that, for certain fields (including all Type fields, Confidence fields, and GeneralLithology), lists the terms that populate these fields, term definitions, and sources for definitions.',
    'IsoValueLines':'Lines that represent structure contours, concentration isopleths, and other lines that share properties of: (A) Having an associated value (e.g., elevation, concentration) that is a real number. (B ) Having a definable uncertainty in their location. (C) Describing an idealized surface that need not be shown as concealed beneath covering map units.',
    'MiscellaneousMapInformation':'Properties of the map report as a whole. May include title, authorship, scale, geologic mapping credit, editing credit, cartography credit, date of approval, local magnetic declination, publication series and number, and base map information.',
    'MapUnitPolys':'Polygons that record distribution of map units (including water, snowfields, glaciers, and unmapped area) on the particular map horizon. ',
    'MapUnitOverlayPolys':'Polygons that delineate underlying material, overlying material, or some other aspect of earth materials that is described in table DescriptionOfMapUnits, e.g., dike swarm, colluvium. On a map graphic, such polygons are commonly shown by a patterned overprint.', 
    'OrientationPoints':'Point structure data (e.g., bedding attitudes, foliation attitudes, slip vectors measured at a point, etc.), one point per measurement. Multiple measurements at a single station (e.g., bedding and cleavage) should have the same StationID.',
    'OverlayPolys':'Polygons that delineate underlying material, overlying material, or some aspect of earth materials other than the geologic map unit, e.g., dike swarm, alteration zone. On a map graphic, such polygons are commonly shown by a patterned overprint.',
    'RepurposedSymbols':'Non-spatial table that identifies symbols from the FGDC Digital Cartographic Standard for Geologic Map Symbolization (FGDC-STD-013-2006) that are "repurposed" for this map.',
    'StandardLithology':'Non-spatial table for describing the lithologic constituents of geologic map units. Has 1 to many rows per map unit. May be used to extend and supplement the GeneralLithology terms and unstructured free text Description found in the DescriptionOfMapUnits table.',
    'Stations':'Point locations of field observations and (or) samples.',    
    }



#***************************************************
tableDict = {}

# build CSA feature class attribute definitions
startDict['CSAMapUnitPolys'] = startDict['MapUnitPolys']
startDict['CSAContactsAndFaults'] = startDict['ContactsAndFaults']
startDict['CSAOrientationPoints'] = startDict['OrientationPoints']

# set feature_ID definitions
for table in startDict.keys():
	oldFields = startDict[table]
	newfields = []
	for field in oldFields:
		newfields.append(field)
	newfields.append([table+'_ID','String','NoNulls',IDLength])
	tableDict[table] = newfields

# build fieldNullsOKDict
fieldNullsOKDict = {}
for table in tableDict.keys():
    for field in tableDict[table]:
        tableField = table+' '+field[0]
        if field[2] == 'NullsOK':
            fieldNullsOKDict[tableField] = True
        else:
            fieldNullsOKDict[tableField] = False
        
                
