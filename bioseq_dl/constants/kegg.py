"""KEGG database constants and configuration."""

METHODS = ["info", "list", "find", "get", "conv", "link", "ddi"]

DATABASES = [
    "pathway",
    "brite",
    "module",
    "genome",
    "compound",
    "glycan",
    "reaction",
    "enzyme",
    "network",
    "disease",
    "drug",
    "genes",
    "ligand",
    "kegg",
]

METHOD_OPTIONS = {
    "find": ["formula", "exact_mass", "mol_weight", "nop"],
    "get": ["aaseq", "ntseq", "mol", "kcf", "image", "conf", "kml", "json"],
    "link": ["turtle", "n-triple"],
}
