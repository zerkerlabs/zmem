from setuptools import setup


setup(
    entry_points={
        "activegraph.packs": [
            "zmem=zerker_memory.pack:pack",
        ],
    }
)
