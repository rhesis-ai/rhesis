'use client';

import { useState, useMemo, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Tabs,
  Tab,
  Chip,
  Collapse,
  IconButton,
  Tooltip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from '@mui/material';
import {
  GridColDef,
  GridPaginationModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import FolderIcon from '@mui/icons-material/Folder';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import ListIcon from '@mui/icons-material/List';
import AddIcon from '@mui/icons-material/AddOutlined';
import EditIcon from '@mui/icons-material/EditOutlined';
import {
  TestNode,
  TestNodeCreate,
  TestNodeUpdate,
  Topic,
} from '@/utils/api-client/interfaces/adaptive-testing';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

// ============================================================================
// Types
// ============================================================================

interface TopicTreeNode {
  name: string;
  path: string;
  children: TopicTreeNode[];
  directTestCount: number;
  totalTestCount: number;
  avgScore: number | null;
}

interface AdaptiveTestingDetailProps {
  tests: TestNode[];
  topics: Topic[];
  testSetName: string;
  testSetId: string;
  sessionToken: string;
}

// ============================================================================
// Helpers
// ============================================================================

function getScoreColor(
  score: number | null
): 'success' | 'warning' | 'error' | 'default' {
  if (score === null) return 'default';
  if (score >= 0.7) return 'error';
  if (score >= 0.3) return 'warning';
  return 'success';
}

function getLabelColor(
  label: string
): 'success' | 'error' | 'default' {
  if (label === 'pass') return 'success';
  if (label === 'fail') return 'error';
  return 'default';
}

/**
 * Build a hierarchical tree from flat topic list and tests.
 */
function buildTopicTree(
  topics: Topic[],
  tests: TestNode[]
): TopicTreeNode[] {
  const nodeMap = new Map<string, TopicTreeNode>();

  // Create nodes from topics
  for (const topic of topics) {
    nodeMap.set(topic.path, {
      name: topic.name || topic.path.split('/').pop() || '',
      path: topic.path,
      children: [],
      directTestCount: 0,
      totalTestCount: 0,
      avgScore: null,
    });
  }

  // Also create nodes from test topics (for any not in topics list)
  for (const test of tests) {
    if (test.topic && !nodeMap.has(test.topic)) {
      const parts = test.topic.split('/');
      // Create all intermediate nodes
      for (let i = 0; i < parts.length; i++) {
        const path = parts.slice(0, i + 1).join('/');
        if (!nodeMap.has(path)) {
          nodeMap.set(path, {
            name: decodeURIComponent(parts[i]),
            path,
            children: [],
            directTestCount: 0,
            totalTestCount: 0,
            avgScore: null,
          });
        }
      }
    }
  }

  // Count tests per topic
  const testCounts = new Map<string, number>();
  const scoreSums = new Map<string, number>();
  const scoreCounts = new Map<string, number>();

  for (const test of tests) {
    if (!test.topic) continue;
    testCounts.set(
      test.topic,
      (testCounts.get(test.topic) || 0) + 1
    );
    if (test.model_score !== null && test.model_score !== undefined) {
      scoreSums.set(
        test.topic,
        (scoreSums.get(test.topic) || 0) + test.model_score
      );
      scoreCounts.set(
        test.topic,
        (scoreCounts.get(test.topic) || 0) + 1
      );
    }
  }

  // Update node counts
  for (const [path, node] of nodeMap) {
    node.directTestCount = testCounts.get(path) || 0;
    const sCount = scoreCounts.get(path) || 0;
    node.avgScore =
      sCount > 0
        ? (scoreSums.get(path) || 0) / sCount
        : null;
  }

  // Build parent-child relationships
  for (const [path, node] of nodeMap) {
    const parentPath = path.includes('/')
      ? path.substring(0, path.lastIndexOf('/'))
      : null;
    if (parentPath && nodeMap.has(parentPath)) {
      const parent = nodeMap.get(parentPath)!;
      if (!parent.children.find(c => c.path === path)) {
        parent.children.push(node);
      }
    }
  }

  // Compute total counts recursively
  function computeTotals(node: TopicTreeNode): {
    count: number;
    scoreSum: number;
    scoreCount: number;
  } {
    let totalCount = node.directTestCount;
    let scoreSum =
      node.avgScore !== null
        ? node.avgScore * node.directTestCount
        : 0;
    let scoreCount =
      node.avgScore !== null ? node.directTestCount : 0;

    for (const child of node.children) {
      const childStats = computeTotals(child);
      totalCount += childStats.count;
      scoreSum += childStats.scoreSum;
      scoreCount += childStats.scoreCount;
    }

    node.totalTestCount = totalCount;
    if (scoreCount > 0) {
      node.avgScore = scoreSum / scoreCount;
    }

    return { count: totalCount, scoreSum, scoreCount };
  }

  // Get root nodes (no parent in nodeMap)
  const roots: TopicTreeNode[] = [];
  for (const [path, node] of nodeMap) {
    const parentPath = path.includes('/')
      ? path.substring(0, path.lastIndexOf('/'))
      : null;
    if (!parentPath || !nodeMap.has(parentPath)) {
      roots.push(node);
    }
  }

  // Compute totals for all roots
  for (const root of roots) {
    computeTotals(root);
  }

  // Sort children alphabetically
  function sortTree(nodes: TopicTreeNode[]) {
    nodes.sort((a, b) => a.name.localeCompare(b.name));
    for (const node of nodes) {
      sortTree(node.children);
    }
  }
  sortTree(roots);

  return roots;
}

// ============================================================================
// Tree Node Component
// ============================================================================

interface TreeNodeViewProps {
  node: TopicTreeNode;
  level: number;
  selectedTopic: string | null;
  onTopicSelect: (path: string | null) => void;
  expandedPaths: Set<string>;
  onToggleExpand: (path: string) => void;
}

function TreeNodeView({
  node,
  level,
  selectedTopic,
  onTopicSelect,
  expandedPaths,
  onToggleExpand,
}: TreeNodeViewProps) {
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedPaths.has(node.path);
  const isSelected = selectedTopic === node.path;

  return (
    <Box>
      <Box
        onClick={() => onTopicSelect(node.path)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          py: 0.75,
          px: 1,
          ml: level * 2,
          cursor: 'pointer',
          borderRadius: 1,
          backgroundColor: isSelected
            ? 'action.selected'
            : 'transparent',
          '&:hover': {
            backgroundColor: isSelected
              ? 'action.selected'
              : 'action.hover',
          },
        }}
      >
        {/* Expand/Collapse */}
        <Box sx={{ width: 28, flexShrink: 0 }}>
          {hasChildren && (
            <IconButton
              size="small"
              onClick={e => {
                e.stopPropagation();
                onToggleExpand(node.path);
              }}
              sx={{ p: 0.5 }}
            >
              {isExpanded ? (
                <ExpandMoreIcon
                  fontSize="small"
                  sx={{ color: 'text.secondary' }}
                />
              ) : (
                <ChevronRightIcon
                  fontSize="small"
                  sx={{ color: 'text.secondary' }}
                />
              )}
            </IconButton>
          )}
        </Box>

        {/* Folder Icon */}
        <Box
          sx={{
            mr: 1,
            display: 'flex',
            alignItems: 'center',
          }}
        >
          {isExpanded ? (
            <FolderOpenIcon
              fontSize="small"
              sx={{ color: 'text.secondary' }}
            />
          ) : (
            <FolderIcon
              fontSize="small"
              sx={{ color: 'text.secondary' }}
            />
          )}
        </Box>

        {/* Topic Name */}
        <Typography
          variant="body2"
          sx={{
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            fontWeight: isSelected ? 600 : 400,
          }}
        >
          {decodeURIComponent(node.name)}
        </Typography>

        {/* Direct Test Count */}
        <Chip
          label={node.directTestCount}
          size="small"
          variant="outlined"
          sx={{
            height: 20,
            fontSize: '0.75rem',
            ml: 1,
          }}
        />

        {/* Children count */}
        {node.totalTestCount > node.directTestCount && (
          <Chip
            label={`+${node.totalTestCount - node.directTestCount}`}
            size="small"
            variant="outlined"
            sx={{
              height: 18,
              fontSize: '0.7rem',
              ml: 0.5,
              color: 'text.secondary',
              borderColor: 'divider',
            }}
          />
        )}

        {/* Average Score */}
        {node.avgScore !== null && (
          <Chip
            label={node.avgScore.toFixed(2)}
            size="small"
            color={getScoreColor(node.avgScore)}
            sx={{
              height: 20,
              fontSize: '0.75rem',
              ml: 0.5,
            }}
          />
        )}
      </Box>

      {/* Children */}
      {hasChildren && (
        <Collapse in={isExpanded} timeout="auto" unmountOnExit>
          <Box
            sx={{
              position: 'relative',
              ml: 1.5,
              '&::before': {
                content: '""',
                position: 'absolute',
                left: level * 16 + 14,
                top: 0,
                bottom: 8,
                width: '1px',
                backgroundColor: 'divider',
              },
            }}
          >
            {node.children.map(child => (
              <TreeNodeView
                key={child.path}
                node={child}
                level={level + 1}
                selectedTopic={selectedTopic}
                onTopicSelect={onTopicSelect}
                expandedPaths={expandedPaths}
                onToggleExpand={onToggleExpand}
              />
            ))}
          </Box>
        </Collapse>
      )}
    </Box>
  );
}

// ============================================================================
// Add Topic Dialog
// ============================================================================

interface AddTopicDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (topicPath: string) => Promise<void>;
  parentTopic: string | null;
}

function AddTopicDialog({
  open,
  onClose,
  onSubmit,
  parentTopic,
}: AddTopicDialogProps) {
  const [topicName, setTopicName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const fullPath = parentTopic
    ? `${parentTopic}/${topicName}`
    : topicName;

  const handleSubmit = async () => {
    const trimmed = topicName.trim();
    if (!trimmed) {
      setError('Topic name is required');
      return;
    }
    if (trimmed.includes('/')) {
      setError('Use parent selection for nested topics');
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      await onSubmit(fullPath);
      setTopicName('');
      onClose();
    } catch (err) {
      setError(
        (err as Error).message || 'Failed to create topic'
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setTopicName('');
    setError('');
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle>Add Topic</DialogTitle>
      <DialogContent>
        {parentTopic && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: 2 }}
          >
            Parent: {decodeURIComponent(parentTopic)}
          </Typography>
        )}
        <TextField
          autoFocus
          label="Topic Name"
          fullWidth
          value={topicName}
          onChange={e => {
            setTopicName(e.target.value);
            setError('');
          }}
          onKeyDown={e => {
            if (e.key === 'Enter' && !submitting) {
              handleSubmit();
            }
          }}
          error={!!error}
          helperText={
            error ||
            (topicName.trim()
              ? `Will create: ${fullPath}`
              : ' ')
          }
          disabled={submitting}
          sx={{ mt: 1 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={submitting || !topicName.trim()}
        >
          {submitting ? 'Creating...' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ============================================================================
// Add Test Dialog
// ============================================================================

interface AddTestDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: TestNodeCreate) => Promise<void>;
  topic: string | null;
  topics: Topic[];
}

function AddTestDialog({
  open,
  onClose,
  onSubmit,
  topic,
  topics,
}: AddTestDialogProps) {
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [selectedTopic, setSelectedTopic] = useState(
    topic || ''
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Sync default topic when dialog opens with a new topic
  const handleOpen = () => {
    setSelectedTopic(topic || '');
  };

  const handleSubmit = async () => {
    const trimmedInput = input.trim();
    if (!trimmedInput) {
      setError('Test input is required');
      return;
    }
    if (!selectedTopic.trim()) {
      setError('Topic is required');
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      await onSubmit({
        topic: selectedTopic.trim(),
        input: trimmedInput,
        output: output.trim(),
        labeler: 'user',
      });
      // Reset form
      setInput('');
      setOutput('');
      setSelectedTopic('');
      onClose();
    } catch (err) {
      setError(
        (err as Error).message || 'Failed to create test'
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setInput('');
    setOutput('');
    setError('');
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      TransitionProps={{ onEnter: handleOpen }}
    >
      <DialogTitle>Add Test</DialogTitle>
      <DialogContent
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          pt: 1,
        }}
      >
        {error && (
          <Typography variant="body2" color="error">
            {error}
          </Typography>
        )}
        <TextField
          select
          label="Topic"
          fullWidth
          value={selectedTopic}
          onChange={e => {
            setSelectedTopic(e.target.value);
            setError('');
          }}
          disabled={submitting}
          sx={{ mt: 1 }}
          SelectProps={{ native: true }}
        >
          <option value="">Select a topic...</option>
          {topics.map(t => (
            <option key={t.path} value={t.path}>
              {t.path}
            </option>
          ))}
        </TextField>
        <TextField
          autoFocus
          label="Input"
          placeholder="Enter the test prompt..."
          fullWidth
          multiline
          minRows={2}
          maxRows={6}
          value={input}
          onChange={e => {
            setInput(e.target.value);
            setError('');
          }}
          disabled={submitting}
        />
        <TextField
          label="Expected Output"
          placeholder="Expected or actual output (optional)"
          fullWidth
          multiline
          minRows={2}
          maxRows={6}
          value={output}
          onChange={e => setOutput(e.target.value)}
          disabled={submitting}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={
            submitting ||
            !input.trim() ||
            !selectedTopic.trim()
          }
        >
          {submitting ? 'Creating...' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ============================================================================
// Edit Test Dialog
// ============================================================================

interface EditTestDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (
    testId: string,
    data: TestNodeUpdate
  ) => Promise<void>;
  test: TestNode | null;
  topics: Topic[];
}

function EditTestDialog({
  open,
  onClose,
  onSubmit,
  test,
  topics,
}: EditTestDialogProps) {
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [label, setLabel] = useState<'' | 'pass' | 'fail'>(
    ''
  );
  const [selectedTopic, setSelectedTopic] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Populate form when dialog opens with a test
  const handleOpen = () => {
    if (test) {
      setInput(test.input || '');
      setOutput(test.output || '');
      setLabel(
        (test.label as '' | 'pass' | 'fail') || ''
      );
      setSelectedTopic(test.topic || '');
    }
  };

  const handleSubmit = async () => {
    if (!test) return;
    const trimmedInput = input.trim();
    if (!trimmedInput) {
      setError('Test input is required');
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      const updates: TestNodeUpdate = {};
      if (trimmedInput !== (test.input || ''))
        updates.input = trimmedInput;
      if (output.trim() !== (test.output || ''))
        updates.output = output.trim();
      if (label !== ((test.label as '' | 'pass' | 'fail') || ''))
        updates.label = label;
      if (
        selectedTopic.trim() &&
        selectedTopic.trim() !== (test.topic || '')
      )
        updates.topic = selectedTopic.trim();

      await onSubmit(test.id, updates);
      onClose();
    } catch (err) {
      setError(
        (err as Error).message || 'Failed to update test'
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setError('');
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      TransitionProps={{ onEnter: handleOpen }}
    >
      <DialogTitle>Edit Test</DialogTitle>
      <DialogContent
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          pt: 1,
        }}
      >
        {error && (
          <Typography variant="body2" color="error">
            {error}
          </Typography>
        )}
        <TextField
          select
          label="Topic"
          fullWidth
          value={selectedTopic}
          onChange={e => {
            setSelectedTopic(e.target.value);
            setError('');
          }}
          disabled={submitting}
          sx={{ mt: 1 }}
          SelectProps={{ native: true }}
        >
          <option value="">Select a topic...</option>
          {topics.map(t => (
            <option key={t.path} value={t.path}>
              {t.path}
            </option>
          ))}
        </TextField>
        <TextField
          autoFocus
          label="Input"
          fullWidth
          multiline
          minRows={2}
          maxRows={6}
          value={input}
          onChange={e => {
            setInput(e.target.value);
            setError('');
          }}
          disabled={submitting}
        />
        <TextField
          label="Expected Output"
          fullWidth
          multiline
          minRows={2}
          maxRows={6}
          value={output}
          onChange={e => setOutput(e.target.value)}
          disabled={submitting}
        />
        <TextField
          select
          label="Label"
          fullWidth
          value={label}
          onChange={e =>
            setLabel(
              e.target.value as '' | 'pass' | 'fail'
            )
          }
          disabled={submitting}
          SelectProps={{ native: true }}
        >
          <option value="">No label</option>
          <option value="pass">Pass</option>
          <option value="fail">Fail</option>
        </TextField>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={submitting}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={submitting || !input.trim()}
        >
          {submitting ? 'Saving...' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ============================================================================
// Topic Tree Panel
// ============================================================================

interface TopicTreePanelProps {
  topicTree: TopicTreeNode[];
  tests: TestNode[];
  selectedTopic: string | null;
  onTopicSelect: (path: string | null) => void;
  onAddTopic: (parentTopic: string | null) => void;
}

function TopicTreePanel({
  topicTree,
  tests,
  selectedTopic,
  onTopicSelect,
  onAddTopic,
}: TopicTreePanelProps) {
  // Start with all paths expanded
  const [expandedPaths, setExpandedPaths] = useState<
    Set<string>
  >(() => {
    const paths = new Set<string>();
    function collectPaths(nodes: TopicTreeNode[]) {
      for (const node of nodes) {
        paths.add(node.path);
        collectPaths(node.children);
      }
    }
    collectPaths(topicTree);
    return paths;
  });

  const handleToggleExpand = (path: string) => {
    setExpandedPaths(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  if (topicTree.length === 0) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          No topics found
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* All Tests option */}
      <Box
        onClick={() => onTopicSelect(null)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          py: 0.75,
          px: 1,
          cursor: 'pointer',
          borderRadius: 1,
          backgroundColor:
            selectedTopic === null
              ? 'action.selected'
              : 'transparent',
          '&:hover': {
            backgroundColor:
              selectedTopic === null
                ? 'action.selected'
                : 'action.hover',
          },
          mb: 1,
        }}
      >
        <Box sx={{ width: 28, flexShrink: 0 }} />
        <FolderIcon
          fontSize="small"
          sx={{ mr: 1, color: 'text.secondary' }}
        />
        <Typography
          variant="body2"
          sx={{
            flex: 1,
            fontWeight:
              selectedTopic === null ? 600 : 400,
          }}
        >
          All Tests
        </Typography>
        <Chip
          label={tests.length}
          size="small"
          variant="outlined"
          sx={{ height: 20, fontSize: '0.75rem' }}
        />
      </Box>

      {/* Topic Tree */}
      {topicTree.map(node => (
        <TreeNodeView
          key={node.path}
          node={node}
          level={0}
          selectedTopic={selectedTopic}
          onTopicSelect={onTopicSelect}
          expandedPaths={expandedPaths}
          onToggleExpand={handleToggleExpand}
        />
      ))}

      {/* Add Topic Button */}
      <Box sx={{ mt: 1, px: 1 }}>
        <Button
          size="small"
          startIcon={<AddIcon />}
          onClick={() => onAddTopic(selectedTopic)}
          sx={{
            textTransform: 'none',
            color: 'text.secondary',
            justifyContent: 'flex-start',
          }}
          fullWidth
        >
          Add topic
          {selectedTopic
            ? ` under ${decodeURIComponent(selectedTopic.split('/').pop() || selectedTopic)}`
            : ''}
        </Button>
      </Box>
    </Box>
  );
}

// ============================================================================
// Tests List (DataGrid)
// ============================================================================

interface TestsListProps {
  tests: TestNode[];
  loading: boolean;
  onEditTest?: (test: TestNode) => void;
}

function TestsList({
  tests,
  loading,
  onEditTest,
}: TestsListProps) {
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });

  const handlePaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      setPaginationModel(newModel);
    },
    []
  );

  const columns: GridColDef[] = [
    {
      field: 'input',
      headerName: 'Input',
      flex: 2,
      minWidth: 200,
      renderCell: params => (
        <Tooltip
          title={params.value || ''}
          arrow
          placement="top"
        >
          <Typography
            variant="body2"
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {params.value || '-'}
          </Typography>
        </Tooltip>
      ),
    },
    {
      field: 'output',
      headerName: 'Output',
      flex: 2,
      minWidth: 200,
      renderCell: params => (
        <Tooltip
          title={params.value || ''}
          arrow
          placement="top"
        >
          <Typography
            variant="body2"
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {params.value || '-'}
          </Typography>
        </Tooltip>
      ),
    },
    {
      field: 'model_score',
      headerName: 'Score',
      width: 100,
      align: 'center',
      headerAlign: 'center',
      renderCell: params => {
        const score = params.value;
        if (
          score === null ||
          score === undefined ||
          score === 0
        ) {
          return (
            <Chip
              label="N/A"
              size="small"
              variant="outlined"
            />
          );
        }
        return (
          <Chip
            label={score.toFixed(2)}
            size="small"
            color={getScoreColor(score)}
            variant="filled"
          />
        );
      },
    },
    {
      field: 'label',
      headerName: 'Label',
      width: 100,
      renderCell: params => {
        const label = params.value;
        if (!label) return '-';
        return (
          <Chip
            label={label}
            size="small"
            color={getLabelColor(label)}
            variant="outlined"
          />
        );
      },
    },
    ...(onEditTest
      ? [
          {
            field: 'actions',
            headerName: '',
            width: 50,
            sortable: false,
            filterable: false,
            disableColumnMenu: true,
            renderCell: (params: any) => (
              <IconButton
                size="small"
                onClick={() => onEditTest(params.row)}
                sx={{ color: 'text.secondary' }}
              >
                <EditIcon fontSize="small" />
              </IconButton>
            ),
          } as GridColDef,
        ]
      : []),
  ];

  return (
    <Box>
      {tests.length === 0 ? (
        <Box sx={{ p: 4, textAlign: 'center' }}>
          <Typography
            variant="body1"
            color="text.secondary"
          >
            No tests found
          </Typography>
        </Box>
      ) : (
        <BaseDataGrid
          columns={columns}
          rows={tests}
          loading={loading}
          getRowId={row => row.id}
          showToolbar={false}
          paginationModel={paginationModel}
          onPaginationModelChange={
            handlePaginationModelChange
          }
          serverSidePagination={false}
          totalRows={tests.length}
          pageSizeOptions={[10, 25, 50, 100]}
          disablePaperWrapper={true}
          persistState
        />
      )}
    </Box>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function AdaptiveTestingDetail({
  tests: initialTests,
  topics: initialTopics,
  testSetName,
  testSetId,
  sessionToken,
}: AdaptiveTestingDetailProps) {
  const [selectedTopic, setSelectedTopic] = useState<
    string | null
  >(null);
  const [activeTab, setActiveTab] = useState(0);
  const [addTopicDialogOpen, setAddTopicDialogOpen] =
    useState(false);
  const [addTopicParent, setAddTopicParent] = useState<
    string | null
  >(null);
  const [tests, setTests] = useState<TestNode[]>(initialTests);
  const [topics, setTopics] =
    useState<Topic[]>(initialTopics);
  const [addTestDialogOpen, setAddTestDialogOpen] =
    useState(false);
  const [editTestDialogOpen, setEditTestDialogOpen] =
    useState(false);
  const [editingTest, setEditingTest] =
    useState<TestNode | null>(null);

  // Build the topic tree
  const topicTree = useMemo(
    () => buildTopicTree(topics, tests),
    [topics, tests]
  );

  const handleAddTopicOpen = (parentTopic: string | null) => {
    setAddTopicParent(parentTopic);
    setAddTopicDialogOpen(true);
  };

  const handleAddTopicSubmit = async (topicPath: string) => {
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getAdaptiveTestingClient();

    await client.createTopic(testSetId, { path: topicPath });

    // Refresh tree and topics data
    const [treeNodes, updatedTopics] = await Promise.all([
      client.getTree(testSetId),
      client.getTopics(testSetId),
    ]);

    setTests(
      treeNodes.filter(node => node.label !== 'topic_marker')
    );
    setTopics(updatedTopics);
  };

  const handleAddTestSubmit = async (data: TestNodeCreate) => {
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getAdaptiveTestingClient();

    await client.createTest(testSetId, data);

    // Refresh tree and topics data
    const [treeNodes, updatedTopics] = await Promise.all([
      client.getTree(testSetId),
      client.getTopics(testSetId),
    ]);

    setTests(
      treeNodes.filter(node => node.label !== 'topic_marker')
    );
    setTopics(updatedTopics);
  };

  const handleEditTestOpen = (test: TestNode) => {
    setEditingTest(test);
    setEditTestDialogOpen(true);
  };

  const handleEditTestSubmit = async (
    testId: string,
    data: TestNodeUpdate
  ) => {
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getAdaptiveTestingClient();

    await client.updateTest(testSetId, testId, data);

    // Refresh tree and topics data
    const [treeNodes, updatedTopics] = await Promise.all([
      client.getTree(testSetId),
      client.getTopics(testSetId),
    ]);

    setTests(
      treeNodes.filter(node => node.label !== 'topic_marker')
    );
    setTopics(updatedTopics);
  };

  // Filter tests by selected topic
  const filteredTests = useMemo(() => {
    if (selectedTopic === null) {
      return tests;
    }
    return tests.filter(test => test.topic === selectedTopic);
  }, [tests, selectedTopic]);

  // Stats
  const totalTests = tests.length;
  const totalTopics = topics.length;
  const passCount = tests.filter(
    t => t.label === 'pass'
  ).length;
  const failCount = tests.filter(
    t => t.label === 'fail'
  ).length;

  return (
    <Box>
      {/* Summary Stats */}
      <Box
        sx={{
          display: 'flex',
          gap: 2,
          mb: 3,
          flexWrap: 'wrap',
        }}
      >
        <Paper
          variant="outlined"
          sx={{ px: 3, py: 2, minWidth: 120 }}
        >
          <Typography
            variant="caption"
            color="text.secondary"
          >
            Total Tests
          </Typography>
          <Typography variant="h5" fontWeight={600}>
            {totalTests}
          </Typography>
        </Paper>
        <Paper
          variant="outlined"
          sx={{ px: 3, py: 2, minWidth: 120 }}
        >
          <Typography
            variant="caption"
            color="text.secondary"
          >
            Topics
          </Typography>
          <Typography variant="h5" fontWeight={600}>
            {totalTopics}
          </Typography>
        </Paper>
        <Paper
          variant="outlined"
          sx={{ px: 3, py: 2, minWidth: 120 }}
        >
          <Typography
            variant="caption"
            color="text.secondary"
          >
            Pass
          </Typography>
          <Typography
            variant="h5"
            fontWeight={600}
            color="success.main"
          >
            {passCount}
          </Typography>
        </Paper>
        <Paper
          variant="outlined"
          sx={{ px: 3, py: 2, minWidth: 120 }}
        >
          <Typography
            variant="caption"
            color="text.secondary"
          >
            Fail
          </Typography>
          <Typography
            variant="h5"
            fontWeight={600}
            color="error.main"
          >
            {failCount}
          </Typography>
        </Paper>
      </Box>

      {/* View Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs
          value={activeTab}
          onChange={(_, newValue) => setActiveTab(newValue)}
        >
          <Tab
            icon={<AccountTreeIcon />}
            iconPosition="start"
            label="Tree View"
          />
          <Tab
            icon={<ListIcon />}
            iconPosition="start"
            label="List View"
          />
        </Tabs>
      </Box>

      {/* Tree View */}
      {activeTab === 0 && (
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            minHeight: 400,
          }}
        >
          {/* Left Panel - Topic Tree */}
          <Paper
            variant="outlined"
            sx={{
              width: 320,
              minWidth: 260,
              maxWidth: 380,
              overflow: 'auto',
              flexShrink: 0,
            }}
          >
            <Box
              sx={{
                p: 1.5,
                borderBottom: 1,
                borderColor: 'divider',
              }}
            >
              <Typography
                variant="subtitle2"
                fontWeight={600}
              >
                Topics
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
              >
                Click to filter tests by topic
              </Typography>
            </Box>
            <Box sx={{ p: 1 }}>
              <TopicTreePanel
                topicTree={topicTree}
                tests={tests}
                selectedTopic={selectedTopic}
                onTopicSelect={setSelectedTopic}
                onAddTopic={handleAddTopicOpen}
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
                gap: 1,
              }}
            >
              <Typography
                variant="subtitle2"
                color="text.primary"
              >
                {selectedTopic
                  ? decodeURIComponent(selectedTopic)
                  : 'All Tests'}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ flex: 1 }}
              >
                ({filteredTests.length}{' '}
                {filteredTests.length === 1
                  ? 'test'
                  : 'tests'}
                )
              </Typography>
              <Button
                size="small"
                startIcon={<AddIcon />}
                onClick={() => setAddTestDialogOpen(true)}
                sx={{ textTransform: 'none' }}
              >
                Add test
              </Button>
            </Box>
            <Paper variant="outlined" sx={{ p: 1 }}>
              <TestsList
                tests={filteredTests}
                loading={false}
                onEditTest={handleEditTestOpen}
              />
            </Paper>
          </Box>
        </Box>
      )}

      {/* List View - All tests in a flat table */}
      {activeTab === 1 && (
        <Box>
          <Box
            sx={{
              mb: 1,
              display: 'flex',
              justifyContent: 'flex-end',
            }}
          >
            <Button
              size="small"
              startIcon={<AddIcon />}
              onClick={() => setAddTestDialogOpen(true)}
              sx={{ textTransform: 'none' }}
            >
              Add test
            </Button>
          </Box>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <TestsList
              tests={tests}
              loading={false}
              onEditTest={handleEditTestOpen}
            />
          </Paper>
        </Box>
      )}

      {/* Add Topic Dialog */}
      <AddTopicDialog
        open={addTopicDialogOpen}
        onClose={() => setAddTopicDialogOpen(false)}
        onSubmit={handleAddTopicSubmit}
        parentTopic={addTopicParent}
      />

      {/* Add Test Dialog */}
      <AddTestDialog
        open={addTestDialogOpen}
        onClose={() => setAddTestDialogOpen(false)}
        onSubmit={handleAddTestSubmit}
        topic={selectedTopic}
        topics={topics}
      />

      {/* Edit Test Dialog */}
      <EditTestDialog
        open={editTestDialogOpen}
        onClose={() => {
          setEditTestDialogOpen(false);
          setEditingTest(null);
        }}
        onSubmit={handleEditTestSubmit}
        test={editingTest}
        topics={topics}
      />
    </Box>
  );
}
