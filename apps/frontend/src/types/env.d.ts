export {};

declare global {
  interface Window {
    __ENV__?: {
      apiBaseUrl: string;
      /** Absent unless the deployment sets `BRAND_PRIMARY_COLOR`. */
      brandPrimaryColor?: string;
      brandFaviconUrl?: string;
      brandProductName?: string;
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
