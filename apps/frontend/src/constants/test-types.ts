/**
 * Test type constants aligned with backend initial_data.json
 * These values match the type_lookup table entries for TestType
 */
export const TEST_TYPES = {
  SINGLE_TURN: 'Single-Turn',
  MULTI_TURN: 'Multi-Turn',
} as const;

/**
 * Type for test type values
 */
export type TestTypeValue = typeof TEST_TYPES[keyof typeof TEST_TYPES];

/**
 * Check if a string value matches a known test type (case-insensitive)
 * @param value The value to check
 * @returns The matching test type constant or null if not found
 */
export function getTestType(value: string | undefined | null): TestTypeValue | null {
  if (!value) return null;
  
  const valueLower = value.toLowerCase();
  const entries = Object.values(TEST_TYPES);
  
  return entries.find(testType => testType.toLowerCase() === valueLower) || null;
}

/**
 * Check if a value represents a multi-turn test (case-insensitive)
 * @param value The test type value to check
 * @returns True if the value represents a multi-turn test
 */
export function isMultiTurnTest(value: string | undefined | null): boolean {
  const testType = getTestType(value);
  return testType === TEST_TYPES.MULTI_TURN;
}

/**
 * Check if a value represents a single-turn test (case-insensitive)
 * @param value The test type value to check
 * @returns True if the value represents a single-turn test
 */
export function isSingleTurnTest(value: string | undefined | null): boolean {
  const testType = getTestType(value);
  return testType === TEST_TYPES.SINGLE_TURN;
}

