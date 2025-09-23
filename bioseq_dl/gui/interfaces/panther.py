from bioseq_dl import PantherInterface

PANTHER = {
    "class": PantherInterface,
    "label": "Panther",
    "methods": {
        "familyortholog": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "family",
                    "required": True,
                    "type": "str",
                    "label": "Family ID",
                    "placeholder": "PTHR10000",
                },
                {
                    "name": "taxonFltr",
                    "required": False,
                    "type": "list[str]",
                    "label": "Taxon Filter",
                    "placeholder": "9606",
                }
            ]
        },
        "familymsa": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "family",
                    "required": True,
                    "type": "str",
                    "label": "Family ID",
                    "placeholder": "PTHR10000",
                },
                {
                    "name": "taxonFltr",
                    "required": False,
                    "type": "list[str]",
                    "label": "Taxon Filter",
                    "placeholder": "9606",
                }
            ]
        },
        "geneinfo": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "geneInputList",
                    "required": True,
                    "type": "list[str]",
                    "label": "Gene Input List",
                    "placeholder": "BRCA1, CIROP",
                },
                {
                    "name": "organism",
                    "required": True,
                    "type": "str",
                    "label": "Organism",
                    "placeholder": "9606",
                }
            ]
        }
    }
}