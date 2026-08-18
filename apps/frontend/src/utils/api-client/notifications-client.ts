import { BaseApiClient } from './base-client';
import { NotificationSection } from '@/constants/notifications';

export interface NotificationSectionSummary {
  /** Unread items, not unread rows -- a batch notification counts as all the
   * entities it covers. See `item_count` below. */
  unread: number;
  entity_ids: string[];
}

export interface NotificationSummaryResponse {
  sections: Partial<Record<NotificationSection, NotificationSectionSummary>>;
}

export interface Notification {
  id: string;
  event_type: string;
  section: string;
  title: string;
  body: string | null;
  is_failure: boolean;
  entity_type: string | null;
  entity_id: string | null;
  /** Entities this one notification covers -- 3 for a Garak import of three
   * test sets. Badge counts add this, not 1. */
  item_count: number;
  payload: Record<string, unknown> | null;
  read_at: string | null;
  created_at: string;
  project_id: string | null;
}

export interface MarkReadRequest {
  section?: NotificationSection;
  /**
   * `Notification.id` values -- NOT the `entity_id` of whatever the
   * notification is about. Sending entity ids here matches nothing and comes
   * back as `updated: 0`.
   */
  notification_ids?: string[];
}

/**
 * Client for `/notifications`. Notifications are created only by the
 * backend (via a completed job) -- no create method here.
 */
export class NotificationsClient extends BaseApiClient {
  async getSummary(): Promise<NotificationSummaryResponse> {
    return this.fetch<NotificationSummaryResponse>('/notifications/summary', {
      cache: 'no-store',
    });
  }

  async getNotifications(params?: {
    section?: NotificationSection;
    unread_only?: boolean;
    skip?: number;
    limit?: number;
  }): Promise<Notification[]> {
    const query = new URLSearchParams();
    if (params?.section) query.set('section', params.section);
    if (params?.unread_only !== undefined)
      query.set('unread_only', String(params.unread_only));
    if (params?.skip !== undefined) query.set('skip', String(params.skip));
    if (params?.limit !== undefined) query.set('limit', String(params.limit));
    const suffix = query.toString() ? `?${query.toString()}` : '';
    return this.fetch<Notification[]>(`/notifications/${suffix}`, {
      cache: 'no-store',
    });
  }

  async markRead(body: MarkReadRequest): Promise<{ updated: number }> {
    return this.fetch<{ updated: number }>('/notifications/read', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }
}
