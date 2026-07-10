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
  Autocomplete,
  createFilterOptions,
  Badge,
  Tooltip,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import { drawerOutlinedFieldSx } from '@/components/common/drawerFormFieldSx';
import {
  Delete as DeleteIcon,
  Save as SaveIcon,
  Download as DownloadIcon,
  AttachFile as AttachFileIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabAddIcon, FabGroup } from '@/components/common/Fab';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme-constants';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Behavior } from '@/utils/api-client/interfaces/behavior';
import { Topic } from '@/utils/api-client/interfaces/topic';
import { Category } from '@/utils/api-client/interfaces/category';
import {
  TestBulkCreate,
  TestCreate,
  TestPromptCreate,
} from '@/utils/api-client/interfaces/tests';
import { UUID } from 'crypto';
import { MultiTurnTestConfig } from '@/utils/api-client/interfaces/multi-turn-test-config';
import { TEST_TYPES, TYPE_NAMES, normalizeTestType } from '@/constants/test-types';
import MultiFileUpload from '@/components/common/MultiFileUpload';
import { EntityType } from '@/types/entity-type';
import { useTypeLookups } from '@/hooks/useLookups';

type TestType = 'Single-Turn' | 'Multi-Turn';

interface SingleTurnTestCase {
  id: string;
  testType: 'Single-Turn';
  prompt: string;
  category: string;
  topic: string;
  behavior: string;
  expectedOutput: string;
}

interface MultiTurnTestCase {
  id: string;
  testType: 'Multi-Turn';
  goal: string;
  instructions: string;
  restrictions: string;
  scenario: string;
  minTurns: number;
  maxTurns: number;
  category: string;
  topic: string;
  behavior: string;
}

type TestCase = SingleTurnTestCase | MultiTurnTestCase;

const filter = createFilterOptions<string>();

export default function ManualTestWriter() {
  const router = useRouter();
  const { data: session } = useSession();
  const notifications = useNotifications();

  const [testType, setTestType] = useState<TestType>(() => {
    if (typeof window !== 'undefined') {
      const storedType = sessionStorage.getItem('testType');
      return normalizeTestType(storedType) as TestType;
    }
    return 'Single-Turn';
  });

  const handleTestTypeChange = (newType: TestType) => {
    if (newType === testType) return;
    setTestType(newType);
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('testType', newType);
    }
    const initialCase: TestCase =
      newType === 'Single-Turn'
        ? {
            id: '1',
            testType: 'Single-Turn',
            prompt: '',
            category: '',
            topic: '',
            behavior: '',
            expectedOutput: '',
          }
        : {
            id: '1',
            testType: 'Multi-Turn',
            goal: '',
            instructions: '',
            restrictions: '',
            scenario: '',
            minTurns: 1,
            maxTurns: 10,
            category: '',
            topic: '',
            behavior: '',
          };
    setTestCases([initialCase]);
    setPendingFilesMap({});
  };

  const [testCases, setTestCases] = useState<TestCase[]>(() => {
    const initialTestCase: TestCase =
      testType === 'Single-Turn'
        ? {
            id: '1',
            testType: 'Single-Turn',
            prompt: '',
            category: '',
            topic: '',
            behavior: '',
            expectedOutput: '',
          }
        : {
            id: '1',
            testType: 'Multi-Turn',
            goal: '',
            instructions: '',
            restrictions: '',
            scenario: '',
            minTurns: 1,
            maxTurns: 10,
            category: '',
            topic: '',
            behavior: '',
          };
    return [initialTestCase];
  });

  // API data
  const [behaviors, setBehaviors] = useState<Behavior[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);

  // File attachments per row
  const [pendingFilesMap, setPendingFilesMap] = useState<
    Record<string, File[]>
  >({});
  const [attachDialogRowId, setAttachDialogRowId] = useState<string | null>(
    null
  );

  // Test set type ID resolved from testType
  const [testSetTypeId, setTestSetTypeId] = useState<UUID | undefined>();
  const testTypeValue =
    testType === 'Single-Turn' ? TEST_TYPES.SINGLE_TURN : TEST_TYPES.MULTI_TURN;
  const { data: resolvedTestSetTypes } = useTypeLookups(
    session?.session_token ?? '',
    `type_name eq '${TYPE_NAMES.TEST_SET_TYPE}' and type_value eq '${testTypeValue}'`,
    !!session?.session_token
  );
  useEffect(() => {
    if (resolvedTestSetTypes && resolvedTestSetTypes.length > 0) {
      setTestSetTypeId(resolvedTestSetTypes[0].id as UUID);
    }
  }, [resolvedTestSetTypes]);

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
          entity_type: EntityType.TEST,
          sort_by: 'name',
          sort_order: 'asc',
        });
        setTopics(topicsData);

        // Fetch categories
        const categoriesClient = apiFactory.getCategoryClient();
        const categoriesData = await categoriesClient.getCategories({
          entity_type: EntityType.TEST,
          sort_by: 'name',
          sort_order: 'asc',
        });
        setCategories(categoriesData);
      } catch (_error) {
        notifications.show('Failed to load test dimensions', {
          severity: 'error',
        });
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [session, notifications, testType]);

  const addNewRow = () => {
    const newTestCase: TestCase =
      testType === 'Single-Turn'
        ? {
            id: Date.now().toString(),
            testType: 'Single-Turn',
            prompt: '',
            category: '',
            topic: '',
            behavior: '',
            expectedOutput: '',
          }
        : {
            id: Date.now().toString(),
            testType: 'Multi-Turn',
            goal: '',
            instructions: '',
            restrictions: '',
            scenario: '',
            minTurns: 1,
            maxTurns: 10,
            category: '',
            topic: '',
            behavior: '',
          };
    setTestCases([...testCases, newTestCase]);
  };

  const deleteRow = (id: string) => {
    if (testCases.length > 1) {
      setTestCases(testCases.filter(tc => tc.id !== id));
      setPendingFilesMap(prev => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }
  };

  const updateTestCase = (
    id: string,
    field: string,
    value: string | number | undefined
  ) => {
    setTestCases(
      testCases.map(tc => (tc.id === id ? { ...tc, [field]: value } : tc))
    );
  };

  const handleSave = () => {
    // Filter out completely empty rows
    const nonEmptyTestCases = testCases.filter(tc => {
      if (tc.testType === 'Single-Turn') {
        return (
          tc.prompt.trim() ||
          tc.category.trim() ||
          tc.topic.trim() ||
          tc.behavior.trim() ||
          tc.expectedOutput.trim()
        );
      } else {
        return (
          tc.goal.trim() ||
          tc.category.trim() ||
          tc.topic.trim() ||
          tc.behavior.trim() ||
          tc.instructions.trim() ||
          tc.restrictions.trim() ||
          tc.scenario.trim()
        );
      }
    });

    // Check if there are any test cases to save
    if (nonEmptyTestCases.length === 0) {
      notifications.show('Please add at least one test case', {
        severity: 'error',
      });
      return;
    }

    // Validate that all non-empty rows have required fields filled
    const hasIncompleteRows = nonEmptyTestCases.some(tc => {
      if (tc.testType === 'Single-Turn') {
        return (
          !tc.prompt.trim() ||
          !tc.category.trim() ||
          !tc.topic.trim() ||
          !tc.behavior.trim()
        );
      } else {
        return (
          !tc.goal.trim() ||
          !tc.category.trim() ||
          !tc.topic.trim() ||
          !tc.behavior.trim()
        );
      }
    });

    if (hasIncompleteRows) {
      const requiredFields =
        testType === 'Single-Turn'
          ? 'Prompt, Category, Topic, Behavior'
          : 'Goal, Category, Topic, Behavior';
      notifications.show(
        `Please fill in all required fields (${requiredFields}) for each test case`,
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
      const nonEmptyTestCases = testCases.filter(tc => {
        if (tc.testType === 'Single-Turn') {
          return (
            tc.prompt.trim() ||
            tc.category.trim() ||
            tc.topic.trim() ||
            tc.behavior.trim() ||
            tc.expectedOutput.trim()
          );
        } else {
          return (
            tc.goal.trim() ||
            tc.category.trim() ||
            tc.topic.trim() ||
            tc.behavior.trim() ||
            tc.instructions.trim() ||
            tc.restrictions.trim() ||
            tc.scenario.trim()
          );
        }
      });

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
          test_set_type_id: testSetTypeId,
        });
        testSetId = newTestSet.id;
      }

      const hasAnyFiles = nonEmptyTestCases.some(
        tc => (pendingFilesMap[tc.id]?.length ?? 0) > 0
      );

      const testsClient = apiFactory.getTestsClient();

      if (hasAnyFiles) {
        // Create tests individually to get IDs for file uploads
        const filesClient = apiFactory.getFilesClient();
        let uploadFailures = 0;
        const createdTestIds: string[] = [];

        for (const tc of nonEmptyTestCases) {
          const payload = buildTestPayload(tc);
          const created = await testsClient.createTest(payload);
          createdTestIds.push(created.id);

          const rowFiles = pendingFilesMap[tc.id];
          if (rowFiles?.length) {
            try {
              await filesClient.uploadFiles(rowFiles, created.id, 'Test');
            } catch {
              uploadFailures++;
            }
          }
        }

        // Associate created tests with the test set
        if (testSetId && createdTestIds.length > 0) {
          const testSetsClient = apiFactory.getTestSetsClient();
          await testSetsClient.associateTestsWithTestSet(
            testSetId,
            createdTestIds
          );
        }

        const msg =
          `Successfully created ${nonEmptyTestCases.length} test case${nonEmptyTestCases.length !== 1 ? 's' : ''}` +
          (testSetName.trim() ? ' and test set' : '') +
          (uploadFailures > 0
            ? ` (${uploadFailures} file upload${uploadFailures !== 1 ? 's' : ''} failed)`
            : '');
        notifications.show(msg, {
          severity: uploadFailures > 0 ? 'warning' : 'success',
        });
      } else {
        // No files — use efficient bulk creation
        const testsToCreate: TestBulkCreate[] = nonEmptyTestCases.map(tc =>
          buildBulkPayload(tc)
        );

        await testsClient.createTestsBulk({
          tests: testsToCreate,
          test_set_id: testSetId as UUID,
        });

        notifications.show(
          `Successfully created ${nonEmptyTestCases.length} test case${nonEmptyTestCases.length !== 1 ? 's' : ''}${testSetName.trim() ? ' and test set' : ''}`,
          { severity: 'success' }
        );
      }

      setShowSaveDialog(false);
      setTestSetName('');
      setPendingFilesMap({});

      // Clear sessionStorage
      if (typeof window !== 'undefined') {
        sessionStorage.removeItem('testType');
      }

      // Navigate to test set detail page if created, otherwise tests list
      if (testSetId) {
        router.push(`/test-sets/${testSetId}`);
      } else {
        router.push('/tests');
      }
    } catch (error) {
      notifications.show(
        error instanceof Error ? error.message : 'Failed to save test cases',
        { severity: 'error' }
      );
    } finally {
      setSaving(false);
    }
  };

  /** Build payload for single createTest (returns ID for file upload). */
  const buildTestPayload = (tc: TestCase): TestCreate => {
    if (tc.testType === 'Single-Turn') {
      const prompt: TestPromptCreate = {
        content: tc.prompt,
        expected_response: tc.expectedOutput || undefined,
      };
      return {
        prompt,
        behavior: tc.behavior,
        category: tc.category,
        topic: tc.topic,
      };
    }
    const config: MultiTurnTestConfig = {
      goal: tc.goal,
      instructions: tc.instructions || undefined,
      restrictions: tc.restrictions || undefined,
      scenario: tc.scenario || undefined,
      min_turns: tc.minTurns,
      max_turns: tc.maxTurns,
    };
    return {
      behavior: tc.behavior,
      category: tc.category,
      topic: tc.topic,
      test_configuration: config as unknown as Record<string, unknown>,
    };
  };

  /** Build payload for bulk createTestsBulk (no file support). */
  const buildBulkPayload = (tc: TestCase): TestBulkCreate => {
    if (tc.testType === 'Single-Turn') {
      return {
        prompt: {
          content: tc.prompt,
          expected_response: tc.expectedOutput || undefined,
        },
        behavior: tc.behavior,
        category: tc.category,
        topic: tc.topic,
      };
    }
    const config: MultiTurnTestConfig = {
      goal: tc.goal,
      instructions: tc.instructions || undefined,
      restrictions: tc.restrictions || undefined,
      scenario: tc.scenario || undefined,
      min_turns: tc.minTurns,
      max_turns: tc.maxTurns,
    };
    return {
      behavior: tc.behavior,
      category: tc.category,
      topic: tc.topic,
      test_configuration: config as unknown as Record<string, unknown>,
    };
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

  const _handleImport = () => {
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
          } catch (_error) {
            notifications.show('Failed to parse file', { severity: 'error' });
          }
        };
        reader.readAsText(file);
      }
    };
    input.click();
  };

  // Get unique option lists
  const behaviorOptions = behaviors.map(b => b.name);
  const topicOptions = topics.map(t => t.name);
  const categoryOptions = categories.map(c => c.name);

  return (
    <>
      <PageLayout
        title="Manual Test Writer"
        description="Create test cases manually. One test case per row."
        breadcrumbs={[
          { label: 'Tests', href: '/tests' },
          { label: 'Manual Test Writer' },
        ]}
        actions={
          <FabGroup>
            <Fab
              icon={<DownloadIcon />}
              tooltip="Export test cases"
              onClick={handleExport}
              disabled={loading || testCases.length === 0}
            />
            <Fab
              icon={<FabAddIcon />}
              tooltip="Add test case"
              onClick={addNewRow}
              disabled={loading}
            />
            <Fab
              icon={<SaveIcon />}
              tooltip="Save"
              onClick={handleSave}
              disabled={loading || testCases.length === 0}
            />
          </FabGroup>
        }
      >
        <Box sx={{ mt: 2, mb: 2 }}>
          <Paper
            sx={{
              width: '100%',
              borderRadius: BORDER_RADIUS.md,
              boxShadow: ELEVATION.xs,
              border: theme => `1px solid ${theme.palette.greyscale.border}`,
              overflow: 'hidden',
            }}
          >
            {/* Card toolbar — test type toggle, matching BaseDataGrid toolbar layout */}
            <Box
              sx={{
                px: '30px',
                py: '16px',
                display: 'flex',
                alignItems: 'center',
                borderBottom: theme =>
                  `1px solid ${theme.palette.greyscale.border}`,
              }}
            >
              <ToggleButtonGroup
                value={testType}
                exclusive
                onChange={(_, val) => {
                  if (val) handleTestTypeChange(val as TestType);
                }}
                size="small"
              >
                <ToggleButton value="Single-Turn">Single-Turn</ToggleButton>
                <ToggleButton value="Multi-Turn">Multi-Turn</ToggleButton>
              </ToggleButtonGroup>
            </Box>
            <TableContainer
              sx={{
                overflowX: 'auto',
                // ── Header ───────────────────────────────────────────────
                '& .MuiTableHead-root .MuiTableCell-root': {
                  fontWeight: 700,
                  bgcolor: 'background.paper',
                  borderBottom: theme =>
                    `1px solid ${theme.palette.greyscale.border}`,
                  color: 'text.primary',
                  fontSize: theme => theme.typography.body2.fontSize,
                  py: '12px',
                  // first/last column inset matching BaseDataGrid (30px)
                  '&:first-of-type': { pl: '30px' },
                  '&:last-of-type': { pr: '30px' },
                },
                // ── Body cells ───────────────────────────────────────────
                '& .MuiTableBody-root .MuiTableCell-root': {
                  borderBottom: theme =>
                    `1px solid ${theme.palette.greyscale.border}`,
                  // first-of-type gets 30px left inset matching BaseDataGrid
                  '&:first-of-type': { pl: '30px' },
                },
                '& .MuiTableBody-root .MuiTableRow-root:last-child .MuiTableCell-root':
                  { borderBottom: 'none' },
                // ── Row hover ────────────────────────────────────────────
                '& .MuiTableBody-root .MuiTableRow-root': {
                  transition: 'background-color 0.1s ease',
                },
                '& .MuiTableBody-root .MuiTableRow-root:hover': {
                  bgcolor: theme =>
                    theme.palette.mode === 'light'
                      ? theme.palette.greyscale.surface1
                      : 'rgba(255,255,255,0.04)',
                },
                // ── Input fields: invisible border until hover/focus ──────
                // This makes the table look like a read-only grid; borders
                // only appear when the user interacts with a cell.
                '& .MuiOutlinedInput-notchedOutline': {
                  borderColor: 'transparent',
                  transition: 'border-color 0.15s ease',
                },
                '& .MuiOutlinedInput-root:hover .MuiOutlinedInput-notchedOutline':
                  {
                    borderColor: theme => theme.palette.greyscale.border,
                  },
                '& .MuiOutlinedInput-root.Mui-focused .MuiOutlinedInput-notchedOutline':
                  {
                    borderColor: 'primary.main',
                    borderWidth: '2px',
                  },
                // Compact input size matching grid row height
                '& .MuiInputBase-root': {
                  fontSize: theme => theme.typography.body2.fontSize,
                },
                '& .MuiOutlinedInput-input': {
                  py: '7px',
                  px: '8px',
                  fontSize: theme => theme.typography.body2.fontSize,
                },
                '& .MuiInputBase-inputMultiline': { py: '6px', px: '8px' },
                // ── Row actions hover ────────────────────────────────────
                '& .row-actions': {
                  opacity: 0,
                  pointerEvents: 'none',
                  transition: 'opacity 0.15s ease',
                },
                '& .MuiTableRow-root:hover .row-actions': {
                  opacity: 1,
                  pointerEvents: 'auto',
                },
              }}
            >
              <Table>
                <TableHead>
                  <TableRow>
                    {testType === 'Single-Turn' ? (
                      <>
                        <TableCell sx={{ minWidth: 300 }}>
                          Test Prompt *
                        </TableCell>
                        <TableCell sx={{ minWidth: 200 }}>Category *</TableCell>
                        <TableCell sx={{ minWidth: 200 }}>Topic *</TableCell>
                        <TableCell sx={{ minWidth: 200 }}>Behavior *</TableCell>
                        <TableCell sx={{ minWidth: 300 }}>
                          Expected Output
                        </TableCell>
                      </>
                    ) : (
                      <>
                        <TableCell sx={{ minWidth: 320 }}>Goal *</TableCell>
                        <TableCell sx={{ minWidth: 280 }}>
                          Instructions
                        </TableCell>
                        <TableCell sx={{ minWidth: 280 }}>
                          Restrictions
                        </TableCell>
                        <TableCell sx={{ minWidth: 280 }}>Scenario</TableCell>
                        <TableCell sx={{ minWidth: 160 }}>
                          Turn Config
                        </TableCell>
                        <TableCell sx={{ minWidth: 200 }}>Category *</TableCell>
                        <TableCell sx={{ minWidth: 200 }}>Topic *</TableCell>
                        <TableCell sx={{ minWidth: 200 }}>Behavior *</TableCell>
                      </>
                    )}
                    <TableCell sx={theme => ({ width: theme.spacing(7.5) })}>
                      Files
                    </TableCell>
                    <TableCell sx={{ width: 60 }} />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {testCases.map(testCase => (
                    <TableRow key={testCase.id}>
                      {testCase.testType === 'Single-Turn' ? (
                        <>
                          <TableCell sx={{ p: 1 }}>
                            <TextField
                              fullWidth
                              multiline
                              minRows={2}
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
                              multiline
                              minRows={2}
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
                        </>
                      ) : (
                        <>
                          <TableCell sx={{ p: 1 }}>
                            <TextField
                              fullWidth
                              multiline
                              minRows={2}
                              maxRows={2}
                              value={testCase.goal}
                              onChange={e =>
                                updateTestCase(
                                  testCase.id,
                                  'goal',
                                  e.target.value
                                )
                              }
                              placeholder="What the target should do - the success criteria for this test"
                              size="small"
                              disabled={loading}
                            />
                          </TableCell>
                          <TableCell sx={{ p: 1 }}>
                            <TextField
                              fullWidth
                              multiline
                              minRows={2}
                              maxRows={2}
                              value={testCase.instructions}
                              onChange={e =>
                                updateTestCase(
                                  testCase.id,
                                  'instructions',
                                  e.target.value
                                )
                              }
                              placeholder="How to conduct the test - if not provided, the agent plans its own approach"
                              size="small"
                              disabled={loading}
                            />
                          </TableCell>
                          <TableCell sx={{ p: 1 }}>
                            <TextField
                              fullWidth
                              multiline
                              minRows={2}
                              maxRows={2}
                              value={testCase.restrictions}
                              onChange={e =>
                                updateTestCase(
                                  testCase.id,
                                  'restrictions',
                                  e.target.value
                                )
                              }
                              placeholder="What the target must not do - forbidden behaviors or boundaries"
                              size="small"
                              disabled={loading}
                            />
                          </TableCell>
                          <TableCell sx={{ p: 1 }}>
                            <TextField
                              fullWidth
                              multiline
                              minRows={2}
                              maxRows={2}
                              value={testCase.scenario}
                              onChange={e =>
                                updateTestCase(
                                  testCase.id,
                                  'scenario',
                                  e.target.value
                                )
                              }
                              placeholder="Context and persona for the test - narrative setup or user role"
                              size="small"
                              disabled={loading}
                            />
                          </TableCell>
                          <TableCell sx={{ p: 1 }}>
                            <Box
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                              }}
                            >
                              <TextField
                                type="number"
                                label="Min"
                                value={testCase.minTurns}
                                onChange={e => {
                                  const val = Math.min(
                                    50,
                                    Math.max(1, parseInt(e.target.value) || 1)
                                  );
                                  updateTestCase(
                                    testCase.id,
                                    'minTurns',
                                    Math.min(val, testCase.maxTurns)
                                  );
                                }}
                                inputProps={{ min: 1, max: 50 }}
                                size="small"
                                disabled={loading}
                                sx={{ width: 72 }}
                              />
                              <TextField
                                type="number"
                                label="Max"
                                value={testCase.maxTurns}
                                onChange={e => {
                                  const val = Math.min(
                                    50,
                                    Math.max(1, parseInt(e.target.value) || 10)
                                  );
                                  updateTestCase(
                                    testCase.id,
                                    'maxTurns',
                                    Math.max(val, testCase.minTurns ?? 1)
                                  );
                                }}
                                inputProps={{ min: 1, max: 50 }}
                                size="small"
                                disabled={loading}
                                sx={{ width: 72 }}
                              />
                            </Box>
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
                        </>
                      )}
                      <TableCell sx={{ textAlign: 'center' }}>
                        <Tooltip title="Attach files">
                          <IconButton
                            size="small"
                            onClick={() => setAttachDialogRowId(testCase.id)}
                            disabled={loading}
                          >
                            <Badge
                              badgeContent={
                                pendingFilesMap[testCase.id]?.length ?? 0
                              }
                              color="primary"
                              max={9}
                            >
                              <AttachFileIcon fontSize="small" />
                            </Badge>
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                      <TableCell sx={{ px: 1 }}>
                        <Box
                          className="row-actions"
                          sx={{
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                          }}
                        >
                          <IconButton
                            onClick={() => deleteRow(testCase.id)}
                            disabled={testCases.length === 1 || loading}
                            size="small"
                            sx={{
                              color: 'text.secondary',
                              '&:hover': {
                                color: 'error.main',
                                bgcolor: 'action.hover',
                              },
                            }}
                          >
                            <DeleteIcon sx={{ fontSize: 18 }} />
                          </IconButton>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Box>
      </PageLayout>

      {/* Save Test Cases Drawer */}
      <BaseDrawer
        open={showSaveDialog}
        onClose={handleCancelSave}
        title="Save Test Cases"
        onSave={handleConfirmSave}
        saveButtonText={saving ? 'Saving...' : 'Save'}
        saveDisabled={saving}
        loading={saving}
      >
        <TextField
          fullWidth
          label="Test Set Name (Optional)"
          placeholder="Leave empty to save tests without a set"
          value={testSetName}
          onChange={e => setTestSetName(e.target.value)}
          helperText="If provided, tests will be grouped into a reusable test set"
          disabled={saving}
          sx={drawerOutlinedFieldSx}
        />
      </BaseDrawer>

      {/* Attach Files Dialog */}
      <Dialog
        open={attachDialogRowId !== null}
        onClose={() => setAttachDialogRowId(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <Typography variant="h6">
              Attach Files to Test Case #
              {attachDialogRowId
                ? testCases.findIndex(tc => tc.id === attachDialogRowId) + 1
                : ''}
            </Typography>
            <IconButton size="small" onClick={() => setAttachDialogRowId(null)}>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent>
          {attachDialogRowId && (
            <MultiFileUpload
              selectedFiles={pendingFilesMap[attachDialogRowId] ?? []}
              onFilesSelect={files =>
                setPendingFilesMap(prev => ({
                  ...prev,
                  [attachDialogRowId]: [
                    ...(prev[attachDialogRowId] ?? []),
                    ...files,
                  ],
                }))
              }
              onFileRemove={idx =>
                setPendingFilesMap(prev => ({
                  ...prev,
                  [attachDialogRowId]: (prev[attachDialogRowId] ?? []).filter(
                    (_, i) => i !== idx
                  ),
                }))
              }
            />
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            variant="contained"
            onClick={() => setAttachDialogRowId(null)}
          >
            Done
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
