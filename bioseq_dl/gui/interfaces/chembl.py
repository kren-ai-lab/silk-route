from bioseq_dl import ChEMBLInterface

CHEMBL = {
    "class": ChEMBLInterface,
    "label": "ChEMBL",
    "methods": {
        "activity": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "target_chembl_id",
                    "required": True,
                    "type": "str",
                    "label": "Compound ID",
                    "placeholder": "CHEMBL1824"
                },
                {
                    "name": "pchembl_value",
                    "required": False,
                    "type": "float",
                    "label": "P-Value",
                    "placeholder": "5.62"
                }
            ]
        },
        "binding_site": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "target_chembl_id",
                    "required": True,
                    "type": "str",
                    "label": "Compound ID",
                    "placeholder": "CHEMBL1824"
                }
            ]
        }
    }
}