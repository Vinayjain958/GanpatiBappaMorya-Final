import importlib
import pkgutil
import sys

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
        if hasattr(attribute, '__module__') and attribute.__module__:
            if attribute.__module__.startswith('src.'):
                get_transitive_imports(attribute.__module__, visited)
                
    return visited

def test_safety_isolation_transitive():
    # Import safety root
    import src.api.v1.safety
    import src.services.safety.contacts
    import src.services.safety.emergency_alerts
    import src.services.safety.safety_resources
    import src.models.safety
    
    # We want to trace all src.* imports from these roots
    roots = [
        'src.api.v1.safety',
        'src.services.safety.contacts',
        'src.services.safety.emergency_alerts',
        'src.services.safety.safety_resources',
        'src.models.safety',
    ]
    
    all_dependencies = set()
    for root in roots:
        get_transitive_imports(root, all_dependencies)
        
    forbidden_modules = [
        'src.services.discovery',
        'src.services.ranking',
        'src.services.feasibility',
        'src.services.compose_itinerary',
        'src.services.experience_composer',
        'src.services.replanning',
        'src.services.provider_intelligence',
        'src.adapters.gemini'
    ]
    
    violations = []
    for dep in all_dependencies:
        for forbidden in forbidden_modules:
            if dep.startswith(forbidden):
                violations.append((dep, forbidden))
                
    assert not violations, f"Safety module transitively depends on forbidden recommendation modules: {violations}"
