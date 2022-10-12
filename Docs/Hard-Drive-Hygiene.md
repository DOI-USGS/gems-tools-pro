# Hard drive hygiene
Goals:

- Find stuff, both now and in 5 years when you have forgotten everything
- Segregate *must-be-backed-up* from *can-be-replaced*
- Consistent naming structure (easier to code for, and helps in finding stuff)

3+ sorts of stuff:

- Tools: GeMS_Tools directory, USGS Symbols2.style, ... *can-be-replaced*; *not specific to any project*
- Most base-map materials: DEMs, PLSS lines, scans of topo maps, ...  *can-be-replaced*; *some specific to a particular project*; *often bulky*
- Geology: vectors (.gdb, .shp, .e00) which incorporate lots of expensive to irreplaceable hand editing, .mxd files with carefully-worked-out symbolization, scans of field sheets, ...  *must-be-backed-up*; *specific to a particular project*

Here's a suggested directory structure:

```
My_GIS_workspace/
	Projects/
		Suquamish/  # or whatever your project name is
			BaseMaterials/
				SuquamishBase.gdb/ # clipped hillshade, roads, ... for this map
				ModifiedDEMs.gdb/
				myquad.tif
				myquad.tfw
			FieldSheetScans/
			Suquamish.gdb/
			Suquamish_2017-03-11.gdb/
			00Notes.docx
			Suquamish-edit.mxd
			Suquamish-publish.mxd
		Tualatin/  # another project
		...
	Resources/
		DEMs/  # regional library of DEMs, not project-specific
		GeMS_Tools-2018May03/
			Docs/
			Resources/
			Scripts/
			.gitignore
			GeMS_ToolsArc10.tbx
			GeMS_ToolsArc10.5.tbx
			LICENSE.md
			README.md	
```

Don't use spaces in pathnames. They can be a pain to code around. 

Best to back up everything. But if back-up resources are limited, back up the Projects directory and skip the Resources directory. 

Maintain at least two .mxds, one for editing and analysis and one for publication.  Typically these will be rather different, with a changing,  unstable .mxd for editing and a publication .mxd that records very carefully worked out symbolization.  

You may find yourself *saving as...* an .mxd to clear it of accumulated cruft. If you do this, post-pend successively higher numbers to the name (Suquamish-edit2.mxd, Suquamish-edit3.mxd, ...) and always use the one with the highest number. After a while you can delete the old, lower-number versions.

Don't stuff DEMs or non-Arc objects into your vector geology .gdb directories. An exception: GeMS_Tools [Create New Database](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#create-new-database) script places 00logfile.txt in the .gdb and [Compact and Backup](https://github.com/usgs/GeMS_Tools/wiki/GeMS_ToolsDocumentation#compact-and-backup) has an option to write to this file. You may want to use 00logfile.txt to supplement the minimal logging that ESRI provides. 

