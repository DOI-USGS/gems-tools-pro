import arcpy, sys, os.path

from GeMS_utilityFunctions import *

# 5 January: added switch to optionally add/subtract polygon-based rules
versionString = 'GeMS_MakeTopology_Arc10.py, version of 5 January 2018'

debug = False

def buildCafMupTopology(inFds, um):
    if um.upper() == 'TRUE':
        useMup = True
    else:
        useMup = False
    inCaf = getCaf(inFds)
    caf = os.path.basename(inCaf)
    nameToken = caf.replace('ContactsAndFaults','')
    if debug:
        addMsgAndPrint('name token='+nameToken)
    if nameToken == '':
        nameToken = 'GeologicMap'
    inMup = inCaf.replace('ContactsAndFaults','MapUnitPolys')
    
    # First delete any existing topology
    ourTop = nameToken+'_topology'
    testAndDelete(inFds+'/'+ourTop)
    # create topology
    addMsgAndPrint('  creating topology '+ourTop)
    arcpy.CreateTopology_management(inFds,ourTop)
    ourTop = inFds+'/'+ourTop
    # add feature classes to topology
    arcpy.AddFeatureClassToTopology_management(ourTop, inCaf,1,1)
    if useMup and arcpy.Exists(inMup):
        addMsgAndPrint(ourTop)
        addMsgAndPrint(inMup)
        arcpy.AddFeatureClassToTopology_management(ourTop, inMup,2,2)
    # add rules to topology
    addMsgAndPrint('  adding rules to topology:')
    for aRule in ('Must Not Overlap (Line)','Must Not Self-Overlap (Line)','Must Not Self-Intersect (Line)','Must Be Single Part (Line)','Must Not Have Dangles (Line)'):
        addMsgAndPrint('    '+aRule)
        arcpy.AddRuleToTopology_management(ourTop, aRule, inCaf)
    # If we add rules that involve MUP, topology must be deleted before polys are rebuilt
    if useMup and arcpy.Exists(inMup):
        for aRule in ('Must Not Overlap (Area)','Must Not Have Gaps (Area)'):
            addMsgAndPrint('    '+aRule)
            arcpy.AddRuleToTopology_management(ourTop, aRule, inMup)
        addMsgAndPrint('    '+'Boundary Must Be Covered By (Area-Line)')
        arcpy.AddRuleToTopology_management(ourTop,'Boundary Must Be Covered By (Area-Line)',inMup,'',inCaf)
    # validate topology
    addMsgAndPrint('  validating topology')
    arcpy.ValidateTopology_management(ourTop)


addMsgAndPrint(versionString)
addMsgAndPrint(sys.argv[1])
buildCafMupTopology(sys.argv[1], sys.argv[2])
