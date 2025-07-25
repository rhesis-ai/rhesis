#!/bin/bash

# GitHub PR Creation Script
# This script analyzes the current branch and creates a PR with auto-generated title and description

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper function for colored output
log() {
    echo -e "${BLUE}[PR-Creator]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    error "GitHub CLI (gh) is not installed. Please install it first."
    exit 1
fi

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    error "Not in a git repository."
    exit 1
fi

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
BASE_BRANCH=${1:-main}

if [ "$CURRENT_BRANCH" = "$BASE_BRANCH" ]; then
    error "You're already on the base branch ($BASE_BRANCH). Please switch to a feature branch."
    exit 1
fi

log "Current branch: $CURRENT_BRANCH"
log "Base branch: $BASE_BRANCH"

# Check if there are commits to create PR for
COMMIT_COUNT=$(git rev-list --count $BASE_BRANCH..$CURRENT_BRANCH 2>/dev/null || echo "0")

if [ "$COMMIT_COUNT" = "0" ]; then
    error "No commits found between $BASE_BRANCH and $CURRENT_BRANCH."
    exit 1
fi

log "Found $COMMIT_COUNT commit(s) to include in PR"

# Get commit information
COMMITS=$(git log --pretty=format:"- %s (%h)" $BASE_BRANCH..$CURRENT_BRANCH)
COMMIT_DETAILS=$(git log --pretty=format:"%h - %s (%an, %ar)" $BASE_BRANCH..$CURRENT_BRANCH)
CHANGED_FILES=$(git diff --name-only $BASE_BRANCH..$CURRENT_BRANCH)
FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l)

# Generate PR title based on branch name and commits
generate_title() {
    # Common abbreviations that should stay uppercase
    local abbreviations=(
        "DEV" "STAGING" "STG" "PROD" "PRD" "PRODUCTION"
        "API" "REST" "HTTP" "HTTPS" "URL" "URI" "GRPC"
        "UI" "UX" "CSS" "HTML" "JS" "TS" "JSX" "TSX"
        "DB" "SQL" "AWS" "GCP" "AZURE" "K8S" "DOCKER"
        "CI" "CD" "QA" "QC"
        "JWT" "AUTH" "OAUTH" "SSO" "LDAP"
        "JSON" "XML" "YAML" "YML" "CSV" "PDF"
        "SDK" "CLI" "GUI" "IDE" "VM" "VPC" "DNS"
        "TCP" "UDP" "SSH" "FTP" "SMTP" "IMAP"
        "CRM" "ERP" "SAAS" "PAAS" "IAAS"
        "ML" "AI" "NLP" "OCR" "IOT" "AR" "VR"
    )
    
    local title=""
    
    # Extract title based on branch type
    if [[ $CURRENT_BRANCH == feature/* ]]; then
        title=${CURRENT_BRANCH#feature/}
    elif [[ $CURRENT_BRANCH == fix/* ]]; then
        title="Fix: ${CURRENT_BRANCH#fix/}"
    elif [[ $CURRENT_BRANCH == hotfix/* ]]; then
        title="Hotfix: ${CURRENT_BRANCH#hotfix/}"
    else
        title=$CURRENT_BRANCH
    fi

    # Replace dashes and underscores with spaces
    title=$(echo "$title" | tr '_-' '  ')

    # Convert to title case (capitalize first letter of each word)
    title=$(echo "$title" | perl -pe 's/\b(\w)/\u$1/g')

    # Fix known abbreviations
    for abbrev in "${abbreviations[@]}"; do
        local lower=$(echo "$abbrev" | tr '[:upper:]' '[:lower:]')
        local capitalized=$(echo "$lower" | sed 's/^./\U&/')
        for variant in "$lower" "$capitalized" "$abbrev"; do
            title=$(echo "$title" | sed "s/\b$variant\b/$abbrev/g")
        done
    done

    echo "$title"
}

# Generate PR description
generate_description() {
    cat << EOF
This PR introduces changes from the \`$CURRENT_BRANCH\` branch.

## 📝 Summary

<!-- Add a brief summary of the changes here -->

## 🔄 Changes

$COMMITS

## 📁 Files Changed ($FILE_COUNT files)

\`\`\`
$CHANGED_FILES
\`\`\`

## 📋 Commit Details

\`\`\`
$COMMIT_DETAILS
\`\`\`

## ✅ Checklist

- [ ] Code follows the project's style guidelines
- [ ] Self-review of code has been performed
- [ ] Code is commented, particularly in hard-to-understand areas
- [ ] Corresponding changes to documentation have been made
- [ ] Tests have been added/updated for new functionality
- [ ] All tests pass locally

## 🧪 Testing

<!-- Describe how to test the changes -->

## 📸 Screenshots (if applicable)

<!-- Add screenshots for UI changes -->

## 🔗 Related Issues

<!-- Link any related issues: Closes #123 -->
EOF
}

PR_TITLE=$(generate_title)
PR_DESCRIPTION=$(generate_description)

log "Generated PR title: $PR_TITLE"
log "Creating PR..."

# Create the PR
if PR_URL=$(gh pr create \
    --base "$BASE_BRANCH" \
    --head "$CURRENT_BRANCH" \
    --title "$PR_TITLE" \
    --body "$PR_DESCRIPTION" \
    --assignee "@me" \
    2>&1); then
    success "Pull request created successfully!"
    success "URL: $PR_URL"
    
    # Ask if user wants to open the PR in browser
    read -p "Would you like to open the PR in your browser? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        gh pr view --web
    fi
else
    error "Failed to create PR: $PR_URL"
    exit 1
fi

# Display summary
echo
log "PR Summary:"
echo "  • Title: $PR_TITLE"
echo "  • Base: $BASE_BRANCH → Head: $CURRENT_BRANCH"
echo "  • Commits: $COMMIT_COUNT"
echo "  • Files changed: $FILE_COUNT"
echo
success "Done! 🎉" 