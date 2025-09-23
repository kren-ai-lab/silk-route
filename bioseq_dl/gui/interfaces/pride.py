from bioseq_dl import PrideInterface

PRIDE = {
    "class": PrideInterface,
    "label": "Pride",
    "methods": {
        "search": {
            "options": {
                "projects": {
                    "input_type": "composite",
                    "inputs": [
                        {
                            "name": "keyword",
                            "required": True,
                            "type": "str",
                            "label": "Keyword",
                            "placeholder": "cancer",
                        },
                        {
                            "name": "filter",
                            "required": False,
                            "type": "str",
                            "label": "Filter",
                            "placeholder": "",
                        }
                    ]
                }
                
            }
        },
        "projects": {
            "options": {
                "default": {
                    "input_type": "composite",
                    "inputs": [
                        {
                            "name": "projectAccession",
                            "required": True,
                            "type": "str",
                            "label": "Project Accession",
                            "placeholder": "PXD000001",
                        }
                    ]
                },
                "similarProjects": {
                    "input_type": "composite",
                    "inputs": [
                        {
                            "name": "accession",
                            "required": True,
                            "type": "str",
                            "label": "Accession",
                            "placeholder": "PXD000001",
                        }
                    ]
                }
            }
        }
    }
}