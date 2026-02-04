'use client';

import { useState, useMemo, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Snackbar,
  Alert,
  CircularProgress,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Breadcrumbs,
  Link,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import TopicTreeView, {
  AdaptiveTest,
  TopicAction,
  TopicNode,
  ApiTopic,
} from './TopicTreeView';
import AdaptiveTestsGrid from './AdaptiveTestsGrid';
import AddTestDialog, { TestFormData } from './AddTestDialog';
import TopicDialog, { TopicFormData } from './TopicDialog';
import DeleteTopicDialog from './DeleteTopicDialog';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

interface AdaptiveTestsExplorerProps {
  tests: AdaptiveTest[];
  topics?: ApiTopic[];
  loading: boolean;
  sessionToken?: string;
  testSetId: string;
}

export default function AdaptiveTestsExplorer({
  tests: initialTests,
  topics: initialTopics = [],
  loading,
  sessionToken,
  testSetId,
}: AdaptiveTestsExplorerProps) {
  const [tests, setTests] = useState<AdaptiveTest[]>(initialTests);
  const [topics, setTopics] = useState<ApiTopic[]>(initialTopics);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<'add' | 'edit'>('add');
  const [editingTest, setEditingTest] = useState<AdaptiveTest | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [testToDelete, setTestToDelete] = useState<AdaptiveTest | null>(null);
  // Topic dialog state
  const [topicDialogOpen, setTopicDialogOpen] = useState(false);
  const [topicDialogMode, setTopicDialogMode] = useState<'create' | 'rename'>('create');
  const [topicDialogParentPath, setTopicDialogParentPath] = useState<string | null>(null);
  const [topicDialogInitialName, setTopicDialogInitialName] = useState('');
  const [topicToRename, setTopicToRename] = useState<string | null>(null);
  const [deleteTopicDialogOpen, setDeleteTopicDialogOpen] = useState(false);
  const [topicToDelete, setTopicToDelete] = useState<{
    path: string;
    node?: TopicNode;
  } | null>(null);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({ open: false, message: '', severity: 'success' });

  // Handle moving a test to a new topic
  const handleTestDrop = useCallback(
    async (testId: string, newTopicPath: string) => {
      if (!sessionToken) {
        setSnackbar({
          open: true,
          message: 'Session token not available',
          severity: 'error',
        });
        return;
      }

      // Find the test being moved
      const test = tests.find(t => t.id === testId);
      if (!test) {
        setSnackbar({
          open: true,
          message: 'Test not found',
          severity: 'error',
        });
        return;
      }

      // Don't do anything if dropping on the same topic
      if (test.topic === newTopicPath) {
        return;
      }

      setIsUpdating(true);

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const topicClient = clientFactory.getTopicClient();
        const testsClient = clientFactory.getTestsClient();

        // First, get or create the topic by name
        const topic = await topicClient.getOrCreateTopic(newTopicPath, 'Test');

        // Then update the test with the new topic_id
        await testsClient.updateTest(testId, {
          topic_id: topic.id,
        });

        // Update local state
        setTests(prevTests =>
          prevTests.map(t => (t.id === testId ? { ...t, topic: newTopicPath } : t))
        );

        setSnackbar({
          open: true,
          message: `Test moved to "${decodeURIComponent(newTopicPath)}"`,
          severity: 'success',
        });
      } catch (error) {
        console.error('Failed to update test topic:', error);
        setSnackbar({
          open: true,
          message: `Failed to move test: ${error instanceof Error ? error.message : 'Unknown error'}`,
          severity: 'error',
        });
      } finally {
        setIsUpdating(false);
      }
    },
    [sessionToken, tests]
  );

  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({ ...prev, open: false }));
  };

  // Handle adding or editing a test
  const handleSubmitTest = useCallback(
    async (testData: TestFormData) => {
      if (!sessionToken) {
        throw new Error('Session token not available');
      }

      setIsSubmitting(true);

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const testsClient = clientFactory.getTestsClient();
        const topicClient = clientFactory.getTopicClient();

        if (testData.id && dialogMode === 'edit') {
          // Update existing test
          // First get or create the topic
          const topic = await topicClient.getOrCreateTopic(testData.topic, 'Test');

          // Update the test - we need to update the prompt content separately
          // For now, update the topic and metadata
          await testsClient.updateTest(testData.id, {
            topic_id: topic.id,
            test_metadata: {
              output: testData.output || undefined,
            },
          });

          // Update local state
          setTests(prevTests =>
            prevTests.map(t =>
              t.id === testData.id
                ? {
                    ...t,
                    input: testData.input,
                    output: testData.output || '[no output]',
                    topic: testData.topic,
                  }
                : t
            )
          );

          setSnackbar({
            open: true,
            message: 'Test updated successfully',
            severity: 'success',
          });
        } else {
          // Create new test using bulk create endpoint
          const response = await testsClient.createTestsBulk({
            tests: [
              {
                prompt: {
                  content: testData.input,
                  expected_response: testData.output || undefined,
                },
                topic: testData.topic,
                behavior: 'General',
                category: 'General',
              },
            ],
            test_set_id: testSetId as `${string}-${string}-${string}-${string}-${string}`,
          });

          if (response.success) {
            const newTest: AdaptiveTest = {
              id: `temp-${Date.now()}` as `${string}-${string}-${string}-${string}-${string}`,
              input: testData.input,
              output: testData.output || '[no output]',
              score: null,
              topic: testData.topic,
              label: '',
            };

            setTests(prevTests => [...prevTests, newTest]);

            setSnackbar({
              open: true,
              message: 'Test added successfully',
              severity: 'success',
            });
          } else {
            throw new Error(response.message || 'Failed to create test');
          }
        }
      } catch (error) {
        console.error('Failed to save test:', error);
        setSnackbar({
          open: true,
          message: `Failed to save test: ${error instanceof Error ? error.message : 'Unknown error'}`,
          severity: 'error',
        });
        throw error;
      } finally {
        setIsSubmitting(false);
      }
    },
    [sessionToken, testSetId, dialogMode]
  );

  // Handle opening add dialog
  const handleOpenAddDialog = useCallback(() => {
    setEditingTest(null);
    setDialogMode('add');
    setDialogOpen(true);
  }, []);

  // Handle opening edit dialog
  const handleEditTest = useCallback((test: AdaptiveTest) => {
    setEditingTest(test);
    setDialogMode('edit');
    setDialogOpen(true);
  }, []);

  // Handle delete confirmation
  const handleDeleteClick = useCallback((test: AdaptiveTest) => {
    setTestToDelete(test);
    setDeleteConfirmOpen(true);
  }, []);

  // Handle confirmed delete
  const handleConfirmDelete = useCallback(async () => {
    if (!testToDelete || !sessionToken) return;

    setIsSubmitting(true);

    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const testsClient = clientFactory.getTestsClient();

      await testsClient.deleteTest(testToDelete.id);

      setTests(prevTests => prevTests.filter(t => t.id !== testToDelete.id));

      setSnackbar({
        open: true,
        message: 'Test deleted successfully',
        severity: 'success',
      });
    } catch (error) {
      console.error('Failed to delete test:', error);
      setSnackbar({
        open: true,
        message: `Failed to delete test: ${error instanceof Error ? error.message : 'Unknown error'}`,
        severity: 'error',
      });
    } finally {
      setIsSubmitting(false);
      setDeleteConfirmOpen(false);
      setTestToDelete(null);
    }
  }, [testToDelete, sessionToken]);

  // Handle topic action from context menu
  const handleTopicAction = useCallback((action: TopicAction) => {
    switch (action.type) {
      case 'create':
        setTopicDialogMode('create');
        setTopicDialogParentPath(action.topicPath || null);
        setTopicDialogInitialName('');
        setTopicToRename(null);
        setTopicDialogOpen(true);
        break;
      case 'rename':
        setTopicDialogMode('rename');
        setTopicDialogParentPath(null);
        setTopicDialogInitialName(
          decodeURIComponent(action.topicPath.split('/').pop() || '')
        );
        setTopicToRename(action.topicPath);
        setTopicDialogOpen(true);
        break;
      case 'delete':
        setTopicToDelete({ path: action.topicPath, node: action.topicNode });
        setDeleteTopicDialogOpen(true);
        break;
    }
  }, []);

  // Handle topic create/rename submit
  const handleTopicSubmit = useCallback(
    async (data: TopicFormData) => {
      if (!sessionToken) {
        throw new Error('Session token not available');
      }

      setIsSubmitting(true);

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const topicClient = clientFactory.getTopicClient();

        if (topicDialogMode === 'create') {
          // Create new topic
          const newTopicPath = data.parentPath
            ? `${data.parentPath}/${encodeURIComponent(data.name)}`
            : encodeURIComponent(data.name);

          const createdTopic = await topicClient.getOrCreateTopic(newTopicPath, 'Test');

          // Add the new topic to local state so it shows even without tests
          setTopics(prevTopics => [
            ...prevTopics,
            { id: createdTopic.id, name: newTopicPath },
          ]);

          setSnackbar({
            open: true,
            message: `Topic "${data.name}" created successfully`,
            severity: 'success',
          });
        } else if (topicDialogMode === 'rename' && topicToRename) {
          // Rename topic - update all tests with the old topic path
          const oldPath = topicToRename;
          const parentPath = oldPath.includes('/')
            ? oldPath.substring(0, oldPath.lastIndexOf('/'))
            : '';
          const newPath = parentPath
            ? `${parentPath}/${encodeURIComponent(data.name)}`
            : encodeURIComponent(data.name);

          // Update all tests that have this topic or are under this topic
          const testsToUpdate = tests.filter(t => {
            const topic = typeof t.topic === 'string' ? t.topic : '';
            return topic === oldPath || topic.startsWith(oldPath + '/');
          });

          const testsClient = clientFactory.getTestsClient();
          const deletedTestIds: string[] = [];

          for (const test of testsToUpdate) {
            const testTopic = typeof test.topic === 'string' ? test.topic : '';
            const updatedTopic = testTopic === oldPath
              ? newPath
              : newPath + testTopic.substring(oldPath.length);

            try {
              // Get or create the new topic
              const topic = await topicClient.getOrCreateTopic(updatedTopic, 'Test');

              await testsClient.updateTest(test.id, {
                topic_id: topic.id,
              });
            } catch (updateError) {
              // Handle 410 Gone (test was deleted) - skip and remove from local state
              if (
                updateError instanceof Error &&
                (updateError.message.includes('410') ||
                  updateError.message.includes('deleted'))
              ) {
                console.warn(`Test ${test.id} was deleted, removing from local state`);
                deletedTestIds.push(test.id);
              } else {
                throw updateError;
              }
            }
          }

          // Update local state - remove deleted tests and update renamed ones
          setTests(prevTests =>
            prevTests
              .filter(t => !deletedTestIds.includes(t.id))
              .map(t => {
                const topic = typeof t.topic === 'string' ? t.topic : '';
                if (topic === oldPath) {
                  return { ...t, topic: newPath };
                } else if (topic.startsWith(oldPath + '/')) {
                  return { ...t, topic: newPath + topic.substring(oldPath.length) };
                }
                return t;
              })
          );

          // Update selected topic if it was the renamed one
          if (selectedTopic === oldPath) {
            setSelectedTopic(newPath);
          } else if (selectedTopic?.startsWith(oldPath + '/')) {
            setSelectedTopic(newPath + selectedTopic.substring(oldPath.length));
          }

          const message = deletedTestIds.length > 0
            ? `Topic renamed to "${data.name}" (${deletedTestIds.length} deleted test(s) removed)`
            : `Topic renamed to "${data.name}"`;

          setSnackbar({
            open: true,
            message,
            severity: 'success',
          });
        }
      } catch (error) {
        console.error('Failed to save topic:', error);
        setSnackbar({
          open: true,
          message: `Failed to ${topicDialogMode} topic: ${
            error instanceof Error ? error.message : 'Unknown error'
          }`,
          severity: 'error',
        });
        throw error;
      } finally {
        setIsSubmitting(false);
      }
    },
    [sessionToken, topicDialogMode, topicToRename, tests, selectedTopic]
  );

  // Handle topic delete
  const handleTopicDelete = useCallback(async () => {
    if (!topicToDelete || !sessionToken) return;

    setIsSubmitting(true);

    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const topicClient = clientFactory.getTopicClient();
      const testsClient = clientFactory.getTestsClient();

      const deletedPath = topicToDelete.path;
      const parentPath = deletedPath.includes('/')
        ? deletedPath.substring(0, deletedPath.lastIndexOf('/'))
        : '';

      // Find all tests that need to be moved
      const testsToMove = tests.filter(t => {
        const topic = typeof t.topic === 'string' ? t.topic : '';
        return topic === deletedPath || topic.startsWith(deletedPath + '/');
      });

      const deletedTestIds: string[] = [];

      // Move tests to parent topic (or root if no parent)
      for (const test of testsToMove) {
        const testTopic = typeof test.topic === 'string' ? test.topic : '';

        let newTopic: string;
        if (testTopic === deletedPath) {
          // Direct children go to parent
          newTopic = parentPath;
        } else {
          // Nested children: replace the deleted segment
          const suffix = testTopic.substring(deletedPath.length + 1);
          newTopic = parentPath ? `${parentPath}/${suffix}` : suffix;
        }

        try {
          if (newTopic) {
            const topic = await topicClient.getOrCreateTopic(newTopic, 'Test');
            await testsClient.updateTest(test.id, { topic_id: topic.id });
          } else {
            // Moving to root - set topic_id to null
            await testsClient.updateTest(test.id, { topic_id: undefined });
          }
        } catch (updateError) {
          // Handle 410 Gone (test was deleted) - skip and remove from local state
          if (
            updateError instanceof Error &&
            (updateError.message.includes('410') ||
              updateError.message.includes('deleted'))
          ) {
            console.warn(`Test ${test.id} was deleted, removing from local state`);
            deletedTestIds.push(test.id);
          } else {
            throw updateError;
          }
        }
      }

      // Update local state - remove deleted tests and update moved ones
      setTests(prevTests =>
        prevTests
          .filter(t => !deletedTestIds.includes(t.id))
          .map(t => {
            const topic = typeof t.topic === 'string' ? t.topic : '';
            if (topic === deletedPath) {
              return { ...t, topic: parentPath };
            } else if (topic.startsWith(deletedPath + '/')) {
              const suffix = topic.substring(deletedPath.length + 1);
              return { ...t, topic: parentPath ? `${parentPath}/${suffix}` : suffix };
            }
            return t;
          })
      );

      // Update selected topic if it was deleted
      if (selectedTopic === deletedPath || selectedTopic?.startsWith(deletedPath + '/')) {
        setSelectedTopic(parentPath || null);
      }

      setSnackbar({
        open: true,
        message: 'Topic deleted successfully',
        severity: 'success',
      });
    } catch (error) {
      console.error('Failed to delete topic:', error);
      setSnackbar({
        open: true,
        message: `Failed to delete topic: ${
          error instanceof Error ? error.message : 'Unknown error'
        }`,
        severity: 'error',
      });
    } finally {
      setIsSubmitting(false);
      setDeleteTopicDialogOpen(false);
      setTopicToDelete(null);
    }
  }, [topicToDelete, sessionToken, tests, selectedTopic]);

  // Calculate stats for delete dialog
  const getTopicStats = useCallback(
    (topicPath: string) => {
      let directTestCount = 0;
      const childPaths = new Set<string>();

      tests.forEach(t => {
        const topic = typeof t.topic === 'string' ? t.topic : '';
        if (topic === topicPath) {
          directTestCount++;
        } else if (topic.startsWith(topicPath + '/')) {
          // Count as child
          const remainder = topic.substring(topicPath.length + 1);
          const nextSegment = remainder.split('/')[0];
          childPaths.add(nextSegment);
        }
      });

      return {
        testCount: directTestCount,
        childTopicCount: childPaths.size,
      };
    },
    [tests]
  );

  // Filter tests based on selected topic (exact match only, not children)
  const filteredTests = useMemo(() => {
    if (selectedTopic === null) {
      return tests;
    }
    return tests.filter(test => {
      const topic = typeof test.topic === 'string' ? test.topic : '';
      // Match exact topic only
      return topic === selectedTopic;
    });
  }, [tests, selectedTopic]);

  // Check if we have any topics at all
  const hasTopics = tests.some(test => {
    const topic = typeof test.topic === 'string' ? test.topic : '';
    return topic.length > 0;
  });

  // If no topics, show the grid with add button
  if (!hasTopics) {
    return (
      <>
        <Box
          sx={{
            mb: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Typography variant="subtitle2" color="text.secondary">
            All Tests ({tests.length})
          </Typography>
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={handleOpenAddDialog}
          >
            Add Test
          </Button>
        </Box>
        <AdaptiveTestsGrid
          tests={tests}
          loading={loading}
          sessionToken={sessionToken}
          onEdit={handleEditTest}
          onDelete={handleDeleteClick}
        />
        <AddTestDialog
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          onSubmit={handleSubmitTest}
          selectedTopic={selectedTopic}
          loading={isSubmitting}
          mode={dialogMode}
          initialData={
            editingTest
              ? {
                  id: editingTest.id,
                  input: editingTest.input,
                  output: editingTest.output,
                  topic: editingTest.topic,
                }
              : null
          }
        />
        <Dialog open={deleteConfirmOpen} onClose={() => setDeleteConfirmOpen(false)}>
          <DialogTitle>Delete Test</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to delete this test? This action cannot be undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteConfirmOpen(false)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              onClick={handleConfirmDelete}
              color="error"
              variant="contained"
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogActions>
        </Dialog>
      </>
    );
  }

  return (
    <>
      <Box sx={{ display: 'flex', gap: 2, height: '100%', minHeight: 400 }}>
        {/* Left Panel - Topic Tree */}
        <Paper
          variant="outlined"
          sx={{
            width: 300,
            minWidth: 250,
            maxWidth: 350,
            overflow: 'auto',
            flexShrink: 0,
            position: 'relative',
          }}
        >
          {isUpdating && (
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: 'rgba(255, 255, 255, 0.7)',
                zIndex: 1,
              }}
            >
              <CircularProgress size={24} />
            </Box>
          )}
          <Box sx={{ p: 1.5, borderBottom: 1, borderColor: 'divider' }}>
            <Typography variant="subtitle2" fontWeight={600}>
              Topics
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Drag tests to move between topics
            </Typography>
          </Box>
          <Box sx={{ p: 1 }}>
            <TopicTreeView
              tests={tests}
              topics={topics}
              selectedTopic={selectedTopic}
              onTopicSelect={setSelectedTopic}
              onTestDrop={handleTestDrop}
              onTopicAction={handleTopicAction}
            />
          </Box>
        </Paper>

        {/* Right Panel - Tests Grid */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box
            sx={{
              mb: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {selectedTopic ? (
                <Breadcrumbs separator="/" sx={{ '& .MuiBreadcrumbs-separator': { mx: 0.5 } }}>
                  <Link
                    component="button"
                    variant="subtitle2"
                    color="text.secondary"
                    underline="hover"
                    onClick={() => setSelectedTopic(null)}
                    sx={{ cursor: 'pointer' }}
                  >
                    All Tests
                  </Link>
                  {selectedTopic.split('/').map((segment, index, arr) => {
                    const path = arr.slice(0, index + 1).join('/');
                    const isLast = index === arr.length - 1;
                    return isLast ? (
                      <Typography key={path} variant="subtitle2" color="text.primary">
                        {decodeURIComponent(segment)}
                      </Typography>
                    ) : (
                      <Link
                        key={path}
                        component="button"
                        variant="subtitle2"
                        color="text.secondary"
                        underline="hover"
                        onClick={() => setSelectedTopic(path)}
                        sx={{ cursor: 'pointer' }}
                      >
                        {decodeURIComponent(segment)}
                      </Link>
                    );
                  })}
                </Breadcrumbs>
              ) : (
                <Typography variant="subtitle2" color="text.primary">
                  All Tests
                </Typography>
              )}
              <Typography variant="caption" color="text.secondary">
                ({filteredTests.length} {filteredTests.length === 1 ? 'test' : 'tests'})
              </Typography>
            </Box>
            <Button
              variant="contained"
              size="small"
              startIcon={<AddIcon />}
              onClick={handleOpenAddDialog}
            >
              Add Test
            </Button>
          </Box>
          <AdaptiveTestsGrid
            tests={filteredTests}
            loading={loading}
            sessionToken={sessionToken}
            enableDragDrop={true}
            onEdit={handleEditTest}
            onDelete={handleDeleteClick}
          />
        </Box>
      </Box>

      {/* Feedback Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={handleCloseSnackbar}
          severity={snackbar.severity}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>

      {/* Add/Edit Test Dialog */}
      <AddTestDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleSubmitTest}
        selectedTopic={selectedTopic}
        loading={isSubmitting}
        mode={dialogMode}
        initialData={
          editingTest
            ? {
                id: editingTest.id,
                input: editingTest.input,
                output: editingTest.output,
                topic: editingTest.topic,
              }
            : null
        }
      />

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteConfirmOpen} onClose={() => setDeleteConfirmOpen(false)}>
        <DialogTitle>Delete Test</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete this test? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirmOpen(false)} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirmDelete}
            color="error"
            variant="contained"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Topic Create/Rename Dialog */}
      <TopicDialog
        open={topicDialogOpen}
        onClose={() => setTopicDialogOpen(false)}
        onSubmit={handleTopicSubmit}
        loading={isSubmitting}
        mode={topicDialogMode}
        initialName={topicDialogInitialName}
        parentPath={topicDialogParentPath}
      />

      {/* Delete Topic Dialog */}
      <DeleteTopicDialog
        open={deleteTopicDialogOpen}
        onClose={() => setDeleteTopicDialogOpen(false)}
        onConfirm={handleTopicDelete}
        loading={isSubmitting}
        topicPath={topicToDelete?.path || ''}
        {...(topicToDelete ? getTopicStats(topicToDelete.path) : { testCount: 0, childTopicCount: 0 })}
      />
    </>
  );
}
