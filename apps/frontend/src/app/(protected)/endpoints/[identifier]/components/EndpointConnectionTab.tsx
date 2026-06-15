'use client';

import { useMemo } from 'react';
import {
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Box,
} from '@mui/material';
import EditableSection from '@/components/common/EditableSection';
import ViewField from '@/components/common/ViewField';
import { normalizeUrl } from '@/utils/validation';
import { useEndpointDetailContext } from './EndpointDetailContext';
import { METHODS } from './endpoint-detail-shared';
import { detailGridSpacing } from './endpoint-overview-utils';
import EndpointSdkConnectionPanel from './EndpointSdkConnectionPanel';

interface RestConnectionDraft {
  url: string;
  method: string;
}

export default function EndpointConnectionTab() {
  const { endpoint, saveFields } = useEndpointDetailContext();

  const restInitial = useMemo(
    () => ({
      url: endpoint.url || '',
      method: endpoint.method || 'POST',
    }),
    [endpoint.url, endpoint.method]
  );

  if (endpoint.connection_type === 'SDK') {
    return <EndpointSdkConnectionPanel />;
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      <EditableSection<RestConnectionDraft>
        title="REST connection"
        initialValue={restInitial}
        onSave={async draft => {
          await saveFields({
            url: normalizeUrl(draft.url),
            method: draft.method,
          });
        }}
      >
        {({ draft, setDraft, isEditing }) => (
          <Grid
            container
            columnSpacing={detailGridSpacing.columnSpacing(isEditing)}
            rowSpacing={detailGridSpacing.rowSpacing(isEditing)}
          >
            <Grid size={{ xs: 12, md: 8 }}>
              {isEditing ? (
                <TextField
                  fullWidth
                  label="URL"
                  placeholder="api.example.com or https://api.example.com"
                  helperText="https:// will be added automatically if omitted"
                  value={draft.url}
                  onChange={e =>
                    setDraft(prev => ({ ...prev, url: e.target.value }))
                  }
                />
              ) : (
                <ViewField label="URL" value={endpoint.url || '—'} />
              )}
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              {isEditing ? (
                <FormControl fullWidth>
                  <InputLabel>Method</InputLabel>
                  <Select
                    value={draft.method}
                    label="Method"
                    onChange={e =>
                      setDraft(prev => ({ ...prev, method: e.target.value }))
                    }
                  >
                    {METHODS.map(method => (
                      <MenuItem key={method} value={method}>
                        {method}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              ) : (
                <ViewField label="Method" value={endpoint.method || '—'} />
              )}
            </Grid>
            <Grid size={12}>
              <ViewField
                label="Connection type"
                value={endpoint.connection_type}
              />
            </Grid>
          </Grid>
        )}
      </EditableSection>
    </Box>
  );
}
