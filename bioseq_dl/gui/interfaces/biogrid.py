from bioseq_dl import BioGRIDInterface

BIOGRID ={
    "class": BioGRIDInterface,
    "label": "BioGRID",
    "methods": {
        "interactions": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "id",
                    "required": False,
                    "type": "str",
                    "label": "Entrez Gene ID",
                    "placeholder": "103"
                },
                {
                    "name": "geneList",
                    "required": False,
                    "type": "list[str]",
                    "label": "Genes (Comma separated)",
                    "placeholder": "TP53, BRCA1"
                },
                {
                    "name": "taxId",
                    "required": False,
                    "type": "str",
                    "label": "Taxon ID",
                    "placeholder": "9606"
                }
            ]
        }
    }
}