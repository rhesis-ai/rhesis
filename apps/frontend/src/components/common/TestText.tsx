'use client';

import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import MarkdownContent from '@/components/common/MarkdownContent';
import { JsonPreview } from '@/app/(protected)/endpoints/components/JsonPreview';
import { testPreviewSx } from '@/app/(protected)/endpoints/components/endpoint-styles';
import { looksLikeMarkdown, parseJsonString } from '@/utils/message-content';

// Helper function to render text with proper list formatting
export const renderFormattedText = (text: string) => {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let currentParagraph: string[] = [];

  lines.forEach((line, index) => {
    const trimmedLine = line.trim();

    const numbered = /^(\d+)[.)]\s+(.*)$/.exec(trimmedLine);
    if (trimmedLine.startsWith('- ') || numbered) {
      if (currentParagraph.length > 0) {
        const paragraphKey = `p-${index}-${currentParagraph.join(' ').substring(0, 20)}`;
        elements.push(
          <Typography key={paragraphKey} variant="body2" sx={{ mb: 1 }}>
            {currentParagraph.join(' ')}
          </Typography>
        );
        currentParagraph = [];
      }

      const bulletKey = `bullet-${index}-${trimmedLine.substring(0, 20)}`;
      elements.push(
        <Box key={bulletKey} sx={{ display: 'flex', gap: 1, mb: 0.5, pl: 2 }}>
          <Typography variant="body2">
            {numbered ? `${numbered[1]}.` : '•'}
          </Typography>
          <Typography variant="body2" sx={{ flex: 1 }}>
            {numbered ? numbered[2] : trimmedLine.substring(2).trim()}
          </Typography>
        </Box>
      );
    } else if (trimmedLine) {
      currentParagraph.push(trimmedLine);
    } else if (currentParagraph.length > 0) {
      const paragraphKey = `p-${index}-${currentParagraph.join(' ').substring(0, 20)}`;
      elements.push(
        <Typography key={paragraphKey} variant="body2" sx={{ mb: 1 }}>
          {currentParagraph.join(' ')}
        </Typography>
      );
      currentParagraph = [];
    }
  });

  if (currentParagraph.length > 0) {
    elements.push(
      <Typography key="p-final" variant="body2">
        {currentParagraph.join(' ')}
      </Typography>
    );
  }

  return <>{elements}</>;
};

/** A small uppercase label over plain text, lighter than ViewField's filled box. */
export function SectionField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const theme = useTheme();
  return (
    <Box>
      <Typography
        variant="caption"
        component="h4"
        color="text.secondary"
        sx={{
          display: 'block',
          mb: 0.75,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: theme.typography.overline.letterSpacing,
        }}
      >
        {label}
      </Typography>
      {children}
    </Box>
  );
}

const ABBREVIATION = /\b(e\.g|i\.e|etc|vs|Dr|Mr|Mrs|Ms|No)\.$/i;

/**
 * One line of separate sentences ("Must not X. Must not Y.") as "- " lines, so
 * renderFormattedText lists them. Text that already has lines is left alone.
 */
export function asSentenceList(text: string): string {
  if (text.includes('\n')) return text;
  const sentences = text
    .trim()
    // A line break after each sentence end, then split on it: no regex lookbehind needed.
    .replace(/([.!?])\s+(?=[A-Z])/g, '$1\n')
    .split('\n')
    .reduce<string[]>((acc, part) => {
      const prev = acc[acc.length - 1];
      if (prev && ABBREVIATION.test(prev))
        acc[acc.length - 1] = `${prev} ${part}`;
      else acc.push(part);
      return acc;
    }, []);
  return sentences.length > 1 ? sentences.map(x => `- ${x}`).join('\n') : text;
}

/** Text a test author wrote: JSON, markdown or plain. */
export function TextContent({ text }: { text: string }) {
  const parsed = parseJsonString(text);
  if (parsed !== null) {
    return (
      <Box component="pre" sx={{ ...testPreviewSx, minHeight: 'unset', m: 0 }}>
        <JsonPreview value={parsed} />
      </Box>
    );
  }
  return looksLikeMarkdown(text) ? (
    <MarkdownContent content={text} variant="body2" />
  ) : (
    <Typography
      variant="body2"
      sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0 }}
    >
      {text}
    </Typography>
  );
}
