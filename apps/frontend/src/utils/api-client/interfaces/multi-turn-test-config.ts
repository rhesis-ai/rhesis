/**
 * Multi-turn test configuration interfaces.
 *
 * These define the structure stored in test.test_configuration JSON
 * for multi-turn tests (when test_type is multi-turn).
 */

export interface MultiTurnTestConfig {
  /**
   * What the target SHOULD do - success criteria (required)
   */
  goal: string;

  /**
   * HOW Penelope should conduct the test - methodology (optional)
   */
  instructions?: string;

  /**
   * What the target MUST NOT do - forbidden behaviors (optional)
   */
  restrictions?: string;

  /**
   * Context and persona for the test (optional)
   */
  scenario?: string;

  /**
   * Maximum number of conversation turns (default: 10, range: 1-50)
   */
  max_turns?: number;
}

/**
 * Type guard to check if a test_configuration is a multi-turn config
 */
export function isMultiTurnConfig(config: any): config is MultiTurnTestConfig {
  return config !== null && typeof config === 'object' && 'goal' in config;
}

/**
 * Create an empty multi-turn test configuration with defaults
 */
export function createEmptyMultiTurnConfig(): MultiTurnTestConfig {
  return {
    goal: '',
    instructions: undefined,
    restrictions: undefined,
    scenario: undefined,
    max_turns: 10,
  };
}
