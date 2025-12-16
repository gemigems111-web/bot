"""Setup script for PyQuotex Integration."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pyquotex-integration",
    version="0.1.0",
    author="PyQuotex Integration Team",
    description="Comprehensive wrapper for pyquotex.stable_api with production-ready features",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/pyquotex-integration",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "quotexapi>=1.0.0",
        "asyncio-atexit>=1.0.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "pylint>=2.17.0",
        ],
    },
)
