import * as React from 'react';
import Box from '@mui/material/Box';
import { CODE_FONT_SIZE, rem } from '@/styles/theme-constants';

/**
 * Splits a target summary into plain text and the names it quotes in
 * backticks: "each tool call named `issue_refund`" gives three parts, the
 * middle one code. An unclosed backtick stays as text.
 */
export function summaryParts(
  summary: string
): { text: string; code: boolean }[] {
  const pieces = summary.split('`');
  // An even count means an odd number of backticks: the last one is unclosed.
  const closed = pieces.length % 2 === 1;
  return pieces
    .map((text, i) => ({ text, code: i % 2 === 1 }))
    .flatMap((part, i, all) =>
      !closed && i === all.length - 1 && part.code
        ? [{ text: `\`${part.text}`, code: false }]
        : [part]
    )
    .filter(part => part.text !== '');
}

/** A summary without its backticks, for labels that can't hold markup. */
export function summaryPlainText(summary: string): string {
  return summary.split('`').join('');
}

/** A target summary from the API, its quoted names set as code. */
export default function TargetSummaryText({ summary }: { summary: string }) {
  return (
    <>
      {summaryParts(summary).map((part, i) =>
        part.code ? (
          <Box
            // Parts never reorder: the summary is rendered whole each time.
            // eslint-disable-next-line react/no-array-index-key
            key={i}
            component="code"
            sx={{
              fontFamily: theme => theme.typography.fontFamilyCode,
              fontSize: rem(CODE_FONT_SIZE),
            }}
          >
            {part.text}
          </Box>
        ) : (
          // eslint-disable-next-line react/no-array-index-key
          <React.Fragment key={i}>{part.text}</React.Fragment>
        )
      )}
    </>
  );
}
