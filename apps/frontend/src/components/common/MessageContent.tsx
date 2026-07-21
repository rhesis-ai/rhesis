'use client';

import React from 'react';
import { Box, Typography, TypographyProps } from '@mui/material';
import MarkdownContent from '@/components/common/MarkdownContent';
import { JsonPreview } from '@/app/(protected)/endpoints/components/JsonPreview';
import { testPreviewSx } from '@/app/(protected)/endpoints/components/endpoint-styles';
import { looksLikeMarkdown, parseJsonString } from '@/utils/message-content';

interface MessageContentProps {
  content: string;
  variant?: TypographyProps['variant'];
}

/** Renders message text as JSON preview, markdown, or plain pre-wrapped text. */
export default function MessageContent({
  content,
  variant = 'body2',
}: MessageContentProps) {
  const parsed = parseJsonString(content);
  if (parsed !== null) {
    return (
      <Box component="pre" sx={{ ...testPreviewSx, minHeight: 'unset', m: 0 }}>
        <JsonPreview value={parsed} />
      </Box>
    );
  }
  if (looksLikeMarkdown(content)) {
    return <MarkdownContent content={content} variant={variant} />;
  }
  return (
    <Typography
      variant={variant}
      sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0 }}
    >
      {content}
    </Typography>
  );
}
