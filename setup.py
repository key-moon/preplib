from setuptools import setup

setup(
    name="shlib-tools",
    version="0.0.1",
    install_requires=[
        "appdirs==1.4.4"
    ],
    extras_require={},
    entry_points={
        "console_scripts": [
            "extractlib = extractlib.main:main",
            "patchlib = patchlib.main:main",
        ]
    }
)
