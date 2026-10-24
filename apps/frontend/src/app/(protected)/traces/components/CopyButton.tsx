'use client';

import { useState } from 'react';
import { IconButton, Tooltip } from '@mui/material';
import { CheckIcon, ContentCopyIcon } from '@/components/icons';

interface CopyButtonProps {
  text: string;
  /** What is copied, for the accessible name: "Copy span ID". */
  label: string;
}

export default function CopyButton({ text, label }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be blocked (insecure origin, permissions); nothing useful to show.
    }
  };

  return (
    <Tooltip title={copied ? 'Copied' : label}>
      <IconButton
        size="small"
        aria-label={label}
        onClick={handleCopy}
        sx={{ p: 0.25, color: 'text.secondary' }}
      >
        {copied ? (
          <CheckIcon sx={{ fontSize: theme => theme.spacing(1.75) }} />
        ) : (
          <ContentCopyIcon sx={{ fontSize: theme => theme.spacing(1.75) }} />
        )}
      </IconButton>
    </Tooltip>
  );
}
