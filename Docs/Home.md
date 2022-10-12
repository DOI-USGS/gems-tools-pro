
### THIS WIKI IS UNDER CONSTRUCTION 
#### At present this wiki is (mostly) a copy of the wiki at https://github.com/usgs/gems-tools-arcmap/wiki
It will get updated to reflect usage of the tools in ArcGIS Pro
***

This wiki documents the [GeMS](http://ngmdb.usgs.gov/Info/standards/GeMS) (<u>**Ge**</u>ologic <u>**M**</u>ap <u>**S**</u>chema) tools for ArcGIS and makes suggestions for the use of GeMS. GeMS is a draft standard for encoding a geologic map in a GIS.  It succeeds the [NCGMP09v1.1 database schema](https://pubs.usgs.gov/of/2010/1335/pdf/usgs_of2010-1335_NCGMP09.pdf) published in 2010. 

GeMS is focused on the publication (transfer and archiving) of a single geologic map, as well as creation of that map.  GeMS is intended to be sufficiently inclusive and extensible to encode the great majority of existing and future geologic maps.  

GeMS is a standard. That is, it is a more-or-less fixed schema intended to give geologic map producers and consumers the benefit of a stable data structure, consistent naming of data elements, and uniform expectations about database content. It is of necessity both a content standard and a format (in ESRI's ArcGIS) standard. It would be good to see GeMS implemented in another GIS. 

Formal documentation of GeMS, useful resources, and historical documents are online at http://ngmdb.usgs.gov/Info/standards/GeMS. Comments and questions about GeMS may be directed to *gems@usgs.gov*. 

We assume that readers have some familiarity with ArcGIS and geologic maps.

This wiki was developed for a 1-day workshop *Implementation of the GeMS database schema for geologic maps*, to be offered at the [May 2018 Digital Mapping Techniques meeting in Lexington, Kentucky](http://kgs.uky.edu/kgsweb/dmt18/index.htm). The wiki is derived from earlier documentation of GeMS_Tools (see older versions of the tools), a half-day short course *Making Digital Geologic Maps with the NCGMP09 Database Schema* at the Geological Society of America 2014 Annual Meeting, and materials used to teach the NCGMP09/GeMS schema to *GIS for the Earth Sciences* and *Field Geology* classes at the University of Washington.  

This wiki is incomplete, incompletely edited, and idiosyncratic. If you feel compelled to fix any of this, please suggest changes! [Raise an issue](https://github.com/usgs/gems-tools-pro/issues/). Or clone the wiki, edit your version, zip up your new and(or) revised files, and send them to gems@usgs.gov with a note that briefly explains what you have done. New pages that describe how you accomplish a GeMS-related task are particularly encouraged. 

## GeMS Tools, an ArcGIS toolbox

[***Link to ArcGIS tool interface documentation***](https://github.com/usgs/gems-tools-pro/wiki/GeMS_ToolsDocumentation)  *With some discussion on tool use*

## Some common tasks

***[Configure ArcMap](https://github.com/usgs/gems-tools-pro/wiki/ConfigureArcMap)***

***[Hard-drive hygiene](https://github.com/usgs/gems-tools-pro/wiki/HardDriveHygiene)***  *Recommendations on directory structure*

[***Work with multi-attribute lines***](https://github.com/usgs/gems-tools-pro/wiki/MultiAttributeLines)

***[Make and color map-unit polygons](https://github.com/usgs/gems-tools-pro/wiki/MakeColorPolygons)***

[***Create CMU and DMU***](https://github.com/usgs/gems-tools-pro/wiki/CMUandDMU)

[***Topology Check***](https://github.com/usgs/gems-tools-pro/wiki/TopologyCheck) *Find topology errors that Arc cannot*

[***Set Symbol and Label values***](https://github.com/usgs/gems-tools-pro/wiki/SymbolsAndLabels)

***[Complete metadata](https://github.com/usgs/gems-tools-pro/wiki/CompleteMetadata)***

***[Finalize database](https://github.com/usgs/gems-tools-pro/wiki/FinalizeDatabase)***

## Learning exercises

[***Make a new geomorphic map***](https://github.com/usgs/gems-tools-pro/wiki/MakeNewGeomorphicMap)

[***Translate an existing digital geologic map***](https://github.com/usgs/gems-tools-pro/wiki/TranslateDigitalMap)

[***Transcribe an existing analog geologic map***](https://github.com/usgs/gems-tools-pro/wiki/TranscribeAnalogMap)

------

The GeMS Tools software and this wiki are preliminary or provisional and are subject to revision. They are being provided to meet the need for timely best science. The software and this wiki have not received final approval by the U.S. Geological Survey (USGS). No warranty, expressed or implied, is made by the USGS or the U.S. Government as to the functionality of the software and related material nor shall the fact of release constitute any such warranty. The software and this wiki are provided on the condition that neither the USGS nor the U.S. Government shall be held liable for any damages resulting from the authorized or unauthorized use of the software.

Any use of trade, firm, or product names is for descriptive purposes only and does not imply endorsement by the U.S. Government.





