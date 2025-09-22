#!/usr/bin/env python3
"""
CI/CD Security Check: Organization Filtering Validation

This script scans the codebase for database queries that may be missing
organization filtering, helping prevent cross-tenant data access vulnerabilities.

Usage:
    python scripts/check_organization_filtering.py [--fix] [--verbose]

Exit codes:
    0: No issues found
    1: Issues found that need attention
    2: Script error
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
import argparse


class OrganizationFilterChecker:
    """Checks for missing organization filtering in database queries"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.issues: List[Dict] = []
        
        # Models that require organization filtering
        self.organization_models = {
            'Behavior', 'Category', 'Comment', 'Demographic', 'Dimension',
            'Metric', 'Model', 'Prompt', 'Risk', 'Source', 'Status', 
            'Tag', 'Task', 'Test', 'TestResult', 'TestRun', 'TestSet',
            'Token', 'Topic', 'TypeLookup', 'UseCase', 'Endpoint'
        }
        
        # Query patterns that need organization filtering
        self.query_patterns = [
            r'db\.query\([^)]*\)',
            r'session\.query\([^)]*\)',
            r'\.query\([^)]*\)',
        ]
        
        # Safe patterns that don't need organization filtering
        self.safe_patterns = [
            r'User\.query',  # User queries handled separately
            r'Organization\.query',  # Organization queries don't need filtering
            r'\.query\(func\.count',  # Count queries often don't need filtering
            r'\.query\([^)]*\)\.filter\([^)]*organization_id[^)]*\)',  # Already has org filtering
        ]
        
        # Directories to scan
        self.scan_dirs = [
            'apps/backend/src/rhesis/backend/app/crud.py',
            'apps/backend/src/rhesis/backend/app/services/',
            'apps/backend/src/rhesis/backend/app/routers/',
            'apps/backend/src/rhesis/backend/app/auth/',
            'apps/backend/src/rhesis/backend/app/utils/',
        ]

    def check_file(self, file_path: Path) -> List[Dict]:
        """Check a single file for organization filtering issues"""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                # Skip comments and docstrings
                if line.strip().startswith('#') or '"""' in line or "'''" in line:
                    continue
                    
                # Check for query patterns
                for pattern in self.query_patterns:
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        if self._is_potentially_unsafe_query(line, match.group()):
                            issues.append({
                                'file': str(file_path),
                                'line': line_num,
                                'content': line.strip(),
                                'issue': 'Potential missing organization filtering',
                                'severity': 'HIGH' if any(model in line for model in self.organization_models) else 'MEDIUM'
                            })
                            
        except Exception as e:
            if self.verbose:
                print(f"Error checking {file_path}: {e}")
                
        return issues

    def _is_potentially_unsafe_query(self, line: str, query_match: str) -> bool:
        """Determine if a query might be missing organization filtering"""
        
        # Check if it's a safe pattern
        for safe_pattern in self.safe_patterns:
            if re.search(safe_pattern, line):
                return False
        
        # IMPORTANT: Queries by unique ID are SAFE - UUIDs are globally unique
        id_based_patterns = [
            r'\.filter\([^)]*\.id\s*==',  # .filter(Model.id == uuid)
            r'\.filter_by\(id\s*=',       # .filter_by(id=uuid)
            r'\.get\(',                   # .get(uuid) - primary key lookup
        ]
        
        for id_pattern in id_based_patterns:
            if re.search(id_pattern, line):
                return False  # ID-based queries are safe
                
        # Check if it queries an organization-aware model
        for model in self.organization_models:
            if model in query_match:
                # Check if the line already has organization filtering
                if 'organization_id' in line or 'org_id' in line:
                    return False
                    
                # Check if it's a safe ID-based query
                if any(re.search(pattern, line) for pattern in id_based_patterns):
                    return False
                    
                return True  # Potentially unsafe
                
        # Check for generic query patterns that might be unsafe
        if '.query(' in query_match and '.filter(' not in line:
            return True
            
        return False

    def scan_codebase(self, root_dir: Path) -> List[Dict]:
        """Scan the entire codebase for organization filtering issues"""
        all_issues = []
        
        for scan_path in self.scan_dirs:
            full_path = root_dir / scan_path
            
            if full_path.is_file():
                # Single file
                all_issues.extend(self.check_file(full_path))
            elif full_path.is_dir():
                # Directory - scan all Python files
                for py_file in full_path.rglob('*.py'):
                    all_issues.extend(self.check_file(py_file))
                    
        return all_issues

    def generate_report(self, issues: List[Dict]) -> str:
        """Generate a formatted report of issues"""
        if not issues:
            return "✅ No organization filtering issues found!"
            
        report = ["🔒 SECURITY: Organization Filtering Issues Found", "=" * 60, ""]
        
        # Group by severity
        high_issues = [i for i in issues if i['severity'] == 'HIGH']
        medium_issues = [i for i in issues if i['severity'] == 'MEDIUM']
        
        if high_issues:
            report.extend([
                f"🚨 HIGH SEVERITY ISSUES ({len(high_issues)}):",
                "-" * 40
            ])
            for issue in high_issues:
                report.extend([
                    f"File: {issue['file']}:{issue['line']}",
                    f"Issue: {issue['issue']}",
                    f"Code: {issue['content']}",
                    ""
                ])
                
        if medium_issues:
            report.extend([
                f"⚠️  MEDIUM SEVERITY ISSUES ({len(medium_issues)}):",
                "-" * 40
            ])
            for issue in medium_issues:
                report.extend([
                    f"File: {issue['file']}:{issue['line']}",
                    f"Issue: {issue['issue']}",
                    f"Code: {issue['content']}",
                    ""
                ])
                
        report.extend([
            "RECOMMENDATIONS:",
            "- Add organization_id parameter to functions with HIGH severity issues",
            "- Apply .filter(Model.organization_id == organization_id) to queries",
            "- Review MEDIUM severity issues for potential security implications",
            "- Run security tests to verify fixes: pytest -m security",
            ""
        ])
        
        return "\n".join(report)


def create_github_action() -> str:
    """Create a GitHub Action workflow for organization filtering checks"""
    return """name: Security - Organization Filtering Check

on:
  pull_request:
    paths:
      - 'apps/backend/src/**/*.py'
      - 'scripts/check_organization_filtering.py'
  push:
    branches: [main, develop]
    paths:
      - 'apps/backend/src/**/*.py'

jobs:
  check-organization-filtering:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Check Organization Filtering
        run: |
          python scripts/check_organization_filtering.py --verbose
          
      - name: Run Security Tests
        run: |
          cd apps/backend
          pip install -e .
          pytest ../../tests/backend/test_security_fixes.py -v
          
      - name: Comment PR (on failure)
        if: failure()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '🔒 **Security Check Failed**: Organization filtering issues detected. Please review the security check results and ensure all database queries include proper organization filtering to prevent cross-tenant data access.'
            })
"""


def create_pre_commit_hook() -> str:
    """Create a pre-commit hook for organization filtering checks"""
    return """#!/bin/bash
# Pre-commit hook: Organization Filtering Security Check

echo "🔒 Running organization filtering security check..."

# Run the security check
python scripts/check_organization_filtering.py

exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo ""
    echo "❌ Security check failed! Please fix organization filtering issues before committing."
    echo "   Run: python scripts/check_organization_filtering.py --verbose"
    echo "   Test: pytest tests/backend/test_security_fixes.py -v"
    exit 1
fi

echo "✅ Organization filtering security check passed!"
exit 0
"""


def main():
    parser = argparse.ArgumentParser(description='Check for missing organization filtering in database queries')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--fix', action='store_true', help='Generate fix suggestions (not implemented)')
    parser.add_argument('--setup-ci', action='store_true', help='Setup CI/CD integration files')
    
    args = parser.parse_args()
    
    try:
        # Find the project root
        current_dir = Path.cwd()
        project_root = current_dir
        
        # Look for project markers to find root
        for parent in [current_dir] + list(current_dir.parents):
            if (parent / 'apps' / 'backend').exists() or (parent / 'pyproject.toml').exists():
                project_root = parent
                break
                
        if args.verbose:
            print(f"Scanning project root: {project_root}")
            
        # Setup CI/CD files if requested
        if args.setup_ci:
            # Create GitHub Action
            gh_action_path = project_root / '.github' / 'workflows' / 'security-organization-filtering.yml'
            gh_action_path.parent.mkdir(parents=True, exist_ok=True)
            gh_action_path.write_text(create_github_action())
            print(f"Created GitHub Action: {gh_action_path}")
            
            # Create pre-commit hook
            hook_path = project_root / '.git' / 'hooks' / 'pre-commit'
            hook_path.write_text(create_pre_commit_hook())
            hook_path.chmod(0o755)
            print(f"Created pre-commit hook: {hook_path}")
            
            print("✅ CI/CD integration files created successfully!")
            return 0
        
        # Run the security check
        checker = OrganizationFilterChecker(verbose=args.verbose)
        issues = checker.scan_codebase(project_root)
        
        # Generate and print report
        report = checker.generate_report(issues)
        print(report)
        
        # Return appropriate exit code
        if issues:
            high_severity_count = len([i for i in issues if i['severity'] == 'HIGH'])
            if high_severity_count > 0:
                print(f"\n❌ Found {high_severity_count} HIGH severity security issues!")
                return 1
            else:
                print(f"\n⚠️  Found {len(issues)} MEDIUM severity issues to review.")
                return 0
        else:
            print("\n✅ No organization filtering issues detected!")
            return 0
            
    except Exception as e:
        print(f"❌ Script error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2


if __name__ == '__main__':
    sys.exit(main())
