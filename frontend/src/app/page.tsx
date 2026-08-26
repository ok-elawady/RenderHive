"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { JobTreePanel } from "@/components/dashboard/JobTreePanel";
import { TaskDetailPanel } from "@/components/dashboard/TaskDetailPanel";
import { BottomTabsPanel } from "@/components/dashboard/BottomTabsPanel";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { PageSkeleton } from "@/components/ui/SkeletonLoaders";
import {
  computeFarmEfficiency,
  fetchJobs,
  getNodes,
  getPools,
  mapBackendJobToRenderJob,
  type WorkerNode,
  type WorkerPool,
} from "@/services/api";
import { useClusterHealth } from "@/hooks/useClusterHealth";
import type { RenderJob } from "@/types/dashboard";

export default function DashboardPage() {
  const { latencyMs, isOffline: isClusterOffline } = useClusterHealth();
  const [jobs, setJobs] = useState<RenderJob[]>([]);
  const [nodes, setNodes] = useState<WorkerNode[]>([]);
  const [pools, setPools] = useState<WorkerPool[]>([]);
  const [isFetchOffline, setIsFetchOffline] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Layout persistence state
  const [layoutV, setLayoutV] = useState<any>(null);
  const [layoutH, setLayoutH] = useState<any>(null);
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
    const v = localStorage.getItem("dashboard-layout-v");
    if (v) { try { setLayoutV(JSON.parse(v)); } catch {} }
    const h = localStorage.getItem("dashboard-layout-h");
    if (h) { try { setLayoutH(JSON.parse(h)); } catch {} }
  }, []);

  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedLayerId, setSelectedLayerId] = useState<string | null>(null);

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
      const [backendJobs, backendNodes, backendPools] = await Promise.all([
        fetchJobs(),
        getNodes().catch(() => []),
        getPools().catch(() => []),
      ]);
      const mappedJobs = backendJobs.map(mapBackendJobToRenderJob);

      setJobs(mappedJobs);
      setNodes(backendNodes);
      setPools(backendPools);
      setIsFetchOffline(false);
    } catch {
      setIsFetchOffline(true);
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

  if (!isClient) {
    return <PageSkeleton />;
  }

  // Helper to extract layout values correctly since they might be number arrays (v1) or objects (v4)
  const getLayoutSize = (layout: any, key: string, index: number, defaultVal: number) => {
    if (!layout) return defaultVal;
    if (Array.isArray(layout)) return layout[index] ?? defaultVal;
    if (typeof layout === "object") return layout[key] ?? defaultVal;
    return defaultVal;
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">
      <ResizablePanelGroup 
        orientation="vertical" 
        id="dashboard-vertical"
        onLayoutChange={(sizes) => localStorage.setItem("dashboard-layout-v", JSON.stringify(sizes))}
      >
        <ResizablePanel 
          id="top"
          defaultSize={getLayoutSize(layoutV, "top", 0, 66)} 
          minSize={20}
        >
          <ResizablePanelGroup 
            orientation="horizontal" 
            id="dashboard-horizontal"
            onLayoutChange={(sizes) => localStorage.setItem("dashboard-layout-h", JSON.stringify(sizes))}
          >
            {/* Left Pane: Job Tree */}
            <ResizablePanel 
              id="job-tree"
              defaultSize={getLayoutSize(layoutH, "job-tree", 0, 65)} 
              minSize={20} 
              className="bg-surface-deep flex flex-col"
            >
              <JobTreePanel
                jobs={jobs}
                selectedJobId={selectedJobId}
                selectedLayerId={selectedLayerId}
                onSelectJob={(id) => {
                  setSelectedJobId(id);
                  setSelectedLayerId(null);
                }}
                onSelectLayer={(jid, lid) => {
                  setSelectedJobId(jid);
                  setSelectedLayerId(lid);
                }}
                onJobRemoved={refreshDashboardData}
              />
            </ResizablePanel>

            <ResizableHandle />

            {/* Right Pane: Task Details */}
            <ResizablePanel 
              id="task-details"
              defaultSize={getLayoutSize(layoutH, "task-details", 1, 35)} 
              minSize={20} 
              className="bg-background flex flex-col min-w-0"
            >
              <TaskDetailPanel
                selectedJobId={selectedJobId}
                selectedLayerId={selectedLayerId}
                jobs={jobs}
                nodes={nodes}
                pools={pools}
                onSelectLayer={(jid, lid) => {
                  setSelectedJobId(jid);
                  setSelectedLayerId(lid);
                }}
              />
            </ResizablePanel>
          </ResizablePanelGroup>
        </ResizablePanel>

        <ResizableHandle />

        {/* Bottom Split (Unified Bottom Panel) */}
        <ResizablePanel 
          id="bottom"
          defaultSize={getLayoutSize(layoutV, "bottom", 1, 34)} 
          minSize={10} 
          className="flex flex-col min-h-0"
        >
          <BottomTabsPanel 
            nodes={nodes}
            totalNodes={totalNodes}
            onlineNodes={onlineNodes}
            totalCores={totalCores}
            farmEfficiency={efficiency}
            latencyMs={latencyMs}
            isOffline={isClusterOffline || isFetchOffline}
            errorCount={failedJobs}
          />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
