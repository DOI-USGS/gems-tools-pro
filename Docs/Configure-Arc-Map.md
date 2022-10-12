# Configure ArcMap

How you configure ArcMap is a matter of preference. Here are some of mine. 

I strongly encourage you to set a significant [Sticky-move tolerance](#StickyMoveTolerance) and enable [Snapping](#Snapping). Other suggestions below are more optional.



### Default to relative path names

Tap **Customize** on the ArcMap toolbar and select **ArcMap Options...**

[[WikiImages/ArcMapOptions.png]][[WikiImages/RelativePathnames.png]]

On the **General** tab of the **ArcMap Options** window, ensure that **Make relative paths the default for new map documents** is checked. 

If you have already created a map document without making relative paths the default, you can set relative paths for the document by tapping **File** on the ArcMap toolbar, selecting **Map Document Properties...**, and in the **Map Document Properties** window checking **Store relative pathnames to data sources** (near bottom of window).



### Toolbars

Tap **Customize** on the ArcMap toolbar again, and select Toolbars. I choose to work with the following always enabled:

- Advanced Editing
- Editor
- Snapping
- Standard
- Tools
- Topology



### Extensions

They are not generally relevant to GeMS, but I like to have **3D Analyst** and **Spatial Analyst** enabled.



### <a name="StickyMoveTolerance"></a>Sticky-move tolerance

On Editor toolbar, click Editor dropdown and select Options

[[WikiImages/EditorOptions.png]][[WikiImages/StickyMove.png]]

In the **Editing Options** window, on the **General** tab, set **Sticky move tolerance:** to some moderately large number (20 in the example here).  *If you leave it at zero, it is very easy to inadvertently move features while selecting them!* This can be a disaster if you, for example, move map-unit polygons relative to their bounding contacts. 



### Add GeMS_Tools

Open the **ArcToolbox** window 

[[WikiImages/ArcToolbox.png]]

and right-click on an empty area to 

[[WikiImages/AddToolbox.png]] 

to bring up the Add Toolbox window. 

In the Add Toolbox window, navigate to your GeMS_Tools directory 

[[WikiImages/AddToolboxWindow.png]]

and select the appropriate toolbox (.tbx) file: **GeMS_ToolsArc10.5.tbx** if you are using ArcGIS 10.5 or higher, **GeMS_ToolsArc10.tbx** if you are using Arc 10--Arc 10.4. 

I then usually right-click again on an empty area of the **ArcToolbox** window and **Save Settings... To Default**. But this seems to make little difference!  I find I usually have to re-add GeMS_Tools whenever I open an .mxd.

  

### <a name="Snapping"></a>Snapping

Load an editable feature class, such as ContactsAndFaults. Start Editing. On the Snapping toolbar, hit the dropdown and ensure that **Use Snapping** is checked (red below). You may want to also check **Snap to Sketch** (blue below) so that single-arc loops can snap to themselves.

[[WikiImages/Snapping.png]]



### FGDC Symbology

The GeMS schema does not require the use of any particular symbols.  But we encourage you to use the symbols defined in [FGDC Digital Cartographic Standard for Geologic Map Symbolization](https://ngmdb.usgs.gov/fgdc_gds/), FGDC-STD-013-2006.  These are, for the most part, implemented in 

- [style file created by Geological Survey of Canada](https://ngmdb.usgs.gov/Info/standards/GeMS/docs/GSC_FGDC-style.zip) (5.7 MB, requires administrator privileges to install included fonts) 
- [style file created by Alaska Division of Geological and Geophysical Surveys](https://ngmdb.usgs.gov/Info/standards/GeMS/docs/AKDGGS-style_10-2013.zip) (33.4 MB, no font installation required)
- [USGS Symbols2.style](https://github.com/usgs/GeMS_Tools/blob/master/Resources/USGS_Symbols2.zip), included in the Resources directory of GeMS_Tools. This style combines the GSC implementation of the FGDC symbols and the WPGCMYK shadeset (fill colors).  Requires administrator privileges to install the FGDCGeoSym fonts which are included in the zip file