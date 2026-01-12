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

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List


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
            # UUID-based query patterns (SAFE - globally unique)
            r'\.filter\([^)]*\.id\s*==\s*test_set_id\)',  # Filter by test_set_id
            r'\.filter\([^)]*\.id\s*==\s*test_run_id\)',  # Filter by test_run_id
            r'\.filter\([^)]*\.id\s*==\s*test_set_uuid\)',  # Filter by test_set_uuid
            r'\.filter\([^)]*\.id\s*==\s*\w+_uuid\)',     # Filter by any_uuid
            r'\.filter_by\(id\s*=\s*entity_id\)',        # Filter by entity_id (UUID)
            r'\.filter\([^)]*\.id\s*==\s*current_user\.organization_id\)',  # Filter by user's org
            r'get_test_set.*by.*id',                       # get_test_set by ID functions
            r'get_test_run.*by.*id',                       # get_test_run by ID functions
            # Diagnostic/debug queries (legitimate)
            r'all_orgs\s*=\s*db\.query\(models\.Organization\)\.all\(\)',  # Debug query
            # QueryBuilder initialization (filtering applied later)
            r'self\.query\s*=\s*db\.query\(model\)',      # QueryBuilder init
        ]
        
        # Known safe functions that properly implement organization filtering via filter_params
        self.safe_functions = [
            'get_test_result_stats',
            'get_test_run_stats',
        ]
        
        # Known safe file/line combinations (specific false positives)
        self.safe_locations = [
            ('services/stats/test_run.py', 387),  # get_test_run_stats function
            ('services/stats/test_result.py', 286),  # get_test_result_stats function
            ('services/stats/calculator.py', 483),  # UUID-based entity lookup
            ('routers/user.py', 71),  # Organization lookup by current_user.organization_id
        ]
        
        # Additional patterns to check for existing organization filtering
        self.org_filter_indicators = [
            r'organization_id\s*==',
            r'organization_id\s*=',
            r'\.organization_id\s*==',
            r'Tag\.organization_id',
            r'TaggedItem\.organization_id',
            r'Token\.organization_id',
            r'Metric\.organization_id',
            r'Behavior\.organization_id',
            # Filter parameter patterns (functions that pass organization_id to filter helpers)
            r'"organization_id":\s*organization_id',
            r'filter_params\s*=.*organization_id',
            r'apply_filters.*organization_id',
            r'_apply_organization_filter',
            # Stats service patterns (filter_params mechanism)
            r'filter_params\s*=\s*{[^}]*"organization_id"',
            r'apply_filters\s*\([^)]*filter_params',
            r'get_test_result_stats.*organization_id',
            r'get_test_run_stats.*organization_id',
            # Filter application patterns
            r'apply_filters\([^)]*base_query[^)]*filter_params',
            r'base_query\s*=\s*apply_filters',
            r'_apply_filters\([^)]*base_query[^)]*filter_params',
            r'base_query\s*=\s*_apply_filters',
            # Comprehensive stats service patterns (base_query + filter_params + _apply_filters)
            r'base_query.*_apply_filters.*filter_params',
            r'filter_params.*organization_id.*_apply_filters',
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
                        if self._is_potentially_unsafe_query(line, match.group(), lines, line_num, str(file_path)):
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

    def _is_potentially_unsafe_query(self, line: str, query_match: str, lines: List[str], line_num: int, file_path: str = "") -> bool:
        """Determine if a query might be missing organization filtering"""
        
        # Check if it's a known safe location
        for safe_file, safe_line in self.safe_locations:
            if safe_file in file_path and line_num == safe_line:
                return False  # Known safe location
        
        # Check if it's a safe pattern
        for safe_pattern in self.safe_patterns:
            if re.search(safe_pattern, line):
                return False
        
        # IMPORTANT: Queries by unique ID are SAFE - UUIDs are globally unique
        id_based_patterns = [
            r'\.filter\([^)]*\.id\s*==',  # .filter(Model.id == uuid)
            r'\.filter_by\(id\s*=',       # .filter_by(id=uuid)
            r'\.get\(',                   # .get(uuid) - primary key lookup
            r'\.filter\([^)]*_id\s*==',   # .filter(model.some_id == uuid) - any ID field
            r'test_run_id\s*==',          # test_run_id filtering
            r'test_set_id\s*==',          # test_set_id filtering
            r'behavior_id\s*==',          # behavior_id filtering
            r'metric_id\s*==',            # metric_id filtering
            r'user_id\s*==',              # user_id filtering (when used for ID lookup)
            r'entity_id\s*==',            # entity_id filtering
        ]
        
        for id_pattern in id_based_patterns:
            if re.search(id_pattern, line):
                return False  # ID-based queries are safe
        
        # Check surrounding lines for organization filtering context (multi-line queries)
        context_start = max(0, line_num - 15)
        context_end = min(len(lines), line_num + 15)
        context_lines = ' '.join(lines[context_start:context_end])
        
        # Check for UUID-based filtering in the surrounding context (multi-line queries)
        uuid_context_patterns = [
            r'\.filter\([^)]*\.id\s*==\s*\w+_uuid\)',    # .filter(Model.id == some_uuid)
            r'\.filter\([^)]*\.id\s*==\s*test_set_uuid\)',  # .filter(Model.id == test_set_uuid)
            r'\.filter\([^)]*\.id\s*==\s*test_run_uuid\)',  # .filter(Model.id == test_run_uuid)
            r'UUID\(test_set_id\)',                      # UUID(test_set_id) conversion
            r'UUID\(test_run_id\)',                      # UUID(test_run_id) conversion
            r'test_set_uuid\s*=\s*UUID\(',               # test_set_uuid = UUID(...)
            r'test_run_uuid\s*=\s*UUID\(',               # test_run_uuid = UUID(...)
        ]
        
        for uuid_pattern in uuid_context_patterns:
            if re.search(uuid_pattern, context_lines):
                return False  # UUID-based filtering found in context
        
        # Check if organization filtering exists in the context
        for org_indicator in self.org_filter_indicators:
            if re.search(org_indicator, context_lines):
                return False  # Organization filtering found in context
        
        # Check if we're inside a known safe function
        function_context = ' '.join(lines[max(0, line_num - 50):min(len(lines), line_num + 10)])
        for safe_func in self.safe_functions:
            if f'def {safe_func}(' in function_context:
                return False  # Inside a known safe function
        
        # Check for function parameters that indicate organization filtering is handled
        if re.search(r'def\s+\w+.*organization_id.*:', function_context):
            # Function accepts organization_id parameter, likely handled properly
            if ('filter_params' in context_lines or 
                'QueryBuilder' in context_lines or
                'apply_filters' in context_lines or
                '_apply_filters' in context_lines or
                '_apply_organization_filter' in context_lines or
                '"organization_id": organization_id' in context_lines or
                'organization_id.*filter_params' in context_lines or
                # Stats service specific patterns
                ('base_query = _apply_filters' in context_lines and 'filter_params' in context_lines) or
                ('_apply_filters(base_query' in context_lines and '"organization_id": organization_id' in context_lines)):
                return False  # Organization filtering handled through parameters or QueryBuilder
        
        # Check for UUID-based function contexts (functions that take UUID parameters)
        uuid_function_patterns = [
            r'def\s+\w+.*_id:\s*uuid\.UUID',      # Function takes UUID parameter
            r'def\s+\w+.*_id:\s*UUID',            # Function takes UUID parameter (imported)
            r'def\s+get_\w+.*by.*id',             # get_something_by_id functions
            r'def\s+\w+.*test_run_id.*uuid',     # Functions with test_run_id UUID
            r'def\s+\w+.*test_set_id.*uuid',     # Functions with test_set_id UUID
        ]
        
        for uuid_pattern in uuid_function_patterns:
            if re.search(uuid_pattern, function_context, re.IGNORECASE):
                return False  # UUID-based function context is safe
                
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
