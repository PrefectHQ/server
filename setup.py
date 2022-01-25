import sys

from setuptools import find_packages, setup

import versioneer

install_requires = [
    "prefect >= 0.13.0",
    "alembic >= 1.2, < 2.0",
    "ariadne >= 0.8.0, < 0.12.0",
    "asyncpg >= 0.20, < 0.22",
    "click >= 6.7, < 9.0",
    "coolname >= 1.1, < 2.0",
    "docker >= 3.4,< 5.0",
    "graphql-core < 3.1",
    "httpx >= 0.13.0, < 0.14.0",
    "json_log_formatter >= 0.3.0, < 0.4.0",
    "packaging >= 20.0, < 22.0",
    "psycopg2-binary >= 2.7, < 3.0",
    "pydantic >= 1.7, < 1.8",
    "python-slugify >= 1.2,< 6.0",
    "pyyaml >= 3.13, < 6.0",
    "starlette >= 0.13, < 0.14",
    "toml >= 0.9.0, < 0.11",
    "urllib3 >= 1.26.0, < 1.27",
    "uvicorn >= 0.11.4, < 0.12",
]

dev_requires = [
    "black",
    "asynctest >= 0.13, < 0.14",
    "pytest >= 5.0, < 7.0",
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
