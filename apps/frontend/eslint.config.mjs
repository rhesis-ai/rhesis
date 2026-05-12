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
];
// Note: EE source lives outside apps/frontend/ so ESLint does not scan it.
// The boundary guard runs only in the other direction (core → EE), which the
// no-restricted-imports rule above and check-ee-boundary.mjs enforce.
