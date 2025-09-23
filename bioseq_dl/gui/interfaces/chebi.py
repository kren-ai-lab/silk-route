from bioseq_dl import ChEBIInterface

CHEBI = {
    "class": ChEBIInterface,
    "label": "ChEBI",
    "methods": {
        "compound": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "chebi_id",
                    "required": True,
                    "type": "str",
                    "label": "ChEBI ID",
                    "placeholder": "CHEBI:18357",
                },
                {
                    "name": "only_ontology_parents",
                    "required": False,
                    "type": "bool",
                    "label": "Only Ontology Parents",
                    "placeholder": "",
                },
                {
                    "name": "only_ontology_children",
                    "required": False,
                    "type": "bool",
                    "label": "Only Ontology Children",
                    "placeholder": "",
                }

            ]
        },
        "compounds": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "chebi_ids",
                    "required": True,
                    "type": "list[str]",
                    "label": "ChEBI ID",
                    "placeholder": "CHEBI:18357,CHEBI:29033",
                }
            ],
        },
        "es_search": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "term",
                    "required": True,
                    "type": "str",
                    "label": "Search Term",
                    "placeholder": "paracetamol",
                },
                {
                    "name": "page",
                    "required": False,
                    "type": "int",
                    "label": "Page",
                    "placeholder": "1",
                },
                {
                    "name": "size",
                    "required": False,
                    "type": "int",
                    "label": "Size",
                    "placeholder": "15",
                }
            ]
        },
        "ontology-children": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "chebi_id",
                    "required": True,
                    "type": "str",
                    "label": "ChEBI ID",
                    "placeholder": "CHEBI:18357",

                }
            ]
        },
        "ontology-parents": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "chebi_id",
                    "required": True,
                    "type": "str",
                    "label": "ChEBI ID",
                    "placeholder": "CHEBI:18357",

                }
            ]
        }
    }
}