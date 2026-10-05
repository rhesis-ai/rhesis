'use client';

import React, { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { Box, Button, Divider, Typography } from '@mui/material';
import HubOutlinedIcon from '@mui/icons-material/HubOutlined';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import AddIcon from '@mui/icons-material/Add';
import { handleSignOut } from '@/actions/auth';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import {
  MODEL_TYPES,
  PROVIDER_TYPE_LOOKUP_FILTER,
} from '@/constants/model-types';
import {
  useRefreshFeatures,
  useRhesisKeyEnabled,
} from '@/contexts/FeaturesContext';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { useCreateModel } from '@/hooks/useCreateModel';
import { useTypeLookups } from '@/hooks/useLookups';
import { BORDER_RADIUS } from '@/styles/theme';
import type { ModelCreate } from '@/utils/api-client/interfaces/model';

// Lazy, so the two forms stay out of the protected layout's bundle.
const PlatformKeyDrawer = dynamic(
  () => import('./PlatformKeyDrawer').then(mod => mod.PlatformKeyDrawer),
  { ssr: false }
);
const ModelConnectionDrawer = dynamic(
  () =>
    import('./ModelConnectionDrawer').then(mod => mod.ModelConnectionDrawer),
  { ssr: false }
);

export const CONNECT_MODEL_COPY = {
  title: 'Connect a model',
  body: 'Rhesis uses a language model to generate tests and evaluate results. Connect one to get started.',
  platformKeyAction: 'Use a Rhesis API key',
  platformKeyHint: 'Run on the models hosted by Rhesis.',
  ownModelAction: 'Add your own model',
  ownModelHint: 'Connect a provider account or a local model.',
  noAccess: 'Ask an organization admin to connect a model, then check again.',
  or: 'or',
  checkAgain: 'Check again',
  signOut: 'Sign out',
} as const;

/**
 * Full-screen step shown by `ModelSetupGate`. It never closes itself: both
 * fixes end in a `GET /features` refetch, and the gate drops it.
 */
export default function ConnectModelStep() {
  const createModel = useCreateModel();
  const rhesisKeyEnabled = useRhesisKeyEnabled();
  const canAddModel = useCan(Capability.Model.CREATE);
  const refreshFeatures = useRefreshFeatures();
  const [platformKeyOpen, setPlatformKeyOpen] = useState(false);
  const [addModelOpen, setAddModelOpen] = useState(false);
  const [checking, setChecking] = useState(false);
  const { setChecklistHidden } = useOnboarding();

  // The checklist is mounted in the root layout and would float over this step.
  useEffect(() => {
    setChecklistHidden(true);
    return () => setChecklistHidden(false);
  }, [setChecklistHidden]);
  const { data: providers = [] } = useTypeLookups(
    PROVIDER_TYPE_LOOKUP_FILTER,
    canAddModel
  );

  const handleConnect = (_providerId: string, modelData: ModelCreate) =>
    createModel(modelData);

  // Refetch on close, not on create: the form is still saving the default
  // choices then, and dropping the gate would unmount it halfway.
  const handleAddModelClose = () => {
    setAddModelOpen(false);
    void refreshFeatures();
  };

  const handleCheckAgain = async () => {
    setChecking(true);
    try {
      await refreshFeatures();
    } finally {
      setChecking(false);
    }
  };

  const hasBothOptions = rhesisKeyEnabled && canAddModel;
  const hasNoOption = !rhesisKeyEnabled && !canAddModel;

  return (
    <Box
      component="main"
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
        p: 4,
      }}
    >
      <Box
        sx={{
          maxWidth: theme => theme.spacing(58),
          width: '100%',
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 3,
        }}
      >
        <Box
          sx={{
            width: theme => theme.spacing(9),
            height: theme => theme.spacing(9),
            borderRadius: '50%',
            bgcolor: theme =>
              theme.palette.mode === 'light' ? 'grey.100' : 'grey.900',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <HubOutlinedIcon fontSize="large" sx={{ color: 'text.secondary' }} />
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Typography variant="h5" component="h1" fontWeight={700}>
            {CONNECT_MODEL_COPY.title}
          </Typography>
          <Typography variant="body1" color="text.secondary">
            {CONNECT_MODEL_COPY.body}
          </Typography>
        </Box>

        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 1.5,
            width: '100%',
          }}
        >
          {rhesisKeyEnabled && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              <Button
                variant="contained"
                size="large"
                startIcon={<VpnKeyIcon />}
                onClick={() => setPlatformKeyOpen(true)}
                sx={{ borderRadius: BORDER_RADIUS.sm }}
              >
                {CONNECT_MODEL_COPY.platformKeyAction}
              </Button>
              <Typography variant="caption" color="text.secondary">
                {CONNECT_MODEL_COPY.platformKeyHint}
              </Typography>
            </Box>
          )}

          {hasBothOptions && (
            <Divider>
              <Typography variant="caption" color="text.disabled">
                {CONNECT_MODEL_COPY.or}
              </Typography>
            </Divider>
          )}

          {canAddModel && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              <Button
                variant={rhesisKeyEnabled ? 'outlined' : 'contained'}
                size="large"
                startIcon={<AddIcon />}
                onClick={() => setAddModelOpen(true)}
                sx={{ borderRadius: BORDER_RADIUS.sm }}
              >
                {CONNECT_MODEL_COPY.ownModelAction}
              </Button>
              <Typography variant="caption" color="text.secondary">
                {CONNECT_MODEL_COPY.ownModelHint}
              </Typography>
            </Box>
          )}

          {hasNoOption && (
            <Typography variant="body2" color="text.secondary">
              {CONNECT_MODEL_COPY.noAccess}
            </Typography>
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button size="small" onClick={handleCheckAgain} disabled={checking}>
            {CONNECT_MODEL_COPY.checkAgain}
          </Button>
          <Button size="small" color="inherit" onClick={() => handleSignOut()}>
            {CONNECT_MODEL_COPY.signOut}
          </Button>
        </Box>
      </Box>

      {rhesisKeyEnabled && (
        <PlatformKeyDrawer
          open={platformKeyOpen}
          onClose={() => setPlatformKeyOpen(false)}
        />
      )}

      {canAddModel && (
        <ModelConnectionDrawer
          open={addModelOpen}
          onClose={handleAddModelClose}
          providers={providers}
          modelType={MODEL_TYPES.LANGUAGE}
          mode="create"
          onConnect={handleConnect}
        />
      )}
    </Box>
  );
}
