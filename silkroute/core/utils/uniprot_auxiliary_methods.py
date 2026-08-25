"""Field extraction helpers for UniProt API responses."""

from collections.abc import Iterator
from typing import Any


# Specific extraction functions
def extract_simple(value: Any) -> Any:
    """Extract a simple value from the data."""
    return value


def extract_ec_numbers(ec_data: list) -> list[str]:
    """Extract EC numbers.

    Args:
        ec_data (list): EC number entries, each a dict with a ``value`` key.

    Returns:
        list[str]: The EC number values, or an empty list if input is not a list.

    """
    return [ec["value"] for ec in ec_data] if isinstance(ec_data, list) else []


def extract_protein_name(description: dict) -> str | None:
    """Extract the recommended protein name, falling back to a submitted name."""
    if not isinstance(description, dict):
        return None
    recommended = description.get("recommendedName") or {}
    value = (recommended.get("fullName") or {}).get("value")
    if value:
        return value
    for submitted in description.get("submissionNames") or []:
        value = (submitted.get("fullName") or {}).get("value")
        if value:
            return value
    return None


def _iter_protein_names(description: dict) -> Iterator[dict]:
    """Yield UniProt protein-name objects from a description and its components."""
    if not isinstance(description, dict):
        return

    recommended = description.get("recommendedName")
    if isinstance(recommended, dict):
        yield recommended
    for key in ("submissionNames", "alternativeNames"):
        for name in description.get(key) or []:
            if isinstance(name, dict):
                yield name

    for key in ("contains", "includes"):
        for component in description.get(key) or []:
            if isinstance(component, dict):
                yield from _iter_protein_names(component)


def extract_protein_ec_numbers(description: dict) -> list[str]:
    """Extract stable, deduplicated EC numbers from UniProt protein names/components."""
    values = [
        ec.get("value")
        for name in _iter_protein_names(description)
        for ec in name.get("ecNumbers", [])
        if isinstance(ec, dict)
    ]
    return list(dict.fromkeys(value for value in values if value))


def extract_gene_primary(genes: list) -> list[str]:
    """Extract only primary gene names."""
    if not isinstance(genes, list):
        return []
    return [
        value
        for gene in genes
        if isinstance(gene, dict)
        if (value := (gene.get("geneName") or {}).get("value"))
    ]


def extract_gene_names(genes: list) -> list[str]:
    """Extract all names represented by UniProt's public ``gene_names`` field.

    Args:
        genes (list): Gene entries containing primary names, synonyms, ordered
            locus names, and/or ORF names.

    Returns:
        list[str]: The gene name values, or an empty list if input is not a list.

    """
    if not isinstance(genes, list):
        return []
    names: list[str] = []
    for gene in genes:
        if not isinstance(gene, dict):
            continue
        groups = [[gene.get("geneName")] if gene.get("geneName") else []]
        groups.extend(gene.get(key) or [] for key in ("synonyms", "orderedLocusNames", "orfNames"))
        for item in (item for group in groups for item in group):
            value = item.get("value") if isinstance(item, dict) else None
            if value and value not in names:
                names.append(value)
    return names


def extract_reviewed(entry_type: str) -> bool | None:
    """Return whether an entry is reviewed from UniProt's ``entryType`` label."""
    if not isinstance(entry_type, str):
        return None
    return entry_type.casefold().startswith("uniprotkb reviewed")


def extract_fragment(description: dict) -> str | None:
    """Return UniProt's fragment marker without conflating other flags."""
    if not isinstance(description, dict):
        return None
    flag = description.get("flag")
    return flag if flag in {"Fragment", "Fragments"} else None


def extract_lineage_ids(lineages: list) -> list[int]:
    """Extract taxon IDs from top-level UniProt lineage objects."""
    if not isinstance(lineages, list):
        return []
    return [
        taxon_id
        for lineage in lineages
        if isinstance(lineage, dict)
        if (taxon_id := lineage.get("taxonId")) is not None
    ]


def extract_organism_hosts(hosts: list) -> list[dict]:
    """Preserve the structured values returned for UniProt virus hosts."""
    return [dict(host) for host in hosts if isinstance(host, dict)] if isinstance(hosts, list) else []


def extract_comment_texts(comments: list, comment_type: str = "FUNCTION") -> list[str]:
    """Extract text values from comments of a requested type."""
    values: list[str] = []
    for comment in comments if isinstance(comments, list) else []:
        if not isinstance(comment, dict) or comment.get("commentType") != comment_type:
            continue
        values.extend(
            text["value"] for text in comment.get("texts", []) if isinstance(text, dict) and text.get("value")
        )
    return values


def extract_catalytic_activity(comments: list) -> list[dict]:
    """Preserve structured reactions from CATALYTIC ACTIVITY comments."""
    if not isinstance(comments, list):
        return []
    return [
        dict(comment["reaction"])
        for comment in comments
        if isinstance(comment, dict)
        and comment.get("commentType") == "CATALYTIC ACTIVITY"
        and isinstance(comment.get("reaction"), dict)
    ]


def extract_go_ids(xrefs: list) -> list[str]:
    """Extract the requested GO identifiers without renaming their semantics."""
    return extract_database_terms(xrefs, "GO")


def extract_database_terms(xrefs: list, database: str) -> list[str]:
    """Extract cross-reference IDs for a given database.

    Handles both plain cross-references and reaction cross-references nested
    under comments.

    Args:
        xrefs (list): Cross-reference entries to scan.
        database (str): The database name to match against.

    Returns:
        list[str]: The matching cross-reference IDs.

    """
    if not isinstance(xrefs, list):
        return []
    values = [
        reaction_xref.get("id")
        for xref in xrefs
        if isinstance(xref, dict)
        for reaction_xref in (xref.get("reaction") or {}).get("reactionCrossReferences", [])
        if reaction_xref.get("database") == database
    ]
    values.extend(
        xref.get("id") for xref in xrefs if isinstance(xref, dict) and xref.get("database") == database
    )
    return list(dict.fromkeys(value for value in values if value))


def extract_references(refs: list) -> list[dict]:
    """Extract literature references.

    Args:
        refs (list): Reference entries, each with a ``citation`` dict.

    Returns:
        list[dict]: References with title, authors, journal, pub_date, and pmid.

    """
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


def _format_location(feature: dict) -> str:
    """Format a feature's start/end as 'start', 'start-end', or '' when absent."""
    location = feature.get("location") or {}
    start_pos = location.get("start", {}).get("value")
    end_pos = location.get("end", {}).get("value")
    if start_pos and end_pos:
        return start_pos if start_pos == end_pos else f"{start_pos}-{end_pos}"
    return ""


# For fields ft_mutagen and ft_variant
def extract_variants(features: list) -> list[dict]:
    """Extract variant information from sequence features.

    Keeps only mutagenesis, natural variant, and disease mutation features.

    Args:
        features (list): Feature entries to scan.

    Returns:
        list[dict]: Variant records with type, id, location, sequences, and description.

    """
    VARIANTS_NAMES = {"Mutagenesis", "Natural variant", "Disease mutation"}
    extracted = []
    for feature in features if isinstance(features, list) else []:
        if feature.get("type") in VARIANTS_NAMES:
            vtype = feature.get("type")
            feature_id = feature.get("featureId", "")
            location = _format_location(feature)
            alt_seq = feature.get("alternativeSequence") or {}
            original_seq = alt_seq.get("originalSequence", "")
            alt_seqs = alt_seq.get("alternativeSequences", [])
            description = feature.get("description", "")

            extracted.append(
                {
                    "type": vtype,
                    "id": feature_id,
                    "location": location,
                    "originalSequence": original_seq,
                    "alternativeSequences": alt_seqs,
                    "description": description,
                }
            )

    return extracted


def extract_diseases(comments: list) -> list[dict]:
    """Extract structured disease comments from UniProt comment data.

    Args:
        comments (list): Comment entries to scan for DISEASE comments.

    Returns:
        list[dict]: Disease records with id, acronym, accession, description,
        cross_reference, note, and evidences.

    """
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
    """Extract active sites from features.

    Keeps only active site, binding site, and site features.

    Args:
        active_sites (list): Feature entries to scan.

    Returns:
        list[dict]: Site records with type, description, and location.

    """
    ACTIVE_SITE_TYPES = {"Active site", "Binding site", "Site"}
    extracted = []
    for feature in active_sites if isinstance(active_sites, list) else []:
        if feature.get("type") in ACTIVE_SITE_TYPES:
            stype = feature.get("type")
            description = feature.get("description", "")
            location = _format_location(feature)
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
    """Extract interaction information from comments.

    Args:
        comments (list): Comment entries to scan for INTERACTION comments.

    Returns:
        list[dict]: Interaction records with the two interactants' accessions and
        gene names, experiment count, and organism-differ flag.

    """
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
                    "accesion_b": interactor_two.get("uniProtKBAccession", ""),
                    "geneName_b": interactor_two.get("geneName", ""),
                    "numberOfExperiments": interactor.get("numberOfExperiments", 0),
                    "organismDiffer": interactor.get("organismDiffer", False),
                }
            )
    return extracted


# for fields temp_dependence, ph_dependence
def _extract_dependence(comments: list, dependence_key: str) -> list[str]:
    """Extract BIOPHYSICOCHEMICAL PROPERTIES dependence texts for ``dependence_key``.

    Args:
        comments (list): Comment entries to scan.
        dependence_key (str): The dependence field to read (e.g. ``temperatureDependence``).

    Returns:
        list[str]: The dependence text values.

    """
    extracted = []
    for c in comments if isinstance(comments, list) else []:
        if c.get("commentType", "") != "BIOPHYSICOCHEMICAL PROPERTIES":
            continue
        if dependence_key in c:
            extracted.extend(text.get("value", "") for text in c.get(dependence_key, {}).get("texts", []))
    return extracted


def extract_temperature(comments: list) -> list[str]:
    """Extract temperature dependence information from comments."""
    return _extract_dependence(comments, "temperatureDependence")


def extract_ph(comments: list) -> list[str]:
    """Extract pH dependence information from comments."""
    return _extract_dependence(comments, "phDependence")


# for fields ft_domain,ft_motif and ft_region,
def extract_domains(domains: list) -> list[dict]:
    """Extract protein domains from features.

    Keeps region, motif, domain, repeat, coiled coil, and compositional bias features.

    Args:
        domains (list): Feature entries to scan.

    Returns:
        list[dict]: Domain records with type, description, and location.

    """
    DOMAINS_TYPES = {"Region", "Motif", "Domain", "Repeat", "Coiled coil", "Compositional bias"}
    extracted = []
    for domain in domains if isinstance(domains, list) else []:
        if domain.get("type") in DOMAINS_TYPES:
            dtype = domain.get("type")
            description = domain.get("description", "")
            location = _format_location(domain)
            extracted.append(
                {
                    "type": dtype,
                    "description": description,
                    "location": location,
                }
            )

    return extracted


def extract_keywords(keywords: list) -> list[str]:
    """Extract keywords.

    Args:
        keywords (list): Keyword entries, each with a ``name`` field.

    Returns:
        list[str]: The keyword names, or an empty list if input is not a list.

    """
    return [kw.get("name", "") for kw in keywords] if isinstance(keywords, list) else []
