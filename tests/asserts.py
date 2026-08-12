import warnings
from contextlib import contextmanager

"""Assertions not provided by `pytest` or `mock`."""

@contextmanager
def does_not_warn(category=Warning):
    with warnings.catch_warnings():
        warnings.simplefilter("error", category)
        yield

def assert_not_called_with_param(mock_obj, param_name=None, param_value=None):
    """Asserts a specific param name or value was never passed to the mock."""
    for args, kwargs in mock_obj.call_args_list:
        # Check keyword arguments
        if param_name in kwargs and kwargs[param_name] == param_value:
            raise AssertionError(f"Mock was called with unexpected kwarg {param_name}={param_value}")

        # Check positional arguments
        if param_value in args and param_name is None:
            raise AssertionError(f"Mock was called with unexpected positional arg {param_value}")

