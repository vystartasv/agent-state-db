from setuptools import setup, find_packages

setup(
    name="agent-state-db",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "agent-state=agent_state_db.cli:main",
        ],
    },
)
