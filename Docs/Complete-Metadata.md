GeMS stores metadata at three levels:

1. Per-feature metadata

   These include values of DataSourceID, ExistenceConfidence, IdentityConfidence, and LocationConfidenceMeters. 

2. Internal metadata dictionaries

   Tables DataSources and Glossary are metadata. So are DescriptionOfMapUnits and the Correlation of MapUnits diagram, but we treat them separately.

3. Formal metadata for ArcGIS objects (geodatabase, feature dataset, feature class, table)

### What you should do:

1. Keep track of DataSourceID values as you create and (or) import features. In general, for a multi-source map, it is often difficult to reconstruct data sources after the fact. Use of editor tracking, and the resulting time stamp for feature creation, can help

2. Run [Validate Database](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#ValidateDatabase) script

   1. Fix missing values (except for xxxID values)
   2. Add missing entries to tables DataSources and Glossary. Remove unused entries
   3. Run the [(re)Set ID Values](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#(re)SetIDValues) script
   4. Repeat until there are no problems with missing values, unused entries, or duplicate ID values

3. Fire up the Metadata Wizard (https://github.com/usgs/fort-pymdwizard) to create a formal metadata record for the geodatabase as a whole.  Much of the required material is present within a GeMS database, in the file [GeMS_Definitions.py](https://github.com/usgs/GeMS_Tools/Scripts/GeMS_Definitions.py), and in the GeMS documentation. I (RH) have a half-finished set of scripts to extract this material and supply it to the Metadata Wizard, but it's nowhere near ready

   A couple of suggestions:

   1. Many geologic-map databases are parts of a larger work, and should be cited as such. Besides providing intellectual context and more complete bibliographic data, this allows more-visible credit for the creator of the database  
   2. In the Supplemental Information section, note that this is a GeMS database and provide a link to http://ngmdb.usgs.gov/Info/standards/GeMS 