'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  Button,
  Paper,
} from '@mui/material';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import EditIcon from '@mui/icons-material/Edit';
import ShieldIcon from '@mui/icons-material/Shield';
import PeopleIcon from '@mui/icons-material/People';
import SpeedIcon from '@mui/icons-material/Speed';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DescriptionIcon from '@mui/icons-material/Description';

interface TestGenerationLandingProps {
  sessionToken: string;
}

interface TestSetTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  testCount: number;
  color: string;
  icon: React.ReactNode;
}

const testSetTemplates: TestSetTemplate[] = [
  {
    id: 'gdpr-compliance',
    name: 'GDPR Compliance',
    description: 'Comprehensive GDPR compliance validation tests',
    category: 'Data Protection',
    testCount: 243,
    color: theme.palette.primary.main,
    icon: <ShieldIcon />,
  },
  {
    id: 'bias-detection',
    name: 'Bias Detection',
    description: 'AI model bias and fairness evaluation',
    category: 'Fairness',
    testCount: 178,
    color: theme.palette.secondary.main,
    icon: <PeopleIcon />,
  },
  {
    id: 'performance-testing',
    name: 'Performance Testing',
    description: 'Response time and scalability testing',
    category: 'Speed & Load',
    testCount: 92,
    color: theme.palette.warning.main,
    icon: <SpeedIcon />,
  },
  {
    id: 'financial-services',
    name: 'Financial Services',
    description: 'Financial industry specific test scenarios',
    category: 'Banking & Finance',
    testCount: 201,
    color: theme.palette.info.main,
    icon: <TrendingUpIcon />,
  },
];

export default function TestGenerationLanding({
  sessionToken,
}: TestGenerationLandingProps) {
  const router = useRouter();

  const handleAIGeneration = () => {
    router.push('/tests/generate/describe');
  };

  const handleManualWriting = () => {
    router.push('/tests/new-manual');
  };

  const handleUseTemplate = (templateId: string) => {
    // TODO: Implement template usage
    console.log('Using template:', templateId);
  };

  const handleViewMoreTemplates = () => {
    // TODO: Navigate to templates page
    console.log('View more templates');
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ textAlign: 'center', mb: 6 }}>
        <Typography variant="h3" component="h1" gutterBottom fontWeight="bold">
          Test Generation
        </Typography>
        <Typography variant="h6" color="text.secondary" sx={{ maxWidth: 600, mx: 'auto' }}>
          Create comprehensive test cases using AI-powered generation or select from recommended test sets.
        </Typography>
      </Box>

      {/* Generation Options */}
      <Grid container spacing={4} sx={{ mb: 8 }}>
        <Grid item xs={12} md={6}>
          <Card
            sx={{
              height: '100%',
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
                sx={{
                  width: 80,
                  height: 80,
                  borderRadius: theme.shape.borderRadius,
                  bgcolor: 'primary.main',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  mx: 'auto',
                  mb: 3,
                }}
              >
                <AutoFixHighIcon sx={{ fontSize: 40, color: 'white' }} />
              </Box>
              <Typography variant="h5" component="h2" gutterBottom fontWeight="bold">
                Generate Tests with AI
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
                Describe your testing needs and let AI create comprehensive test cases.
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
        </Grid>

        <Grid item xs={12} md={6}>
          <Card
            sx={{
              height: '100%',
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
                sx={{
                  width: 80,
                  height: 80,
                  borderRadius: theme.shape.borderRadius,
                  bgcolor: 'grey.800',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  mx: 'auto',
                  mb: 3,
                }}
              >
                <EditIcon sx={{ fontSize: 40, color: 'white' }} />
              </Box>
              <Typography variant="h5" component="h2" gutterBottom fontWeight="bold">
                Write Tests Manually
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
                Create custom test cases with full control over content and format.
              </Typography>
              <Button
                variant="outlined"
                size="large"
                startIcon={<EditIcon />}
                onClick={handleManualWriting}
                sx={{ px: 4, py: 1.5 }}
              >
                Start Writing
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Existing Test Sets */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h2" gutterBottom fontWeight="bold" sx={{ mb: 4 }}>
          Or use our existing test sets
        </Typography>

        <Grid container spacing={3}>
          {testSetTemplates.map((template) => (
            <Grid item xs={12} sm={6} md={3} key={template.id}>
              <Card
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'transform 0.2s, box-shadow 0.2s',
                  '&:hover': {
                    transform: 'translateY(-2px)',
                    boxShadow: 3,
                  },
                }}
              >
                <CardContent sx={{ flexGrow: 1, p: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Box
                      sx={{
                        width: 12,
                        height: 12,
                        borderRadius: '50%',
                        bgcolor: template.color,
                        mr: 1,
                      }}
                    />
                    <Box
                      sx={{
                        width: 40,
                        height: 40,
                        borderRadius: theme.shape.borderRadius * 0.5,
                        bgcolor: `${template.color}20`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: template.color,
                      }}
                    >
                      {template.icon}
                    </Box>
                  </Box>

                  <Typography variant="h6" component="h3" gutterBottom fontWeight="bold">
                    {template.name}
                  </Typography>

                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    {template.category}
                  </Typography>

                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    {template.description}
                  </Typography>

                  <Typography variant="body2" fontWeight="medium" sx={{ mb: 2 }}>
                    {template.testCount} tests
                  </Typography>

                  <Button
                    variant="contained"
                    size="small"
                    startIcon={<PlayArrowIcon />}
                    onClick={() => handleUseTemplate(template.id)}
                    sx={{ width: '100%' }}
                  >
                    Use
                  </Button>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>

      {/* Footer */}
      <Box sx={{ textAlign: 'center', mt: 6 }}>
        <Button
          variant="outlined"
          startIcon={<DescriptionIcon />}
          onClick={handleViewMoreTemplates}
          sx={{ px: 4, py: 1.5 }}
        >
          View More Templates
        </Button>
      </Box>
    </Container>
  );
}
