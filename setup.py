from setuptools import setup, find_packages
from pathlib import Path

setup(
    name="agent-state-db",
    version="0.1.0",
    description="SQLite+WAL shared state for autonomous AI agents — 19 robots, one whiteboard, no chaos",
    long_description=(Path(__file__).parent / "README.md").read_text(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "agent-state=agent_state_db.cli:main",
        ],
    },
)
