"""STRING database constants and configuration."""

METHODS = [
    "get_string_ids",
    "network",
    "get_link",
    "interaction_partners",
    "homology",
    "homology_best",
    "enrichment",
    "ppi_enrichment",
    "valueranks_enrichment_submit",
]

METHOD_FORMATS = {
    "get_string_ids": ["json", "tsv", "tsv-no-header", "xml"],
    "network": ["image", "highres_image", "svg"],
    "get_link": ["json", "tsv", "tsv-no-header", "xml"],
    "interaction_partners": ["json", "tsv", "tsv-no-header", "xml", "psi-mi", "psi-mi-lab"],
    "homology": ["tsv", "tsv-no-header", "json", "xml"],
    "homology_best": ["json", "tsv", "tsv-no-header", "xml"],
}

METHOD_PARAMS = {
    "get_string_ids": ["identifiers", "echo_query", "species", "caller_identity"],
    "network": [
        "identifiers",
        "species",
        "add_color_nodes",
        "add_white_nodes",
        "required_score",
        "network_type",
        "caller_identify",
    ],
    "get_link": [
        "identifiers",
        "species",
        "add_color_nodes",
        "add_white_nodes",
        "required_score",
        "network_flavor",
        "network_type",
        "hide_node_labels",
        "hide_disconnected_nodes",
        "show_query_node_labels",
        "block_structure_pics_in_bubbles",
        "caller_identify",
    ],
    "interaction_partners": [
        "identifiers",
        "species",
        "limit",
        "required_score",
        "network_type",
        "caller_identity",
    ],
    "homology": ["identifiers", "species", "caller_identity"],
    "homology_best": ["identifiers", "species", "species_b", "caller_identity"],
}
