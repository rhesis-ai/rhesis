'use client';

import React, { useRef, useState } from 'react';
import {
  Box,
  IconButton,
  InputAdornment,
  Menu,
  MenuItem,
  TextField,
  Typography,
} from '@mui/material';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import ArrowRightIcon from '@mui/icons-material/ArrowRight';

const FILES_PROVIDERS = [
  { label: 'OpenAI', value: '{{ files | to_openai | tojson }}' },
  { label: 'Anthropic', value: '{{ files | to_anthropic | tojson }}' },
  { label: 'Gemini', value: '{{ files | to_gemini | tojson }}' },
];

interface Props {
  value: string;
  onChange: (value: string) => void;
  variables: string[];
  placeholder?: string;
}

export default function TemplateVariableInput({
  value,
  onChange,
  variables,
  placeholder,
}: Props) {
  const [anchor, setAnchor] = useState<null | HTMLElement>(null);
  const [filesAnchor, setFilesAnchor] = useState<null | HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const isSingleVariable = (v: string) => /^\s*\{\{[^}]+\}\}\s*$/.test(v);

  const insertVariable = (variable: string) => {
    setAnchor(null);
    setFilesAnchor(null);
    const el = inputRef.current;

    const shouldReplace = !value.trim() || isSingleVariable(value);
    if (shouldReplace) {
      onChange(variable);
      const cursorPos =
        variable === '{{ params. }}' ? '{{ params.'.length : variable.length;
      requestAnimationFrame(() => {
        el?.focus();
        el?.setSelectionRange(cursorPos, cursorPos);
      });
      return;
    }

    if (!el) {
      onChange(value + variable);
      return;
    }

    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    const next = value.slice(0, start) + variable + value.slice(end);
    onChange(next);

    const cursorPos =
      variable === '{{ params. }}'
        ? start + '{{ params.'.length
        : start + variable.length;

    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(cursorPos, cursorPos);
    });
  };

  const handleMenuItemClick = (v: string, e: React.MouseEvent<HTMLElement>) => {
    if (v === '{{ files }}') {
      setFilesAnchor(e.currentTarget);
    } else {
      insertVariable(v);
    }
  };

  return (
    <Box sx={{ width: '100%' }}>
      <TextField
        inputRef={inputRef}
        size="small"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder ?? 'value or {{ variable }}'}
        fullWidth
        inputProps={{ style: { fontFamily: 'monospace', fontSize: 12 } }}
        InputProps={{
          endAdornment: (
            <InputAdornment position="end">
              <IconButton
                size="small"
                tabIndex={-1}
                onClick={e => setAnchor(e.currentTarget)}
                sx={{ color: 'text.disabled', mr: -0.5 }}
              >
                <ArrowDropDownIcon fontSize="small" />
              </IconButton>
            </InputAdornment>
          ),
        }}
      />

      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={() => setAnchor(null)}
        slotProps={{ paper: { sx: { minWidth: 220 } } }}
      >
        {variables.map(v => (
          <MenuItem
            key={v}
            onClick={e => handleMenuItemClick(v, e)}
            sx={{
              fontFamily: 'monospace',
              fontSize: 12,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            {v}
            {v === '{{ files }}' && (
              <ArrowRightIcon
                fontSize="small"
                sx={{ color: 'text.disabled', ml: 1 }}
              />
            )}
          </MenuItem>
        ))}
      </Menu>

      {/* Files sub-menu */}
      <Menu
        anchorEl={filesAnchor}
        open={Boolean(filesAnchor)}
        onClose={() => setFilesAnchor(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'left' }}
        slotProps={{ paper: { sx: { minWidth: 200 } } }}
      >
        <Typography
          variant="caption"
          sx={{
            px: 2,
            py: 0.5,
            display: 'block',
            color: 'text.disabled',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
          }}
        >
          Provider format
        </Typography>
        {FILES_PROVIDERS.map(({ label, value: v }) => (
          <MenuItem
            key={label}
            onClick={() => insertVariable(v)}
            sx={{ fontSize: 12 }}
          >
            <Box>
              <Typography variant="body2" sx={{ fontSize: 12 }}>
                {label}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  fontFamily: 'monospace',
                  fontSize: 10,
                  color: 'text.disabled',
                }}
              >
                {v}
              </Typography>
            </Box>
          </MenuItem>
        ))}
      </Menu>
    </Box>
  );
}
