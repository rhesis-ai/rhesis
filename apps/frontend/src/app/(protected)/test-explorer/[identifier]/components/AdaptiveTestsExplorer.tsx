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
        const adaptiveTestingClient = clientFactory.getAdaptiveTestingClient();

        // Update the test's topic using the adaptive testing endpoint
        await adaptiveTestingClient.updateTest(testSetId, testId, {
          topic: newTopicPath,
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
    [sessionToken, tests, testSetId]
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
        const adaptiveTestingClient = clientFactory.getAdaptiveTestingClient();

        if (testData.id && dialogMode === 'edit') {
          // Update existing test using adaptive testing endpoint
          const updatedTest = await adaptiveTestingClient.updateTest(
            testSetId,
            testData.id,
            {
              topic: testData.topic,
              input: testData.input,
              output: testData.output || '[no output]',
            }
          );

          // Update local state
          setTests(prevTests =>
            prevTests.map(t =>
              t.id === testData.id
                ? {
                    ...t,
                    input: updatedTest.input,
                    output: updatedTest.output,
                    topic: updatedTest.topic,
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
          // Create new test using adaptive testing endpoint
          const createdTest = await adaptiveTestingClient.createTest(testSetId, {
            topic: testData.topic,
            input: testData.input,
            output: testData.output || '[no output]',
          });

          const newTest: AdaptiveTest = {
            id: createdTest.id as `${string}-${string}-${string}-${string}-${string}`,
            input: createdTest.input,
            output: createdTest.output,
            score: createdTest.model_score || null,
            topic: createdTest.topic,
            label: createdTest.label,
          };

          setTests(prevTests => [...prevTests, newTest]);

          setSnackbar({
            open: true,
            message: 'Test added successfully',
            severity: 'success',
          });
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
      const adaptiveTestingClient = clientFactory.getAdaptiveTestingClient();

      await adaptiveTestingClient.deleteTest(testSetId, testToDelete.id);

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
  }, [testToDelete, sessionToken, testSetId]);

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
        const adaptiveTestingClient = clientFactory.getAdaptiveTestingClient();

        if (topicDialogMode === 'create') {
          // Create new topic using adaptive testing endpoint
          const newTopicPath = data.parentPath
            ? `${data.parentPath}/${encodeURIComponent(data.name)}`
            : encodeURIComponent(data.name);

          const createdTopic = await adaptiveTestingClient.createTopic(testSetId, {
            path: newTopicPath,
          });

          // Add the new topic to local state so it shows even without tests
          setTopics(prevTopics => [
            ...prevTopics,
            { id: createdTopic.path, name: newTopicPath },
          ]);

          setSnackbar({
            open: true,
            message: `Topic "${data.name}" created successfully`,
            severity: 'success',
          });
        } else if (topicDialogMode === 'rename' && topicToRename) {
          // Rename topic using adaptive testing endpoint
          const oldPath = topicToRename;
          const parentPath = oldPath.includes('/')
            ? oldPath.substring(0, oldPath.lastIndexOf('/'))
            : '';
          const newPath = parentPath
            ? `${parentPath}/${encodeURIComponent(data.name)}`
            : encodeURIComponent(data.name);

          // Use the backend to rename - it handles all tests under this topic
          await adaptiveTestingClient.updateTopic(testSetId, oldPath, {
            new_name: encodeURIComponent(data.name),
          });

          // Update local state - the backend already updated all tests
          setTests(prevTests =>
            prevTests.map(t => {
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

          setSnackbar({
            open: true,
            message: `Topic renamed to "${data.name}"`,
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
    [sessionToken, testSetId, topicDialogMode, topicToRename, selectedTopic]
  );

  // Handle topic delete
  const handleTopicDelete = useCallback(async () => {
    if (!topicToDelete || !sessionToken) return;

    setIsSubmitting(true);

    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const adaptiveTestingClient = clientFactory.getAdaptiveTestingClient();

      const deletedPath = topicToDelete.path;
      const parentPath = deletedPath.includes('/')
        ? deletedPath.substring(0, deletedPath.lastIndexOf('/'))
        : '';

      // Delete topic using adaptive testing endpoint
      // The backend handles moving tests to parent topic
      await adaptiveTestingClient.deleteTopic(testSetId, deletedPath, true);

      // Update local state - the backend already moved all tests
      setTests(prevTests =>
        prevTests.map(t => {
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
  }, [topicToDelete, sessionToken, testSetId, selectedTopic]);

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
