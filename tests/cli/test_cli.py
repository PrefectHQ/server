import subprocess


def test_cli_is_installed():
    output = subprocess.check_output(["prefect-server"])
    assert b"The Prefect Server CLI" in output
