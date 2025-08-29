from bioseq_dl import (
    AlphafoldInterface, 
    BioDBNetInterface, 
    BioGRIDInterface,
    BrendaInterface,
    ChEMBLInterface,
    ChEBIInterface,
    GenOntologyInterface,
    InterproInterface,
    KEGGInterface,
    PathwayCommonsInterface,
    PantherInterface,
    PDBInterface,
    PrideInterface,
    PubChemInterface,
    ReactomeInterface,
    RefSeqInterface,
    RheaInterface,
    StringInterface
)
from bioseq_dl.constants.biodbnet import inputs as biodbnet_inputs, outputs as biodbnet_outputs

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

# Input_type can be 'atomic' (single string), 'composite' (multiple fields)
# For 'atomic' input_type you can add 'multisearch' to allow multiple queries separated by commas

REGISTRY = {
    "AlphaFold": {
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
    },
    "BioDBNet": {
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
    },
    "BioGRID": {
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
                    },
                    {
                        "name": "accessKey",
                        "required": True,
                        "type": "str",
                        "label": "API Key",
                        "placeholder": "Your BioGRID API key"
                    }
                ]
            }
        }
    },
    "BRENDA": {
        "class": BrendaInterface,
        "label": "BRENDA",
        "init": [
            {
                "name": "email",
                "label": "BRENDA Email",
                "type": "str",
                "required": True,
                "env": ["brenda_email"]
            },
            {
                "name": "password",
                "label": "BRENDA Password",
                "type": "str",
                "required": True,
                "env": ["brenda_password"]
            }
        ],
        "methods": {
            "getKmValue": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "ecNumber",
                        "required": False,
                        "type": "str",
                        "label": "EC Number",
                        "placeholder": "1.1.1.10"
                    },
                    {
                        "name": "organism",
                        "required": False,
                        "type": "str",
                        "label": "Organism Name",
                        "placeholder": "Homo sapiens"
                    },
                    {
                        "name": "kmValue",
                        "required": False,
                        "type": "str",
                        "label": "Km Value",
                        "placeholder": ""
                    },
                    {
                        "name": "kmValueMaximum",
                        "required": False,
                        "type": "str",
                        "label": "Km Value Maximum",
                        "placeholder": ""
                    }
                ]
            },
            "getKcatKmValue": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "ecNumber",
                        "required": False,
                        "type": "str",
                        "label": "EC Number",
                        "placeholder": "1.1.1.10"
                    },
                    {
                        "name": "organism",
                        "required": False,
                        "type": "str",
                        "label": "Organism Name",
                        "placeholder": "Homo sapiens"
                    },
                    {
                        "name": "kcatKmValue",
                        "required": False,
                        "type": "str",
                        "label": "Kcat/Km Value",
                        "placeholder": ""
                    },
                    {
                        "name": "kcatKmValueMaximum",
                        "required": False,
                        "type": "str",
                        "label": "Kcat/Km Value Maximum",
                        "placeholder": ""
                    }
                ]
            },
            "getKiValue": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "ecNumber",
                        "required": False,
                        "type": "str",
                        "label": "EC Number",
                        "placeholder": "1.1.1.10"
                    },
                    {
                        "name": "organism",
                        "required": False,
                        "type": "str",
                        "label": "Organism Name",
                        "placeholder": "Homo sapiens"
                    },
                    {
                        "name": "kiValue",
                        "required": False,
                        "type": "str",
                        "label": "Ki Value",
                        "placeholder": ""
                    },
                    {
                        "name": "kiValueMaximum",
                        "required": False,
                        "type": "str",
                        "label": "Ki Value Maximum",
                        "placeholder": ""
                    }
                ]
            },
            "getPhRange": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "ecNumber",
                        "required": False,
                        "type": "str",
                        "label": "EC Number",
                        "placeholder": "1.1.1.10"
                    },
                    {
                        "name": "organism",
                        "required": False,
                        "type": "str",
                        "label": "Organism Name",
                        "placeholder": "Homo sapiens"
                    },
                    {
                        "name": "phRange",
                        "required": False,
                        "type": "str",
                        "label": "pH Range",
                        "placeholder": "7.0-7.5"
                    },
                    {
                        "name": "phRangeMaximum",
                        "required": False,
                        "type": "str",
                        "label": "pH Range Maximum",
                        "placeholder": ""
                    }
                ]
            },
            "getPhOptimum": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "ecNumber",
                        "required": False,
                        "type": "str",
                        "label": "EC Number",
                        "placeholder": "1.1.1.10"
                    },
                    {
                        "name": "organism",
                        "required": False,
                        "type": "str",
                        "label": "Organism Name",
                        "placeholder": "Homo sapiens"
                    },
                    {
                        "name": "phOptimum",
                        "required": False,
                        "type": "str",
                        "label": "pH Optimum",
                        "placeholder": "7.0"
                    },
                    {
                        "name": "phOptimumMaximum",
                        "required": False,
                        "type": "str",
                        "label": "pH Optimum Maximum",
                        "placeholder": ""
                    }
                ]
            },
            "getPhStability": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "ecNumber",
                        "required": False,
                        "type": "str",
                        "label": "EC Number",
                        "placeholder": "1.1.1.10"
                    },
                    {
                        "name": "organism",
                        "required": False,
                        "type": "str",
                        "label": "Organism Name",
                        "placeholder": "Homo sapiens"
                    },
                    {
                        "name": "phStability",
                        "required": False,
                        "type": "str",
                        "label": "pH Stability",
                        "placeholder": "7.0"
                    },
                    {
                        "name": "phStabilityMaximum",
                        "required": False,
                        "type": "str",
                        "label": "pH Stability Maximum",
                        "placeholder": ""
                    }
                ]
            },
            "getCofactor": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "ecNumber",
                        "required": False,
                        "type": "str",
                        "label": "EC Number",
                        "placeholder": "1.1.1.10"
                    },
                    {
                        "name": "organism",
                        "required": False,
                        "type": "str",
                        "label": "Organism Name",
                        "placeholder": "Homo sapiens"
                    },
                    {
                        "name": "cofactor",
                        "required": False,
                        "type": "str",
                        "label": "Cofactor",
                        "placeholder": "NADP"
                    }
                ]
            },
            "getTemperatureOptimum": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "ecNumber",
                        "required": False,
                        "type": "str",
                        "label": "EC Number",
                        "placeholder": "1.1.1.10"
                    },
                    {
                        "name": "organism",
                        "required": False,
                        "type": "str",
                        "label": "Organism Name",
                        "placeholder": "Homo sapiens"
                    },
                    {
                        "name": "temperatureOptimum",
                        "required": False,
                        "type": "str",
                        "label": "Temperature Optimum",
                        "placeholder": "37"
                    },
                    {
                        "name": "temperatureOptimumMaximum",
                        "required": False,
                        "type": "str",
                        "label": "Temperature Optimum Maximum",
                        "placeholder": ""
                    }
                ]
            },
            "getTemperatureStability": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "ecNumber",
                        "required": False,
                        "type": "str",
                        "label": "EC Number",
                        "placeholder": "1.1.1.10"
                    },
                    {
                        "name": "organism",
                        "required": False,
                        "type": "str",
                        "label": "Organism Name",
                        "placeholder": "Homo sapiens"
                    },
                    {
                        "name": "temperatureStability",
                        "required": False,
                        "type": "str",
                        "label": "Temperature Stability",
                        "placeholder": "37"
                    },
                    {
                        "name": "temperatureStabilityMaximum",
                        "required": False,
                        "type": "str",
                        "label": "Temperature Stability Maximum",
                        "placeholder": ""
                    }
                ]
            },
            "getTemperatureRange": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "ecNumber",
                        "required": False,
                        "type": "str",
                        "label": "EC Number",
                        "placeholder": "1.1.1.10"
                    },
                    {
                        "name": "organism",
                        "required": False,
                        "type": "str",
                        "label": "Organism Name",
                        "placeholder": "Homo sapiens"
                    },
                    {
                        "name": "temperatureRange",
                        "required": False,
                        "type": "str",
                        "label": "Temperature Range",
                        "placeholder": "30-40"
                    },
                    {
                        "name": "temperatureRangeMaximum",
                        "required": False,
                        "type": "str",
                        "label": "Temperature Range Maximum",
                        "placeholder": ""
                    }
                ]
            }
        }
    },
    "ChEMBL": {
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
    },
    "ChEBI": {
        "class": ChEBIInterface,
        "label": "ChEBI",
        "methods": {
            "compound": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "chebi_id",
                        "required": True,
                        "type": "str",
                        "label": "ChEBI ID",
                        "placeholder": "CHEBI:18357",
                    },
                    {
                        "name": "only_ontology_parents",
                        "required": False,
                        "type": "bool",
                        "label": "Only Ontology Parents",
                        "placeholder": "",
                    },
                    {
                        "name": "only_ontology_children",
                        "required": False,
                        "type": "bool",
                        "label": "Only Ontology Children",
                        "placeholder": "",
                    }

                ]
            },
            "compounds": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "chebi_ids",
                        "required": True,
                        "type": "list[str]",
                        "label": "ChEBI ID",
                        "placeholder": "CHEBI:18357,CHEBI:29033",
                    }
                ],
            },
            "es_search": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "term",
                        "required": True,
                        "type": "str",
                        "label": "Search Term",
                        "placeholder": "paracetamol",
                    },
                    {
                        "name": "page",
                        "required": False,
                        "type": "int",
                        "label": "Page",
                        "placeholder": "1",
                    },
                    {
                        "name": "size",
                        "required": False,
                        "type": "int",
                        "label": "Size",
                        "placeholder": "15",
                    }
                ]
            },
            "ontology-children": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "chebi_id",
                        "required": True,
                        "type": "str",
                        "label": "ChEBI ID",
                        "placeholder": "CHEBI:18357",

                    }
                ]
            },
            "ontology-parents": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "chebi_id",
                        "required": True,
                        "type": "str",
                        "label": "ChEBI ID",
                        "placeholder": "CHEBI:18357",

                    }
                ]
            }
        }
    },
    "GenOntology": {
        "class": GenOntologyInterface,
        "label": "Gene Ontology",
        "methods": {
            "bioentity-function": {
                "input_type": "atomic",
                "inputs": [
                    {
                        "name": "atomic",
                        "required": True,
                        "type": "str",
                        "label": "GO ID",
                        "placeholder": "GO:0005783",
                    }
                ],
                "multisearch": True
            },
            "ontology-term": {
                "input_type": "atomic",
                "inputs": [
                    {
                        "name": "goid",
                        "required": True,
                        "type": "str",
                        "label": "GO ID",
                        "placeholder": "GO:0005783",
                    },
                ],
                "multisearch": True
            }
        }
    },
    "Interpro": {
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
    },
    "KEGG": {
        "class": KEGGInterface,
        "label": "KEGG",
        "methods": {
            "get": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "entries",
                        "required": True,
                        "type": "list[str]",
                        "label": "Entries",
                        "placeholder": "hsa:10458",
                    },
                    {
                        "name": "db",
                        "required": False,
                        "type": "str",
                        "label": "Database",
                        "choices": ["genes", "pathway", "compound", "reaction", "enzyme",
                                    "module", "disease", "drug"],
                        "selected": "genes"
                    },
                    {
                        "name": "option",
                        "required": False,
                        "type": "str",
                        "label": "Option",
                        "placeholder": "",
                    }
                ]
            }
        }
    },
    "PathwayCommons": {
        "class": PathwayCommonsInterface,
        "label": "Pathway Commons",
        "methods": {
            "fetch": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "uri",
                        "required": True,
                        "type": "list[str]",
                        "label": "Reactome ID",
                        "placeholder": "R-ALL-444824",
                    },
                    {
                        "name": "pattern",
                        "required": False,
                        "type": "list[str]",
                        "checkboxgroup": ["interacts-with", "used-to-produce"],
                        "label": "Pattern",
                    },
                    {
                        "name": "subpw",
                        "required": False,
                        "type": "bool",
                        "label": "Subpathways",
                    }
                ]
            },
            "top_pathways": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "q",
                        "required": True,
                        "type": "str",
                        "label": "Query",
                        "placeholder": "TYW5",
                    },
                    {
                        "name": "organism",
                        "required": False,
                        "type": "list[str]",
                        "label": "Organism",
                        "placeholder": "9606",
                    },
                    {
                        "name": "datasource",
                        "required": False,
                        "type": "list[str]",
                        "label": "Datasource",
                        "placeholder": "reactome, uniprot",
                    }

                ]
            },
            "neighborhood": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "source",
                        "required": True,
                        "type": "str",
                        "label": "Source",
                        "placeholder": "TYW5",
                    },
                    {
                        "name": "limit",
                        "required": False,
                        "type": "int",
                        "label": "Limit",
                        "placeholder": "1",
                    },
                    {
                        "name": "organism",
                        "required": False,
                        "type": "list[str]",
                        "label": "Organism",
                        "placeholder": "9606",
                    },
                    {
                        "name": "datasource",
                        "required": False,
                        "type": "list[str]",
                        "label": "Datasource",
                        "placeholder": "reactome, uniprot",
                    },
                    {
                        "name": "pattern",
                        "required": False,
                        "type": "list[str]",
                        "checkboxgroup": ["interacts-with"],
                        "label": "Pattern",
                    },
                    {
                        "name": "subpw",
                        "required": False,
                        "type": "bool",
                        "label": "Subpathways",
                    },
                    {
                        "name": "direction",
                        "required": False,
                        "type": "str",
                        "label": "Direction",
                        "choices": ["undirected", "directed", "incoming", "outgoing"],
                        "selected": "undirected"
                    }
                ]
            }         
        }
    },
    "Panther": {
        "class": PantherInterface,
        "label": "Panther",
        "methods": {
            "familyortholog": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "family",
                        "required": True,
                        "type": "str",
                        "label": "Family ID",
                        "placeholder": "PTHR10000",
                    },
                    {
                        "name": "taxonFltr",
                        "required": False,
                        "type": "list[str]",
                        "label": "Taxon Filter",
                        "placeholder": "9606",
                    }
                ]
            },
            "familymsa": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "family",
                        "required": True,
                        "type": "str",
                        "label": "Family ID",
                        "placeholder": "PTHR10000",
                    },
                    {
                        "name": "taxonFltr",
                        "required": False,
                        "type": "list[str]",
                        "label": "Taxon Filter",
                        "placeholder": "9606",
                    }
                ]
            },
            "geneinfo": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "geneInputList",
                        "required": True,
                        "type": "list[str]",
                        "label": "Gene Input List",
                        "placeholder": "BRCA1, CIROP",
                    },
                    {
                        "name": "organism",
                        "required": True,
                        "type": "str",
                        "label": "Organism",
                        "placeholder": "9606",
                    }
                ]
            }
        }
    },
    "ProteinDataBank": {
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
    },
    "Pride": {
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
    },
    "PubChem": {
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
    },
    "Reactome": {
        "class": ReactomeInterface,
        "label": "Reactome",
        "methods": {
            "data-discover": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "id",
                        "required": True,
                        "type": "str",
                        "label": "Reactome ID",
                        "placeholder": "R-HSA-199420"
                    }
                ]
            }
        }
    },
    "RefSeq": {
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
    },
    "Rhea": {
        "class": RheaInterface,
        "label": "Rhea",
        "methods": {
            "rhea": {
                "input_type": "composite",
                "inputs": [
                    {
                        "name": "query",
                        "required": True,
                        "type": "str",
                        "label": "Search Term",
                        "placeholder": "uniprot:*",
                    },
                    {
                        "name": "columns",
                        "required": False,
                        "type": "str",
                        "label": "Columns",
                        "checkboxgroup": ["rhea-id", "equation", "chebi", "chebi-id", "ec", "uniprot", "go"],
                    }
                ]
            }
        }
    },
    "StringDB": {
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
}