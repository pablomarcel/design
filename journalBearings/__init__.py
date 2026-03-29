"""journalBearings package.

CLI app for Shigley Chapter 12 journal-bearing selection workflows.
Current scope:
    - Type 1 problems: non-pressure-fed journal bearings with given steady-state viscosity
    - minimum film thickness
    - coefficient of friction
    - volumetric flow rate
    - maximum film pressure
"""

__all__ = [
    "apis",
    "app",
    "cli",
    "core",
    "in_out",
    "utils",
]

__version__ = "0.3.0"
