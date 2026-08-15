"""
PluginManifest dataclass for the freeduction plugin system.

See ARCHITECTURE.md for the full component relationship diagram and lifecycle walkthrough.
Single responsibility: define and validate the plugin.json manifest schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class PluginManifest:
    """Structured representation of a community plugin's plugin.json manifest."""

    id: str                  # unique slug, e.g. "my-cool-plugin"
    name: str                # Python identifier, e.g. "my_cool_plugin"
    display_name: str        # human-readable, e.g. "My Cool Plugin"
    version: str             # semver, e.g. "1.0.0"
    author: str              # author name or handle
    description: str         # one-line description
    category: str            # one of the standard categories
    min_api_version: str     # minimum PLUGIN_API_VERSION required
    entry_point: str         # Python filename, e.g. "my_cool_plugin.py"
    dependencies: List[str]  # list of plugin `name` strings this depends on

    _REQUIRED_FIELDS = (
        "id", "name", "display_name", "version", "author",
        "description", "category", "min_api_version", "entry_point", "dependencies",
    )

    @classmethod
    def from_dict(cls, data: dict) -> "PluginManifest":
        """Create a PluginManifest from a plain dict (e.g. parsed plugin.json).

        Raises:
            KeyError: if any required field is absent, with a message listing them.
        """
        missing = [f for f in cls._REQUIRED_FIELDS if f not in data]
        if missing:
            raise KeyError(f"plugin.json missing required fields: {missing}")

        return cls(
            id=data["id"],
            name=data["name"],
            display_name=data["display_name"],
            version=data["version"],
            author=data["author"],
            description=data["description"],
            category=data["category"],
            min_api_version=data["min_api_version"],
            entry_point=data["entry_point"],
            dependencies=data["dependencies"],
        )

    def to_dict(self) -> dict:
        """Return all manifest fields as a plain dict."""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "category": self.category,
            "min_api_version": self.min_api_version,
            "entry_point": self.entry_point,
            "dependencies": self.dependencies,
        }
