1. [Validate Database](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#ValidateDatabase) 

   One last pass to ensure that there are no missing elements. 

2. [Compact and Backup](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#CompactAndBackup)

   Ensure that there aren't deleted rows that inflate the database unnecessarily. Make a backup copy before the next step.

3. Remove any extraneous elements

   Are there saved MapUnitPolys*NNN* feature classes? Feature classes or tables prepended with *xxx* or *edit_*? These are probably tables and feature classes your users don't need. Delete them.

4. [Translate to Shapefiles](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#TranslateToShapefiles)

   The GeMS schema prescribes the creation of two sets of shapefiles. The SIMPLE set is a denormalized--and commonly incomplete--version of the database designed to be accessible to those with limited GIS resources. The OPEN set is a complete dump of the database into readily-accessible shapefiles and associated open-format tabular data. Use [Translate to Shapefiles](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#TranslateToShapefiles) to create these. 

5. Zip up .pdf, geodatabase, shapefiles .mxd, .style files, base data, etc. for distribution as described below (from pages 14-15 of GeMS specification document):

   ![1526687766959](C:\Users\RHAUGE~1\AppData\Local\Temp\1\1526687766959.png)



