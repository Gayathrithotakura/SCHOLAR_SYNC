"""Package execution entry point for python -m scholarsync."""

import sys

from scholarsync.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
