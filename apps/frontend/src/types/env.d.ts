export {};

declare global {
  interface Window {
    __ENV__?: {
      apiBaseUrl: string;
    };
  }
}
declare global {
  namespace NodeJS {
    interface ProcessEnv {
      // Add other environment variables here
      [key: string]: string | undefined;
    }
  }
}

