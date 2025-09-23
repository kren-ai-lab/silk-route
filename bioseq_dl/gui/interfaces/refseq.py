from bioseq_dl import RefSeqInterface

REFSEQ = {
    "class": RefSeqInterface,
    "label": "RefSeq",
    "methods": {
        "protein": {
            "input_type": "atomic",
            "inputs": [
                {
                    "name": "id",
                    "required": True,
                    "type": "str",
                    "label": "Protein ID",
                    "placeholder": "XP_010804480.1,XP_010804481.1",
                }
            ],
            "multisearch": True
        },
        "gene": {
            "input_type": "atomic",
            "inputs": [
                {
                    "name": "id",
                    "required": True,
                    "type": "str",
                    "label": "Gene ID",
                    "placeholder": "672",
                }
            ],
            "multisearch": True
        },
        "popset": {
            "input_type": "atomic",
            "inputs": [
                {
                    "name": "id",
                    "required": True,
                    "type": "str",
                    "label": "Popset ID",
                    "placeholder": "123456",
                }
            ],
            "multisearch": True
        }
    }
}