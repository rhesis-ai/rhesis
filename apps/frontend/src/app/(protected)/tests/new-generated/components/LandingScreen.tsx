'use client';

import React, { useState } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  Button,
  Chip,
  Avatar,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
} from '@mui/material';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import EditNoteIcon from '@mui/icons-material/EditNote';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import CloseIcon from '@mui/icons-material/Close';
import ShieldIcon from '@mui/icons-material/Shield';
import GavelIcon from '@mui/icons-material/Gavel';
import SpeedIcon from '@mui/icons-material/Speed';
import PsychologyIcon from '@mui/icons-material/Psychology';
import HealthAndSafetyIcon from '@mui/icons-material/HealthAndSafety';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import SecurityIcon from '@mui/icons-material/Security';
import AccessibilityNewIcon from '@mui/icons-material/AccessibilityNew';
import LanguageIcon from '@mui/icons-material/Language';
import PrivacyTipIcon from '@mui/icons-material/PrivacyTip';
import BalanceIcon from '@mui/icons-material/Balance';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import { TestTemplate } from './shared/types';

interface LandingScreenProps {
  open: boolean;
  onClose: () => void;
  onSelectAI: () => void;
  onSelectManual: () => void;
  onSelectTemplate: (template: TestTemplate) => void;
}

// Template library with 12 predefined templates
const TEMPLATES: TestTemplate[] = [
  {
    id: 'gdpr-compliance',
    name: 'GDPR Compliance',
    description: 'Test privacy and data protection compliance',
    icon: ShieldIcon,
    color: 'primary.main',
    behaviors: ['Compliance', 'Privacy'],
    topics: ['GDPR', 'Data Protection', 'User Rights'],
    category: ['Legal', 'Privacy'],
    scenarios: ['Data Access Request', 'Right to be Forgotten'],
    popularity: 'high',
    tags: ['GDPR', 'Privacy', 'Legal'],
  },
  {
    id: 'bias-detection',
    name: 'Bias Detection',
    description: 'Identify and test for AI biases',
    icon: BalanceIcon,
    color: 'secondary.main',
    behaviors: ['Fairness', 'Reliability'],
    topics: ['Bias', 'Fairness', 'Demographics'],
    category: ['Ethics', 'Quality'],
    scenarios: ['Gender Bias', 'Racial Bias', 'Age Bias'],
    popularity: 'high',
    tags: ['Bias', 'Fairness', 'Ethics'],
  },
  {
    id: 'performance-testing',
    name: 'Performance Testing',
    description: 'Test response quality and latency',
    icon: SpeedIcon,
    color: 'warning.main',
    behaviors: ['Reliability', 'Performance'],
    topics: ['Speed', 'Quality', 'Consistency'],
    category: ['Performance', 'Quality'],
    scenarios: ['High Load', 'Edge Cases', 'Error Handling'],
    popularity: 'high',
    tags: ['Performance', 'Speed', 'Quality'],
  },
  {
    id: 'hallucination-detection',
    name: 'Hallucination Detection',
    description: 'Detect factual inaccuracies',
    icon: PsychologyIcon,
    color: 'error.main',
    behaviors: ['Reliability', 'Accuracy'],
    topics: ['Facts', 'Accuracy', 'Verification'],
    category: ['Quality', 'Reliability'],
    scenarios: ['Fact Checking', 'Source Verification'],
    popularity: 'medium',
    tags: ['Hallucination', 'Accuracy', 'Facts'],
  },
  {
    id: 'medical-safety',
    name: 'Medical Safety',
    description: 'Test healthcare AI applications',
    icon: HealthAndSafetyIcon,
    color: 'success.main',
    behaviors: ['Safety', 'Compliance'],
    topics: ['Medical', 'Safety', 'HIPAA'],
    category: ['Healthcare', 'Safety'],
    scenarios: ['Medical Advice', 'Patient Privacy'],
    popularity: 'medium',
    tags: ['Healthcare', 'Safety', 'HIPAA'],
  },
  {
    id: 'financial-compliance',
    name: 'Financial Compliance',
    description: 'Test financial service regulations',
    icon: AccountBalanceIcon,
    color: 'info.main',
    behaviors: ['Compliance', 'Security'],
    topics: ['Financial', 'Regulations', 'Security'],
    category: ['Finance', 'Legal'],
    scenarios: ['KYC', 'AML', 'Transaction Security'],
    popularity: 'medium',
    tags: ['Finance', 'Compliance', 'Security'],
  },
  {
    id: 'security-testing',
    name: 'Security Testing',
    description: 'Test for security vulnerabilities',
    icon: SecurityIcon,
    color: 'error.dark',
    behaviors: ['Security', 'Reliability'],
    topics: ['Security', 'Vulnerabilities', 'Attacks'],
    category: ['Security', 'Testing'],
    scenarios: ['Prompt Injection', 'Data Leakage'],
    popularity: 'high',
    tags: ['Security', 'Vulnerabilities', 'Testing'],
  },
  {
    id: 'accessibility',
    name: 'Accessibility',
    description: 'Test for accessibility compliance',
    icon: AccessibilityNewIcon,
    color: 'warning.dark',
    behaviors: ['Accessibility', 'Compliance'],
    topics: ['Accessibility', 'WCAG', 'Inclusivity'],
    category: ['Accessibility', 'Legal'],
    scenarios: ['Screen Reader', 'Keyboard Navigation'],
    popularity: 'low',
    tags: ['Accessibility', 'WCAG', 'Inclusivity'],
  },
  {
    id: 'multilingual',
    name: 'Multilingual',
    description: 'Test language understanding',
    icon: LanguageIcon,
    color: 'secondary.main',
    behaviors: ['Reliability', 'Quality'],
    topics: ['Languages', 'Translation', 'Localization'],
    category: ['Localization', 'Quality'],
    scenarios: ['Translation Quality', 'Cultural Context'],
    popularity: 'medium',
    tags: ['Languages', 'Translation', 'Localization'],
  },
  {
    id: 'content-moderation',
    name: 'Content Moderation',
    description: 'Test content filtering and safety',
    icon: VerifiedUserIcon,
    color: 'info.dark',
    behaviors: ['Safety', 'Compliance'],
    topics: ['Content', 'Moderation', 'Safety'],
    category: ['Safety', 'Content'],
    scenarios: ['Harmful Content', 'Policy Violations'],
    popularity: 'medium',
    tags: ['Content', 'Moderation', 'Safety'],
  },
  {
    id: 'legal-compliance',
    name: 'Legal Compliance',
    description: 'Test legal and regulatory compliance',
    icon: GavelIcon,
    color: 'primary.dark',
    behaviors: ['Compliance', 'Legal'],
    topics: ['Legal', 'Regulations', 'Policies'],
    category: ['Legal', 'Compliance'],
    scenarios: ['Terms of Service', 'Copyright'],
    popularity: 'medium',
    tags: ['Legal', 'Compliance', 'Regulations'],
  },
  {
    id: 'privacy-protection',
    name: 'Privacy Protection',
    description: 'Test data privacy measures',
    icon: PrivacyTipIcon,
    color: 'info.main',
    behaviors: ['Privacy', 'Security'],
    topics: ['Privacy', 'Data Protection', 'Encryption'],
    category: ['Privacy', 'Security'],
    scenarios: ['Data Encryption', 'Access Controls'],
    popularity: 'high',
    tags: ['Privacy', 'Security', 'Data Protection'],
  },
];

/**
 * LandingScreen Component
 * Modal entry point for test generation with 3 options: AI, Manual, Template
 */
export default function LandingScreen({
  open,
  onClose,
  onSelectAI,
  onSelectManual,
  onSelectTemplate,
}: LandingScreenProps) {
  const [showAllTemplates, setShowAllTemplates] = useState(false);
  const visibleTemplates = showAllTemplates ? TEMPLATES : TEMPLATES.slice(0, 4);

  const handleSelectAI = () => {
    onSelectAI();
    // Keep modal open during navigation
  };

  const handleSelectManual = () => {
    onSelectManual();
    // Keep modal open during navigation
  };

  const handleSelectTemplate = (template: TestTemplate) => {
    onSelectTemplate(template);
    // Keep modal open during navigation
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: theme => theme.shape.borderRadius,
          maxHeight: '90vh',
        },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pb: 1,
        }}
      >
        Create Test Suite
        <IconButton edge="end" onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ pt: 3 }}>
        {/* Primary Action Cards */}
        <Grid container spacing={3} sx={{ mb: 6 }}>
          {/* AI Generation Card */}
          <Grid item xs={12} md={6}>
            <Card
              sx={{
                height: '100%',
                cursor: 'pointer',
              }}
              onClick={handleSelectAI}
            >
              <CardContent
                sx={{
                  p: 4,
                  textAlign: 'center',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                }}
              >
                <Box
                  sx={{
                    bgcolor: 'primary.lighter',
                    borderRadius: theme => theme.shape.circular,
                    width: 64,
                    height: 64,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mx: 'auto',
                  }}
                >
                  <AutoFixHighIcon
                    sx={{ fontSize: 32, color: 'primary.main' }}
                  />
                </Box>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Typography variant="h6" component="h3">
                    Generate Tests with AI
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Describe your testing needs and let AI create comprehensive
                    test cases
                  </Typography>
                </Box>
                <Button variant="contained" size="large" fullWidth>
                  Start Generation
                </Button>
              </CardContent>
            </Card>
          </Grid>

          {/* Manual Writing Card */}
          <Grid item xs={12} md={6}>
            <Card
              sx={{
                height: '100%',
                cursor: 'pointer',
              }}
              onClick={handleSelectManual}
            >
              <CardContent
                sx={{
                  p: 4,
                  textAlign: 'center',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                }}
              >
                <Box
                  sx={{
                    bgcolor: 'secondary.lighter',
                    borderRadius: theme => theme.shape.circular,
                    width: 64,
                    height: 64,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mx: 'auto',
                  }}
                >
                  <EditNoteIcon
                    sx={{ fontSize: 32, color: 'secondary.main' }}
                  />
                </Box>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Typography variant="h6" component="h3">
                    Write Tests Manually
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Create custom test cases with full control over every detail
                  </Typography>
                </Box>
                <Button variant="outlined" size="large" fullWidth>
                  Start Writing
                </Button>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Template Library Section */}
        <Box sx={{ mb: 4 }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              mb: 3,
            }}
          >
            <LibraryBooksIcon sx={{ fontSize: 32, color: 'primary.main' }} />
            <Box>
              <Typography variant="h6">Test Templates</Typography>
              <Typography variant="body2" color="text.secondary">
                Start with pre-configured templates for common testing scenarios
              </Typography>
            </Box>
          </Box>

          <Grid container spacing={3}>
            {visibleTemplates.map(template => {
              const IconComponent = template.icon;
              return (
                <Grid item xs={12} sm={6} md={3} key={template.id}>
                  <Card
                    sx={{
                      height: '100%',
                      cursor: 'pointer',
                    }}
                    onClick={() => handleSelectTemplate(template)}
                  >
                    <CardContent>
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          mb: 2,
                        }}
                      >
                        <Box
                          sx={{
                            width: 12,
                            height: 12,
                            borderRadius: theme => theme.shape.circular,
                            bgcolor: template.color,
                          }}
                        />
                        <IconComponent
                          sx={{ fontSize: 20, color: template.color }}
                        />
                      </Box>

                      <Typography variant="h6" gutterBottom>
                        {template.name}
                      </Typography>

                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{ mb: 2, minHeight: 40 }}
                      >
                        {template.description}
                      </Typography>

                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {template.tags
                          ?.slice(0, 2)
                          .map(tag => (
                            <Chip
                              key={tag}
                              label={tag}
                              size="small"
                              variant="outlined"
                            />
                          ))}
                        {template.popularity === 'high' && (
                          <Chip
                            label="Popular"
                            size="small"
                            color="primary"
                            variant="filled"
                          />
                        )}
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              );
            })}
          </Grid>

          {/* View More/Less Button */}
          <Box sx={{ textAlign: 'center', mt: 3 }}>
            <Button
              variant="text"
              onClick={() => setShowAllTemplates(!showAllTemplates)}
            >
              {showAllTemplates
                ? 'Show Less'
                : `View More (${TEMPLATES.length - 4} more templates)`}
            </Button>
          </Box>
        </Box>
      </DialogContent>
    </Dialog>
  );
}
