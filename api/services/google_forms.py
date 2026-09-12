import json
import logging
from pathlib import Path

from api.config import get_settings

logger = logging.getLogger(__name__)

EXTERNAL_CCA_NAMES = ["BOP", "Tech Crew", "AnG", "BnC", "Devs", "Commotion", "PP", "PS"]


def _load_configs() -> dict:
    """Load readable repo config, with GOOGLE_FORM_CONFIGS as an override."""
    configured = get_settings().google_form_configs
    if configured and configured != "{}":
        try:
            value = json.loads(configured)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            logger.warning("GOOGLE_FORM_CONFIGS is not valid JSON; using config/google_forms.json")

    config_path = Path(__file__).resolve().parents[2] / "config" / "google_forms.json"
    try:
        with config_path.open(encoding="utf-8") as config_file:
            value = json.load(config_file)
            return value if isinstance(value, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("Could not load config/google_forms.json")
        return {}


def configured_form(committee_name: str) -> dict | None:
    """Return the configured test form for a committee, if one exists."""
    configs = _load_configs()

    config = configs.get(committee_name, {})
    if not isinstance(config, dict):
        return None
    return {
        "url": config.get("url"),
        "fields": _normalise_fields(config.get("fields", {})),
        "sections": config.get("sections", []) if isinstance(config.get("sections", []), list) else [],
    }


def configured_forms() -> list[tuple[str, dict]]:
    """Return all configured form destinations, including external committees."""
    configs = _load_configs()
    names = list(dict.fromkeys(EXTERNAL_CCA_NAMES + list(configs)))
    return [(name, form) for name in names if (form := configured_form(name))]


def _normalise_fields(fields: dict) -> dict:
    """Accept the readable object format used by config/google_forms.json."""
    if not isinstance(fields, dict):
        return {}
    result = {}
    for key, value in fields.items():
        if isinstance(value, str):
            value = {"entry_id": value, "source": key, "label": key.replace("_", " ").title()}
        if not isinstance(value, dict) or not value.get("entry_id"):
            continue
        result[key] = {
            "entry_id": value["entry_id"],
            "source": value.get("source", "manual"),
            "label": value.get("label", key.replace("_", " ").title()),
            "type": value.get("type", "text"),
            "required": bool(value.get("required", False)),
            "options": value.get("options", []) if isinstance(value.get("options", []), list) else [],
        }
    return result
