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
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';

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

export function useStatuses(entityType: string, enabled = true) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<Status[]>({
    queryKey: statusKeys.list(entityType),
    queryFn: async () => {
      const statuses = await new ApiClientFactory()
        .getStatusClient()
        .getStatuses({
          entity_type: entityType,
          sort_by: 'name',
          sort_order: 'asc',
        });
      return statuses;
    },
    enabled: enabled && isAuthenticated,
    staleTime: STALE_TIME,
  });
}

export function useBehaviors(enabled = true) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<BehaviorWithMetrics[]>({
    queryKey: behaviorKeys.list('', 0, 100, 'name', 'asc'),
    queryFn: async () => {
      const behaviors = await new ApiClientFactory()
        .getBehaviorClient()
        .getAllBehaviors({ sort_by: 'name', sort_order: 'asc' });
      return behaviors;
    },
    enabled: enabled && isAuthenticated,
    staleTime: STALE_TIME,
  });
}

export function useCategories(entityType: string, enabled = true) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<Category[]>({
    queryKey: categoryKeys.list(entityType),
    queryFn: async () => {
      const categories = await new ApiClientFactory()
        .getCategoryClient()
        .getCategories({
          entity_type: entityType,
          sort_by: 'name',
          sort_order: 'asc',
        });
      return categories;
    },
    enabled: enabled && isAuthenticated,
    staleTime: STALE_TIME,
  });
}

export function useTopics(entityType: string, enabled = true) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<Topic[]>({
    queryKey: topicKeys.list(entityType),
    queryFn: async () => {
      const topics = await new ApiClientFactory().getTopicClient().getTopics({
        entity_type: entityType,
        sort_by: 'name',
        sort_order: 'asc',
      });
      return topics;
    },
    enabled: enabled && isAuthenticated,
    staleTime: STALE_TIME,
  });
}

export function useTags(enabled = true) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<Tag[]>({
    queryKey: tagKeys.list(),
    queryFn: async () => {
      const tags = await new ApiClientFactory()
        .getTagsClient()
        .getTags({ sort_by: 'name', sort_order: 'asc' });
      return tags;
    },
    enabled: enabled && isAuthenticated,
    staleTime: STALE_TIME,
  });
}

export function useUsers(enabled = true) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<User[]>({
    queryKey: userKeys.list(),
    queryFn: async () => {
      const response = await new ApiClientFactory().getUsersClient().getUsers();
      return response.data;
    },
    enabled: enabled && isAuthenticated,
    staleTime: STALE_TIME,
  });
}

export function useTypeLookups(filter: string, enabled = true) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<TypeLookup[]>({
    queryKey: typeLookupKeys.list(filter),
    queryFn: async () => {
      const types = await new ApiClientFactory()
        .getTypeLookupClient()
        .getTypeLookups({
          $filter: filter,
          sort_by: 'type_value',
          sort_order: 'asc',
        });
      return types;
    },
    enabled: enabled && isAuthenticated,
    staleTime: STALE_TIME,
  });
}

/** Thin React Query wrapper around the existing TTL-cached `getPriorities` utility. */
export function usePriorities(enabled = true) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<Priority[]>({
    queryKey: ['task-priorities'],
    queryFn: () => getPriorities(),
    enabled: enabled && isAuthenticated,
    staleTime: STALE_TIME,
  });
}
