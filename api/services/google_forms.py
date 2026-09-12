import json
import logging

from api.config import get_settings

logger = logging.getLogger(__name__)

EXTERNAL_CCA_NAMES = ["BOP", "Tech Crew", "AnG", "BnC", "Devs", "Commotion", "PP", "PS"]


def configured_form(committee_name: str) -> dict | None:
    """Return the configured test form for a committee, if one exists."""
    try:
        configs = json.loads(get_settings().google_form_configs or "{}")
    except json.JSONDecodeError:
        logger.warning("GOOGLE_FORM_CONFIGS is not valid JSON")
        return None

    config = configs.get(committee_name, {})
    if not isinstance(config, dict):
        return None
    return {
        "url": config.get("url"),
        "fields": config.get("fields", {}) if isinstance(config.get("fields", {}), dict) else {},
        "sections": config.get("sections", []) if isinstance(config.get("sections", []), list) else [],
    }


def configured_forms() -> list[tuple[str, dict]]:
    """Return all configured form destinations, including external committees."""
    try:
        configs = json.loads(get_settings().google_form_configs or "{}")
    except json.JSONDecodeError:
        logger.warning("GOOGLE_FORM_CONFIGS is not valid JSON")
        return []

    if not isinstance(configs, dict):
        configs = {}
    names = list(dict.fromkeys(EXTERNAL_CCA_NAMES + list(configs)))
    return [(name, form) for name in names if (form := configured_form(name))]
