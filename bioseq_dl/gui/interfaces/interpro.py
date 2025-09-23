from bioseq_dl import InterproInterface

INTERPRO = {
    "class": InterproInterface,
    "label": "Interpro",
    "methods": {
        "entry": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "id",
                    "required": False,
                    "type": "str",
                    "label": "InterPro ID",
                    "placeholder": "IPR000001",
                },
                {
                    "name": "db",
                    "required": False,
                    "type": "str",
                    "label": "Database",
                    "choices": ["Pfam", "PRINTS", "ProDom", "SMART",
                                "ProSiteProfiles", "ProSitePatterns", "SUPERFAMILY", "TIGRFAMs"],
                    "selected": "Pfam"
                },
                {
                    "name": "filters",
                    "required": False,
                    "type": "list[dict]",
                    "label": "Filters",
                    "inputs": [
                        {
                            "name": "type",
                            "required": True,
                            "type": "str",
                            "label": "Type",
                            "choices": ["protein"]
                        },
                        {
                            "name": "db",
                            "required": True,
                            "type": "str",
                            "label": "Database",
                            "placeholder": "reviewed"
                        },
                        {
                            "name": "value",
                            "required": True,
                            "type": "str",
                            "label": "Value",
                            "placeholder": "P02666"
                        }
                    ]
                }
            ]
        }
    }
}