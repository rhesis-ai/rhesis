/**
 * Type lookup type_name constants matching the backend type_lookup table
 */
export const TYPE_NAMES = {
  TEST_TYPE: 'TestType',
  TEST_SET_TYPE: 'TestSetType',
} as const;

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
export type TestTypeValue = (typeof TEST_TYPES)[keyof typeof TEST_TYPES];

/** Filter/dropdown options — label matches the canonical value. */
export const TEST_TYPE_FILTER_OPTIONS = [
  { label: TEST_TYPES.SINGLE_TURN, value: TEST_TYPES.SINGLE_TURN },
  { label: TEST_TYPES.MULTI_TURN, value: TEST_TYPES.MULTI_TURN },
] as const;

/** Grid toolbar pill tabs including "All". */
export const TEST_TYPE_PILL_TABS = [
  { label: 'All', value: 'all' },
  ...TEST_TYPE_FILTER_OPTIONS,
] as const;

const TEST_TYPE_ALIASES: Record<string, TestTypeValue> = {
  single_turn: TEST_TYPES.SINGLE_TURN,
  multi_turn: TEST_TYPES.MULTI_TURN,
};

/**
 * Check if a string value matches a known test type (case-insensitive)
 * @param value The value to check
 * @returns The matching test type constant or null if not found
 */
export function getTestType(
  value: string | undefined | null
): TestTypeValue | null {
  if (!value) return null;

  const alias = TEST_TYPE_ALIASES[value.toLowerCase()];
  if (alias) return alias;

  const valueLower = value.toLowerCase();
  const entries = Object.values(TEST_TYPES);

  return (
    entries.find(testType => testType.toLowerCase() === valueLower) || null
  );
}

/**
 * Normalize legacy or variant test type strings to canonical values.
 */
export function normalizeTestType(
  value: string | undefined | null,
  fallback: TestTypeValue = TEST_TYPES.SINGLE_TURN
): TestTypeValue {
  return getTestType(value) ?? fallback;
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
