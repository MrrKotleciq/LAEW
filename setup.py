"""Setup shim for LAEW (backward compatibility).

All packaging metadata lives in pyproject.toml (PEP 621). This file is kept
so legacy ``pip install -e .`` / ``python setup.py ...`` flows keep working.
"""

from setuptools import setup

setup()