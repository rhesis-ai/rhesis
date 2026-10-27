'use client';

import React from 'react';
import NextLink from 'next/link';
import Markdown from 'markdown-to-jsx';
import { Box, Link, useTheme, type TypographyProps } from '@mui/material';

interface MarkdownContentProps {
  /** The markdown content to render */
  content: string;
  /** Typography variant to use for body text (default: 'body1') */
  variant?: TypographyProps['variant'];
  /**
   * Render an internal link as plain text unless it points at an entity by a
   * real id. For model-written text, where a link may carry an id it made up.
   */
  entityLinksOnly?: boolean;
}

// A UUID, or the 12-character nano id every entity also carries.
const ENTITY_ID =
  /^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9A-Za-z]{12})$/i;

/** `/metrics/<uuid>` passes; `/metrics/tone-id-placeholder` does not. */
export function isEntityLink(href: string): boolean {
  const [, route, id, ...rest] = href.split(/[?#]/)[0].split('/');
  return (
    Boolean(route) && Boolean(id) && rest.length === 0 && ENTITY_ID.test(id)
  );
}

function isInternalPath(href: string | undefined): href is string {
  if (!href) return false;
  return href.startsWith('/') && !href.startsWith('//');
}

/**
 * Repair markdown link patterns that LLMs sometimes break:
 * - Backtick-wrapped links: `[text](url)` → [text](url)
 * - Escaped brackets: \[text\](url) → [text](url)
 * - Whitespace between ] and (: [text] (url) → [text](url)
 * Only targets URLs starting with / or http(s):// to avoid false positives.
 */
function normalizeMarkdownLinks(content: string): string {
  return content
    .replace(/`(\[([^\]`]+)\]\(((?:\/|https?:\/\/)[^)\s`]+)\))`/g, '[$2]($3)')
    .replace(
      /\\?\[([^\]\\]+)\\?\]\s*\(((?:\/|https?:\/\/)[^)\s]+)\)/g,
      '[$1]($2)'
    );
}

function SmartLink({
  href,
  children,
  entityLinksOnly,
  ...props
}: React.AnchorHTMLAttributes<HTMLAnchorElement> & {
  entityLinksOnly?: boolean;
}) {
  if (isInternalPath(href) && entityLinksOnly && !isEntityLink(href)) {
    return <>{children}</>;
  }
  if (isInternalPath(href)) {
    return (
      <Link component={NextLink} href={href} target="_blank" {...props}>
        {children}
      </Link>
    );
  }
  return (
    <Link href={href} target="_blank" rel="noopener noreferrer" {...props}>
      {children}
    </Link>
  );
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
  entityLinksOnly = false,
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
        '& li > input[type="checkbox"]': {
          mr: 0.75,
          verticalAlign: 'middle',
          accentColor: theme.palette.success.main,
          pointerEvents: 'none',
        },
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
          disableParsingRawHTML: true,
          overrides: {
            a: {
              component: SmartLink,
              props: { entityLinksOnly },
            },
          },
        }}
      >
        {typeof content === 'string'
          ? normalizeMarkdownLinks(content)
          : '```json\n' + JSON.stringify(content, null, 2) + '\n```'}
      </Markdown>
    </Box>
  );
}
