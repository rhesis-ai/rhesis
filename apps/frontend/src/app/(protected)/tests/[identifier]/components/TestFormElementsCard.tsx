'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import EditableSection from '@/components/common/EditableSection';
import BaseTag from '@/components/common/BaseTag';
import FileAttachmentList from '@/components/common/FileAttachmentList';
import MultiFileUpload from '@/components/common/MultiFileUpload';
import { TestDetail } from '@/utils/api-client/interfaces/tests';
import { useNotifications } from '@/components/common/NotificationContext';
import { EntityType, Tag } from '@/utils/api-client/interfaces/tag';
import { TagsClient } from '@/utils/api-client/tags-client';
import { useFiles } from '@/hooks/useFiles';
import { UUID } from 'crypto';

interface TagsDraft {
  tagNames: string[];
}

interface TestFormElementsCardProps {
  sessionToken: string;
  test: TestDetail;
  onUpdate?: () => void;
}

export default function TestFormElementsCard({
  sessionToken,
  test,
  onUpdate: _onUpdate,
}: TestFormElementsCardProps) {
  const notifications = useNotifications();
  const [pendingFiles, setPendingFiles] = React.useState<File[]>([]);
  const [isUploading, setIsUploading] = React.useState(false);

  const {
    files: attachedFiles,
    isLoading: filesLoading,
    totalSizeBytes: existingFilesSize,
    uploadFiles: uploadFilesToServer,
    deleteFile: deleteAttachedFile,
  } = useFiles({
    entityId: test.id,
    entityType: 'Test',
    sessionToken,
  });

  const initialTagNames = (test.tags ?? []).map((t: Tag) => t.name);

  const initialDraft: TagsDraft = { tagNames: initialTagNames };

  const handleSave = async (draft: TagsDraft) => {
    const tagsClient = new TagsClient(sessionToken);
    const currentNames = initialTagNames;
    const newNames = draft.tagNames;

    const tagsToRemove = currentNames.filter(n => !newNames.includes(n));
    const tagsToAdd = newNames.filter(n => !currentNames.includes(n));

    for (const name of tagsToRemove) {
      const tag = test.tags?.find((t: Tag) => t.name === name);
      if (tag) {
        await tagsClient.removeTagFromEntity(
          EntityType.TEST,
          test.id as UUID,
          tag.id
        );
      }
    }

    for (const name of tagsToAdd) {
      await tagsClient.assignTagToEntity(EntityType.TEST, test.id as UUID, {
        name,
        organization_id: test.organization_id,
        user_id: test.user_id,
      });
    }

    notifications.show('Tags updated', {
      severity: 'success',
      autoHideDuration: 4000,
    });
  };

  const handleFilesSelect = React.useCallback(
    async (files: File[]) => {
      setPendingFiles([]);
      setIsUploading(true);
      try {
        await uploadFilesToServer(files);
      } finally {
        setIsUploading(false);
      }
    },
    [uploadFilesToServer]
  );

  return (
    <EditableSection
      title="Tags & attachments"
      initialValue={initialDraft}
      onSave={handleSave}
      isDirty={(draft, initial) =>
        JSON.stringify(draft.tagNames.slice().sort()) !==
        JSON.stringify(initial.tagNames.slice().sort())
      }
    >
      {({ draft, setDraft, isEditing }) => (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Tags */}
          {isEditing ? (
            <BaseTag
              value={draft.tagNames}
              onChange={tagNames => setDraft(d => ({ ...d, tagNames }))}
              label="Tags"
              placeholder="Add tags (press Enter or comma to add)"
              helperText="These tags help categorize and find this test"
              chipColor="default"
              addOnBlur
              delimiters={[',', 'Enter']}
              size="medium"
              fullWidth
            />
          ) : (
            /* View mode: outlined box (Figma 1222:35827) — chips shown without × */
            <Box>
              <Box
                sx={{
                  border: '1px solid #c1c7d1',
                  borderRadius: '4px',
                  pl: '16px',
                  pr: '12px',
                  py: '16px',
                  display: 'flex',
                  gap: '10px',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  minHeight: 56,
                }}
              >
                {draft.tagNames.length > 0 ? (
                  draft.tagNames.map(tag => (
                    <Box
                      key={tag}
                      sx={{
                        bgcolor: '#f3f4f6',
                        borderRadius: '4px',
                        px: '12px',
                        py: '2px',
                      }}
                    >
                      <Typography
                        sx={{
                          fontSize: 14,
                          lineHeight: '22px',
                          color: '#2a2e36',
                        }}
                      >
                        {tag}
                      </Typography>
                    </Box>
                  ))
                ) : (
                  <Typography
                    sx={{ fontSize: 16, lineHeight: '24px', color: '#545a65' }}
                  >
                    Tags
                  </Typography>
                )}
              </Box>
              <Typography
                sx={{
                  fontSize: 12,
                  lineHeight: '18px',
                  color: 'text.secondary',
                  px: '14px',
                  pt: '3px',
                }}
              >
                These tags help categorize and find this test
              </Typography>
            </Box>
          )}

          {/* Attachments */}
          <Box>
            <Typography
              sx={{
                fontSize: 18,
                fontWeight: 700,
                lineHeight: '25px',
                color: 'text.primary',
                mb: '2px',
              }}
            >
              Attachments
            </Typography>
            <Typography
              sx={{
                fontSize: 12,
                lineHeight: '18px',
                color: 'text.secondary',
                display: 'block',
                mb: 2,
              }}
            >
              Images, PDFs or audio files attached to this test
            </Typography>
            <FileAttachmentList
              files={attachedFiles}
              sessionToken={sessionToken}
              isLoading={filesLoading}
              onDelete={deleteAttachedFile}
            />
            <MultiFileUpload
              selectedFiles={pendingFiles}
              onFilesSelect={handleFilesSelect}
              onFileRemove={idx =>
                setPendingFiles(prev => prev.filter((_, i) => i !== idx))
              }
              existingFilesSize={existingFilesSize}
              disabled={isUploading}
            />
          </Box>
        </Box>
      )}
    </EditableSection>
  );
}
