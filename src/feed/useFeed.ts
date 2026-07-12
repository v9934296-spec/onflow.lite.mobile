import { useCallback, useEffect, useState } from "react";
import { fetchFeed } from "../api/feedApi";
import type { LifecycleStage } from "../types/api/feed";
import type { FeedEvent } from "../types/feedEvent";

export function useFeed() {
  const [items, setItems] = useState<FeedEvent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [lifecycleStage, setLifecycleStage] = useState<LifecycleStage | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyPage = useCallback((append: boolean, page: { items: FeedEvent[]; next_cursor: string | null; lifecycle_stage: LifecycleStage }) => {
    setItems((prev) => (append ? [...prev, ...page.items] : page.items));
    setCursor(page.next_cursor);
    setLifecycleStage(page.lifecycle_stage);
  }, []);

  const loadInitial = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await fetchFeed({ limit: 20 });
    if (!res.ok) {
      setError(res.error.message);
      setLoading(false);
      return;
    }
    applyPage(false, res.data);
    setLoading(false);
  }, [applyPage]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    const res = await fetchFeed({ limit: 20 });
    if (!res.ok) {
      setError(res.error.message);
      setRefreshing(false);
      return;
    }
    applyPage(false, res.data);
    setRefreshing(false);
  }, [applyPage]);

  const loadMore = useCallback(async () => {
    if (!cursor || loadingMore) return;
    setLoadingMore(true);
    setError(null);
    const res = await fetchFeed({ limit: 20, cursor });
    if (!res.ok) {
      setError(res.error.message);
      setLoadingMore(false);
      return;
    }
    applyPage(true, res.data);
    setLoadingMore(false);
  }, [applyPage, cursor, loadingMore]);

  useEffect(() => {
    void loadInitial();
  }, [loadInitial]);

  return {
    items,
    cursor,
    lifecycleStage,
    loading,
    refreshing,
    loadingMore,
    error,
    refresh,
    loadMore,
    retry: loadInitial,
  };
}
