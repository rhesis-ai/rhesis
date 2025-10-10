"""
CLI interface for the Rhesis release tool.
"""

import argparse
import os
import sys
from pathlib import Path

from .processor import ReleaseProcessor
from .publish import publish_releases
from .utils import error
import json


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser"""
    parser = argparse.ArgumentParser(
        description="Rhesis Platform Release Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s backend --minor frontend --patch sdk --major
  %(prog)s --dry-run backend --patch frontend --minor platform --major
  %(prog)s --no-branch sdk --patch  # Skip branch creation
  %(prog)s --publish  # Create tags and GitHub releases from current release branch
  %(prog)s --publish --dry-run  # Preview what would be published

Components:
  backend, frontend, worker, chatbot, polyphemus, sdk
  platform (for platform-wide releases)

Version Types:
  --patch   (0.0.X)
  --minor   (0.X.0)  
  --major   (X.0.0)

Publish Mode:
  Use --publish to create git tags and GitHub releases based on the current
  release branch. This will:
  • Parse component versions from the current release branch
  • Create missing git tags for each component
  • Push tags to remote repository
  • Create GitHub releases (requires gh CLI)
  • Ask for confirmation before making changes
        """
    )
    
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--no-branch', action='store_true',
                       help='Skip automatic release branch creation')
    parser.add_argument('--gemini-key', type=str,
                       help='Gemini API key for changelog generation')
    parser.add_argument('--bump-config-file', type=str,
                       help='Bump config file')
    parser.add_argument('--publish', action='store_true',
                       help='Create git tags and GitHub releases from current release branch')
    
    return parser


def parse_component_arguments(remaining_args: list) -> dict:
    """Parse component arguments from remaining command line arguments"""
    component_bumps = {}
    i = 0
    while i < len(remaining_args):
        if remaining_args[i] in ['backend', 'frontend', 'worker', 'chatbot', 'polyphemus', 'sdk', 'platform']:
            component = remaining_args[i]
            if i + 1 < len(remaining_args) and remaining_args[i + 1] in ['--patch', '--minor', '--major']:
                bump_type = remaining_args[i + 1][2:]  # Remove --
                component_bumps[component] = bump_type
                i += 2
            else:
                error(f"Missing version type for component: {component}")
                error("Must be one of: --patch, --minor, --major")
                return {}
        else:
            error(f"Unknown argument: {remaining_args[i]}")
            return {}
    
    return component_bumps


def find_repository_root() -> Path:
    """Find the repository root directory"""
    repo_root = Path.cwd()
    while repo_root != repo_root.parent:
        if (repo_root / '.git').exists():
            break
        repo_root = repo_root.parent
    else:
        error("Not in a git repository")
        sys.exit(1)
    
    return repo_root


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
        with open(bump_config_file, 'r') as f:
            component_bumps = json.load(f)
    else:
    # Handle regular release mode
        component_bumps = parse_component_arguments(remaining)
    
    if not component_bumps:
        if not remaining:  # No arguments provided at all
            error("No components specified for release")
            parser.print_help()
        sys.exit(1)
    
    # Get Gemini API key from environment if not provided
    gemini_key = args.gemini_key or os.environ.get('GEMINI_API_KEY', '')
    
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


if __name__ == '__main__':
    main() 