"""Native function schemas derived only from the active LAEW tool registry."""

import inspect
import types
from typing import get_args, get_origin, get_type_hints, Union


def _type_schema(annotation):
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        options = [a for a in get_args(annotation) if a is not type(None)]
        return _type_schema(options[0]) if len(options) == 1 else {}
    if origin is list:
        return {"type": "array", "items": _type_schema(get_args(annotation)[0])}
    return {"type": {str: "string", int: "integer", float: "number", bool: "boolean",
                     dict: "object", list: "array"}[annotation]} if annotation in (str, int, float, bool, dict, list) else {}


def tool_definitions(tools):
    """One function per documented operation; never expose private helpers."""
    definitions = []
    for name, tool in tools.items():
        for operation, info in (tool.operations or {}).items():
            method = getattr(tool, "_" + operation, None) or getattr(tool, operation, None)
            signature = inspect.signature(method) if callable(method) else None
            hints = get_type_hints(method) if callable(method) else {}
            properties, required = {}, []
            for param in info.get("params", []):
                entry = signature.parameters.get(param) if signature else None
                properties[param] = info.get("properties", {}).get(param, _type_schema(hints.get(param, str)))
                if entry is not None and entry.default is inspect.Parameter.empty:
                    required.append(param)
                elif entry is None and param in info.get("required", []):
                    required.append(param)
            definitions.append({"type": "function", "name": name + "__" + operation,
                "description": (tool.description or name) + "\n" + info.get("description", operation),
                "parameters": {"type": "object", "properties": properties,
                               "required": required, "additionalProperties": False}, "strict": False})
    return definitions


def validate_arguments(definition, args):
    """Validate the schema subset we emit before prompting for permission."""
    schema = definition["parameters"]
    if not isinstance(args, dict):
        return "Function arguments must be a JSON object."
    if set(args) - set(schema["properties"]):
        return "Unknown function argument."
    if set(schema["required"]) - set(args):
        return "Missing required function argument."
    types_by_name = {"string": str, "integer": int, "number": (int, float), "boolean": bool,
                     "object": dict, "array": list}
    for key, value in args.items():
        kind = schema["properties"][key].get("type")
        if kind and (not isinstance(value, types_by_name[kind]) or
                     (kind in {"integer", "number"} and isinstance(value, bool))):
            return f"Invalid type for argument '{key}': expected {kind}."
    return None
