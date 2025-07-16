import ast
import json
import pprint
from typing import Any

import griffe
from _griffe.agents.inspector import Inspector
from _griffe.agents.nodes.runtime import ObjectNode
from _griffe.agents.visitor import Visitor
from _griffe.models import Attribute

from amqtt.contexts import default_listeners, default_broker_plugins, default_client_plugins

default_factory_map = {
    'default_listeners': default_listeners(),
    'default_broker_plugins': default_broker_plugins(),
    'default_client_plugins': default_client_plugins()
}

def get_qualified_name(node: ast.AST) -> str | None:
    """Recursively build the qualified name from an AST node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        parent = get_qualified_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
        return node.attr
    elif isinstance(node, ast.Call):
        # e.g., uuid.uuid4()
        return get_qualified_name(node.func)
    return None

def get_fully_qualified_name(call_node):
    """
    Extracts the fully qualified name from an ast.Call node.
    """
    if isinstance(call_node.func, ast.Name):
        # Direct function call (e.g., "my_function(arg)")
        return call_node.func.id
    elif isinstance(call_node.func, ast.Attribute):
        # Method call or qualified name (e.g., "obj.method(arg)" or "module.submodule.function(arg)")
        parts = []
        current = call_node.func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))
    else:
        # Handle other potential cases (e.g., ast.Subscript) if necessary
        return None

def get_callable_name(node):
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{get_callable_name(node.value)}.{node.attr}"
    return None

def evaluate_callable_node(node):
    try:
        # Wrap the node in an Expression so it can be compiled
        expr = ast.Expression(body=node)
        compiled = compile(expr, filename="<ast>", mode="eval")
        return eval(compiled, {"__builtins__": __builtins__, "list": list, "dict": dict})
    except Exception as e:
        return f"<unresolvable: {e}>"

class MyExtension(griffe.Extension):
    def on_instance(
        self,
        node: ast.AST | griffe.ObjectNode,
        obj: griffe.Object,
        agent: griffe.Visitor | griffe.Inspector,
        **kwargs,
    ) -> None:
        """Do something with `node` and/or `obj`."""
        if obj.kind == griffe.Kind.FUNCTION and obj.name == 'default_broker_plugins':
            print(f"my extension on instance {node} > {obj}")

    def on_attribute_instance(
        self,
        *,
        node: ast.AST | ObjectNode,
        attr: Attribute,
        agent: Visitor | Inspector,
        **kwargs: Any,
    ) -> None:
        if not hasattr(node, "value"):
            return
        if isinstance(node.value, ast.Call):
            default_factory_value: str | None = None
            for kw in node.value.keywords:
                if kw.arg == "default_factory":
                    match get_callable_name(kw.value):
                        case 'dict':
                            default_factory_value = "{}"
                        case 'list':
                            default_factory_value = "[]"
                        case _:
                            callable_name = get_callable_name(kw.value)
                            if callable_name in default_factory_map:
                                default_factory_value = pprint.pformat(default_factory_map[callable_name], indent=4, width=80, sort_dicts=False)
                            else:
                                default_factory_value = f"{callable_name}()"

            if "factory" not in attr.extra:
                attr.extra["factory"] = {}
            attr.extra["dataclass_ext"]["has_default_factory"] = False
            if default_factory_value is not None:
                attr.extra["dataclass_ext"]["has_default_factory"] = True
                attr.extra["dataclass_ext"]["default_factory"] = default_factory_value
