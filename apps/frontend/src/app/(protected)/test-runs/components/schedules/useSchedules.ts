'use client';

import { useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { scheduleKeys, testRunKeys } from '@/constants/query-keys';
import { SCHEDULES_REFETCH_MS } from '@/constants/test-run-schedules';
import { useNotifications } from '@/components/common/NotificationContext';
import { getApiErrorMessage } from '@/utils/error-utils';
import type { TestRunSchedule } from '@/utils/api-client/interfaces/test-run-schedule';

const client = () => new ApiClientFactory().getTestRunSchedulesClient();

/** Every schedule, refetched each minute while the tab is visible. */
export function useSchedules(enabled = true) {
  return useQuery({
    queryKey: scheduleKeys.all(),
    queryFn: () => client().list(),
    refetchInterval: SCHEDULES_REFETCH_MS,
    refetchIntervalInBackground: false,
    enabled,
  });
}

export function useScheduleDetail(id: string | null) {
  return useQuery({
    queryKey: scheduleKeys.detail(id ?? ''),
    queryFn: () => client().get(id ?? ''),
    enabled: Boolean(id),
  });
}

/** Quick actions on a schedule; each refreshes the schedule lists and says what happened. */
export function useScheduleActions() {
  const queryClient = useQueryClient();
  const notifications = useNotifications();

  return useMemo(() => {
    const refresh = () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: scheduleKeys.all() }),
        queryClient.invalidateQueries({ queryKey: testRunKeys.all() }),
      ]);

    const run = async <T>(
      action: () => Promise<T>,
      success: (result: T) => string,
      failure: string
    ): Promise<T | null> => {
      try {
        const result = await action();
        await refresh();
        notifications.show(success(result), { severity: 'success' });
        return result;
      } catch (error) {
        notifications.show(getApiErrorMessage(error, failure), {
          severity: 'error',
        });
        return null;
      }
    };

    return {
      refresh,
      run,
      pause: (s: TestRunSchedule) =>
        run(
          () => client().pause(s.id),
          () => `${s.name} paused`,
          'Could not pause it'
        ),
      resume: (s: TestRunSchedule) =>
        run(
          () => client().resume(s.id),
          () => `${s.name} resumed`,
          'Could not resume it'
        ),
      skipNext: (s: TestRunSchedule) =>
        run(
          () => client().skipNext(s.id),
          () => `The next run of ${s.name} is skipped`,
          'Could not skip the next run'
        ),
      runNow: (s: TestRunSchedule) =>
        run(
          () => client().runNow(s.id),
          () => `${s.name} started`,
          'Could not start a run'
        ),
      takeOver: (s: TestRunSchedule) =>
        run(
          () => client().takeOver(s.id),
          () => `You now own ${s.name}`,
          'Could not take it over'
        ),
      remove: (s: TestRunSchedule) =>
        run(
          () => client().remove(s.id),
          () => `${s.name} deleted`,
          'Could not delete it'
        ),
    };
  }, [queryClient, notifications]);
}
