"""Entry point wrapper.

The implementation has been refactored into the `edge_server/` package.
"""

from edge_server.main import main as edge_main

if __name__ == "__main__":
    edge_main()
    raise SystemExit(0)
