"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AgenticLogs from "@/components/dashboard/AgenticLogs";
import HardwareTelemetry from "@/components/dashboard/HardwareTelemetry";
import JobQueue from "@/components/dashboard/JobQueue";
import KpiCards from "@/components/dashboard/KpiCards";
import { PoolSaturationStrip } from "@/components/dashboard/PoolSaturationStrip";
import { PageSkeleton } from "@/components/ui/SkeletonLoaders";
import {
  computeClusterTelemetry,
  computeFarmEfficiency,
  fetchJobs,
  getNodes,
  getPools,
  mapBackendJobToRenderJob,
  pingBackendLatency,
  type WorkerNode,
  type WorkerPool,
} from "@/services/api";
import type { RenderJob, TelemetryMetrics } from "@/types/dashboard";

const emptyTelemetry: TelemetryMetrics = {
  vramUsage: 0,
  cpuLoad: 0,
  points: [],
};

export default function DashboardPage() {
  const [jobs, setJobs] = useState<RenderJob[]>([]);
  const [nodes, setNodes] = useState<WorkerNode[]>([]);
  const [pools, setPools] = useState<WorkerPool[]>([]);
  const [telemetry, setTelemetry] = useState<TelemetryMetrics>(emptyTelemetry);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [isOffline, setIsOffline] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const initialFetchTimerRef = useRef<number | null>(null);
  const pollingTimerRef = useRef<number | null>(null);

  // Derived real-time cluster metrics
  const totalNodes = nodes.length;
  const onlineNodes = useMemo(
    () => nodes.filter((n) => n.status === "ONLINE" || n.status === "RENDERING").length,
    [nodes]
  );
  const totalCores = useMemo(
    () => nodes.reduce((sum, n) => sum + (n.cores || 1), 0),
    [nodes]
  );
  const activeJobCount = useMemo(
    () => jobs.filter((job) => job.status === "Rendering").length,
    [jobs]
  );
  const activeTaskCount = useMemo(
    () =>
      jobs.reduce(
        (sum, j) => sum + (j.running_tasks ?? (j.status === "Rendering" ? 1 : 0)),
        0
      ),
    [jobs]
  );

  const { efficiency, completedJobs, failedJobs } = useMemo(
    () => computeFarmEfficiency(jobs),
    [jobs]
  );

  const fetchDashboardData = useCallback(async (): Promise<void> => {
    try {
      const [backendJobs, backendNodes, backendPools, latency] = await Promise.all([
        fetchJobs(),
        getNodes().catch(() => []),
        getPools().catch(() => []),
        pingBackendLatency().catch(() => null),
      ]);
      const mappedJobs = backendJobs.map(mapBackendJobToRenderJob);

      setJobs(mappedJobs);
      setNodes(backendNodes);
      setPools(backendPools);
      if (latency !== null) {
        setLatencyMs(latency);
      }
      setIsOffline(false);

      setTelemetry((prev) =>
        computeClusterTelemetry(mappedJobs, backendNodes, prev.points)
      );
    } catch {
      setIsOffline(true);
      setLatencyMs(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshDashboardData = useCallback(async (): Promise<void> => {
    await fetchDashboardData();
  }, [fetchDashboardData]);

  useEffect(() => {
    initialFetchTimerRef.current = window.setTimeout(() => {
      void fetchDashboardData();
    }, 0);

    pollingTimerRef.current = window.setInterval(() => {
      void fetchDashboardData();
    }, 7000);

    return () => {
      if (initialFetchTimerRef.current !== null) {
        window.clearTimeout(initialFetchTimerRef.current);
      }

      if (pollingTimerRef.current !== null) {
        window.clearInterval(pollingTimerRef.current);
      }
    };
  }, [fetchDashboardData]);

  if (isLoading) {
    return <PageSkeleton />;
  }

  return (
    <div className="flex-1 flex flex-col p-6 space-y-6 font-mono h-[calc(100vh-theme(spacing.16))]">
      <KpiCards
        totalNodes={totalNodes}
        onlineNodes={onlineNodes}
        totalCores={totalCores}
        activeJobs={activeJobCount}
        activeTasks={activeTaskCount}
        farmEfficiency={efficiency}
        completedJobs={completedJobs}
        failedJobs={failedJobs}
        latencyMs={latencyMs}
        isOffline={isOffline}
      />

      <PoolSaturationStrip pools={pools} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 lg:relative min-h-[400px] lg:min-h-0">
          <div className="lg:absolute lg:inset-0 h-full w-full">
            <JobQueue jobs={jobs} searchQuery="" onJobRemoved={refreshDashboardData} />
          </div>
        </div>
        <div>
          <HardwareTelemetry telemetry={telemetry} />
        </div>
      </div>

      <div className="flex-1 min-h-0">
        <AgenticLogs searchQuery="" />
      </div>
    </div>
  );
}
