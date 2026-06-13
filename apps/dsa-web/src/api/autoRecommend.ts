import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  AutoRecommendRequest,
  AutoRecommendResponse,
  AutoRecommendLastResponse,
} from '../types/autoRecommend';

export const autoRecommendApi = {
  /**
   * Trigger auto-recommend scan.
   */
  run: async (data: AutoRecommendRequest = {}): Promise<AutoRecommendResponse> => {
    const requestData = {
      mode: data.mode || 'full',
      top_n: data.topN || 10,
      deep_analyze: data.deepAnalyze || 3,
      notify: data.notify || false,
    };

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/auto-recommend/run',
      requestData
    );

    return toCamelCase<AutoRecommendResponse>(response.data);
  },

  /**
   * Get the last recommend result (runs a fresh scan).
   */
  getLast: async (): Promise<AutoRecommendLastResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/auto-recommend/last'
    );

    return toCamelCase<AutoRecommendLastResponse>(response.data);
  },
};
