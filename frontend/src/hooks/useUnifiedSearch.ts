import { useState, useEffect } from "react";
import { client } from "@/services/api";
import type { components } from "@/types/schema";

type Job = components["schemas"]["JobList"];
type WorkerNode = components["schemas"]["WorkerNode"];
type WorkerPool = components["schemas"]["WorkerPool"];

interface SearchResults {
  jobs: Job[];
  workers: WorkerNode[];
  pools: WorkerPool[];
}

export function useUnifiedSearch(query: string, debounceMs = 300) {
  const [results, setResults] = useState<SearchResults>({ jobs: [], workers: [], pools: [] });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!query.trim()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResults({ jobs: [], workers: [], pools: [] });
      setIsLoading(false);
      return;
    }

    const handler = setTimeout(async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [jobsRes, workersRes, poolsRes] = await Promise.all([
          client.GET("/api/jobs/", { params: { query: { search: query } } }),
          client.GET("/api/workers/", { params: { query: { search: query } } }),
          client.GET("/api/pools/", { params: { query: { search: query } } }),
        ]);

        if (!jobsRes.data) throw new Error("Failed to fetch jobs");
        if (!workersRes.data) throw new Error("Failed to fetch workers");
        if (!poolsRes.data) throw new Error("Failed to fetch pools");

        setResults({
          jobs: jobsRes.data.results || [],
          workers: workersRes.data.results || [],
          pools: poolsRes.data.results || [],
        });
      } catch (err) {
        console.error("Search failed:", err);
        setError(err instanceof Error ? err : new Error("Unknown error occurred"));
      } finally {
        setIsLoading(false);
      }
    }, debounceMs);

    return () => clearTimeout(handler);
  }, [query, debounceMs]);

  return { results, isLoading, error };
}
