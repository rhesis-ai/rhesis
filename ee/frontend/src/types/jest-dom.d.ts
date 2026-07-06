// Pulls @testing-library/jest-dom's global `jest.Matchers` augmentation into
// this package's standalone tsc program (`tsc -p ee/frontend/tsconfig.json`),
// which does not otherwise include apps/frontend/jest.setup.js.
import '@testing-library/jest-dom';
