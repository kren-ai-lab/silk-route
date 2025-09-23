from bioseq_dl import StringInterface

STRINGDB = {
    "class": StringInterface,
    "label": "StringDB",
    "methods": {
        "get_string_ids": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "identifiers",
                    "required": True,
                    "type": "list[str]",
                    "label": "Identifiers",
                    "placeholder": "p53",
                },
                {
                    "name": "species",
                    "required": False,
                    "type": "str",
                    "label": "Species",
                    "placeholder": "9606",
                },
                {
                    "name": "echo_query",
                    "required": False,
                    "type": "int",
                    "label": "Echo Query",
                    "placeholder": "0",
                }
            ]
        },
        "interaction_partners": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "identifiers",
                    "required": True,
                    "type": "list[str]",
                    "label": "Identifiers",
                    "placeholder": "p53,cdk2",
                },
                {
                    "name": "species",
                    "required": False,
                    "type": "str",
                    "label": "Species",
                    "placeholder": "9606",
                },
                {
                    "name": "required_score",
                    "required": False,
                    "type": "int",
                    "label": "Required Score",
                    "placeholder": "0.999",
                },
            ]
        }
    }
}