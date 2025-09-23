from bioseq_dl import PathwayCommonsInterface

PATHWAYCOMMONS = {
    "class": PathwayCommonsInterface,
    "label": "Pathway Commons",
    "methods": {
        "fetch": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "uri",
                    "required": True,
                    "type": "list[str]",
                    "label": "Reactome ID",
                    "placeholder": "R-ALL-444824",
                },
                {
                    "name": "pattern",
                    "required": False,
                    "type": "list[str]",
                    "checkboxgroup": ["interacts-with", "used-to-produce"],
                    "label": "Pattern",
                },
                {
                    "name": "subpw",
                    "required": False,
                    "type": "bool",
                    "label": "Subpathways",
                }
            ]
        },
        "top_pathways": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "q",
                    "required": True,
                    "type": "str",
                    "label": "Query",
                    "placeholder": "TYW5",
                },
                {
                    "name": "organism",
                    "required": False,
                    "type": "list[str]",
                    "label": "Organism",
                    "placeholder": "9606",
                },
                {
                    "name": "datasource",
                    "required": False,
                    "type": "list[str]",
                    "label": "Datasource",
                    "placeholder": "reactome, uniprot",
                }

            ]
        },
        "neighborhood": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "source",
                    "required": True,
                    "type": "str",
                    "label": "Source",
                    "placeholder": "TYW5",
                },
                {
                    "name": "limit",
                    "required": False,
                    "type": "int",
                    "label": "Limit",
                    "placeholder": "1",
                },
                {
                    "name": "organism",
                    "required": False,
                    "type": "list[str]",
                    "label": "Organism",
                    "placeholder": "9606",
                },
                {
                    "name": "datasource",
                    "required": False,
                    "type": "list[str]",
                    "label": "Datasource",
                    "placeholder": "reactome, uniprot",
                },
                {
                    "name": "pattern",
                    "required": False,
                    "type": "list[str]",
                    "checkboxgroup": ["interacts-with"],
                    "label": "Pattern",
                },
                {
                    "name": "subpw",
                    "required": False,
                    "type": "bool",
                    "label": "Subpathways",
                },
                {
                    "name": "direction",
                    "required": False,
                    "type": "str",
                    "label": "Direction",
                    "choices": ["undirected", "directed", "incoming", "outgoing"],
                    "selected": "undirected"
                }
            ]
        }         
    }
}