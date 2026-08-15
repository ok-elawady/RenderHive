"use client";

import useSWR from "swr";
import { pingBackendLatency } from "@/services/api";

export interface ClusterHealthState {
  latencyMs: number | null;
  isOffline: boolean;
  isDegraded: boolean;
  isValidating: boolean;
  recheck: () => Promise<number | undefined>;
}

/**
 * Shared, reactive cluster latency & health state hook.
 * SWR automatically deduplicates polling across TopNav, KPI cards, and pages.
 */
export function useClusterHealth(): ClusterHealthState {
  const {
    data: latency,
    error,
    isValidating,
    mutate,
  } = useSWR<number>(
    "/api/health/latency",
    () => pingBackendLatency(),
    {
      refreshInterval: 7000,
      revalidateOnFocus: true,
      dedupingInterval: 3000,
      shouldRetryOnError: true,
      errorRetryInterval: 5000,
    }
  );

  const isOffline = !!error || latency === undefined;
  const isDegraded = !isOffline && (latency ?? 0) > 200;

  return {
    latencyMs: latency ?? null,
    isOffline,
    isDegraded,
    isValidating,
    recheck: () => mutate(),
  };
}
