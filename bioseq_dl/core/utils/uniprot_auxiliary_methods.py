from typing import Any


# Specific extraction functions
def extract_simple(value: Any) -> Any:
    """Extracts a simple value from the data"""
    return value


def extract_ec_numbers(ec_data: list) -> list[str]:
    """Extracts EC numbers"""
    return [ec["value"] for ec in ec_data] if isinstance(ec_data, list) else []


def extract_gene_names(gene_names: list) -> list[str]:
    """Extracts gene names"""
    return [gene["geneName"]["value"] for gene in gene_names] if isinstance(gene_names, list) else []


def extract_database_terms(xrefs: list, database: str) -> list[str]:
    """Extracts database terms"""
    # Comment solution
    if all("reaction" in xref for xref in xrefs if isinstance(xrefs, list)):
        return [
            reaction_xref.get("id")
            for xref in xrefs
            for reaction_xref in xref.get("reaction", {}).get("reactionCrossReferences", [])
            if reaction_xref.get("database") == database
        ]
    # Normal solution
    return [x["id"] for x in xrefs if isinstance(x, dict) and x.get("database") == database]


def extract_references(refs: list) -> list[dict]:
    """Extracts references"""
    extracted = []
    for ref in refs if isinstance(refs, list) else []:
        citation = ref.get("citation", {})
        extracted.append(
            {
                "title": citation.get("title"),
                "authors": citation.get("authors", []),
                "journal": citation.get("journal"),
                "pub_date": citation.get("publicationDate"),
                "pmid": next(
                    (
                        x["id"]
                        for x in citation.get("citationCrossReferences", [])
                        if x.get("database") == "PubMed"
                    ),
                    None,
                ),
            }
        )
    return extracted


# TODO: currently not used, delete if not needed
def extract_features(features: list) -> list[dict]:
    """Extracts protein features"""
    return [
        {"type": f.get("type"), "description": f.get("description", ""), "location": f.get("location", {})}
        for f in features
        if isinstance(features, list)
    ]


# For fields ft_mutagen and ft_variant
def extract_variants(features: list) -> list[dict]:
    """Extracts variant information"""
    VARIANTS_NAMES = {"Mutagenesis", "Natural variant", "Disease mutation"}
    extracted = []
    for feature in features if isinstance(features, list) else []:
        if feature.get("type") in VARIANTS_NAMES:
            vtype = feature.get("type")
            id = feature.get("featureId", "")
            variant_start_pos = feature.get("location", "").get("start", "").get("value")
            variant_end_pos = feature.get("location", "").get("end", "").get("value")
            if variant_start_pos and variant_end_pos:
                if variant_start_pos == variant_end_pos:
                    location = variant_start_pos
                else:
                    location = f"{variant_start_pos}-{variant_end_pos}"
            else:
                location = ""
            original_seq = feature.get("alternativeSequence", "").get("originalSequence", "")
            alt_seqs = feature.get("alternativeSequence", []).get("alternativeSequences", [])
            description = feature.get("description", "")

            extracted.append(
                {
                    "type": vtype,
                    "id": id,
                    "location": location,
                    "originalSequence": original_seq,
                    "alternativeSequences": alt_seqs,
                    "description": description,
                }
            )

    return extracted


def extract_diseases(comments: list) -> list[dict]:
    """Extract structured disease comments from UniProt comment data."""
    if not isinstance(comments, list):
        return []

    extracted = []
    for comment in comments:
        if not isinstance(comment, dict) or comment.get("commentType") != "DISEASE":
            continue

        disease = comment.get("disease")
        if not isinstance(disease, dict):
            continue

        note_texts = []
        note = comment.get("note", {})
        note_items = note.get("texts", []) if isinstance(note, dict) else []

        if isinstance(note_items, dict):
            note_items = [note_items]
        elif not isinstance(note_items, list):
            note_items = [note_items] if note_items else []

        for text in note_items:
            value = text.get("value", "") if isinstance(text, dict) else str(text)
            if value:
                note_texts.append(value)

        cross_reference = disease.get("diseaseCrossReference", {})
        cross_reference = dict(cross_reference) if isinstance(cross_reference, dict) else {}

        evidences = disease.get("evidences", [])
        evidences = list(evidences) if isinstance(evidences, list) else []

        extracted.append(
            {
                "disease_id": disease.get("diseaseId", ""),
                "acronym": disease.get("acronym", ""),
                "accession": disease.get("diseaseAccession", ""),
                "description": disease.get("description", ""),
                "cross_reference": cross_reference,
                "note": " ".join(note_texts),
                "evidences": evidences,
            }
        )

    return extracted


# For fields ft_act_site, ft_binding, and ft_site.
def extract_active_sites(active_sites: list) -> list[dict]:
    """Extracts active sites from features"""
    ACTIVE_SITE_TYPES = {"Active site", "Binding site", "Site"}
    extracted = []
    for feature in active_sites if isinstance(active_sites, list) else []:
        if feature.get("type") in ACTIVE_SITE_TYPES:
            stype = feature.get("type")
            description = feature.get("description", "")
            site_start_pos = feature.get("location", "").get("start", "").get("value")
            site_end_pos = feature.get("location", "").get("end", "").get("value")
            if site_start_pos and site_end_pos:
                if site_start_pos == site_end_pos:
                    location = site_start_pos
                else:
                    location = f"{site_start_pos}-{site_end_pos}"
            else:
                location = ""
            extracted.append(
                {
                    "type": stype,
                    "description": description,
                    "location": location,
                }
            )

    return extracted


# for fields cc_interaction
def extract_interactions(comments: list) -> list[dict]:
    """Extracts interaction information from comments"""
    extracted = []
    for c in comments if isinstance(comments, list) else []:
        comment_type = c.get("commentType", "")
        if comment_type != "INTERACTION":
            continue

        interactors = c.get("interactions", [])
        for interactor in interactors:
            interactor_one = interactor.get("interactantOne", {})
            interactor_two = interactor.get("interactantTwo", {})
            extracted.append(
                {
                    "accesion_a": interactor_one.get("uniProtKBAccession", ""),
                    "geneName_a": interactor_one.get("geneName", ""),
                    # You can also retrieve intact id, but will be left out for now
                    #'intActId_a': interactor_one.get('intActId', '')
                    "accesion_b": interactor_two.get("uniProtKBAccession", ""),
                    "geneName_b": interactor_two.get("geneName", ""),
                    #'intActId_b': interactor_two.get('intActId', '')
                    "numberOfExperiments": interactor.get("numberOfExperiments", 0),
                    "organismDiffer": interactor.get("organismDiffer", False),
                }
            )
    return extracted


# for fields temp_dependence, ph_dependence
def extract_temperature(comments: list) -> list[str]:
    """Extracts temperature dependence information from comments"""
    extracted = []
    for c in comments if isinstance(comments, list) else []:
        comment_type = c.get("commentType", "")
        if comment_type != "BIOPHYSICOCHEMICAL PROPERTIES":
            continue

        if "temperatureDependence" in c:
            temp_dep = c.get("temperatureDependence", {}).get("texts", [])
            for temp in temp_dep:
                temp_value = temp.get("value", "")
                extracted.append(temp_value)
    return extracted


# for fields temp_dependence, ph_dependence
def extract_ph(comments: list) -> list[str]:
    """Extracts pH dependence information from comments"""
    extracted = []
    for c in comments if isinstance(comments, list) else []:
        comment_type = c.get("commentType", "")
        if comment_type != "BIOPHYSICOCHEMICAL PROPERTIES":
            continue

        if "phDependence" in c:
            ph_dep = c.get("phDependence", {}).get("texts", [])
            for ph in ph_dep:
                ph_value = ph.get("value", "")
                extracted.append(ph_value)
    return extracted


# for fields ft_domain,ft_motif and ft_region,
def extract_domains(domains: list) -> list[dict]:
    """Extracts protein domains from features"""
    DOMAINS_TYPES = {"Region", "Motif", "Domain", "Repeat", "Coiled coil", "Compositional bias"}
    extracted = []
    for domain in domains if isinstance(domains, list) else []:
        if domain.get("type") in DOMAINS_TYPES:
            dtype = domain.get("type")
            description = domain.get("description", "")
            domain_start_pos = domain.get("location", "").get("start", "").get("value")
            domain_end_pos = domain.get("location", "").get("end", "").get("value")
            if domain_start_pos and domain_end_pos:
                if domain_start_pos == domain_end_pos:
                    location = domain_start_pos
                else:
                    location = f"{domain_start_pos}-{domain_end_pos}"
            else:
                location = ""
            extracted.append(
                {
                    "type": dtype,
                    "description": description,
                    "location": location,
                }
            )

    return extracted


def extract_keywords(keywords: list) -> list[str]:
    """Extracts keywords"""
    return [kw.get("name", "") for kw in keywords if isinstance(keywords, list)]
