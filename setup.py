import sys

from setuptools import find_packages, setup

import versioneer

install_requires = [
    "prefect >= 1.0.0, < 2.0.0",
    "alembic >= 1.2",
    "ariadne >= 0.8.0",
    "asyncpg >= 0.20",
    "click >= 6.7",
    "coolname >= 1.1",
    "docker >= 3.4",
    "graphql-core < 3.1",
    "httpx >= 0.13.0",
    "json_log_formatter >= 0.3.0",
    "packaging >= 20.0",
    "psycopg2-binary >= 2.7",
    "pydantic >= 1.7",
    "python-slugify >= 1.2",
    "pyyaml >= 3.13",
    "starlette >= 0.13",
    "toml >= 0.9.0",
    "urllib3 >= 1.26.0",
    "uvicorn >= 0.11.4",
]

dev_requires = [
    "black",
    "asynctest >= 0.13",
    "pytest >= 5.0",
    "pytest-asyncio < 0.19.0",
    "pytest-cov",
    "pytest-env",
]


setup(
    name="prefect_server",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="",
    long_description=open("README.md").read(),
    url="https://github.com/prefecthq/server",
    author="Prefect Technologies, Inc.",
    author_email="hello@prefect.io",
    install_requires=install_requires,
    extras_require={"dev": dev_requires},
    scripts=[],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    entry_points="""
        [console_scripts]
        prefect-server=prefect_server.cli:cli
        """,
)
