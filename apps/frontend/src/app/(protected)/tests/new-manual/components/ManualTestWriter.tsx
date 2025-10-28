'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Card,
  CardContent,
  Autocomplete,
  createFilterOptions,
  Breadcrumbs,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Save as SaveIcon,
  Download as DownloadIcon,
  Upload as UploadIcon,
  ArrowBack as ArrowBackIcon,
  NavigateNext as NavigateNextIcon,
} from '@mui/icons-material';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { useNotifications } from '@/components/common/NotificationContext';
import ActionBar from '@/components/common/ActionBar';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Behavior } from '@/utils/api-client/interfaces/behavior';
import { Topic } from '@/utils/api-client/interfaces/topic';
import { Category } from '@/utils/api-client/interfaces/category';
import { TestBulkCreate } from '@/utils/api-client/interfaces/tests';

interface TestCase {
  id: string;
  prompt: string;
  category: string;
  topic: string;
  behavior: string;
  expectedOutput: string;
}

interface ManualTestWriterProps {
  onBack?: () => void;
}

const filter = createFilterOptions<string>();

export default function ManualTestWriter({ onBack }: ManualTestWriterProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const notifications = useNotifications();

  const [testCases, setTestCases] = useState<TestCase[]>([
    {
      id: '1',
      prompt: '',
      category: '',
      topic: '',
      behavior: '',
      expectedOutput: '',
    },
  ]);

  // API data
  const [behaviors, setBehaviors] = useState<Behavior[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);

  // Dialogs
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [testSetName, setTestSetName] = useState('');
  const [saving, setSaving] = useState(false);

  // Fetch data from API
  useEffect(() => {
    const fetchData = async () => {
      if (!session?.session_token) {
        notifications.show('No session token available', { severity: 'error' });
        return;
      }

      try {
        setLoading(true);
        const apiFactory = new ApiClientFactory(session.session_token);

        // Fetch behaviors
        const behaviorsClient = apiFactory.getBehaviorClient();
        const behaviorsData = await behaviorsClient.getBehaviors({
          sort_by: 'name',
          sort_order: 'asc',
        });
        setBehaviors(
          behaviorsData.filter(b => b.id && b.name && b.name.trim() !== '')
        );

        // Fetch topics with entity_type filter
        const topicsClient = apiFactory.getTopicClient();
        const topicsData = await topicsClient.getTopics({
          entity_type: 'Test',
          sort_by: 'name',
          sort_order: 'asc',
        });
        setTopics(topicsData);

        // Fetch categories
        const categoriesClient = apiFactory.getCategoryClient();
        const categoriesData = await categoriesClient.getCategories({
          entity_type: 'Test',
          sort_by: 'name',
          sort_order: 'asc',
        });
        setCategories(categoriesData);
      } catch (error) {
        notifications.show('Failed to load test dimensions', {
          severity: 'error',
        });
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [session, notifications]);

  const addNewRow = () => {
    const newTestCase: TestCase = {
      id: Date.now().toString(),
      prompt: '',
      category: '',
      topic: '',
      behavior: '',
      expectedOutput: '',
    };
    setTestCases([...testCases, newTestCase]);
  };

  const deleteRow = (id: string) => {
    if (testCases.length > 1) {
      setTestCases(testCases.filter(tc => tc.id !== id));
    }
  };

  const updateTestCase = (id: string, field: keyof TestCase, value: string) => {
    setTestCases(
      testCases.map(tc => (tc.id === id ? { ...tc, [field]: value } : tc))
    );
  };

  const handleSave = () => {
    // Filter out completely empty rows
    const nonEmptyTestCases = testCases.filter(
      tc =>
        tc.prompt.trim() ||
        tc.category.trim() ||
        tc.topic.trim() ||
        tc.behavior.trim() ||
        tc.expectedOutput.trim()
    );

    // Check if there are any test cases to save
    if (nonEmptyTestCases.length === 0) {
      notifications.show('Please add at least one test case', {
        severity: 'error',
      });
      return;
    }

    // Validate that all non-empty rows have required fields filled
    const hasIncompleteRows = nonEmptyTestCases.some(
      tc =>
        !tc.prompt.trim() ||
        !tc.category.trim() ||
        !tc.topic.trim() ||
        !tc.behavior.trim()
    );

    if (hasIncompleteRows) {
      notifications.show(
        'Please fill in all required fields (Prompt, Category, Topic, Behavior) for each test case',
        { severity: 'error' }
      );
      return;
    }

    setShowSaveDialog(true);
  };

  const handleConfirmSave = async () => {
    if (!session?.session_token) {
      notifications.show('No session token available', { severity: 'error' });
      return;
    }

    try {
      setSaving(true);
      const apiFactory = new ApiClientFactory(session.session_token);

      // Filter out completely empty rows
      const nonEmptyTestCases = testCases.filter(
        tc =>
          tc.prompt.trim() ||
          tc.category.trim() ||
          tc.topic.trim() ||
          tc.behavior.trim() ||
          tc.expectedOutput.trim()
      );

      if (nonEmptyTestCases.length === 0) {
        notifications.show('No test cases to save', { severity: 'error' });
        setSaving(false);
        return;
      }

      // First, create test set if name is provided
      let testSetId: string | undefined;
      if (testSetName.trim()) {
        const testSetsClient = apiFactory.getTestSetsClient();
        const newTestSet = await testSetsClient.createTestSet({
          name: testSetName.trim(),
        });
        testSetId = newTestSet.id;
      }

      // Prepare bulk test creation with only non-empty test cases
      const testsToCreate: TestBulkCreate[] = nonEmptyTestCases.map(tc => ({
        prompt: {
          content: tc.prompt,
          expected_response: tc.expectedOutput || undefined,
        },
        behavior: tc.behavior,
        category: tc.category,
        topic: tc.topic,
      }));

      const testsClient = apiFactory.getTestsClient();
      await testsClient.createTestsBulk({
        tests: testsToCreate,
        test_set_id: testSetId as any,
      });

      notifications.show(
        `Successfully created ${nonEmptyTestCases.length} test case${nonEmptyTestCases.length !== 1 ? 's' : ''}${testSetName.trim() ? ' and test set' : ''}`,
        { severity: 'success' }
      );

      setShowSaveDialog(false);
      setTestSetName('');

      // Navigate back to tests list
      router.push('/tests');
    } catch (error) {
      notifications.show(
        error instanceof Error ? error.message : 'Failed to save test cases',
        { severity: 'error' }
      );
    } finally {
      setSaving(false);
    }
  };

  const handleCancelSave = () => {
    setShowSaveDialog(false);
    setTestSetName('');
  };

  const handleExport = () => {
    const dataStr = JSON.stringify(testCases, null, 2);
    const dataUri =
      'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
    const exportFileDefaultName = `test-cases-${Date.now()}.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();

    notifications.show('Test cases exported successfully', {
      severity: 'success',
    });
  };

  const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/json';
    input.onchange = (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (event: ProgressEvent<FileReader>) => {
          try {
            const importedData = JSON.parse(event.target?.result as string);
            if (Array.isArray(importedData)) {
              setTestCases(importedData);
              notifications.show('Test cases imported successfully', {
                severity: 'success',
              });
            } else {
              notifications.show('Invalid file format', { severity: 'error' });
            }
          } catch (error) {
            notifications.show('Failed to parse file', { severity: 'error' });
          }
        };
        reader.readAsText(file);
      }
    };
    input.click();
  };

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      router.push('/tests');
    }
  };

  // Get unique option lists
  const behaviorOptions = behaviors.map(b => b.name);
  const topicOptions = topics.map(t => t.name);
  const categoryOptions = categories.map(c => c.name);

  return (
    <>
      {/* Main Content */}
      <Box sx={{ flexGrow: 1, p: 3, pb: 0 }}>
        {/* Breadcrumbs */}
        <Breadcrumbs
          separator={<NavigateNextIcon fontSize="small" />}
          aria-label="breadcrumb"
          sx={{ mb: 2 }}
        >
          <Link
            href="/tests"
            passHref
            style={{ textDecoration: 'none', color: 'inherit' }}
          >
            <Typography color="text.primary">Tests</Typography>
          </Link>
          <Typography color="text.primary">Manual Test Writer</Typography>
        </Breadcrumbs>

        {/* Page Title */}
        <Typography variant="h4" sx={{ mb: 3 }}>
          Manual Test Writer
        </Typography>

        {/* Test Cases Grid */}
        <Box>
          <Card>
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  mb: 2,
                }}
              >
                <Box>
                  <Typography variant="h6">
                    Test Cases ({testCases.length})
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    One test case per row
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    onClick={handleExport}
                    disabled={loading || testCases.length === 0}
                    size="small"
                  >
                    Export
                  </Button>
                </Box>
              </Box>

              <TableContainer component={Paper} variant="outlined">
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ width: 50 }}>#</TableCell>
                      <TableCell sx={{ minWidth: 300 }}>
                        Test Prompt *
                      </TableCell>
                      <TableCell sx={{ minWidth: 200 }}>Category *</TableCell>
                      <TableCell sx={{ minWidth: 200 }}>Topic *</TableCell>
                      <TableCell sx={{ minWidth: 200 }}>Behavior *</TableCell>
                      <TableCell sx={{ minWidth: 300 }}>
                        Expected Output
                      </TableCell>
                      <TableCell sx={{ width: 80 }}>Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {testCases.map((testCase, index) => (
                      <TableRow key={testCase.id}>
                        <TableCell sx={{ textAlign: 'center' }}>
                          <Typography variant="body2" color="text.secondary">
                            {index + 1}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ p: 1 }}>
                          <TextField
                            fullWidth
                            value={testCase.prompt}
                            onChange={e =>
                              updateTestCase(
                                testCase.id,
                                'prompt',
                                e.target.value
                              )
                            }
                            placeholder="Enter test prompt or scenario description..."
                            size="small"
                            disabled={loading}
                          />
                        </TableCell>
                        <TableCell sx={{ p: 1 }}>
                          <Autocomplete
                            freeSolo
                            options={categoryOptions}
                            value={testCase.category}
                            onChange={(_, newValue) => {
                              updateTestCase(
                                testCase.id,
                                'category',
                                newValue || ''
                              );
                            }}
                            onInputChange={(_, newInputValue) => {
                              updateTestCase(
                                testCase.id,
                                'category',
                                newInputValue
                              );
                            }}
                            filterOptions={(options, params) => {
                              const filtered = filter(options, params);
                              const { inputValue } = params;
                              const isExisting = options.some(
                                option => inputValue === option
                              );
                              if (inputValue !== '' && !isExisting) {
                                filtered.push(inputValue);
                              }
                              return filtered;
                            }}
                            renderInput={params => (
                              <TextField
                                {...params}
                                placeholder="Select or type new..."
                                size="small"
                              />
                            )}
                            disabled={loading}
                          />
                        </TableCell>
                        <TableCell sx={{ p: 1 }}>
                          <Autocomplete
                            freeSolo
                            options={topicOptions}
                            value={testCase.topic}
                            onChange={(_, newValue) => {
                              updateTestCase(
                                testCase.id,
                                'topic',
                                newValue || ''
                              );
                            }}
                            onInputChange={(_, newInputValue) => {
                              updateTestCase(
                                testCase.id,
                                'topic',
                                newInputValue
                              );
                            }}
                            filterOptions={(options, params) => {
                              const filtered = filter(options, params);
                              const { inputValue } = params;
                              const isExisting = options.some(
                                option => inputValue === option
                              );
                              if (inputValue !== '' && !isExisting) {
                                filtered.push(inputValue);
                              }
                              return filtered;
                            }}
                            renderInput={params => (
                              <TextField
                                {...params}
                                placeholder="Select or type new..."
                                size="small"
                              />
                            )}
                            disabled={loading}
                          />
                        </TableCell>
                        <TableCell sx={{ p: 1 }}>
                          <Autocomplete
                            freeSolo
                            options={behaviorOptions}
                            value={testCase.behavior}
                            onChange={(_, newValue) => {
                              updateTestCase(
                                testCase.id,
                                'behavior',
                                newValue || ''
                              );
                            }}
                            onInputChange={(_, newInputValue) => {
                              updateTestCase(
                                testCase.id,
                                'behavior',
                                newInputValue
                              );
                            }}
                            filterOptions={(options, params) => {
                              const filtered = filter(options, params);
                              const { inputValue } = params;
                              const isExisting = options.some(
                                option => inputValue === option
                              );
                              if (inputValue !== '' && !isExisting) {
                                filtered.push(inputValue);
                              }
                              return filtered;
                            }}
                            renderInput={params => (
                              <TextField
                                {...params}
                                placeholder="Select or type new..."
                                size="small"
                              />
                            )}
                            disabled={loading}
                          />
                        </TableCell>
                        <TableCell sx={{ p: 1 }}>
                          <TextField
                            fullWidth
                            value={testCase.expectedOutput}
                            onChange={e =>
                              updateTestCase(
                                testCase.id,
                                'expectedOutput',
                                e.target.value
                              )
                            }
                            placeholder="Describe expected output or behavior..."
                            size="small"
                            disabled={loading}
                          />
                        </TableCell>
                        <TableCell>
                          <IconButton
                            onClick={() => deleteRow(testCase.id)}
                            disabled={testCases.length === 1 || loading}
                            color="error"
                            size="small"
                          >
                            <DeleteIcon />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>

              <Box
                sx={{
                  mt: 2,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <Button
                  variant="outlined"
                  startIcon={<AddIcon />}
                  onClick={addNewRow}
                  disabled={loading}
                >
                  Add Another Test Case
                </Button>
                <Typography variant="body2" color="text.secondary">
                  Total: {testCases.length} test case
                  {testCases.length !== 1 ? 's' : ''}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>

      {/* Bottom Action Bar */}
      <ActionBar
        leftButton={{
          label: 'Back to Tests',
          onClick: handleBack,
          variant: 'text',
          startIcon: <ArrowBackIcon />,
        }}
        rightButton={{
          label: 'Save',
          onClick: handleSave,
          variant: 'contained',
          startIcon: <SaveIcon />,
          disabled: loading || testCases.length === 0,
        }}
      />

      {/* Save Test Set Dialog */}
      <Dialog
        open={showSaveDialog}
        onClose={handleCancelSave}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Save Test Cases</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              label="Test Set Name (Optional)"
              placeholder="Leave empty to save tests without a set"
              value={testSetName}
              onChange={e => setTestSetName(e.target.value)}
              helperText="If provided, tests will be grouped into a reusable test set"
              disabled={saving}
            />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            variant="outlined"
            onClick={handleCancelSave}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            startIcon={<SaveIcon />}
            onClick={handleConfirmSave}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
