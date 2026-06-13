import type React from 'react';
import { useCallback, useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Sparkles, Zap, RefreshCw } from 'lucide-react';
import { autoRecommendApi } from '../api/autoRecommend';
import { Button, Card, EmptyState, InlineAlert, Loading } from '../components/common';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type {
  AutoRecommendResponse,
  AutoRecommendStock,
} from '../types/autoRecommend';

const SIGNAL_STYLES: Record<string, string> = {
  buy: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300',
  watch: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  hold: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
  sell: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
};

const CHANNEL_LABELS: Record<string, string> = {
  sector: '板块',
  theme: '主题',
  factor: '因子',
  technical: '技术',
  alphasift: 'AlphaSift',
};

const RecommendStockCard: React.FC<{ stock: AutoRecommendStock; rank: number }> = ({
  stock,
  rank,
}) => {
  const signalClass = SIGNAL_STYLES[stock.signal] || SIGNAL_STYLES.hold;
  const channelLabel = CHANNEL_LABELS[stock.channel] || stock.channel;

  return (
    <div className="flex items-center gap-3 rounded-lg border border-base-300 bg-base-100 p-3 transition hover:shadow-md">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
        {rank}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-semibold">{stock.stockName || stock.stockCode}</span>
          <span className="text-xs text-base-content/50">{stock.stockCode}</span>
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs">
          <span className={`rounded px-1.5 py-0.5 font-medium ${signalClass}`}>
            {stock.signal.toUpperCase()}
          </span>
          <span className="rounded bg-base-200 px-1.5 py-0.5">{channelLabel}</span>
          <span className="text-base-content/60">
            {(stock.confidence * 100).toFixed(0)}%
          </span>
          {stock.sector && (
            <span className="text-base-content/50">{stock.sector}</span>
          )}
        </div>
        {stock.summary && (
          <p className="mt-1 truncate text-xs text-base-content/60">{stock.summary}</p>
        )}
      </div>
    </div>
  );
};

const RecommendPage: React.FC = () => {
  const { t } = useUiLanguage();
  const [loading, setLoading] = useState(false);
  const [quickMode, setQuickMode] = useState(false);
  const [result, setResult] = useState<AutoRecommendResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRun = useCallback(
    async (mode: 'full' | 'quick') => {
      setLoading(true);
      setError(null);
      setQuickMode(mode === 'quick');
      try {
        const res = await autoRecommendApi.run({ mode });
        setResult(res);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-bold">{t('recommend.title') || 'AI 自动荐股'}</h1>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleRun('quick')}
            isLoading={loading && quickMode}
          >
            <Zap className="mr-1 h-3.5 w-3.5" />
            {t('recommend.quick') || '快速推荐'}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => handleRun('full')}
            isLoading={loading && !quickMode}
          >
            <RefreshCw className="mr-1 h-3.5 w-3.5" />
            {t('recommend.full') || '完整推荐'}
          </Button>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <Card padding="lg">
          <Loading label={t('recommend.scanning') || '正在扫描全市场...'} />
        </Card>
      )}

      {/* Error */}
      {error && !loading && (
        <InlineAlert variant="danger" title="Error" message={error} />
      )}

      {/* Empty state */}
      {!loading && !result && !error && (
        <Card padding="lg">
          <EmptyState
            title={t('recommend.empty') || '点击上方按钮开始荐股'}
            description={
              t('recommend.emptyDesc') ||
              '完整推荐扫描全部通道，快速推荐仅使用板块+因子通道'
            }
            icon={<Sparkles className="h-10 w-10 text-base-content/30" />}
          />
        </Card>
      )}

      {/* Results */}
      {!loading && result && result.success && (
        <>
          {/* Stats bar */}
          <div className="flex flex-wrap items-center gap-4 text-sm text-base-content/70">
            <span>
              扫描 <strong>{result.totalScanned}</strong> 只
            </span>
            <span>
              推荐 <strong>{result.recommendations.length}</strong> 只
            </span>
            {result.candidates.length > 0 && (
              <span className="text-xs text-base-content/50">
                候选: {result.candidates.join(', ')}
              </span>
            )}
          </div>

          {/* Recommendation list */}
          {result.recommendations.length > 0 ? (
            <div className="space-y-2">
              {result.recommendations.map((stock, i) => (
                <RecommendStockCard
                  key={stock.stockCode}
                  stock={stock}
                  rank={i + 1}
                />
              ))}
            </div>
          ) : (
            <Card padding="lg">
              <EmptyState
                title="今日暂无推荐"
                description="市场条件未达到推荐阈值"
              />
            </Card>
          )}

          {/* Markdown report */}
          {result.reportMarkdown && (
            <Card title="完整报告" padding="md">
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <Markdown remarkPlugins={[remarkGfm]}>
                  {result.reportMarkdown}
                </Markdown>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
};

export default RecommendPage;
