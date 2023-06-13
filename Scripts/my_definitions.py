# -*- coding: utf-8 -*-
# extensions to definitions given in GeMS_Definition.py
#  largely for use in automating generation of FGDC metadata
#  It is likely that this file will be renamed and modified
#  for each map project, and should be kept in the map project
#  working directory.

# Assumptions:
#    a bunch of definitions (dictionary entries) that correspond to
#    dictionaries created in GeMS_Definitions.py
#
#    AND a function addDefs() that appends these entries to the dictionaries
#    from GeMS_Definitions
#
#    1) the interface that drives the calling script locates this file
#    2) this module is loaded by the calling script
#    3) the calling script then executes addDefs()
#

from GeMS_Definition import *

myAttribDict = {
    "SamplePretreatment": [
        "Procedure(s) by which some samples were pretreated, before carbon extraction, to minimize the effects of later contamination.",
        "foobar",
    ],
    "AnalysisMethod": [
        "How carbon isotopes were analyzed. Not reported for all samples. AMS = accelerator mass spectrometry.",
        "foobar",
    ],
    "SampleElevationFt": [
        "Elevation at which sample was collected, in feet above datum.",
        "foobar",
    ],
    "delta_13C": [
        "Observed 13C : 12C ratio, reported as an offset, in parts per thousand, relative to standard value PDB. Not reported for all samples.",
        "foobar",
    ],
    "CalibratedAge": [
        "2-sigma age range determined from CALIB5.2 program (Stuiver and Reimer, 1993). Rounded to nearest decade. Calculated from reservoir-corrected age for marine samples. Also known as calendrical age.",
        "foobar",
    ],
    "Location": [
        "Brief text description of locale at which sample was collected.",
        "foobar",
    ],
    "MaterialDated": [
        "Type of material dated. Values include marine shell, peat, detrital wood, etc.",
        "foobar",
    ],
    "Lab_no": ["Laboratory identifier for analyzed sample.", "foobar"],
    "ConventionalAge": [
        "Age reported by laboratory. Reflects assumed constant 14C production rate and accepted 14C decay constant. Ages normalized to delta 13C = -25.0 per mil, +/- 1 sigma, lab error multiplier = 1.",
        "foobar",
    ],
    "ReservoirCorrectedAge": [
        "The reservoir corrected age for marine shells is the conventional 14C age minus a reservoir value of 1,100 yrs (delta R of 700 +/- 100 yrs; Kovanen and Easterbrook, 2002b). The +/- is the reported laboratory precision and does not include any error associated with determination of the reservoir value. N.A. = not applicable (terrestrial samples). ",
        "foobar",
    ],
    "Significance": ["Brief discussion of significance of reported age.", "foobar"],
    "StratigraphicContext": [
        "Stratigraphic horizon from which sample was collected.",
        "foobar",
    ],
    "Phase": [
        "Integer index number of time period within late Pleistocene history of map area. Nine phases are recognized."
        "foobar"
    ],
}

myEntityDict = {
    "C14Points": "Table that documents locales, sample and analytic information, and significance of selected radiocarbon ages from map area."
}

myUnrepresentableDomainDict = {
    "SamplePretreatment": "Arbitrary string",
    "AnalysisMethod": "Arbitrary string",
    "ElevationFt": "Real number",
    "delta_13C": "Real number",
    "CalibratedAge": "Arbitrary string",
    "Location": "Arbitrary string",
    "MaterialDated": "Arbitrary string",
    "Lab_no": "Arbitrary string",
    "ConventionalAge": "Arbitrary string",
    "ReservoirCorrectedAge": "Arbitrary string",
    "Significance": "Arbitrary string",
    "StratigraphicContext": "Arbitrary string",
}

myEnumeratedValueDomainFieldList = []


def addDefs():
    entityDict.update(myEntityDict)
    attribDict.update(myAttribDict)
    unrepresentableDomainDict.update(myUnrepresentableDomainDict)
    for f in myEnumeratedValueDomainFieldList:
        enumeratedValueDomainFieldList.append(f)
    return
