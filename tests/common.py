"""Shared helpers for static tests of the public monitoring repository."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

class UniqueMappingLoader(yaml.SafeLoader):
    """Fail on duplicated YAML keys that silently override configuration."""


def construct_unique_mapping(loader, node):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in mapping:
            raise ValueError(f"Duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}")
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping

UniqueMappingLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_unique_mapping)


def load_yaml(relative_path):
    path = ROOT / relative_path
    return yaml.load(path.read_text(encoding='utf-8'), Loader=UniqueMappingLoader)
