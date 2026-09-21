'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import { FilledStatusAlert } from '@/components/common/FilledStatusAlert';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestToolConnectionResponse } from '@/utils/api-client/services-client';
import {
  Tool,
  ToolCreate,
  ToolUpdate,
  TypeLookup,
} from '@/utils/api-client/interfaces/tool';
import type { ToolProvider } from '@/utils/api-client/interfaces/tool-provider';
import { useToolProviders } from '@/hooks/useToolProviders';
import { getErrorMessage } from '@/utils/entity-error-handler';
import type { UUID } from 'crypto';
import { ProviderPicker } from './ProviderPicker';
import { ProviderFields, type FieldOption } from './fields/ProviderFields';
import {
  buildCredentials,
  buildMetadata,
  emptyValues,
  hydrateValues,
  missingRequired,
  type FieldValues,
} from './fields/values';

/** Resolve the provider TypeLookup for a tool in edit mode. */
function resolveToolProvider(
  tool: Tool | null | undefined,
  providers: TypeLookup[]
): TypeLookup | null {
  const embedded = tool?.tool_provider_type;
  if (!embedded) return null;
  return (
    providers.find(p => p.id === embedded.id) ??
    providers.find(p => p.type_value === embedded.type_value) ??
    embedded
  );
}

interface ToolConnectionDrawerProps {
  open: boolean;
  provider?: TypeLookup | null;
  providers?: TypeLookup[];
  toolType?: TypeLookup | null;
  tool?: Tool | null;
  mode?: 'create' | 'edit';
  onClose: () => void;
  onConnect?: (providerId: string, toolData: ToolCreate) => Promise<Tool>;
  onUpdate?: (toolId: UUID, updates: Partial<ToolUpdate>) => Promise<void>;
}

export function ToolConnectionDrawer({
  open,
  provider: providerProp,
  providers = [],
  tool,
  mode = 'create',
  onClose,
  onConnect,
  onUpdate,
}: ToolConnectionDrawerProps) {
  const isEditMode = mode === 'edit';

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [values, setValues] = useState<FieldValues>({});
  const [baseline, setBaseline] = useState<{
    name: string;
    description: string;
    values: FieldValues;
  }>({ name: '', description: '', values: {} });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] =
    useState<TestToolConnectionResponse | null>(null);
  const [connectionTested, setConnectionTested] = useState(false);
  const [spaces, setSpaces] = useState<FieldOption[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<TypeLookup | null>(
    providerProp ?? null
  );

  const { data: toolProviders = [], isLoading: providersLoading } =
    useToolProviders();

  const sortedProviders = useMemo(
    () =>
      [...providers].sort((a, b) => a.type_value.localeCompare(b.type_value)),
    [providers]
  );

  const providerLookup = useMemo(() => {
    if (isEditMode && tool) return resolveToolProvider(tool, providers);
    return selectedProvider ?? providerProp ?? null;
  }, [isEditMode, tool, providers, selectedProvider, providerProp]);

  const manifest: ToolProvider | null = useMemo(() => {
    const key = providerLookup?.type_value;
    return toolProviders.find(p => p.key === key) ?? null;
  }, [toolProviders, providerLookup]);

  const toolId = tool?.id ?? null;

  // Reset when the drawer opens, or when it is reused for a different tool.
  //
  // Keyed on identifiers rather than on `tool` and `providers` themselves: the
  // lookups query swaps its array for a fresh one when it resolves, and the
  // parent can re-render with a new `tool` object for the same row. Depending
  // on either would re-run this and wipe whatever the user had typed.
  useEffect(() => {
    if (!open) return;

    setError(null);
    setTestResult(null);
    setConnectionTested(false);
    setSpaces([]);

    if (isEditMode && tool) {
      setName(tool.name || '');
      setDescription(tool.description || '');
    } else {
      setName('');
      setDescription('');
      setValues({});
      setBaseline({ name: '', description: '', values: {} });
    }
    // Reset is keyed on the drawer opening and on which tool, not on object
    // identity, for the reason above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, isEditMode, toolId]);

  // Track which provider is selected. Kept apart from the reset above so that
  // refreshed lookups update the selection without clearing the form.
  useEffect(() => {
    if (!open) {
      setSelectedProvider(providerProp ?? null);
      return;
    }
    if (isEditMode && tool) {
      const resolved = resolveToolProvider(tool, providers);
      if (resolved) setSelectedProvider(resolved);
    }
  }, [open, isEditMode, tool, providers, providerProp]);

  // Seed the field values once the manifest for the chosen provider is known.
  const manifestKey = manifest?.key ?? null;

  useEffect(() => {
    if (!open || !manifest) return;
    const seeded =
      isEditMode && tool
        ? hydrateValues(manifest, tool)
        : emptyValues(manifest);
    setValues(seeded);
    setBaseline({
      name: isEditMode && tool ? tool.name || '' : '',
      description: isEditMode && tool ? tool.description || '' : '',
      values: seeded,
    });
    // Keyed on identifiers, never on object identity. React Query hands back a
    // fresh manifest array on a refetch, and the parent can re-render with a
    // new `tool` for the same row; depending on either would reseed the form
    // and discard edits in progress.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, manifestKey, isEditMode, toolId]);

  const setValue = useCallback((key: string, value: string) => {
    setValues(prev => ({ ...prev, [key]: value }));
    setConnectionTested(false);
    setTestResult(null);
  }, []);

  const missing = manifest ? missingRequired(manifest, values) : [];
  const credentialsChanged = manifest
    ? Object.keys(buildCredentials(manifest, values)).length > 0
    : false;
  const scopeChanged = manifest
    ? manifest.fields
        .filter(f => f.store === 'metadata')
        .some(f => (values[f.key] ?? '') !== (baseline.values[f.key] ?? ''))
    : false;
  const detailsChanged =
    name !== baseline.name || description !== baseline.description;
  const needsRetest = credentialsChanged || scopeChanged;

  const handleTestConnection = async () => {
    if (!manifest || !providerLookup) return;
    setTesting(true);
    setError(null);

    try {
      const { metadata, error: metadataError } = buildMetadata(
        manifest,
        values
      );
      if (metadataError) {
        setTestResult({ is_authenticated: 'No', message: metadataError });
        setConnectionTested(false);
        return;
      }

      const credentials = buildCredentials(manifest, values);
      const servicesClient = new ApiClientFactory().getServicesClient();

      // With a saved tool and no re-entered credentials, the backend fills the
      // rest from what is stored, so only the scope override travels.
      const request =
        isEditMode && tool?.id && Object.keys(credentials).length === 0
          ? { tool_id: tool.id, tool_metadata: metadata }
          : {
              ...(isEditMode && tool?.id ? { tool_id: tool.id } : {}),
              provider_type_id: providerLookup.id as string,
              credentials,
              tool_metadata: metadata,
            };

      const result = await servicesClient.testToolConnection(request);
      setTestResult(result);

      if (result.is_authenticated === 'Yes') {
        setConnectionTested(true);
        // Some providers hand back the scopes they can see; offer them as
        // choices rather than making the user find the key by hand.
        const offered =
          result.additional_metadata?.spaces ??
          result.additional_metadata?.projects ??
          [];
        setSpaces(offered);
      } else {
        setConnectionTested(false);
        setSpaces([]);
      }
    } catch (err) {
      setTestResult({
        is_authenticated: 'No',
        message:
          getErrorMessage(err) ||
          'Failed to test connection. Please try again.',
      });
      setConnectionTested(false);
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async () => {
    if (!manifest || !providerLookup) return;
    setLoading(true);
    setError(null);

    try {
      const { metadata, error: metadataError } = buildMetadata(
        manifest,
        values
      );
      if (metadataError) {
        setError(metadataError);
        return;
      }
      const credentials = buildCredentials(manifest, values);

      if (isEditMode && tool && onUpdate) {
        const updates: Partial<ToolUpdate> = {
          name,
          description: description || undefined,
        };
        // Omitted rather than sent empty: the backend keeps what is stored for
        // any field the manifest marks preserve_on_update.
        if (Object.keys(credentials).length > 0) {
          updates.credentials = credentials;
        }
        if (scopeChanged) {
          updates.tool_metadata = metadata;
        }
        await onUpdate(tool.id, updates);
      } else if (onConnect) {
        await onConnect(providerLookup.id as string, {
          name,
          description: description || undefined,
          tool_provider_type_id: providerLookup.id as UUID,
          credentials,
          tool_metadata: metadata,
        });
      }
      onClose();
    } catch (err) {
      setError(getErrorMessage(err) || 'Failed to save the connection.');
    } finally {
      setLoading(false);
    }
  };

  // Empty in edit mode until something actually changes, and an Alert with no
  // content still draws its box.
  const testPrompt =
    connectionTested || testResult
      ? null
      : isEditMode
        ? needsRetest
          ? 'Please test the connection with your changes before saving.'
          : null
        : 'Please test the connection before saving the tool configuration.';

  const showForm = isEditMode || Boolean(providerLookup);
  const saveDisabled =
    loading ||
    !name.trim() ||
    missing.length > 0 ||
    (isEditMode
      ? (!detailsChanged && !needsRetest) || (needsRetest && !connectionTested)
      : !connectionTested);

  const drawerTitle = isEditMode
    ? `Edit ${manifest?.display_name ?? 'tool'} connection`
    : providerLookup
      ? `Connect ${manifest?.display_name ?? providerLookup.type_value}`
      : 'Add tool connection';

  const sectionHeadingSx = {
    fontWeight: 600,
    color: 'text.primary',
  } as const;

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title={drawerTitle}
      onSave={() => void handleSubmit()}
      saveDisabled={saveDisabled}
      saveButtonText={isEditMode ? 'Update' : 'Connect'}
      loading={loading}
      error={error ?? undefined}
      width={640}
    >
      <Stack spacing={3}>
        {!isEditMode && (
          <Stack spacing={1}>
            <Typography sx={sectionHeadingSx}>Provider</Typography>
            <ProviderPicker
              lookups={sortedProviders}
              providers={toolProviders}
              loading={providersLoading}
              selectedId={providerLookup?.id ?? null}
              onSelect={choice => {
                const next = sortedProviders.find(p => p.id === choice.id);
                setSelectedProvider(next ?? null);
                setConnectionTested(false);
                setTestResult(null);
                setError(null);
              }}
            />
          </Stack>
        )}

        {showForm && manifest && (
          <>
            <Stack spacing={3}>
              <TextField
                label="Connection Name"
                fullWidth
                required
                value={name}
                onChange={e => setName(e.target.value)}
              />
              <TextField
                label="Description"
                fullWidth
                multiline
                rows={2}
                value={description}
                onChange={e => setDescription(e.target.value)}
              />
            </Stack>

            <Stack spacing={3}>
              <Typography sx={sectionHeadingSx}>Authentication</Typography>
              <ProviderFields
                manifest={manifest}
                values={values}
                onChange={setValue}
                options={{ space_key: spaces }}
                disabled={loading}
              />

              <Box>
                <Button
                  variant="outlined"
                  size="medium"
                  onClick={() => void handleTestConnection()}
                  disabled={testing || loading || missing.length > 0}
                  sx={{ minWidth: 150 }}
                >
                  {testing ? 'Testing...' : 'Test Connection'}
                </Button>
                {testResult && (
                  <Box sx={{ mt: 2 }}>
                    <FilledStatusAlert
                      severity={
                        testResult.is_authenticated === 'Yes'
                          ? 'success'
                          : 'error'
                      }
                      title={
                        testResult.is_authenticated === 'Yes'
                          ? 'Connection Successful'
                          : 'Connection Failed'
                      }
                      description={testResult.message}
                    />
                  </Box>
                )}
              </Box>
            </Stack>

            {testPrompt && <Alert severity="info">{testPrompt}</Alert>}
          </>
        )}
      </Stack>
    </BaseDrawer>
  );
}
