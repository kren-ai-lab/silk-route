"""Query interpretation and transformation for UniProt and ChEMBL."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import partial
from typing import Any

from bioseq_dl.core.workflow.chembl_query_parser import parse_chembl_query_builder_string
from bioseq_dl.core.workflow.query_field_catalog import get_uniprot_query_field_catalog

QUOTED_CSV_VALUE_PATTERN = re.compile(r"(?:'[^']*'|\"[^\"]*\"|[^,]+)")
MIN_QUOTED_VALUE_LENGTH = 2


def strip_surrounding_quotes(value: str) -> str:
    """Strip one matching pair of surrounding single or double quotes."""
    stripped = value.strip()
    if len(stripped) >= MIN_QUOTED_VALUE_LENGTH and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def split_quoted_csv_values(value: str) -> list[str]:
    """Split comma-separated values while preserving commas inside quotes."""
    return [item.strip() for item in QUOTED_CSV_VALUE_PATTERN.findall(value) if item and item.strip()]


def compact_parentheses_spacing(value: str) -> str:
    """Remove spacing artifacts immediately inside query parentheses."""
    compacted = re.sub(r"\(\s+", "(", value)
    return re.sub(r"\s+\)", ")", compacted)


def _remove_unknown_field_match(match: re.Match, allowed_fields: set[str]) -> str:
    """Replace a fielded match with a space unless its field is in the allowed set.

    Args:
        match (re.Match): A match whose group 2 is the field name.
        allowed_fields (set[str]): Field names that should be preserved.

    Returns:
        str: A single space if the field is not allowed, otherwise the original match text.

    """
    field_name = match.group(2)
    if field_name not in allowed_fields:
        return " "
    return match.group(0)


@dataclass(frozen=True)
class MultiModeFieldConfig:
    """Generic configuration for a multimode field.

    Attributes:
        field (str): The target/native field name used by the downstream service.
        value_map (dict[str, str]): Mapping from user tokens to native tokens.
        supports_range (bool): Whether the field accepts numeric ranges (low-high).
        resolver_kind (str | None): Optional resolver hint for custom resolution logic in subclasses.

    """

    field: str
    value_map: dict[str, str]
    supports_range: bool
    resolver_kind: str | None


@dataclass
class QueryInterpreterConfig:
    """Generic interpreter configuration shared by concrete interpreters.

    Attributes:
        fields (dict[str, MultiModeFieldConfig]): Mapping of friendly field name to its config.
        field_aliases (dict[str, str]): Simple prefix aliases (e.g. 'taxon' -> 'taxonomy_id').
        ignored_fields (list[str]): Field prefixes that should be stripped by the base
            interpreter because they may imply additional searches.
        extras (dict[str, Any] | None): Place to keep implementation specific extra config values.

    """

    fields: dict[str, MultiModeFieldConfig]
    field_aliases: dict[str, str]
    ignored_fields: list[str]
    extras: dict[str, Any] | None


class BaseQueryInterpreter:
    """Base class for query interpreters.

    This class provides a set of small, reusable helpers that concrete
    interpreters (e.g. UniProt, ChEMBL) can use when implementing their
    own `interpret` method. The base does not make assumptions about the
    final query language; it only provides parsing and extraction utilities.
    """

    def __init__(self, config: Any) -> None:
        """Store the interpreter configuration object.

        Args:
            config (Any): A configuration object exposing ``fields``, ``field_aliases``,
                ``ignored_fields`` and ``extras`` (typically a ``QueryInterpreterConfig``).

        """
        self.config = config

    def interpret(self, query: str) -> str:
        """Interpret a query string into the target data source's query language.

        Expand field aliases, strip ignored/unknown fields, normalize whitespace,
        then resolve each ``field:value`` item via the subclass ``_resolve_item``.

        Args:
            query (str): The raw user query to interpret.

        Returns:
            str: The query rewritten in the target query language.

        """
        processed_query = self._expand_field_aliases(query)
        if self.config.extras and self.config.extras.get("ignore_all_fields", False):
            processed_query = self._remove_all_fields(processed_query)
        else:
            processed_query = self._remove_ignored_fields(processed_query)
        processed_query = self._cleanup_whitespace(processed_query)
        return self._resolve_query_items(processed_query)

    def _resolve_item(self, prefix: str, value: str, cfg: MultiModeFieldConfig) -> tuple[str, str]:
        """Resolve a single ``prefix:value`` item according to its field config.

        Abstract hook implemented by concrete interpreters.

        Args:
            prefix (str): The (already formatted) field prefix.
            value (str): The raw value to resolve.
            cfg (MultiModeFieldConfig): Configuration for the field being resolved.

        Returns:
            tuple[str, str]: The resolved ``(prefix, value)`` pair.

        Raises:
            NotImplementedError: Always; subclasses must override this method.

        """
        msg = "Subclasses must implement this method."
        raise NotImplementedError(msg)

    # --- Generic helpers useful across interpreters ---
    def _resolve_query_items(self, text: str) -> str:
        """Resolve each item in the query string against the field configurations.

        Tokenizes the query, expands multimode tokens (commas / ``_any``/``_all``/``_not``)
        into boolean expressions, then formats and resolves every ``field:value`` token while
        passing boolean operators and parentheses through unchanged.

        Args:
            text (str): The preprocessed query string.

        Returns:
            str: The space-joined, fully resolved query.

        """
        if not text:
            return ""

        # 1) Initial tokenize to separate top-level boolean operators
        tokens = self._tokenize_query(text)

        # 2) Expand multimode tokens (commas / _any/_all/_not) into full expressions
        expanded_tokens: list[str] = []
        for tok in tokens:
            expanded = self._split_modes(tok)
            # If expansion produced something different, re-tokenize it so boolean ops are preserved
            if expanded != tok:
                expanded_tokens.extend(self._tokenize_query(expanded))
            else:
                expanded_tokens.append(tok)

        # 3) Resolve each final token (field:value) according to config
        resolved_final: list[str] = []
        for item in expanded_tokens:
            if ":" not in item or item.upper() in {"AND", "OR", "NOT", "(", ")"}:
                # operator or parenthesized expression without colon
                resolved_final.append(item)
                continue
            prefix, value = item.split(":", 1)
            field_cfg = self.config.fields.get(prefix, None)
            if not field_cfg:
                resolved_final.append(item)
                continue

            prefix = self._format_prefix(prefix, field_cfg)
            value = strip_surrounding_quotes(value)
            formatted_value = self._format_value_for_field(value, field_cfg)
            if formatted_value:
                value = formatted_value

            resolved_prefix, resolved_value = self._resolve_item(prefix, value, field_cfg)
            if resolved_prefix == "":
                resolved_final.append(f"{resolved_value}")
            else:
                resolved_final.append(f"{resolved_prefix}:{resolved_value}")

        return compact_parentheses_spacing(" ".join(resolved_final))

    def _format_prefix(self, _prefix: str, cfg: MultiModeFieldConfig) -> str:
        """Return the native field name for a prefix from its field configuration.

        Args:
            _prefix (str): The original (friendly) prefix; ignored.
            cfg (MultiModeFieldConfig): Configuration providing the native field name.

        Returns:
            str: The native field name.

        """
        return cfg.field

    def _format_value_for_field(self, value: str, cfg: MultiModeFieldConfig) -> str:
        """Format a value for a field, normalizing numeric ranges when supported.

        Args:
            value (str): The raw value.
            cfg (MultiModeFieldConfig): Configuration for the field.

        Returns:
            str: A ``low-high`` range when the field supports ranges and the value parses
                as one; otherwise the original value.

        """
        if cfg.supports_range:
            low, high = self._parse_numeric_range(value)
            if low is not None and high is not None:
                return f"{low}-{high}"
        return value

    def _cleanup_whitespace(self, text: str) -> str:
        """Normalize whitespace to a single space and trim edges."""
        return re.sub(r"\s+", " ", text or "").strip()

    def _split_modes(self, text: str) -> str:
        """Expand mode suffixes (_any/_all/_not) in a field:value token.

        - field_any:value1,value2  -> (value1 OR value2)
        - field_all:value1,value2  -> (value1 AND value2)
        - field_not:value1,value2  -> NOT (value1 AND value2)

        Values are split on commas while respecting quoted segments. When no mode suffix is
        present the default is ``all``. Single-value tokens are returned without parentheses.

        Args:
            text (str): A single ``field:value`` token, optionally with a mode suffix.

        Returns:
            str: The expanded boolean expression, or the original text if it cannot be parsed.

        """
        if not text or ":" not in text:
            return text

        # Allow optional _mode suffix; if absent, default to 'all'
        m = re.match(
            r"^\s*(?P<prefix>[^:_\s]+)(?:_(?P<mode>any|all|not))?\s*:\s*(?P<values>.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if not m:
            return text

        base_field = m.group("prefix")
        mode = (m.group("mode") or "all").lower()
        values = m.group("values").strip()

        items = split_quoted_csv_values(values)

        # Build fragments preserving original quoting
        fragments = [f"{base_field}:{it}" for it in items]

        # If only one clause, return it without extra parentheses.
        if len(fragments) == 1:
            single = fragments[0]
            if mode == "not":
                return f"NOT {single}"
            return single

        if mode == "any":
            return "(" + " OR ".join(fragments) + ")"
        if mode == "all":
            return "(" + " AND ".join(fragments) + ")"
        if mode == "not":
            return "NOT (" + " AND ".join(fragments) + ")"

        return text

    def _tokenize_query(self, text: str) -> list[str]:
        """Tokenize a query string into components.

        Preserves quoted phrases, boolean operators (AND/OR/NOT) as separate tokens,
        and separates parentheses '(' and ')' into their own tokens.

        Args:
            text (str): The query string to tokenize.

        Returns:
            list[str]: The ordered tokens, with boolean operators normalized to uppercase.

        """
        if not text:
            return []

        token_re = re.compile(
            r"""(
                [a-zA-Z0-9_]+(?:_(?:any|all|not))?\s*:\s*
                    (?:
                        '(?:[^'\\]|\\.)*'
                        |"(?:[^"\\]|\\.)*"
                        |[^\s(),]+
                    )
                    (?:
                        \s*,\s*
                        (?:
                            '(?:[^'\\]|\\.)*'
                            |"(?:[^"\\]|\\.)*"
                            |[^\s(),]+
                        )
                    )*
                |'(?:[^'\\]|\\.)*'
                |"(?:[^"\\]|\\.)*"
                |\b(?:AND|OR|NOT)\b
                |\(
                |\)
                |[^\s()]+
            )""",
            re.IGNORECASE | re.VERBOSE,
        )

        tokens: list[str] = []
        for m in token_re.finditer(text):
            tok = m.group(0)
            # Normalize boolean operators to uppercase
            if re.fullmatch(r"\b(?:AND|OR|NOT)\b", tok, flags=re.IGNORECASE):
                tokens.append(tok.upper())
            else:
                tokens.append(tok)
        return tokens

    def _parse_numeric_range(self, value: str) -> tuple[str | None, str | None]:
        """Parse a numeric range expressed as 'low-high'.

        Args:
            value (str): The candidate range string.

        Returns:
            tuple[str | None, str | None]: The ``(low, high)`` bounds, or ``(None, None)`` if
                the value is not a valid numeric range.

        """
        if not value or "-" not in value:
            return None, None
        parts = value.split("-", 1)
        low = parts[0].strip()
        high = parts[1].strip()
        if low == "" or high == "":
            return None, None
        if not self._is_number(low) or not self._is_number(high):
            return None, None
        return low, high

    def _is_number(self, text: str) -> bool:
        """Return True if text can be parsed as float."""
        try:
            float(str(text))
        except (ValueError, TypeError):
            return False
        else:
            return True

    def _expand_field_aliases(self, text: str) -> str:
        """Replace simple prefix aliases like 'taxon:' -> 'taxonomy_id:' based on configuration.

        Simple prefix substitution that does not fully parse boolean grammar.

        Args:
            text (str): The query string to process.

        Returns:
            str: The query with configured field aliases substituted.

        """
        out = text or ""
        for friendly, native in (self.config.field_aliases or {}).items():
            pattern = re.compile(rf"\b{re.escape(friendly)}:")
            out = pattern.sub(f"{native}:", out)
        return out

    def _remove_ignored_fields(self, text: str) -> str:
        """Remove ignored field macros from the query so they can be handled elsewhere.

        Strips field tokens and attempts to keep boolean operators well-formed.
        If "ignore_all_fields" is set in extras, removes all fielded queries
        except those explicitly listed in fields.

        Args:
            text (str): The query string to process.

        Returns:
            str: The query with ``ignored_fields`` tokens removed and dangling booleans cleaned.

        """
        out = text or ""
        fields_to_ignore = set(self.config.ignored_fields or [])

        for field_name in fields_to_ignore:
            pattern = re.compile(
                rf"(\s*(?:AND|OR|NOT)\s+)?"  # optional leading boolean
                rf"\b{re.escape(field_name)}(?:_?(any|all|not))?:"
                r"("  # start items capture
                r"(?:\"[^\"]+\"|'[^']+')(?:\s*,\s*(?:\"[^\"]+\"|'[^']+'))*"  # quoted csv
                r"|"
                r"[^\s()]+(?:\s*,\s*[^\s()]+)*"  # unquoted csv (no spaces)
                r")",
                flags=re.IGNORECASE,
            )
            out = pattern.sub(" ", out)

        return self._strip_dangling_booleans(out)

    def _strip_dangling_booleans(self, text: str) -> str:
        """Collapse consecutive, leading, or trailing boolean operators left after field removal.

        Args:
            text (str): The query string to clean.

        Returns:
            str: The query with stray boolean operators removed.

        """
        out = re.sub(r"\b(AND|OR|NOT)\s*(?=\b(AND|OR|NOT)\b)", " ", text, flags=re.IGNORECASE)
        out = re.sub(r"^\s*(AND|OR|NOT)\b\s*", "", out, flags=re.IGNORECASE)
        return re.sub(r"\b(AND|OR|NOT)\s*$", "", out, flags=re.IGNORECASE)

    def _remove_all_fields(self, text: str) -> str:
        """Remove every fielded query from the text except those listed in ``config.fields``.

        Args:
            text (str): The query string to process.

        Returns:
            str: The query with unknown fields removed and dangling booleans cleaned.

        """
        out = text or ""
        allowed_fields = set(self.config.fields.keys())

        pattern = re.compile(
            r"(\s*(?:AND|OR|NOT)\s+)?"  # optional leading boolean
            r"\b([a-zA-Z0-9_]+)(?:_?(any|all|not))?:"
            r"("  # start items capture
            r"(?:\"[^\"]+\"|'[^']+')(?:\s*,\s*(?:\"[^\"]+\"|'[^']+'))*"  # quoted csv
            r"|"
            r"[^\s()]+(?:\s*,\s*[^\s()]+)*"  # unquoted csv (no spaces)
            r")",
            flags=re.IGNORECASE,
        )

        replacement = partial(_remove_unknown_field_match, allowed_fields=allowed_fields)
        out = pattern.sub(replacement, out)

        return self._strip_dangling_booleans(out)


class UniProtQueryInterpreter(BaseQueryInterpreter):
    """Query interpreter for UniProt queries."""

    def _looks_like_go_id(self, text: str) -> bool:
        """Check if a string matches a 7-digit GO numeric ID."""
        return bool(re.fullmatch(r"\d{7}", text.strip()))

    # Resolver kinds whose only job is a friendly-name -> native-id lookup in the
    # field's own ``value_map`` (after stripping any surrounding quotes).
    _MAP_RESOLVERS = frozenset(
        {
            "database_map",
            "function_map",
            "go_name_map",
            "keyword_map",
            "organism_map",
            "taxonomy_map",
        }
    )

    def _resolve_item(self, prefix: str, value: str, cfg: MultiModeFieldConfig) -> tuple[str, str]:
        """Resolve a single ``prefix:value`` item against its field configuration.

        Map-based resolvers translate a friendly value to its native id via
        ``cfg.value_map``; ``length_transform`` rewrites a numeric range to UniProt
        ``[low TO high]`` syntax. Values that are already native ids pass through.

        Args:
            prefix (str): The (already formatted) field prefix.
            value (str): The value to resolve.
            cfg (MultiModeFieldConfig): Configuration for the field, including its resolver kind.

        Returns:
            tuple[str, str]: The resolved ``(prefix, value)`` pair.

        """
        # Already-native ids pass through untouched.
        if cfg.resolver_kind == "go_name_map" and self._looks_like_go_id(value):
            return prefix, value
        if cfg.resolver_kind == "keyword_map" and "KW-" in value:
            return prefix, value

        if cfg.resolver_kind == "length_transform":
            low, high = self._parse_numeric_range(value)
            if low is not None and high is not None:
                return prefix, f"[{low} TO {high}]"
            return prefix, value

        if cfg.resolver_kind in self._MAP_RESOLVERS:
            mapped = cfg.value_map.get(value.strip("'\"").lower())
            if mapped:
                return prefix, mapped

        return prefix, value

    def extract_databases(self, query: str) -> list[str]:
        """Extract databases implied by special fields in the query.

        Some fields imply enrichment searches. For example, 'temperature' implies
        searching brenda with "getTemperatureOptimum", "getTemperatureStability",
        "getTemperatureRange". Call this before interpreting the query.

        Args:
            query (str): The raw query to inspect.

        Returns:
            list[str]: Database identifiers implied by the query's special fields.

        """
        databases: list[str] = []
        tokens = self._tokenize_query(query)
        for tok in tokens:
            if ":" not in tok:
                continue
            prefix, value = tok.split(":", 1)
            # Ignore _any/_all/_not suffixes for this purpose
            if "_" in prefix:
                prefix = prefix.rsplit("_", 1)[0]

            if prefix == "databases":
                for database in value.split(","):
                    _, resolved_db = self._resolve_item(
                        prefix, database.strip(), self.config.fields["databases"]
                    )
                    if resolved_db:
                        databases.append(database.strip())

            elif prefix == "temperature":
                databases.extend(
                    [
                        "brenda_getTemperatureOptimum",
                        "brenda_getTemperatureStability",
                        "brenda_getTemperatureRange",
                    ]
                )

        return databases


def build_default_uniprot_interpreter() -> UniProtQueryInterpreter:
    """Build a UniProtQueryInterpreter with default configuration."""
    catalog = get_uniprot_query_field_catalog()
    fields = {
        key: MultiModeFieldConfig(
            field=entry.native_field,
            value_map=dict(entry.value_map),
            supports_range=entry.supports_range,
            resolver_kind=entry.resolver_kind,
        )
        for key, entry in catalog.items()
    }

    field_aliases = {
        "taxon": "taxonomy_id",
        "taxid": "taxonomy_id",
        "org": "organism",
        "db": "database",
        "xref": "database",
        "temperature": "cc_bpcp_temp_dependence",
        "ph": "cc_bpcp_ph_dependence",
    }

    config = QueryInterpreterConfig(
        fields=fields,
        field_aliases=field_aliases,
        ignored_fields=["ic50", "activity", "target"],
        extras=None,
    )

    return UniProtQueryInterpreter(config=config)


class ChEMBLQueryInterpreter(BaseQueryInterpreter):
    """Query interpreter for ChEMBL queries."""

    def _resolve_item(self, prefix: str, value: str, cfg: MultiModeFieldConfig) -> tuple[str, str]:
        """Resolve an item value based on the field configuration.

        Currently applies IC50 transforms (ranges, comparison operators, and plain numbers
        are rewritten to ``standard_type``/``standard_value`` clauses); no other resolution
        is implemented for ChEMBL.

        Args:
            prefix (str): The (already formatted) field prefix.
            value (str): The value to resolve.
            cfg (MultiModeFieldConfig): Configuration for the field, including its resolver kind.

        Returns:
            tuple[str, str]: The resolved ``(prefix, value)`` pair; an empty prefix indicates
                the value is a complete standalone clause.

        """
        if cfg.resolver_kind == "ic50_transform":
            m_comp = re.fullmatch(r"(>=|<=|>|<)\s*(\d+(?:\.\d+)?)", value.strip())
            low, high = self._parse_numeric_range(value)
            # 1) Range case
            if low is not None and high is not None:
                return "", f"standard_type=IC50 AND standard_value>{low} AND standard_value<{high}"
            # 2) Comparison: >1000, <=50, etc.
            if m_comp:
                operator = m_comp.group(1)
                number = m_comp.group(2)
                return "", f"standard_type=IC50 AND standard_value{operator}{number}"
            # 3) Plain number
            if self._is_number(value):
                return "", f"standard_type=IC50 AND standard_value={value.strip()}"

        return prefix, value

    def interpret(self, query: str) -> str:
        """Interpret a query string into a ChEMBL-compatible query string."""
        # Replace field aliases
        processed_query = self._expand_field_aliases(query)
        # Remove ignored fields
        if self.config.extras and self.config.extras.get("ignore_all_fields", False):
            processed_query = self._remove_all_fields(processed_query)
        else:
            processed_query = self._remove_ignored_fields(processed_query)
        # Clean additional whitespace
        processed_query = self._cleanup_whitespace(processed_query)
        # Resolve item values as needed
        return self._resolve_query_items(processed_query)

    def parse_query_builder_string(self, query: str) -> dict[str, object]:
        """Parse a ChEMBL query-builder string into an internal query structure."""
        return parse_chembl_query_builder_string(query)


def build_default_chembl_interpreter() -> ChEMBLQueryInterpreter:
    """Build a ChEMBLQueryInterpreter with default configuration.

    Returns:
        ChEMBLQueryInterpreter: An interpreter wired with the default ChEMBL fields and the
            ``ignore_all_fields`` extra enabled.

    """
    fields = {
        "ic50": MultiModeFieldConfig(
            field="ic50",
            value_map={},
            supports_range=True,
            resolver_kind="ic50_transform",
        ),
        "activity": MultiModeFieldConfig(
            field="activity",
            value_map={},
            supports_range=False,
            resolver_kind=None,
        ),
        "target": MultiModeFieldConfig(
            field="target",
            value_map={},
            supports_range=False,
            resolver_kind=None,
        ),
    }

    config = QueryInterpreterConfig(
        fields=fields,
        field_aliases={},
        ignored_fields=[],
        extras={"ignore_all_fields": True},
    )

    return ChEMBLQueryInterpreter(config=config)
