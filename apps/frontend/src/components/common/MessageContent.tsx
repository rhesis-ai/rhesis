'use client';

import React from 'react';
import { Box, Typography, TypographyProps } from '@mui/material';
import MarkdownContent from '@/components/common/MarkdownContent';
import { JsonPreview } from '@/app/(protected)/endpoints/components/JsonPreview';
import { testPreviewSx } from '@/app/(protected)/endpoints/components/endpoint-styles';
import { looksLikeMarkdown, parseJsonString } from '@/utils/message-content';

interface MessageContentProps {
  content: unknown;
  variant?: TypographyProps['variant'];
}

function renderJsonPreview(value: unknown) {
  return (
    <Box component="pre" sx={{ ...testPreviewSx, minHeight: 'unset', m: 0 }}>
      <JsonPreview value={value} />
    </Box>
  );
}

/** Renders message text as JSON preview, markdown, or plain pre-wrapped text. */
export default function MessageContent({
  content,
  variant = 'body2',
}: MessageContentProps) {
  if (content !== null && typeof content === 'object') {
    return renderJsonPreview(content);
  }

  const text = content == null ? '' : String(content);
  const parsed = parseJsonString(text);
  if (parsed !== null) {
    return renderJsonPreview(parsed);
  }
  if (looksLikeMarkdown(text)) {
    return <MarkdownContent content={text} variant={variant} />;
  }
  return (
    <Typography
      variant={variant}
      sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0 }}
    >
      {text}
    </Typography>
  );
}
