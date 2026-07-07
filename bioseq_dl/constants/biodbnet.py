"""BioDBNet database constants and configuration."""

# More inputs can be added from
# https://biodbnet.abcc.ncifcrf.gov/webServices/rest.php/biodbnetRestApi.json?method=getinputs
inputs = [
    "ecnumber",
    "geneid",
    "genesymbol",
    "genesymbolandsynonyms",
    "genesymbolorderedlocus",
    "genesymbolorf",
    "goid",
    "interproid",
    "keggcompoundid",
    "keggcompoundname",
    "keggdiseaseid",
    "keggdrugid",
    "keggdrugname",
    "kegggeneid",
    "keggpathwayid",
    "pdbid",
    "pfamid",
    "pubchemid",
    "reactomepathwayname",
    "refseqgenomicaccession",
    "refseqmrnaaccession",
    "refseqproteinaccession",
    "taxonid",
    "uniprotaccession",
    "uniprotentryname",
    "uniprotproteinname",
]

# More outputs can be added from
# https://biodbnet.abcc.ncifcrf.gov/webServices/rest.php/biodbnetRestApi.json?method=getoutputsforinput
outputs = [
    "affyid",
    "genesymbol",
    "go-biologicalprocess",
]
