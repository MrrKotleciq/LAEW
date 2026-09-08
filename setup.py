"""Setup configuration for LAEW package."""

from setuptools import setup, find_packages

setup(
    name="laew",
    version="0.1.0",
    description="Local AI Engineering Workspace",
    author="LAEW Contributors",
    python_requires=">=3.10",
    packages=find_packages(exclude=["tests*"]),
    install_requires=[
        "pyyaml>=6.0",
        "requests>=2.31.0",
        "numpy>=1.24.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "html2text>=2020.1.16",
            "chromadb>=0.4.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "laew=laew.cli:main",
        ],
    },
)
