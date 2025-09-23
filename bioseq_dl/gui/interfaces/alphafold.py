from bioseq_dl import AlphafoldInterface

ALPHAFOLD = {
    "class": AlphafoldInterface,
    "label": "AlphaFold",
    "methods": {
        "prediction": {
            "input_type": "atomic",
            "inputs": [
                {
                    "name": "id", 
                    "required": True,
                    "type": "str", 
                    "label": "UniProt ID",
                    "placeholder": "P02666",
                    
                }
            ],
            "multisearch": True
        }
    }
}