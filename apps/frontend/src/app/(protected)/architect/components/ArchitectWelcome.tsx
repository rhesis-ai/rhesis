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
  const [inputValue, setInputValue] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = () => {
    const trimmed = inputValue.trim();
    if (!trimmed || isSubmitting) return;
    setIsSubmitting(true);
    onSubmit(trimmed);
  };

  const handleSuggestedPrompt = (prompt: string) => {
    if (isSubmitting) return;
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
        alignItems: 'center',
        justifyContent: 'center',
        p: 4,
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
            fontWeight: theme => theme.typography.fontWeightLight,
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
          placeholder="Describe what you want to test..."
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isSubmitting}
          autoFocus
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
                    disabled={!inputValue.trim() || isSubmitting}
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
              disabled={isSubmitting}
              sx={{ cursor: 'pointer' }}
            />
          ))}
        </Box>
      </Box>
    </Box>
  );
}
