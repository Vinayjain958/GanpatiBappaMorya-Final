"""Transitive isolation check for the Wikimedia image system — mirrors
tests/test_safety_isolation.py's pattern. The image adapter/matching
service must never import recommendation/ranking/safety/Gemini modules;
it only uses generic HTTP/cache/rate-limit/geo infrastructure."""

import importlib


def get_transitive_imports(module_name, visited=None):
    if visited is None:
        visited = set()
    if module_name in visited:
        return visited

    visited.add(module_name)
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return visited

    for attribute_name in dir(module):
        attribute = getattr(module, attribute_name)
        if hasattr(attribute, "__module__") and attribute.__module__:
            if attribute.__module__.startswith("src."):
                get_transitive_imports(attribute.__module__, visited)

    return visited


def test_image_system_isolation_transitive():
    import src.adapters.wikimedia_commons
    import src.services.experience_images

    roots = [
        "src.adapters.wikimedia_commons",
        "src.services.experience_images",
    ]

    all_dependencies = set()
    for root in roots:
        get_transitive_imports(root, all_dependencies)

    forbidden_modules = [
        "src.services.discovery",
        "src.services.ranking",
        "src.services.feasibility",
        "src.services.compose_itinerary",
        "src.services.experience_composer",
        "src.services.replanning",
        "src.services.provider_intelligence",
        "src.services.safety",
        "src.adapters.gemini",
    ]

    violations = []
    for dep in all_dependencies:
        for forbidden in forbidden_modules:
            if dep.startswith(forbidden):
                violations.append((dep, forbidden))

    assert not violations, f"Image system transitively depends on forbidden modules: {violations}"
