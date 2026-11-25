'use client';

import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import ScheduleIcon from '@mui/icons-material/Schedule';
import Link from 'next/link';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { SCHEDULE_TRIGGER, scheduleLink } from '@/constants/test-run-schedules';

export interface RunSchedule {
  id: string;
  name: string;
}

/** The schedule that started this run, if any and if it still exists. */
export function scheduleOf(run: TestRunDetail): RunSchedule | null {
  if (run.attributes?.trigger !== SCHEDULE_TRIGGER.SCHEDULE) return null;
  const config = run.test_configuration;
  const schedule = config?.attributes?.schedule;
  if (!config?.id || typeof schedule !== 'object' || schedule === null) {
    return null;
  }
  const name = (schedule as { name?: unknown }).name;
  return typeof name === 'string' ? { id: String(config.id), name } : null;
}

export default function RunNameCell({
  name,
  schedule,
}: {
  name: string;
  schedule: RunSchedule | null;
}) {
  if (!schedule) return <>{name}</>;
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        height: '100%',
        lineHeight: 1.3,
      }}
    >
      <Typography variant="body2" noWrap>
        {name}
      </Typography>
      <Typography
        variant="caption"
        color="text.secondary"
        noWrap
        title={`From schedule: ${schedule.name}`}
        sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
      >
        <ScheduleIcon sx={{ fontSize: 'inherit' }} />
        From schedule:{' '}
        <Box
          component={Link}
          href={scheduleLink(schedule.id)}
          onClick={event => event.stopPropagation()}
          sx={{ color: 'inherit' }}
        >
          {schedule.name}
        </Box>
      </Typography>
    </Box>
  );
}
