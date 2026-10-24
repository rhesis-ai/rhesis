'use client';

import { useState, useEffect, useMemo } from 'react';
import { useSession } from 'next-auth/react';
import { Box, Typography } from '@mui/material';
import { GridBadge } from '@/components/common/GridBadge';
import DetailTabNav from '@/components/common/DetailTabNav';
import {
  SpanNode,
  TraceDetailResponse,
  TraceMetricsStatus,
} from '@/utils/api-client/interfaces/telemetry';
import { FileResponse } from '@/utils/api-client/interfaces/file';
import { FilesClient } from '@/utils/api-client/files-client';
import FileAttachmentList from '@/components/common/FileAttachmentList';
import { MentionOption } from '@/components/common/MentionTextInput';
import { TasksAndCommentsWrapper } from '@/components/tasks/TasksAndCommentsWrapper';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import EvaluationTab from './EvaluationTab';
import SpanHeader from './SpanHeader';
import SpanIOPane from './SpanIOPane';
import SpanAttributeSections from './SpanAttributeSections';
import { extractSpanIO, groupAttributes, type SpanIO } from './span-io';
import { automatedVerdictFor } from './trace-verdict';

interface SpanDetailsPanelProps {
  span: SpanNode | null;
  trace: TraceDetailResponse | null;
  hasTraceMetrics?: boolean;
  isConversationTrace?: boolean;
  currentUserId?: string;
  currentUserName?: string;
  currentUserPicture?: string;
  onTraceUpdated?: () => void;
  onAnnotateMetric?: (metricName: string) => void;
  onAnnotateTrace?: () => void;
  onAnnotateTurn?: (turnNumber: number, turnPassed?: boolean) => void;
  mentionableMetrics?: MentionOption[];
  mentionableTurns?: MentionOption[];
  traceMetricsStatus?: TraceMetricsStatus | null;
  selectedTurnNumber?: number | null;
}

type TabKey = 'details' | 'evaluation' | 'comments';

const IO_KIND_LABEL: Record<SpanIO['kind'], string> = {
  function: 'Function',
  llm: 'LLM',
  tool: 'Tool',
  agent: 'Agent',
};

function TabPanel({
  children,
  value,
  index,
}: {
  children?: React.ReactNode;
  index: TabKey;
  value: TabKey;
}) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`span-detail-tabpanel-${index}`}
      aria-labelledby={`span-detail-tab-${index}`}
    >
      {value === index && children}
    </div>
  );
}

/** Input first, then output, for each kind of I/O the span carries. */
function SpanIOList({ span }: { span: SpanNode }) {
  const ios = extractSpanIO(span);
  if (ios.length === 0) {
    return (
      <Typography variant="caption" color="text.secondary">
        This span recorded no input or output.
      </Typography>
    );
  }
  // Prefix the kind only when there is more than one, e.g. a function that is also an agent.
  const prefix = (io: SpanIO, word: string) =>
    ios.length > 1 ? `${IO_KIND_LABEL[io.kind]} ${word.toLowerCase()}` : word;

  return (
    <>
      {ios.map(io => (
        <Box
          key={io.kind}
          sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}
        >
          {io.messages ? (
            <SpanIOPane title={prefix(io, 'Input')} messages={io.messages} />
          ) : (
            io.input.length > 0 && (
              <SpanIOPane title={prefix(io, 'Input')} entries={io.input} />
            )
          )}
          {io.output !== null && (
            <SpanIOPane
              title={prefix(io, 'Output')}
              entries={[{ value: io.output }]}
            />
          )}
        </Box>
      ))}
    </>
  );
}

export default function SpanDetailsPanel({
  span,
  trace,
  hasTraceMetrics = false,
  isConversationTrace = false,
  currentUserId = '',
  currentUserName = '',
  currentUserPicture,
  onTraceUpdated,
  onAnnotateMetric,
  onAnnotateTrace,
  onAnnotateTurn,
  mentionableMetrics = [],
  mentionableTurns = [],
  traceMetricsStatus = null,
  selectedTurnNumber = null,
}: SpanDetailsPanelProps) {
  const { status } = useSession();
  const [activeTab, setActiveTab] = useState<TabKey>('details');
  const [spanFiles, setSpanFiles] = useState<FileResponse[]>([]);
  const [spanFilesLoading, setSpanFilesLoading] = useState(false);

  const automated = span ? automatedVerdictFor(span) : null;
  const failedCount = automated?.failed ?? 0;

  const tabs = useMemo(() => {
    const list: {
      key: TabKey;
      label: string;
      badge?: React.ReactNode;
      id: string;
      'aria-controls': string;
    }[] = [
      { key: 'details', label: 'Details' },
      {
        key: 'evaluation',
        label: 'Evaluation',
        badge:
          failedCount > 0 ? (
            <GridBadge
              label={`${failedCount} failed`}
              size="grid"
              sx={{ color: 'error.main' }}
            />
          ) : undefined,
      },
    ].map(tab => ({
      ...tab,
      key: tab.key as TabKey,
      id: `span-detail-tab-${tab.key}`,
      'aria-controls': `span-detail-tabpanel-${tab.key}`,
    }));
    if (trace?.root_spans?.[0]?.id) {
      list.push({
        key: 'comments',
        label: 'Comments',
        id: 'span-detail-tab-comments',
        'aria-controls': 'span-detail-tabpanel-comments',
      });
    }
    return list;
  }, [failedCount, trace?.root_spans]);

  const activeIndex = Math.max(
    tabs.findIndex(t => t.key === activeTab),
    0
  );

  // Fetch files attached to the selected span
  useEffect(() => {
    if (!span?.id || !isAuthenticated(status)) {
      setSpanFiles([]);
      return;
    }

    let cancelled = false;
    setSpanFilesLoading(true);

    const filesClient = new FilesClient();
    filesClient
      .getSpanFiles(span.id)
      .then(files => {
        if (!cancelled) setSpanFiles(files);
      })
      .catch(() => {
        if (!cancelled) setSpanFiles([]);
      })
      .finally(() => {
        if (!cancelled) setSpanFilesLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [span?.id, status]);

  const attributeGroups = useMemo(
    () => groupAttributes(span?.attributes),
    [span?.attributes]
  );

  if (!span) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Select a span to view details
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box
        sx={{
          flexShrink: 0,
          height: theme => theme.spacing(5.5),
          px: 2,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <DetailTabNav
          tabs={tabs}
          activeIndex={activeIndex}
          onChange={index => setActiveTab(tabs[index]?.key ?? 'details')}
          aria-label="span detail tabs"
          tabGap="20px"
          size="compact"
          scrollable
          sx={{ height: '100%' }}
        />
      </Box>

      {tabs[activeIndex]?.key === 'details' && (
        <SpanHeader span={span} traceId={trace?.trace_id} />
      )}

      <Box sx={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        <TabPanel value={tabs[activeIndex].key} index="details">
          <Box
            sx={{
              px: 2,
              py: 1.5,
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            <SpanIOList span={span} />
          </Box>
          <SpanAttributeSections
            span={span}
            groups={attributeGroups}
            attachmentCount={spanFilesLoading ? undefined : spanFiles.length}
            attachments={
              spanFiles.length > 0 || spanFilesLoading ? (
                <FileAttachmentList
                  files={spanFiles}
                  isLoading={spanFilesLoading}
                />
              ) : undefined
            }
          />
        </TabPanel>

        {trace && (
          <TabPanel value={tabs[activeIndex].key} index="evaluation">
            <EvaluationTab
              span={span}
              trace={trace}
              hasTraceMetrics={hasTraceMetrics}
              isConversationTrace={isConversationTrace}
              selectedTurnNumber={selectedTurnNumber}
              traceMetricsStatus={traceMetricsStatus}
              onAnnotateMetric={onAnnotateMetric}
              onAnnotateTrace={onAnnotateTrace}
              onAnnotateTurn={onAnnotateTurn}
              onTraceUpdated={onTraceUpdated ?? (() => {})}
              mentionableMetrics={mentionableMetrics}
              mentionableTurns={mentionableTurns}
            />
          </TabPanel>
        )}

        {trace?.root_spans?.[0]?.id && (
          <TabPanel value={tabs[activeIndex].key} index="comments">
            <Box sx={{ px: 2, py: 1.5 }}>
              <TasksAndCommentsWrapper
                entityType="Trace"
                entityId={trace.root_spans[0].id}
                currentUserId={currentUserId}
                currentUserName={currentUserName}
                currentUserPicture={currentUserPicture}
              />
            </Box>
          </TabPanel>
        )}
      </Box>
    </Box>
  );
}
