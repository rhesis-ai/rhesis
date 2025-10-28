#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

/**
 * GitHub Action script to check for hardcoded styles that should use theme values
 *
 * This script checks for:
 * - Hardcoded hex colors that should use theme.palette.*
 * - Hardcoded font sizes that should use typography variants
 * - Hardcoded spacing values that should use theme.spacing() or customSpacing
 * - Hardcoded elevations/box-shadows that should use theme.elevation
 */

// Theme values extracted from apps/frontend/src/styles/theme.ts
const THEME_VALUES = {
  colors: {
    // Light mode colors
    light: {
      primary: ['#50B9E0', '#97D5EE', '#2AA1CE'],
      secondary: ['#FD6E12', '#FDD803', '#1A1A1A'],
      background: ['#FFFFFF', '#F2F9FD', '#E4F2FA', '#C2E5F5', '#97D5EE'],
      text: ['#3D3D3D', '#1A1A1A'],
      success: ['#2E7D32'],
      warning: ['#F57C00'],
      error: ['#C62828']
    },
    // Dark mode colors
    dark: {
      primary: ['#2AA1CE', '#3BC4F2'],
      secondary: ['#FD6E12', '#F78166', '#58A6FF'],
      background: ['#0D1117', '#161B22', '#1F242B', '#2C2C2C'],
      text: ['#E6EDF3', '#A9B1BB'],
      success: ['#86EFAC'],
      warning: ['#FCD34D'],
      error: ['#FCA5A5']
    },
    // Chart colors
    chart: ['#50B9E0', '#FD6E12', '#2AA1CE', '#FDD803', '#97D5EE']
  },

  spacing: {
    // MUI default spacing multipliers (8px base)
    mui: [0, 8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96],
    // Custom spacing values from theme
    custom: [16, 24, 32] // small, medium, large
  },

  typography: {
    // Font sizes that should use typography variants
    fontSizes: ['0.625rem', '0.75rem', '0.875rem', '1rem', '1.25rem', '1.5rem', '1.75rem', '2rem', '2.125rem'],
    // Font weights that should use typography variants
    fontWeights: [300, 400, 500, 600, 700, 800]
  },

  elevation: {
    // Box shadow values that should use theme.elevation
    boxShadows: [
      '0 2px 12px rgba(61, 61, 61, 0.15), 0 1px 4px rgba(61, 61, 61, 0.1)',
      '0 4px 16px rgba(61, 61, 61, 0.18), 0 2px 6px rgba(61, 61, 61, 0.12)',
      '0 8px 24px rgba(61, 61, 61, 0.25), 0 4px 12px rgba(61, 61, 61, 0.15)',
      '0 4px 16px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.2)',
      '0 6px 20px rgba(0, 0, 0, 0.45), 0 3px 10px rgba(0, 0, 0, 0.25)',
      '0 12px 32px rgba(0, 0, 0, 0.6), 0 6px 16px rgba(0, 0, 0, 0.3)'
    ]
  }
};

// Regex patterns for detecting hardcoded values
const PATTERNS = {
  // Hex colors (3, 4, 6, or 8 digit hex codes)
  hexColors: /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/g,

  // RGB/RGBA colors
  rgbColors: /rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+)?\s*\)/g,

  // Font sizes in px, rem, em
  fontSizes: /fontSize:\s*['"`](\d+(?:\.\d+)?(?:px|rem|em))['"`]/g,

  // Hardcoded spacing values (px, rem, em) in margin/padding
  spacing: /(?:margin|padding)(?:[TRBL]|Top|Right|Bottom|Left)?:\s*['"`]?(\d+(?:\.\d+)?(?:px|rem|em))['"`]?/g,

  // Box shadows
  boxShadows: /boxShadow:\s*['"`]([^'"`]+)['"`]/g,

  // Border radius values
  borderRadius: /borderRadius:\s*['"`]?(\d+(?:\.\d+)?(?:px|rem|em)?)['"`]?/g,

  // Emoji characters (Unicode emoji ranges)
  emojis: /[\u{1F600}-\u{1F64F}]|[\u{1F300}-\u{1F5FF}]|[\u{1F680}-\u{1F6FF}]|[\u{1F1E0}-\u{1F1FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]/gu
};

// Files to exclude from checking
const EXCLUDE_PATTERNS = [
  /node_modules/,
  /\.git/,
  /dist/,
  /build/,
  /coverage/,
  /\.next/,
  /theme\.ts$/, // Exclude the theme file itself
  /globals\.css$/, // Exclude globals.css (contains theme definitions)
  /check-hardcoded-styles\.js$/, // Exclude this script itself
  /apps\/documentation\/components\//, // Temporarily exclude docs components (need refactoring)
  /^docs\//, // Exclude docs/ directory (markdown documentation)
  /create-pr-comment\.js$/, // Exclude PR comment script (contains documentation examples)
  /\.module\.css$/, // Exclude CSS modules (they might have hardcoded values for specific reasons)
  /\.test\./,
  /\.spec\./,
  /storybook/i
];

// Theme-related patterns that should be ignored (these are acceptable)
const IGNORE_PATTERNS = [
  // Theme property access patterns
  /theme\.palette\./,
  /theme\.typography\./,
  /theme\.spacing\(/,
  /theme\.elevation\./,
  /theme\.customSpacing\./,
  /theme\.iconSizes\./,

  // MUI system props
  /\b(?:color|bgcolor|m|mt|mr|mb|ml|mx|my|p|pt|pr|pb|pl|px|py):\s*['"`]?\w+['"`]?/,

  // Common acceptable patterns
  /transparent|inherit|initial|unset|auto|none/,

  // SVG and image related colors (often need to be hardcoded)
  /fill:\s*['"`]#/,
  /stroke:\s*['"`]#/,
  /<path[^>]*fill=['"`]#[^'"`]*['"`][^>]*>/,
  /<svg[^>]*>/,

  // CSS custom properties (CSS variables)
  /var\(/,

  // Specific acceptable values
  /#fff\b|#ffffff\b|#000\b|#000000\b/, // Pure black/white are often acceptable
  /rgba?\(0\s*,\s*0\s*,\s*0\s*,/, // Transparent black overlays
  /rgba?\(255\s*,\s*255\s*,\s*255\s*,/, // Transparent white overlays

  // Small spacing values that might be acceptable for fine-tuning
  /['"`][1-4]px['"`]/, // 1-4px values are often acceptable for micro-adjustments

  // Documentation-specific patterns
  /style=\{\{[^}]*\}\}/, // Inline styles in React components (often necessary in docs)
  /className=["'][^"']*["']/, // CSS class names
  /--[a-zA-Z-]+:/, // CSS custom properties definitions

  // Intentional overrides (marked with comments)
  /\/\/\s*Intentional:/i, // Lines marked as intentional (e.g., borderRadius: 0, // Intentional: flush edges)
];

class StyleChecker {
  constructor() {
    this.violations = [];
    this.checkedFiles = 0;
  }

  /**
   * Check if a file should be excluded from checking
   */
  shouldExcludeFile(filePath) {
    return EXCLUDE_PATTERNS.some(pattern => pattern.test(filePath));
  }

  /**
   * Check if a line should be ignored (contains acceptable patterns)
   */
  shouldIgnoreLine(line) {
    // Check for SVG content (any line containing SVG elements)
    if (/<(?:svg|path|circle|rect|ellipse|line|polyline|polygon|g|defs|use|image|text)[\s>]/i.test(line)) {
      return true;
    }

    return IGNORE_PATTERNS.some(pattern => pattern.test(line));
  }

  /**
   * Get all theme colors as a flat array for checking
   */
  getAllThemeColors() {
    const colors = [];
    Object.values(THEME_VALUES.colors.light).forEach(colorArray => colors.push(...colorArray));
    Object.values(THEME_VALUES.colors.dark).forEach(colorArray => colors.push(...colorArray));
    colors.push(...THEME_VALUES.colors.chart);
    return colors.map(c => c.toLowerCase());
  }

  /**
   * Check if a color is defined in the theme
   */
  isThemeColor(color) {
    const themeColors = this.getAllThemeColors();
    return themeColors.includes(color.toLowerCase());
  }

  /**
   * Suggest theme alternative for a hardcoded value
   */
  suggestThemeAlternative(type, value) {
    switch (type) {
      case 'color':
        if (this.isThemeColor(value)) {
          return `Use theme.palette.* instead of hardcoded color ${value}`;
        }
        return `Consider using theme.palette.* instead of hardcoded color ${value}`;

      case 'fontSize':
        return `Use Typography variant or theme.typography.* instead of hardcoded fontSize ${value}`;

      case 'spacing':
        return `Use theme.spacing() or theme.customSpacing.* instead of hardcoded spacing ${value}`;

      case 'boxShadow':
        return `Use theme.elevation.* instead of hardcoded boxShadow`;

      case 'borderRadius':
        if (value === '12px' || value === '12') {
          return `This matches theme card borderRadius, consider using a theme value`;
        }
        return `Consider using consistent borderRadius values from theme`;

      case 'emoji':
        return `Use MUI icons instead of emoji characters for better accessibility and theme consistency`;

      default:
        return `Consider using theme values instead of hardcoded ${type}`;
    }
  }

  /**
   * Check a single file for hardcoded styles
   */
  checkFile(filePath) {
    if (this.shouldExcludeFile(filePath)) {
      return;
    }

    try {
      const content = fs.readFileSync(filePath, 'utf8');
      const lines = content.split('\n');

      lines.forEach((line, lineIndex) => {
        const lineNumber = lineIndex + 1;

        // Skip lines that should be ignored
        if (this.shouldIgnoreLine(line)) {
          return;
        }

        // Check for hex colors
        let match;
        while ((match = PATTERNS.hexColors.exec(line)) !== null) {
          this.violations.push({
            file: filePath,
            line: lineNumber,
            column: match.index + 1,
            type: 'color',
            value: match[0],
            message: this.suggestThemeAlternative('color', match[0]),
            context: line.trim()
          });
        }

        // Check for RGB colors
        PATTERNS.rgbColors.lastIndex = 0;
        while ((match = PATTERNS.rgbColors.exec(line)) !== null) {
          this.violations.push({
            file: filePath,
            line: lineNumber,
            column: match.index + 1,
            type: 'color',
            value: match[0],
            message: this.suggestThemeAlternative('color', match[0]),
            context: line.trim()
          });
        }

        // Check for hardcoded font sizes
        PATTERNS.fontSizes.lastIndex = 0;
        while ((match = PATTERNS.fontSizes.exec(line)) !== null) {
          this.violations.push({
            file: filePath,
            line: lineNumber,
            column: match.index + 1,
            type: 'fontSize',
            value: match[1],
            message: this.suggestThemeAlternative('fontSize', match[1]),
            context: line.trim()
          });
        }

        // Check for hardcoded spacing
        PATTERNS.spacing.lastIndex = 0;
        while ((match = PATTERNS.spacing.exec(line)) !== null) {
          this.violations.push({
            file: filePath,
            line: lineNumber,
            column: match.index + 1,
            type: 'spacing',
            value: match[1],
            message: this.suggestThemeAlternative('spacing', match[1]),
            context: line.trim()
          });
        }

        // Check for hardcoded box shadows
        PATTERNS.boxShadows.lastIndex = 0;
        while ((match = PATTERNS.boxShadows.exec(line)) !== null) {
          this.violations.push({
            file: filePath,
            line: lineNumber,
            column: match.index + 1,
            type: 'boxShadow',
            value: match[1],
            message: this.suggestThemeAlternative('boxShadow', match[1]),
            context: line.trim()
          });
        }

        // Check for hardcoded border radius
        PATTERNS.borderRadius.lastIndex = 0;
        while ((match = PATTERNS.borderRadius.exec(line)) !== null) {
          this.violations.push({
            file: filePath,
            line: lineNumber,
            column: match.index + 1,
            type: 'borderRadius',
            value: match[1],
            message: this.suggestThemeAlternative('borderRadius', match[1]),
            context: line.trim()
          });
        }

        // Check for emoji characters
        PATTERNS.emojis.lastIndex = 0;
        while ((match = PATTERNS.emojis.exec(line)) !== null) {
          this.violations.push({
            file: filePath,
            line: lineNumber,
            column: match.index + 1,
            type: 'emoji',
            value: match[0],
            message: this.suggestThemeAlternative('emoji', match[0]),
            context: line.trim()
          });
        }

        // Reset regex lastIndex to avoid issues
        Object.values(PATTERNS).forEach(pattern => {
          if (pattern.global) pattern.lastIndex = 0;
        });
      });

      this.checkedFiles++;
    } catch (error) {
      console.error(`Error reading file ${filePath}:`, error.message);
    }
  }

  /**
   * Recursively find and check all relevant files
   */
  checkDirectory(dirPath) {
    try {
      const entries = fs.readdirSync(dirPath, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(dirPath, entry.name);

        if (entry.isDirectory()) {
          this.checkDirectory(fullPath);
        } else if (entry.isFile()) {
          // Check TypeScript, JavaScript, TSX, and MDX files
          if (/\.(ts|tsx|js|jsx|mdx)$/.test(entry.name)) {
            this.checkFile(fullPath);
          }
        }
      }
    } catch (error) {
      console.error(`Error reading directory ${dirPath}:`, error.message);
    }
  }

  /**
   * Get changed files from git diff (for PR checks)
   */
  getChangedFiles() {
    try {
      // Get files changed in this PR/commit
      const gitDiff = execSync('git diff --name-only HEAD~1 HEAD', { encoding: 'utf8' });
      return gitDiff.split('\n').filter(file =>
        file.trim() && /\.(ts|tsx|js|jsx|mdx)$/.test(file)
      );
    } catch (error) {
      console.warn('Could not get git diff, checking all files');
      return null;
    }
  }

  /**
   * Generate a report of violations
   */
  generateReport() {
    if (this.violations.length === 0) {
      console.log('✅ No hardcoded style violations found!');
      console.log(`Checked ${this.checkedFiles} files.`);
      return;
    }

    console.log(`❌ Found ${this.violations.length} hardcoded style violations:`);
    console.log(`Checked ${this.checkedFiles} files.\n`);

    // Group violations by file
    const violationsByFile = {};
    this.violations.forEach(violation => {
      if (!violationsByFile[violation.file]) {
        violationsByFile[violation.file] = [];
      }
      violationsByFile[violation.file].push(violation);
    });

    // Print violations grouped by file
    Object.entries(violationsByFile).forEach(([file, violations]) => {
      console.log(`\n📄 ${file}:`);
      violations.forEach(violation => {
        console.log(`  Line ${violation.line}:${violation.column} - ${violation.type.toUpperCase()}`);
        console.log(`    Value: ${violation.value}`);
        console.log(`    Suggestion: ${violation.message}`);
        console.log(`    Context: ${violation.context}`);
        console.log('');
      });
    });

    // Summary by violation type
    const violationsByType = {};
    this.violations.forEach(violation => {
      violationsByType[violation.type] = (violationsByType[violation.type] || 0) + 1;
    });

    console.log('\n📊 Summary by violation type:');
    Object.entries(violationsByType).forEach(([type, count]) => {
      console.log(`  ${type}: ${count} violations`);
    });

    console.log('\n💡 Quick fixes:');
    console.log('  • Colors: Use theme.palette.primary.main, theme.palette.secondary.main, etc.');
    console.log('  • Font sizes: Use Typography variants (h1, h2, body1, etc.) or theme.typography.*');
    console.log('  • Spacing: Use theme.spacing(1), theme.spacing(2), or theme.customSpacing.*');
    console.log('  • Elevations: Use theme.elevation.standard, theme.elevation.prominent, etc.');
    console.log('  • Emojis: Use MUI icons from @mui/icons-material instead of emoji characters');
    console.log('  • See apps/frontend/src/styles/rhesis-theme-usage.md for detailed examples');
  }

  /**
   * Run the style check
   */
  run(targetFiles = []) {
    console.log('🔍 Checking for hardcoded styles that should use theme values...\n');

    // If specific files are provided as arguments, check those
    if (targetFiles.length > 0) {
      console.log(`Checking ${targetFiles.length} specified files...`);
      targetFiles.forEach(file => {
        if (fs.existsSync(file)) {
          this.checkFile(file);
        } else {
          console.warn(`File not found: ${file}`);
        }
      });
    } else {
      // Check if we're in a PR context (only check changed files)
      const changedFiles = this.getChangedFiles();

      if (changedFiles && changedFiles.length > 0) {
        console.log(`Checking ${changedFiles.length} changed files...`);
        changedFiles.forEach(file => {
          if (fs.existsSync(file)) {
            this.checkFile(file);
          }
        });
      } else {
        // Check both frontend and documentation directories
        const frontendSrcPath = path.join(process.cwd(), 'apps', 'frontend', 'src');
        const docsSrcPath = path.join(process.cwd(), 'apps', 'documentation');

        let checkedAny = false;

        if (fs.existsSync(frontendSrcPath)) {
          console.log('Checking all files in apps/frontend/src...');
          this.checkDirectory(frontendSrcPath);
          checkedAny = true;
        }

        if (fs.existsSync(docsSrcPath)) {
          console.log('Checking all files in apps/documentation...');
          this.checkDirectory(docsSrcPath);
          checkedAny = true;
        }

        if (!checkedAny) {
          console.error('Neither frontend nor documentation source directories found');
          process.exit(1);
        }
      }
    }

    this.generateReport();

    // Exit with error code if violations found
    if (this.violations.length > 0) {
      process.exit(1);
    }
  }
}

// Run the checker
if (require.main === module) {
  const checker = new StyleChecker();
  // Get command line arguments (files to check)
  const targetFiles = process.argv.slice(2);
  checker.run(targetFiles);
}

module.exports = StyleChecker;
