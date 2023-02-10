from setuptools import setup

setup(
    name="libc-tools",
    version="0.0.1",
    install_requires=[],
    extras_require={
    },
    entry_points={
        "console_scripts": [
            "prepare-lib = prepare_lib.main:main",
            "extract-lib = extract_lib.main:main",
            "patchlib = patchlib.main:main",
        ]
    }
)
