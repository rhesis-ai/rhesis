'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import ConnectModelStep from '@/app/(protected)/models/components/ConnectModelStep';
import { useModelsReady, useRefreshFeatures } from '@/contexts/FeaturesContext';
import { onModelNotConfigured } from '@/utils/model-setup';

interface ModelSetupGateProps {
  /** `models_ready` is also false before the org exists; that user belongs in onboarding. */
  hasOrganization: boolean;
  children: React.ReactNode;
}

/**
 * Hard gate: replaces the app with the "Connect a model" step while
 * `models_ready` is a definite `false`. Unknown lets the app through, since
 * the backend fails open on this check too.
 */
export default function ModelSetupGate({
  hasOrganization,
  children,
}: ModelSetupGateProps) {
  const router = useRouter();
  const modelsReady = useModelsReady();
  const refreshFeatures = useRefreshFeatures();
  const gated = hasOrganization && modelsReady === false;
  const [holding, setHolding] = React.useState(gated);
  const [, startTransition] = React.useTransition();

  // A failed model check anywhere (see `utils/model-setup`) rechecks readiness.
  React.useEffect(
    () =>
      onModelNotConfigured(() => {
        void refreshFeatures();
      }),
    [refreshFeatures]
  );

  // The page behind the step was server-rendered before a model existed (the
  // Models page would not list the new one). Refresh it, and keep the step up
  // until the fresh page is ready: both updates share one transition.
  const refreshStarted = React.useRef(false);
  React.useEffect(() => {
    if (gated) {
      refreshStarted.current = false;
      setHolding(true);
    } else if (holding && !refreshStarted.current) {
      refreshStarted.current = true;
      startTransition(() => {
        router.refresh();
        setHolding(false);
      });
    }
  }, [gated, holding, router]);

  if (gated || holding) {
    return <ConnectModelStep />;
  }

  return <>{children}</>;
}
