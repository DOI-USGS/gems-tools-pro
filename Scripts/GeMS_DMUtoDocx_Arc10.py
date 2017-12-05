"""
Translates DMU table in NCGMP09-style geodatabase into a fully formatted
Microsoft Word .docx file.

Assumes formatting and style names in USGS Pubs template MapManuscript_v1-0_04-11.dotx

Arguments
    Input geodatabase
    Output workspace
    Output filename (if it doesn't end in .docx, .docx will be appended)
    UseMapUnitForUnitLabl (Boolean, either 'true' or 'false')
    
"""

import sys, os.path, arcpy
from GeMS_utilityFunctions import *
from docxModified import *

versionString = 'GeMS_DMUtoDocx_Arc10.py, version of 2 September 2017'
addMsgAndPrint( versionString )

debug = False
debug2 = False

tab = '<tab></tab>'
emDash = u"\u2014"

startTags = []
endTags = []
tags = ['b','i','g','ul','sup','sub','tab']
for tag in tags:
    startTags.append('<'+tag+'>')
    endTags.append('</'+tag+'>')


def isNotBlank(thing):
    if thing <> '' and thing <> None:
        return True
    else:
        return False
    
def isKnownStyle(pStyle):
    if pStyle == 'DMUHeadnote' or pStyle.find('DMU-Heading') > -1 or pStyle.find('DMUUnit') > -1:
        return True
    else:
        return False

def notNullText(txt):
    if txt == '#null' or txt == None or txt == '#Null' or txt == '#' or txt == '' or len(txt.split()) == 0:
        return False
    else:
        return True

gdb = sys.argv[1]
outfl = sys.argv[3]
if outfl.lower()[-5:] <> '.docx':
    outfl = outfl+'.docx'
outDMUdocx = os.path.join(sys.argv[2],outfl)
if sys.argv[4] == 'true':
    useMapUnitForUnitLabl = True
else:
    useMapUnitForUnitLabl = False
if sys.argv[5] == 'true': # LMU only
    notLMU = False
else:
    notLMU = True   

arcpy.env.workspace = gdb


relationships = relationshiplist()
document = newdocument()
docbody = document.xpath('/w:document/w:body', namespaces=nsprefixes)[0]

if notLMU:
    docbody.append(paragraph('Description of Map Units','DMU-Heading1'))
else:
    docbody.append(paragraph('List of Map Units','DMU-Heading1'))
lastParaWasHeading = True

"""
DMU has many rows
  Each row has content for 1 or more paragraphs. 1st paragraph has style 'row.ParagraphStyle'
  2nd and subsequent paragraphs have style 'DMUParagraph'
     Each paragraph is composed of one or more runs, each of which _may_ include
     markup tags

We sort DMU on HierarchyKey and then step through the rows, constructing rowtext w/ markup
  according to row.paragraphStyle.
We then divide the newly-built rowtext into paragraphs.
For each paragraph, we 

"""

addMsgAndPrint('Getting DMU rows and creating output paragraphs')
dmuRows = arcpy.SearchCursor('DescriptionOfMapUnits',"","","",'HierarchyKey')
for row in dmuRows:
    rowText = ''
    if isNotBlank(row.HierarchyKey) and isKnownStyle(row.ParagraphStyle):   
        addMsgAndPrint('  '+ str(row.HierarchyKey)+' '+str(row.ParagraphStyle))
        #if row.ParagraphStyle == 'DMUHeadnote':
        #    rowText = '['+row.Description+']'
        if row.ParagraphStyle.find('DMU-Heading') > -1:  # is a heading
            rowText = row.Name
            paraStyle = row.ParagraphStyle
            if notNullText(row.Description):  # heading has headnote. Append heading to docbody and make new row
                addMsgAndPrint('Description='+row.Description)
                docbody.append(paragraph(rowText,row.ParagraphStyle))
                rowText = row.Description
                paraStyle = 'DMUHeadnote'
                    
        elif row.ParagraphStyle.find('DMUUnit') > -1:  # is a unit
            if not useMapUnitForUnitLabl and notNullText(row.Label):  
                rowText = '<ul>'+row.Label+'</ul>'
            elif useMapUnitForUnitLabl and notNullText(row.MapUnit):
                rowText = '<ul>'+row.MapUnit+'</ul>'
            rowText = rowText + tab
            if row.ParagraphStyle[-1:] in ('4','5'):
                rowText = rowText + tab # add second tab for DMUUnit4 and DMUUnit4
            if isNotBlank(row.Name):
                rowText = rowText + '<b>'+row.Name+'</b>'
            if isNotBlank(row.Age):  
                rowText = rowText + '<b> ('+row.Age+')</b>'
            if isNotBlank(row.Description) and notLMU:
                rowText = rowText + emDash + row.Description
            paraStyle = row.ParagraphStyle
        else: # Unrecognized paragraph style
            addMsgAndPrint('Do not recognize paragraph style '+row.ParagraphStyle)
            
        ## divide into paragraphs and build list of [paraText, paraStyle]
        if debug: addMsgAndPrint('    dividing into paragraphs')
        paras = []
        if paraStyle == 'DMUUnit1' and lastParaWasHeading:
            paraStyle = 'DMUUnit11stafterheading'
        if rowText.find('<br>') > 0:
            print ' got multiple paragraphs!'
            while rowText.find('<br>') > 0:
                paras.append([rowText.partition('<br>')[0],paraStyle])
                rowText = rowText.partition('<br>')[2]
                paraStyle = 'DMUParagraph'
        paras.append([rowText,paraStyle])
        if paraStyle.find('Head') > -1:
            lastParaWasHeading = True
        else:
            lastParaWasHeading = False
        
        if debug: addMsgAndPrint('    finding formatting')
        # for each paragraph:
        for pgraph in paras:
            para = pgraph[0]; paraStyle = pgraph[1]
            runs = []
            while len(para) > 0:
                ## Look for initial unformatted text chunk
                firstPos = len(para)
                for tag in startTags:
                    pos = para.find(tag)
                    if pos > -1 and pos < firstPos:
                        firstPos = pos
                if firstPos > 0:
                    runs.append([[],para[0:firstPos]])
                    newPara = para[firstPos:]
                    para = newPara
                elif firstPos == len(para):
                    runs.append([[],para])
                    para = ''
                ## or may be no initial unformatted chunk (firstpos = 0), in which case do nothing
                ## Then pull succeeding chunks
                runTags = []
                isTag = True
                # trim starting tags (and append them to runTags)
                while len(para) > 0 and isTag == True:
                    isTag = False
                    for tag in startTags:
                        if para.find(tag) == 0:
                             runTags.append(tag.replace('<','').replace('>',''))
                             newPara = para[len(tag):]
                             para = newPara
                             isTag = True
                # find first endTag
                endPos = len(para)
                for tag in endTags:
                    tagPos = para.find(tag)
                    if tagPos > -1 and tagPos < endPos:
                        endPos = tagPos
                runs.append([runTags,para[0:endPos]])
                newPara = para[endPos:]
                para = newPara
                # strip end tags
                isTag = True
                while len(para) > 0 and isTag:
                    isTag = False
                    for tag in endTags:
                        if para.find(tag) == 0:
                            isTag = True
                            newPara = para[len(tag):]
                            para = newPara
                pText = []
                for run in runs:
                    #if debug: addMsgAndPrint(str(run))
                    text = run[1]
                    if text <> '':
                        tags = ''
                        if 'b' in run[0]:
                            tags = tags+'b'
                        if 'i' in run[0]:
                            tags = tags+'i'
                        if 'g' in run[0]:
                            tags = tags+'g'
                        if 'ul' in run[0]:
                            tags = tags+'l'
                        if 'sup' in run[0]:
                            tags = tags+'p'
                        if 'sub' in run[0]:
                            tags = tags+'d'
                        pText.append([text,tags])
                    elif 'tab' in run[0]:
                        # if this run is a tab, ignore any other tags and set tags to 'tab'
                        tags = 'tab'
                        pText.append(['',tags])
                
            docbody.append(paragraph(pText,paraStyle))
            addMsgAndPrint('    finished appending paragraphs')

if sys.argv[4] == 3:
    print Null
    pass

addMsgAndPrint('Setting core properties')

coreprops = coreproperties(title='DMU for '+gdb,subject='',creator=versionString,keywords=['python','NCGMP09','Word'])
appprops = appproperties()
contenttypes = contenttypes()
websettings = websettings()
wordrelationships = wordrelationships(relationships)
    
# Save our document
addMsgAndPrint('Saving to file '+outDMUdocx)
savedocx(document,coreprops,appprops,contenttypes,websettings,wordrelationships,outDMUdocx)


