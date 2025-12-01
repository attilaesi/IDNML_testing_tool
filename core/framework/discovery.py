# core/framework/discovery.py

import importlib
import pkgutil
import inspect
import sys
from pathlib import Path
from typing import Dict, List, Type, Tuple

from core.base_test import BaseTest


def _iter_test_module_names() -> List[str]:
    """
    Dynamically discover and yield all test module names under the top-level
    'tests' directory — including all subpackages like prebid_tests, gpt_tests, etc.

    We include any module that contains "test" in its module name.
    """
    root_pkg = "tests"

    # discovery.py is in core/framework/, so:
    #   discovery.py -> framework -> core -> project_root
    tests_root = Path(__file__).resolve().parent.parent.parent / "tests"

    # Ensure tests_root’s parent (project root) is on sys.path
    tests_root_parent = tests_root.parent
    if str(tests_root_parent) not in sys.path:
        sys.path.insert(0, str(tests_root_parent))

    # Import the top-level tests package
    try:
        importlib.import_module(root_pkg)
    except Exception as e:
        print(f"⚠️  Could not import root package {root_pkg}: {e}")
        return []

    module_names: List[str] = []

    # Recursively walk all packages and collect .py modules that look like test files
    for _importer, modname, _ispkg in pkgutil.walk_packages(
        [str(tests_root)], prefix=f"{root_pkg}."
    ):
        # Skip dunder/private
        if modname.split(".")[-1].startswith("_"):
            continue
        # Only keep modules that look like tests by name
        if "test" in modname.lower():
            module_names.append(modname)

    return module_names


def discover_tests() -> Tuple[Dict[str, Type[BaseTest]], Dict[str, List[str]]]:
    """
    Discover all test classes.

    Returns:
      - tests: name -> class
      - test_categories: category -> [names]
    """
    tests: Dict[str, Type[BaseTest]] = {}
    test_categories: Dict[str, List[str]] = {}

    for module_name in _iter_test_module_names():
        try:
            test_module = importlib.import_module(module_name)
        except Exception as e:
            print(f"❌ Failed to import {module_name}: {e}")
            continue

        # Determine category from folder name (informational only)
        if ".prebid_tests." in module_name:
            category = "PREBID"
        elif ".gpt_tests." in module_name:
            category = "GPT"
        else:
            category = "OTHER"

        test_categories.setdefault(category, [])

        # Collect concrete subclasses defined in this module
        for name, obj in inspect.getmembers(test_module, inspect.isclass):
            if obj.__module__ != module_name:
                continue
            if not issubclass(obj, BaseTest) or obj is BaseTest:
                continue

            tests[name] = obj
            test_categories[category].append(name)
            print(f"Discovered test: {name} in category {category}")

    return tests, test_categories


def get_tests_by_category(
    tests: Dict[str, Type[BaseTest]],
    test_categories: Dict[str, List[str]],
    category: str,
) -> List[Type[BaseTest]]:
    """Get all tests in a specific category."""
    test_names = test_categories.get(category.upper(), [])
    return [tests[name] for name in test_names if name in tests]