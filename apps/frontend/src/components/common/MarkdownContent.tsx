'use client';

import React from 'react';
import Markdown from 'markdown-to-jsx';
import { Box, Link, useTheme } from '@mui/material';
import type { TypographyProps } from '@mui/material';

interface MarkdownContentProps {
  /** The markdown content to render */
  content: string;
  /** Typography variant to use for body text (default: 'body1') */
  variant?: TypographyProps['variant'];
}

/**
 * MarkdownContent Component
 *
 * Renders markdown content using markdown-to-jsx with simple HTML elements.
 * Uses the specified typography variant's font size for consistent sizing.
 */
export default function MarkdownContent({
  content,
  variant = 'body1',
}: MarkdownContentProps) {
  const theme = useTheme();

  // Get the actual font size and line height from the theme for the specified variant
  const variantStyle =
    theme.typography[variant as keyof typeof theme.typography];
  const fontSize =
    typeof variantStyle === 'object' && 'fontSize' in variantStyle
      ? variantStyle.fontSize
      : theme.typography.body1.fontSize;
  const lineHeight =
    typeof variantStyle === 'object' && 'lineHeight' in variantStyle
      ? variantStyle.lineHeight
      : theme.typography.body1.lineHeight;

  return (
    <Box
      sx={{
        // Set base font size and line height from the variant
        fontSize,
        lineHeight,
        // Headings scale relative to the base font size using theme multipliers
        '& h1': {
          fontSize: theme.typography.markdownH1Scale,
          fontWeight: theme.typography.fontWeightBold,
          mt: 1.5,
          mb: 0.75,
        },
        '& h2': {
          fontSize: theme.typography.markdownH2Scale,
          fontWeight: theme.typography.fontWeightBold,
          mt: 1.25,
          mb: 0.5,
        },
        '& h3': {
          fontSize: theme.typography.markdownH3Scale,
          fontWeight: theme.typography.fontWeightMedium,
          mt: 1,
          mb: 0.5,
        },
        '& h4, & h5, & h6': {
          fontSize: theme.typography.markdownH4Scale,
          fontWeight: theme.typography.fontWeightMedium,
          mt: 1,
          mb: 0.5,
        },
        // Spacing adjustments
        '& > *:first-of-type': { mt: 0 },
        '& > *:last-child': { mb: 0 },
        '& p': { mb: 1, '&:last-child': { mb: 0 } },
        '& ul, & ol': { pl: 2.5, mb: 1, '&:last-child': { mb: 0 } },
        '& li': { mb: 0.5 },
        '& pre': {
          bgcolor: 'action.hover',
          p: 1.5,
          borderRadius: theme.shape.borderRadius * 0.25,
          overflow: 'auto',
          mb: 1,
          '&:last-child': { mb: 0 },
        },
        '& code': {
          fontFamily: theme.typography.fontFamily,
          bgcolor: 'action.hover',
          px: 0.5,
          py: 0.25,
          borderRadius: theme.shape.borderRadius * 0.125,
        },
        '& pre code': {
          bgcolor: 'inherit',
          p: 0,
        },
        '& blockquote': {
          borderLeft: 3,
          borderColor: 'primary.main',
          pl: 2,
          ml: 0,
          my: 1,
          fontStyle: 'italic',
          color: 'text.secondary',
        },
        '& a': {
          color: 'primary.main',
          textDecoration: 'underline',
          '&:hover': { textDecoration: 'none' },
        },
        '& table': {
          borderCollapse: 'collapse',
          width: 1,
          mb: 1,
        },
        '& th, & td': {
          border: 1,
          borderColor: 'divider',
          p: 1,
          textAlign: 'left',
        },
        '& th': {
          bgcolor: 'action.hover',
          fontWeight: 'fontWeightMedium',
        },
        '& hr': {
          border: 0,
          borderTop: 1,
          borderColor: 'divider',
          my: 2,
        },
      }}
    >
      <Markdown
        options={{
          overrides: {
            a: {
              component: Link,
              props: {
                target: '_blank',
                rel: 'noopener noreferrer',
              },
            },
          },
        }}
      >
        {content}
      </Markdown>
    </Box>
  );
}
