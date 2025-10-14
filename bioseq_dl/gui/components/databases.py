import os, json, logging
import gradio as gr
import pandas as pd
from functools import partial

import yaml
import importlib

# ----- Optional logging (fallback to stdlib) -----
try:
    from bioseq_dl.logging import get_logger
except Exception:
    def get_logger(name: str) -> logging.Logger:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        return logging.getLogger(name)

log = get_logger("bioseq_dl.gui.components.databases")
# -------------------------------------------------

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True), override=True)
except Exception:
    pass

def has_options(method_info: dict) -> bool:
    """Return True if the method defines non-empty 'options'."""
    return isinstance(method_info.get("options"), dict) and bool(method_info["options"])


def toggle_visibility(selected: str, option_names: list[str]):
    """Return visibility updates for option groups given the selected option."""
    from gradio import update
    return [update(visible=(name == selected)) for name in option_names]

def truncate_dataframe(df: pd.DataFrame, max_len: int = 40) -> pd.DataFrame:
    """
    Return a copy of df where long cell values are truncated for display.
    - Only string-like content is truncated (str, list, dict).
    - Numeric and boolean values are left intact.
    - Lists are joined by ', ' before truncation.
    - Dicts are JSON-serialized (compact) before truncation.
    """
    def _fmt(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return v

        if isinstance(v, (list, tuple, set)):
            s = ", ".join(map(str, v))
        elif isinstance(v, dict):
            try:
                s = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
            except Exception:
                s = str(v)
        elif isinstance(v, str):
            s = v
        else:
            # Non-string types: keep as-is (numbers, bools, etc.)
            return v

        return s if len(s) <= max_len else s[:max_len - 1] + "…"

    out = df.copy()
    for c in out.columns:
        out[c] = out[c].map(_fmt)
    return out

def get_init_defs(api_info):
    """
    Return the list of constructor parameters declared under 'init' in registry,
    or an empty list if none is present.
    """
    return api_info.get("init", []) or []

def resolve_init_kwargs(api_name, init_defs, ui_values):
    """
    Build kwargs for API constructor from UI values and environment variables.

    Rules:
    - Prefer the non-empty UI value if provided.
    - Otherwise, read from environment using the key in param['env'] if set,
      else fallback to f"{API}_{NAME}".upper().
    - If 'required' and still missing, raise ValueError.

    Parameters
    ----------
    api_name : str
        Name of the API (used to build fallback env var keys).
    init_defs : list[dict]
        Param specs: {'name','label','type','required','env'(optional)}.
    ui_values : list
        Values captured from the UI in the same order as init_defs.

    Returns
    -------
    dict
        Kwargs for the API constructor.
    """
    kwargs = {}
    for spec, ui_val in zip(init_defs, ui_values):
        name = spec["name"]
        required = spec.get("required", True)
        env_key = spec.get("env") or f"{api_name.upper()}_{name.upper()}"

        # prefer UI value if non-empty
        if ui_val not in (None, ""):
            kwargs[name] = ui_val
            continue

        # fallback to env
        env_val = os.getenv(env_key)
        if env_val not in (None, ""):
            kwargs[name] = env_val
            continue

        if required:
            raise ValueError(
                f"Missing constructor parameter '{name}'. "
                f"Provide it in the UI or set env var '{env_key}'."
            )

    return kwargs

#####################
# Env var helpers
#####################

def _env_keys_for_param(spec: dict, api_name: str, param_name: str):
    """
    Return a list of environment variable names to try for a constructor param.
    - spec['env'] can be a string or list of strings.
    - If not provided, fallback to f"{API}_{PARAM}" (uppercased).
    - Also add UPPERCASE variants of provided keys for convenience.
    """
    raw = spec.get("env")
    if isinstance(raw, str):
        keys = [raw]
    elif isinstance(raw, (list, tuple)):
        keys = [str(k) for k in raw]
    else:
        keys = [f"{api_name.upper()}_{param_name.upper()}"]

    # Add uppercase versions if needed
    out = []
    for k in keys:
        if isinstance(k, str):
            out.append(k)
            ku = k.upper()
            if ku != k:
                out.append(ku)
    return out


def _getenv_first(keys):
    """
    Return the first non-empty environment value among keys (strings).
    Ignores non-string entries defensively.
    """
    for k in keys:
        if not isinstance(k, str):
            continue
        v = os.getenv(k)
        if v not in (None, ""):
            return v
    return None

def _config_keys_for_param(spec: dict, api_name: str, param_name: str):
    """
    Return a list of config keys to try for a constructor param.
    - spec['config'] can be a string or list of strings.
    - If not provided, fallback to param_name (as-is).
    """
    raw = spec.get("config")
    if isinstance(raw, str):
        keys = [raw]
    elif isinstance(raw, (list, tuple)):
        keys = [str(k) for k in raw]
    else:
        keys = [param_name]
    return keys

def _getconfig_first(keys, api_name: str):
    """
    Return the first non-empty config value among keys taken from the API's init.yml.

    It resolves CONFIG_DIR from the constants module:
      bioseq_dl.constants.databases -> <DBConfig object by UPPERCASE api_name> -> CONFIG_DIR

    Example:
      api_name='brenda' -> constants.BRENDA.CONFIG_DIR/init.yml
    """
    if not keys:
        return None

    try:
        # Import the constants module (it's a module, not a package of per-API submodules)
        const_mod = importlib.import_module("bioseq_dl.constants.databases")
        dbcfg = getattr(const_mod, api_name.upper())  # e.g., BRENDA, BIOGRID, REFSEQ
        config_dir = getattr(dbcfg, "CONFIG_DIR")
    except Exception as e:
        log.error(f"Error resolving CONFIG_DIR for '{api_name}': {e}")
        return None

    config_path = os.path.join(config_dir, "init.yml")
    try:
        if not os.path.exists(config_path):
            return None
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for k in keys:
            if isinstance(k, str) and k in data:
                val = data.get(k)
                if val not in (None, ""):
                    return val
    except Exception as e:
        log.error(f"Error reading config file {config_path}: {e}")
    return None

def _resolve_init_kwargs_config_first(api_name: str, init_defs: list, ui_values: list):
    """
    Build constructor kwargs with precedence:
      1) Non-empty UI values
      2) Config file (init.yml in constants' CONFIG_DIR)
      3) Environment variables (fallback)

    Raises ValueError if a required param remains missing.
    """
    kwargs = {}
    if not init_defs:
        return kwargs

    if not ui_values:
        ui_values = [None] * len(init_defs)

    for spec, ui_val in zip(init_defs, ui_values):
        name = spec["name"]
        required = spec.get("required", True)

        # 1) UI
        if ui_val not in (None, ""):
            kwargs[name] = ui_val
            continue

        # 2) Config
        cfg_keys = _config_keys_for_param(spec, api_name, name)
        cfg_val = _getconfig_first(cfg_keys, api_name)
        if cfg_val not in (None, ""):
            kwargs[name] = cfg_val
            continue

        # 3) Env
        env_keys = _env_keys_for_param(spec, api_name, name)
        env_val = _getenv_first(env_keys)
        if env_val not in (None, ""):
            kwargs[name] = env_val
            continue

        if required:
            raise ValueError(
                f"Missing initialization parameter '{name}'. "
                f"Provide it via UI or config keys {cfg_keys} or env vars {env_keys}."
            )

    return kwargs

def coerce_value(type_str, raw):
    """
    Coerce UI value to declared type.
    list[...] -> Python list (parse comma-separated text or accept widget lists).
    Returns (value, is_empty).
    """
    if type_str.startswith("list[") and type_str.endswith("]"):
        inner = type_str[5:-1]  # 'str' | 'int' | 'float'
        if raw is None:
            items = []
        elif isinstance(raw, (list, tuple, set)):
            items = [x for x in raw if not (isinstance(x, str) and x.strip() == "")]
        else:
            items = [t.strip() for t in str(raw).split(",") if t.strip() != ""]
        caster = str
        if inner == "int":   caster = int
        elif inner == "float": caster = float
        items = [caster(x) for x in items]
        return items, (len(items) == 0)

    # Scalars
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None, True
    if type_str == "int":   return int(raw), False
    if type_str == "float": return float(raw), False
    return str(raw), False  # default 'str'


#############################
# Visual components
#############################


def create_input_component(param, prefix: str = ""):
    """
    Build UI components recursively from a registry param spec.

    Returns
    -------
    List[Tuple[str, str, gr.Component]]
        A flat list of (full_name, type_str, component) ready to be wired in build_method_ui.

    Notes
    -----
    - Supports primitives: 'str', 'int', 'float', 'list[str]', 'list[int]', 'list[float]'.
    - Supports 'choices' (Dropdown) and 'checkboxgroup' (CheckboxGroup).
    - If 'inputs' is present, renders a visual group and recurses on children.
    - Nested field names are joined as "<group>.<child>" (e.g., "filters.type").
    """
    out = []

    # Group / nested case (e.g., list[dict] or any compound spec with 'inputs')
    if "inputs" in param and isinstance(param["inputs"], list):
        group_name = param.get("name", prefix.rstrip(".")) or ""
        # Visual grouping only; the children are appended to 'out'
        with gr.Group():
            if param.get("label"):
                gr.Markdown(f"**{param['label']}**")
            child_prefix = f"{prefix}{group_name}." if group_name else prefix
            for child in param["inputs"]:
                out.extend(create_input_component(child, prefix=child_prefix))
        return out
    
    # Leaf (primitive) case
    name = param["name"]
    full_name = f"{prefix}{name}" if prefix else name
    type_str = param.get("type", "str")
    required = param.get("required", False)

    common = {
        "label": param.get("label", name),
        "info": "Required" if required else None,
    }

    # Numeric
    if type_str in ("int", "float"):
        comp = gr.Number(
            **common,
            value=param.get("default", None),
        )
        out.append((full_name, type_str, comp))
        return out

    # Free text (scalar)
    if type_str == "str" and "choices" not in param and "checkboxgroup" not in param:
        comp = gr.Textbox(
            **common,
            placeholder=param.get("placeholder", param.get("default", "")),
            value=param.get("default", ""),
            lines=1
        )
        out.append((full_name, type_str, comp))
        return out

    # List-as-text (comma-separated)
    if type_str in ("list[str]", "list[int]", "list[float]") and "checkboxgroup" not in param and "choices" not in param:
        comp = gr.Textbox(
            **common,
            placeholder=param.get("placeholder", ""),
            lines=2
        )
        out.append((full_name, type_str, comp))
        return out

    # Dropdown (choices)
    if "choices" in param:
        comp = gr.Dropdown(
            choices=param["choices"],
            **common,
            multiselect=("list" in type_str),
            value=param.get("selected", param.get("default", None))
        )
        out.append((full_name, type_str, comp))
        return out

    # CheckboxGroup
    if "checkboxgroup" in param:
        comp = gr.CheckboxGroup(
            choices=param["checkboxgroup"],
            **common,
            value=param.get("selected", param.get("default", []))
        )
        out.append((full_name, type_str, comp))
        return out

    # Fallback → Textbox
    comp = gr.Textbox(
        **common,
        placeholder=param.get("placeholder", param.get("default", "")),
        value=param.get("default", "")
    )
    out.append((full_name, type_str, comp))
    return out


def build_method_ui(api_name, api_class, method_name, method_info, init_defs, init_inputs):
    """Render UI for a method using the recursive `create_input_components`.

    - If the method has no 'options', render a flat list of inputs produced by `create_input_components`.
    - If the method defines 'options', render a Radio to select an option and, per option,
      render its own flat list of inputs (again via `create_input_components`).
    - The click handler always calls `run_query` (unified runner) with the same signature you already use.
    """
    with gr.Tab(method_name):
        # A) Normal method (without options)
        if not (isinstance(method_info.get("options"), dict) and method_info["options"]):
            inputs = []
            for p in method_info.get("inputs", []):
                inputs.extend(create_input_component(p))  # <- recursive, returns flattened list

            df_out = gr.Dataframe(label="Result (DataFrame)", interactive=False, wrap=True, visible=False)
            json_out = gr.JSON(label="Result (JSON)", visible=False)
            run_btn = gr.Button("Run")

            # Input order: init..., then all method components (flattened)
            all_inputs = [c for (_n, c) in init_inputs] + [c for (_full, _t, c) in inputs]

            run_btn.click(
                partial(
                    run_query,
                    api_name=api_name,
                    api_class=api_class,
                    method_name=method_name,
                    method_info=method_info,
                    init_defs=init_defs,
                    init_count=len(init_inputs),
                    df_out=df_out,
                    json_out=json_out,
                    options_def=None,
                    option_names=None,
                    option_len_map=None,
                ),
                inputs=all_inputs,
                outputs=[df_out, json_out],
            )
            return

        # B) Method with 'options'
        options_def = method_info["options"]
        option_names = list(options_def.keys())
        first_opt = option_names[0]

        # Option selector (no accordion)
        opt_selector = gr.Radio(option_names, label="Options", value=first_opt, interactive=True)

        # Build a group and flattened inputs per option
        option_groups = {}
        option_inputs_map = {}  # option_name -> [(full_name, type_str, component), ...]
        option_len_map = {}     # option_name -> number of flattened components

        for name in option_names:
            params = options_def[name].get("inputs", [])
            with gr.Group(visible=(name == first_opt)) as grp:
                flat_inputs = []
                for p in params:
                    flat_inputs.extend(create_input_component(p))  # <- recursive/flatten
                option_groups[name] = grp
                option_inputs_map[name] = flat_inputs
                option_len_map[name] = len(flat_inputs)

        # Toggle visibility when changing option
        def _toggle(selected):
            return [gr.update(visible=(n == selected)) for n in option_names]

        opt_selector.change(
            _toggle,
            inputs=[opt_selector],
            outputs=[option_groups[n] for n in option_names]
        )

        # Outputs + button
        df_out = gr.Dataframe(label="Result (DataFrame)", interactive=False, wrap=True, visible=False)
        json_out = gr.JSON(label="Result (JSON)", visible=False)
        run_btn = gr.Button("Run")

        # Inputs: init..., selector, and all components (flattened) of all options (in option_names order)
        flat_option_components = []
        for n in option_names:
            flat_option_components.extend([c for (_full, _t, c) in option_inputs_map[n]])

        all_inputs = [c for (_n, c) in init_inputs] + [opt_selector] + flat_option_components

        run_btn.click(
            partial(
                run_query,
                api_name=api_name,
                api_class=api_class,
                method_name=method_name,
                method_info=method_info,      # runner will choose the selected option
                init_defs=init_defs,
                init_count=len(init_inputs),
                df_out=df_out,
                json_out=json_out,
                options_def=options_def,
                option_names=option_names,
                option_len_map=option_len_map,  # important: tells runner how many inputs each option has
            ),
            inputs=all_inputs,
            outputs=[df_out, json_out],
        )

def build_api_ui(api_name, api_info):
    """Builds the tab for a complete API"""
    with gr.Blocks():
        with gr.Row():
            with gr.Column(min_width=420):  # centered content
                gr.Markdown(
                    "<div style='text-align:center'>"
                    f"<h1>{api_name}</h1>"
                    "</div>"
                )
        with gr.Row():
            api_class = api_info["class"]
            
            # Init Constructor parameters
            init_defs = get_init_defs(api_info)
            init_inputs = []

            if init_defs:
                missing_required = False
                # Check if any required param is missing in env or config
                for spec in init_defs:
                    if not spec.get("required", True):
                        continue
                    # First check config
                    cfg_keys = _config_keys_for_param(spec, api_name, spec["name"])
                    in_config = False
                    if _getconfig_first(cfg_keys, api_name) is not None:
                        in_config = True
                    
                    # Then check env
                    keys = _env_keys_for_param(spec, api_name, spec["name"])
                    in_env = False
                    if _getenv_first(keys) is None:
                        in_env = True
                    
                    # The parameter is missing if not in config and not in env
                    # So it's required to input the missing parameter in the UI
                    if not in_config and not in_env:
                        missing_required = True
                        break
                
                if missing_required:
                    with gr.Accordion("Initialization parameters", open=True):
                        for spec in init_defs:
                            label = spec.get("label", spec["name"])

                            # First try config (init.yml), then env
                            cfg_keys = _config_keys_for_param(spec, api_name, spec["name"])
                            prefill_cfg = _getconfig_first(cfg_keys, api_name)

                            env_keys = _env_keys_for_param(spec, api_name, spec["name"])
                            prefill_env = _getenv_first(env_keys)

                            # Choose non-sensitive prefill. Avoid prefill for type "password"
                            if spec.get("name") == "password":
                                prefill = None
                                input_type = "password"
                            else:
                                prefill = prefill_cfg if prefill_cfg not in (None, "") else prefill_env
                                input_type = "text"
                            
                            comp = gr.Textbox(
                                label=label,
                                value=prefill,
                                type=input_type,
                                info="Required" if spec.get("required", True) else None
                            )
                            init_inputs.append((spec["name"], comp))

            for method_name, method_info in api_info["methods"].items():
                build_method_ui(
                    api_name,
                    api_class, 
                    method_name, 
                    method_info, 
                    init_defs, 
                    init_inputs
                )

##############################
# Logic to run queries
##############################

def _flatten_input_specs(specs: list, prefix: str = "") -> list[dict]:
    """
    Flatten registry input specs into a list of leaves with full dotted names.

    Returns a list of dicts:
      {"full_name": "<name or group.sub>", "type": "<type_str>", "required": bool}

    If a spec has "inputs" (e.g., list[dict] container), children are emitted as
    "<group>.<child>" leaves using the children's own types/required flags.
    """
    out = []
    for p in specs or []:
        if isinstance(p, dict) and isinstance(p.get("inputs"), list):
            group = p.get("name", "")
            child_prefix = f"{prefix}{group}." if group else prefix
            out.extend(_flatten_input_specs(p["inputs"], prefix=child_prefix))
        else:
            out.append({
                "full_name": f"{prefix}{p['name']}" if prefix else p["name"],
                "type": p.get("type", "str"),
                "required": bool(p.get("required", False)),
            })
    return out

def run_query(
        *all_values, 
        api_name, 
        api_class, 
        method_name,
        method_info,
        init_defs,
        init_count,
        options_def=None,
        option_names=None,
        option_len_map=None,
        df_out, 
        json_out
    ):
    """Executor for methods

    Contract (inputs order):
    - Normal method: [init..., method_inputs...]
    - Method with options: [init..., selected_option, *all_options_inputs_flattened_in_option_names_order]

    Behavior:
    - Instantiates API using init values (UI > env).
    - Picks effective method schema: method_info or selected option's schema.
    - Coerces and validates values according to declared types (str/int/float/list[..]).
    - Minimal multisearch support (atomic + single str input + multisearch=True):
        * multisearch=False -> fetch_single(query=<string>)
        * multisearch=True  -> fetch_batch(queries=[...]) using comma split
    - Otherwise:
        * 'atomic' -> batch with a single query dict by default
        * 'composite' -> batch with a single query dict (expansion can be layered on top if needed)
    """
    # --- 1) Split init values ---
    ui_init_values = list(all_values[:init_count])
    idx = init_count

    # --- 2) Select effective schema and capture UI values for it ---
    eff_info = method_info
    selected_vals = []

    has_opts = isinstance(options_def, dict) and options_def
    selected_option = None
    
    if has_opts and option_names and options_def:
        selected_option = all_values[idx]; idx += 1
        flat_vals = list(all_values[idx:])
        # slice values of selected option based on option_len_map
        offset = 0
        for name in option_names:
            n = option_len_map.get(name, 0) if option_len_map else 0
            chunk = flat_vals[offset:offset+n]
            if name == selected_option:
                selected_vals = chunk
            offset += n
        eff_info = options_def[selected_option]
    else:
        selected_vals = list(all_values[idx:])

    # --- 3) Instantiate API (UI > env) ---
    try:
        ctor_kwargs = _resolve_init_kwargs_config_first(api_name, init_defs, ui_init_values) if init_defs else {}
        api = api_class(**ctor_kwargs) if ctor_kwargs else api_class()
    except Exception as e:
        return gr.update(visible=False), gr.update(value={"error": str(e)}, visible=True)

    # --- 4) Coerce + validate according to eff_info['inputs'] ---
    inputs_schema = eff_info.get("inputs", [])

    # Map of top-level specs and sub-specs for list[dict]
    top_specs = {p["name"]: p for p in inputs_schema}
    listdict_subspecs = {
        name: {c["name"]: c for c in spec.get("inputs", [])}
        for name, spec in top_specs.items()
        if spec.get("type") == "list[dict]"
    }

    # Flatten the schema as rendered by the UI (dot names)
    flat_specs = _flatten_input_specs(inputs_schema)

    vals = {}
    groups = {}  # group -> {"spec": top_spec, "obj": {sub: val}, "empties": {sub: bool}}

    # Coerce + validate using the flattened schema and UI values
    for spec, raw in zip(flat_specs, selected_vals):
        full_name = spec["full_name"]
        t = spec["type"]
        required = spec["required"]

        if "." in full_name:
            group, sub = full_name.split(".", 1)
            gspec = top_specs.get(group)
            # Only fold if parent is list[dict]
            if gspec and gspec.get("type") == "list[dict]":
                # Use the type/required from the subfield (flat spec is already the child's)
                v, empty = coerce_value(t, raw)
                g = groups.setdefault(group, {"spec": gspec, "obj": {}, "empties": {}})
                g["obj"][sub] = v
                g["empties"][sub] = empty
                continue

        # Normal leaf (or group not list[dict])
        v, empty = coerce_value(t, raw)
        if required and empty:
            return gr.update(visible=False), gr.update(value={"error": f"The field '{full_name}' is required and cannot be empty."}, visible=True)
        if not required and empty:
            continue
        vals[full_name] = v

    # Fold list[dict] groups into vals (as a list with ONE dict)
    for gname, data in groups.items():
        gspec = data["spec"]
        subs_map = listdict_subspecs.get(gname, {})

        # Are all subfields empty?
        all_empty = all(data["empties"].get(s, True) for s in subs_map.keys())
        if all_empty:
            if gspec.get("required", False):
                return gr.update(visible=False), gr.update(value={"error": f"The group '{gname}' is required and cannot be empty."}, visible=True)
            continue  # optional group empty -> skip

        # Validate required subfields
        for sname, ssub in subs_map.items():
            if ssub.get("required", False) and data["empties"].get(sname, True):
                return gr.update(visible=False), gr.update(value={"error": f"The required subfield '{gname}.{sname}' cannot be empty."}, visible=True)

        # Build the object with non-empty subfields
        obj = {
            sname: data["obj"].get(sname)
            for sname in subs_map.keys()
            if not data["empties"].get(sname, True)
        }
        vals[gname] = [obj]  # contract: list with 1 dict for list[dict]


    
    # Build call kwargs; include 'option' if present
    call_kwargs = {"method": method_name, "parse": True, "to_dataframe": True}
    if has_opts and selected_option:
        call_kwargs["option"] = selected_option

    itype = eff_info.get("input_type", "atomic")
    multisearch = bool(eff_info.get("multisearch", False))

    # --- 5) Execute according to minimal rules ---
    try:
        if multisearch and len(inputs_schema) == 1 and inputs_schema[0].get("type", "str") == "str":
            # Atomic, single string input with optional commas -> single or batch
            field = inputs_schema[0]["name"]
            tokens = [t.strip() for t in vals.get(field, "").split(",") if t.strip()]
            if tokens:
                result = api.fetch_batch(queries=tokens, **call_kwargs)
            else:
                # single empty is handled above; single non-empty with no commas
                result = api.fetch_single(query=vals.get(field), **call_kwargs)
        else:
            # Default: send one dict as a batch of size 1 (keeps previous semantics for dict methods)
            query_dict = vals
            result = api.fetch_batch(queries=[query_dict], **call_kwargs)

        # --- 6) Show only one output ---
        if isinstance(result, pd.DataFrame) and not result.empty:
            try:
                df_preview = truncate_dataframe(result, max_len=40)  # optional pretty display
            except Exception:
                df_preview = result
            return gr.update(value=df_preview, visible=True), gr.update(visible=False)

        payload = {"message": "No results found", "method": method_name}
        if not isinstance(result, pd.DataFrame):
            payload = result
        return gr.update(visible=False), gr.update(value=payload, visible=True)

    except Exception as e:
        return gr.update(visible=False), gr.update(value={"error": str(e), "method": method_name}, visible=True)