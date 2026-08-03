"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { useCallback, useEffect, useMemo, useState, useRef, type ChangeEvent } from "react";
import {
  Pause,
  Play,
  RefreshCw,
  Search,
  Trash2,
  Loader2,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Clock,
  LayoutGrid,
  Link2,
  Edit3,
  Server,
  AlertTriangle,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Filter,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/PageHeader";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge, badgeVariants } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { SegmentedProgressBar } from "@/components/ui/segmented-progress";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  deleteJob,
  formatApiError,
  getJobs,
  pauseJob,
  resumeJob,
  updateJob,
  type BackendJob,
  type JobFilters,
  type JobStateFilter,
} from "@/services/api";

const jobStates: Array<JobStateFilter | ""> = ["", "PENDING", "RUNNING", "PAUSED", "FINISHED", "FAILED"];

function getJobStateBadge(state: BackendJob["state"]) {
  switch (state) {
    case "RUNNING":
      return (
        <Badge variant="info" className="gap-1.5 font-medium pr-2">
          <Loader2 className="animate-spin" size={12} /> {state}
        </Badge>
      );
    case "FINISHED":
      return (
        <Badge variant="success" className="gap-1.5 font-medium pr-2 bg-success/15 text-success hover:bg-success/20">
          <CheckCircle2 size={12} /> {state}
        </Badge>
      );
    case "FAILED":
      return (
        <Badge
          variant="destructive"
          className="gap-1.5 font-medium pr-2 bg-destructive/15 text-destructive hover:bg-destructive/20"
        >
          <XCircle size={12} /> {state}
        </Badge>
      );
    case "PAUSED":
      return (
        <Badge variant="warning" className="gap-1.5 font-medium pr-2 bg-warning/15 text-warning hover:bg-warning/20">
          <Pause size={12} /> {state}
        </Badge>
      );
    case "PENDING":
      return (
        <Badge
          variant="secondary"
          className="gap-1.5 font-medium pr-2 bg-muted/60 text-muted-foreground hover:bg-muted"
        >
          <Clock size={12} /> {state}
        </Badge>
      );
    default:
      return (
        <Badge variant="secondary" className="gap-1.5 font-medium pr-2">
          <AlertCircle size={12} /> {state}
        </Badge>
      );
  }
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<BackendJob[]>([]);
  const [filters, setFilters] = useState<JobFilters>({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [actionJobId, setActionJobId] = useState<string | null>(null);
  const [jobToDelete, setJobToDelete] = useState<BackendJob | null>(null);

  const [jobToEditPriority, setJobToEditPriority] = useState<BackendJob | null>(null);
  const [newPriority, setNewPriority] = useState<number>(50);

  const [sortConfig, setSortConfig] = useState<{ key: string; direction: "asc" | "desc" } | null>(null);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.project) count++;
    if (filters.department) count++;
    if (filters.user) count++;
    return count;
  }, [filters]);

  const handleSort = (key: string) => {
    setSortConfig((current) => {
      let newDirection: "asc" | "desc" = "asc";
      if (current?.key === key) {
        if (current.direction === "asc") newDirection = "desc";
        else return null;
      }
      return { key, direction: newDirection };
    });
  };

  useEffect(() => {
    setFilters((current) => ({
      ...current,
      ordering: sortConfig ? `${sortConfig.direction === "desc" ? "-" : ""}${sortConfig.key}` : undefined,
    }));
  }, [sortConfig]);

  const renderSortIcon = (key: string) => {
    if (sortConfig?.key !== key)
      return <ArrowUpDown className="ml-2 size-4 opacity-50 group-hover:opacity-100 transition-opacity" />;
    if (sortConfig.direction === "asc") return <ArrowUp className="ml-2 size-4 text-primary" />;
    return <ArrowDown className="ml-2 size-4 text-primary" />;
  };

  const fetchData = useCallback(
    async (showLoadingState = true): Promise<void> => {
      if (showLoadingState) setIsLoading(true);
      setIsRefreshing(true);
      try {
        setJobs(await getJobs(filters));
      } catch (error) {
        toast.error("Unable to load jobs", { description: formatApiError(error) });
      } finally {
        if (showLoadingState) setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [filters],
  );

  const initialLoad = useRef(true);

  useEffect(() => {
    if (!initialLoad.current) {
      setIsRefreshing(true);
    }
    const timer = window.setTimeout(() => {
      void fetchData(initialLoad.current);
      initialLoad.current = false;
    }, 300);
    return () => window.clearTimeout(timer);
  }, [fetchData]);

  const updateFilter =
    (key: keyof JobFilters) =>
    (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>): void => {
      const value = event.target.value;
      setFilters((current) => ({
        ...current,
        [key]: value || undefined,
      }));
    };

  const handleUpdatePriority = async (): Promise<void> => {
    if (!jobToEditPriority) return;
    setIsRefreshing(true);
    try {
      await updateJob(jobToEditPriority.id, { priority: newPriority });
      setJobs((currentJobs) =>
        currentJobs.map((j) => (j.id === jobToEditPriority.id ? { ...j, priority: newPriority } : j)),
      );
      toast.success("Priority updated");
    } catch (error) {
      toast.error("Update failed", { description: formatApiError(error) });
    } finally {
      setIsRefreshing(false);
      setJobToEditPriority(null);
    }
  };

  const formatRuntime = (start: string | undefined): string => {
    if (!start) return "N/A";
    const startDate = new Date(start);
    const diffMs = new Date().getTime() - startDate.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const hours = Math.floor(diffMins / 60);
    const mins = diffMins % 60;
    if (hours > 0) return `${hours}h ${mins}m ago`;
    return `${mins}m ago`;
  };

  const handleTransition = async (jobId: string, action: "pause" | "resume"): Promise<void> => {
    setActionJobId(jobId);
    try {
      if (action === "pause") {
        await pauseJob(jobId);
      } else {
        await resumeJob(jobId);
      }
      toast.success(action === "pause" ? "Job paused" : "Job resumed");
      await fetchData(false);
    } catch (error) {
      toast.error("Job action failed", { description: formatApiError(error) });
    } finally {
      setActionJobId(null);
    }
  };

  const handleRemoveJob = async (jobId: string): Promise<void> => {
    setActionJobId(jobId);
    try {
      await deleteJob(jobId);
      setJobs((currentJobs) => currentJobs.filter((job) => job.id !== jobId));
      toast.success("Job deleted");
      await fetchData(false);
    } catch (error) {
      toast.error("Delete failed", { description: formatApiError(error) });
    } finally {
      setActionJobId(null);
    }
  };

  return (
    <div className="flex h-full flex-col bg-background font-sans text-foreground">
      <PageHeader title="Job Queue" description="Monitor, prioritize, and manage the active render queue.">
        <Button variant="outline" onClick={() => void fetchData(false)} className="gap-2">
          <RefreshCw size={14} className={isLoading || isRefreshing ? "animate-spin" : ""} />
          Refresh
        </Button>
      </PageHeader>

      <Tabs
        value={filters.state ?? ""}
        onValueChange={(val) => updateFilter("state")({ target: { value: val } } as any)}
        className="flex h-full flex-col"
      >
        <div className="px-6 pt-4">
          <div className="w-full overflow-x-auto hide-scrollbar">
            <TabsList className="justify-start h-10 w-full min-w-max">
              {jobStates.map((state) => (
                <TabsTrigger key={state} value={state} className="px-4 capitalize">
                  {state ? state.toLowerCase() : "All Jobs"}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 pt-4">
          <div className="space-y-6">
            <div className="flex items-center justify-end gap-2 w-full">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  value={filters.search ?? ""}
                  onChange={updateFilter("search")}
                  placeholder="Search jobs, projects, users..."
                  className="pl-9 h-10 bg-card border-border/50 shadow-none"
                />
                {filters.search && (
                  <button
                    onClick={() => updateFilter("search")({ target: { value: "" } } as any)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 opacity-50 hover:opacity-100"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>

              <Popover>
                <PopoverTrigger
                  className={cn(
                    buttonVariants({ variant: "outline" }),
                    "h-10 gap-2 px-3 shadow-sm relative cursor-pointer transition-all duration-300",
                    activeFilterCount > 0
                      ? "border-primary/50 bg-primary/5 text-primary hover:bg-primary/10 hover:border-primary/70 ring-1 ring-primary/20"
                      : "border-border/50 bg-card hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  <Filter size={16} />
                  <span className="hidden sm:inline">Filters</span>
                  {activeFilterCount > 0 && (
                    <span className="absolute -top-2 -right-2 size-5 rounded-full bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center ring-2 ring-background">
                      {activeFilterCount}
                    </span>
                  )}
                </PopoverTrigger>
                <PopoverContent
                  align="end"
                  className="w-[340px] p-5 shadow-[0_16px_48px_rgba(0,0,0,0.4)] border border-border/80 bg-popover/85 backdrop-blur-2xl text-popover-foreground rounded-xl"
                >
                  <div className="flex items-center justify-between border-b border-border/50 pb-3">
                    <div className="font-semibold text-sm flex items-center gap-2">
                      <Filter size={14} className="text-primary" />
                      Advanced Filters
                    </div>
                    {(filters.project || filters.department || filters.user) && (
                      <button
                        onClick={() =>
                          setFilters((cur) => ({ ...cur, project: undefined, department: undefined, user: undefined }))
                        }
                        className="text-[10px] font-medium text-muted-foreground hover:text-destructive transition-colors flex items-center gap-1 bg-muted/40 hover:bg-destructive/10 px-2 py-1 rounded-md"
                      >
                        <X size={10} /> Clear all
                      </button>
                    )}
                  </div>

                  <div className="space-y-4">
                    <div className="space-y-2 group">
                      <label className="text-xs font-semibold text-foreground/80 flex items-center gap-1.5 transition-colors group-focus-within:text-primary">
                        Project
                      </label>
                      <Input
                        value={filters.project ?? ""}
                        onChange={updateFilter("project")}
                        placeholder="e.g. Apollo"
                        className="h-9 shadow-sm bg-background/50 focus-visible:bg-background border-border/50 focus-visible:border-primary/50 transition-all"
                      />
                    </div>
                    <div className="space-y-2 group">
                      <label className="text-xs font-semibold text-foreground/80 flex items-center gap-1.5 transition-colors group-focus-within:text-primary">
                        Department
                      </label>
                      <Input
                        value={filters.department ?? ""}
                        onChange={updateFilter("department")}
                        placeholder="e.g. Lighting"
                        className="h-9 shadow-sm bg-background/50 focus-visible:bg-background border-border/50 focus-visible:border-primary/50 transition-all"
                      />
                    </div>
                    <div className="space-y-2 group">
                      <label className="text-xs font-semibold text-foreground/80 flex items-center gap-1.5 transition-colors group-focus-within:text-primary">
                        User
                      </label>
                      <Input
                        value={filters.user ?? ""}
                        onChange={updateFilter("user")}
                        placeholder="e.g. j.doe"
                        className="h-9 shadow-sm bg-background/50 focus-visible:bg-background border-border/50 focus-visible:border-primary/50 transition-all"
                      />
                    </div>
                  </div>
                </PopoverContent>
              </Popover>
            </div>

            <Card className="border-border overflow-hidden p-0 gap-0 font-mono">
              <CardContent className="p-0">
                <Table className="table-fixed">
                  <TableHeader className="bg-muted/30">
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="w-[20%] pl-6">
                        <div className="flex justify-start w-full">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleSort("project")}
                            className="font-semibold flex items-center group -ml-4"
                          >
                            Job ID / Project
                            {renderSortIcon("project")}
                          </Button>
                        </div>
                      </TableHead>
                      <TableHead className="w-[15%]">
                        <div className="flex justify-center w-full">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleSort("state")}
                            className="font-semibold flex items-center group"
                          >
                            State
                            {renderSortIcon("state")}
                          </Button>
                        </div>
                      </TableHead>
                      <TableHead className="w-[10%]">
                        <div className="flex justify-center w-full">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleSort("priority")}
                            className="font-semibold flex items-center group"
                          >
                            Priority
                            {renderSortIcon("priority")}
                          </Button>
                        </div>
                      </TableHead>
                      <TableHead className="w-[15%]">
                        <div className="flex justify-center w-full">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleSort("created_at")}
                            className="font-semibold flex items-center group"
                          >
                            Runtime
                            {renderSortIcon("created_at")}
                          </Button>
                        </div>
                      </TableHead>
                      <TableHead className="font-semibold text-center w-[15%]">Pools</TableHead>
                      <TableHead className="font-semibold text-center w-[15%]">Tasks Progress</TableHead>
                      <TableHead className="font-semibold text-right pr-6 w-[10%]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody
                    className={cn(
                      "transition-opacity duration-200",
                      isRefreshing && !isLoading && "opacity-50 pointer-events-none",
                    )}
                  >
                    {isLoading ? (
                      Array.from({ length: 5 }).map((_, i) => (
                        <TableRow key={i} className="hover:bg-transparent">
                          <TableCell className="pl-6 py-4">
                            <Skeleton className="h-8 w-40" />
                          </TableCell>
                          <TableCell className="text-center py-4">
                            <Skeleton className="h-10 w-24 mx-auto" />
                          </TableCell>
                          <TableCell className="text-center py-4">
                            <Skeleton className="h-8 w-16 mx-auto" />
                          </TableCell>
                          <TableCell className="text-center py-4">
                            <Skeleton className="h-8 w-16 mx-auto" />
                          </TableCell>
                          <TableCell className="text-center py-4">
                            <Skeleton className="h-6 w-20 mx-auto" />
                          </TableCell>
                          <TableCell className="align-middle py-4 px-4">
                            <Skeleton className="h-4 w-full" />
                          </TableCell>
                          <TableCell className="pr-6 py-4">
                            <Skeleton className="h-8 w-24 ml-auto" />
                          </TableCell>
                        </TableRow>
                      ))
                    ) : jobs.length > 0 ? (
                      jobs.map((job) => {
                        const completed = job.succeeded_tasks + job.skipped_tasks;
                        const total = job.total_tasks || 1;
                        const percentage = Math.round((completed / total) * 100);

                        return (
                          <TableRow key={job.id} className="hover:bg-muted/40 transition-colors group">
                            {/* Job ID / Project */}
                            <TableCell className="pl-6 py-3">
                              <div className="flex flex-col gap-1">
                                <div className="flex items-center gap-2">
                                  <Link
                                    className="text-primary hover:text-primary/80 font-bold text-sm transition-colors truncate max-w-[200px]"
                                    href={`/jobs/${job.id}`}
                                  >
                                    {job.visible_name || job.name}
                                  </Link>
                                </div>
                                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                  <span className="font-semibold text-foreground/80">{job.project}</span>
                                  <span>•</span>
                                  <span>{job.department}</span>
                                  <span>•</span>
                                  <span>{job.user}</span>
                                </div>
                              </div>
                            </TableCell>

                            {/* State */}
                            <TableCell className="text-center py-3">
                              <div className="flex flex-col items-center gap-1.5">
                                {getJobStateBadge(job.state)}
                                {(job.depend_tasks ?? 0) > 0 && (
                                  <TooltipProvider delayDuration={150}>
                                    <Tooltip>
                                      <TooltipTrigger
                                        className={cn(
                                          badgeVariants({ variant: "warning" }),
                                          "gap-1 text-[10px] h-4 px-1.5 cursor-help",
                                        )}
                                      >
                                        <Link2 className="size-2.5" />
                                        {job.depend_tasks} blocked
                                      </TooltipTrigger>
                                      <TooltipContent side="top">
                                        <p>
                                          Waiting on {job.depend_tasks} upstream task{job.depend_tasks !== 1 ? "s" : ""}{" "}
                                          to complete.
                                        </p>
                                      </TooltipContent>
                                    </Tooltip>
                                  </TooltipProvider>
                                )}
                              </div>
                            </TableCell>

                            {/* Priority */}
                            <TableCell className="text-center py-3">
                              <Badge
                                variant="outline"
                                className="gap-1.5 text-xs h-5 px-2 cursor-pointer hover:bg-muted hover:border-primary/50 transition-colors bg-card font-semibold"
                                onClick={() => {
                                  setJobToEditPriority(job);
                                  setNewPriority(job.priority ?? 50);
                                }}
                              >
                                {job.priority ?? 50}
                                <Edit3 size={10} className="text-muted-foreground ml-0.5" />
                              </Badge>
                            </TableCell>

                            {/* Tags & Meta (Runtime) */}
                            <TableCell className="text-center py-3">
                              <div className="flex flex-col items-center gap-1">
                                <div className="text-xs font-semibold text-foreground">
                                  {formatRuntime(job.created_at)}
                                </div>
                                {job.created_at && (
                                  <div className="text-[10px] text-muted-foreground whitespace-nowrap">
                                    {new Date(job.created_at).toLocaleString([], {
                                      month: "short",
                                      day: "numeric",
                                      hour: "2-digit",
                                      minute: "2-digit",
                                    })}
                                  </div>
                                )}
                              </div>
                            </TableCell>

                            {/* Pools */}
                            <TableCell className="text-center py-3">
                              <div className="flex flex-wrap justify-center items-center gap-1.5 max-w-[140px] mx-auto">
                                {job.included_pools && job.included_pools.length > 0 ? (
                                  job.included_pools.map((pool) => (
                                    <Badge
                                      key={pool}
                                      variant="secondary"
                                      className="text-[10px] h-5 px-2 bg-secondary/40 text-secondary-foreground hover:bg-secondary/60"
                                    >
                                      {pool}
                                    </Badge>
                                  ))
                                ) : (
                                  <span className="text-[10px] text-muted-foreground/60 italic font-medium tracking-wide uppercase">
                                    Any Pool
                                  </span>
                                )}

                                {job.excluded_pools && job.excluded_pools.length > 0 && (
                                  <TooltipProvider delayDuration={150}>
                                    <Tooltip>
                                      <TooltipTrigger
                                        className={cn(
                                          badgeVariants({ variant: "outline" }),
                                          "text-[10px] h-5 px-1.5 cursor-help border-destructive/20 text-destructive/80 bg-destructive/5 hover:bg-destructive/10",
                                        )}
                                      >
                                        -{job.excluded_pools.length}
                                      </TooltipTrigger>
                                      <TooltipContent>
                                        <div className="text-xs font-semibold mb-1">Excluded Pools</div>
                                        <div className="text-[11px] text-muted-foreground">
                                          {job.excluded_pools.join(", ")}
                                        </div>
                                      </TooltipContent>
                                    </Tooltip>
                                  </TooltipProvider>
                                )}
                              </div>
                            </TableCell>

                            {/* Tasks Progress */}
                            <TableCell className="align-middle px-4 py-3">
                              <div className="w-full">
                                <SegmentedProgressBar
                                  total={job.total_tasks || 1}
                                  succeeded={job.succeeded_tasks}
                                  failed={job.failed_tasks}
                                  running={job.running_tasks}
                                  ready={job.ready_tasks}
                                  waiting={job.waiting_tasks}
                                  skipped={job.skipped_tasks}
                                  showCounts={true}
                                />
                              </div>
                            </TableCell>

                            {/* Actions */}
                            <TableCell className="text-right pr-6 align-middle py-3">
                              <TooltipProvider delay={150}>
                                <div className="flex justify-end gap-1 transition-opacity">
                                  <Tooltip>
                                    <TooltipTrigger
                                      render={
                                        <Button
                                          variant="ghost"
                                          size="icon"
                                          className={
                                            job.state === "PAUSED"
                                              ? "h-8 w-8 text-muted-foreground hover:text-success hover:bg-success/10 border border-transparent hover:border-success/20"
                                              : "h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-background border border-transparent hover:border-border"
                                          }
                                          disabled={
                                            actionJobId === job.id || job.state === "FINISHED" || job.state === "FAILED"
                                          }
                                          onClick={() =>
                                            void handleTransition(job.id, job.state === "PAUSED" ? "resume" : "pause")
                                          }
                                        >
                                          {job.state === "PAUSED" ? <Play size={14} /> : <Pause size={14} />}
                                        </Button>
                                      }
                                    />
                                    <TooltipContent>
                                      {job.state === "PAUSED" ? "Resume Job" : "Pause Job"}
                                    </TooltipContent>
                                  </Tooltip>

                                  <Tooltip>
                                    <TooltipTrigger
                                      render={
                                        <Button
                                          variant="ghost"
                                          size="icon"
                                          className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                          disabled={actionJobId === job.id}
                                          onClick={() => setJobToDelete(job)}
                                        >
                                          <Trash2 size={14} />
                                        </Button>
                                      }
                                    />
                                    <TooltipContent>Delete Job</TooltipContent>
                                  </Tooltip>
                                </div>
                              </TooltipProvider>
                            </TableCell>
                          </TableRow>
                        );
                      })
                    ) : (
                      <TableRow className="hover:bg-transparent">
                        <TableCell colSpan={7} className="h-[400px]">
                          <div className="flex flex-col items-center justify-center text-center h-full text-muted-foreground space-y-4">
                            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted/50 border border-border/50">
                              <LayoutGrid size={24} className="text-muted-foreground/60" />
                            </div>
                            <div className="space-y-1">
                              <h3 className="text-base font-semibold text-foreground">No jobs found</h3>
                              <p className="text-sm">There are no render jobs matching your current filters.</p>
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        </div>
      </Tabs>

      <Dialog open={!!jobToDelete} onOpenChange={(open) => !open && setJobToDelete(null)}>
        <DialogContent>
          <DialogHeader className="sm:text-center">
            <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-destructive/10 mb-4">
              <AlertTriangle className="size-6 text-destructive" />
            </div>
            <DialogTitle className="text-center text-lg">Delete Render Job</DialogTitle>
            <DialogDescription className="text-center pt-2">
              Are you sure you want to delete{" "}
              <strong className="text-foreground">{jobToDelete?.visible_name || jobToDelete?.name}</strong>?<br />
              This will permanently delete the job and all associated layers and tasks.{" "}
              <strong className="text-destructive font-semibold">This action cannot be undone.</strong>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setJobToDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (jobToDelete) {
                  void handleRemoveJob(jobToDelete.id);
                  setJobToDelete(null);
                }
              }}
            >
              Delete Job
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Priority Dialog */}
      <Dialog open={!!jobToEditPriority} onOpenChange={(open) => !open && setJobToEditPriority(null)}>
        <DialogContent className="sm:max-w-[300px]">
          <DialogHeader>
            <DialogTitle>Edit Priority</DialogTitle>
            <DialogDescription>
              Update priority for job <strong className="text-foreground">{jobToEditPriority?.visible_name}</strong>.
            </DialogDescription>
          </DialogHeader>
          <div className="py-6 space-y-6">
            <div className="space-y-4">
              <div className="flex justify-between items-center text-xs font-medium text-muted-foreground px-1">
                <span>Low</span>
                <span className="text-primary text-xl font-bold font-mono">{newPriority}</span>
                <span>Critical</span>
              </div>
              <input
                type="range"
                min="1"
                max="100"
                value={newPriority}
                onChange={(e) => setNewPriority(parseInt(e.target.value))}
                className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              />
            </div>
            <div className="grid grid-cols-4 gap-2">
              {[
                { label: "Low", val: 10 },
                { label: "Normal", val: 50 },
                { label: "High", val: 80 },
                { label: "Critical", val: 100 },
              ].map((preset) => (
                <Button
                  key={preset.val}
                  variant={newPriority === preset.val ? "default" : "outline"}
                  size="sm"
                  className="h-7 text-[10px] px-0"
                  onClick={() => setNewPriority(preset.val)}
                >
                  {preset.label}
                </Button>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setJobToEditPriority(null)}>
              Cancel
            </Button>
            <Button onClick={() => void handleUpdatePriority()}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
