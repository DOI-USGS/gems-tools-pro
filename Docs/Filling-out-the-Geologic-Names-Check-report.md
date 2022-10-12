This tool provides a cursory check of formal geologic names applied to geologic units in a GeMS-compliant DescriptionOfMapUnits table (DMU). It allows for the semi-automated comparison of the usage, age, and extent (to the State level) of the unit names in the DMU with the information compiled in the U.S.Geologic Names Lexicon, or [Geolex](https://ngmdb.usgs.gov/Geolex/search#:~:text=The%20U.S.%20Geologic%20Names%20Lexicon,and%20descriptions%20of%20geologic%20units.). 

The script queries Geolex to identify possible matches with any formal geologic names that are among the map unit names in the DMU and then creates a spreadsheet for review by the map author. If submitted to the NGMDB, the secretary of the Geologic Names Committee (GNC) will then evaluate and compile into Geolex the information from the author-provided comments and references and(or) from the map (when published).

Input to the tool is a DMU table although the table need not be a in a file geodatabase — Excel and CSV files are also acceptable — nor are all GeMS fields required. The minimum fields required are ```HierarchyKey```, ```MapUnit```, ```Name```, ```FullName```, and  ```Age```. In addition, the extent of the map features as one or more comma-separated state abbreviations must be provided.

The output of the tool is an Excel spreadsheet that reports the results of posting each ```Name``` in the DMU to the Geolex search API and is organized into three sections:

#### Green - DMU Contents

This section shows the contents of the required fields from the DMU. ```Name``` is the field first evaluated by the script, but if no Geolex names are found there, ```Fullname``` will be evaluated. The other fields are for use by the author when comparing geologic age and extent to the values in Geolex, and to assist in providing some context if clarification of author comments is needed. The values reported in this section, except for ```Extent```, come verbatim from the DMU. Extent is currently collected at runtime through the tool parameter form although it may, in the future, be calculated from features in the geodatabase. 

#### Yellow - Geolex Results

This section shows selected fields from Geolex: ```GeolexID```, ```Name``` (the geographic part of the geologic name), ```Usage```, ```Age```, ```Extent```, and ```Geolex URL```. If multiple usages recorded in Geolex are associated with a single name, all usages and the states in which they are used (i.e., the ```Extent```) are reported. Where that occurs, the value for the DMU HierarchyKey is repeated with an appended incrementing character; those characters serve only to properly re-sort the spreadsheet if the user were to reorganize it.  The URL and Age are listed once for each Geolex Name. 

The value in ```Usage``` comes verbatim from Geolex, so it may include parenthetical phrases or symbols which clarify some property of the usage:
* Asterisk (*) indicates published by U.S. Geological Survey authors.
* "No current usage" (†) implies that a name has been abandoned or has fallen into disuse. Former usage and, if known, replacement name given in parentheses ( ).
* Slash (/) indicates name does not conform with nomenclatural guidelines (CSN, 1933; ACSN, 1961, 1970; NACSN, 1983, 2005). This may be explained within brackets ([]).

#### Orange - Author Review

This section includes five columns: ```Extent Match?```, ```Usage Match?```, ```Age Match?```, ```Remarks```, and ```References```. If any of the state abbreviations in the DMU Extent value are found in the extent for a usage in Geolex, ```Extent Match?``` will be “yes” and, otherwise, “no”. 

```Usage Match?``` will need to be evaluated by the author. Enter “yes” for the usage that exactly, or most closely (e.g., is of the same nomenclatural rank), matches the name on the map.

With this version of the tool, the logic for checking matches of age and status (formal vs informal usages) has not been devised.  Therefore, the author is responsible for determining if a map unit’s geologic age is within the age range specified in Geolex, and for evaluating only those map units that include formal geologic nomenclature.

If there are no exact matches for Usage, please fill out the row that has the closest match, and indicate ```Extent/Usage/Age``` discrepancies in the ```Remarks``` field.

The ```Remarks``` field is for the author to explain discrepancies between Geolex and a unit name shown in their DMU.  The ```References``` field is for citations that support the explanation.

#### Guidance for the Remarks and Reference(s) fields 

##### If formally named geologic units in the DMU are missing from Geolex:
Please include the original or principal reference  and, if applicable, a reference to the current definition of the geologic unit (e.g., perhaps there have been changes to boundaries, rank, assignment to larger units, subdivisions). 

If, in your DMU or accompanying report or pamphlet, you are already citing any of the references requested here, rather than copy/pasting the information into the References field, please simply note “reference(s) cited in map.” 

If you are proposing a new formal geologic unit, Congratulations! Please also separately notify the Geologic Names Committee (GNC) at [gnc@usgs.gov](gnc@usgs.gov), and estimate when your map will be published.

##### Differences in Usage: 
* If there are differences in rank, or in the larger unit—please include the reference(s) in which the formally named geologic unit changed rank or was assigned to (or unassigned from) a larger unit.
* If there are differences in usage, notably for formation-rank units (e.g., Dakota Sandstone, Dakota Formation), please indicate if the usage is local or regional.

If you find a complete match, but you are revising the unit (e.g., changing the upper or lower boundaries), please indicate the nature of the revision in the Remarks field. 

Note that if your map unit name includes two or more formal geologic names (e.g., indicated as “undivided” or “undifferentiated”), they should be listed separately in the results. Please evaluate each geologic name.

##### If the Extent does not match: 
Please indicate if the formal geologic unit is local (occurs in and around your study area) or regional, and if the State in which you mapped the unit should be added to Geolex’s Extent field.

##### If the geologic Age indicated in the DMU is not within the age range indicated in Geolex: 
Please include the reference(s) in which the age of the formal geologic unit was changed. 

##### Regarding whether a unit has Formal or Informal status:
* If Informal in the DMU but Formal in Geolex—please include the reference  in which the formally named geologic unit was abandoned. If the geologic unit has never been formally abandoned and is considered informal by your agency, please briefly state reasons.
* If Formal in the DMU but Informal in Geolex—please include the original or principal reference and, if applicable, a reference to the current definition of the geologic unit (e.g., perhaps there have been changes to boundaries, rank, assignment to larger units, subdivisions).

References should be formal publications, as defined in Article 4 of the 2005 Code (p. 1561), available online at [https://ngmdb.usgs.gov/Geolex/resources/docs/AAPG_Bull-89_NACSN2005-rev2016.pdf](https://ngmdb.usgs.gov/Geolex/resources/docs/AAPG_Bull-89_NACSN2005-rev2016.pdf).