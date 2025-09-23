from bioseq_dl import ReactomeInterface

REACTOME = {
    "class": ReactomeInterface,
    "label": "Reactome",
    "methods": {
        "data-discover": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "id",
                    "required": True,
                    "type": "str",
                    "label": "Reactome ID",
                    "placeholder": "R-HSA-199420"
                }
            ]
        }
    }
}