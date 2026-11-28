'use client';

import React, { useEffect, useState } from 'react';
import { Box, ButtonBase, Collapse, Typography } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { drawerFieldsSx } from '@/components/common/drawerFormFieldSx';
import { BORDER_RADIUS } from '@/styles/theme';
import { formSectionHeadlineSx } from '@/components/common/FormSectionDivider';

interface Props {
  title: string;
  /** One line shown beside the title while the section is folded. */
  summary?: React.ReactNode;
  defaultExpanded?: boolean;
  /** Folds the section when this turns true, e.g. once its field is filled for the user. */
  collapse?: boolean;
  children: React.ReactNode;
}

/**
 * A run drawer section: a FormSectionDivider-style heading over a divider line,
 * which folds the section down to its title and a one-line summary.
 */
export default function RunDrawerSection({
  title,
  summary,
  defaultExpanded = true,
  collapse = false,
  children,
}: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const contentId = React.useId();

  useEffect(() => {
    if (collapse) setExpanded(false);
  }, [collapse]);

  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider', pb: 2 }}>
      <ButtonBase
        onClick={() => setExpanded(prev => !prev)}
        aria-expanded={expanded}
        aria-controls={contentId}
        sx={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          py: 1,
          textAlign: 'left',
          borderRadius: BORDER_RADIUS.xs,
        }}
      >
        <Typography
          component="span"
          sx={{ ...formSectionHeadlineSx, flexShrink: 0 }}
        >
          {title}
        </Typography>
        <Typography
          component="span"
          variant="body2"
          color="text.secondary"
          noWrap
          sx={{ flex: 1, textAlign: 'right' }}
        >
          {!expanded && summary}
        </Typography>
        <ExpandMoreIcon
          fontSize="small"
          sx={{
            color: 'text.secondary',
            transform: expanded ? 'rotate(180deg)' : 'none',
            transition: theme => theme.transitions.create('transform'),
          }}
        />
      </ButtonBase>
      {/* Folded fields stay mounted, so their state and pending requests survive. */}
      <Collapse in={expanded} id={contentId}>
        <Box sx={{ pt: 2.5, pb: 1 }}>
          <Box sx={drawerFieldsSx}>{children}</Box>
        </Box>
      </Collapse>
    </Box>
  );
}
