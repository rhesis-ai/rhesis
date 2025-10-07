#!/usr/bin/env node

/**
 * Frontend Test Runner Script
 *
 * This script provides convenient commands for running frontend tests
 * and integrates with the project's wrapper script system.
 */

const { spawn } = require('child_process');
const path = require('path');

// Get command line arguments (everything after the script name)
const args = process.argv.slice(2);

function runCommand(command, args = [], options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: 'inherit',
      shell: true,
      ...options,
    });

    child.on('close', code => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`Command failed with exit code ${code}`));
      }
    });

    child.on('error', error => {
      reject(error);
    });
  });
}

async function main() {
  const frontendDir = path.join(__dirname, '..');

  try {
    switch (args[0]) {
      case 'setup':
        console.log('Installing frontend test dependencies...');
        await runCommand('npm install', [], { cwd: frontendDir });
        console.log('Frontend test setup complete!');
        break;

      case 'watch':
        console.log('Starting frontend tests in watch mode...');
        await runCommand('npm run test:watch', [], { cwd: frontendDir });
        break;

      case 'coverage':
        console.log('Running frontend tests with coverage...');
        await runCommand('npm run test:coverage', [], { cwd: frontendDir });
        break;

      case 'ci':
        console.log('Running frontend tests for CI...');
        await runCommand('npm run test:ci', [], { cwd: frontendDir });
        break;

      default:
        if (args[0] === 'run' || args.length === 0) {
          console.log('Running all frontend tests...');
          await runCommand('npm test', [], { cwd: frontendDir });
        } else {
          console.log('Running frontend tests with custom arguments...');
          await runCommand('npm test', args, { cwd: frontendDir });
        }
        break;
    }
  } catch (error) {
    console.error('Test execution failed:', error.message);
    process.exit(1);
  }
}

// Show help if asked
if (args.includes('--help') || args.includes('-h')) {
  console.log(`
Frontend Test Runner

Usage:
  node apps/frontend/scripts/test-frontend.js [command] [options]

Commands:
  setup             Install test dependencies
  watch             Run tests in watch mode
  coverage          Run tests with coverage report
  ci                Run tests for CI (single run)
  run               Run all tests (default)
  [test-pattern]    Run specific tests matching pattern

Examples:
  node apps/frontend/scripts/test-frontend.js setup
  node apps/frontend/scripts/test-frontend.js watch
  node apps/frontend/scripts/test-frontend.js coverage
  node apps/frontend/scripts/test-frontend.js BaseDrawer
  node apps/frontend/scripts/test-frontend.js --testPathPattern=components

Options:
  --help, -h        Show this help message
`);
  process.exit(0);
}

main().catch(error => {
  console.error('Script failed:', error.message);
  process.exit(1);
});
