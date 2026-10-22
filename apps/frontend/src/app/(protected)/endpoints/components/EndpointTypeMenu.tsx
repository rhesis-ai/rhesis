'use client';

import React from 'react';
import { ListItemText, Menu, MenuItem } from '@mui/material';
import { OpenInNewIcon } from '@/components/icons';

const SDK_ENDPOINTS_DOCS_URL =
  'https://docs.rhesis.ai/docs/endpoints/sdk-endpoints';

interface EndpointTypeMenuProps {
  anchorEl: HTMLElement | null;
  onClose: () => void;
  onCreateRest: () => void;
}

/**
 * Asks which kind of endpoint to add. Only REST is created in the app; SDK
 * endpoints are registered from code, so that item opens the guide instead.
 */
export default function EndpointTypeMenu({
  anchorEl,
  onClose,
  onCreateRest,
}: EndpointTypeMenuProps) {
  return (
    <Menu
      anchorEl={anchorEl}
      open={Boolean(anchorEl)}
      onClose={onClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      transformOrigin={{ vertical: 'top', horizontal: 'right' }}
    >
      <MenuItem
        onClick={() => {
          onClose();
          onCreateRest();
        }}
      >
        REST endpoint
      </MenuItem>
      <MenuItem
        component="a"
        href={SDK_ENDPOINTS_DOCS_URL}
        target="_blank"
        rel="noopener noreferrer"
        onClick={onClose}
        sx={{ gap: 1.5 }}
      >
        <ListItemText>SDK Connector</ListItemText>
        <OpenInNewIcon fontSize="small" sx={{ color: 'text.disabled' }} />
      </MenuItem>
    </Menu>
  );
}
