from bioseq_dl import PDBInterface
PDB = {
    "class": PDBInterface,
    "label": "Protein Data Bank",
    "methods": {
        "entry": {
            "input_type": "atomic",
            "inputs": [
                {
                    "name": "id",
                    "required": True,
                    "type": "str",
                    "label": "PDB ID",
                    "placeholder": "4HHB",
                }
            ]
        }
    }
}