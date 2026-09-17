export {};

declare global {
  interface Window {
    __ENV__?: {
      apiBaseUrl: string;
      /**
       * The deployment's `BRAND_*` values, before any organisation override.
       * Everything else in the app uses the resolved branding; this is here so
       * the organisation settings form can show what an empty field inherits.
       * Individual fields are absent unless the deployment sets them.
       */
      deploymentBranding?: {
        primaryColor?: string;
        secondaryColor?: string;
        faviconUrl?: string;
        productName?: string;
        fontFamily?: string;
      };
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
