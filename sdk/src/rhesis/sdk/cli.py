import argparse
import sys

from rhesis.sdk import __version__


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rhesis SDK - Testing and validation tools for GenAI applications"
    )

    parser.add_argument("--version", action="version", version=f"rhesis-sdk {__version__}")

    # Since we only have --help and --version,
    # if no arguments are provided, show help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    # Parse arguments but don't store them since we don't use them
    parser.parse_args()


if __name__ == "__main__":
    main()
