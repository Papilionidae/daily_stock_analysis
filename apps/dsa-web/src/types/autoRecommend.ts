export interface AutoRecommendStock {
  stockCode: string;
  stockName: string;
  channel: string;
  signal: string;
  confidence: number;
  sector: string | null;
  summary: string;
}

export interface AutoRecommendRequest {
  mode?: 'full' | 'quick';
  topN?: number;
  deepAnalyze?: number;
  notify?: boolean;
}

export interface AutoRecommendResponse {
  success: boolean;
  candidates: string[];
  recommendations: AutoRecommendStock[];
  totalScanned: number;
  reportMarkdown: string;
}

export interface AutoRecommendLastResponse {
  success: boolean;
  totalScanned?: number;
  pickCount?: number;
  reportMarkdown: string;
  error?: string;
}
