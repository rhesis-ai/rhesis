import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  Typography,
  Chip,
  DialogActions,
  Button,
  CircularProgress,
  IconButton,
  TextField,
} from '@mui/material';
import BaseTable from '@/components/common/BaseTable';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import { Test } from '../types/test';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import regenerateTestTemplate from '../templates/regenerate_test.md';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useRouter } from 'next/navigation';

interface TestsDialogProps {
  open: boolean;
  onClose: () => void;
  tests: Test[];
  setTests: (tests: Test[]) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  prompt: string;
  sessionToken: string;
}

interface TestFeedback {
  [key: number]: {
    type: 'approved' | 'rejected' | undefined;
    reason?: string;
  };
}

export default function TestsDialog({ open, onClose, tests, setTests, isLoading, setIsLoading, prompt, sessionToken }: TestsDialogProps) {
  const router = useRouter();
  const [feedback, setFeedback] = React.useState<TestFeedback>({});
  const [expandedRow, setExpandedRow] = React.useState<number | null>(null);
  const [loadingTests, setLoadingTests] = React.useState<number[]>([]);
  const [isGeneratingTestSet, setisGeneratingTestSet] = React.useState(false);

  const handleFeedback = (index: number, type: 'approved' | 'rejected' | undefined) => {
    if (feedback[index]?.type === type) {
      // Clicking the same button again - clear feedback
      setFeedback(prev => ({
        ...prev,
        [index]: {
          type: undefined,
          reason: undefined
        }
      }));
      setExpandedRow(null);
    } else {
      // New feedback or changing feedback type
      setFeedback(prev => ({
        ...prev,
        [index]: {
          ...prev[index],
          type: type
        }
      }));
      
      if (type === 'rejected') {
        setExpandedRow(index);
      } else {
        setExpandedRow(null);
      }
    }
  };

  const handleReasonChange = (index: number, reason: string) => {
    setFeedback(prev => ({
      ...prev,
      [index]: {
        ...prev[index],
        reason
      }
    }));
  };

  const handleSaveFeedback = (index: number) => {
    setExpandedRow(null);
  };

  const handleCancelFeedback = (index: number) => {
    setExpandedRow(null);
  };

  const columns = [
    {
      id: 'prompt',
      label: 'Test Prompt',
      render: (row: Test, index: number) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {loadingTests.includes(index) ? (
            <CircularProgress size={20} />
          ) : (
            <Typography variant="body2">{row.prompt}</Typography>
          )}
        </Box>
      ),
    },
    {
      id: 'behavior',
      label: 'Behavior',
      render: (row: Test) => (
        <Chip
          label={row.behavior}
          size="small"
          color={
            row.behavior === 'Reliability' ? 'success' :
            row.behavior === 'Compliance' ? 'warning' : 'error'
          }
        />
      ),
    },
    {
      id: 'category',
      label: 'Category',
      render: (row: Test) => (
        <Chip
          label={row.category}
          size="small"
          variant="outlined"
          color={
            row.category === 'Harmless' ? 'success' :
            row.category === 'Toxic' ? 'warning' :
            'error'
          }
        />
      ),
    },
    {
      id: 'feedback',
      label: 'Feedback',
      render: (row: Test, index: number) => (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <IconButton 
              onClick={() => handleFeedback(index, feedback[index]?.type === 'approved' ? undefined : 'approved')}
              color={feedback[index]?.type === 'approved' ? 'success' : 'default'}
            >
              {feedback[index]?.type === 'approved' ? (
                <CheckCircleIcon fontSize="medium" />
              ) : (
                <CheckCircleOutlineIcon fontSize="medium" />
              )}
            </IconButton>
            <IconButton 
              onClick={() => handleFeedback(index, feedback[index]?.type === 'rejected' ? undefined : 'rejected')}
              color={feedback[index]?.type === 'rejected' ? 'error' : 'default'}
            >
              {feedback[index]?.type === 'rejected' ? (
                <CancelIcon fontSize="medium" />
              ) : (
                <CancelOutlinedIcon fontSize="medium" />
              )}
            </IconButton>
          </Box>
        </Box>
      ),
    },
  ];

  const handleRegenerateTests = async () => {
    const rejectedTests = tests.map((test, index) => ({
      ...test,
      index,
      feedback: feedback[index]
    })).filter(test => test.feedback?.type === 'rejected');

    // Set loading state for rejected tests
    setLoadingTests(rejectedTests.map(test => test.index));

    try {
      const client = new ApiClientFactory(sessionToken).getServicesClient();
      
      // Process each rejected test in parallel
      const regeneratedTests = await Promise.all(rejectedTests.map(async (test) => {
        const template = regenerateTestTemplate
          .replace('{generation_prompt}', prompt)
          .replace('{prompt}', test.prompt)
          .replace('{behavior}', test.behavior)
          .replace('{category}', test.category)
          .replace('{test_feedback}', test.feedback?.reason || '');

        const response = await client.getOpenAIJson(template);
        return {
          index: test.index,
          newTest: response as Test
        };
      }));

      // Update tests array with regenerated tests
      const updatedTests = [...tests];
      regeneratedTests.forEach(({ index, newTest }) => {
        updatedTests[index] = newTest;
      });

      // Clear feedback for regenerated tests
      const updatedFeedback = { ...feedback };
      rejectedTests.forEach(test => {
        delete updatedFeedback[test.index];
      });

      setTests(updatedTests);
      setFeedback(updatedFeedback);
    } catch (error) {
      console.error('Error regenerating tests:', error);
    } finally {
      setLoadingTests([]);
    }
  };

  const handleGenerateTestSet = async () => {
    setisGeneratingTestSet(true);
    // Simulate API call with 3 second delay
    await new Promise(resolve => setTimeout(resolve, 3000));
    router.push('/test-sets/bf5bde9b-5b1a-402c-ab02-efcd197cfb93');
    setisGeneratingTestSet(false);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">Generated Tests</Typography>
          <Button
            variant="contained"
            color="primary"
            startIcon={isGeneratingTestSet ? <CircularProgress size={20} color="inherit" /> : <AutoFixHighIcon />}
            onClick={handleGenerateTestSet}
            disabled={
              isGeneratingTestSet ||
              tests.length === 0 || 
              tests.length !== Object.values(feedback).filter(f => f?.type === 'approved').length
            }
          >
            {isGeneratingTestSet ? 'Generating test set...' : 'Generate Test Set'}
          </Button>
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" color="primary" gutterBottom>
            Generation Prompt
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {prompt}
          </Typography>
        </Box>
        
        {isLoading ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', p: 3, gap: 2 }}>
            <CircularProgress />
            <Typography variant="body2" color="text.secondary">
              Generating tests...
            </Typography>
          </Box>
        ) : (
          <BaseTable
            columns={columns}
            data={tests}
            rowHighlight={
              Object.entries(feedback).reduce((acc, [index, value]) => ({
                ...acc,
                [Number(index)]: {
                  color: value.type === 'approved' ? '#2e7d32' : 
                         value.type === 'rejected' ? '#d32f2f' : 
                         'transparent'
                }
              }), {})
            }
            expandedRow={expandedRow}
            renderExpanded={(row, index) => (
              <Box sx={{ px: 2 }}>
                <Box sx={{ 
                  display: 'flex', 
                  gap: 2,
                  alignItems: 'center'
                }}>
                  <TextField
                    fullWidth
                    size="small"
                    placeholder="Provide feedback reason..."
                    value={feedback[index]?.reason || ''}
                    onChange={(e) => handleReasonChange(index, e.target.value)}
                  />
                  <Button 
                    size="small" 
                    onClick={() => handleCancelFeedback(index)}
                  >
                    Cancel
                  </Button>
                  <Button 
                    size="small" 
                    variant="contained" 
                    onClick={() => handleSaveFeedback(index)}
                    disabled={!feedback[index]?.reason}
                  >
                    Save
                  </Button>
                </Box>
              </Box>
            )}
          />
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        <Button 
          color="primary"
          disabled={isLoading || !Object.values(feedback).some(f => f?.type === 'rejected')}
          onClick={handleRegenerateTests}
        >
          Regenerate
        </Button>
      </DialogActions>
    </Dialog>
  );
} 