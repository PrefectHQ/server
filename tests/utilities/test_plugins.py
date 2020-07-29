import sys
import pytest

import prefect_server
from prefect_server.utilities import plugins


def test_plugin_modules_is_list():
    assert isinstance(prefect_server.config.plugins.modules, list)


def test_import_modules():
    with prefect_server.utilities.tests.set_temporary_config("plugins.modules", ["x"]):
        with pytest.raises(ModuleNotFoundError, match="No module named 'x'"):
            plugins.import_plugins()


class TestAPIRegistry:
    def test_register_function(self):
        @plugins.register_api("tests.my_fn")
        def f(x):
            return x + 1

        assert prefect_server.api.tests.my_fn is f

    def test_overwrite_function(self):
        @plugins.register_api("tests.my_fn")
        def f(x):
            return x + 1

        @plugins.register_api("tests.my_fn")
        def g(x):
            return x + 100

        assert prefect_server.api.tests.my_fn is g

    def test_overwritten_function_is_respected_at_runtime(self):
        @plugins.register_api("tests.my_fn")
        def f(x):
            return x + 1

        def add(x):
            return prefect_server.api.tests.my_fn(x)

        assert add(1) == 2

        @plugins.register_api("tests.my_fn")
        def g(x):
            return x + 100

        assert add(1) == 101
