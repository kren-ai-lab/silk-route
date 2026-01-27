from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from bioseq_dl.constants.uniprot import XREF_MAPPING


@dataclass(frozen=True)
class MultiModeFieldConfig:
    """
    Configuration for a multi-mode field expansion.

    Attributes:
        uniprot_field: Target UniProt field prefix (e.g., 'database', 'keyword', 'go').
        value_map: Optional mapping from user tokens to UniProt tokens (e.g., 'alphafold' -> 'alphafolddb').
        supports_range: If True, values like '25-37' will be converted to '[25 TO 37]'.
        quote_phrases: If True, values containing whitespace will be quoted in the output.
        resolver_kind: Optional resolver type. Supported:
            - None: no special resolution
            - 'go_name_to_id': resolve GO names to GO IDs using interpreter config.
    """
    uniprot_field: str
    value_map: Dict[str, str]
    supports_range: bool
    quote_phrases: bool
    resolver_kind: Optional[str]


@dataclass(frozen=True)
class UniProtInterpreterConfig:
    """
    Top-level interpreter configuration.

    Attributes:
        fields: Mapping from friendly field name (DSL) to MultiModeFieldConfig.
        go_name_to_id: Mapping from GO term names (lowercased) to GO IDs (7 digits).
        field_aliases: Simple prefix aliases, e.g. 'taxon:' -> 'taxonomy_id:'.
        temperature_uniprot_field: UniProt field used for temperature dependence.
        ignored_fields: Field prefixes to strip from interpretation (e.g., 'ic50').
    """
    fields: Dict[str, MultiModeFieldConfig]
    go_name_to_id: Dict[str, str]
    field_aliases: Dict[str, str]
    temperature_uniprot_field: str
    ph_uniprot_field: str
    ignored_fields: List[str]


class UniProtQueryInterpreter:
    """
    Translate a user-friendly multi-mode DSL into UniProt query syntax.

    Supported patterns:
        <field>_<mode>:<items>
        <field>:<items>  (defaults to _any)
    Where:
        field: registered in config.fields
        mode: any | all | not
        items: comma-separated tokens, optionally quoted (double quotes)

    Examples:
        databases_any:alphafold,biogrid
        keywords_all:membrane,"signal peptide"
        go_any:"DNA repair"
        temperature_any:25-37

    Notes:
        - Boolean operators AND/OR/NOT and parentheses in the user's query are preserved.
        - The interpreter performs macro expansions only, without fully parsing the boolean grammar.
    """

    def __init__(self, config: UniProtInterpreterConfig) -> None:
        self.config = config

    def interpret(self, query: str) -> str:
        """
        Interpret and expand a user-friendly query into a UniProt query string.

        Args:
            query: Raw user query.

        Returns:
            UniProt-compatible query string.
        """
        text = query.strip()
        text = self._remove_ignored_fields(text)
        text = self._expand_all_multimode_fields(text)
        text = self._expand_temperature_multimode(text)
        text = self._expand_ph_multimode(text)
        text = self._expand_field_aliases(text)
        text = self._cleanup_whitespace(text)
        return text

    def _expand_all_multimode_fields(self, text: str) -> str:
        """
        Expand all registered <field>_<mode>:... macros.
        """
        out = text
        for field_name, field_cfg in self.config.fields.items():
            out = self._expand_one_multimode_field(out, field_name, field_cfg)
        return out

    def _expand_one_multimode_field(self, text: str, field_name: str, cfg: MultiModeFieldConfig) -> str:
        """
        Expand a single registered field for any/all/not modes. A bare field behaves like _any.
        """
        pattern = re.compile(
            rf"\b{re.escape(field_name)}(?:_?(any|all|not))?:"  # field + optional mode
            r"("                                          # start items capture
            r"(?:\"[^\"]+\"|'[^']+')(?:\s*,\s*(?:\"[^\"]+\"|'[^']'))*"            # quoted csv (single or double)
            r"|"
            r"[^\s()]+(?:\s*,\s*[^\s()]+)*"                # unquoted csv (no spaces)
            r")"
        )

        matches = list(pattern.finditer(text))
        if not matches:
            return text

        out = text
        for m in reversed(matches):
            mode = (m.group(1) or "").strip().lower()
            # If the user omitted the mode for `keywords` assume _all (AND behavior)
            if mode == "" and field_name == "keywords":
                mode = "all"

            raw_items = m.group(2).strip()
            items = self._parse_csv_items(raw_items)

            clauses = self._build_field_clauses(items, cfg)
            replacement = self._combine_clauses_by_mode(clauses, mode)

            out = out[:m.start()] + replacement + out[m.end():]

        return out

    def _build_field_clauses(self, items: List[str], cfg: MultiModeFieldConfig) -> List[str]:
        """
        Build UniProt field clauses for each item.

        Special cases:
        - For 'go' fields: if the token is not a numeric GO ID, try mapping via config.go_name_to_id.
        - For 'keyword' fields: try mapping via keyword_map in the build_default_uniprot_interpreter config.
        """
        clauses: List[str] = []
        for item in items:
            resolved_value = self._resolve_item_value(item, cfg)
            if resolved_value is None or resolved_value == "":
                continue

            # Additional mapping for 'go' if resolver not used or token is a name
            if cfg.uniprot_field == "go":
                # if looks like numeric go id (7 digits), keep; else try mapping
                if not self._looks_like_go_id(resolved_value):
                    mapped = self.config.go_name_to_id.get(resolved_value.lower())
                    if mapped:
                        resolved_value = mapped

            if cfg.uniprot_field == "keyword":
                # try to map keyword names (case-insensitive) via the keyword_map in fields
                # note: cfg.value_map may contain the keyword_map; prefer that
                key = resolved_value.lower()
                mapped_kw = cfg.value_map.get(key)
                if mapped_kw:
                    resolved_value = mapped_kw

            formatted_value = self._format_value_for_field(resolved_value, cfg)
            clauses.append(f"{cfg.uniprot_field}:{formatted_value}")

        return clauses

    def _resolve_item_value(self, item: str, cfg: MultiModeFieldConfig) -> Optional[str]:
        """
        Resolve one item using mapping and optional resolver rules.
        """
        raw = item.strip()
        if raw == "":
            return None

        # For database queries, anything after the first underscore is a method hint
        # (e.g., brenda_getOptimumTemperature) that should not influence the UniProt term.
        base_raw = raw.split("_", 1)[0] if cfg.uniprot_field == "database" else raw

        key = base_raw.lower()
        mapped = cfg.value_map.get(key, base_raw)

        if cfg.resolver_kind == "go_name_to_id":
            if self._looks_like_go_id(mapped):
                return mapped
            go_id = self.config.go_name_to_id.get(mapped.lower())
            if (go_id):
                return go_id
            return mapped
        # Add other resolver kinds here as needed.
        # Example:
        # elif cfg.resolver_kind == "some_other_kind":
        #     ...

        return mapped

    def _format_value_for_field(self, value: str, cfg: MultiModeFieldConfig) -> str:
        """
        Format value for UniProt query field, applying range and quoting if needed.
        """
        if cfg.supports_range:
            low, high = self._parse_numeric_range(value)
            if low is not None and high is not None:
                return f"{low}-{high}"
                #return f"[{low} TO {high}]"

        if cfg.quote_phrases and self._needs_quotes(value):
            return f"\"{value}\""

        return value

    def _combine_clauses_by_mode(self, clauses: List[str], mode: str) -> str:
        """
        Combine clauses according to mode.
        Normally we use {field}_any -> OR, _all -> AND, _not -> NOT (OR group).
        """
        if not clauses:
            return ""

        if mode == "any":
            return "(" + " OR ".join(clauses) + ")"
        if mode == "all":
            return "(" + " AND ".join(clauses) + ")"
        if mode == "not":
            # NOT of OR-group is usually the most intuitive for users:
            # field_not:a,b -> NOT (field:a OR field:b)
            return "NOT (" + " OR ".join(clauses) + ")"
        if mode == "":
            return "(" + " OR ".join(clauses) + ")"

        return "(" + " OR ".join(clauses) + ")"

    def _expand_temperature_multimode(self, text: str) -> str:
        """
        Expand temperature_<mode>:... into the configured UniProt temperature field.

        Supported:
            temperature_any:27
            temperature_any:25-37
            temperature_not:25-37
        """
        field_name = "temperature"
        cfg = MultiModeFieldConfig(
            uniprot_field=self.config.temperature_uniprot_field,
            value_map={},
            supports_range=True,
            quote_phrases=False,
            resolver_kind=None,
        )
        return self._expand_one_multimode_field(text, field_name, cfg)
    
    def _expand_ph_multimode(self, text: str) -> str:
        """
        Expand pH_<mode>:... into the configured UniProt pH field.

        Supported:
            pH_any:7.0
            pH_any:6.5-8.0
            pH_not:6.5-8.0
        """
        field_name = "pH"
        cfg = MultiModeFieldConfig(
            uniprot_field="cc_bpcp_ph_dependence",
            value_map={},
            supports_range=True,
            quote_phrases=False,
            resolver_kind=None,
        )
        return self._expand_one_multimode_field(text, field_name, cfg)

    def _expand_field_aliases(self, text: str) -> str:
        """
        Replace simple prefix aliases like 'taxon:' -> 'taxonomy_id:'.
        """
        out = text
        for friendly, native in self.config.field_aliases.items():
            pattern = re.compile(rf"\b{re.escape(friendly)}:")
            out = pattern.sub(f"{native}:", out)
        return out

    def _remove_ignored_fields(self, text: str) -> str:
        """
        Remove ignored field macros from the query so they can be handled elsewhere.
        """
        out = text
        for field_name in self.config.ignored_fields:
            pattern = re.compile(
                rf"(\s*(?:AND|OR|NOT)\s+)?"                 # optional leading boolean
                rf"\b{re.escape(field_name)}(?:_?(any|all|not))?:"
                r"("                                       # start items capture
                r"(?:\"[^\"]+\"|'[^']+')(?:\s*,\s*(?:\"[^\"]+\"|'[^']'))*"        # quoted csv (single or double)
                r"|"
                r"[^\s()]+(?:\s*,\s*[^\s()]+)*"            # unquoted csv (no spaces)
                r")",
                flags=re.IGNORECASE,
            )
            out = pattern.sub(" ", out)

        out = re.sub(r"\b(AND|OR|NOT)\s*(?=\b(AND|OR|NOT)\b)", " ", out, flags=re.IGNORECASE)
        out = re.sub(r"^\s*(AND|OR|NOT)\b\s*", "", out, flags=re.IGNORECASE)
        out = re.sub(r"\b(AND|OR|NOT)\s*$", "", out, flags=re.IGNORECASE)
        return out

    def _parse_csv_items(self, raw_items: str) -> List[str]:
        """
        Parse comma-separated items, supporting quoted phrases with either single or double quotes.

        Accept also the case where the entire CSV is wrapped in a single pair of quotes
        (e.g. 'a,b,c' or "a,b,c") - in that case split the inner string on commas.

        Examples:
            a,b,c
            "DNA repair","protein folding"
            'response to stimulus',"signal peptide"
            'atp binding,antiviral protein'  -> ['atp binding','antiviral protein']
        """
        raw = raw_items.strip()
        # Special-case: entire CSV wrapped in a single pair of quotes -> split inner on commas
        if len(raw) >= 2 and ((raw[0] == '"' and raw[-1] == '"') or (raw[0] == "'" and raw[-1] == "'")):
            inner = raw[1:-1]
            # split on commas and strip whitespace
            parts = [p.strip() for p in inner.split(",") if p.strip() != ""]
            return parts

        items: List[str] = []
        token = ""
        in_quotes = False
        quote_char: Optional[str] = None

        i = 0
        while i < len(raw_items):
            ch = raw_items[i]
            if ch in ('"', "'"):
                if not in_quotes:
                    in_quotes = True
                    quote_char = ch
                elif quote_char == ch:
                    # closing quote
                    in_quotes = False
                    quote_char = None
                else:
                    # different quote char inside quoted string -> treat literally
                    token += ch
                i += 1
                continue
            if ch == "," and not in_quotes:
                item = token.strip()
                # strip surrounding quotes if any (defensive)
                if len(item) >= 2 and ((item[0] == '"' and item[-1] == '"') or (item[0] == '\'' and item[-1] == '\'')):
                    item = item[1:-1]
                items.append(item)
                token = ""
                i += 1
                continue
            token += ch
            i += 1

        if token.strip() != "":
            item = token.strip()
            if len(item) >= 2 and ((item[0] == '"' and item[-1] == '"' or (item[0] == '\'' and item[-1] == '\''))):
                item = item[1:-1]
            items.append(item)

        return items

    def _parse_numeric_range(self, value: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse 'low-high' ranges and return (low, high) strings if valid.
        """
        if "-" not in value:
            return None, None
        parts = value.split("-", 1)
        low = parts[0].strip()
        high = parts[1].strip()
        if low == "" or high == "":
            return None, None
        if not self._is_number(low) or not self._is_number(high):
            return None, None
        return low, high

    def _looks_like_go_id(self, text: str) -> bool:
        """
        Check if a string matches a 7-digit GO numeric ID.
        """
        return bool(re.fullmatch(r"\d{7}", text.strip()))

    def _needs_quotes(self, value: str) -> bool:
        """
        Decide if a value should be wrapped in double quotes.
        """
        return bool(re.search(r"\s", value))

    def _is_number(self, text: str) -> bool:
        """
        Return True if text can be parsed as float.
        """
        try:
            float(text)
            return True
        except ValueError:
            return False

    def _cleanup_whitespace(self, text: str) -> str:
        """
        Normalize whitespace.
        """
        return re.sub(r"\s+", " ", text).strip()

    def extract_databases(self, query: str) -> str:
        """
        Extract database tokens from a query (databases:<items>) and return them comma-separated.

        Supports method suffixes (e.g., brenda_getOptimumTemperature). If no suffix is
        provided, '_all' is assumed to signal all available methods.
        """
        cfg = self.config.fields.get("databases")
        if not cfg:
            return ""

        db_pattern = re.compile(
            r"\bdatabases(?:_?(any|all|not))?:"
            r"("                                          # start items capture
            r"\"[^\"]+\"(?:\s*,\s*\"[^\"]+\")*"            # quoted csv
            r"|"
            r"[^\s()]+(?:\s*,\s*[^\s()]+)*"                # unquoted csv (no spaces)
            r")"
        )
        temperature_pattern = re.compile(r"\btemperature(?:_?(any|all|not))?:")

        tokens: List[str] = []
        for match in db_pattern.finditer(query):
            raw_items = match.group(2).strip()
            items = self._parse_csv_items(raw_items)
            for item in items:
                base, method = self._split_db_token(item)
                resolved = self._resolve_item_value(base, cfg)
                # Special-case: prefer the original 'alphafold' token instead of the mapped 'alphafolddb'
                if base.strip().lower() == "alphafold":
                    token_base = "alphafold"
                else:
                    token_base = resolved
                if token_base:
                    tokens.append(f"{token_base}_{method}")

        # If a temperature filter is present, restrict/augment BRENDA calls to temperature-only methods.
        if temperature_pattern.search(query):
            allowed_methods = {
                "getTemperatureOptimum",
                "getTemperatureStability",
                "getTemperatureRange",
            }
            brenda_resolved = self._resolve_item_value("brenda", cfg)

            filtered: List[str] = []
            seen = set()
            for t in tokens:
                base, method = self._split_db_token(t)
                if brenda_resolved and base == brenda_resolved:
                    if method not in allowed_methods:
                        continue
                if t not in seen:
                    filtered.append(t)
                    seen.add(t)

            # Ensure required BRENDA temperature methods are present
            if brenda_resolved:
                for method in allowed_methods:
                    token = f"{brenda_resolved}_{method}"
                    if token not in seen:
                        filtered.append(token)
                        seen.add(token)

            tokens = filtered

        return ",".join(tokens)
    
    def extract_additional_searches(self, query: str) -> List[dict]:
        """
        Sometimes, a query may imply additional searches beyond UniProt.
        For example, searching IC50 values requires doing a ChEMBL search first
        and then linking back to UniProt by searching Chembl IDs obtained.

        This method extracts such implied searches from the query, returning
        them as a dict with keys indicating the following:
            - 'query': The additional query dict to perform. It's body depends on the search type.
            - 'database': The database to search (e.g., 'chembl').
            - 'method': The method to use for searching (e.g., 'activity_search').
            - 'option': Any additional options needed for the search.
        
        For example, for IC50 searches, you may define the following query pattern:
            ic50:10-50 -> implies searching ChEMBL for activities with IC50 < 50 and > 10.
            ic50:5000 -> implies searching ChEMBL for activities with IC50 = 5000.
            ic50:>1000 -> implies searching ChEMBL for activities with IC50 > 1000.
        Returns:
            {
                'database': 'chembl',
                'method': 'activity_search',
                'query': "ic50>10 AND ic50<50",
                'option': None
            }
        """
        ic50_pattern = re.compile(
            r"\bic50(?:_?(any|all|not))?:"
            r"("                                          # start items capture
            r"\"[^\"]+\"(?:\s*,\s*\"[^\"]+\")*"            # quoted csv
            r"|"
            r"[^\s()]+(?:\s*,\s*[^\s()]+)*"                # unquoted csv (no spaces)
            r")"
        )
        
        additional_searches: List[dict] = []
        # IC50 handling: ranges, exact values, greater-than and less-than prefixes.
        for match in ic50_pattern.finditer(query):
            raw_items = match.group(2).strip()
            items = self._parse_csv_items(raw_items)
            for item in items:
                base, method = self._split_db_token(item)
                token = base.strip()

                # 1) Range: "low-high"
                low, high = self._parse_numeric_range(token)
                if low is not None and high is not None:
                    ic50_query = f"ic50>{low} AND ic50<{high}"
                    additional_searches.append({
                    'database': 'chembl',
                    'method': 'activity-search',
                    'query': ic50_query,
                    'option': None,
                    'params': {}
                    })
                    continue

                # 2) Comparison: >1000, <500, >=100, <=200
                m_comp = re.fullmatch(r"(>=|<=|>|<)\s*(\d+(?:\.\d+)?)", token)
                if m_comp:
                    op = m_comp.group(1)
                    num = m_comp.group(2)
                    ic50_query = f"ic50{op}{num}"
                    additional_searches.append({
                    'database': 'chembl',
                    'method': 'activity-search',
                    'query': ic50_query,
                    'option': None,
                    'params': {}
                    })
                    continue

                # 3) Exact numeric value: "5000" -> equality
                if self._is_number(token):
                    # Use '=' for exact match
                    ic50_query = f"ic50={token}"
                    additional_searches.append({
                    'database': 'chembl',
                    'method': 'activity-search',
                    'query': ic50_query,
                    'option': None,
                    'params': {}
                    })
                    continue

                # Otherwise ignore non-numeric / unrecognized tokens for IC50
        return additional_searches


    def _split_db_token(self, token: str) -> Tuple[str, str]:
        """
        Split a database token into (base, method). Defaults method to 'all'.
        """
        if "_" in token:
            base, method = token.split("_", 1)
            method = method or "all"
        else:
            base, method = token, "all"
        return base.strip(), method.strip()


def build_default_uniprot_interpreter() -> UniProtQueryInterpreter:
    """
    Build a default UniProtQueryInterpreter with multi-mode fields enabled.
    """

    db_map = {db_name: db_name for _, (_, db_name) in XREF_MAPPING.items()}
    db_map["alphafold"] = "alphafolddb" # Special case

    # Small starter dictionary; extend over time from your users' queries.
    go_name_to_id = {
        "dna repair": "0006281",
        "protein folding": "0006457",
        "response to heat": "0009408",
        "translation": "0006412",
        "proteolysis": "0006508",
        "antioxidant activity": "0016209",
        "hydrocarbon catabolic process": "0120252",
        "peptidase activity": "0008233",
        "response to stimulus": "0050896",
    }

    keyword_map = {
        "atp binding": "KW-0067",
        "metal-binding": "KW-0479",
        "antiviral defense": "KW-0051",
        "antiviral protein": "KW-0930"
    }

    function_map = {
        "oxidoreductase": "1",
        "transferase": "2",
        "hydrolase": "3",
        "lyase": "4",
        "isomerase": "5",
        "ligase": "6",
        "translocase": "7"
    }

    fields = {
        # Multi-mode databases
        "databases": MultiModeFieldConfig(
            uniprot_field="database",
            value_map=db_map,
            supports_range=False,
            quote_phrases=False,
            resolver_kind=None,
        ),
        # Multi-mode keywords
        "keywords": MultiModeFieldConfig(
            uniprot_field="keyword",
            value_map=keyword_map,
            supports_range=False,
            quote_phrases=True,
            resolver_kind=None,
        ),
        # Multi-mode GO (supports resolving known names -> IDs)
        "go": MultiModeFieldConfig(
            uniprot_field="go",
            value_map={},
            supports_range=False,
            quote_phrases=False,
            resolver_kind="go_name_to_id",
        ),
        # Example: taxa / organisms (you can keep growing these)
        "taxa": MultiModeFieldConfig(
            uniprot_field="taxonomy_id",
            value_map={},
            supports_range=False,
            quote_phrases=False,
            resolver_kind=None,
        ),
        "organisms": MultiModeFieldConfig(
            uniprot_field="organism",
            value_map={},
            supports_range=False,
            quote_phrases=True,
            resolver_kind=None,
        ),
        "ec": MultiModeFieldConfig(
            uniprot_field="ec",
            value_map=function_map,
            supports_range=False,
            quote_phrases=False,
            resolver_kind=None,
        ),
    }

    field_aliases = {
        "taxon": "taxonomy_id",
        "taxid": "taxonomy_id",
        "org": "organism",
        "db": "database",
        "xref": "database",
    }

    config = UniProtInterpreterConfig(
        fields=fields,
        go_name_to_id=go_name_to_id,
        field_aliases=field_aliases,
        temperature_uniprot_field="cc_bpcp_temp_dependence",
        ph_uniprot_field="cc_bpcp_ph_dependence",
        ignored_fields=["ic50"],
    )

    return UniProtQueryInterpreter(config=config)
