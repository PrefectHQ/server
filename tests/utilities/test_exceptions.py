import pytest
from prefect_server.utilities.exceptions import reraise_as_api_error, APIError
from prefect_server.utilities.logging import get_logger


class TestReraiseAsAPIError:
    async def test_does_not_capture_other_exceptions(self):
        with pytest.raises(ValueError, match="TEST"):
            async with reraise_as_api_error(TypeError):
                raise ValueError("TEST")

    async def test_captures_specified_exception(self):
        with pytest.raises(APIError) as exc_info:
            async with reraise_as_api_error(ValueError):
                raise ValueError("TEST")
        assert "TEST" not in str(exc_info)

    @pytest.mark.parametrize("match", ["TEST", "TEST (FOO|BAR)", "FOO"])
    async def test_captures_specified_exception_with_match(self, match):
        # Parameterized to test with substring match and regex
        with pytest.raises(APIError) as exc_info:
            async with reraise_as_api_error(ValueError, match=match):
                raise ValueError("TEST FOO")
        assert "TEST" not in str(exc_info)

    async def test_does_not_capture_other_exception_with_match(self):
        with pytest.raises(ValueError):
            async with reraise_as_api_error(ValueError, match="TEST BAR"):
                raise ValueError("TEST FOO")

    async def test_logs_exception_information(self, caplog):
        with pytest.raises(APIError):
            async with reraise_as_api_error(Exception, logger=get_logger()):
                raise ValueError("Test error")
        assert caplog.records
        log = caplog.records[0]
        # Exc info attached
        assert "ValueError: Test error" in log.exc_text
        # Message includes original error message
        assert log.message == "Encountered internal API exception: Test error"
        # Logs as error
        assert log.levelname == "ERROR"


def test_api_error_is_always_same_message():
    assert str(APIError()) == APIError.__message__


def test_api_error_does_not_allow_custom_message():
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        APIError(message="Extra")

    with pytest.raises(TypeError):
        APIError("Foo")
