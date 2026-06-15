'use client';

/**
 * Tabular list of AuthClient rows for one organization.
 *
 * Read-only display + per-row action menu. Mutating operations
 * (rotate, disable, enable, delete) bubble up via callbacks rather
 * than calling the API client directly so the parent owns the
 * lifecycle (including the secret-display dialog that follows a
 * successful rotate).
 *
 * Why not a DataGrid?
 * -------------------
 * The action buttons are state-dependent (disable vs enable, delete
 * gated on disabled) and we want a confirmation dialog per
 * destructive action. MUI's DataGrid pushes those into custom cell
 * renderers that end up bigger than a plain table. The list will
 * never have hundreds of rows for a single org -- a plain `Table`
 * is the right shape.
 */

import * as React from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
} from '@mui/material';
import {
  Refresh as RotateIcon,
  Block as DisableIcon,
  CheckCircle as EnableIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import type { AuthClient } from '../types';

export interface ApiClientsListProps {
  clients: AuthClient[];
  loading: boolean;
  /** Called when the rotate-secret button on a row is clicked + confirmed. */
  onRotate: (client: AuthClient) => Promise<void>;
  onDisable: (client: AuthClient) => Promise<void>;
  onEnable: (client: AuthClient) => Promise<void>;
  /** Only callable when `client.disabled === true`; the UI hides the button otherwise. */
  onDelete: (client: AuthClient) => Promise<void>;
}

/**
 * State machine for the per-row confirm dialog. We use one shared
 * dialog with three modes rather than three separate dialogs because
 * exactly one confirmation can be open at a time (we own the
 * controlled `open` flag) and the styling is identical.
 */
type ConfirmAction = 'rotate' | 'disable' | 'delete';
interface ConfirmState {
  client: AuthClient;
  action: ConfirmAction;
}

const ACTION_COPY: Record<
  ConfirmAction,
  { title: string; body: string; cta: string; danger: boolean }
> = {
  rotate: {
    title: 'Rotate client secret?',
    body:
      'A new secret will be issued and the previous one will stop ' +
      'working immediately. Tokens issued before now stay valid until ' +
      'they expire, but cannot be refreshed without the new secret.',
    cta: 'Rotate',
    danger: false,
  },
  disable: {
    title: 'Disable client?',
    body:
      'New token-exchange requests from this client will fail with ' +
      'invalid_client. Existing access tokens stay valid until they ' +
      'expire. You can re-enable the client at any time.',
    cta: 'Disable',
    danger: true,
  },
  delete: {
    title: 'Delete client?',
    body:
      'This permanently removes the client. There is no undo. Any ' +
      'integration still using these credentials will start failing ' +
      'with invalid_client.',
    cta: 'Delete',
    danger: true,
  },
};

export default function ApiClientsList({
  clients,
  loading,
  onRotate,
  onDisable,
  onEnable,
  onDelete,
}: ApiClientsListProps) {
  const [confirm, setConfirm] = React.useState<ConfirmState | null>(null);
  const [working, setWorking] = React.useState(false);

  const handleConfirm = async () => {
    if (!confirm) return;
    setWorking(true);
    try {
      switch (confirm.action) {
        case 'rotate':
          await onRotate(confirm.client);
          break;
        case 'disable':
          await onDisable(confirm.client);
          break;
        case 'delete':
          await onDelete(confirm.client);
          break;
      }
      setConfirm(null);
    } finally {
      setWorking(false);
    }
  };

  if (loading || clients.length === 0) {
    return null;
  }

  return (
    <>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Client ID</TableCell>
              <TableCell>Name</TableCell>
              <TableCell>Expected azp</TableCell>
              <TableCell>Scopes</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {clients.map(client => (
              <TableRow key={client.id} hover>
                <TableCell sx={{ fontFamily: 'monospace' }}>
                  {client.client_id}
                </TableCell>
                <TableCell>{client.name ?? '-'}</TableCell>
                <TableCell sx={{ fontFamily: 'monospace' }}>
                  {client.expected_subject_azp}
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap">
                    {client.allowed_scopes.map(scope => {
                      const isDefault = scope === client.default_scope;
                      const chip = (
                        <Chip
                          key={scope}
                          label={scope}
                          size="small"
                          variant="outlined"
                        />
                      );
                      // Tooltip the default scope so the distinction
                      // we previously encoded with a filled variant
                      // isn't lost; the chips themselves render with
                      // a single consistent style.
                      return isDefault ? (
                        <Tooltip key={scope} title="Default scope">
                          {chip}
                        </Tooltip>
                      ) : (
                        chip
                      );
                    })}
                  </Stack>
                </TableCell>
                <TableCell>
                  {client.disabled ? (
                    <Chip label="Disabled" size="small" color="warning" />
                  ) : (
                    <Chip label="Active" size="small" color="success" />
                  )}
                </TableCell>
                <TableCell>{formatDate(client.created_at)}</TableCell>
                <TableCell align="right">
                  <Tooltip title="Rotate secret">
                    <span>
                      <IconButton
                        size="small"
                        onClick={() =>
                          setConfirm({ client, action: 'rotate' })
                        }
                        aria-label={`Rotate secret for ${client.client_id}`}
                      >
                        <RotateIcon fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                  {client.disabled ? (
                    <Tooltip title="Re-enable">
                      <span>
                        <IconButton
                          size="small"
                          onClick={() => onEnable(client)}
                          aria-label={`Enable ${client.client_id}`}
                        >
                          <EnableIcon fontSize="small" />
                        </IconButton>
                      </span>
                    </Tooltip>
                  ) : (
                    <Tooltip title="Disable">
                      <span>
                        <IconButton
                          size="small"
                          onClick={() =>
                            setConfirm({ client, action: 'disable' })
                          }
                          aria-label={`Disable ${client.client_id}`}
                        >
                          <DisableIcon fontSize="small" />
                        </IconButton>
                      </span>
                    </Tooltip>
                  )}
                  {/*
                    Delete is gated on `disabled` because the backend
                    rejects DELETE on an enabled client (409). Showing
                    the button anyway would lead the operator into a
                    failed action; hiding it makes the two-step
                    workflow (disable then delete) obvious.
                  */}
                  {client.disabled && (
                    <Tooltip title="Delete">
                      <span>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() =>
                            setConfirm({ client, action: 'delete' })
                          }
                          aria-label={`Delete ${client.client_id}`}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </span>
                    </Tooltip>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog
        open={confirm !== null}
        onClose={() => !working && setConfirm(null)}
        maxWidth="xs"
        fullWidth
      >
        {confirm && (
          <>
            <DialogTitle>{ACTION_COPY[confirm.action].title}</DialogTitle>
            <DialogContent>
              <DialogContentText>
                {ACTION_COPY[confirm.action].body}
              </DialogContentText>
              <Box sx={{ mt: 2, fontFamily: 'monospace' }}>
                {confirm.client.client_id}
              </Box>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setConfirm(null)} disabled={working}>
                Cancel
              </Button>
              <Button
                variant="contained"
                color={ACTION_COPY[confirm.action].danger ? 'error' : 'primary'}
                onClick={handleConfirm}
                disabled={working}
                startIcon={working ? <CircularProgress size={16} /> : undefined}
              >
                {ACTION_COPY[confirm.action].cta}
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </>
  );
}

function formatDate(iso: string): string {
  // Locale-formatted short date; the full timestamp is in the
  // browser DevTools if the user inspects the row, no need to
  // crowd the column.
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}
