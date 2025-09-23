from bioseq_dl import RheaInterface

RHEA = {
    "class": RheaInterface,
    "label": "Rhea",
    "methods": {
        "rhea": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "query",
                    "required": True,
                    "type": "str",
                    "label": "Search Term",
                    "placeholder": "uniprot:*",
                },
                {
                    "name": "columns",
                    "required": False,
                    "type": "str",
                    "label": "Columns",
                    "checkboxgroup": ["rhea-id", "equation", "chebi", "chebi-id", "ec", "uniprot", "go"],
                }
            ]
        }
    }
}