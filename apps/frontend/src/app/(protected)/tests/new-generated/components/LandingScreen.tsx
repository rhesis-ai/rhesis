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
import { TestTemplate } from './shared/types';
import { TEMPLATES } from '@/config/test-templates';

interface LandingScreenProps {
  open: boolean;
  onClose: () => void;
  onSelectAI: () => void;
  onSelectManual: () => void;
  onSelectTemplate: (template: TestTemplate) => void;
}

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
