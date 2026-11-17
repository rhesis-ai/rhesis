'use client';

import * as React from 'react';
import { Box, IconButton, TextField, Tooltip, Typography } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import BaseDrawer from '@/components/common/BaseDrawer';

/** The page title with the rename button test runs have; renaming opens a drawer. */
export default function ReportTitle({
  title,
  canRename,
  onRename,
}: {
  title: string;
  canRename: boolean;
  /** Resolves false when the rename failed; the drawer then stays open. */
  onRename: (title: string) => Promise<boolean>;
}) {
  const [open, setOpen] = React.useState(false);
  const [value, setValue] = React.useState(title);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | undefined>();
  const next = value.trim();
  const unchanged = !next || next === title;

  const submit = async () => {
    if (unchanged) return;
    setSaving(true);
    setError(undefined);
    try {
      if (await onRename(next)) setOpen(false);
      else setError('Failed to rename the report. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
        <Typography
          variant="h4"
          component="h1"
          noWrap
          sx={{
            fontWeight: 700,
            color: theme => theme.palette.greyscale.title,
          }}
        >
          {title}
        </Typography>
        {canRename && (
          <Tooltip title="Rename report">
            <IconButton
              size="small"
              aria-label="Rename"
              onClick={() => {
                setValue(title);
                setError(undefined);
                setOpen(true);
              }}
              sx={{ displayPrint: 'none' }}
            >
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Box>
      <BaseDrawer
        open={open}
        onClose={() => setOpen(false)}
        title="Rename Report"
        onSave={() => void submit()}
        saveDisabled={unchanged}
        saveButtonText="Save"
        loading={saving}
        error={error}
      >
        <TextField
          autoFocus
          fullWidth
          label="Title"
          value={value}
          onChange={e => setValue(e.target.value)}
          inputProps={{ maxLength: 200 }}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              e.preventDefault();
              void submit();
            }
          }}
          sx={{ flexShrink: 0 }}
        />
      </BaseDrawer>
    </>
  );
}
