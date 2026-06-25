import { fixupConfigRules } from '@eslint/compat';
import pluginReact from 'eslint-plugin-react';
import pluginReactHooks from 'eslint-plugin-react-hooks';
import pluginJsxA11y from 'eslint-plugin-jsx-a11y';
import pluginImport from 'eslint-plugin-import';
import { configs as typescriptConfigs } from 'typescript-eslint';
import globals from 'globals';

export default [
  {
    ignores: [
      'node_modules/',
      '.next/',
      '.next-e2e/',
      'out/',
      'dist/',
      'build/',
      'coverage/',
      'jest.config.js',
      'jest.setup.js',
      'scripts/**/*.js',
    ],
  },
  ...typescriptConfigs.recommended,
  ...fixupConfigRules({
    plugins: {
      react: pluginReact,
      'react-hooks': pluginReactHooks,
      'jsx-a11y': pluginJsxA11y,
      import: pluginImport,
    },
  }),
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
      },
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
    rules: {
      // TypeScript specific rules
      '@typescript-eslint/no-unused-vars': [
        'warn',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
        },
      ],
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/explicit-module-boundary-types': 'off',
      '@typescript-eslint/no-non-null-assertion': 'warn',
      '@typescript-eslint/no-non-null-asserted-optional-chain': 'error',
      '@typescript-eslint/ban-ts-comment': 'warn',

      // General JavaScript rules
      'prefer-const': 'error',
      'no-var': 'error',
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'no-debugger': 'error',
      'no-duplicate-imports': 'error',
      'no-unused-expressions': 'error',

      // React specific rules
      'react/prop-types': 'off',
      'react/react-in-jsx-scope': 'off',
      'react/no-array-index-key': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'react-hooks/rules-of-hooks': 'error',
      'react/jsx-uses-react': 'off',
      'react/jsx-uses-vars': 'error',

      // Prevent dark-mode regressions: GREYSCALE.light.* and GREYSCALE.dark.*
      // are raw static tokens; use theme.palette.greyscale.* in sx callbacks instead.
      // Only src/styles/theme.ts and src/styles/theme-constants.ts are exempt.
      'no-restricted-syntax': [
        'error',
        {
          selector:
            "MemberExpression[object.object.name='GREYSCALE'][object.property.name='light']",
          message:
            'Use theme.palette.greyscale.* in an sx callback instead of GREYSCALE.light.* (dark-mode regression risk). Only src/styles/theme*.ts is exempt.',
        },
        {
          selector:
            "MemberExpression[object.object.name='GREYSCALE'][object.property.name='dark']",
          message:
            'Use theme.palette.greyscale.* in an sx callback instead of GREYSCALE.dark.* (dark-mode regression risk). Only src/styles/theme*.ts is exempt.',
        },
      ],

      // Open-core boundary guard.
      //
      // Core (apps/frontend/) must never statically import EE code. The
      // only sanctioned bridge is apps/frontend/src/ee_bootstrap.ts,
      // which is exempted in the override below. EE code may import
      // freely from core; the inverse is what we forbid here.
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@rhesis/ee-frontend', '@rhesis/ee-frontend/*'],
              message:
                'Core frontend may not import from @rhesis/ee-frontend. Plug into a registry in @/lib/extension-registries instead, and register from ee/frontend/src/bootstrap.ts. The only sanctioned exception is apps/frontend/src/ee_bootstrap.ts.',
            },
            {
              group: [
                '../../../../../ee/frontend/*',
                '../../../../ee/frontend/*',
                '../../../ee/frontend/*',
                '../../ee/frontend/*',
                '../ee/frontend/*',
              ],
              message:
                'Use the @rhesis/ee-frontend package rather than relative paths into ee/frontend/. (Note: relative imports of EE from core are forbidden anyway -- see the @rhesis/ee-frontend rule.)',
            },
          ],
        },
      ],
    },
  },
  {
    // Sanctioned bridge: only ee_bootstrap.ts may import from @rhesis/ee-frontend.
    files: ['src/ee_bootstrap.ts'],
    rules: {
      'no-restricted-imports': 'off',
    },
  },
  {
    // Theme definition files are allowed to reference GREYSCALE.light/dark directly.
    files: ['src/styles/theme.ts', 'src/styles/theme-constants.ts'],
    rules: {
      'no-restricted-syntax': 'off',
    },
  },
  {
    // Project-isolation guard for always-server code (server actions + API route
    // handlers). These run server-side where `document.cookie` is unreadable, so
    // a bare `new ApiClientFactory(...)` would omit the X-Project-Id scope and
    // leak cross-project data. Use `createServerApiFactory(session.session_token)`
    // from '@/utils/api-client/server-factory' instead, which reads the active
    // project cookie via next/headers.
    //
    // Note: this override REPLACES no-restricted-syntax for matching files, so the
    // GREYSCALE selectors are repeated here to keep that protection in place.
    //
    // Server Components (page.tsx / layout.tsx) are intentionally NOT covered:
    // many of those files are 'use client' and legitimately construct
    // ApiClientFactory directly (cookie-based), which a glob ban cannot
    // distinguish. They rely on code review + the createServerApiFactory
    // convention instead.
    files: ['src/actions/**/*.{ts,tsx}', 'src/app/api/**/route.ts'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector:
            "MemberExpression[object.object.name='GREYSCALE'][object.property.name='light']",
          message:
            'Use theme.palette.greyscale.* in an sx callback instead of GREYSCALE.light.* (dark-mode regression risk). Only src/styles/theme*.ts is exempt.',
        },
        {
          selector:
            "MemberExpression[object.object.name='GREYSCALE'][object.property.name='dark']",
          message:
            'Use theme.palette.greyscale.* in an sx callback instead of GREYSCALE.dark.* (dark-mode regression risk). Only src/styles/theme*.ts is exempt.',
        },
        {
          selector: "NewExpression[callee.name='ApiClientFactory']",
          message:
            'Do not construct ApiClientFactory directly in server actions or route handlers; use createServerApiFactory(session.session_token) from @/utils/api-client/server-factory so requests carry the active project (X-Project-Id) scope.',
        },
      ],
    },
  },
];
// Note: EE source lives outside apps/frontend/ so ESLint does not scan it.
// The boundary guard runs only in the other direction (core → EE), which the
// no-restricted-imports rule above and check-ee-boundary.mjs enforce.
