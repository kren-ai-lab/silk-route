from bioseq_dl.constants.biodbnet import inputs as biodbnet_inputs, outputs as biodbnet_outputs
from bioseq_dl import BioDBNetInterface

BIODBNET = {
    "class": BioDBNetInterface,
    "label": "BioDBNet",
    "methods": {
        "db2db": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "input", 
                    "required": True,
                    "type": "str", 
                    "choices": biodbnet_inputs, 
                    "label": "Input Field",
                    "selected": "genesymbol"
                },
                {
                    "name": "inputValues", 
                    "required": True,
                    "type": "list[str]", 
                    "label": "Input Values",
                    "placeholder": "APP"
                },
                {
                    "name": "outputs", 
                    "required": True,
                    "type": "list[str]", 
                    "checkboxgroup": biodbnet_outputs, 
                    "label": "Output Fields"
                },
                {
                    "name": "taxonId",
                    "required": True, 
                    "type": "str", 
                    "label": "Taxon ID",
                    "placeholder": "9606"
                }
            ]
        },
        "getpathways": {
            "input_type": "composite",
            "inputs": [
                {
                    "name": "pathways", 
                    "required": True,
                    "type": "str", 
                    "label": "Pathways",
                    "placeholder": "ncbi, kegg"
                },
                {
                    "name": "taxonId",
                    "required": True,
                    "type": "str", 
                    "label": "Taxon ID",
                    "placeholder": "9606"
                }
            ]
        }
    }
}