from __future__ import annotations

from collections.abc import Iterable

# (provider_display_name, [(model_id, short_label), ...])
PROVIDER_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("── Gemini ──────────────────────────────────────", [
        ("gemini/gemini-3.1-pro-preview",              "Gemini 3.1 Pro Preview"),
        ("gemini/gemini-3.1-pro-preview-customtools",  "Gemini 3.1 Pro CustomTools"),
        ("gemini/gemini-3-flash-preview",              "Gemini 3 Flash Preview"),
        ("gemini/gemini-3.1-flash-lite-preview",       "Gemini 3.1 Flash Lite Preview"),
        ("gemini/gemini-2.5-pro",                      "Gemini 2.5 Pro"),
        ("gemini/gemini-2.5-flash",                    "Gemini 2.5 Flash"),
        ("gemini/gemini-2.5-flash-lite",               "Gemini 2.5 Flash Lite"),
    ]),

    ("── Gemma ───────────────────────────────────────", [
        ("gemma/gemma-4-31b-it",       "Gemma 4 31B IT"),
        ("gemma/gemma-4-26b-a4b-it",   "Gemma 4 26B A4B IT"),
        ("gemma/gemma-3-27b-it",       "Gemma 3 27B IT"),
        ("gemma/gemma-3-12b-it",       "Gemma 3 12B IT"),
        ("gemma/gemma-3-4b-it",        "Gemma 3 4B IT"),
        ("gemma/gemma-3-1b-it",        "Gemma 3 1B IT"),
        ("gemma/gemma-3n-e4b-it",      "Gemma 3N E4B IT"),
    ]),
]

# Flat list: (model_id, short_label, provider_header)
ALL_MODELS: list[tuple[str, str, str]] = [
    (mid, lbl, hdr)
    for hdr, models in PROVIDER_GROUPS
    for mid, lbl in models
]


def iter_model_ids() -> Iterable[str]:
    for model_id, _, _ in ALL_MODELS:
        yield model_id


def get_model_label(model_id: str) -> str:
    """Return the short label for a model ID, or the ID itself if not found."""
    for mid, lbl, _ in ALL_MODELS:
        if mid == model_id:
            return lbl
    return model_id


def resolve_model(query: str) -> str | None:
    """Resolve a free-form user query to a unique model ID."""
    value = query.strip().lower()
    if not value:
        return None

    exact_matches = [model_id for model_id in iter_model_ids() if model_id.lower() == value]
    if exact_matches:
        return exact_matches[0]

    label_matches = [
        model_id
        for model_id, label, _ in ALL_MODELS
        if value in model_id.lower() or value in label.lower()
    ]
    if len(label_matches) == 1:
        return label_matches[0]
    return None
