# pwaccs: Pathway Accession Codes
# Falta Pwaccs de gene
OPTIONS = {
    "pug/protein": ["summary", "aids", "concise", "pwaccs", ""],
    "pug/compound": ["default", "record", "synonyms", "sids", "cids", "aids", "assaysummary", "description"],
    "pug/gene": ["summary","aids","concise","pwaccs"],
    "autocomplete": ["default"],
    "pug_view/protein": ["default"],
    "pug_view/compound": ["default"],
    "pug_view/gene": ["default"],
    "pug_view/pathway": ["default"],
    "pug_view/taxonomy": ["default"]
}

COMPOUND_TEMPLATE = {
    "http_method": "GET",
    "path_param": None,
    "parameters": {
        "cid": (str, None, True),
        "name": (str, None, True),
        "smiles": (str, None, True),
        "inchi": (str, None, True),
        "property": (str, None, True),
        "name_type": (str, "complete", True),
    },
    "group_queries": ["cid", "property"],
    "separator": ","
}

PROTEIN_TEMPLATE = {
    "http_method": "GET",
    "path_param": None,
    "parameters": {
        "accession": (str, None, True),
    },
    "group_queries": [None],
    "separator": None 
}

GENE_TEMPLATE = {
    "http_method": "GET",
    "path_param": None,
    "parameters": {
        "genesymbol": (str, None, True),
        "geneid": (str, None, True),
        "synonym": (str, None, True),
        "taxid": (str, None, True),
    },
    "group_queries": ["genesymbol"],
    "separator": ","
}