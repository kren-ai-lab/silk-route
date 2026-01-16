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
    """
    fields: Dict[str, MultiModeFieldConfig]
    go_name_to_id: Dict[str, str]
    field_aliases: Dict[str, str]
    temperature_uniprot_field: str


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
        text = self._expand_all_multimode_fields(text)
        text = self._expand_temperature_multimode(text)
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
            r"\"[^\"]+\"(?:\s*,\s*\"[^\"]+\")*"            # quoted csv
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
            raw_items = m.group(2).strip()
            items = self._parse_csv_items(raw_items)

            clauses = self._build_field_clauses(items, cfg)
            replacement = self._combine_clauses_by_mode(clauses, mode)

            out = out[:m.start()] + replacement + out[m.end():]

        return out

    def _build_field_clauses(self, items: List[str], cfg: MultiModeFieldConfig) -> List[str]:
        """
        Build UniProt field clauses for each item.
        """
        clauses: List[str] = []
        for item in items:
            resolved_value = self._resolve_item_value(item, cfg)
            if resolved_value is None or resolved_value == "":
                continue

            formatted_value = self._format_value_for_field(resolved_value, cfg)
            clauses.append(f"({cfg.uniprot_field}:{formatted_value})")

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
            if go_id:
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
                return f"[{low} TO {high}]"

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

    def _expand_field_aliases(self, text: str) -> str:
        """
        Replace simple prefix aliases like 'taxon:' -> 'taxonomy_id:'.
        """
        out = text
        for friendly, native in self.config.field_aliases.items():
            pattern = re.compile(rf"\b{re.escape(friendly)}:")
            out = pattern.sub(f"{native}:", out)
        return out

    def _parse_csv_items(self, raw_items: str) -> List[str]:
        """
        Parse comma-separated items, supporting quoted phrases.

        Examples:
            a,b,c
            "DNA repair","protein folding"
            membrane,"signal peptide"
        """
        items: List[str] = []
        token = ""
        in_quotes = False

        i = 0
        while i < len(raw_items):
            ch = raw_items[i]
            if ch == '"':
                in_quotes = not in_quotes
                i += 1
                continue
            if ch == "," and not in_quotes:
                items.append(token.strip())
                token = ""
                i += 1
                continue
            token += ch
            i += 1

        if token.strip() != "":
            items.append(token.strip())

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
                if resolved:
                    tokens.append(f"{resolved}_{method}")

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

    # Small starter dictionary; extend over time from your users' queries.
    go_name_to_id = {
        "dna repair": "0006281",
        "protein folding": "0006457",
        "response to heat": "0009408",
        "translation": "0006412",
        "proteolysis": "0006508",
    }

    keyword_map = {
        "membrane": "Membrane",
        "secreted": "Secreted",
        "transmembrane": "Transmembrane",
        "signal peptide": "Signal peptide",
        "chaperone": "Chaperone",
        "enzyme": "Enzyme",
        "stress response": "Stress response",
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
    )
    return UniProtQueryInterpreter(config=config)
