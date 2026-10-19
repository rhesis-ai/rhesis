import type { DeploymentBranding } from '@/config/branding';
import type { PublicEnv } from '@/config/runtime-config';

export {};

declare global {
  interface Window {
    /** Filled by the root layout; read it through `publicEnv()`. */
    __ENV__?: Partial<PublicEnv> & {
      /**
       * The deployment's `BRAND_*` values, before any organisation override.
       * Everything else in the app uses the resolved branding; this is here so
       * the organisation settings form can show what an empty field inherits.
       */
      deploymentBranding?: DeploymentBranding;
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
