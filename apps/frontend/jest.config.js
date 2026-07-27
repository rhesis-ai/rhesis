const nextJest = require('next/jest');

const createJestConfig = nextJest({
  // Provide the path to your Next.js app to load next.config.js and .env files
  dir: './',
});

// Add any custom config to be passed to Jest
const customJestConfig = {
  setupFiles: ['<rootDir>/jest.polyfills.js'],
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jsdom',
  // Tell Jest which directory trees to scan for tests. Default is
  // <rootDir>; we add ee/frontend/src so EE feature tests under
  // ee/frontend/src/<feature>/__tests__/ are discovered alongside
  // core tests.
  roots: ['<rootDir>', '<rootDir>/../../ee/frontend/src'],
  // EE source files live outside <rootDir>, so the default
  // node_modules walk-up from those files never reaches
  // apps/frontend/node_modules. Adding it explicitly to modulePaths
  // mirrors what tsconfig.json + next.config.mjs already do at type-
  // check and bundle time: external dependencies resolve from a
  // single, shared node_modules tree.
  modulePaths: ['<rootDir>/node_modules'],
  // Use v8 coverage provider to avoid inflight/test-exclude compatibility issue
  coverageProvider: 'v8',
  moduleNameMapper: {
    // Themed RTL render for all unit tests (see src/test/testing-library-react.tsx).
    '^@testing-library/react-original$': '@testing-library/react',
    '^@testing-library/react$': '<rootDir>/src/test/testing-library-react.tsx',
    // Path aliases must mirror tsconfig.json + next.config.mjs so test
    // imports resolve identically to runtime imports.
    '^@/(.*)$': '<rootDir>/src/$1',
    // @rhesis/ee-frontend is a file: dependency installed in node_modules,
    // but Jest does not follow symlinks for module resolution by default.
    // Map the package name directly to the EE source directory so Jest
    // finds EE modules without needing a full npm install in tests.
    '^@rhesis/ee-frontend$': '<rootDir>/../../ee/frontend/src/index.ts',
    '^@rhesis/ee-frontend/(.*)$': '<rootDir>/../../ee/frontend/src/$1',
    // Redirect @testing-library/react to a themed wrapper so all renders
    // automatically include the custom MUI theme (theme.palette.greyscale.*).
    '^@testing-library/react$': '<rootDir>/src/test-utils.tsx',
  },
  collectCoverageFrom: [
    'src/**/*.{js,jsx,ts,tsx}',
    // Include EE frontend in coverage so EE feature work shows up in
    // the same report. Path is relative to rootDir (apps/frontend).
    '../../ee/frontend/src/**/*.{js,jsx,ts,tsx}',
    '!src/**/*.d.ts',
    '!../../ee/frontend/src/**/*.d.ts',
    '!src/**/index.ts',
    '!../../ee/frontend/src/**/index.ts',
    '!src/app/layout.tsx',
    '!src/app/page.tsx',
    '!src/auth.ts',
  ],
  testPathIgnorePatterns: [
    '<rootDir>/.next/',
    '<rootDir>/node_modules/',
    '<rootDir>/out/',
  ],
  transformIgnorePatterns: [
    'node_modules/(?!(.*\\.mjs$|@mui|@toolpad|next-auth|@auth|msw|@mswjs))',
  ],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node'],
  testMatch: [
    '<rootDir>/src/**/__tests__/**/*.{js,jsx,ts,tsx}',
    '<rootDir>/src/**/*.{test,spec}.{js,jsx,ts,tsx}',
    '<rootDir>/tests/frontend/**/*.{test,spec}.{js,jsx,ts,tsx}',
    // EE feature tests live colocated with their source under
    // ee/frontend/src/<feature>/__tests__/, mirroring the rest of the
    // frontend's "tests next to code" convention.
    '<rootDir>/../../ee/frontend/src/**/__tests__/**/*.{js,jsx,ts,tsx}',
    '<rootDir>/../../ee/frontend/src/**/*.{test,spec}.{js,jsx,ts,tsx}',
  ],
};

// createJestConfig is exported this way to ensure that next/jest can load the Next.js config which is async
module.exports = createJestConfig(customJestConfig);
