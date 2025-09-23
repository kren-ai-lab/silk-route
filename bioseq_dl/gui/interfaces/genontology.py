from bioseq_dl import GenOntologyInterface

GENONTOLOGY = {
    "class": GenOntologyInterface,
    "label": "Gene Ontology",
    "methods": {
        "bioentity-function": {
            "input_type": "atomic",
            "inputs": [
                {
                    "name": "atomic",
                    "required": True,
                    "type": "str",
                    "label": "GO ID",
                    "placeholder": "GO:0005783",
                }
            ],
            "multisearch": True
        },
        "ontology-term": {
            "input_type": "atomic",
            "inputs": [
                {
                    "name": "goid",
                    "required": True,
                    "type": "str",
                    "label": "GO ID",
                    "placeholder": "GO:0005783",
                },
            ],
            "multisearch": True
        }
    }
}