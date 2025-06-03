export interface Test {
  prompt: string;
  behavior: 'Reliability' | 'Compliance' | 'Robustness';
  category: 'Harmless' | 'Toxic' | 'Harmful' | 'Jailbreak';
} 