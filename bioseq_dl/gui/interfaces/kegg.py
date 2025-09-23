from bioseq_dl import KEGGInterface

KEGG ={
    "class": KEGGInterface,
    "label": "KEGG",
    "methods": {
        "get": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "entries",
                    "required": True,
                    "type": "list[str]",
                    "label": "Entries",
                    "placeholder": "hsa:10458",
                },
                {
                    "name": "db",
                    "required": False,
                    "type": "str",
                    "label": "Database",
                    "choices": ["genes", "pathway", "compound", "reaction", "enzyme",
                                "module", "disease", "drug"],
                    "selected": "genes"
                },
                {
                    "name": "option",
                    "required": False,
                    "type": "str",
                    "label": "Option",
                    "placeholder": "",
                }
            ]
        }
    }
}