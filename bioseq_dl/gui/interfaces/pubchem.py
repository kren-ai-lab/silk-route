from bioseq_dl import PubChemInterface

PUBCHEM_COMPOUND_TEMPLATE = {   
    "input_type": "composite",  
    "inputs": [
{
            "name": "cid",
            "required": False,
            "type": "str",
            "label": "CID",
            "placeholder": "2244",
        },
        {
            "name": "name",
            "required": False,
            "type": "str",
            "label": "Name",
            "placeholder": "Aspirin",
        },
        {
            "name": "smiles",
            "required": False,
            "type": "str",
            "label": "SMILES",
            "placeholder": "CC(=O)OC1=CC=CC=C1C(=O)O",
        },
        {
            "name": "property",
            "required": False,
            "type": "str",
            "label": "Property",
            "placeholder": "MolecularFormula,MolecularWeight,CanonicalSMILES",
        },
    ]
}
PUBCHEM_PROTEIN_TEMPLATE = {
    "input_type": "composite",
    "inputs": [
        {
            "name": "accession",
            "required": True,
            "type": "str",
            "label": "Accession",
            "placeholder": "P02666",
        }
    ]
}
PUBCHEM_GENE_TEMPLATE = {
    "input_type": "composite",
    "inputs": [
        {
            "name": "genesymbol",
            "required": False,
            "type": "str",
            "label": "Gene Symbol",
            "placeholder": "BRCA1",
        },
        {
            "name": "geneid",
            "required": False,
            "type": "str",
            "label": "Gene ID",
            "placeholder": "672",
        },
        {
            "name": "synonym",
            "required": False,
            "type": "str",
            "label": "Synonym",
            "placeholder": "PSCP",
        },
        {
            "name": "taxid",
            "required": False,
            "type": "str",
            "label": "Taxon ID",
            "placeholder": "9606",
        }
    ]
}

PUBCHEM = {
    "class": PubChemInterface,
    "label": "PubChem",
    "methods": {
        "compound": {
            "options": {
                "default": PUBCHEM_COMPOUND_TEMPLATE,
                "record": PUBCHEM_COMPOUND_TEMPLATE,
                "synonyms": PUBCHEM_COMPOUND_TEMPLATE,
                "sids": PUBCHEM_COMPOUND_TEMPLATE,
                "cids": PUBCHEM_COMPOUND_TEMPLATE,
                "aids": PUBCHEM_COMPOUND_TEMPLATE,
                "assaysummary": PUBCHEM_COMPOUND_TEMPLATE,
                "description": PUBCHEM_COMPOUND_TEMPLATE
            }
        },
        "protein": {
            "options": {
                "summary": PUBCHEM_PROTEIN_TEMPLATE,
                "aids": PUBCHEM_PROTEIN_TEMPLATE,
                "concise": PUBCHEM_PROTEIN_TEMPLATE,
                "pwaccs": PUBCHEM_PROTEIN_TEMPLATE
            }
        },
        "gene": {
            "options": {
                "summary": PUBCHEM_GENE_TEMPLATE,
                "aids": PUBCHEM_GENE_TEMPLATE,
                "concise": PUBCHEM_GENE_TEMPLATE,
                "pwaccs": PUBCHEM_GENE_TEMPLATE
            }
        }
    }
}