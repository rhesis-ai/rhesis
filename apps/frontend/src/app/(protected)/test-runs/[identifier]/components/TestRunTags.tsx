'use client';

import React, { useState, useEffect } from 'react';
import { Paper } from '@mui/material';
import type { Theme } from '@mui/material/styles';
import BaseTag from '@/components/common/BaseTag';
import { drawerTagFieldSx } from '@/components/common/drawerFormFieldSx';
import { EntityType } from '@/utils/api-client/interfaces/tag';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';

interface TestRunTagsProps {
  testRun: TestRunDetail;
}

export default function TestRunTags({ testRun }: TestRunTagsProps) {
  const [tagNames, setTagNames] = useState<string[]>([]);

  useEffect(() => {
    if (testRun.tags) {
      setTagNames(testRun.tags.map(tag => tag.name));
    } else {
      setTagNames([]);
    }
  }, [testRun.tags]);

  return (
    <Paper
      elevation={0}
      sx={{
        p: '30px',
        borderRadius: BORDER_RADIUS.md,
        boxShadow: (theme: Theme) =>
          theme.palette.mode === 'light' ? ELEVATION.xs : 'none',
        bgcolor: (theme: Theme) =>
          theme.palette.mode === 'light'
            ? '#ffffff'
            : theme.palette.greyscale.surface1,
        border: (theme: Theme) => `1px solid ${theme.palette.greyscale.border}`,
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
      }}
    >
      {/* No section heading: the field's own label already says "Tags", and
          a card whose only content is one field does not need the word twice.
          Matches TestResultTags, the sibling section on this page. Keeping the
          label rather than the heading is deliberate -- it is what gives the
          input its accessible name. */}
      <BaseTag
        value={tagNames}
        onChange={setTagNames}
        label="Tags"
        placeholder="Add tags (press Enter or comma to add)"
        chipColor="default"
        addOnBlur
        delimiters={[',', 'Enter']}
        size="small"
        margin="none"
        fullWidth
        entityType={EntityType.TEST_RUN}
        entity={testRun}
        sx={drawerTagFieldSx}
      />
    </Paper>
  );
}
