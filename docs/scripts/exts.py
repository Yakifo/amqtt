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

class DataclassDefaultFactoryExtension(griffe.Extension):
    """Renders the output of a dataclasses field which uses a default factory.

    def other_field_defaults():
        return {'item1': 'value1', 'item2': 'value2'}

    @dataclass
    class MyDataClass:
        my_field: dict[str, Any] = field(default_factory=dict)
        my_other_field: dict[str, Any] = field(default_factory=other_field_defaults)

    instead of documentation rendering this as:

    ```
      class MyDataClass:
        my_field: dict[str, Any] = dict()
        my_other_field: dict[str, Any] = other_field_defaults()
    ```

    it will be displayed with the output of factory functions for more clarity:

    ```
    class MyDataClass:
        my_field: dict[str, Any] = {}
        my_other_field: dict[str, Any] = {'item1': 'value1', 'item2': 'value2'}
    ```

    _note_ : for any custom default factory function, it must be added to the `default_factory_map`
    in this file as `griffe` doesn't provide a straightforward mechanism with its AST to dynamically
    import/call the function.
    """

    def on_attribute_instance(
        self,
        *,
        node: ast.AST | ObjectNode,
        attr: Attribute,
        agent: Visitor | Inspector,
        **kwargs: Any,
    ) -> None:
        """Called for every `node` and/or `attr` on a file's AST."""
        if not hasattr(node, "value"):
            return
        if isinstance(node.value, ast.Call):
            # Search for all of the `default_factory` fields.
            default_factory_value: str | None = None
            for kw in node.value.keywords:
                if kw.arg == "default_factory":
                    # based on the node type, return the proper function name
                    match get_callable_name(kw.value):
                        # `dict` and `list` are common default factory functions
                        case 'dict':
                            default_factory_value = "{}"
                        case 'list':
                            default_factory_value = "[]"

                        case _:
                            # otherwise, see the nodes is in our map for the custom default factory function
                            callable_name = get_callable_name(kw.value)
                            if callable_name in default_factory_map:
                                default_factory_value = pprint.pformat(default_factory_map[callable_name], indent=4, width=80, sort_dicts=False)
                            else:
                                # if not, display as the default
                                default_factory_value = f"{callable_name}()"

            # store the information in the griffe attribute, which is what is passed to the template for rendering
            if "dataclass_ext" not in attr.extra:
                attr.extra["dataclass_ext"] = {}
            attr.extra["dataclass_ext"]["has_default_factory"] = False
            if default_factory_value is not None:
                attr.extra["dataclass_ext"]["has_default_factory"] = True
                attr.extra["dataclass_ext"]["default_factory"] = default_factory_value
