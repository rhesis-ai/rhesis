'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Button,
  Chip,
} from '@mui/material';
import { Grid } from '@mui/material';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import EditNoteIcon from '@mui/icons-material/EditNote';
import { TestTemplate, TestType } from './shared/types';
import { TEMPLATES } from '@/config/test-templates';
import SelectionModal, { SelectionCardConfig } from './shared/SelectionModal';
import { useOnboarding } from '@/contexts/OnboardingContext';

interface SelectTestCreationMethodProps {
  open: boolean;
  onClose: () => void;
  onBack?: () => void;
  onSelectAI: () => void;
  onSelectManual: () => void;
  onSelectTemplate: (template: TestTemplate) => void;
  testType?: TestType;
}

/**
 * SelectTestCreationMethod Component
 * Modal entry point for test generation with 3 options: AI, Manual, Template
 */
export default function SelectTestCreationMethod({
  open,
  onClose,
  onBack,
  onSelectAI,
  onSelectManual,
  onSelectTemplate,
  testType = 'single_turn',
}: SelectTestCreationMethodProps) {
  const [showAllTemplates, setShowAllTemplates] = useState(false);
  const visibleTemplates = showAllTemplates ? TEMPLATES : TEMPLATES.slice(0, 4);
  const { markStepComplete } = useOnboarding();

  // Mark onboarding step complete when the modal opens
  useEffect(() => {
    if (open) {
      markStepComplete('testCasesCreated');
    }
  }, [open, markStepComplete]);

  const testTypeLabel =
    testType === 'single_turn' ? 'Single-Turn' : 'Multi-Turn';

  const cards: SelectionCardConfig[] = [
    {
      id: 'ai-generation',
      title: `Generate Tests with AI`,
      description: `Describe your testing needs and let AI create comprehensive ${testTypeLabel.toLowerCase()} test cases.`,
      icon: <AutoFixHighIcon sx={{ fontSize: 64 }} />,
      iconBgColor: 'secondary.lighter',
      iconColor: 'secondary.main',
      buttonLabel: 'Start Generation',
      buttonVariant: 'contained',
      onClick: onSelectAI,
    },
    {
      id: 'manual-writing',
      title: `Write Tests Manually`,
      description: `Create custom ${testTypeLabel.toLowerCase()} test cases with full control over every detail.`,
      icon: <EditNoteIcon sx={{ fontSize: 64 }} />,
      iconBgColor: 'primary.lighter',
      iconColor: 'primary.main',
      buttonLabel: 'Start Writing',
      buttonVariant: 'outlined',
      buttonColor: 'primary',
      onClick: onSelectManual,
    },
  ];

  // Template Library Section
  const templatesContent = (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6">Templates</Typography>
        <Typography variant="body2" color="text.secondary">
          Start with pre-configured templates for common testing scenarios
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {visibleTemplates.map((template, index) => {
          const IconComponent = template.icon;
          // Show "Popular" chip only for the first 3 templates
          const isPopular = index < 3;

          return (
            <Grid size={{ xs: 12, sm: 6, md: 3 }} key={template.id}>
              <Card
                sx={{
                  height: '100%',
                  cursor: 'pointer',
                }}
                onClick={() => onSelectTemplate(template)}
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
                    {isPopular && (
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
  );

  return (
    <SelectionModal
      open={open}
      onClose={onClose}
      onBack={onBack}
      title={`Create ${testTypeLabel} Test Suite`}
      subtitle={`Choose how you want to create your ${testTypeLabel.toLowerCase()} test suite`}
      cards={cards}
      maxWidth="lg"
      additionalContent={templatesContent}
    />
  );
}
