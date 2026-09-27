"""Hukuki dilekçe motoru — sınıflandır, denetle, puanla. Üretim şablonunu değiştirmez."""
from .catalog import CLAIM_SPECS, LABOR_CLAIMS, TRACK_CLAIMS
from . import stages
from .pipeline import (
    analyze,
    claim_labels,
    classify,
    cite_fits_claims,
    detect_claims,
    form_claims,
    format_preflight,
    format_quality_report,
    intent_text,
    is_kalem_dump,
)

__all__ = [
    "CLAIM_SPECS",
    "LABOR_CLAIMS",
    "TRACK_CLAIMS",
    "analyze",
    "claim_labels",
    "classify",
    "cite_fits_claims",
    "detect_claims",
    "form_claims",
    "format_preflight",
    "format_quality_report",
    "intent_text",
    "is_kalem_dump",
    "stages",
]
