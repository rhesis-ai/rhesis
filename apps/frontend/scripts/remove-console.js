#!/usr/bin/env node

/**
 * Script to automatically remove console statements from TypeScript/TSX files
 * Uses AST parsing to safely handle multi-line statements and preserve code structure
 */

const fs = require('fs');
const path = require('path');
const { parse } = require('@typescript-eslint/typescript-estree');
const { generate } = require('@babel/generator');

// Console methods to remove
const CONSOLE_METHODS = ['log', 'error', 'warn', 'debug', 'info'];

/**
 * Remove console statements from source code
 */
function removeConsoleStatements(sourceCode, filePath) {
  try {
    // Parse the source code into an AST
    const ast = parse(sourceCode, {
      loc: true,
      range: true,
      comment: true,
      jsx: filePath.endsWith('.tsx'),
      filePath: filePath,
    });

    // Track positions of console statements to remove (in reverse order)
    const rangeToRemove = [];

    // Traverse the AST
    function traverse(node) {
      if (!node || typeof node !== 'object') return;

      // Check if this is a console statement
      if (
        node.type === 'ExpressionStatement' &&
        node.expression &&
        node.expression.type === 'CallExpression' &&
        node.expression.callee &&
        node.expression.callee.type === 'MemberExpression' &&
        node.expression.callee.object &&
        node.expression.callee.object.name === 'console' &&
        node.expression.callee.property &&
        CONSOLE_METHODS.includes(node.expression.callee.property.name)
      ) {
        if (node.range) {
          rangeToRemove.push(node.range);
        }
      }

      // Recursively traverse child nodes
      for (const key in node) {
        if (key === 'parent' || key === 'tokens' || key === 'comments')
          continue;
        const child = node[key];

        if (Array.isArray(child)) {
          child.forEach(c => traverse(c));
        } else if (child && typeof child === 'object') {
          traverse(child);
        }
      }
    }

    traverse(ast);

    // If no console statements found, return original source
    if (rangeToRemove.length === 0) {
      return { modified: false, code: sourceCode };
    }

    // Sort ranges in reverse order (remove from end to start to preserve indices)
    rangeToRemove.sort((a, b) => b[0] - a[0]);

    // Remove console statements
    let modifiedCode = sourceCode;
    for (const [start, end] of rangeToRemove) {
      // Find the start of the line
      let lineStart = start;
      while (lineStart > 0 && modifiedCode[lineStart - 1] !== '\n') {
        lineStart--;
      }

      // Check if there's only whitespace before the console statement on this line
      const beforeStatement = modifiedCode.substring(lineStart, start);
      const onlyWhitespace = /^\s*$/.test(beforeStatement);

      if (onlyWhitespace) {
        // Remove the entire line including newline
        let lineEnd = end;
        if (modifiedCode[lineEnd] === ';') lineEnd++;
        while (
          lineEnd < modifiedCode.length &&
          modifiedCode[lineEnd] !== '\n'
        ) {
          if (!/\s/.test(modifiedCode[lineEnd])) break;
          lineEnd++;
        }
        if (modifiedCode[lineEnd] === '\n') lineEnd++;

        modifiedCode =
          modifiedCode.substring(0, lineStart) +
          modifiedCode.substring(lineEnd);
      } else {
        // Just remove the statement itself (there's other code on the line)
        let statementEnd = end;
        if (modifiedCode[statementEnd] === ';') statementEnd++;
        modifiedCode =
          modifiedCode.substring(0, start) +
          modifiedCode.substring(statementEnd);
      }
    }

    return { modified: true, code: modifiedCode, count: rangeToRemove.length };
  } catch (error) {
    console.error(`Error parsing ${filePath}:`, error.message);
    return { modified: false, code: sourceCode, error: error.message };
  }
}

/**
 * Process a single file
 */
function processFile(filePath) {
  const sourceCode = fs.readFileSync(filePath, 'utf8');
  const result = removeConsoleStatements(sourceCode, filePath);

  if (result.modified) {
    fs.writeFileSync(filePath, result.code, 'utf8');
    return { file: filePath, count: result.count };
  }

  return null;
}

/**
 * Recursively find all TypeScript/TSX files in a directory
 */
function findFiles(dir, fileList = []) {
  const files = fs.readdirSync(dir);

  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);

    if (stat.isDirectory()) {
      // Skip node_modules, .next, etc.
      if (
        ![
          'node_modules',
          '.next',
          'dist',
          'build',
          'coverage',
          '.git',
        ].includes(file)
      ) {
        findFiles(filePath, fileList);
      }
    } else if (file.endsWith('.ts') || file.endsWith('.tsx')) {
      fileList.push(filePath);
    }
  });

  return fileList;
}

/**
 * Main execution
 */
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.error('Usage: node remove-console.js <directory>');
    process.exit(1);
  }

  const targetDir = path.resolve(args[0]);

  if (!fs.existsSync(targetDir)) {
    console.error(`Directory not found: ${targetDir}`);
    process.exit(1);
  }

  console.log(`Finding TypeScript files in ${targetDir}...`);
  const files = findFiles(targetDir);
  console.log(`Found ${files.length} files to process\n`);

  const results = [];
  let totalRemoved = 0;

  files.forEach((file, index) => {
    process.stdout.write(`\rProcessing: ${index + 1}/${files.length}`);

    const result = processFile(file);
    if (result) {
      results.push(result);
      totalRemoved += result.count;
    }
  });

  console.log('\n\n=== Results ===');
  console.log(`Total files processed: ${files.length}`);
  console.log(`Files modified: ${results.length}`);
  console.log(`Console statements removed: ${totalRemoved}\n`);

  if (results.length > 0) {
    console.log('Modified files:');
    results.forEach(({ file, count }) => {
      console.log(`  ${path.relative(targetDir, file)}: ${count} statement(s)`);
    });
  }
}

main();
