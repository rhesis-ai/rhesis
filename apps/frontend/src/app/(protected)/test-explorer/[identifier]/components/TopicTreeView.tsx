'use client';

import { useState, useMemo, DragEvent } from 'react';
import { Box, Typography, Collapse, IconButton, Chip } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import FolderIcon from '@mui/icons-material/Folder';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';

export interface TopicNode {
  name: string;
  path: string;
  children: TopicNode[];
  testCount: number;
  avgScore: number | null;
}

export interface AdaptiveTest {
  id: string;
  input: string;
  output: string;
  score: number | null;
  topic: string;
  label: string;
}

interface TopicTreeViewProps {
  tests: AdaptiveTest[];
  selectedTopic: string | null;
  onTopicSelect: (topicPath: string | null) => void;
  onTestDrop?: (testId: string, newTopicPath: string) => void;
}

// Build tree structure from flat test list
function buildTopicTree(tests: AdaptiveTest[]): TopicNode[] {
  const rootNodes: Map<string, TopicNode> = new Map();

  // Helper to get or create a node at a path
  function getOrCreateNode(
    path: string,
    parentMap: Map<string, TopicNode>
  ): TopicNode {
    const parts = path.split('/').filter(Boolean);
    let currentMap = parentMap;
    let currentPath = '';
    let node: TopicNode | undefined;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      currentPath = currentPath ? `${currentPath}/${part}` : part;

      if (!currentMap.has(part)) {
        const newNode: TopicNode = {
          name: decodeURIComponent(part),
          path: currentPath,
          children: [],
          testCount: 0,
          avgScore: null,
        };
        currentMap.set(part, newNode);

        // If this is not the root level, add to parent's children
        if (node) {
          const existingChild = node.children.find(c => c.path === currentPath);
          if (!existingChild) {
            node.children.push(newNode);
          }
        }
      }

      node = currentMap.get(part)!;

      // For next iteration, we need to work with this node's children
      // Convert children array to a map for lookup
      const childMap = new Map<string, TopicNode>();
      for (const child of node.children) {
        const childName = child.path.split('/').pop() || '';
        childMap.set(childName, child);
      }
      currentMap = childMap;
    }

    return node!;
  }

  // Process all tests
  for (const test of tests) {
    const topic = typeof test.topic === 'string' ? test.topic : '';
    if (!topic) continue;

    const node = getOrCreateNode(topic, rootNodes);
    node.testCount++;

    if (test.score !== null) {
      if (node.avgScore === null) {
        node.avgScore = test.score;
      } else {
        // Running average
        node.avgScore =
          (node.avgScore * (node.testCount - 1) + test.score) / node.testCount;
      }
    }
  }

  // Update parent counts recursively
  function updateCounts(node: TopicNode): { count: number; scoreSum: number; scoreCount: number } {
    let totalCount = node.testCount;
    let scoreSum = node.avgScore !== null ? node.avgScore * node.testCount : 0;
    let scoreCount = node.avgScore !== null ? node.testCount : 0;

    for (const child of node.children) {
      const childStats = updateCounts(child);
      totalCount += childStats.count;
      scoreSum += childStats.scoreSum;
      scoreCount += childStats.scoreCount;
    }

    node.testCount = totalCount;
    node.avgScore = scoreCount > 0 ? scoreSum / scoreCount : null;

    return { count: totalCount, scoreSum, scoreCount };
  }

  const result = Array.from(rootNodes.values());
  for (const node of result) {
    updateCounts(node);
  }

  return result;
}

function getScoreColor(
  score: number | null
): 'success' | 'warning' | 'error' | 'default' {
  if (score === null) return 'default';
  if (score >= 0.7) return 'error';
  if (score >= 0.3) return 'warning';
  return 'success';
}

interface TopicTreeNodeProps {
  node: TopicNode;
  selectedTopic: string | null;
  onTopicSelect: (topicPath: string | null) => void;
  level: number;
  expandedPaths: Set<string>;
  onToggleExpand: (path: string) => void;
  onTestDrop?: (testId: string, newTopicPath: string) => void;
  dragOverPath: string | null;
  onDragOverChange: (path: string | null) => void;
}

function TopicTreeNode({
  node,
  selectedTopic,
  onTopicSelect,
  level,
  expandedPaths,
  onToggleExpand,
  onTestDrop,
  dragOverPath,
  onDragOverChange,
}: TopicTreeNodeProps) {
  const hasChildren = node.children.length > 0;
  const isExpanded = expandedPaths.has(node.path);
  const isSelected = selectedTopic === node.path;
  const isDragOver = dragOverPath === node.path;

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    onToggleExpand(node.path);
  };

  const handleClick = () => {
    onTopicSelect(node.path);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    onDragOverChange(node.path);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    // Only clear if we're leaving this specific node
    if (dragOverPath === node.path) {
      onDragOverChange(null);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    onDragOverChange(null);

    const testId = e.dataTransfer.getData('text/plain');
    if (testId && onTestDrop) {
      onTestDrop(testId, node.path);
    }
  };

  return (
    <Box>
      <Box
        onClick={handleClick}
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
          backgroundColor: isDragOver
            ? 'primary.light'
            : isSelected
              ? 'action.selected'
              : 'transparent',
          border: isDragOver ? '2px dashed' : '2px solid transparent',
          borderColor: isDragOver ? 'primary.main' : 'transparent',
          transition: 'all 0.15s ease-in-out',
          '&:hover': {
            backgroundColor: isDragOver
              ? 'primary.light'
              : isSelected
                ? 'action.selected'
                : 'action.hover',
          },
        }}
      >
        {/* Expand/Collapse Icon */}
        <Box sx={{ width: 28, flexShrink: 0 }}>
          {hasChildren && (
            <IconButton size="small" onClick={handleToggle} sx={{ p: 0.5 }}>
              {isExpanded ? (
                <ExpandMoreIcon fontSize="small" />
              ) : (
                <ChevronRightIcon fontSize="small" />
              )}
            </IconButton>
          )}
        </Box>

        {/* Folder Icon */}
        <Box sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
          {isExpanded ? (
            <FolderOpenIcon fontSize="small" color="primary" />
          ) : (
            <FolderIcon fontSize="small" color="action" />
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
          {node.name}
        </Typography>

        {/* Test Count */}
        <Chip
          label={node.testCount}
          size="small"
          variant="outlined"
          sx={{ height: 20, fontSize: '0.75rem', ml: 1 }}
        />

        {/* Average Score */}
        {node.avgScore !== null && (
          <Chip
            label={node.avgScore.toFixed(2)}
            size="small"
            color={getScoreColor(node.avgScore)}
            sx={{ height: 20, fontSize: '0.75rem', ml: 0.5 }}
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
              <TopicTreeNode
                key={child.path}
                node={child}
                selectedTopic={selectedTopic}
                onTopicSelect={onTopicSelect}
                level={level + 1}
                expandedPaths={expandedPaths}
                onToggleExpand={onToggleExpand}
                onTestDrop={onTestDrop}
                dragOverPath={dragOverPath}
                onDragOverChange={onDragOverChange}
              />
            ))}
          </Box>
        </Collapse>
      )}
    </Box>
  );
}

export default function TopicTreeView({
  tests,
  selectedTopic,
  onTopicSelect,
  onTestDrop,
}: TopicTreeViewProps) {
  const topicTree = useMemo(() => buildTopicTree(tests), [tests]);
  const [dragOverPath, setDragOverPath] = useState<string | null>(null);

  // Start with all paths expanded
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(() => {
    const paths = new Set<string>();
    function collectPaths(nodes: TopicNode[]) {
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
          backgroundColor: selectedTopic === null ? 'action.selected' : 'transparent',
          '&:hover': {
            backgroundColor: selectedTopic === null ? 'action.selected' : 'action.hover',
          },
          mb: 1,
        }}
      >
        <Box sx={{ width: 28, flexShrink: 0 }} />
        <FolderIcon fontSize="small" color="action" sx={{ mr: 1 }} />
        <Typography
          variant="body2"
          sx={{ flex: 1, fontWeight: selectedTopic === null ? 600 : 400 }}
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
        <TopicTreeNode
          key={node.path}
          node={node}
          selectedTopic={selectedTopic}
          onTopicSelect={onTopicSelect}
          level={0}
          expandedPaths={expandedPaths}
          onToggleExpand={handleToggleExpand}
          onTestDrop={onTestDrop}
          dragOverPath={dragOverPath}
          onDragOverChange={setDragOverPath}
        />
      ))}
    </Box>
  );
}
