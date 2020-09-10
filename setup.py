import sys

from setuptools import find_packages, setup

import versioneer

install_requires = [
    "prefect >= 0.13.0",
    "alembic >= 1.2, < 2.0",
    "ariadne >= 0.8.0, < 0.12.0",
    "asyncpg >= 0.20, < 0.21",
    "click >= 6.7, <8.0",
    "coolname >= 1.1, < 2.0",
    "docker >= 3.4,< 5.0",
    "graphql-core < 3.1",
    "httpx >= 0.13.0, < 0.14.0",
    "json_log_formatter >= 0.3.0, < 0.4.0",
    "psycopg2-binary >= 2.7, < 3.0",
    # pin below 1.6 pending https://github.com/samuelcolvin/pydantic/issues/1710
    "pydantic >= 1.5, < 1.6",
    "python-slugify >= 1.2,< 5.0",
    "starlette >= 0.13, < 0.14",
    "toml >= 0.9.0, < 0.11",
    "uvicorn >= 0.11.4, < 0.12",
    "pyyaml >= 3.13, < 6.0",
    "packaging >= 20.0, < 20.4",
]

dev_requires = [
    "black",
    "asynctest >= 0.13, < 0.14",
    "pytest >= 5.0, < 6.0",
    "pytest-asyncio",
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
