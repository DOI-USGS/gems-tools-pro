import arcpy, os.path, sys, math, shutil

from GeMS_utilityFunctions import *

# September 2017: now invokes arcpy.da.Editor in line 183
# 5 October 2017: fixed crash when symbolizing CMU feature dataset

versionString = 'GeMS_SetSymbols_Arc10.py, version of 5 October 2017'

EightfoldLineDict = {}
TwofoldOrientPointDict = {}
MySymbolDict = {}

unrecognizedTypes = []

dictionaryFile = os.path.dirname(sys.argv[0])+'/../Resources/Type-FgdcSymbol.txt'

debug1 = False

def buildSymbolDicts(dFile):
    df = open(dictionaryFile,'r')
    for aline in df:
        if aline[0] <> '#':
            words = aline.split()
            if len(words) > 0:
                aline = aline[:-1]
                newWords = []
                words = aline.split('|')
                for word in words:
                    newWord = word.lstrip().rstrip()
                    newWords.append(newWord)
                if aline == '***Eight-fold Lines***':
                    aDict = EightfoldLineDict
                elif aline == '***Two-fold Orientation Points***':
                    aDict = TwofoldOrientPointDict
                elif aline == '***My Symbols***':
                    aDict = MySymbolDict
                else:
                    key = newWords[0]
                    val1 = newWords[1]
                    if len(newWords) > 2:
                        val2 = newWords[2]
                        aDict[key] = [val1,val2]
                    else:
                        aDict[key] = val1
    
def incrementSymbol(sym,increment):
    symWords = sym.split('.')
    lastWord = symWords[len(symWords)-1]
    newLastWord = str(int(lastWord)+increment).zfill(len(lastWord))
    newSym = sym[0:0-len(lastWord)]+newLastWord
    return newSym

def unrecognizedType(t):
    if not t in unrecognizedTypes:
        unrecognizedTypes.append(t)

def hasCartoRep(fds,fc):
    hostGdb = os.path.dirname(fds)
    domains = arcpy.da.ListDomains(hostGdb)
    shortFc = os.path.basename(fc)
    hasRep = False
    repDomain = ''
    for aDomain in domains:
        if aDomain.name.find(shortFc)>-1 and aDomain.name.find('_rep')>-1:
            hasRep = True
            repDomain = aDomain
    return hasRep, repDomain

def trimLeftZeros(fgdc):
    words = fgdc.split('.')
    fgdc1 = ''
    for word in words:
        fgdc1 = fgdc1+'.'+str(int(word))
    fgdc2 = fgdc1[1:]
    return fgdc2

def buildRepRuleDict(repDomain):
    newDict = {}
    domKeys = list(repDomain.codedValues.keys())
    domKeys.sort()
    for i in domKeys:
        newDict[repDomain.codedValues[i]] = i
    return newDict

#####################################################
addMsgAndPrint('  '+versionString)
addMsgAndPrint('  dictionary file: '+dictionaryFile)

# get inputs
inFds = sys.argv[1]
mapScale = float(sys.argv[2])
certain_Approxmm = float(sys.argv[3])
if sys.argv[4] == 'true':
    useInferred = True
else:
    useInferred = False
if useInferred:
    approx_Inferredmm = float(sys.argv[5])
else:
    approx_Inferredmm = 100
if sys.argv[6] == 'true':
    useApproxOrient = True
else:
    useApproxOrient = False
orientThresholdDegrees = float(sys.argv[7])
if sys.argv[8] == 'true':
    setPolys = True
else:
    setPolys = False
    
# set thresholds
approxThreshold = mapScale * certain_Approxmm / 1000.0
inferredThreshold = mapScale * approx_Inferredmm / 1000.0
#read dictionaryFile to build symbolDicts
buildSymbolDicts(dictionaryFile)
#set featureClasses  (ContactsAndFaults, OrientationPoints, GeologicLines)
caf = getCaf(inFds)
if inFds.find('CorrelationOfMapUnits') == -1:
    gel = caf.replace('ContactsAndFaults','GeologicLines')
    orp = caf.replace('ContactsAndFaults','OrientationPoints')
    mup = caf.replace('ContactsAndFaults','MapUnitPolys')
    fields = ['Type','IsConcealed','LocationConfidenceMeters','ExistenceConfidence','IdentityConfidence','Symbol']
else:  # is CMU
    caf = ''
    mup = inFds+'/CMUMapUnitPolys'
    gel = ''
    orp = ''
    fields = ['Type']
dmu = os.path.dirname(inFds)+'/DescriptionOfMapUnits'
    
addMsgAndPrint('  Feature dataset '+inFds+', isLocked = '+str(arcpy.TestSchemaLock(inFds)))

for fc in caf,gel:
    if arcpy.Exists(fc):
      if numberOfRows(fc) > 0:
        addMsgAndPrint('  processing '+os.path.basename(fc))
        hasRep, repDomain = hasCartoRep(inFds,fc)
        if hasRep:
            fields.append('RuleID1')
            repRuleDict = buildRepRuleDict(repDomain)
        addMsgAndPrint('fields = '+str(fields))
        with arcpy.da.UpdateCursor(fc, fields) as cursor:
            for row in cursor:
                rowChanged = False
                typ = row[0]
                isCon = row[1]
                locConfM = row[2]
                exConf = row[3]
                idConf = row[4]
                if debug1:  addMsgAndPrint(typ)
                if typ in EightfoldLineDict.keys():
                    if debug1: addMsgAndPrint(typ+' is in EightfoldLineDict')
                    inc = 0                     
                    if isQuestionable(exConf) or isQuestionable(idConf):
                        inc = inc+1
                    if isCon == 'N':
                        if useInferred and locConfM > inferredThreshold:
                            inc = inc+4
                        elif locConfM > approxThreshold:
                            inc = inc+2
                    else: # isCon == 'Y'
                        inc = inc+6
                    row[5] = incrementSymbol(EightfoldLineDict[typ],inc)
                    rowChanged = True
                elif typ in MySymbolDict.keys():
                    row[5] = MySymbolDict[typ]
                    rowChanged = True
                else:
                    unrecognizedType(typ)
                if rowChanged:
                    if hasRep:
                        # turn GSC label into original FGDC labe: 06.03 to 6.3
                        noZeros = trimLeftZeros(row[5])
                        if repRuleDict.has_key(noZeros):
                            row[6] = repRuleDict[noZeros]
                    cursor.updateRow(row)     
                    
fields = ['Type','OrientationConfidenceDegrees','Symbol']
fc = orp
if arcpy.Exists(fc):
    addMsgAndPrint('  processing '+os.path.basename(fc))
    hasRep, repDomain = hasCartoRep(inFds,fc)
    if hasRep:
        fields.append('RuleID1')
        repRuleDict = buildRepRuleDict(repDomain)

    with arcpy.da.Editor(os.path.dirname(inFds)) as edit:
        if debug:
            addMsgAndPrint('beginning edit session')
            addMsgAndPrint('fields = '+str(fields)+',  fc = '+fc)
        with arcpy.da.UpdateCursor(fc, fields) as cursor:
            for row in cursor:
                typ = row[0]
                orConf = row[1]
                rowChanged = False
                if typ in TwofoldOrientPointDict.keys():
                    rowChanged = True
                    if orConf > orientThresholdDegrees and useApproxOrient:
                        row[2] = TwofoldOrientPointDict[typ][1]
                    else:
                        row[2] = TwofoldOrientPointDict[typ][0]
                elif typ in MySymbolDict.keys():
                    #addMsgAndPrint('**'+typ+'**')
                    rowChanged = True
                    row[2] = MySymbolDict[typ]
                else:
                    #addMsgAndPrint('++'+typ+'++')
                    unrecognizedType(typ)
                if rowChanged:
                    if hasRep:
                        # turn GSC label into original FGDC label: 06.03 to 6.3
                        noZeros = trimLeftZeros(row[2])
                        if repRuleDict.has_key(noZeros):
                            row[3] = repRuleDict[noZeros]
                    cursor.updateRow(row)

addMsgAndPrint('  \n  Unrecognized Type values: ')
if len(unrecognizedTypes) == 0:
    addMsgAndPrint('    none')
else:
    for t in unrecognizedTypes:
        if t <> None:
            addMsgAndPrint('    '+t)
        else:
            addMsgAndPrint('    missing type value')
addMsgAndPrint('  ')

if setPolys:
    if arcpy.Exists(dmu) and arcpy.Exists(mup):
        addMsgAndPrint('  setting Symbol and Label values in MapUnitPolys')
        mupTable = 'mupTable'
        testAndDelete(mupTable)
        arcpy.MakeTableView_management(mup,mupTable)
        # check to see if join already exists
        joinAdded = True
        fields = arcpy.ListFields(mupTable)
        for f in fields:
            if f.name.find('DescriptionOfMapUnits.Symbol') > -1:
                joinAdded = False
        # else add join
        if joinAdded:
            arcpy.AddJoin_management(mupTable,'MapUnit',dmu,'MapUnit')

        # get field names for Symbol, Label
        mupSymbol = os.path.basename(mup)+'.Symbol'
        mupLabel = os.path.basename(mup)+'.Label'
        # calculate Symbol
        arcpy.CalculateField_management(mupTable,mupSymbol,'!DescriptionOfMapUnits.Symbol!','PYTHON')
        # calculate Label
        arcpy.CalculateField_management(mupTable,mupLabel,'!DescriptionOfMapUnits.Label!','PYTHON')
        # calculate Label for IdentityConfidence <> 'certain'
        if inFds.find('CorrelationOfMapUnits') == -1:
            selectField = arcpy.AddFieldDelimiters(os.path.dirname(inFds),'IdentityConfidence')
            arcpy.SelectLayerByAttribute_management(mupTable,'NEW_SELECTION',selectField+" <> 'certain'")
            arcpy.CalculateField_management(mupTable,'MapUnitPolys.Label','!DescriptionOfMapUnits.Label! + "?"','PYTHON')
        
        # if joinAdded, remove join
        if joinAdded:
            arcpy.RemoveJoin_management(mupTable)
    else:
        addMsgAndPrint('Table '+dmu+' does not exist.')                           
   
#raise arcpy.ExecuteError

