"""
Common command-line argument parsing for Penelope examples.
"""

import argparse


def create_base_parser(description: str, example_name: str) -> argparse.ArgumentParser:
    """
    Create a base argument parser with common options for Penelope examples.
    
    Args:
        description: Description of the example
        example_name: Name of the example file (e.g., "basic_example.py")
    
    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  uv run python {example_name} --endpoint-id 2d8d2060-b85a-46fa-b299-e3c940598088
  uv run python {example_name} -e your-endpoint-id --verbose
  uv run python {example_name} -e your-endpoint-id --max-iterations 20
        """
    )
    
    parser.add_argument(
        "--endpoint-id", "-e",
        required=True,
        help="Rhesis endpoint ID to test"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=True,
        help="Enable verbose output (default: True)"
    )
    
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of iterations (default: 10)"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress verbose output"
    )
    
    return parser


def parse_args_with_endpoint(description: str, example_name: str):
    """
    Parse common arguments for Penelope examples.
    
    Args:
        description: Description of the example
        example_name: Name of the example file
    
    Returns:
        Parsed arguments namespace
    """
    parser = create_base_parser(description, example_name)
    args = parser.parse_args()
    
    # Handle quiet flag
    if args.quiet:
        args.verbose = False
    
    return args

