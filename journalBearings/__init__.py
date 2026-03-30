"""journalBearings package.

CLI app for journal-bearing selection workflows.
Current scope:
    - finite journal bearing table driven automation
    - minimum film thickness
    - coefficient of friction
    - volumetric flow rate
    - maximum film pressure
    - temperature rise with iterative viscosity update
    - self-contained bearing steady-state solution
    - pressure-fed circumferential-groove bearings
"""

__all__ = [
    'apis',
    'app',
    'cli',
    'core',
    'in_out',
    'utils',
]

__version__ = '0.7.0'
