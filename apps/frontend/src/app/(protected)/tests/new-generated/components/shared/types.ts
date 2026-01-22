/**
 * Shared type definitions for the Test Generation feature
 */

import { Project } from '@/utils/api-client/interfaces/project';
import { ConversationTurn } from '@/utils/api-client/interfaces/test-results';

/**
 * Test type selection
 */
export type TestType = 'single_turn' | 'multi_turn';

/**
 * Multi-turn prompt structure
 */
export interface MultiTurnPrompt {
  goal: string;
  instructions: string;
  restrictions: string;
  scenario: string;
}

/**
 * Individual chip configuration
 */
export interface ChipConfig {
  id: string;
  label: string;
  description?: string;
  active: boolean;
  colorVariant?: 'blue' | 'purple' | 'orange' | 'green';
}

/**
 * Configuration chips grouped by category
 */
export interface ConfigChips {
  behavior: ChipConfig[];
  topics: ChipConfig[];
  category: ChipConfig[];
}

/**
 * Chip state for API communication
 */
export interface ChipState {
  label: string;
  description: string;
  active: boolean;
  category: 'behavior' | 'topic' | 'category' | 'scenario';
}

/**
 * Test sample with rating and feedback (single-turn)
 */
export interface TestSample {
  id: string;
  testType: 'single_turn';
  prompt: string;
  response?: string;
  behavior: string;
  topic: string;
  rating: number | null; // 1-5 or null
  feedback: string;
  isLoadingResponse?: boolean;
  responseError?: string;
  context?: Array<{ name: string; description?: string; content?: string }>; // Sources used
}

/**
 * Multi-turn test sample with rating and feedback
 */
export interface MultiTurnTestSample {
  id: string;
  testType: 'multi_turn';
  prompt: MultiTurnPrompt;
  response?: string;
  behavior: string;
  topic: string;
  category: string;
  rating: number | null; // 1-5 or null
  feedback: string;
  isLoadingResponse?: boolean;
  responseError?: string;
  context?: Array<{ name: string; description?: string; content?: string }>; // Sources used
  // Conversation-related fields for multi-turn execution
  conversation?: ConversationTurn[];
  conversationError?: string;
  isLoadingConversation?: boolean;
}

/**
 * Union type for all test samples
 */
export type AnyTestSample = TestSample | MultiTurnTestSample;

/**
 * Chat message in the refinement interface
 */
export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  chip_states?: ChipState[];
}

/**
 * Generation configuration for API
 */
export interface GenerationConfig {
  project: Project | null;
  behaviors: string[];
  purposes: string[];
  testType: 'single_turn' | 'multi_turn';
  responseGeneration: 'prompt_only' | 'prompt_and_response';
  testCoverage: 'focused' | 'standard' | 'comprehensive';
  tags: string[];
  description: string;
}

/**
 * Test set size options
 */
export type TestSetSize = 'small' | 'medium' | 'large';

/**
 * Test set size configuration
 */
export interface TestSetSizeConfig {
  id: TestSetSize;
  label: string;
  description: string;
  testCount: string;
  estimatedCost: string;
  recommended?: boolean;
}

/**
 * Current flow step
 */
export type FlowStep = 'input' | 'interface' | 'confirmation';

/**
 * Generation mode
 */
export type GenerationMode = 'ai' | 'template' | 'manual';

/**
 * Template configuration
 */
export interface TestTemplate {
  id: string;
  name: string;
  description: string;
  icon: React.ComponentType<any>;
  color: string;
  prompt: string;
  topics: string[];
  category: string[];
  popularity?: 'high' | 'medium' | 'low';
}

/**
 * Main flow state
 */
export interface FlowState {
  // Navigation
  currentScreen: FlowStep;
  mode: GenerationMode | null;
  testType: TestType;

  // Input Screen
  description: string;
  uploadedFiles: File[];

  // Configuration
  project: Project | null;
  configChips: ConfigChips;

  // Generation
  testSamples: TestSample[];
  chatMessages: ChatMessage[];

  // Final Configuration
  testSetSize: TestSetSize;
  testSetName: string;
  createTestSet: boolean;

  // UI State
  isGenerating: boolean;
  error: string | null;
}

/**
 * Document processing status
 */
export type DocumentStatus =
  | 'uploading'
  | 'extracting'
  | 'generating'
  | 'completed'
  | 'error';
