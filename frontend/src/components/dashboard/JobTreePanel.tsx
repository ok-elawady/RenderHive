"use client";

import { useState, useRef, useMemo } from "react";
import {
  ChevronRight,
  ChevronDown,
  ListOrdered,
  Pause,
  Play,
  Search,
  CheckCircle2,
  XCircle,
  Clock,
  PlayCircle,
  Trash2,
  Box,
  Wind,
  Hexagon,
  Component,
  Film,
  Terminal,
  Loader2,
  ExternalLink,
  ArrowUp,
  ArrowDown,
  ArrowUpDown,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SegmentedProgressBar } from "@/components/ui/segmented-progress";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { LayerInfoDialog } from "@/components/dashboard/LayerInfoDialog";
import { formatApiError, getJobLayers, pauseJob, resumeJob, deleteJob, type LayerList } from "@/services/api";
import type { RenderJob } from "@/types/dashboard";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

export interface JobTreePanelProps {
  jobs: RenderJob[];
  selectedJobId: string | null;
  selectedLayerId: string | null;
  onSelectJob: (jobId: string) => void;
  onSelectLayer: (jobId: string, layerId: string) => void;
  onJobRemoved: () => Promise<void>;
}

type QueueTabFilter = "ALL" | "RUNNING" | "PENDING" | "PAUSED" | "COMPLETED" | "FAILED";

function getJobStateBadge(state: string, displayStatus: string) {
  switch (state) {
    case "RUNNING":
      return (
        <Badge variant="info" className="gap-1.5 h-5 px-1.5 text-[10px] rounded-full font-bold bg-opacity-15 border-0">
          <Loader2 className="animate-spin" size={10} /> {displayStatus}
        </Badge>
      );
    case "FINISHED":
      return (
        <Badge
          variant="success"
          className="gap-1.5 h-5 px-1.5 text-[10px] rounded-full font-bold bg-opacity-15 border-0 bg-success/15 text-success hover:bg-success/20"
        >
          <CheckCircle2 size={10} /> {displayStatus}
        </Badge>
      );
    case "FAILED":
      return (
        <Badge
          variant="destructive"
          className="gap-1.5 h-5 px-1.5 text-[10px] rounded-full font-bold bg-opacity-15 border-0 bg-destructive/15 text-destructive hover:bg-destructive/20"
        >
          <XCircle size={10} /> {displayStatus}
        </Badge>
      );
    case "PAUSED":
      return (
        <Badge
          variant="warning"
          className="gap-1.5 h-5 px-1.5 text-[10px] rounded-full font-bold bg-opacity-15 border-0 bg-warning/15 text-warning hover:bg-warning/20"
        >
          <Clock size={10} /> {displayStatus}
        </Badge>
      );
    case "PENDING":
      return (
        <Badge
          variant="secondary"
          className="gap-1.5 h-5 px-1.5 text-[10px] rounded-full font-bold border-0 bg-muted/60 text-muted-foreground hover:bg-muted"
        >
          <Clock size={10} /> {displayStatus}
        </Badge>
      );
    default:
      return (
        <Badge variant="secondary" className="gap-1.5 h-5 px-1.5 text-[10px] rounded-full font-bold border-0">
          <Clock size={10} /> {displayStatus}
        </Badge>
      );
  }
}

function LayerStateIcon({ state }: { state: string }) {
  switch (state) {
    case "FINISHED":
      return <CheckCircle2 className="size-3 text-success" />;
    case "FAILED":
      return <XCircle className="size-3 text-destructive" />;
    case "RUNNING":
      return <PlayCircle className="size-3 text-info" />;
    case "PAUSED":
      return <Pause className="size-3 text-muted-foreground" />;
    case "PENDING":
      return <Clock className="size-3 text-warning" />;
    default:
      return <Clock className="size-3 text-muted-foreground" />;
  }
}

function formatDeadlineDate(dateStr?: string) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return "—";
  const pad = (n: number) => n.toString().padStart(2, "0");
  const dd = pad(d.getDate());
  const mm = pad(d.getMonth() + 1);
  const yy = d.getFullYear().toString().slice(-2);
  const hh = pad(d.getHours());
  const min = pad(d.getMinutes());
  return `${dd}/${mm}/${yy} ${hh}:${min}`;
}

function formatDeadlineDuration(startStr?: string, endStr?: string, state?: string) {
  if (!startStr) return "—";
  const start = new Date(startStr).getTime();
  if (isNaN(start)) return "—";
  if (!endStr && state !== "RUNNING") return "—";
  const end = endStr ? new Date(endStr).getTime() : Date.now();
  if (isNaN(end)) return "—";
  const diffSecs = Math.floor(Math.max(0, end - start) / 1000);
  const d = Math.floor(diffSecs / 86400);
  const h = Math.floor((diffSecs % 86400) / 3600);
  const m = Math.floor((diffSecs % 3600) / 60);
  const s = diffSecs % 60;
  const pad = (n: number) => n.toString().padStart(2, "0");
  if (d > 0) {
    return `${d}d ${pad(h)}:${pad(m)}:${pad(s)}`;
  }
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

export function JobTreePanel({
  jobs,
  selectedJobId,
  selectedLayerId,
  onSelectJob,
  onSelectLayer,
  onJobRemoved,
}: JobTreePanelProps) {
  const [activeTab, setActiveTab] = useState<QueueTabFilter>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedJobs, setExpandedJobs] = useState<Set<string>>(new Set());
  const [layersCache, setLayersCache] = useState<Record<string, LayerList[]>>({});
  const [loadingLayers, setLoadingLayers] = useState<Set<string>>(new Set());

  const [actionJobId, setActionJobId] = useState<string | null>(null);
  const [jobToDelete, setJobToDelete] = useState<RenderJob | null>(null);
  const router = useRouter();
  const [masterAction, setMasterAction] = useState<"pause" | "resume" | null>(null);
  const [isExecutingMaster, setIsExecutingMaster] = useState(false);

  const [infoDialogJobId, setInfoDialogJobId] = useState<string | null>(null);
  const [infoDialogLayerId, setInfoDialogLayerId] = useState<string | null>(null);
  const [infoDialogOpen, setInfoDialogOpen] = useState(false);

  const openLayerInfo = (jobId: string, layerId: string) => {
    setInfoDialogJobId(jobId);
    setInfoDialogLayerId(layerId);
    setInfoDialogOpen(true);
  };

  const normalizedQuery = searchQuery.trim().toLowerCase();

  const runningCount = useMemo(() => jobs.filter((j) => j.status === "Rendering").length, [jobs]);
  const pendingCount = useMemo(() => jobs.filter((j) => j.backendState === "PENDING").length, [jobs]);
  const pausedCount = useMemo(() => jobs.filter((j) => j.status === "Paused").length, [jobs]);
  const failedCount = useMemo(() => jobs.filter((j) => j.status === "Failed").length, [jobs]);
  const completedCount = useMemo(() => jobs.filter((j) => j.status === "Completed").length, [jobs]);

  const filteredJobs = useMemo(() => {
    let result = jobs;
    if (activeTab === "RUNNING") result = result.filter((j) => j.status === "Rendering");
    else if (activeTab === "PENDING") result = result.filter((j) => j.backendState === "PENDING");
    else if (activeTab === "PAUSED") result = result.filter((j) => j.status === "Paused");
    else if (activeTab === "FAILED") result = result.filter((j) => j.status === "Failed");
    else if (activeTab === "COMPLETED") result = result.filter((j) => j.status === "Completed");

    if (normalizedQuery) {
      result = result.filter((job) =>
        [job.id, job.displayId, job.user, job.backendState, job.project, job.department].some((v) =>
          v.toLowerCase().includes(normalizedQuery),
        ),
      );
    }
    return result;
  }, [jobs, activeTab, normalizedQuery]);

  type JobSortField =
    | "priority"
    | "name"
    | "user"
    | "status"
    | "frames"
    | "progress"
    | "created_at"
    | "started_at"
    | "finished_at"
    | "duration";
  type SortDirection = "asc" | "desc";

  const [sortField, setSortField] = useState<JobSortField>("created_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const handleSort = (field: JobSortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      if (["priority", "created_at", "started_at", "finished_at", "progress", "duration"].includes(field)) {
        setSortDirection("desc");
      } else {
        setSortDirection("asc");
      }
    }
  };

  const sortedJobs = useMemo(() => {
    const list = [...filteredJobs];
    return list.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "priority":
          cmp = (a.priority ?? 0) - (b.priority ?? 0);
          break;
        case "name":
          cmp = (a.displayId || "").localeCompare(b.displayId || "", undefined, { numeric: true, sensitivity: "base" });
          break;
        case "user":
          cmp = (a.user || "").localeCompare(b.user || "");
          break;
        case "status":
          cmp = (a.status || "").localeCompare(b.status || "");
          break;
        case "frames":
          cmp = (a.frame_range || "").localeCompare(b.frame_range || "", undefined, { numeric: true });
          break;
        case "progress": {
          const progA = ((a.succeeded_tasks || 0) + (a.skipped_tasks || 0)) / Math.max(1, a.total_tasks || 1);
          const progB = ((b.succeeded_tasks || 0) + (b.skipped_tasks || 0)) / Math.max(1, b.total_tasks || 1);
          cmp = progA - progB;
          break;
        }
        case "created_at":
          cmp = new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
          break;
        case "started_at":
          cmp =
            (a.started_at ? new Date(a.started_at).getTime() : 0) -
            (b.started_at ? new Date(b.started_at).getTime() : 0);
          break;
        case "finished_at":
          cmp =
            (a.finished_at ? new Date(a.finished_at).getTime() : 0) -
            (b.finished_at ? new Date(b.finished_at).getTime() : 0);
          break;
        case "duration": {
          const durA = a.started_at
            ? (a.finished_at ? new Date(a.finished_at).getTime() : Date.now()) - new Date(a.started_at).getTime()
            : -1;
          const durB = b.started_at
            ? (b.finished_at ? new Date(b.finished_at).getTime() : Date.now()) - new Date(b.started_at).getTime()
            : -1;
          cmp = durA - durB;
          break;
        }
      }
      return sortDirection === "asc" ? cmp : -cmp;
    });
  }, [filteredJobs, sortField, sortDirection]);

  const renderSortIcon = (field: JobSortField) => {
    if (sortField !== field) {
      return (
        <ArrowUpDown
          size={10}
          className="opacity-0 group-hover/col:opacity-40 transition-opacity ml-1 inline shrink-0"
        />
      );
    }
    return sortDirection === "asc" ? (
      <ArrowUp size={10} className="text-primary ml-1 inline shrink-0" />
    ) : (
      <ArrowDown size={10} className="text-primary ml-1 inline shrink-0" />
    );
  };

  const tabs: Array<{ id: QueueTabFilter | "COMPLETED"; label: string; count: number; alert?: boolean }> = [
    { id: "ALL", label: "All", count: jobs.length },
    { id: "RUNNING", label: "Running", count: runningCount },
    { id: "PENDING", label: "Pending", count: pendingCount },
    { id: "PAUSED", label: "Paused", count: pausedCount },
    { id: "COMPLETED", label: "Completed", count: completedCount },
    { id: "FAILED", label: "Failed", count: failedCount, alert: failedCount > 0 },
  ];

  const toggleExpand = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newExpanded = new Set(expandedJobs);
    if (newExpanded.has(jobId)) {
      newExpanded.delete(jobId);
      setExpandedJobs(newExpanded);
    } else {
      newExpanded.add(jobId);
      setExpandedJobs(newExpanded);
      if (!layersCache[jobId] && !loadingLayers.has(jobId)) {
        setLoadingLayers((prev) => new Set(prev).add(jobId));
        try {
          const layers = await getJobLayers(jobId);
          setLayersCache((prev) => ({ ...prev, [jobId]: layers }));
        } catch (error) {
          toast.error("Failed to load layers");
        } finally {
          setLoadingLayers((prev) => {
            const next = new Set(prev);
            next.delete(jobId);
            return next;
          });
        }
      }
    }
  };

  const handleTransition = async (jobId: string, action: "pause" | "resume") => {
    setActionJobId(jobId);
    try {
      if (action === "pause") {
        await pauseJob(jobId);
        toast.success("Job paused");
      } else {
        await resumeJob(jobId);
        toast.success("Job resumed");
      }
      await onJobRemoved();
    } catch (error) {
      toast.error("Action failed", { description: formatApiError(error) });
    } finally {
      setActionJobId(null);
    }
  };

  const handleDelete = async (jobId: string) => {
    setActionJobId(jobId);
    try {
      await deleteJob(jobId);
      toast.success("Job deleted");
      await onJobRemoved();
    } catch (error) {
      toast.error("Delete failed", { description: formatApiError(error) });
    } finally {
      setActionJobId(null);
      setJobToDelete(null);
    }
  };

  const handleMasterBatchAction = async () => {
    if (!masterAction) return;
    setIsExecutingMaster(true);
    const targetJobs =
      masterAction === "pause"
        ? jobs.filter((j) => j.status === "Rendering")
        : jobs.filter((j) => j.status === "Paused");

    try {
      await Promise.all(targetJobs.map((j) => (masterAction === "pause" ? pauseJob(j.id) : resumeJob(j.id))));
      toast.success(
        masterAction === "pause" ? `Paused ${targetJobs.length} jobs` : `Resumed ${targetJobs.length} jobs`,
      );
      await onJobRemoved();
    } catch (error) {
      toast.error("Batch action failed", { description: formatApiError(error) });
    } finally {
      setIsExecutingMaster(false);
      setMasterAction(null);
    }
  };

  const handleJobClick = (jobId: string) => {
    onSelectJob(jobId);
    const newExpanded = new Set(expandedJobs);
    if (newExpanded.has(jobId)) {
      newExpanded.delete(jobId);
      setExpandedJobs(newExpanded);
    } else {
      newExpanded.add(jobId);
      setExpandedJobs(newExpanded);
      if (!layersCache[jobId] && !loadingLayers.has(jobId)) {
        setLoadingLayers((prev) => new Set(prev).add(jobId));
        getJobLayers(jobId)
          .then((layers) => setLayersCache((prev) => ({ ...prev, [jobId]: layers })))
          .catch(() => toast.error("Failed to load layers"))
          .finally(() => {
            setLoadingLayers((prev) => {
              const next = new Set(prev);
              next.delete(jobId);
              return next;
            });
          });
      }
    }
  };

  return (
    <div className="flex flex-col h-full w-full min-h-0 overflow-hidden bg-surface-deep border-r border-border/60">
      {/* Header */}
      <div className="h-10 px-3 bg-muted/40 border-b border-border/50 flex items-center justify-between shrink-0">
        <div className="flex flex-wrap gap-1">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "px-2 py-1 rounded text-[11px] font-mono font-medium transition-colors flex items-center gap-1 cursor-pointer",
                  isActive ? "bg-primary text-primary-foreground" : "bg-muted/50 text-muted-foreground hover:bg-muted",
                  tab.alert && !isActive && "text-destructive bg-destructive/10",
                )}
              >
                {tab.label} <span className="opacity-70">{tab.count}</span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2">
          <div className="relative w-48">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search jobs..."
              className="pl-7 h-7 text-[11px] bg-background/50 border-border/60"
            />
          </div>

          <div className="flex items-center bg-muted/30 rounded-md border border-border/50 p-0.5">
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 rounded-sm"
                    disabled={runningCount === 0}
                    onClick={() => setMasterAction("pause")}
                  >
                    <Pause
                      size={10}
                      className={runningCount > 0 ? "text-warning" : "text-muted-foreground opacity-50"}
                    />
                  </Button>
                }
              />
              <TooltipContent>Pause All Active</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 rounded-sm"
                    disabled={pausedCount === 0}
                    onClick={() => setMasterAction("resume")}
                  >
                    <Play size={10} className={pausedCount > 0 ? "text-success" : "text-muted-foreground opacity-50"} />
                  </Button>
                }
              />
              <TooltipContent>Resume All Paused</TooltipContent>
            </Tooltip>
          </div>
        </div>
      </div>

      {/* Tree List */}
      <div className="flex-1 overflow-y-auto overflow-x-auto font-mono text-xs">
        {filteredJobs.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">No matching jobs found.</div>
        ) : (
          <div className="flex flex-col min-w-[1250px] w-full">
            {/* Table Header */}
            <div className="sticky top-0 z-10 bg-background/95 backdrop-blur border-b border-border/50 grid grid-cols-[24px_48px_minmax(160px,1fr)_80px_115px_80px_150px_110px_110px_110px_90px_76px] items-center gap-2 p-1.5 text-[11px] font-bold text-foreground uppercase tracking-wider select-none shadow-sm">
              <div className="shrink-0" /> {/* Spacer for expand icon */}
              <div
                onClick={() => handleSort("priority")}
                className="min-w-0 text-center cursor-pointer hover:text-primary transition-colors flex items-center justify-center group/col"
                title="Sort by Priority"
              >
                Pri {renderSortIcon("priority")}
              </div>
              <div
                onClick={() => handleSort("name")}
                className="min-w-0 text-left cursor-pointer hover:text-primary transition-colors flex items-center group/col"
                title="Sort by Job Name"
              >
                Job Name {renderSortIcon("name")}
              </div>
              <div
                onClick={() => handleSort("user")}
                className="min-w-0 text-center cursor-pointer hover:text-primary transition-colors flex items-center justify-center group/col"
                title="Sort by User"
              >
                User {renderSortIcon("user")}
              </div>
              <div
                onClick={() => handleSort("status")}
                className="min-w-0 text-center cursor-pointer hover:text-primary transition-colors flex items-center justify-center group/col"
                title="Sort by Status"
              >
                Status {renderSortIcon("status")}
              </div>
              <div
                onClick={() => handleSort("frames")}
                className="min-w-0 text-center cursor-pointer hover:text-primary transition-colors flex items-center justify-center group/col"
                title="Sort by Frame Range"
              >
                Frames {renderSortIcon("frames")}
              </div>
              <div
                onClick={() => handleSort("progress")}
                className="min-w-0 text-center px-2 cursor-pointer hover:text-primary transition-colors flex items-center justify-center group/col"
                title="Sort by Progress"
              >
                Task Progress {renderSortIcon("progress")}
              </div>
              <div
                onClick={() => handleSort("created_at")}
                className="min-w-0 text-center cursor-pointer hover:text-primary transition-colors flex items-center justify-center group/col"
                title="Sort by Submitted Time"
              >
                Submitted {renderSortIcon("created_at")}
              </div>
              <div
                onClick={() => handleSort("started_at")}
                className="min-w-0 text-center cursor-pointer hover:text-primary transition-colors flex items-center justify-center group/col"
                title="Sort by Started Time"
              >
                Started {renderSortIcon("started_at")}
              </div>
              <div
                onClick={() => handleSort("finished_at")}
                className="min-w-0 text-center cursor-pointer hover:text-primary transition-colors flex items-center justify-center group/col"
                title="Sort by Finished Time"
              >
                Finished {renderSortIcon("finished_at")}
              </div>
              <div
                onClick={() => handleSort("duration")}
                className="min-w-0 text-center cursor-pointer hover:text-primary transition-colors flex items-center justify-center group/col"
                title="Sort by Duration"
              >
                Duration {renderSortIcon("duration")}
              </div>
              <div className="min-w-0 text-right pr-2">Actions</div>
            </div>

            {sortedJobs.map((job) => {
              const isExpanded = expandedJobs.has(job.id);
              const isSelected = selectedJobId === job.id;
              const isActioning = actionJobId === job.id;
              const displayStatus = job.status === "Rendering" ? `Rendering (${job.running_tasks})` : job.status;

              const poolText = job.included_pools?.length > 0 ? job.included_pools.join(",") : "Any";

              return (
                <div key={job.id} className="flex flex-col border-b border-border/30 last:border-0">
                  {/* Job Row */}
                  <div
                    onClick={() => handleJobClick(job.id)}
                    className={cn(
                      "grid grid-cols-[24px_48px_minmax(160px,1fr)_80px_115px_80px_150px_110px_110px_110px_90px_76px] items-center gap-2 p-1.5 cursor-pointer transition-colors group relative",
                      isSelected ? "bg-primary/10" : "hover:bg-muted/40",
                      job.status === "Rendering" && "bg-success/10",
                    )}
                  >
                    {isSelected && <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-primary" />}

                    <button
                      onClick={(e) => toggleExpand(job.id, e)}
                      className="size-6 flex items-center justify-center rounded hover:bg-muted/50 text-foreground shrink-0 cursor-pointer"
                    >
                      {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    </button>

                    {/* Priority */}
                    <div className="flex items-center justify-center text-foreground font-semibold text-[11px] min-w-0">
                      {job.priority}
                    </div>

                    {/* Job Name */}
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="text-xs text-foreground truncate">{job.displayId}</span>
                    </div>

                    {/* User */}
                    <div className="flex items-center justify-center text-foreground truncate text-[11px] min-w-0">
                      {job.user || "system"}
                    </div>

                    <div className="flex items-center justify-center min-w-0">
                      {getJobStateBadge(job.backendState, displayStatus)}
                    </div>

                    {/* Frames */}
                    <div className="flex items-center justify-center text-muted-foreground truncate text-[11px] min-w-0">
                      {job.frame_range || "—"}
                    </div>

                    {/* Progress */}
                    <div className="flex items-center gap-1.5 min-w-0 pr-1">
                      <div className="flex-1">
                        <SegmentedProgressBar
                          className="h-2 rounded-full"
                          total={job.total_tasks}
                          succeeded={job.succeeded_tasks}
                          failed={job.failed_tasks}
                          running={job.running_tasks}
                          ready={job.ready_tasks}
                          waiting={job.waiting_tasks}
                          skipped={job.skipped_tasks}
                          showCounts={false}
                        />
                      </div>
                      <span className="text-[10px] text-muted-foreground tabular-nums min-w-[36px] text-right">
                        {job.succeeded_tasks + job.skipped_tasks}/{job.total_tasks}
                      </span>
                    </div>

                    {/* Dates */}
                    <div className="flex items-center justify-center text-foreground truncate text-[11px] min-w-0">
                      {formatDeadlineDate(job.created_at)}
                    </div>
                    <div className="flex items-center justify-center text-foreground truncate text-[11px] min-w-0">
                      {formatDeadlineDate(job.started_at)}
                    </div>
                    <div className="flex items-center justify-center text-foreground truncate text-[11px] min-w-0">
                      {formatDeadlineDate(job.finished_at)}
                    </div>
                    <div className="flex items-center justify-center text-foreground truncate text-[11px] min-w-0">
                      {formatDeadlineDuration(job.started_at, job.finished_at, job.backendState)}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center justify-end gap-0.5 transition-opacity min-w-0 pr-1">
                      {job.backendState === "PAUSED" ? (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-5 h-5 hover:text-success"
                          disabled={isActioning}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleTransition(job.id, "resume");
                          }}
                        >
                          <Play size={10} />
                        </Button>
                      ) : job.backendState === "RUNNING" || job.backendState === "PENDING" ? (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-5 h-5 hover:text-warning"
                          disabled={isActioning}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleTransition(job.id, "pause");
                          }}
                        >
                          <Pause size={10} />
                        </Button>
                      ) : (
                        <div className="size-5" />
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-5 h-5 hover:text-primary"
                        title="Open Job Details"
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push(`/jobs/${job.id}`);
                        }}
                      >
                        <ExternalLink size={10} />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-5 h-5 hover:text-destructive"
                        disabled={isActioning}
                        onClick={(e) => {
                          e.stopPropagation();
                          setJobToDelete(job);
                        }}
                      >
                        <Trash2 size={10} />
                      </Button>
                    </div>
                  </div>

                  {/* Layer Sub-rows */}
                  {isExpanded && (
                    <div className="bg-background/80 flex flex-col gap-0 border-t border-border/30 shadow-inner">
                      {loadingLayers.has(job.id) ? (
                        <div className="py-2 text-[11px] text-muted-foreground flex items-center justify-center gap-2">
                          <div className="size-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                          Loading layers...
                        </div>
                      ) : layersCache[job.id]?.length === 0 ? (
                        <div className="py-2 text-[11px] text-center text-muted-foreground">No layers.</div>
                      ) : (
                        layersCache[job.id]?.map((layer) => {
                          const isLayerSelected = isSelected && selectedLayerId === layer.id;
                          return (
                            <div
                              key={layer.id}
                              onClick={(e) => {
                                onSelectLayer(job.id, layer.id);
                              }}
                              onDoubleClick={(e) => {
                                e.stopPropagation();
                                openLayerInfo(job.id, layer.id);
                              }}
                              className={cn(
                                "grid grid-cols-[24px_48px_minmax(160px,1fr)_80px_115px_80px_150px_110px_110px_110px_90px_76px] items-center gap-2 p-1.5 border-b border-border/20 last:border-0 cursor-pointer transition-colors relative",
                                isLayerSelected ? "bg-primary/20" : "bg-muted/10 hover:bg-muted/30",
                                layer.state === "RUNNING" && "bg-success/5",
                              )}
                            >
                              {isLayerSelected && (
                                <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-primary/70" />
                              )}
                              <div className="shrink-0" /> {/* Spacer */}
                              <div className="min-w-0 text-center text-muted-foreground text-[10px]">—</div>
                              <div className="flex items-center gap-1.5 min-w-0">
                                <span className="text-xs truncate">{layer.name}</span>
                              </div>
                              <div className="min-w-0" />
                              <div className="flex items-center justify-center min-w-0">
                                {getJobStateBadge(
                                  layer.state,
                                  layer.state === "RUNNING"
                                    ? "Rendering"
                                    : layer.state === "FINISHED"
                                      ? "Completed"
                                      : layer.state,
                                )}
                              </div>
                              <div className="flex items-center justify-center text-muted-foreground truncate text-[11px] min-w-0">
                                {layer.frame_range || "—"}
                              </div>
                              <div className="min-w-0 px-1">
                                <div className="flex items-center gap-1.5 w-full">
                                  <div className="flex-1">
                                    <SegmentedProgressBar
                                      className="h-1.5 rounded-full"
                                      total={layer.total_tasks}
                                      succeeded={layer.succeeded_tasks}
                                      failed={layer.failed_tasks}
                                      running={layer.running_tasks}
                                      ready={layer.ready_tasks}
                                      waiting={layer.waiting_tasks}
                                      skipped={layer.skipped_tasks}
                                      showCounts={false}
                                    />
                                  </div>
                                  <span className="text-[10px] text-muted-foreground tabular-nums min-w-[36px] text-right">
                                    {layer.succeeded_tasks + layer.skipped_tasks}/{layer.total_tasks}
                                  </span>
                                </div>
                              </div>
                              <div className="min-w-0" />
                              <div className="min-w-0" />
                              <div className="min-w-0" />
                              <div className="min-w-0" />
                              <div className="min-w-0" />
                            </div>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!jobToDelete}
        onOpenChange={(open) => !open && setJobToDelete(null)}
        variant="destructive"
        title="Delete Render Job"
        description={
          <>
            Are you sure you want to delete <strong className="text-foreground">{jobToDelete?.displayId}</strong>?
          </>
        }
        confirmText="Delete Job"
        isLoading={actionJobId === jobToDelete?.id}
        onConfirm={async () => {
          if (jobToDelete) await handleDelete(jobToDelete.id);
        }}
      />
      <ConfirmDialog
        open={!!masterAction}
        onOpenChange={(open) => !open && setMasterAction(null)}
        variant={masterAction === "pause" ? "warning" : "default"}
        title={masterAction === "pause" ? "Pause All Active Jobs?" : "Resume All Paused Jobs?"}
        description={masterAction === "pause" ? "Suspend all active rendering jobs." : "Resume all paused jobs."}
        confirmText={masterAction === "pause" ? "Pause All Active" : "Resume All Paused"}
        isLoading={isExecutingMaster}
        onConfirm={handleMasterBatchAction}
      />
      <LayerInfoDialog
        jobId={infoDialogJobId}
        layerId={infoDialogLayerId}
        isOpen={infoDialogOpen}
        onClose={() => setInfoDialogOpen(false)}
      />
    </div>
  );
}
