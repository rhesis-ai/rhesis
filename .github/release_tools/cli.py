"""
CLI interface for the Rhesis release tool.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from .config import COMPONENTS, follows_platform
from .processor import ReleaseProcessor
from .publish import publish_releases
from .utils import error, find_repository_root


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser"""
    parser = argparse.ArgumentParser(
        description="Rhesis Platform Release Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s platform --minor sdk --patch
  %(prog)s --dry-run platform --major polyphemus --minor
  %(prog)s --no-branch sdk --patch  # Skip branch creation
  %(prog)s --publish  # Create tags and GitHub releases from current release branch
  %(prog)s --publish --dry-run  # Preview what would be published

Components:
  platform (backend and frontend ship with it and take its version)
  sdk, polyphemus, ee-backend

Version Types:
  --patch   (0.0.X)
  --minor   (0.X.0)  
  --major   (X.0.0)

Publish Mode:
  Use --publish to create git tags and GitHub releases based on the current
  release branch. This will:
  • Read each component's version off the release branch
  • Create missing git tags for each component
  • Push tags to remote repository
  • Create GitHub releases (requires gh CLI)
  • Ask for confirmation before making changes
        """,
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--no-branch", action="store_true", help="Skip automatic release branch creation"
    )
    parser.add_argument("--gemini-key", type=str, help="Gemini API key for changelog generation")
    parser.add_argument("--bump-config-file", type=str, help="Bump config file")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Create git tags and GitHub releases from current release branch",
    )

    return parser


def bumpable_components() -> list[str]:
    """Components a release can bump: everything with its own version, plus the platform"""
    return ["platform"] + [name for name in COMPONENTS if not follows_platform(name)]


def reject_platform_followers(component_bumps: dict) -> bool:
    """Refuse a bump for a component that takes the platform's version.

    release_config.json lives on main, so a stale one can still name backend or frontend.
    """
    named = [component for component in component_bumps if follows_platform(component)]
    if not named:
        return True

    error(f"These components ship with the platform and cannot be bumped: {', '.join(named)}")
    error("Bump 'platform' instead - they take its version automatically.")
    return False


def parse_component_arguments(remaining_args: list) -> dict:
    """Parse component arguments from remaining command line arguments"""
    component_bumps = {}
    i = 0
    while i < len(remaining_args):
        if remaining_args[i] in bumpable_components():
            component = remaining_args[i]
            if i + 1 < len(remaining_args) and remaining_args[i + 1] in [
                "--patch",
                "--minor",
                "--major",
            ]:
                bump_type = remaining_args[i + 1][2:]  # Remove --
                component_bumps[component] = bump_type
                i += 2
            else:
                error(f"Missing version type for component: {component}")
                error("Must be one of: --patch, --minor, --major")
                return {}
        elif follows_platform(remaining_args[i]):
            reject_platform_followers({remaining_args[i]: ""})
            return {}
        else:
            error(f"Unknown argument: {remaining_args[i]}")
            error(f"Must be one of: {', '.join(bumpable_components())}")
            return {}

    return component_bumps


def main():
    """Main CLI entry point"""
    parser = create_argument_parser()

    # Parse known args to handle component arguments
    args, remaining = parser.parse_known_args()

    # Find repository root
    repo_root = find_repository_root()

    # Handle publish mode
    if args.publish:
        if remaining:
            error("--publish cannot be used with component arguments")
            error("Use --publish on a release branch to create tags and GitHub releases")
            sys.exit(1)

        try:
            success = publish_releases(repo_root, args.dry_run)
            sys.exit(0 if success else 1)
        except KeyboardInterrupt:
            error("Publish cancelled by user")
            sys.exit(1)
        except Exception as e:
            error(f"Unexpected error during publish: {e}")
            sys.exit(1)
    if args.bump_config_file:
        bump_config_file = args.bump_config_file
        bump_config_file = Path(repo_root, bump_config_file)
        with open(bump_config_file, "r") as f:
            component_bumps = json.load(f)
        if not reject_platform_followers(component_bumps):
            sys.exit(1)
    else:
        # Handle regular release mode
        component_bumps = parse_component_arguments(remaining)

    if not component_bumps:
        if not remaining:  # No arguments provided at all
            error("No components specified for release")
            parser.print_help()
        sys.exit(1)

    # Get Gemini API key from environment if not provided
    gemini_key = args.gemini_key or os.environ.get("GEMINI_API_KEY", "")

    # Create release processor and run
    processor = ReleaseProcessor(repo_root, args.dry_run, gemini_key, args.no_branch)

    try:
        success = processor.run(component_bumps)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        error("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
