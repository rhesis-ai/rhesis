'use client';

import { useQuery } from '@tanstack/react-query';
import {
  statusKeys,
  behaviorKeys,
  categoryKeys,
  topicKeys,
  tagKeys,
  userKeys,
  typeLookupKeys,
} from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Status } from '@/utils/api-client/interfaces/status';
import { BehaviorWithMetrics } from '@/utils/api-client/interfaces/behavior';
import { Category } from '@/utils/api-client/interfaces/category';
import { Topic } from '@/utils/api-client/interfaces/topic';
import { Tag } from '@/utils/api-client/interfaces/tag';
import { User } from '@/utils/api-client/interfaces/user';
import { TypeLookup } from '@/utils/api-client/interfaces/type-lookup';
import { getPriorities } from '@/utils/task-lookup';
import type { Priority } from '@/utils/api-client/interfaces/task';

const STALE_TIME = 5 * 60_000;

/**
 * Shared read-only lookup hooks for filter drawers and forms.
 *
 * These endpoints are near-static reference data (statuses, categories,
 * tags, etc.) fetched by multiple independent drawers today with no
 * caching — every re-open refetches, and drawers that need the same
 * lookup (e.g. statuses) don't share a call. Centralizing them here means
 * one network call per lookup per `staleTime` window, shared by whichever
 * component asks for it.
 */

export function useStatuses(
  sessionToken: string,
  entityType: string,
  enabled = true
) {
  return useQuery<Status[]>({
    queryKey: statusKeys.list(entityType),
    queryFn: async () => {
      const statuses = await new ApiClientFactory(sessionToken)
        .getStatusClient()
        .getStatuses({
          entity_type: entityType,
          sort_by: 'name',
          sort_order: 'asc',
        });
      return statuses;
    },
    enabled: enabled && !!sessionToken,
    staleTime: STALE_TIME,
  });
}

export function useBehaviors(sessionToken: string, enabled = true) {
  return useQuery<BehaviorWithMetrics[]>({
    queryKey: behaviorKeys.list('', 0, 100, 'name', 'asc'),
    queryFn: async () => {
      const behaviors = await new ApiClientFactory(sessionToken)
        .getBehaviorClient()
        .getBehaviors({ sort_by: 'name', sort_order: 'asc' });
      return behaviors;
    },
    enabled: enabled && !!sessionToken,
    staleTime: STALE_TIME,
  });
}

export function useCategories(
  sessionToken: string,
  entityType: string,
  enabled = true
) {
  return useQuery<Category[]>({
    queryKey: categoryKeys.list(entityType),
    queryFn: async () => {
      const categories = await new ApiClientFactory(sessionToken)
        .getCategoryClient()
        .getCategories({
          entity_type: entityType,
          sort_by: 'name',
          sort_order: 'asc',
        });
      return categories;
    },
    enabled: enabled && !!sessionToken,
    staleTime: STALE_TIME,
  });
}

export function useTopics(
  sessionToken: string,
  entityType: string,
  enabled = true
) {
  return useQuery<Topic[]>({
    queryKey: topicKeys.list(entityType),
    queryFn: async () => {
      const topics = await new ApiClientFactory(sessionToken)
        .getTopicClient()
        .getTopics({
          entity_type: entityType,
          sort_by: 'name',
          sort_order: 'asc',
        });
      return topics;
    },
    enabled: enabled && !!sessionToken,
    staleTime: STALE_TIME,
  });
}

export function useTags(sessionToken: string, enabled = true) {
  return useQuery<Tag[]>({
    queryKey: tagKeys.list(),
    queryFn: async () => {
      const tags = await new ApiClientFactory(sessionToken)
        .getTagsClient()
        .getTags({ sort_by: 'name', sort_order: 'asc' });
      return tags;
    },
    enabled: enabled && !!sessionToken,
    staleTime: STALE_TIME,
  });
}

export function useUsers(sessionToken: string, enabled = true) {
  return useQuery<User[]>({
    queryKey: userKeys.list(),
    queryFn: async () => {
      const response = await new ApiClientFactory(sessionToken)
        .getUsersClient()
        .getUsers();
      return response.data;
    },
    enabled: enabled && !!sessionToken,
    staleTime: STALE_TIME,
  });
}

export function useTypeLookups(
  sessionToken: string,
  filter: string,
  enabled = true
) {
  return useQuery<TypeLookup[]>({
    queryKey: typeLookupKeys.list(filter),
    queryFn: async () => {
      const types = await new ApiClientFactory(sessionToken)
        .getTypeLookupClient()
        .getTypeLookups({
          $filter: filter,
          sort_by: 'type_value',
          sort_order: 'asc',
        });
      return types;
    },
    enabled: enabled && !!sessionToken,
    staleTime: STALE_TIME,
  });
}

/** Thin React Query wrapper around the existing TTL-cached `getPriorities` utility. */
export function usePriorities(sessionToken: string, enabled = true) {
  return useQuery<Priority[]>({
    queryKey: ['task-priorities'],
    queryFn: () => getPriorities(sessionToken),
    enabled: enabled && !!sessionToken,
    staleTime: STALE_TIME,
  });
}
