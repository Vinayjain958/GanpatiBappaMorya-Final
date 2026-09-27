import { api } from './client';

export interface ProviderKPIs {
  impressions: number;
  views: number;
  saves: number;
  completions: number;
  booking_requests: number;
  accepted_bookings: number;
  ratings_count: number;
  average_rating: number | null;
  save_rate: number;
  booking_request_rate: number;
  accepted_booking_rate: number;
}

export interface TrendDataPoint {
  period_start: string;
  period_end: string;
  observed: Record<string, number>;
  synthetic: Record<string, number>;
}

export interface DemandSegment {
  segment_type: string;
  key: string;
  label: string;
  interactions: number | null;
  share: number | null;
  trend_percent: number | null;
  minimum_sample_met: boolean;
  is_synthetic: boolean;
}

export interface ExperiencePerformance {
  experience_id: string;
  title: string;
  category_slug: string;
  category_name: string;
  views: number;
  saves: number;
  completions: number;
  booking_requests: number;
  accepted_bookings: number;
  ratings_count: number;
  average_rating: number | null;
  save_rate: number;
  booking_rate: number;
  is_synthetic: boolean;
}

export interface ProviderMatchSummary {
  match_id: string;
  score: number;
  model_version: string;
  qualified: boolean;
  segment_summary: string[];
  matched_experience_ids: string[];
  evidence_codes: string[];
  created_at: string;
  is_synthetic: boolean;
}

export interface ActionableInsight {
  code: string;
  title: string;
  explanation: string;
  supporting_metric: string;
  period: string;
  confidence: string;
  is_synthetic: boolean;
}

export interface InsightProvenance {
  has_observed_data: boolean;
  has_synthetic_data: boolean;
  observed_interaction_count: number;
  synthetic_interaction_count: number;
  generated_at: string;
  window: string;
  granularity: string;
}

export interface ProviderInsightResponse {
  period_start: string;
  period_end: string;
  kpis: ProviderKPIs;
  trends: TrendDataPoint[];
  segments: DemandSegment[];
  experience_performance: ExperiencePerformance[];
  matches: ProviderMatchSummary[];
  insights: ActionableInsight[];
  provenance: InsightProvenance;
}

export interface ProviderNotificationResponse {
  id: string;
  type: string;
  title: string;
  body: string;
  experience_id: string | null;
  match_score: number | null;
  segment_summary: string[] | null;
  is_read: boolean;
  created_at: string;
  is_synthetic: boolean;
  booking_request_id: string | null;
}

export interface ProviderNotificationListResponse {
  items: ProviderNotificationResponse[];
  total: number;
  unread_count: number;
}

export const providerIntelligenceApi = {
  getInsights: async (window: string = '30d', granularity: string = 'auto'): Promise<ProviderInsightResponse> => {
    const params = new URLSearchParams({ window, granularity });
    const response = await api.get(`/provider/insights?${params.toString()}`);
    return response.data;
  },

  getNotifications: async (unread_only: boolean = false): Promise<ProviderNotificationListResponse> => {
    const params = new URLSearchParams();
    if (unread_only) {
      params.append('unread_only', 'true');
    }
    const response = await api.get(`/provider/notifications?${params.toString()}`);
    return response.data;
  },

  markNotificationRead: async (notificationId: string): Promise<void> => {
    await api.post(`/provider/notifications/${notificationId}/read`);
  },
};
