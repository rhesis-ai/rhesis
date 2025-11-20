'use client';

import React from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
} from '@mui/material';
import ChatIcon from '@mui/icons-material/Chat';
import ForumIcon from '@mui/icons-material/Forum';
import CloseIcon from '@mui/icons-material/Close';
import { TestType } from './shared/types';

interface TestTypeSelectionScreenProps {
  open: boolean;
  onClose: () => void;
  onSelectTestType: (testType: TestType) => void;
}

/**
 * TestTypeSelectionScreen Component
 * Modal to choose between single-turn and multi-turn tests
 */
export default function TestTypeSelectionScreen({
  open,
  onClose,
  onSelectTestType,
}: TestTypeSelectionScreenProps) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
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
        <Box>
          <Typography variant="h6">Choose Test Type</Typography>
          <Typography variant="body2" color="text.secondary">
            Select the type of tests you want to generate for your project
          </Typography>
        </Box>
        <IconButton edge="end" onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ pt: 4, px: 3, pb: 4 }}>
        {/* Test Type Cards */}
        <Grid container spacing={3}>
          {/* Single-Turn Tests Card */}
          <Grid item xs={12} md={6}>
            <Card
              sx={{
                height: '100%',
                cursor: 'pointer',
                transition: 'all 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 4,
                },
              }}
              onClick={() => onSelectTestType('single_turn')}
            >
              <CardContent
                sx={{
                  p: 4,
                  textAlign: 'center',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                  height: '100%',
                }}
              >
                <Box
                  sx={{
                    bgcolor: 'primary.lighter',
                    borderRadius: theme => theme.shape.circular,
                    width: 80,
                    height: 80,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mx: 'auto',
                  }}
                >
                  <ChatIcon sx={{ fontSize: 48, color: 'primary.main' }} />
                </Box>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Typography variant="h5" component="h3" fontWeight="bold">
                    Single-Turn Tests
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Test individual prompts and responses. Best for evaluating
                    specific behaviors, accuracy, and compliance in standalone
                    interactions.
                  </Typography>
                </Box>
                <Box
                  sx={{
                    mt: 'auto',
                    pt: 2,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 1,
                  }}
                >
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ fontWeight: 'medium' }}
                  >
                    Examples:
                  </Typography>
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 0.5,
                      textAlign: 'left',
                    }}
                  >
                    <Typography variant="caption" color="text.secondary">
                      • Factual accuracy checks
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      • Policy compliance validation
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      • Safety and bias testing
                    </Typography>
                  </Box>
                </Box>
                <Button
                  variant="contained"
                  size="large"
                  fullWidth
                  sx={{ mt: 2 }}
                >
                  Select Single-Turn
                </Button>
              </CardContent>
            </Card>
          </Grid>

          {/* Multi-Turn Tests Card */}
          <Grid item xs={12} md={6}>
            <Card
              sx={{
                height: '100%',
                cursor: 'pointer',
                transition: 'all 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 4,
                },
              }}
              onClick={() => onSelectTestType('multi_turn')}
            >
              <CardContent
                sx={{
                  p: 4,
                  textAlign: 'center',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                  height: '100%',
                }}
              >
                <Box
                  sx={{
                    bgcolor: 'secondary.lighter',
                    borderRadius: theme => theme.shape.circular,
                    width: 80,
                    height: 80,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mx: 'auto',
                  }}
                >
                  <ForumIcon sx={{ fontSize: 48, color: 'secondary.main' }} />
                </Box>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Typography variant="h5" component="h3" fontWeight="bold">
                    Multi-Turn Tests
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Test conversational scenarios with goals and constraints.
                    Best for evaluating agent behavior across multiple
                    interactions and complex workflows.
                  </Typography>
                </Box>
                <Box
                  sx={{
                    mt: 'auto',
                    pt: 2,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 1,
                  }}
                >
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ fontWeight: 'medium' }}
                  >
                    Examples:
                  </Typography>
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 0.5,
                      textAlign: 'left',
                    }}
                  >
                    <Typography variant="caption" color="text.secondary">
                      • Customer support flows
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      • Complex task completion
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      • Goal-oriented conversations
                    </Typography>
                  </Box>
                </Box>
                <Button
                  variant="outlined"
                  size="large"
                  fullWidth
                  sx={{ mt: 2 }}
                >
                  Select Multi-Turn
                </Button>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </DialogContent>
    </Dialog>
  );
}
