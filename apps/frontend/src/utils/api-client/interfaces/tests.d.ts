declare module '@/utils/api-client/interfaces/tests' {
  export interface TestDetail {
    id: string;
    prompt_id?: string;
    prompt?: {
      id: string;
      content: string;
    };
    // Add other TestDetail fields if needed
  }
} 