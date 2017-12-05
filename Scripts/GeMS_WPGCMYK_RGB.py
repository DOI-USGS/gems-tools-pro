import colortrans, sys, arcpy
from GeMS_utilityFunctions import *

gdb = sys.argv[1]

dmu = gdb+'/DescriptionOfMapUnits'

fields = ('Symbol','AreaFillRGB')

with arcpy.da.UpdateCursor(dmu, fields) as cursor:
    for row in cursor:
        if row[0] <> None:
            try:
                rgb = colortrans.wpg2rgb(row[0])
                r,g,b = rgb.split(',')
                rr = r.zfill(3)
                gg = g.zfill(3)
                bb = b.zfill(3)
                rrggbb = rr+','+gg+','+bb
                addMsgAndPrint(str(row)+', '+rgb+', '+rrggbb)
                cursor.updateRow([row[0],rrggbb])
            except:
                addMsgAndPrint('Symbol = '+str(row[0])+': failed to assign RGB value')
        else:
            addMsgAndPrint('No Symbol value')

