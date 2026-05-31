"""
app/mcq/graph_utils.py

Loads physics_class11_complete_v2.json and provides:
  - VALID_CHAPTERS        list of chapter names with edges
  - get_chapter_edges()   edges for one chapter
  - build_equation_chain()  resolves substitution chain for one edge
  - build_mcq_messages()  builds the prompt messages list for the fine-tuned model
  - parse_model_output()  extracts JSON from model response
  - format_mcq_response() converts raw parsed dict -> clean API MCQ dict

All graph logic is self-contained here so app/routes/mcq.py stays thin.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any

# ── Locate the JSON relative to this file ────────────────────────────────────
# Layout:
#   project_root/
#     app/mcq/graph_utils.py   ← this file
#     physics_class11_complete_v2.json
_HERE       = Path(__file__).resolve().parent          # app/mcq/
_APP_DIR    = _HERE.parent                              # app/
_ROOT       = _APP_DIR.parent                           # project_root/
GRAPH_JSON  = _ROOT / "physics_class11_complete_v2.json"
GRAPH_PKL   = _ROOT / "data" / "graph" / "edumind_graph.pkl"
CONCEPT_CHROMA = str(_ROOT / "vector_stores" / "concept_chroma")

COVERAGE_NOTE = (
    "Currently covering Class 11 Physics Part 1 concepts only. "
    "Questions are generated only for concepts present in the knowledge graph."
)

# ── Default numeric values for known variables ────────────────────────────────
_DEFAULT_VALUES: dict[str, float] = {
    "m": 5,    "M": 10,   "m1": 3,   "m2": 7,
    "v": 20,   "u": 0,    "a": 2,    "t": 4,
    "s": 50,   "s0": 0,
    "F": 30,   "g": 10,   "r": 5,
    "I": 2,    "omega": 3, "tau": 6,
    "p": 50,   "P": 100,
    "W": 200,  "d": 10,   "theta": 60,
    "k_spring": 100, "Fs": -50,
    "N": 40,   "us": 0.4, "uk_spring": 0.3,
    "rho": 1000, "V": 0.5,
    "dp": 10,  "dL": 4,
    "Fc": 80,  "L": 15,
    "pa": 30,  "pb": 20,  "pa_prime": 10, "pb_prime": 40,
    "mi": 2,   "si": 3,   "X": 5,    "I_cm": 1,
    "f_freqs": 15, "f_freqs_mas": 16, "f_freqk_spring": 12,
    "Fab": 20, "Fba": -20, "F_est": 20,
    "A": 0.2,  "h": 5,
}

_AVOID_AS_UNKNOWN = {"g", "theta", "math", "integral", "constant", "pi"}


# ── Graph cache ───────────────────────────────────────────────────────────────
_graph_cache: dict | None = None


def _load_graph_json() -> dict:
    global _graph_cache
    if _graph_cache is None:
        if not GRAPH_JSON.exists():
            raise FileNotFoundError(
                f"Knowledge graph JSON not found: {GRAPH_JSON}\n"
                "Make sure physics_class11_complete_v2.json is in the project root."
            )
        with open(GRAPH_JSON, encoding="utf-8") as f:
            _graph_cache = json.load(f)
    return _graph_cache


def get_node_map() -> dict[str, dict]:
    return {n["concept_id"]: n for n in _load_graph_json()["nodes"]}


def get_chapter_edges(chapter_name: str) -> list[dict]:
    """Return all deduplicated edges for a given chapter name."""
    seen: set[str] = set()
    out: list[dict] = []
    for edge in _load_graph_json()["edges"]:
        if edge.get("chapter", "").strip() == chapter_name.strip():
            formula = edge["formula_str"]
            if formula not in seen:
                seen.add(formula)
                out.append(edge)
    return out


def get_valid_chapters() -> list[str]:
    """Return sorted list of chapter names that have at least one edge."""
    chapters = sorted({
        e["chapter"]
        for e in _load_graph_json()["edges"]
        if e.get("chapter", "").strip()
    })
    return chapters


# Computed once on first import
VALID_CHAPTERS: list[str] = []


def _ensure_valid_chapters() -> list[str]:
    global VALID_CHAPTERS
    if not VALID_CHAPTERS:
        try:
            VALID_CHAPTERS = get_valid_chapters()
        except Exception:
            pass
    return VALID_CHAPTERS


# ── Equation chain builder ────────────────────────────────────────────────────

def _symbol_to_name(symbol: str, node_map: dict) -> str:
    for node in node_map.values():
        if node.get("symbol") == symbol:
            return node["name"]
    fallbacks = {
        "rho": "Density", "omega": "Angular Velocity", "theta": "Angle",
        "tau": "Torque", "alpha": "Angular Acceleration",
        "mu": "Friction Coefficient", "eta": "Viscosity",
        "phi": "Phase", "lamda": "Wavelength",
        "g": "Gravitational Acceleration",
    }
    return fallbacks.get(symbol, symbol.capitalize())


def build_equation_chain(
    edge: dict, node_map: dict
) -> tuple[list[str], list[str], dict[str, float], str]:
    """
    Returns (equations, all_var_list, known_vals, unknown).

    equations    — list of formula strings (base + substitution chains)
    all_var_list — human-readable "symbol (Name)" strings
    known_vals   — {symbol: numeric_value} for all known variables
    unknown      — the symbol to solve for
    """
    base_formula    = edge["formula_str"]
    base_vars       = list(edge["variables"])
    subs            = edge.get("substitute_configs", [])
    equations       = [base_formula]
    all_var_symbols: set[str] = set(base_vars)

    for sc in subs[:2]:
        sub_eq = f"{sc['substitute_variable']} = {sc['replacement_expression']}"
        equations.append(sub_eq)
        all_var_symbols.update(sc["introduces_nodes"])
        for node_id in sc["introduces_nodes"]:
            node = node_map.get(node_id)
            if node and node.get("symbol"):
                all_var_symbols.add(node["symbol"])

    all_var_list = [
        f"{sym} ({_symbol_to_name(sym, node_map)})"
        for sym in sorted(all_var_symbols)
    ]

    # Choose unknown: prefer LHS of base formula, avoid constants
    lhs_match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", base_formula)
    unknown = (
        lhs_match.group(1)
        if lhs_match and lhs_match.group(1) not in _AVOID_AS_UNKNOWN
        else next(
            (v for v in base_vars if v not in _AVOID_AS_UNKNOWN),
            base_vars[0],
        )
    )

    known_vals: dict[str, float] = {}
    for sym in all_var_symbols:
        if sym == unknown or sym in ("math", "integral", "constant"):
            continue
        known_vals[sym] = _DEFAULT_VALUES.get(sym, 5)

    return equations, all_var_list, known_vals, unknown


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_mcq_messages(
    chapter_name: str,
    edges: list[dict],
) -> tuple[list[dict], dict, str, dict[str, float], list[str]]:
    """
    Randomly selects one edge, builds the prompt messages, and returns:
      (messages, chosen_edge, unknown, known_vals, equations)
    """
    node_map   = get_node_map()
    with_subs  = [e for e in edges if e.get("substitute_configs")]
    edge       = random.choice(with_subs if with_subs else edges)

    equations, all_var_list, known_vals, unknown = build_equation_chain(
        edge, node_map
    )

    seeds    = edge.get("scenario_seeds", ["A standard textbook physics problem"])
    scenario = random.choice(seeds)
    difficulty = (
        edge["substitute_configs"][0]["difficulty_upgrade"]
        if edge.get("substitute_configs")
        else "medium"
    )

    eq_block    = "\n".join(f"{i+1}. {eq}" for i, eq in enumerate(equations))
    vars_block  = ", ".join(all_var_list)
    known_block = ", ".join(f"{k}={v}" for k, v in sorted(known_vals.items()))

    system_msg = (
        "You are a physics MCQ generator and solver.\n\n"
        "STRICT FORMAT:\n<think>...</think>\n{ JSON }\n\n"
        "CRITICAL RULES:\n"
        "- You MUST use ONLY the given values\n"
        "- You MUST NOT invent any new numbers\n"
        "- You MUST solve step-by-step\n"
        "- You MUST reverse the equations correctly\n"
        "- Generate ONLY ONE output and STOP\n"
    )
    user_msg = (
        f"CHAPTER: {chapter_name}\n\n"
        f"EQUATIONS:\n{eq_block}\n\n"
        f"ALL VARIABLES:\n{vars_block}\n\n"
        f"KNOWN: {known_block}\n"
        f"UNKNOWN: {unknown}\n"
        f"STYLE: real_world\n"
        f"DIFFICULTY: {difficulty}\n"
        f"SCENARIO SEED: {scenario}"
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": user_msg},
    ]
    return messages, edge, unknown, known_vals, equations


# ── Output parser ─────────────────────────────────────────────────────────────

def parse_model_output(response: str) -> dict | None:
    """
    Extract and return the JSON dict from the model response.
    The model outputs <think>...</think> then a JSON object.
    Returns None if no valid JSON found.
    """
    # Strip thinking block
    cleaned = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()

    json_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if not json_match:
        return None

    raw = json_match.group(1).strip()
    if not raw.endswith("}"):
        raw += "}"

    try:
        return json.loads(raw)
    except Exception:
        # Try removing trailing comma before closing brace
        raw = re.sub(r",\s*\}", "}", raw)
        try:
            return json.loads(raw)
        except Exception:
            return None


# ── Response formatter ────────────────────────────────────────────────────────

def format_mcq_response(
    parsed: dict,
    edge: dict,
    unknown: str,
    equations: list[str],
) -> dict[str, Any]:
    """
    Convert raw model output dict into the clean API MCQ dict.

    The model returns either:
      - correct_answer + distractors[]  (preferred shape)
      - options[] + correct_index       (fallback shape)

    Both are normalised into labeled A/B/C/D options.
    """
    question    = parsed.get("question", "")
    explanation = parsed.get("explanation", "")
    correct_ans = str(parsed.get("correct_answer", ""))
    distractors = parsed.get("distractors", [])

    # Build options list
    if correct_ans and distractors:
        option_texts = [correct_ans] + [
            str(d.get("value", d)) if isinstance(d, dict) else str(d)
            for d in distractors[:3]
        ]
        # Pad to 4 if needed
        while len(option_texts) < 4:
            option_texts.append("N/A")
        option_texts = option_texts[:4]

        random.shuffle(option_texts)
        options = [
            {"label": chr(65 + i), "text": text}
            for i, text in enumerate(option_texts)
        ]
        correct_label = next(
            (opt["label"] for opt in options if opt["text"] == correct_ans),
            "A",
        )
    else:
        # Fallback: model used options[] + correct_index
        raw_options   = parsed.get("options", [])
        correct_index = parsed.get("correct_index", 0)
        options = [
            {"label": chr(65 + i), "text": str(o)}
            for i, o in enumerate(raw_options[:4])
        ]
        correct_label = chr(65 + correct_index) if raw_options else "A"
        correct_ans   = raw_options[correct_index] if raw_options else ""

    formatted_distractors = []
    for d in distractors[:3]:
        if isinstance(d, dict):
            formatted_distractors.append({
                "value": str(d.get("value", "")),
                "reason": str(d.get("reason", "")),
            })

    return {
        "question":       question,
        "options":        options,
        "correct_answer": correct_ans,
        "correct_label":  correct_label,
        "explanation":    explanation,
        "formula_used":   " | ".join(equations),
        "unknown_solved": unknown,
        "distractors":    formatted_distractors,
        "edge_id":        edge.get("edge_id", ""),
    }
