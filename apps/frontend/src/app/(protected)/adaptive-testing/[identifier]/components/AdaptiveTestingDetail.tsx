'use client';

import {
  useState,
  useMemo,
  useCallback,
  useEffect,
  useRef,
  DragEvent,
} from 'react';
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
  Autocomplete,
  CircularProgress,
  Alert,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import { GridColDef, GridPaginationModel } from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import FolderIcon from '@mui/icons-material/Folder';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import ListIcon from '@mui/icons-material/List';
import AddIcon from '@mui/icons-material/AddOutlined';
import EditIcon from '@mui/icons-material/EditOutlined';
import DeleteIcon from '@mui/icons-material/DeleteOutlined';
import PlayArrowIcon from '@mui/icons-material/PlayArrowOutlined';
import {
  TestNode,
  TestNodeCreate,
  TestNodeUpdate,
  Topic,
} from '@/utils/api-client/interfaces/adaptive-testing';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';

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

const allTestsTopicOption: Topic = {
  path: '',
  name: 'All tests',
  parent_path: null,
  depth: 0,
  display_name: 'All tests',
  display_path: 'All tests',
  has_direct_tests: false,
  has_subtopics: false,
};

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

function getLabelColor(label: string): 'success' | 'error' | 'default' {
  if (label === 'pass') return 'success';
  if (label === 'fail') return 'error';
  return 'default';
}

/**
 * Build a hierarchical tree from flat topic list and tests.
 */
function buildTopicTree(topics: Topic[], tests: TestNode[]): TopicTreeNode[] {
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
    testCounts.set(test.topic, (testCounts.get(test.topic) || 0) + 1);
    if (test.model_score !== null && test.model_score !== undefined) {
      scoreSums.set(
        test.topic,
        (scoreSums.get(test.topic) || 0) + test.model_score
      );
      scoreCounts.set(test.topic, (scoreCounts.get(test.topic) || 0) + 1);
    }
  }

  // Update node counts
  for (const [path, node] of nodeMap) {
    node.directTestCount = testCounts.get(path) || 0;
    const sCount = scoreCounts.get(path) || 0;
    node.avgScore = sCount > 0 ? (scoreSums.get(path) || 0) / sCount : null;
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
      node.avgScore !== null ? node.avgScore * node.directTestCount : 0;
    let scoreCount = node.avgScore !== null ? node.directTestCount : 0;

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
  onDropTest?: (testId: string, topicPath: string) => void;
  onEditTopic?: (topicPath: string) => void;
  onDeleteTopic?: (topicPath: string) => void;
}

function TreeNodeView({
  node,
  level,
  selectedTopic,
  onTopicSelect,
  expandedPaths,
  onToggleExpand,
  onDropTest,
  onEditTopic,
  onDeleteTopic,
}: TreeNodeViewProps) {
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedPaths.has(node.path);
  const isSelected = selectedTopic === node.path;
  const [dragOver, setDragOver] = useState(false);

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  };

  const handleDragLeave = (e: DragEvent) => {
    e.stopPropagation();
    setDragOver(false);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const testId = e.dataTransfer.getData('application/test-id');
    if (testId && onDropTest) {
      onDropTest(testId, node.path);
    }
  };

  return (
    <Box>
      <Box
        onClick={() => onTopicSelect(node.path)}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        sx={{
          display: 'flex',
          alignItems: 'center',
          py: 0.75,
          px: 1,
          ml: level * 2,
          cursor: 'pointer',
          borderRadius: 1,
          backgroundColor: dragOver
            ? 'primary.main'
            : isSelected
              ? 'action.selected'
              : 'transparent',
          color: dragOver ? 'primary.contrastText' : 'inherit',
          opacity: dragOver ? 0.9 : 1,
          transition: 'background-color 0.15s ease',
          '&:hover': {
            backgroundColor: dragOver
              ? 'primary.main'
              : isSelected
                ? 'action.selected'
                : 'action.hover',
          },
          '&:hover .topic-edit-btn': {
            opacity: 1,
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
            <FolderOpenIcon fontSize="small" sx={{ color: 'text.secondary' }} />
          ) : (
            <FolderIcon fontSize="small" sx={{ color: 'text.secondary' }} />
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

        {/* Edit Topic Button */}
        {onEditTopic && (
          <IconButton
            size="small"
            onClick={e => {
              e.stopPropagation();
              onEditTopic(node.path);
            }}
            sx={{
              p: 0.25,
              color: 'text.secondary',
              opacity: 0,
              transition: 'opacity 0.15s ease',
              '.MuiBox-root:hover > &': {
                opacity: 1,
              },
            }}
            className="topic-edit-btn"
          >
            <EditIcon sx={{ fontSize: '0.9rem' }} />
          </IconButton>
        )}

        {/* Delete Topic Button */}
        {onDeleteTopic && (
          <Tooltip title="Remove topic">
            <IconButton
              size="small"
              onClick={e => {
                e.stopPropagation();
                onDeleteTopic(node.path);
              }}
              sx={{
                p: 0.25,
                color: 'text.secondary',
                opacity: 0,
                transition: 'opacity 0.15s ease',
                '.MuiBox-root:hover > &': {
                  opacity: 1,
                },
              }}
              className="topic-edit-btn"
            >
              <DeleteIcon sx={{ fontSize: '0.9rem' }} />
            </IconButton>
          </Tooltip>
        )}

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
                onDropTest={onDropTest}
                onEditTopic={onEditTopic}
                onDeleteTopic={onDeleteTopic}
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

  const fullPath = parentTopic ? `${parentTopic}/${topicName}` : topicName;

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
      setError((err as Error).message || 'Failed to create topic');
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
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Add Topic</DialogTitle>
      <DialogContent>
        {parentTopic && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
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
            error || (topicName.trim() ? `Will create: ${fullPath}` : ' ')
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
// Rename Topic Dialog
// ============================================================================

interface RenameTopicDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (topicPath: string, newName: string) => Promise<void>;
  topicPath: string | null;
}

function RenameTopicDialog({
  open,
  onClose,
  onSubmit,
  topicPath,
}: RenameTopicDialogProps) {
  const currentName = topicPath ? topicPath.split('/').pop() || '' : '';
  const [newName, setNewName] = useState(currentName);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleOpen = () => {
    const name = topicPath ? topicPath.split('/').pop() || '' : '';
    setNewName(name);
    setError('');
  };

  const handleSubmit = async () => {
    const trimmed = newName.trim();
    if (!trimmed) {
      setError('Topic name is required');
      return;
    }
    if (trimmed.includes('/')) {
      setError('Topic name cannot contain slashes');
      return;
    }
    if (!topicPath) return;

    setSubmitting(true);
    setError('');
    try {
      await onSubmit(topicPath, trimmed);
      onClose();
    } catch (err) {
      setError((err as Error).message || 'Failed to rename topic');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setError('');
    onClose();
  };

  // Compute preview path
  const parentPath = topicPath?.includes('/')
    ? topicPath.substring(0, topicPath.lastIndexOf('/'))
    : null;
  const previewPath = parentPath
    ? `${parentPath}/${newName.trim()}`
    : newName.trim();

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      TransitionProps={{ onEnter: handleOpen }}
    >
      <DialogTitle>Rename Topic</DialogTitle>
      <DialogContent>
        {topicPath && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Current path: {decodeURIComponent(topicPath)}
          </Typography>
        )}
        <TextField
          autoFocus
          label="New Name"
          fullWidth
          value={newName}
          onChange={e => {
            setNewName(e.target.value);
            setError('');
          }}
          onKeyDown={e => {
            if (e.key === 'Enter' && !submitting) {
              handleSubmit();
            }
          }}
          error={!!error}
          helperText={
            error || (newName.trim() ? `New path: ${previewPath}` : ' ')
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
          disabled={
            submitting || !newName.trim() || newName.trim() === currentName
          }
        >
          {submitting ? 'Renaming...' : 'Rename'}
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
  const [selectedTopic, setSelectedTopic] = useState(topic || '');
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

    setSubmitting(true);
    setError('');
    try {
      await onSubmit({
        ...(selectedTopic.trim() && { topic: selectedTopic.trim() }),
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
      setError((err as Error).message || 'Failed to create test');
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
          label="Topic (optional)"
          fullWidth
          value={selectedTopic}
          onChange={e => {
            setSelectedTopic(e.target.value);
            setError('');
          }}
          disabled={submitting}
          sx={{ mt: 1 }}
          SelectProps={{ native: true }}
          InputLabelProps={{ shrink: true }}
        >
          <option value="">No topic</option>
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
          label="Output (optional)"
          placeholder='Optional. Run "Generate outputs" to fill from the endpoint.'
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
          disabled={submitting || !input.trim()}
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
  onSubmit: (testId: string, data: TestNodeUpdate) => Promise<void>;
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
  const [selectedTopic, setSelectedTopic] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Populate form when dialog opens with a test
  const handleOpen = () => {
    if (test) {
      setInput(test.input || '');
      setOutput(test.output || '');
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
      if (trimmedInput !== (test.input || '')) updates.input = trimmedInput;
      if (output.trim() !== (test.output || '')) updates.output = output.trim();
      if (selectedTopic.trim() && selectedTopic.trim() !== (test.topic || ''))
        updates.topic = selectedTopic.trim();

      await onSubmit(test.id, updates);
      onClose();
    } catch (err) {
      setError((err as Error).message || 'Failed to update test');
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
          InputLabelProps={{ shrink: true }}
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
          label="Output (optional)"
          placeholder='Optional. Run "Generate outputs" to fill from the endpoint.'
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
  onDropTest?: (testId: string, topicPath: string) => void;
  onEditTopic?: (topicPath: string) => void;
  onDeleteTopic?: (topicPath: string) => void;
}

function TopicTreePanel({
  topicTree,
  tests,
  selectedTopic,
  onTopicSelect,
  onAddTopic,
  onDropTest,
  onEditTopic,
  onDeleteTopic,
}: TopicTreePanelProps) {
  // Start with all paths expanded
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(() => {
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
      <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <Typography variant="body2" color="text.secondary" textAlign="center">
          No topics found
        </Typography>
        <Button
          size="small"
          startIcon={<AddIcon />}
          onClick={() => onAddTopic(null)}
          sx={{
            textTransform: 'none',
            color: 'text.secondary',
            justifyContent: 'center',
          }}
        >
          Add topic
        </Button>
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
            selectedTopic === null ? 'action.selected' : 'transparent',
          '&:hover': {
            backgroundColor:
              selectedTopic === null ? 'action.selected' : 'action.hover',
          },
          mb: 1,
        }}
      >
        <Box sx={{ width: 28, flexShrink: 0 }} />
        <FolderIcon fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />
        <Typography
          variant="body2"
          sx={{
            flex: 1,
            fontWeight: selectedTopic === null ? 600 : 400,
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
          onDropTest={onDropTest}
          onEditTopic={onEditTopic}
          onDeleteTopic={onDeleteTopic}
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
  onDeleteTest?: (test: TestNode) => void;
}

function TestsList({
  tests,
  loading,
  onEditTest,
  onDeleteTest,
}: TestsListProps) {
  const gridWrapperRef = useRef<HTMLDivElement>(null);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });

  // Keep DataGrid rows draggable via MutationObserver
  useEffect(() => {
    const container = gridWrapperRef.current;
    if (!container) return;

    const makeRowsDraggable = () => {
      container
        .querySelectorAll('.MuiDataGrid-row:not([draggable])')
        .forEach(row => {
          row.setAttribute('draggable', 'true');
        });
    };

    makeRowsDraggable();

    const observer = new MutationObserver(makeRowsDraggable);
    observer.observe(container, {
      childList: true,
      subtree: true,
    });

    return () => observer.disconnect();
  }, [tests]);

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
        <Tooltip title={params.value || ''} arrow placement="top">
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
        <Tooltip title={params.value || ''} arrow placement="top">
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
        if (score === null || score === undefined || score === 0) {
          return <Chip label="N/A" size="small" variant="outlined" />;
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
    ...(onEditTest || onDeleteTest
      ? [
          {
            field: 'actions',
            headerName: '',
            width: 90,
            sortable: false,
            filterable: false,
            disableColumnMenu: true,
            renderCell: (params: any) => (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                {onEditTest && (
                  <IconButton
                    size="small"
                    onClick={() => onEditTest(params.row)}
                    sx={{ color: 'text.secondary' }}
                  >
                    <EditIcon fontSize="small" />
                  </IconButton>
                )}
                {onDeleteTest && (
                  <IconButton
                    size="small"
                    onClick={() => onDeleteTest(params.row)}
                    sx={{
                      color: 'text.secondary',
                      '&:hover': {
                        color: 'error.main',
                      },
                    }}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
            ),
          } as GridColDef,
        ]
      : []),
  ];

  return (
    <Box>
      {tests.length === 0 ? (
        <Box sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            No tests found
          </Typography>
        </Box>
      ) : (
        <Box
          ref={gridWrapperRef}
          onDragStart={(e: DragEvent<HTMLDivElement>) => {
            const row = (e.target as HTMLElement).closest('[data-id]');
            if (row) {
              const testId = row.getAttribute('data-id') || '';
              e.dataTransfer.setData('application/test-id', testId);
              e.dataTransfer.effectAllowed = 'move';
            }
          }}
        >
          <BaseDataGrid
            columns={columns}
            rows={tests}
            loading={loading}
            getRowId={row => row.id}
            showToolbar={false}
            paginationModel={paginationModel}
            onPaginationModelChange={handlePaginationModelChange}
            serverSidePagination={false}
            totalRows={tests.length}
            pageSizeOptions={[10, 25, 50, 100]}
            disablePaperWrapper={true}
            persistState
            sx={{
              '& .MuiDataGrid-row': {
                cursor: 'grab',
              },
              '& .MuiDataGrid-row:active': {
                cursor: 'grabbing',
              },
            }}
          />
        </Box>
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
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [addTopicDialogOpen, setAddTopicDialogOpen] = useState(false);
  const [addTopicParent, setAddTopicParent] = useState<string | null>(null);
  const [tests, setTests] = useState<TestNode[]>(initialTests);
  const [topics, setTopics] = useState<Topic[]>(initialTopics);
  const [addTestDialogOpen, setAddTestDialogOpen] = useState(false);
  const [editTestDialogOpen, setEditTestDialogOpen] = useState(false);
  const [editingTest, setEditingTest] = useState<TestNode | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingTest, setDeletingTest] = useState<TestNode | null>(null);
  const [renameTopicDialogOpen, setRenameTopicDialogOpen] = useState(false);
  const [renamingTopicPath, setRenamingTopicPath] = useState<string | null>(
    null
  );
  const [deleteTopicConfirmOpen, setDeleteTopicConfirmOpen] = useState(false);
  const [deletingTopicPath, setDeletingTopicPath] = useState<string | null>(
    null
  );
  const [generateOutputsDialogOpen, setGenerateOutputsDialogOpen] =
    useState(false);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [endpointsLoading, setEndpointsLoading] = useState(false);
  const [selectedEndpoint, setSelectedEndpoint] = useState<Endpoint | null>(
    null
  );
  const [generateSubmitting, setGenerateSubmitting] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [generateOutputsTopic, setGenerateOutputsTopic] = useState<
    string | null
  >(null);
  const [generateOutputsIncludeSubtopics, setGenerateOutputsIncludeSubtopics] =
    useState(true);
  const [endpointForGeneration, setEndpointForGeneration] =
    useState<Endpoint | null>(null);
  const [metrics, setMetrics] = useState<MetricDetail[]>([]);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [metricForGeneration, setMetricForGeneration] =
    useState<MetricDetail | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<MetricDetail | null>(
    null
  );

  const notifications = useNotifications();

  // Build the topic tree
  const topicTree = useMemo(
    () => buildTopicTree(topics, tests),
    [topics, tests]
  );

  // Load endpoints on mount for the selector above the table and for the dialog
  useEffect(() => {
    if (!sessionToken) return;
    let cancelled = false;
    setEndpointsLoading(true);
    const clientFactory = new ApiClientFactory(sessionToken);
    const endpointsClient = clientFactory.getEndpointsClient();
    endpointsClient
      .getEndpoints({
        sort_by: 'name',
        sort_order: 'asc',
        limit: 100,
      })
      .then(res => {
        if (cancelled) return;
        const list = res?.data ?? [];
        setEndpoints(Array.isArray(list) ? list : []);
      })
      .catch(() => {
        if (!cancelled) setEndpoints([]);
      })
      .finally(() => {
        if (!cancelled) setEndpointsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  // Load metrics on mount for the metric selector
  useEffect(() => {
    if (!sessionToken) return;
    let cancelled = false;
    setMetricsLoading(true);
    const clientFactory = new ApiClientFactory(sessionToken);
    const metricsClient = clientFactory.getMetricsClient();
    metricsClient
      .getMetrics({
        skip: 0,
        sort_by: 'name',
        sort_order: 'asc',
        limit: 100,
      })
      .then(res => {
        if (cancelled) return;
        const list = res?.data ?? [];
        setMetrics(Array.isArray(list) ? list : []);
      })
      .catch(() => {
        if (!cancelled) setMetrics([]);
      })
      .finally(() => {
        if (!cancelled) setMetricsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  const handleGenerateOutputsOpen = (fromTable?: boolean) => {
    if (fromTable && activeTab === 0 && selectedTopic) {
      setGenerateOutputsTopic(selectedTopic);
      setGenerateOutputsIncludeSubtopics(true);
    } else {
      setGenerateOutputsTopic(null);
      setGenerateOutputsIncludeSubtopics(true);
    }
    setSelectedEndpoint(endpointForGeneration);
    setSelectedMetric(metricForGeneration);
    setGenerateError(null);
    setGenerateOutputsDialogOpen(true);
  };

  const handleGenerateOutputsClose = () => {
    if (!generateSubmitting) {
      setGenerateOutputsDialogOpen(false);
      setSelectedEndpoint(null);
      setSelectedMetric(null);
      setGenerateError(null);
    }
  };

  const handleGenerateOutputsSubmit = async () => {
    if (!selectedEndpoint?.id) {
      setGenerateError('Please select an endpoint.');
      return;
    }
    setGenerateSubmitting(true);
    setGenerateError(null);
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getAdaptiveTestingClient();
    try {
      const result = await client.generateOutputs(testSetId, {
        endpoint_id: selectedEndpoint.id,
        topic: generateOutputsTopic ?? undefined,
        include_subtopics: generateOutputsIncludeSubtopics,
      });
      const [treeNodes, updatedTopics] = await Promise.all([
        client.getTree(testSetId),
        client.getTopics(testSetId),
      ]);
      setTests(treeNodes.filter(node => node.label !== 'topic_marker'));
      setTopics(updatedTopics);
      setGenerateOutputsDialogOpen(false);
      setSelectedEndpoint(null);
      const failedCount = result.failed?.length ?? 0;
      if (failedCount > 0) {
        notifications.show(
          `Generated ${result.generated} outputs; ${failedCount} failed.`,
          { severity: 'warning' }
        );
      } else {
        notifications.show(
          `Generated ${result.generated} output(s) successfully.`,
          { severity: 'success' }
        );
      }
    } catch (err) {
      setGenerateError(
        err instanceof Error ? err.message : 'Failed to generate outputs.'
      );
    } finally {
      setGenerateSubmitting(false);
    }
  };

  const handleAddTopicOpen = (parentTopic: string | null) => {
    setAddTopicParent(parentTopic);
    setAddTopicDialogOpen(true);
  };

  const handleAddTopicSubmit = async (topicPath: string) => {
    // Build optimistic topic object
    const parts = topicPath.split('/');
    const name = parts[parts.length - 1];
    const parentPath = parts.length > 1 ? parts.slice(0, -1).join('/') : null;
    const optimisticTopic: Topic = {
      path: topicPath,
      name,
      parent_path: parentPath,
      depth: parts.length,
      display_name: name,
      display_path: topicPath,
      has_direct_tests: false,
      has_subtopics: false,
    };

    // Optimistically add to local state
    setTopics(prev => [...prev, optimisticTopic]);

    // Fire API call in background (not awaited)
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getAdaptiveTestingClient();

    client.createTopic(testSetId, { path: topicPath }).catch(() => {
      // Rollback: remove the optimistic topic
      setTopics(prev => prev.filter(t => t.path !== topicPath));
      notifications.show('Failed to add topic. Change has been reverted.', {
        severity: 'error',
      });
    });
  };

  const handleAddTestSubmit = async (data: TestNodeCreate) => {
    // Create optimistic test entry with a temporary ID
    const tempId = `temp-${Date.now()}`;
    const optimisticTest: TestNode = {
      id: tempId,
      topic: data.topic || '',
      input: data.input || '',
      output: data.output || '',
      label: data.label || '',
      labeler: data.labeler || 'user',
      to_eval: data.to_eval ?? true,
      model_score: data.model_score ?? 0,
    };

    // Optimistically add to local state
    setTests(prev => [...prev, optimisticTest]);

    // Fire API call in background (not awaited)
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getAdaptiveTestingClient();

    client
      .createTest(testSetId, data)
      .then(async () => {
        // Refresh to get the real test with server ID
        const [treeNodes, updatedTopics] = await Promise.all([
          client.getTree(testSetId),
          client.getTopics(testSetId),
        ]);
        setTests(treeNodes.filter(node => node.label !== 'topic_marker'));
        setTopics(updatedTopics);
      })
      .catch(() => {
        // Rollback: remove the optimistic test
        setTests(prev => prev.filter(t => t.id !== tempId));
        notifications.show('Failed to add test. Change has been reverted.', {
          severity: 'error',
        });
      });
  };

  const handleEditTestOpen = (test: TestNode) => {
    setEditingTest(test);
    setEditTestDialogOpen(true);
  };

  const handleEditTestSubmit = async (testId: string, data: TestNodeUpdate) => {
    // Save previous test state for rollback
    const previousTest = tests.find(t => t.id === testId);
    if (!previousTest) return;

    // Optimistically update local state
    setTests(prev => prev.map(t => (t.id === testId ? { ...t, ...data } : t)));

    // Fire API call in background (not awaited)
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getAdaptiveTestingClient();

    client.updateTest(testSetId, testId, data).catch(() => {
      // Rollback on error
      setTests(prev => prev.map(t => (t.id === testId ? previousTest : t)));
      notifications.show('Failed to update test. Change has been reverted.', {
        severity: 'error',
      });
    });
  };

  const handleDropTestOnTopic = useCallback(
    (testId: string, topicPath: string) => {
      // Find the test to check if topic actually changed
      const test = tests.find(t => t.id === testId);
      if (!test || test.topic === topicPath) return;

      const previousTopic = test.topic;

      // Optimistically update local state
      setTests(prev =>
        prev.map(t => (t.id === testId ? { ...t, topic: topicPath } : t))
      );

      // Fire API call in background
      const clientFactory = new ApiClientFactory(sessionToken);
      const client = clientFactory.getAdaptiveTestingClient();

      client
        .updateTest(testSetId, testId, {
          topic: topicPath,
        })
        .catch(() => {
          // Rollback on error
          setTests(prev =>
            prev.map(t =>
              t.id === testId ? { ...t, topic: previousTopic } : t
            )
          );
          notifications.show('Failed to move test. Change has been reverted.', {
            severity: 'error',
          });
        });
    },
    [tests, sessionToken, testSetId, notifications]
  );

  const handleEditTopicOpen = (topicPath: string) => {
    setRenamingTopicPath(topicPath);
    setRenameTopicDialogOpen(true);
  };

  const handleDeleteTopicOpen = (topicPath: string) => {
    setDeletingTopicPath(topicPath);
    setDeleteTopicConfirmOpen(true);
  };

  const handleDeleteTopicConfirm = () => {
    if (!deletingTopicPath) return;

    const removedTopicPath = deletingTopicPath;
    const previousTopics = topics;
    const previousTests = tests;
    const previousSelectedTopic = selectedTopic;

    // Optimistically remove topic and children from local state
    setTopics(prev =>
      prev.filter(
        t =>
          t.path !== removedTopicPath &&
          !t.path.startsWith(removedTopicPath + '/')
      )
    );

    // Remove tests under the deleted topic
    setTests(prev =>
      prev.filter(
        t =>
          t.topic !== removedTopicPath &&
          !t.topic.startsWith(removedTopicPath + '/')
      )
    );

    if (
      selectedTopic === removedTopicPath ||
      selectedTopic?.startsWith(removedTopicPath + '/')
    ) {
      setSelectedTopic(null);
    }

    setDeleteTopicConfirmOpen(false);
    setDeletingTopicPath(null);

    // Fire API call in background
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getAdaptiveTestingClient();

    client.deleteTopic(testSetId, removedTopicPath).catch(err => {
      // Rollback
      setTopics(previousTopics);
      setTests(previousTests);
      setSelectedTopic(previousSelectedTopic);
      notifications.show(
        err instanceof Error
          ? err.message
          : 'Failed to remove topic. Change has been reverted.',
        { severity: 'error' }
      );
    });
  };

  const handleRenameTopicSubmit = async (
    topicPath: string,
    newName: string
  ) => {
    const parentPath = topicPath.includes('/')
      ? topicPath.substring(0, topicPath.lastIndexOf('/'))
      : null;
    const newPath = parentPath ? `${parentPath}/${newName}` : newName;

    // Save previous state for rollback
    const previousTopics = topics;
    const previousTests = tests;
    const previousSelectedTopic = selectedTopic;

    // Optimistically rename topic and children in local state
    setTopics(prev =>
      prev.map(t => {
        if (t.path === topicPath) {
          return {
            ...t,
            path: newPath,
            name: newName,
            display_name: newName,
            display_path: newPath,
          };
        }
        if (t.path.startsWith(topicPath + '/')) {
          const newChildPath = newPath + t.path.substring(topicPath.length);
          return {
            ...t,
            path: newChildPath,
            parent_path:
              t.parent_path === topicPath
                ? newPath
                : t.parent_path?.startsWith(topicPath + '/')
                  ? newPath + t.parent_path.substring(topicPath.length)
                  : t.parent_path,
            display_path: newChildPath,
          };
        }
        return t;
      })
    );

    // Update test topics that reference the old path
    setTests(prev =>
      prev.map(t => {
        if (t.topic === topicPath) {
          return { ...t, topic: newPath };
        }
        if (t.topic.startsWith(topicPath + '/')) {
          return {
            ...t,
            topic: newPath + t.topic.substring(topicPath.length),
          };
        }
        return t;
      })
    );

    // Update selected topic
    if (selectedTopic) {
      if (selectedTopic === topicPath) {
        setSelectedTopic(newPath);
      } else if (selectedTopic.startsWith(topicPath + '/')) {
        setSelectedTopic(newPath + selectedTopic.substring(topicPath.length));
      }
    }

    // Fire API call in background (not awaited)
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getAdaptiveTestingClient();

    client
      .updateTopic(testSetId, topicPath, {
        new_name: newName,
      })
      .catch(() => {
        // Rollback
        setTopics(previousTopics);
        setTests(previousTests);
        setSelectedTopic(previousSelectedTopic);
        notifications.show(
          'Failed to rename topic. Change has been reverted.',
          { severity: 'error' }
        );
      });
  };

  const handleDeleteTestOpen = (test: TestNode) => {
    setDeletingTest(test);
    setDeleteConfirmOpen(true);
  };

  const handleDeleteTestConfirm = () => {
    if (!deletingTest) return;

    const removedTest = deletingTest;

    // Optimistically remove from local state and close dialog
    setTests(prev => prev.filter(t => t.id !== removedTest.id));
    setDeleteConfirmOpen(false);
    setDeletingTest(null);

    // Fire API call in background
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getAdaptiveTestingClient();

    client.deleteTest(testSetId, removedTest.id).catch(() => {
      // Rollback: re-add the test
      setTests(prev => [...prev, removedTest]);
      notifications.show('Failed to delete test. Change has been reverted.', {
        severity: 'error',
      });
    });
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
  const passCount = tests.filter(t => t.label === 'pass').length;
  const failCount = tests.filter(t => t.label === 'fail').length;

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
        <Paper variant="outlined" sx={{ px: 3, py: 2, minWidth: 120 }}>
          <Typography variant="caption" color="text.secondary">
            Total Tests
          </Typography>
          <Typography variant="h5" fontWeight={600}>
            {totalTests}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ px: 3, py: 2, minWidth: 120 }}>
          <Typography variant="caption" color="text.secondary">
            Topics
          </Typography>
          <Typography variant="h5" fontWeight={600}>
            {totalTopics}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ px: 3, py: 2, minWidth: 120 }}>
          <Typography variant="caption" color="text.secondary">
            Pass
          </Typography>
          <Typography variant="h5" fontWeight={600} color="success.main">
            {passCount}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ px: 3, py: 2, minWidth: 120 }}>
          <Typography variant="caption" color="text.secondary">
            Fail
          </Typography>
          <Typography variant="h5" fontWeight={600} color="error.main">
            {failCount}
          </Typography>
        </Paper>
      </Box>

      {/* Endpoint and Metric for generation - above Tree View / List View */}
      <Box
        sx={{
          display: 'flex',
          gap: 2,
          mb: 2,
          flexWrap: 'wrap',
        }}
      >
        <Autocomplete
          size="small"
          options={endpoints}
          getOptionLabel={option => option.name ?? ''}
          value={endpointForGeneration}
          onChange={(_, value) => setEndpointForGeneration(value ?? null)}
          loading={endpointsLoading}
          renderInput={params => (
            <TextField
              {...params}
              label="Output generation endpoint"
              placeholder="Select endpoint"
              InputProps={{
                ...params.InputProps,
                endAdornment: (
                  <>
                    {endpointsLoading ? (
                      <CircularProgress color="inherit" size={20} />
                    ) : null}
                    {params.InputProps.endAdornment}
                  </>
                ),
              }}
            />
          )}
          sx={{ minWidth: 280, maxWidth: 400 }}
        />
        <Autocomplete
          size="small"
          options={metrics}
          getOptionLabel={option => option.name ?? ''}
          value={metricForGeneration}
          onChange={(_, value) => setMetricForGeneration(value ?? null)}
          loading={metricsLoading}
          renderInput={params => (
            <TextField
              {...params}
              label="Metric"
              placeholder="Select metric"
              InputProps={{
                ...params.InputProps,
                endAdornment: (
                  <>
                    {metricsLoading ? (
                      <CircularProgress color="inherit" size={20} />
                    ) : null}
                    {params.InputProps.endAdornment}
                  </>
                ),
              }}
            />
          )}
          sx={{ minWidth: 280, maxWidth: 400 }}
        />
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
          <Tab icon={<ListIcon />} iconPosition="start" label="List View" />
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
              <Typography variant="subtitle2" fontWeight={600}>
                Topics
              </Typography>
              <Typography variant="caption" color="text.secondary">
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
                onDropTest={handleDropTestOnTopic}
                onEditTopic={handleEditTopicOpen}
                onDeleteTopic={handleDeleteTopicOpen}
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
              <Typography variant="subtitle2" color="text.primary">
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
                {filteredTests.length === 1 ? 'test' : 'tests'})
              </Typography>
              <Button
                size="small"
                startIcon={<PlayArrowIcon />}
                onClick={() => handleGenerateOutputsOpen(true)}
                sx={{ textTransform: 'none' }}
              >
                Generate outputs
              </Button>
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
                onDeleteTest={handleDeleteTestOpen}
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
              gap: 1,
            }}
          >
            <Button
              size="small"
              startIcon={<PlayArrowIcon />}
              onClick={() => handleGenerateOutputsOpen(true)}
              sx={{ textTransform: 'none' }}
            >
              Generate outputs
            </Button>
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
              onDeleteTest={handleDeleteTestOpen}
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

      {/* Rename Topic Dialog */}
      <RenameTopicDialog
        open={renameTopicDialogOpen}
        onClose={() => {
          setRenameTopicDialogOpen(false);
          setRenamingTopicPath(null);
        }}
        onSubmit={handleRenameTopicSubmit}
        topicPath={renamingTopicPath}
      />

      {/* Delete Test Confirmation Dialog */}
      <Dialog
        open={deleteConfirmOpen}
        onClose={() => {
          setDeleteConfirmOpen(false);
          setDeletingTest(null);
        }}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Delete Test</DialogTitle>
        <DialogContent>
          <Typography>Are you sure you want to delete this test?</Typography>
          {deletingTest && (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                mt: 1,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {deletingTest.input}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setDeleteConfirmOpen(false);
              setDeletingTest(null);
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={handleDeleteTestConfirm}
            color="error"
            variant="contained"
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Topic Confirmation Dialog */}
      <Dialog
        open={deleteTopicConfirmOpen}
        onClose={() => {
          setDeleteTopicConfirmOpen(false);
          setDeletingTopicPath(null);
        }}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Remove Topic</DialogTitle>
        <DialogContent>
          <Typography>
            Remove this topic? Subtopics will be removed and all tests under
            this topic will be moved to the parent topic.
          </Typography>
          {deletingTopicPath && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {decodeURIComponent(deletingTopicPath)}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setDeleteTopicConfirmOpen(false);
              setDeletingTopicPath(null);
            }}
          >
            Cancel
          </Button>
          <Button
            onClick={handleDeleteTopicConfirm}
            color="error"
            variant="contained"
          >
            Remove
          </Button>
        </DialogActions>
      </Dialog>

      {/* Generate outputs dialog */}
      <Dialog
        open={generateOutputsDialogOpen}
        onClose={handleGenerateOutputsClose}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Generate outputs</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Invoke the selected endpoint for each test input and store the
            response as the test output.
          </Typography>
          {generateError && (
            <Alert
              severity="error"
              sx={{ mb: 2 }}
              onClose={() => setGenerateError(null)}
            >
              {generateError}
            </Alert>
          )}
          <Box
            sx={{
              display: 'flex',
              gap: 2,
              mb: 2,
              flexWrap: 'wrap',
            }}
          >
            <Autocomplete
              options={endpoints}
              getOptionLabel={option => option.name ?? ''}
              value={selectedEndpoint}
              onChange={(_, value) => setSelectedEndpoint(value ?? null)}
              loading={endpointsLoading}
              renderInput={params => (
                <TextField
                  {...params}
                  label="Endpoint"
                  placeholder="Select endpoint"
                  InputProps={{
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {endpointsLoading ? (
                          <CircularProgress color="inherit" size={20} />
                        ) : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
              sx={{ minWidth: 240, flex: 1 }}
            />
            <Autocomplete
              options={metrics}
              getOptionLabel={option => option.name ?? ''}
              value={selectedMetric}
              onChange={(_, value) => setSelectedMetric(value ?? null)}
              loading={metricsLoading}
              renderInput={params => (
                <TextField
                  {...params}
                  label="Metric"
                  placeholder="Select metric"
                  InputProps={{
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {metricsLoading ? (
                          <CircularProgress color="inherit" size={20} />
                        ) : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
              sx={{ minWidth: 240, flex: 1 }}
            />
          </Box>
          <Autocomplete
            options={[allTestsTopicOption, ...topics]}
            getOptionLabel={option =>
              option.path ? (option.display_path ?? option.path) : 'All tests'
            }
            value={
              generateOutputsTopic === null || generateOutputsTopic === ''
                ? allTestsTopicOption
                : (topics.find(t => t.path === generateOutputsTopic) ?? {
                    path: generateOutputsTopic,
                    name:
                      generateOutputsTopic.split('/').pop() ??
                      generateOutputsTopic,
                    parent_path: null,
                    depth: 0,
                    display_name: generateOutputsTopic,
                    display_path: generateOutputsTopic,
                    has_direct_tests: false,
                    has_subtopics: false,
                  })
            }
            onChange={(_, value) =>
              setGenerateOutputsTopic(
                value?.path && value.path !== '' ? value.path : null
              )
            }
            isOptionEqualToValue={(a, b) => a.path === b.path}
            renderInput={params => (
              <TextField {...params} label="Topic" placeholder="All tests" />
            )}
            sx={{ mb: 1 }}
          />
          {generateOutputsTopic != null && generateOutputsTopic !== '' && (
            <FormControlLabel
              control={
                <Checkbox
                  checked={generateOutputsIncludeSubtopics}
                  onChange={e =>
                    setGenerateOutputsIncludeSubtopics(e.target.checked)
                  }
                />
              }
              label="Include subtopics"
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={handleGenerateOutputsClose}
            disabled={generateSubmitting}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleGenerateOutputsSubmit}
            disabled={!selectedEndpoint || generateSubmitting}
            startIcon={
              generateSubmitting ? (
                <CircularProgress size={16} color="inherit" />
              ) : (
                <PlayArrowIcon />
              )
            }
          >
            {generateSubmitting ? 'Generating…' : 'Generate'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
