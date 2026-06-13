## Docs available at: https://interpro-documentation.readthedocs.io/en/latest/download.html
## https://github.com/ProteinsWebTeam/interpro7-api/tree/master/docs
## https://www.ebi.ac.uk/interpro/result/download/#

# Define constants for InterPro API
data_types = ["entry", "protein", "structure", "taxonomy", "proteome", "set"]
entry_integration_types = ["all", "integrated", "unintegrated"]

# Constants for search
filter_types = data_types[1:]  # Exclude 'entry' from filter types
db_types = {
    "entry": ["InterPro", "antifam", "pfam", "ncbifam"],  # More can be added
    "protein": ["reviewed", "unreviewed", "UniProt"],
    "structure": ["pdb"],
    "taxonomy": ["uniprot"],
    "proteome": ["uniprot"],
    "set": ["cdd", "pfam", "pirsf"],
}
