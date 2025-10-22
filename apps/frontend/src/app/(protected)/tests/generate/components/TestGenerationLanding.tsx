'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Button,
} from '@mui/material';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';

interface TestGenerationLandingProps {
  sessionToken: string;
  onGenerationTypeSelect?: (type: 'ai') => void;
}

export default function TestGenerationLanding({
  sessionToken,
  onGenerationTypeSelect,
}: TestGenerationLandingProps) {
  const router = useRouter();

  const handleAIGeneration = () => {
    if (onGenerationTypeSelect) {
      onGenerationTypeSelect('ai');
    } else {
      router.push('/tests/generate/describe');
    }
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ textAlign: 'center', mb: 6 }}>
        <Typography variant="h3" component="h1" gutterBottom fontWeight="bold">
          Test Generation
        </Typography>
        <Typography
          variant="h6"
          color="text.secondary"
          sx={{ maxWidth: 600, mx: 'auto' }}
        >
          Create comprehensive test cases using AI-powered generation.
        </Typography>
      </Box>

      {/* AI Generation Option */}
      <Box sx={{ display: 'flex', justifyContent: 'center', mb: 8 }}>
        <Card
          sx={{
            maxWidth: 500,
            width: '100%',
            display: 'flex',
            flexDirection: 'column',
            transition: 'transform 0.2s, box-shadow 0.2s',
            '&:hover': {
              transform: 'translateY(-4px)',
              boxShadow: 4,
            },
          }}
        >
          <CardContent sx={{ flexGrow: 1, textAlign: 'center', p: 4 }}>
            <Box
              sx={theme => ({
                width: 80,
                height: 80,
                borderRadius: theme.shape.borderRadius,
                bgcolor: 'primary.main',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                mx: 'auto',
                mb: 3,
              })}
            >
              <AutoFixHighIcon
                sx={{ fontSize: 40, color: 'primary.contrastText' }}
              />
            </Box>
            <Typography
              variant="h5"
              component="h2"
              gutterBottom
              fontWeight="bold"
            >
              Generate Tests with AI
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
              Describe your testing needs and let AI create comprehensive test
              cases.
            </Typography>
            <Button
              variant="contained"
              size="large"
              startIcon={<AutoFixHighIcon />}
              onClick={handleAIGeneration}
              sx={{ px: 4, py: 1.5 }}
            >
              Start Generation
            </Button>
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
}
