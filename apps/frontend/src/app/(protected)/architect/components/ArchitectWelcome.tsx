'use client';

import React, { useState, useRef } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Typography,
  Chip,
  InputAdornment,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import ShieldOutlinedIcon from '@mui/icons-material/ShieldOutlined';
import BugReportOutlinedIcon from '@mui/icons-material/BugReportOutlined';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { useProjectNeedsEndpoint } from '@/hooks/useProjectNeedsEndpoint';
import ArchitectHelpSection from './ArchitectHelpSection';

const SUGGESTED_PROMPTS = [
  {
    label: 'Safety & fairness tests',
    prompt: 'I need safety and fairness tests for my LLM application',
    icon: ShieldOutlinedIcon,
  },
  {
    label: 'Test for vulnerabilities',
    prompt: 'Help me test for prompt injection vulnerabilities',
    icon: BugReportOutlinedIcon,
  },
  {
    label: 'RAG test suite',
    prompt: 'Create a comprehensive test suite for a RAG pipeline',
    icon: FactCheckOutlinedIcon,
  },
];

interface ArchitectWelcomeProps {
  onSubmit: (message: string) => void;
}

export default function ArchitectWelcome({ onSubmit }: ArchitectWelcomeProps) {
  const canCreate = useCan(Capability.Architect.CREATE);
  const { pending: endpointCheckPending, needsEndpoint } =
    useProjectNeedsEndpoint();
  const [inputValue, setInputValue] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const inputDisabled = isSubmitting || !canCreate;

  const handleSubmit = () => {
    const trimmed = inputValue.trim();
    if (!trimmed || inputDisabled) return;
    setIsSubmitting(true);
    onSubmit(trimmed);
  };

  const handleSuggestedPrompt = (prompt: string) => {
    if (inputDisabled) return;
    setIsSubmitting(true);
    onSubmit(prompt);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <Box
      sx={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        overflowY: 'auto',
        p: 4,
      }}
    >
      {/* `my: 'auto'` centres the group while it fits, then resolves to 0 and
          scrolls from the top once the help section makes it taller than the
          viewport. `justifyContent: 'center'` would clip the leading edge.
          The top padding only applies with the help section below: it counts
          towards the centred box's height, so on its own it would push the
          input off-centre by half its value. */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 3,
          width: '100%',
          my: 'auto',
          pt: needsEndpoint ? { xs: 6, md: 18 } : 0,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 3,
            width: '100%',
            maxWidth: theme => theme.spacing(85),
          }}
        >
          <Typography
            variant="h4"
            color="text.secondary"
            sx={{
              fontWeight: theme => theme.typography.fontWeightBold,
              textAlign: 'center',
            }}
          >
            What would you like to test?
          </Typography>

          <TextField
            inputRef={inputRef}
            fullWidth
            multiline
            maxRows={6}
            placeholder={
              canCreate
                ? 'Describe what you want to test...'
                : 'View-only access — you cannot start new Architect sessions'
            }
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={inputDisabled}
            autoFocus={canCreate}
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: theme => theme.spacing(3.5),
                py: 1,
                pl: 2,
                pr: 1,
                bgcolor: 'action.hover',
                '& fieldset': { borderColor: 'divider' },
              },
            }}
            slotProps={{
              input: {
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={handleSubmit}
                      disabled={!inputValue.trim() || inputDisabled}
                      sx={{
                        bgcolor: 'primary.main',
                        color: 'primary.contrastText',
                        width: theme => theme.spacing(4.5),
                        height: theme => theme.spacing(4.5),
                        '&:hover': { bgcolor: 'primary.dark' },
                        '&:disabled': {
                          bgcolor: 'action.disabledBackground',
                          color: 'action.disabled',
                        },
                      }}
                    >
                      <SendIcon fontSize="small" />
                    </IconButton>
                  </InputAdornment>
                ),
              },
            }}
          />

          {/* No endpoint means no prompt can actually run, so the suggestions
              are dead ends — the getting-started cards below replace them.
              Waiting out `pending` keeps the two from swapping visibly. */}
          {!endpointCheckPending && !needsEndpoint && (
            <Box
              sx={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 1,
                justifyContent: 'center',
              }}
            >
              {SUGGESTED_PROMPTS.map(({ label, prompt, icon: Icon }) => (
                <Chip
                  key={label}
                  icon={<Icon fontSize="small" />}
                  label={label}
                  variant="outlined"
                  onClick={() => handleSuggestedPrompt(prompt)}
                  disabled={inputDisabled}
                  sx={{ cursor: 'pointer' }}
                />
              ))}
            </Box>
          )}
        </Box>

        <ArchitectHelpSection />
      </Box>
    </Box>
  );
}
