#!/usr/bin/env node

/**
 * GitHub Action script to create PR comments for hardcoded styles violations
 * 
 * This script parses the output from check-hardcoded-styles.js and creates
 * a well-formatted GitHub PR comment with actionable feedback.
 */

const fs = require('fs');
const { execSync } = require('child_process');

async function createPRComment() {
  // Get GitHub context from environment variables
  const { GITHUB_TOKEN, GITHUB_REPOSITORY, GITHUB_EVENT_PATH } = process.env;
  
  if (!GITHUB_TOKEN || !GITHUB_REPOSITORY || !GITHUB_EVENT_PATH) {
    console.error('Missing required GitHub environment variables');
    process.exit(1);
  }

  // Read the GitHub event payload
  const eventPayload = JSON.parse(fs.readFileSync(GITHUB_EVENT_PATH, 'utf8'));
  const prNumber = eventPayload.pull_request?.number;
  
  if (!prNumber) {
    console.log('Not a pull request event, skipping comment creation');
    return;
  }

  console.log(`Creating PR comment for PR #${prNumber}`);

  // Run the hardcoded styles checker and capture output
  let output = '';
  let hasViolations = false;
  
  try {
    execSync('node scripts/check-hardcoded-styles.js', { 
      encoding: 'utf8',
      stdio: 'pipe'
    });
  } catch (error) {
    hasViolations = true;
    output = error.stdout || error.message;
  }

  if (!hasViolations) {
    console.log('No violations found, no comment needed');
    return;
  }

  // Parse the output to extract key information
  const lines = output.split('\n');
  const fileLines = lines.filter(line => line.startsWith('📄'));
  
  let totalViolations = 0;
  let checkedFiles = 0;
  
  // Extract numbers from output
  const violationMatch = output.match(/Found (\d+) hardcoded style violations/);
  const filesMatch = output.match(/Checked (\d+) files/);
  
  if (violationMatch) totalViolations = parseInt(violationMatch[1]);
  if (filesMatch) checkedFiles = parseInt(filesMatch[1]);

  // Create a list of files with violations
  let filesList = '';
  if (fileLines.length > 0) {
    filesList = fileLines.slice(0, 10).map(line => {
      const fileName = line.replace('📄 ', '').replace(':', '');
      return `- \`${fileName}\``;
    }).join('\n');
    
    if (fileLines.length > 10) {
      filesList += `\n- ... and ${fileLines.length - 10} more files`;
    }
  }

  // Create the PR comment
  const comment = `## 🎨 Hardcoded Styles Check Failed

This PR contains **${totalViolations} hardcoded style violations** across **${fileLines.length} files**.

### 📁 Files with violations:
${filesList}

<details>
<summary>📋 Click to see detailed violations</summary>

\`\`\`
${output.length > 4000 ? output.substring(0, 4000) + '\n\n... (output truncated, run locally for full details)' : output}
\`\`\`

</details>

### 🔧 How to fix these violations:

#### 1. **Colors** → Use theme palette
\`\`\`tsx
// ❌ Hardcoded
sx={{ color: '#50B9E0', backgroundColor: '#f5f5f5' }}

// ✅ Theme-based  
sx={{ color: 'primary.main', backgroundColor: 'grey.100' }}
\`\`\`

#### 2. **Spacing** → Use theme spacing
\`\`\`tsx
// ❌ Hardcoded
sx={{ margin: '16px', padding: '24px' }}

// ✅ Theme-based
sx={{ m: 2, p: 3 }} // 2 * 8px = 16px, 3 * 8px = 24px
\`\`\`

#### 3. **Border Radius** → Use consistent values
\`\`\`tsx
// ❌ Hardcoded
sx={{ borderRadius: '8px' }}

// ✅ Consistent
sx={{ borderRadius: 1 }} // 1 * 4px = 4px (MUI default)
\`\`\`

#### 4. **Font Sizes** → Use Typography variants
\`\`\`tsx
// ❌ Hardcoded
sx={{ fontSize: '14px' }}

// ✅ Typography variant
<Typography variant="body2">Text</Typography>
\`\`\`

### 📖 Resources:
- [Theme Usage Guide](apps/frontend/src/styles/rhesis-theme-usage.md)
- [MUI System Props](https://mui.com/system/properties/)
- Run \`node scripts/check-hardcoded-styles.js\` locally for full details

---
*This check helps maintain consistent design across the application. Fix the violations above to pass the check.* ✨`;

  // Create the GitHub API request
  const [owner, repo] = GITHUB_REPOSITORY.split('/');
  
  const requestBody = {
    body: comment
  };

  // Use curl to make the GitHub API request (simpler than importing libraries)
  const curlCommand = [
    'curl',
    '-X', 'POST',
    '-H', `Authorization: token ${GITHUB_TOKEN}`,
    '-H', 'Accept: application/vnd.github.v3+json',
    '-H', 'Content-Type: application/json',
    `https://api.github.com/repos/${owner}/${repo}/issues/${prNumber}/comments`,
    '-d', `'${JSON.stringify(requestBody).replace(/'/g, "'\"'\"'")}'`
  ].join(' ');

  try {
    execSync(curlCommand, { encoding: 'utf8' });
    console.log(`✅ Successfully created PR comment for PR #${prNumber}`);
  } catch (error) {
    console.error('❌ Failed to create PR comment:', error.message);
    process.exit(1);
  }
}

// Run the script
if (require.main === module) {
  createPRComment().catch(error => {
    console.error('Error creating PR comment:', error);
    process.exit(1);
  });
}

module.exports = { createPRComment };
