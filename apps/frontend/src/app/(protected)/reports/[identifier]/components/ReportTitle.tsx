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
  onRename: (title: string) => Promise<void>;
}) {
  const [open, setOpen] = React.useState(false);
  const [value, setValue] = React.useState(title);
  const [saving, setSaving] = React.useState(false);
  const next = value.trim();
  const unchanged = !next || next === title;

  const submit = async () => {
    if (unchanged) return;
    setSaving(true);
    try {
      await onRename(next);
      setOpen(false);
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
