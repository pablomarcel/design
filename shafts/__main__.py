try:
    from .cli import main
except ImportError:  # pragma: no cover - local package execution shim
    from cli import main

raise SystemExit(main())
