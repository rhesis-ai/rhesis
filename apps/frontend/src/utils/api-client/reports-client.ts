import { BaseApiClient } from './base-client';
import { joinUrl } from '@/utils/url';
import { API_ENDPOINTS } from './config';
import type { PaginatedResponse } from './interfaces/pagination';
import type {
  Report,
  ReportCreate,
  ReportDetail,
  ReportsQueryParams,
  ReportSummaryDraft,
  ReportUpdate,
} from './interfaces/report';

export class ReportsClient extends BaseApiClient {
  async getReportsPage(
    params: ReportsQueryParams = {}
  ): Promise<PaginatedResponse<Report>> {
    const {
      skip = 0,
      limit = 25,
      sort_by = 'created_at',
      sort_order = 'desc',
      $filter,
    } = params;
    return this.fetchPaginated<Report>(
      API_ENDPOINTS.reports,
      { skip, limit, sort_by, sort_order, $filter },
      { cache: 'no-store' }
    );
  }

  async getReport(id: string): Promise<ReportDetail> {
    return this.fetch<ReportDetail>(`${API_ENDPOINTS.reports}/${id}`, {
      cache: 'no-store',
    });
  }

  async createReport(report: ReportCreate): Promise<Report> {
    return this.fetch<Report>(`${API_ENDPOINTS.reports}/`, {
      method: 'POST',
      body: JSON.stringify(report),
    });
  }

  async updateReport(id: string, report: ReportUpdate): Promise<Report> {
    return this.fetch<Report>(`${API_ENDPOINTS.reports}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(report),
    });
  }

  async deleteReport(id: string): Promise<void> {
    await this.fetch(`${API_ENDPOINTS.reports}/${id}`, { method: 'DELETE' });
  }

  async publishReport(id: string): Promise<Report> {
    return this.fetch<Report>(`${API_ENDPOINTS.reports}/${id}/publish`, {
      method: 'POST',
    });
  }

  async copyReport(id: string): Promise<Report> {
    return this.fetch<Report>(`${API_ENDPOINTS.reports}/${id}/copy`, {
      method: 'POST',
    });
  }

  async draftSummary(id: string): Promise<ReportSummaryDraft> {
    return this.fetch<ReportSummaryDraft>(
      `${API_ENDPOINTS.reports}/${id}/summary`,
      { method: 'POST' }
    );
  }

  /** The report as a PDF, built by the backend. Each download is recorded as report.exported. */
  async downloadPdf(id: string): Promise<Blob> {
    const url = joinUrl(this.baseUrl, `${API_ENDPOINTS.reports}/${id}/pdf`);
    const response = await fetch(url, { headers: this.getHeaders() });
    if (!response.ok) {
      throw new Error(
        `API error: ${response.status} - ${await response.text()}`
      );
    }
    return response.blob();
  }
}
