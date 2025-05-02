from setuptools import setup

setup(
    name="shlib-tools",
    version="0.0.1",
    install_requires=[],
    extras_require={
    },
    entry_points={
        "console_scripts": [
            "extract-lib = extract_lib.main:main",
            "patchlib = patchlib.main:main",
        ]
    }
)
