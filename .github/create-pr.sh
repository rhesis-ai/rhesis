#!/bin/bash

# GitHub PR Creation Script
# This script analyzes the current branch and creates a PR with auto-generated title and description
#
# Features:
# - Detects if the current branch exists on remote
# - Detects if there are unpushed commits
# - Prompts user to push before creating PR (Option 1: Detect and Prompt)
# - Supports --force flag to skip push detection
# - Auto-generates PR title and description

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

# Parse command line arguments
FORCE_PUSH=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE_PUSH=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [BASE_BRANCH] [OPTIONS]"
            echo ""
            echo "Creates a GitHub Pull Request from the current branch to BASE_BRANCH (default: main)"
            echo ""
            echo "Options:"
            echo "  -f, --force     Skip push detection and create PR immediately"
            echo "  -h, --help      Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0              # Create PR to main branch"
            echo "  $0 develop      # Create PR to develop branch"
            echo "  $0 --force      # Skip push checks and create PR immediately"
            exit 0
            ;;
        *)
            BASE_BRANCH=$1
            shift
            ;;
    esac
done

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
BASE_BRANCH=${BASE_BRANCH:-main}

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

# Fetch latest remote refs to ensure we have current state
fetch_remote_refs() {
    log "Fetching latest remote references..."
    if ! git fetch origin --quiet 2>/dev/null; then
        warn "Failed to fetch remote references. Continuing with local state."
        return 1
    fi
    return 0
}

# Check if branch exists on remote
check_branch_on_remote() {
    # Check if the current branch exists on the remote
    if git ls-remote --heads origin "$CURRENT_BRANCH" 2>/dev/null | grep -q "refs/heads/$CURRENT_BRANCH"; then
        return 0  # Branch exists on remote
    else
        return 1  # Branch doesn't exist on remote
    fi
}

# Check if there are unpushed commits
check_unpushed_commits() {
    # Check if the branch exists on remote first
    if ! check_branch_on_remote; then
        return 1  # Branch not on remote, so all commits are unpushed
    fi
    
    # Compare local branch with remote branch
    local unpushed_count
    unpushed_count=$(git rev-list --count "origin/$CURRENT_BRANCH..$CURRENT_BRANCH" 2>/dev/null || echo "0")
    
    if [ "$unpushed_count" -gt 0 ]; then
        return 1  # There are unpushed commits
    else
        return 0  # All commits are pushed
    fi
}

# Prompt user to push changes
prompt_and_push() {
    local push_type="$1"  # "branch" or "changes"
    
    if [ "$push_type" = "branch" ]; then
        warn "The branch '$CURRENT_BRANCH' doesn't exist on the remote repository."
        echo "  This means the entire branch needs to be pushed before creating a PR."
    else
        warn "There are unpushed commits on branch '$CURRENT_BRANCH'."
        echo "  You have local commits that haven't been pushed to the remote repository."
    fi
    
    echo
    echo "Options:"
    echo "  1) Push now and continue with PR creation"
    echo "  2) Exit and push manually later"
    echo
    
    while true; do
        read -p "What would you like to do? (1/2): " -n 1 -r choice
        echo
        
        case $choice in
            1)
                log "Pushing $push_type to remote..."
                if git push origin "$CURRENT_BRANCH"; then
                    success "Successfully pushed $push_type to remote!"
                    return 0
                else
                    error "Failed to push $push_type to remote."
                    echo "Please resolve any issues and try again."
                    exit 1
                fi
                ;;
            2)
                log "Exiting. Please push your $push_type manually:"
                echo "  git push origin $CURRENT_BRANCH"
                echo "Then run this script again to create the PR."
                exit 0
                ;;
            *)
                echo "Please enter 1 or 2."
                ;;
        esac
    done
}

# Check if branch and changes are pushed (unless forced)
if [ "$FORCE_PUSH" = true ]; then
    warn "Skipping push detection due to --force flag"
else
    # Fetch remote refs first to ensure we have the latest state
    fetch_remote_refs

    # Check if branch and changes are pushed
    if ! check_branch_on_remote; then
        prompt_and_push "branch"
    elif ! check_unpushed_commits; then
        prompt_and_push "changes"
    else
        log "Branch and all changes are already pushed to remote."
    fi
fi

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

    # Convert to title case (capitalize first letter of each word, except conjunctions/prepositions)
    # First, capitalize all words
    title=$(echo "$title" | perl -pe 's/\b(\w)/\u$1/g')
    
    # Then lowercase common conjunctions, prepositions, and articles (except if they're the first word)
    local lowercase_words=(
        "and" "or" "but" "nor" "for" "so" "yet"
        "a" "an" "the"
        "at" "by" "for" "in" "of" "on" "to" "up" "as" "is"
        "with" "from" "into" "onto" "upon" "over" "under"
        "above" "below" "across" "through" "during" "before" "after"
        "against" "between" "among" "within" "without" "toward" "towards"
    )
    
    for word in "${lowercase_words[@]}"; do
        local cap_word=$(echo "$word" | sed 's/^./\U&/')
        # Only lowercase if it's NOT the first word of the title (preceded by space)
        title=$(echo "$title" | sed "s/\([[:space:]]\)$cap_word\b/\1$word/g")
    done

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