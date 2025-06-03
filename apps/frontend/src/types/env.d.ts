declare global {
  namespace NodeJS {
    interface ProcessEnv {
      NEXT_PUBLIC_API_BASE_URL: string;
      // Add other environment variables here
      [key: string]: string | undefined;
    }
  }
}

export {}; 