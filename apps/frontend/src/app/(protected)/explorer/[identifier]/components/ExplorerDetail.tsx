'use client';

import type { UUID } from 'crypto';
import React, {
  useState,
  useMemo,
  useCallback,
  useEffect,
  useRef,
  useContext,
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
  Stack,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/SettingsOutlined';
import IosShareOutlinedIcon from '@mui/icons-material/IosShareOutlined';
import ApiOutlinedIcon from '@mui/icons-material/ApiOutlined';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import { alpha, useTheme } from '@mui/material/styles';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import {
  GridColDef,
  GridPaginationModel,
  GridRenderCellParams,
  GridRowSelectionModel,
} from '@mui/x-data-grid';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { GridToolbar as AppGridToolbar } from '@/components/common/GridToolbar';
import BaseDrawer from '@/components/common/BaseDrawer';
import { EntityInfoBanner } from '@/components/common/EntityInfoBanner';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabGroup } from '@/components/common/Fab';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import FolderIcon from '@mui/icons-material/Folder';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import ListIcon from '@mui/icons-material/List';
import AddIcon from '@mui/icons-material/AddOutlined';
import CheckIcon from '@mui/icons-material/CheckOutlined';
import EditIcon from '@mui/icons-material/EditOutlined';
import DeleteIcon from '@mui/icons-material/DeleteOutlined';
import PlayArrowIcon from '@mui/icons-material/PlayArrowOutlined';
import GradingIcon from '@mui/icons-material/GradingOutlined';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesomeOutlined';
import OpenInNewOutlinedIcon from '@mui/icons-material/OpenInNewOutlined';
import { MetricDetailView } from '@/app/(protected)/metrics/[identifier]/MetricDetailView';
import {
  TestNode,
  TestNodeCreate,
  TestNodeUpdate,
  Topic,
} from '@/utils/api-client/interfaces/explorer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import type { MetricDetail } from '@/utils/api-client/interfaces/metric';
import SuggestionsDialog from './SuggestionsDialog';
import { ScoreMetricsTooltip } from './scoreMetricsTooltip';
import { METRIC_SCOPES } from '@/constants/metric-scopes';

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

interface ExplorerDetailProps {
  tests: TestNode[];
  topics: Topic[];
  testSetName: string;
  testSetId: string;
  sessionToken: string;
}

const NO_TOPIC_FILTER = '__NO_TOPIC__';

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
 * Matches /metrics/[identifier] — only rhesis and custom backend types have a
 * configuration detail page; other types redirect away.
 */
function metricSupportsDetailPage(metric: {
  backend_type?: { type_value?: string | null } | null;
}): boolean {
  const v = metric.backend_type?.type_value?.toLowerCase();
  return v === 'rhesis' || v === 'custom';
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
      const parent = nodeMap.get(parentPath);
      if (!parent) continue;
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
  const theme = useTheme();
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
          borderRadius: theme.shape.borderRadius / 4,
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
            <EditIcon sx={{ fontSize: theme.typography.subtitle2.fontSize }} />
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
              <DeleteIcon
                sx={{ fontSize: theme.typography.subtitle2.fontSize }}
              />
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
            fontSize: theme.typography.overline.fontSize,
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
              fontSize: theme.typography.chartTick.fontSize,
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
              fontSize: theme.typography.overline.fontSize,
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
          placeholder='Optional. Run "Get outputs" to fill from the endpoint.'
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
          placeholder='Optional. Run "Get outputs" to fill from the endpoint.'
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
// Test Detail Drawer (view + edit)
// ============================================================================

interface TestDetailDrawerProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (testId: string, data: TestNodeUpdate) => Promise<void>;
  test: TestNode | null;
  topics: Topic[];
}

function TestDetailDrawer({
  open,
  onClose,
  onSubmit,
  test,
  topics,
}: TestDetailDrawerProps) {
  const [input, setInput] = useState('');
  const [output, setOutput] = useState('');
  const [selectedTopic, setSelectedTopic] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open && test) {
      setInput(test.input || '');
      setOutput(test.output || '');
      setSelectedTopic(test.topic || '');
      setError('');
    }
  }, [open, test]);

  const handleSave = async () => {
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
      if (selectedTopic.trim() !== (test.topic || ''))
        updates.topic = selectedTopic.trim();
      await onSubmit(test.id, updates);
      onClose();
    } catch (err) {
      setError((err as Error).message || 'Failed to update test');
    } finally {
      setSubmitting(false);
    }
  };

  const score = test?.model_score;
  const label = test?.label;

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Test details"
      onSave={handleSave}
      saveButtonText="Save changes"
      saveDisabled={!input.trim()}
      loading={submitting}
      error={error || undefined}
      anchor="right"
    >
      {/* Score badge */}
      {(label === 'pass' || label === 'fail') && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: -3 }}>
          <Chip
            label={score != null ? score.toFixed(2) : 'N/A'}
            size="small"
            color={getLabelColor(label)}
            variant={score != null ? 'filled' : 'outlined'}
          />
          {test?.metrics && (
            <ScoreMetricsTooltip metrics={test.metrics}>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ cursor: 'help', textDecoration: 'underline dotted' }}
              >
                Score details
              </Typography>
            </ScoreMetricsTooltip>
          )}
        </Box>
      )}

      {/* Topic */}
      <TextField
        select
        label="Topic"
        fullWidth
        value={selectedTopic}
        onChange={e => setSelectedTopic(e.target.value)}
        disabled={submitting}
        SelectProps={{ native: true }}
        InputLabelProps={{ shrink: true }}
      >
        <option value="">Select a topic…</option>
        {topics.map(t => (
          <option key={t.path} value={t.path}>
            {t.path}
          </option>
        ))}
      </TextField>

      {/* Input */}
      <TextField
        label="Input"
        fullWidth
        multiline
        minRows={3}
        maxRows={8}
        value={input}
        onChange={e => {
          setInput(e.target.value);
          setError('');
        }}
        disabled={submitting}
      />

      {/* Output */}
      <TextField
        label="Output"
        placeholder='Optional. Run "Get outputs" to fill from the endpoint.'
        fullWidth
        multiline
        minRows={3}
        maxRows={8}
        value={output}
        onChange={e => setOutput(e.target.value)}
        disabled={submitting}
      />
    </BaseDrawer>
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
  const theme = useTheme();
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
          borderRadius: theme.shape.borderRadius / 4,
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
          sx={{
            height: 20,
            fontSize: theme.typography.overline.fontSize,
          }}
        />
      </Box>

      {/* Tests Without Topic option */}
      <Box
        onClick={() => onTopicSelect(NO_TOPIC_FILTER)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          py: 0.75,
          px: 1,
          cursor: 'pointer',
          borderRadius: theme.shape.borderRadius / 4,
          backgroundColor:
            selectedTopic === NO_TOPIC_FILTER
              ? 'action.selected'
              : 'transparent',
          '&:hover': {
            backgroundColor:
              selectedTopic === NO_TOPIC_FILTER
                ? 'action.selected'
                : 'action.hover',
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
            fontWeight: selectedTopic === NO_TOPIC_FILTER ? 600 : 400,
          }}
        >
          Tests without topic
        </Typography>
        <Chip
          label={tests.filter(t => !t.topic).length}
          size="small"
          variant="outlined"
          sx={{
            height: 20,
            fontSize: theme.typography.overline.fontSize,
          }}
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
// Tests List (DataGrid) + Toolbar
// ============================================================================

interface TestsListToolbarState {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  onGetOutputs: () => void;
  onEvaluate: () => void;
  onAddTest: () => void;
  onSuggest: () => void;
  selectedRowCount: number;
  onBulkDelete: () => void;
  generateSubmitting: boolean;
  evaluateSubmitting: boolean;
}

const TestsListToolbarContext = React.createContext<TestsListToolbarState>({
  searchQuery: '',
  setSearchQuery: () => {},
  onGetOutputs: () => {},
  onEvaluate: () => {},
  onAddTest: () => {},
  onSuggest: () => {},
  selectedRowCount: 0,
  onBulkDelete: () => {},
  generateSubmitting: false,
  evaluateSubmitting: false,
});

function TestsListUnifiedToolbar() {
  const {
    searchQuery,
    setSearchQuery,
    onGetOutputs,
    onEvaluate,
    onAddTest,
    onSuggest,
    selectedRowCount,
    onBulkDelete,
    generateSubmitting,
    evaluateSubmitting,
  } = useContext(TestsListToolbarContext);

  return (
    <AppGridToolbar
      searchQuery={searchQuery}
      onSearchChange={setSearchQuery}
      searchPlaceholder="Search tests…"
      rightContent={
        <>
          {selectedRowCount > 0 && (
            <Tooltip title={`Delete ${selectedRowCount} selected`}>
              <span>
                <IconButton size="small" color="error" onClick={onBulkDelete}>
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          )}
          <Tooltip title="Get outputs">
            <span>
              <IconButton
                size="small"
                onClick={onGetOutputs}
                disabled={generateSubmitting || evaluateSubmitting}
              >
                <PlayArrowIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Evaluate">
            <span>
              <IconButton
                size="small"
                onClick={onEvaluate}
                disabled={generateSubmitting || evaluateSubmitting}
              >
                <GradingIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Add test">
            <span>
              <IconButton size="small" onClick={onAddTest}>
                <AddIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Suggest tests">
            <span>
              <IconButton size="small" onClick={onSuggest}>
                <AutoAwesomeIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </>
      }
    />
  );
}

interface TestsListProps {
  tests: TestNode[];
  loading: boolean;
  onEditTest?: (test: TestNode) => void;
  onDeleteTest?: (test: TestNode) => void;
  onRowClick?: (test: TestNode) => void;
  checkboxSelection?: boolean;
  rowSelectionModel?: GridRowSelectionModel;
  onRowSelectionModelChange?: (model: GridRowSelectionModel) => void;
  newTestInput?: string;
  onNewTestInputChange?: (value: string) => void;
  onNewTestSubmit?: (input: string) => void;
  newTestProcessing?: boolean;
  pendingTestIds?: Set<string>;
  onGetOutputs?: () => void;
  onEvaluate?: () => void;
  onAddTest?: () => void;
  onSuggest?: () => void;
  onBulkDelete?: () => void;
  generateSubmitting?: boolean;
  evaluateSubmitting?: boolean;
}

function TestsList({
  tests,
  loading,
  onEditTest,
  onDeleteTest,
  onRowClick,
  checkboxSelection,
  rowSelectionModel,
  onRowSelectionModelChange,
  newTestInput,
  onNewTestInputChange,
  onNewTestSubmit,
  newTestProcessing = false,
  pendingTestIds = new Set<string>(),
  onGetOutputs,
  onEvaluate,
  onAddTest,
  onSuggest,
  onBulkDelete,
  generateSubmitting = false,
  evaluateSubmitting = false,
}: TestsListProps) {
  const gridWrapperRef = useRef<HTMLDivElement>(null);
  const [paginationModel, setPaginationModel] = useState({
    page: 0,
    pageSize: 25,
  });
  const [searchQuery, setSearchQuery] = useState('');

  const filteredTests = useMemo(() => {
    if (!searchQuery.trim()) return tests;
    const q = searchQuery.toLowerCase();
    return tests.filter(
      t =>
        t.input?.toLowerCase().includes(q) ||
        t.output?.toLowerCase().includes(q) ||
        t.topic?.toLowerCase().includes(q)
    );
  }, [tests, searchQuery]);

  const hasToolbar = !!(onGetOutputs || onEvaluate || onAddTest || onSuggest);

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
            {(params.value ?? '-') || '-'}
          </Typography>
        </Tooltip>
      ),
    },
    {
      field: 'output',
      headerName: 'Output',
      flex: 2,
      minWidth: 200,
      renderCell: params => {
        if (params.row.id && pendingTestIds.has(params.row.id)) {
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CircularProgress size={16} />
              <Typography variant="body2" color="text.secondary">
                Generating...
              </Typography>
            </Box>
          );
        }
        return (
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
        );
      },
    },
    {
      field: 'model_score',
      headerName: 'Score',
      width: 100,
      align: 'center',
      headerAlign: 'center',
      renderCell: params => {
        if (params.row.id && pendingTestIds.has(params.row.id)) {
          return <CircularProgress size={16} />;
        }
        const row = params.row as TestNode;
        const label = row.label;
        const score = params.value;
        if (!label) {
          return <Chip label="N/A" size="small" variant="outlined" />;
        }
        return (
          <ScoreMetricsTooltip metrics={row.metrics}>
            <Chip
              label={score != null ? score.toFixed(2) : 'N/A'}
              size="small"
              color={getLabelColor(label)}
              variant={score != null ? 'filled' : 'outlined'}
            />
          </ScoreMetricsTooltip>
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
            renderCell: (params: GridRenderCellParams) => (
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

  const selectedRowCount = rowSelectionModel?.length ?? 0;

  return (
    <TestsListToolbarContext.Provider
      value={{
        searchQuery,
        setSearchQuery,
        onGetOutputs: onGetOutputs ?? (() => {}),
        onEvaluate: onEvaluate ?? (() => {}),
        onAddTest: onAddTest ?? (() => {}),
        onSuggest: onSuggest ?? (() => {}),
        selectedRowCount,
        onBulkDelete: onBulkDelete ?? (() => {}),
        generateSubmitting,
        evaluateSubmitting,
      }}
    >
      <Box>
        {onNewTestSubmit && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <TextField
              size="small"
              fullWidth
              placeholder="Type test input and press Enter"
              value={newTestInput ?? ''}
              onChange={e => onNewTestInputChange?.(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  const value = (newTestInput ?? '').trim();
                  if (value) {
                    onNewTestSubmit(value);
                  }
                }
              }}
              disabled={newTestProcessing}
            />
            <Tooltip title="Add test">
              <span>
                <IconButton
                  color="primary"
                  onClick={() => {
                    const value = (newTestInput ?? '').trim();
                    if (value) {
                      onNewTestSubmit(value);
                    }
                  }}
                  disabled={newTestProcessing || !(newTestInput ?? '').trim()}
                >
                  {newTestProcessing ? (
                    <CircularProgress size={18} />
                  ) : (
                    <CheckIcon fontSize="small" />
                  )}
                </IconButton>
              </span>
            </Tooltip>
          </Box>
        )}
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
            rows={filteredTests}
            loading={loading}
            getRowId={row => row.id}
            showToolbar={hasToolbar}
            toolbarSlot={hasToolbar ? TestsListUnifiedToolbar : undefined}
            paginationModel={paginationModel}
            onPaginationModelChange={handlePaginationModelChange}
            serverSidePagination={false}
            totalRows={filteredTests.length}
            pageSizeOptions={[10, 25, 50, 100]}
            disablePaperWrapper={true}
            persistState
            checkboxSelection={checkboxSelection}
            disableRowSelectionOnClick={checkboxSelection ? true : undefined}
            rowSelectionModel={rowSelectionModel}
            onRowSelectionModelChange={onRowSelectionModelChange}
            onRowClick={
              onRowClick
                ? params => onRowClick(params.row as TestNode)
                : undefined
            }
            sx={{
              '& .MuiDataGrid-row': {
                cursor: onRowClick ? 'pointer' : 'grab',
              },
              '& .MuiDataGrid-row:active': {
                cursor: onRowClick ? 'pointer' : 'grabbing',
              },
            }}
          />
        </Box>
      </Box>
    </TestsListToolbarContext.Provider>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function ExplorerDetail({
  tests: initialTests,
  topics: initialTopics,
  testSetName,
  testSetId,
  sessionToken,
}: ExplorerDetailProps) {
  type EndpointOption = {
    endpointId: string;
    endpointName: string;
    projectId: string;
    projectName: string;
    environment: Endpoint['environment'];
  };

  const formatEnvironment = (env: Endpoint['environment']) =>
    env.charAt(0).toUpperCase() + env.slice(1);

  const getEnvironmentColor = (env: Endpoint['environment']) => {
    switch (env.toLowerCase()) {
      case 'production':
        return 'error.main';
      case 'staging':
        return 'warning.main';
      case 'development':
        return 'info.main';
      default:
        return 'text.secondary';
    }
  };

  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [selectedRows, setSelectedRows] = useState<GridRowSelectionModel>([]);
  const [activeTab, setActiveTab] = useState(0);
  const [addTopicDialogOpen, setAddTopicDialogOpen] = useState(false);
  const [addTopicParent, setAddTopicParent] = useState<string | null>(null);
  const [tests, setTests] = useState<TestNode[]>(initialTests);
  const [topics, setTopics] = useState<Topic[]>(initialTopics);
  const [newTestInput, setNewTestInput] = useState('');
  const [newTestProcessing, setNewTestProcessing] = useState(false);
  const [pendingTestIds, setPendingTestIds] = useState<Set<string>>(new Set());
  const [addTestDialogOpen, setAddTestDialogOpen] = useState(false);
  const [editTestDialogOpen, setEditTestDialogOpen] = useState(false);
  const [editingTest, setEditingTest] = useState<TestNode | null>(null);
  const [testDetailDrawerOpen, setTestDetailDrawerOpen] = useState(false);
  const [testDetailDrawerTest, setTestDetailDrawerTest] =
    useState<TestNode | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingTest, setDeletingTest] = useState<TestNode | null>(null);
  const [bulkDeleteConfirmOpen, setBulkDeleteConfirmOpen] = useState(false);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
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
  const [endpointOptions, setEndpointOptions] = useState<EndpointOption[]>([]);
  const [endpointsLoading, setEndpointsLoading] = useState(false);
  const [generateSubmitting, setGenerateSubmitting] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [generateOutputsTopic, setGenerateOutputsTopic] = useState<
    string | null
  >(null);
  const [generateOutputsIncludeSubtopics, setGenerateOutputsIncludeSubtopics] =
    useState(true);
  const [metrics, setMetrics] = useState<MetricDetail[]>([]);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [evaluateDialogOpen, setEvaluateDialogOpen] = useState(false);
  const [evaluateSubmitting, setEvaluateSubmitting] = useState(false);
  const [evaluateError, setEvaluateError] = useState<string | null>(null);
  const [evaluateTopic, setEvaluateTopic] = useState<string | null>(null);
  const [evaluateIncludeSubtopics, setEvaluateIncludeSubtopics] =
    useState(true);

  const [suggestionsDialogOpen, setSuggestionsDialogOpen] = useState(false);
  const [suggestionGuidanceDialogOpen, setSuggestionGuidanceDialogOpen] =
    useState(false);
  const [suggestionGuidanceDraft, setSuggestionGuidanceDraft] = useState('');
  /** choose: pick Generate vs Specify guide; guide: optional text field shown */
  const [suggestionGuidanceStep, setSuggestionGuidanceStep] = useState<
    'choose' | 'guide'
  >('choose');
  const [suggestionsUserFeedback, setSuggestionsUserFeedback] = useState<
    string | null
  >(null);
  const [settingsDialogOpen, setSettingsDialogOpen] = useState(false);
  /** True when dialog opened from Edit settings (not initial ?openSettings=1). */
  const [settingsReEvaluateWarning, setSettingsReEvaluateWarning] =
    useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [settingsEndpoint, setSettingsEndpoint] =
    useState<EndpointOption | null>(null);
  const [settingsMetric, setSettingsMetric] = useState<MetricDetail | null>(
    null
  );
  /** Resolved labels for on-page display; null means initial load not finished */
  const [explorerConfigSummary, setExplorerConfigSummary] = useState<{
    endpointLabel: string | null;
    endpointEnvironment: Endpoint['environment'] | null;
    metrics: { id: string; name: string; hasDetailPage: boolean }[];
  } | null>(null);
  const [metricEditorMetricId, setMetricEditorMetricId] = useState<
    string | null
  >(null);
  const [exportSubmitting, setExportSubmitting] = useState(false);

  const theme = useTheme();
  const notifications = useNotifications();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const selectedTopicForApi =
    selectedTopic && selectedTopic !== NO_TOPIC_FILTER ? selectedTopic : null;

  const handleTopicSelect = useCallback((topic: string | null) => {
    setSelectedTopic(topic);
    setSelectedRows([]);
  }, []);

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
    const projectsClient = clientFactory.getProjectsClient();
    const endpointsClient = clientFactory.getEndpointsClient();
    Promise.all([
      projectsClient.getProjects({ limit: 100 }),
      endpointsClient.getEndpoints({ limit: 100 }),
    ])
      .then(([projectsResponse, endpointsResponse]) => {
        if (cancelled) return;

        const projects = Array.isArray(projectsResponse)
          ? projectsResponse
          : projectsResponse?.data || [];

        const endpoints = Array.isArray(endpointsResponse)
          ? endpointsResponse
          : endpointsResponse?.data || [];

        const projectMap = new Map<string, { name?: string }>();
        projects.forEach((project: { id: string; name?: string }) => {
          projectMap.set(project.id.toString(), project);
        });

        const options: EndpointOption[] = endpoints
          .filter(
            (
              endpoint: Endpoint
            ): endpoint is Endpoint & { project_id: string } =>
              !!endpoint.project_id
          )
          .map(endpoint => {
            const project = projectMap.get(endpoint.project_id ?? '');
            return {
              endpointId: endpoint.id,
              endpointName: endpoint.name,
              projectId: endpoint.project_id ?? '',
              projectName: project?.name || 'Unknown Project',
              environment: endpoint.environment,
            };
          })
          .sort((a, b) => {
            const projectCompare = a.projectName.localeCompare(b.projectName);
            if (projectCompare !== 0) return projectCompare;
            return a.endpointName.localeCompare(b.endpointName);
          });

        setEndpointOptions(options);
      })
      .catch(() => {
        if (!cancelled) setEndpointOptions([]);
      })
      .finally(() => {
        if (!cancelled) setEndpointsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  const loadExplorerSettings = useCallback(async () => {
    const clientFactory = new ApiClientFactory(sessionToken);
    const explorerClient = clientFactory.getExplorerClient();
    const metricsClient = clientFactory.getMetricsClient();
    try {
      const settings = await explorerClient.getExplorerSettings(testSetId);
      const resolvedEndpoint =
        endpointOptions.find(
          e => e.endpointId === settings.default_endpoint?.id
        ) ?? null;
      setSettingsEndpoint(resolvedEndpoint);
      const endpointLabel = resolvedEndpoint
        ? `${resolvedEndpoint.projectName} › ${resolvedEndpoint.endpointName}`
        : (settings.default_endpoint?.name ?? null);
      const endpointEnvironment = resolvedEndpoint?.environment ?? null;

      const metricsSummary = await Promise.all(
        settings.metrics.map(async m => {
          const full = metrics.find(mm => mm.id === m.id);
          const name = full?.name ?? m.name;
          if (full) {
            return {
              id: m.id,
              name,
              hasDetailPage: metricSupportsDetailPage(full),
            };
          }
          try {
            const detail = await metricsClient.getMetric(m.id as UUID);
            return {
              id: m.id,
              name,
              hasDetailPage: metricSupportsDetailPage(detail),
            };
          } catch {
            return { id: m.id, name, hasDetailPage: false };
          }
        })
      );
      setExplorerConfigSummary({
        endpointLabel,
        endpointEnvironment,
        metrics: metricsSummary,
      });

      const firstMetricId = settings.metrics[0]?.id;
      setSettingsMetric(
        firstMetricId
          ? (metrics.find(metric => metric.id === firstMetricId) ?? null)
          : null
      );
    } catch {
      setExplorerConfigSummary({
        endpointLabel: null,
        endpointEnvironment: null,
        metrics: [],
      });
    }
  }, [endpointOptions, metrics, sessionToken, testSetId]);

  useEffect(() => {
    if (endpointOptions.length === 0 && metrics.length === 0) return;
    void loadExplorerSettings();
  }, [endpointOptions, metrics, loadExplorerSettings]);

  useEffect(() => {
    if (searchParams.get('openSettings') !== '1') return;
    setSettingsReEvaluateWarning(false);
    setSettingsDialogOpen(true);
    const next = new URLSearchParams(searchParams.toString());
    next.delete('openSettings');
    router.replace(
      next.toString() ? `${pathname}?${next.toString()}` : pathname,
      {
        scroll: false,
      }
    );
  }, [pathname, router, searchParams]);

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
        const metricsList = Array.isArray(list) ? list : [];
        const singleTurnMetrics = metricsList.filter(metric => {
          if (!metric.metric_scope || metric.metric_scope.length === 0)
            return true;
          return metric.metric_scope.some(
            scope =>
              scope.toLowerCase() === METRIC_SCOPES.SINGLE_TURN.toLowerCase()
          );
        });
        setMetrics(singleTurnMetrics);
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

  const handleGenerateOutputsClose = () => {
    if (!generateSubmitting) {
      setGenerateOutputsDialogOpen(false);
      setGenerateError(null);
    }
  };

  const handleGenerateOutputsSubmit = async (options?: {
    topic: string | null;
    includeSubtopics: boolean;
    closeDialog?: boolean;
  }) => {
    setGenerateSubmitting(true);
    setGenerateError(null);
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getExplorerClient();
    const effectiveTopic = options?.topic ?? generateOutputsTopic;
    const effectiveIncludeSubtopics =
      options?.includeSubtopics ?? generateOutputsIncludeSubtopics;
    try {
      const result = await client.generateOutputs(testSetId, {
        topic: effectiveTopic ?? undefined,
        include_subtopics: effectiveIncludeSubtopics,
        overwrite: true,
      });
      const [treeNodes, updatedTopics] = await Promise.all([
        client.getTree(testSetId),
        client.getTopics(testSetId),
      ]);
      setTests(treeNodes.filter(node => node.label !== 'topic_marker'));
      setTopics(updatedTopics);
      if (options?.closeDialog ?? generateOutputsDialogOpen) {
        setGenerateOutputsDialogOpen(false);
      }
      const failedCount = result.failed?.length ?? 0;
      if (failedCount > 0) {
        notifications.show(
          `Got ${result.generated} outputs${result.skipped > 0 ? ` (${result.skipped} skipped)` : ''}; ${failedCount} failed.`,
          { severity: 'warning' }
        );
      } else {
        notifications.show(
          `Got ${result.generated} output(s) successfully${result.skipped > 0 ? ` (${result.skipped} skipped)` : ''}.`,
          { severity: 'success' }
        );
      }
    } catch (err) {
      setGenerateError(
        err instanceof Error ? err.message : 'Failed to get outputs.'
      );
    } finally {
      setGenerateSubmitting(false);
    }
  };

  const handleGenerateOutputsInline = (fromTable?: boolean) => {
    const topic =
      fromTable && activeTab === 0 && selectedTopicForApi
        ? selectedTopicForApi
        : null;
    void handleGenerateOutputsSubmit({
      topic,
      includeSubtopics: true,
      closeDialog: false,
    });
  };

  const handleEvaluateClose = () => {
    if (!evaluateSubmitting) {
      setEvaluateDialogOpen(false);
      setEvaluateError(null);
    }
  };

  const handleEvaluateSubmit = async (options?: {
    topic: string | null;
    includeSubtopics: boolean;
    closeDialog?: boolean;
  }) => {
    setEvaluateSubmitting(true);
    setEvaluateError(null);
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getExplorerClient();
    const effectiveTopic = options?.topic ?? evaluateTopic;
    const effectiveIncludeSubtopics =
      options?.includeSubtopics ?? evaluateIncludeSubtopics;
    try {
      const result = await client.evaluate(testSetId, {
        topic: effectiveTopic ?? undefined,
        include_subtopics: effectiveIncludeSubtopics,
        overwrite: true,
      });
      const [treeNodes, updatedTopics] = await Promise.all([
        client.getTree(testSetId),
        client.getTopics(testSetId),
      ]);
      setTests(treeNodes.filter(node => node.label !== 'topic_marker'));
      setTopics(updatedTopics);
      if (options?.closeDialog ?? evaluateDialogOpen) {
        setEvaluateDialogOpen(false);
      }
      const failedCount = result.failed?.length ?? 0;
      if (failedCount > 0) {
        notifications.show(
          `Evaluated ${result.evaluated} tests${result.skipped > 0 ? ` (${result.skipped} skipped)` : ''}; ${failedCount} failed.`,
          { severity: 'warning' }
        );
      } else {
        notifications.show(
          `Evaluated ${result.evaluated} test(s) successfully${result.skipped > 0 ? ` (${result.skipped} skipped)` : ''}.`,
          { severity: 'success' }
        );
      }
    } catch (err) {
      setEvaluateError(
        err instanceof Error ? err.message : 'Failed to evaluate tests.'
      );
    } finally {
      setEvaluateSubmitting(false);
    }
  };

  const handleEvaluateInline = (fromTable?: boolean) => {
    const topic =
      fromTable && activeTab === 0 && selectedTopicForApi
        ? selectedTopicForApi
        : null;
    void handleEvaluateSubmit({
      topic,
      includeSubtopics: true,
      closeDialog: false,
    });
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
    const client = clientFactory.getExplorerClient();

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
    setPendingTestIds(prev => {
      const next = new Set(prev);
      next.add(tempId);
      return next;
    });

    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getExplorerClient();

    try {
      const created = await client.createTest(testSetId, {
        ...data,
        // Embeddings are generated when accepting tests from suggestion flow only.
        // Persisting embeddings for manually added tests is not implemented yet.
        generate_embedding: false,
      });
      setTests(prev => prev.map(test => (test.id === tempId ? created : test)));
      setPendingTestIds(prev => {
        const next = new Set(prev);
        next.delete(tempId);
        next.add(created.id);
        return next;
      });

      const outputProvided = Boolean(data.output && data.output.trim());
      if (!outputProvided) {
        await client.generateOutputs(testSetId, {
          test_ids: [created.id],
          overwrite: true,
        });
      }

      await client.evaluate(testSetId, {
        test_ids: [created.id],
        overwrite: true,
      });

      // Refresh to pick up outputs + evaluation
      const [treeNodes, updatedTopics] = await Promise.all([
        client.getTree(testSetId),
        client.getTopics(testSetId),
      ]);
      setTests(treeNodes.filter(node => node.label !== 'topic_marker'));
      setTopics(updatedTopics);
    } catch (err) {
      // Rollback: remove the optimistic test
      setTests(prev => prev.filter(t => t.id !== tempId));
      notifications.show(
        err instanceof Error ? err.message : 'Failed to add and evaluate test.',
        { severity: 'error' }
      );
    } finally {
      setPendingTestIds(prev => {
        const next = new Set(prev);
        next.delete(tempId);
        return next;
      });
    }
  };

  const handleInlineAddTest = async (input: string) => {
    const trimmedInput = input.trim();
    if (!trimmedInput || newTestProcessing) return;

    const tempId = `temp-inline-${Date.now()}`;
    const optimisticTest: TestNode = {
      id: tempId,
      topic: selectedTopic ?? '',
      input: trimmedInput,
      output: '',
      label: '',
      labeler: 'user',
      to_eval: true,
      model_score: 0,
    };

    setTests(prev => [optimisticTest, ...prev]);
    setPendingTestIds(prev => {
      const next = new Set(prev);
      next.add(tempId);
      return next;
    });
    setNewTestProcessing(true);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const client = clientFactory.getExplorerClient();

      const created = await client.createTest(testSetId, {
        input: trimmedInput,
        ...(selectedTopicForApi ? { topic: selectedTopicForApi } : {}),
        labeler: 'user',
        // Embeddings are generated when accepting tests from suggestion flow only.
        // Persisting embeddings for manually added tests is not implemented yet.
        generate_embedding: false,
      });
      setTests(prev => prev.map(test => (test.id === tempId ? created : test)));
      setPendingTestIds(prev => {
        const next = new Set(prev);
        next.delete(tempId);
        next.add(created.id);
        return next;
      });
      setNewTestInput('');

      await client.generateOutputs(testSetId, {
        test_ids: [created.id],
        overwrite: true,
      });

      await client.evaluate(testSetId, {
        test_ids: [created.id],
        overwrite: true,
      });

      const [treeNodes, updatedTopics] = await Promise.all([
        client.getTree(testSetId),
        client.getTopics(testSetId),
      ]);
      setTests(treeNodes.filter(node => node.label !== 'topic_marker'));
      setTopics(updatedTopics);
      setPendingTestIds(prev => {
        const next = new Set(prev);
        next.delete(created.id);
        return next;
      });
    } catch (err) {
      setTests(prev => prev.filter(test => test.id !== tempId));
      setPendingTestIds(prev => {
        const next = new Set(prev);
        next.delete(tempId);
        return next;
      });
      notifications.show(
        err instanceof Error ? err.message : 'Failed to add and evaluate test.',
        { severity: 'error' }
      );
    } finally {
      setNewTestProcessing(false);
    }
  };

  const handleSuggestionAccepted = useCallback(async () => {
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getExplorerClient();
    const [treeNodes, updatedTopics] = await Promise.all([
      client.getTree(testSetId),
      client.getTopics(testSetId),
    ]);
    setTests(treeNodes.filter(node => node.label !== 'topic_marker'));
    setTopics(updatedTopics);
  }, [sessionToken, testSetId]);

  const openSuggestionGuidance = useCallback(() => {
    setSuggestionGuidanceDraft('');
    setSuggestionGuidanceStep('choose');
    setSuggestionGuidanceDialogOpen(true);
  }, []);

  const closeSuggestionGuidanceDialog = useCallback(() => {
    setSuggestionGuidanceDialogOpen(false);
    setSuggestionGuidanceStep('choose');
  }, []);

  /** Generate immediately without optional user guidance. */
  const handleSuggestionGuidanceGenerateNow = useCallback(() => {
    setSuggestionsUserFeedback(null);
    closeSuggestionGuidanceDialog();
    setSuggestionsDialogOpen(true);
  }, [closeSuggestionGuidanceDialog]);

  const handleSuggestionGuidanceSpecifyGuide = useCallback(() => {
    setSuggestionGuidanceStep('guide');
  }, []);

  const handleSuggestionGuidanceBackToChoose = useCallback(() => {
    setSuggestionGuidanceStep('choose');
  }, []);

  /** After user chose to specify guide: run generation with trimmed feedback (may be empty). */
  const handleSuggestionGuidanceGenerateWithGuide = useCallback(() => {
    const trimmed = suggestionGuidanceDraft.trim();
    setSuggestionsUserFeedback(trimmed || null);
    closeSuggestionGuidanceDialog();
    setSuggestionsDialogOpen(true);
  }, [suggestionGuidanceDraft, closeSuggestionGuidanceDialog]);

  const handleSuggestionsDialogClose = useCallback(() => {
    setSuggestionsDialogOpen(false);
    setSuggestionsUserFeedback(null);
  }, []);

  const handleEditTestOpen = (test: TestNode) => {
    setEditingTest(test);
    setEditTestDialogOpen(true);
  };

  const handleTestRowClick = (test: TestNode) => {
    setTestDetailDrawerTest(test);
    setTestDetailDrawerOpen(true);
  };

  const handleEditTestSubmit = async (testId: string, data: TestNodeUpdate) => {
    // Save previous test state for rollback
    const previousTest = tests.find(t => t.id === testId);
    if (!previousTest) return;

    // Optimistically update local state
    setTests(prev => prev.map(t => (t.id === testId ? { ...t, ...data } : t)));

    // Fire API call in background (not awaited)
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getExplorerClient();

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
      const client = clientFactory.getExplorerClient();

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
    const client = clientFactory.getExplorerClient();

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
    const client = clientFactory.getExplorerClient();

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
    const client = clientFactory.getExplorerClient();

    client.deleteTest(testSetId, removedTest.id).catch(() => {
      // Rollback: re-add the test
      setTests(prev => [...prev, removedTest]);
      notifications.show('Failed to delete test. Change has been reverted.', {
        severity: 'error',
      });
    });
  };

  const handleBulkDeleteConfirm = async () => {
    if (selectedRows.length === 0) return;

    setIsBulkDeleting(true);
    const testsToDelete = selectedRows as string[];

    // Save previous state for rollback
    const previousTests = tests;

    // Optimistically remove from local state
    setTests(prev => prev.filter(t => !testsToDelete.includes(t.id)));
    setBulkDeleteConfirmOpen(false);

    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getExplorerClient();

    try {
      const results = await Promise.allSettled(
        testsToDelete.map(id => client.deleteTest(testSetId, id))
      );

      const failures = results.filter(r => r.status === 'rejected');

      if (failures.length > 0) {
        // Rollback by fetching full state from server to ensure consistency
        const [treeNodes, updatedTopics] = await Promise.all([
          client.getTree(testSetId),
          client.getTopics(testSetId),
        ]);
        setTests(treeNodes.filter(node => node.label !== 'topic_marker'));
        setTopics(updatedTopics);

        notifications.show(
          `Failed to delete ${failures.length} tests. State refreshed.`,
          {
            severity: 'error',
          }
        );
      } else {
        notifications.show(
          `Successfully deleted ${testsToDelete.length} tests.`,
          {
            severity: 'success',
          }
        );
      }
    } catch (_err) {
      // Complete failure fallback
      setTests(previousTests);
      notifications.show(
        'Failed to delete tests. Changes have been reverted.',
        {
          severity: 'error',
        }
      );
    } finally {
      setIsBulkDeleting(false);
      setSelectedRows([]);
    }
  };

  // Filter tests by selected topic
  const filteredTests = useMemo(() => {
    if (selectedTopic === null) {
      return tests;
    }
    if (selectedTopic === NO_TOPIC_FILTER) {
      return tests.filter(test => !test.topic);
    }
    return tests.filter(test => test.topic === selectedTopic);
  }, [tests, selectedTopic]);

  // Stats
  const totalTests = tests.length;
  const totalTopics = topics.length;
  const passCount = tests.filter(t => t.label === 'pass').length;
  const failCount = tests.filter(t => t.label === 'fail').length;

  const handleSaveSettings = async () => {
    if (!settingsEndpoint?.endpointId || !settingsMetric?.id) {
      setSettingsError('Select both endpoint and metric.');
      return;
    }
    setSettingsSaving(true);
    setSettingsError(null);
    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const explorerClient = clientFactory.getExplorerClient();
      await explorerClient.updateExplorerSettings(testSetId, {
        default_endpoint_id: settingsEndpoint.endpointId,
        metric_ids: [settingsMetric.id],
      });
      setExplorerConfigSummary({
        endpointLabel: `${settingsEndpoint.projectName} › ${settingsEndpoint.endpointName}`,
        endpointEnvironment: settingsEndpoint.environment,
        metrics:
          settingsMetric?.id &&
          settingsMetric.name != null &&
          settingsMetric.name !== ''
            ? [
                {
                  id: settingsMetric.id,
                  name: settingsMetric.name,
                  hasDetailPage: metricSupportsDetailPage(settingsMetric),
                },
              ]
            : [],
      });
      notifications.show('Explorer settings saved.', {
        severity: 'success',
      });
      setSettingsDialogOpen(false);
      setSettingsReEvaluateWarning(false);
    } catch (err) {
      setSettingsError(
        err instanceof Error ? err.message : 'Failed to save settings.'
      );
    } finally {
      setSettingsSaving(false);
    }
  };

  const handleExportToTestSet = useCallback(async () => {
    const clientFactory = new ApiClientFactory(sessionToken);
    const client = clientFactory.getExplorerClient();
    setExportSubmitting(true);
    try {
      const result = await client.exportRegularTestSetFromExplorer(testSetId);
      const { exported, skipped, test_set: created } = result;
      const parts = [
        `Created "${created.name}"`,
        `exported ${exported} test(s)`,
      ];
      if (skipped > 0) {
        parts.push(`skipped ${skipped}`);
      }
      notifications.show(parts.join('. '), {
        severity: 'success',
        autoHideDuration: 6000,
      });
      router.push(`/test-sets/${created.id}`);
    } catch (err) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to export test set.',
        { severity: 'error', autoHideDuration: 6000 }
      );
    } finally {
      setExportSubmitting(false);
    }
  }, [sessionToken, testSetId, notifications, router]);

  return (
    <PageLayout
      title={testSetName}
      description="Interactive explorer session — discover behaviors, generate tests, and export to test sets."
      breadcrumbs={[
        { label: 'Explorer', href: '/explorer' },
        { label: testSetName },
      ]}
      actions={
        <FabGroup>
          <Fab
            icon={<IosShareOutlinedIcon />}
            tooltip="Save to Test Set"
            onClick={() => void handleExportToTestSet()}
            loading={exportSubmitting}
          />
          <Fab
            icon={<SettingsIcon />}
            tooltip="Edit settings"
            onClick={() => {
              setSettingsReEvaluateWarning(true);
              setSettingsDialogOpen(true);
            }}
          />
        </FabGroup>
      }
    >
      <Box>
        {/* View Tabs + Stats */}
        <Box
          sx={{
            borderBottom: '1px solid',
            borderColor: 'divider',
            mb: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Tabs
            value={activeTab}
            onChange={(_, newValue) => {
              setActiveTab(newValue);
              setSelectedRows([]);
            }}
            sx={{ minHeight: 44 }}
          >
            <Tab
              icon={<AccountTreeIcon />}
              iconPosition="start"
              label="Tree View"
              sx={{ minHeight: 44 }}
            />
            <Tab
              icon={<ListIcon />}
              iconPosition="start"
              label="List View"
              sx={{ minHeight: 44 }}
            />
          </Tabs>
          {/* Stats chips — right-aligned, anchored to the tab bar */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              flexWrap: 'wrap',
              pr: 1,
              pb: 0.5,
            }}
          >
            {[
              { label: 'Total', value: totalTests, color: undefined },
              { label: 'Topics', value: totalTopics, color: undefined },
              {
                label: 'Pass',
                value: passCount,
                color: 'success.main' as const,
              },
              {
                label: 'Fail',
                value: failCount,
                color: 'error.main' as const,
              },
            ].map(item => (
              <Box
                key={item.label}
                sx={{
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: 0.5,
                  px: 1,
                  py: 0.25,
                  borderRadius: 1,
                  border: '1px solid',
                  borderColor: 'divider',
                  bgcolor: 'background.paper',
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  {item.label}
                </Typography>
                <Typography
                  variant="caption"
                  fontWeight={700}
                  color={item.color ?? 'text.primary'}
                >
                  {item.value}
                </Typography>
              </Box>
            ))}
          </Box>
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
                borderRadius: BORDER_RADIUS.md,
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
                  onTopicSelect={handleTopicSelect}
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
                sx={{ mb: 0.75, display: 'flex', alignItems: 'center', gap: 1 }}
              >
                <Typography variant="subtitle2" color="text.primary">
                  {selectedTopic
                    ? selectedTopic === NO_TOPIC_FILTER
                      ? 'Tests without topic'
                      : decodeURIComponent(selectedTopic)
                    : 'All Tests'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  ({filteredTests.length}{' '}
                  {filteredTests.length === 1 ? 'test' : 'tests'})
                </Typography>
              </Box>
              {(generateSubmitting ||
                evaluateSubmitting ||
                generateError ||
                evaluateError) && (
                <Stack sx={{ mb: 1 }} spacing={1}>
                  {generateSubmitting && (
                    <Alert
                      severity="info"
                      onClose={() => setGenerateError(null)}
                    >
                      Getting outputs…
                    </Alert>
                  )}
                  {evaluateSubmitting && (
                    <Alert
                      severity="info"
                      onClose={() => setEvaluateError(null)}
                    >
                      Evaluating…
                    </Alert>
                  )}
                  {generateError && (
                    <Alert
                      severity="error"
                      onClose={() => setGenerateError(null)}
                    >
                      {generateError}
                    </Alert>
                  )}
                  {evaluateError && (
                    <Alert
                      severity="error"
                      onClose={() => setEvaluateError(null)}
                    >
                      {evaluateError}
                    </Alert>
                  )}
                </Stack>
              )}
              {/* Inline add-test row lives above the card so the card only has the grid */}
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <TextField
                  size="small"
                  fullWidth
                  placeholder="Type test input and press Enter"
                  value={newTestInput}
                  onChange={e => setNewTestInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') {
                      const value = newTestInput.trim();
                      if (value) void handleInlineAddTest(value);
                    }
                  }}
                  disabled={newTestProcessing}
                />
                <Tooltip title="Add test">
                  <span>
                    <IconButton
                      color="primary"
                      onClick={() => {
                        const value = newTestInput.trim();
                        if (value) void handleInlineAddTest(value);
                      }}
                      disabled={newTestProcessing || !newTestInput.trim()}
                    >
                      {newTestProcessing ? (
                        <CircularProgress size={18} />
                      ) : (
                        <CheckIcon fontSize="small" />
                      )}
                    </IconButton>
                  </span>
                </Tooltip>
              </Box>
              <Paper
                variant="outlined"
                sx={{ borderRadius: BORDER_RADIUS.md, overflow: 'hidden' }}
              >
                <TestsList
                  tests={filteredTests}
                  loading={false}
                  onEditTest={handleEditTestOpen}
                  onDeleteTest={handleDeleteTestOpen}
                  onRowClick={handleTestRowClick}
                  checkboxSelection
                  rowSelectionModel={selectedRows}
                  onRowSelectionModelChange={setSelectedRows}
                  pendingTestIds={pendingTestIds}
                  onGetOutputs={() => handleGenerateOutputsInline(true)}
                  onEvaluate={() => handleEvaluateInline(true)}
                  onAddTest={() => setAddTestDialogOpen(true)}
                  onSuggest={openSuggestionGuidance}
                  onBulkDelete={() => setBulkDeleteConfirmOpen(true)}
                  generateSubmitting={generateSubmitting}
                  evaluateSubmitting={evaluateSubmitting}
                />
              </Paper>
            </Box>
          </Box>
        )}

        {/* List View - All tests in a flat table */}
        {activeTab === 1 && (
          <Box>
            {(generateSubmitting ||
              evaluateSubmitting ||
              generateError ||
              evaluateError) && (
              <Stack sx={{ mb: 1 }} spacing={1}>
                {generateSubmitting && (
                  <Alert severity="info" onClose={() => setGenerateError(null)}>
                    Getting outputs…
                  </Alert>
                )}
                {evaluateSubmitting && (
                  <Alert severity="info" onClose={() => setEvaluateError(null)}>
                    Evaluating…
                  </Alert>
                )}
                {generateError && (
                  <Alert
                    severity="error"
                    onClose={() => setGenerateError(null)}
                  >
                    {generateError}
                  </Alert>
                )}
                {evaluateError && (
                  <Alert
                    severity="error"
                    onClose={() => setEvaluateError(null)}
                  >
                    {evaluateError}
                  </Alert>
                )}
              </Stack>
            )}
            {/* Inline add-test row lives above the card */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <TextField
                size="small"
                fullWidth
                placeholder="Type test input and press Enter"
                value={newTestInput}
                onChange={e => setNewTestInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') {
                    const value = newTestInput.trim();
                    if (value) void handleInlineAddTest(value);
                  }
                }}
                disabled={newTestProcessing}
              />
              <Tooltip title="Add test">
                <span>
                  <IconButton
                    color="primary"
                    onClick={() => {
                      const value = newTestInput.trim();
                      if (value) void handleInlineAddTest(value);
                    }}
                    disabled={newTestProcessing || !newTestInput.trim()}
                  >
                    {newTestProcessing ? (
                      <CircularProgress size={18} />
                    ) : (
                      <CheckIcon fontSize="small" />
                    )}
                  </IconButton>
                </span>
              </Tooltip>
            </Box>
            <Paper
              variant="outlined"
              sx={{ borderRadius: BORDER_RADIUS.md, overflow: 'hidden' }}
            >
              <TestsList
                tests={tests}
                loading={false}
                onEditTest={handleEditTestOpen}
                onDeleteTest={handleDeleteTestOpen}
                onRowClick={handleTestRowClick}
                checkboxSelection
                rowSelectionModel={selectedRows}
                onRowSelectionModelChange={setSelectedRows}
                pendingTestIds={pendingTestIds}
                onGetOutputs={() => handleGenerateOutputsInline(false)}
                onEvaluate={() => handleEvaluateInline(false)}
                onAddTest={() => setAddTestDialogOpen(true)}
                onSuggest={openSuggestionGuidance}
                onBulkDelete={() => setBulkDeleteConfirmOpen(true)}
                generateSubmitting={generateSubmitting}
                evaluateSubmitting={evaluateSubmitting}
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
          topic={selectedTopicForApi}
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

        {/* Test Detail Drawer (row click) */}
        <TestDetailDrawer
          open={testDetailDrawerOpen}
          onClose={() => {
            setTestDetailDrawerOpen(false);
            setTestDetailDrawerTest(null);
          }}
          onSubmit={handleEditTestSubmit}
          test={testDetailDrawerTest}
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

        {/* Bulk Delete Confirmation Dialog */}
        <Dialog
          open={bulkDeleteConfirmOpen}
          onClose={() => {
            if (!isBulkDeleting) setBulkDeleteConfirmOpen(false);
          }}
          maxWidth="xs"
          fullWidth
        >
          <DialogTitle>Delete Tests</DialogTitle>
          <DialogContent>
            <Typography>
              Are you sure you want to delete {selectedRows.length}{' '}
              {selectedRows.length === 1 ? 'test' : 'tests'}?
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button
              onClick={() => setBulkDeleteConfirmOpen(false)}
              disabled={isBulkDeleting}
            >
              Cancel
            </Button>
            <Button
              onClick={handleBulkDeleteConfirm}
              color="error"
              variant="contained"
              disabled={isBulkDeleting}
              startIcon={
                isBulkDeleting ? (
                  <CircularProgress size={16} color="inherit" />
                ) : undefined
              }
            >
              {isBulkDeleting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Get outputs dialog */}
        <Dialog
          open={generateOutputsDialogOpen}
          onClose={handleGenerateOutputsClose}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Get outputs</DialogTitle>
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
                sx={{ display: 'block' }}
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
              onClick={() => {
                void handleGenerateOutputsSubmit();
              }}
              disabled={generateSubmitting}
              startIcon={
                generateSubmitting ? (
                  <CircularProgress size={16} color="inherit" />
                ) : (
                  <PlayArrowIcon />
                )
              }
            >
              {generateSubmitting ? 'Getting…' : 'Get outputs'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Evaluate dialog */}
        <Dialog
          open={evaluateDialogOpen}
          onClose={handleEvaluateClose}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Evaluate</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Run the metric configured in explorer settings against each
              test&apos;s stored input and output, and persist the evaluation
              results in test metadata.
            </Typography>
            {evaluateError && (
              <Alert
                severity="error"
                sx={{ mb: 2 }}
                onClose={() => setEvaluateError(null)}
              >
                {evaluateError}
              </Alert>
            )}
            <Autocomplete
              options={[allTestsTopicOption, ...topics]}
              getOptionLabel={option =>
                option.path ? (option.display_path ?? option.path) : 'All tests'
              }
              value={
                evaluateTopic === null || evaluateTopic === ''
                  ? allTestsTopicOption
                  : (topics.find(t => t.path === evaluateTopic) ?? {
                      path: evaluateTopic,
                      name: evaluateTopic.split('/').pop() ?? evaluateTopic,
                      parent_path: null,
                      depth: 0,
                      display_name: evaluateTopic,
                      display_path: evaluateTopic,
                      has_direct_tests: false,
                      has_subtopics: false,
                    })
              }
              onChange={(_, value) =>
                setEvaluateTopic(
                  value?.path && value.path !== '' ? value.path : null
                )
              }
              isOptionEqualToValue={(a, b) => a.path === b.path}
              renderInput={params => (
                <TextField {...params} label="Topic" placeholder="All tests" />
              )}
              sx={{ mb: 1 }}
            />
            {evaluateTopic != null && evaluateTopic !== '' && (
              <FormControlLabel
                control={
                  <Checkbox
                    checked={evaluateIncludeSubtopics}
                    onChange={e =>
                      setEvaluateIncludeSubtopics(e.target.checked)
                    }
                  />
                }
                label="Include subtopics"
                sx={{ display: 'block' }}
              />
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={handleEvaluateClose} disabled={evaluateSubmitting}>
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={() => {
                void handleEvaluateSubmit();
              }}
              disabled={evaluateSubmitting}
              startIcon={
                evaluateSubmitting ? (
                  <CircularProgress size={16} color="inherit" />
                ) : (
                  <GradingIcon />
                )
              }
            >
              {evaluateSubmitting ? 'Evaluating…' : 'Evaluate'}
            </Button>
          </DialogActions>
        </Dialog>

        <BaseDrawer
          open={settingsDialogOpen}
          onClose={() => {
            if (!settingsSaving) {
              setSettingsDialogOpen(false);
              setSettingsError(null);
              setSettingsReEvaluateWarning(false);
            }
          }}
          title="Explorer settings"
          titleIcon={<SettingsIcon sx={{ fontSize: 24 }} />}
          onSave={() => void handleSaveSettings()}
          saveButtonText="Save"
          loading={settingsSaving}
          error={settingsError ?? undefined}
          anchor="right"
        >
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Typography variant="body2" color="text.secondary">
              Select the endpoint and metric used for explorer generation and
              evaluation.
            </Typography>
            {explorerConfigSummary !== null && (
              <EntityInfoBanner
                name={
                  explorerConfigSummary.endpointLabel
                    ? `${explorerConfigSummary.endpointLabel}${explorerConfigSummary.endpointEnvironment ? ` (${formatEnvironment(explorerConfigSummary.endpointEnvironment)})` : ''}`
                    : 'No endpoint selected'
                }
                description={
                  explorerConfigSummary.metrics.length > 0
                    ? `Metric: ${explorerConfigSummary.metrics.map(m => m.name).join(', ')}`
                    : 'No metric selected'
                }
              />
            )}
            {settingsReEvaluateWarning && (
              <Alert severity="warning">
                To keep results consistent with a new endpoint or metric, use
                Get outputs and Evaluate for all tests in this set.
              </Alert>
            )}
            <Autocomplete
              options={endpointOptions}
              getOptionLabel={option =>
                `${option.projectName} › ${option.endpointName}`
              }
              value={settingsEndpoint}
              onChange={(_, value) => setSettingsEndpoint(value ?? null)}
              loading={endpointsLoading}
              renderOption={(props, option) => {
                const { key: _key, ...otherProps } = props;
                return (
                  <li key={option.endpointId} {...otherProps}>
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        width: '100%',
                      }}
                    >
                      <Typography variant="body2" sx={{ flexGrow: 1 }}>
                        {option.projectName} › {option.endpointName}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{
                          ml: 2,
                          px: 1,
                          py: 0.25,
                          borderRadius: 0.5,
                          bgcolor: 'action.hover',
                          color: getEnvironmentColor(option.environment),
                          fontWeight: 'medium',
                        }}
                      >
                        {formatEnvironment(option.environment)}
                      </Typography>
                    </Box>
                  </li>
                );
              }}
              renderInput={params => (
                <TextField
                  {...params}
                  label="Endpoint"
                  placeholder="Select endpoint"
                />
              )}
            />
            <Autocomplete
              options={metrics}
              getOptionLabel={option => option.name ?? ''}
              value={settingsMetric}
              onChange={(_, value) => setSettingsMetric(value ?? null)}
              loading={metricsLoading}
              renderInput={params => (
                <TextField
                  {...params}
                  label="Metric (single-turn)"
                  placeholder="Select metric"
                />
              )}
            />
          </Box>
        </BaseDrawer>

        <Dialog
          open={metricEditorMetricId != null}
          onClose={() => setMetricEditorMetricId(null)}
          maxWidth={false}
          fullWidth
          PaperProps={{
            sx: {
              m: { xs: 0, sm: 2 },
              width: { xs: '100%', sm: 'min(1100px, 98vw)' },
              maxHeight: { xs: '100%', sm: '94vh' },
              height: { xs: '100%', sm: 'min(900px, 94vh)' },
              borderRadius: { xs: 0, sm: 2 },
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            },
          }}
        >
          {metricEditorMetricId ? (
            <Box
              sx={{
                flex: 1,
                minHeight: 0,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              }}
            >
              <MetricDetailView
                key={metricEditorMetricId}
                metricId={metricEditorMetricId}
                mode="embedded"
                onClose={() => setMetricEditorMetricId(null)}
                onSaved={() => {
                  void loadExplorerSettings();
                }}
              />
            </Box>
          ) : null}
        </Dialog>

        {/* Optional user guidance before generating suggestions */}
        <Dialog
          open={suggestionGuidanceDialogOpen}
          onClose={closeSuggestionGuidanceDialog}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Suggest tests</DialogTitle>
          <DialogContent>
            {suggestionGuidanceStep === 'choose' ? (
              <>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 2 }}
                >
                  New suggestions are generated from examples in this test set.
                  Choose whether to run generation now, or add guidance first
                  for how the model should shape suggestions.
                </Typography>
              </>
            ) : (
              <>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 2 }}
                >
                  Describe how suggestions should be generated. This is sent to
                  the model together with your existing tests.
                </Typography>
                <TextField
                  autoFocus
                  multiline
                  minRows={3}
                  fullWidth
                  label="Generation guide"
                  placeholder="e.g., Focus on edge cases for date parsing..."
                  value={suggestionGuidanceDraft}
                  onChange={e => setSuggestionGuidanceDraft(e.target.value)}
                  inputProps={{ maxLength: 1000 }}
                  helperText="Up to 1000 characters."
                />
              </>
            )}
          </DialogContent>
          <DialogActions>
            {suggestionGuidanceStep === 'choose' ? (
              <>
                <Button onClick={closeSuggestionGuidanceDialog}>Cancel</Button>
                <Button
                  variant="outlined"
                  onClick={handleSuggestionGuidanceSpecifyGuide}
                >
                  Specify guide
                </Button>
                <Button
                  variant="contained"
                  onClick={handleSuggestionGuidanceGenerateNow}
                >
                  Generate
                </Button>
              </>
            ) : (
              <>
                <Button onClick={handleSuggestionGuidanceBackToChoose}>
                  Back
                </Button>
                <Button
                  variant="contained"
                  onClick={handleSuggestionGuidanceGenerateWithGuide}
                >
                  Generate
                </Button>
              </>
            )}
          </DialogActions>
        </Dialog>

        {/* Suggestions dialog */}
        <SuggestionsDialog
          open={suggestionsDialogOpen}
          onClose={handleSuggestionsDialogClose}
          testSetId={testSetId}
          sessionToken={sessionToken}
          topic={selectedTopicForApi}
          userFeedback={suggestionsUserFeedback}
          onTestAccepted={handleSuggestionAccepted}
        />
      </Box>
    </PageLayout>
  );
}
