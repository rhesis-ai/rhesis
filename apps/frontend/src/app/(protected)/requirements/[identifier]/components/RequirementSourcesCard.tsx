'use client';

import React, { useCallback, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Box,
  Button,
  IconButton,
  Link as MuiLink,
  Menu,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import BaseDrawer from '@/components/common/BaseDrawer';
import {
  drawerFieldsSx,
  drawerOutlinedFieldSx,
} from '@/components/common/drawerFormFieldSx';
import { sectionEditButtonSx } from '@/components/common/SectionCardActions';
import type { GridColDef, GridRowModel } from '@mui/x-data-grid';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import { AddIcon, LinkOffIcon } from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import AssignEntityDrawer from '@/components/common/AssignEntityDrawer';
import GridBadge from '@/components/common/GridBadge';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  RequirementSourceLink,
  RequirementWithMetrics,
} from '@/utils/api-client/interfaces/requirement';
import type { Source } from '@/utils/api-client/interfaces/source';
import { useTypeLookups } from '@/hooks/useLookups';
import { BORDER_RADIUS } from '@/styles/theme';
import UploadSourceDrawer from '../../../knowledge/components/UploadSourceDrawer';
import type { UUID } from 'crypto';

export const SOURCES_CARD_ID = 'requirement-sources';

const KNOWLEDGE_PICKER_LIMIT = 100;

interface RequirementSourcesCardProps {
  requirement: RequirementWithMetrics;
  editable: boolean;
  onChanged: () => Promise<void>;
}

function errorText(err: unknown, fallback: string) {
  return err instanceof Error ? `${fallback}: ${err.message}` : fallback;
}

/** Sources a requirement comes from: uploads, Knowledge sources and links. */
export default function RequirementSourcesCard({
  requirement,
  editable,
  onChanged,
}: RequirementSourcesCardProps) {
  const notifications = useNotifications();
  const sources = useMemo(
    () => requirement.sources ?? [],
    [requirement.sources]
  );
  const requirementId = requirement.id as UUID;

  const [addAnchor, setAddAnchor] = useState<HTMLElement | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [urlOpen, setUrlOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerRows, setPickerRows] = useState<Source[]>([]);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [noteTarget, setNoteTarget] = useState<RequirementSourceLink | null>(
    null
  );

  const link = useCallback(
    async (sourceId: string, note: string | null = null) => {
      await new ApiClientFactory()
        .getRequirementClient()
        .linkSource(requirementId, sourceId, note);
    },
    [requirementId]
  );

  const handleUnlink = async (source: RequirementSourceLink) => {
    try {
      await new ApiClientFactory()
        .getRequirementClient()
        .unlinkSource(requirementId, source.id);
      await onChanged();
    } catch (err) {
      notifications.show(errorText(err, 'Failed to remove the source'), {
        severity: 'error',
      });
    }
  };

  const openPicker = async () => {
    setPickerOpen(true);
    setPickerLoading(true);
    try {
      const page = await new ApiClientFactory()
        .getSourcesClient()
        .getSources({ skip: 0, limit: KNOWLEDGE_PICKER_LIMIT });
      setPickerRows(page.data);
    } catch {
      setPickerRows([]);
    } finally {
      setPickerLoading(false);
    }
  };

  const linkedIds = useMemo(
    () => new Set(sources.map(s => String(s.id))),
    [sources]
  );

  const pickerColumns = useMemo<GridColDef[]>(
    () => [
      { field: 'title', headerName: 'Title', flex: 1, minWidth: 180 },
      {
        field: 'source_type',
        headerName: 'Type',
        width: 140,
        valueGetter: (_value: unknown, row: GridRowModel) =>
          (row.source_type as { type_value?: string } | undefined)
            ?.type_value ?? '',
      },
    ],
    []
  );

  return (
    <Box
      id={SOURCES_CARD_ID}
      sx={{ scrollMarginTop: theme => theme.spacing(10) }}
    >
      <SectionCard
        title="Sources"
        subtitle="Where this rule comes from"
        actions={
          editable ? (
            <Button
              size="small"
              variant="outlined"
              startIcon={<AddIcon sx={{ fontSize: 20 }} />}
              onClick={e => setAddAnchor(e.currentTarget)}
              aria-haspopup="menu"
              sx={sectionEditButtonSx}
            >
              Add source
            </Button>
          ) : undefined
        }
      >
        {sources.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No sources yet. Upload a policy, link a Knowledge source, or paste a
            link to a regulation.
          </Typography>
        ) : (
          <Stack spacing={1}>
            {sources.map(source => (
              <SourceRow
                key={source.id}
                source={source}
                editable={editable}
                onEditNote={() => setNoteTarget(source)}
                onRemove={() => void handleUnlink(source)}
              />
            ))}
          </Stack>
        )}
      </SectionCard>

      <Menu
        anchorEl={addAnchor}
        open={addAnchor !== null}
        onClose={() => setAddAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        // Sized to the button it opens from, like ArchitectChart's export menu.
        slotProps={{
          list: {
            dense: true,
            sx: { '& .MuiMenuItem-root': { typography: 'body2' } },
          },
        }}
      >
        <MenuItem
          onClick={() => {
            setAddAnchor(null);
            setUploadOpen(true);
          }}
        >
          Upload a file
        </MenuItem>
        <MenuItem
          onClick={() => {
            setAddAnchor(null);
            void openPicker();
          }}
        >
          From Knowledge
        </MenuItem>
        <MenuItem
          onClick={() => {
            setAddAnchor(null);
            setUrlOpen(true);
          }}
        >
          Link (URL)
        </MenuItem>
      </Menu>

      <UploadSourceDrawer
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={async source => {
          try {
            await link(String(source.id));
            await onChanged();
          } catch (err) {
            notifications.show(
              errorText(err, 'Uploaded, but linking the source failed'),
              { severity: 'error' }
            );
          }
        }}
      />

      <AssignEntityDrawer
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        title="Link Knowledge Sources"
        rows={pickerRows.filter(r => !linkedIds.has(String(r.id)))}
        columns={pickerColumns}
        loading={pickerLoading}
        getRowId={row => String(row.id)}
        saveButtonText="Link"
        searchPlaceholder="Search sources…"
        onAssign={async ids => {
          try {
            await Promise.all(ids.map(id => link(id)));
            await onChanged();
            setPickerOpen(false);
          } catch (err) {
            notifications.show(errorText(err, 'Failed to link sources'), {
              severity: 'error',
            });
          }
        }}
      />

      <UrlSourceDrawer
        open={urlOpen}
        onClose={() => setUrlOpen(false)}
        onCreated={async (sourceId, note) => {
          await link(sourceId, note);
          await onChanged();
        }}
      />

      <NoteDrawer
        source={noteTarget}
        onClose={() => setNoteTarget(null)}
        onSave={async note => {
          if (!noteTarget) return;
          await link(String(noteTarget.id), note);
          await onChanged();
        }}
      />
    </Box>
  );
}

function SourceRow({
  source,
  editable,
  onEditNote,
  onRemove,
}: {
  source: RequirementSourceLink;
  editable: boolean;
  onEditNote: () => void;
  onRemove: () => void;
}) {
  const typeLabel = source.source_type?.type_value;
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        px: 1.5,
        py: 1.25,
        border: 1,
        borderColor: 'divider',
        borderRadius: BORDER_RADIUS.md,
      }}
    >
      <DescriptionOutlinedIcon color="primary" />
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <MuiLink
          component={Link}
          href={`/knowledge/${source.id}`}
          underline="hover"
          sx={{ fontWeight: 600, display: 'block' }}
          noWrap
        >
          {source.title}
        </MuiLink>
        {(source.note || source.url) && (
          <Typography variant="caption" color="text.secondary" noWrap>
            {[source.note, source.url].filter(Boolean).join(' · ')}
          </Typography>
        )}
      </Box>
      {typeLabel && <GridBadge label={typeLabel} />}
      {source.url && (
        <Tooltip title="Open link">
          <IconButton
            size="small"
            component="a"
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Open ${source.title}`}
          >
            <OpenInNewIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      )}
      {editable && (
        <>
          <Tooltip title={source.note ? 'Edit note' : 'Add note'}>
            <IconButton
              size="small"
              onClick={onEditNote}
              aria-label={`Edit note for ${source.title}`}
            >
              <EditOutlinedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Remove">
            <IconButton
              size="small"
              onClick={onRemove}
              aria-label={`Remove ${source.title}`}
            >
              <LinkOffIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </>
      )}
    </Box>
  );
}

function NoteDrawer({
  source,
  onClose,
  onSave,
}: {
  source: RequirementSourceLink | null;
  onClose: () => void;
  onSave: (note: string | null) => Promise<void>;
}) {
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | undefined>();

  React.useEffect(() => {
    setNote(source?.note ?? '');
    setError(undefined);
  }, [source]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(note.trim() || null);
      onClose();
    } catch (err) {
      setError(errorText(err, 'Failed to save the note'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <BaseDrawer
      open={source !== null}
      onClose={onClose}
      title="Edit Note"
      onSave={handleSave}
      saveButtonText="Save"
      loading={saving}
      error={error}
    >
      <TextField
        fullWidth
        label="Note"
        placeholder="e.g. section 4.2"
        value={note}
        onChange={e => setNote(e.target.value)}
        helperText={`Where in “${source?.title ?? 'the source'}” this rule comes from`}
        sx={drawerOutlinedFieldSx}
      />
    </BaseDrawer>
  );
}

function UrlSourceDrawer({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (sourceId: string, note: string | null) => Promise<void>;
}) {
  const { data: websiteTypes } = useTypeLookups(
    "type_name eq 'SourceType' and type_value eq 'Website'",
    open
  );
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | undefined>();

  React.useEffect(() => {
    if (!open) return;
    setTitle('');
    setUrl('');
    setNote('');
    setError(undefined);
  }, [open]);

  const urlValid = /^https?:\/\/\S+$/i.test(url.trim());

  const handleSave = async () => {
    setSaving(true);
    setError(undefined);
    try {
      const source = await new ApiClientFactory()
        .getSourcesClient()
        .createSource({
          title: title.trim(),
          source_type_id: websiteTypes?.[0]?.id,
          source_metadata: { url: url.trim() },
        });
      await onCreated(String(source.id), note.trim() || null);
      onClose();
    } catch (err) {
      setError(errorText(err, 'Failed to add the link'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <BaseDrawer
      open={open}
      onClose={onClose}
      title="Add Link"
      onSave={handleSave}
      saveButtonText="Add Link"
      saveDisabled={!title.trim() || !urlValid}
      loading={saving}
      error={error}
    >
      <Box sx={drawerFieldsSx}>
        <TextField
          label="Title"
          required
          fullWidth
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="e.g. Directive 2014/65/EU, Article 25"
          helperText="A name for the page you link to"
          sx={drawerOutlinedFieldSx}
        />
        <TextField
          label="URL"
          required
          fullWidth
          value={url}
          onChange={e => setUrl(e.target.value)}
          placeholder="https://"
          error={!!url && !urlValid}
          helperText={
            url && !urlValid
              ? 'Enter a full http(s) link.'
              : 'Saved as a Website source in Knowledge'
          }
          sx={drawerOutlinedFieldSx}
        />
        <TextField
          label="Note"
          fullWidth
          value={note}
          onChange={e => setNote(e.target.value)}
          placeholder="e.g. section 4.2"
          helperText="Optional. Where on the page this rule comes from"
          sx={drawerOutlinedFieldSx}
        />
      </Box>
    </BaseDrawer>
  );
}
