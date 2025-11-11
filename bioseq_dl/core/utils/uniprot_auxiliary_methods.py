from typing import List, Dict, Any
import re


# Specific extraction functions
def extract_simple(value: Any) -> Any:
    """Extracts a simple value from the data"""
    return value

def extract_ec_numbers(ec_data: List) -> List[str]:
    """Extracts EC numbers"""
    return [ec['value'] for ec in ec_data] if isinstance(ec_data, list) else []

def extract_gene_names(gene_names: List) -> List[str]:
    """Extracts gene names"""
    return [gene['geneName']['value'] for gene in gene_names] if isinstance(gene_names, list) else []

def extract_database_terms(xrefs: List, database: str) -> List[str]:
    """Extracts database terms"""
    # Comment solution
    if all("reaction" in xref for xref in xrefs if isinstance(xrefs, list)):
        ids = []
        for xref in xrefs:
            for reaction_xref in xref.get("reaction", {}).get("reactionCrossReferences", []):
                if reaction_xref.get("database") == database:
                    ids.append(reaction_xref.get("id"))
        return ids
    # Normal solution
    else:
        return [
            x['id'] 
            for x in xrefs 
            if isinstance(x, dict) and x.get('database') == database
        ]
        
def extract_references(refs: List) -> List[Dict]:
    """Extracts references"""
    extracted = []
    for ref in refs if isinstance(refs, list) else []:
        citation = ref.get('citation', {})
        extracted.append({
            'title': citation.get('title'),
            'authors': citation.get('authors', []),
            'journal': citation.get('journal'),
            'pub_date': citation.get('publicationDate'),
            'pmid': next((x['id'] for x in citation.get('citationCrossReferences', []) 
                        if x.get('database') == 'PubMed'), None)
        })
    return extracted

def extract_features(features: List) -> List[Dict]:
    """Extracts protein features"""
    return [{
        'type': f.get('type'),
        'description': f.get('description', ''),
        'location': f.get('location', {})
    } for f in features if isinstance(features, list)]


# For fields ft_mutagen and ft_variant
def extract_variants(features: List) -> List[Dict]:
    """Extracts variant information"""
    VARIANTS_NAMES = {'Mutagenesis', 'Natural variant', 'Disease mutation'}
    extracted = []
    for feature in features if isinstance(features, list) else []:
        if feature.get('type') in VARIANTS_NAMES:
            vtype = feature.get('type')
            id = feature.get('featureId', '')
            variant_start_pos = feature.get('location', '').get('start', '').get('value')
            variant_end_pos = feature.get('location', '').get('end', '').get('value')
            if variant_start_pos and variant_end_pos:
                if variant_start_pos == variant_end_pos:
                    location = variant_start_pos
                else:
                    location = f"{variant_start_pos}-{variant_end_pos}"
            else:
                location = ''
            original_seq = feature.get('alternativeSequence', '').get('originalSequence', '')
            alt_seqs = feature.get('alternativeSequence', []).get('alternativeSequences', [])
            description = feature.get('description', '')
            
            extracted.append({
                'type': vtype,
                'id': id,
                'location': location,
                'originalSequence': original_seq,
                'alternativeSequences': alt_seqs,
                'description': description,
            })

    return extracted

# Nombres diseases: cc_disease PENDING
def extract_diseases(diseases: List) -> List[Dict]:
    pass

# for fields ft_act_site, ft_binding and ft_site,
def extract_active_sites(active_sites: List) -> List[Dict]:
    """Extracts active sites from features"""
    ACTIVE_SITE_TYPES = {'Active site', 'Binding site', 'Site'}
    extracted = []
    for feature in active_sites if isinstance(active_sites, list) else []:
        if feature.get('type') in ACTIVE_SITE_TYPES:
            stype = feature.get('type')
            description = feature.get('description', '')
            site_start_pos = feature.get('location', '').get('start', '').get('value')
            site_end_pos = feature.get('location', '').get('end', '').get('value')
            if site_start_pos and site_end_pos:
                if site_start_pos == site_end_pos:
                    location = site_start_pos
                else:
                    location = f"{site_start_pos}-{site_end_pos}"
            else:
                location = ''
            extracted.append({
                'type': stype,
                'description': description,
                'location': location,
            })

    return extracted

# for fields ft_domain,ft_motif and ft_region,
def extract_domains(domains: List) -> List[Dict]:
    """Extracts protein domains from features"""
    DOMAINS_TYPES = {'Region', 'Motif', 'Domain', 'Repeat', 'Coiled coil', 'Compositional bias'}
    extracted = []
    for domain in domains if isinstance(domains, list) else []:
        if domain.get('type') in DOMAINS_TYPES:
            dtype = domain.get('type')
            description = domain.get('description', '')
            domain_start_pos = domain.get('location', '').get('start', '').get('value')
            domain_end_pos = domain.get('location', '').get('end', '').get('value')
            if domain_start_pos and domain_end_pos:
                if domain_start_pos == domain_end_pos:
                    location = domain_start_pos
                else:
                    location = f"{domain_start_pos}-{domain_end_pos}"
            else:
                location = ''
            extracted.append({
                'type': dtype,
                'description': description,
                'location': location,
            })

            
    return extracted

def extract_keywords(keywords: List) -> List[str]:
    """Extracts keywords"""
    return [kw.get('name', '') for kw in keywords if isinstance(keywords, list)]
