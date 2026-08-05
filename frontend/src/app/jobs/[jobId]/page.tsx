"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";
import { Pencil, RefreshCw, Trash2, Hash, LayoutList, Server, Folder, Layers, ShieldAlert, CheckCircle2, Clock, PlayCircle, PauseCircle, XCircle, Terminal, Calendar, Network } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/layout/PageHeader";
import { DependencyPanel } from "@/components/dashboard/DependencyPanel";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  abortJob,
  formatApiError,
  getJob,
  getJobLayers,
  updateJob,
  readAuthSession,
  type JobDetail,
  type LayerList,
} from "@/services/api";

const COUNTER_CONFIG = {
  ready_tasks: { label: "Ready Tasks", icon: Clock, color: "text-muted-foreground", bg: "bg-muted/30" },
  running_tasks: { label: "Running Tasks", icon: PlayCircle, color: "text-info", bg: "bg-info/10" },
  succeeded_tasks: { label: "Succeeded", icon: CheckCircle2, color: "text-success", bg: "bg-success/10" },
  failed_tasks: { label: "Failed", icon: XCircle, color: "text-destructive", bg: "bg-destructive/10" },
} as const;

function StateBadge({ state, className }: { state: string; className?: string }) {
  switch (state) {
    case "FINISHED":
      return (
        <Badge variant="success" className={`gap-1.5 pr-2.5 ${className || ""}`}>
          <CheckCircle2 className="size-3.5 fill-success/20" /> Finished
        </Badge>
      );
    case "FAILED":
      return (
        <Badge variant="destructive" className={`gap-1.5 pr-2.5 ${className || ""}`}>
          <XCircle className="size-3.5 fill-destructive/20" /> Failed
        </Badge>
      );
    case "RUNNING":
      return (
        <Badge variant="info" className={`gap-1.5 pr-2.5 ${className || ""}`}>
          <PlayCircle className="size-3.5 fill-info/20 animate-pulse" /> Running
        </Badge>
      );
    case "PAUSED":
      return (
        <Badge variant="secondary" className={`gap-1.5 pr-2.5 text-muted-foreground ${className || ""}`}>
          <PauseCircle className="size-3.5 fill-muted" /> Paused
        </Badge>
      );
    case "PENDING":
      return (
        <Badge variant="warning" className={`gap-1.5 pr-2.5 ${className || ""}`}>
          <Clock className="size-3.5 fill-warning/20" /> Pending
        </Badge>
      );
    default:
      return (
        <Badge variant="secondary" className={`gap-1.5 pr-2.5 text-muted-foreground ${className || ""}`}>
          <Clock className="size-3.5" /> {state.charAt(0) + state.slice(1).toLowerCase()}
        </Badge>
      );
  }
}

export default function JobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const jobId = params.jobId;
  const [job, setJob] = useState<JobDetail | null>(null);
  const [layers, setLayers] = useState<LayerList[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isEditOpen, setIsEditOpen] = useState<boolean>(false);
  const [draft, setDraft] = useState({ visible_name: "", priority: 50, max_tasks_per_worker: 0 });

  const session = useMemo(() => readAuthSession(), []);
  const isStaff = session?.user?.isStaff || session?.user?.isSuperuser || false;

  const completedTasks = useMemo(() => (job ? job.succeeded_tasks + job.skipped_tasks : 0), [job]);

  const loadJob = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      const [jobData, layerData] = await Promise.all([getJob(jobId), getJobLayers(jobId)]);
      setJob(jobData);
      setLayers(layerData);
      setDraft({
        visible_name: jobData.visible_name,
        priority: jobData.priority,
        max_tasks_per_worker: jobData.max_tasks_per_worker,
      });
    } catch (error) {
      toast.error("Unable to load job", { description: formatApiError(error) });
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadJob();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [loadJob]);

  const handleDraftChange =
    (key: keyof typeof draft) =>
    (event: ChangeEvent<HTMLInputElement>): void => {
      const value = event.target.value;
      setDraft((current) => ({
        ...current,
        [key]: key === "visible_name" ? value : Number(value),
      }));
    };

  const handleSave = async (): Promise<void> => {
    try {
      await updateJob(jobId, draft);
      toast.success("Job metadata updated");
      setIsEditOpen(false);
      await loadJob();
    } catch (error) {
      toast.error("Update failed", { description: formatApiError(error) });
    }
  };

  const handleAbort = async (): Promise<void> => {
    if (!window.confirm("Abort this job and remove all nested layers and tasks?")) return;

    try {
      await abortJob(jobId);
      toast.success("Job aborted");
      router.push("/jobs");
    } catch (error) {
      toast.error("Abort failed", { description: formatApiError(error) });
    }
  };

  return (
    <div className="flex h-full flex-col bg-background font-sans text-foreground">
      <PageHeader
        title={job?.visible_name ?? "Loading job..."}
        description={job ? `${job.project} / ${job.department} / ${job.user}` : "Fetching details..."}
        backTo="/jobs"
      >
        <Button variant="outline" onClick={() => void loadJob()} className="gap-2">
          <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
          Refresh
        </Button>
        <Button variant="outline" onClick={() => setIsEditOpen(true)} disabled={!job} className="gap-2">
          <Pencil size={14} />
          Edit
        </Button>
        <Button
          variant="outline"
          onClick={() => void handleAbort()}
          disabled={!job}
          className="gap-2 border-destructive/30 text-destructive hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
        >
          <Trash2 size={14} />
          Abort
        </Button>
      </PageHeader>

      <div className="flex-1 overflow-y-auto p-6 font-mono">
        <div className="space-y-6">
          {isLoading || !job ? (
            <Card className="border-border">
              <CardContent className="flex h-56 items-center justify-center text-muted-foreground">
                Loading job detail...
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
                <Card className="border-border md:col-span-1 relative overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent pointer-events-none" />
                  <CardHeader>
                    <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">State</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <StateBadge state={job.state} />
                    <p className="mt-3 text-xs text-muted-foreground">
                      <span className="font-semibold text-foreground">{completedTasks}</span> of {job.total_tasks} tasks completed
                    </p>
                    <div className="w-full h-1.5 rounded-full bg-muted mt-2 overflow-hidden">
                      <div 
                         className="h-full bg-primary transition-all duration-500" 
                         style={{ width: `${job.total_tasks > 0 ? (completedTasks / job.total_tasks) * 100 : 0}%` }}
                      />
                    </div>
                  </CardContent>
                </Card>

                {(Object.entries(COUNTER_CONFIG) as [keyof typeof COUNTER_CONFIG, typeof COUNTER_CONFIG[keyof typeof COUNTER_CONFIG]][]).map(([key, config]) => {
                  const Icon = config.icon;
                  return (
                    <Card key={key} className="border-border relative overflow-hidden group">
                      <div className={`absolute inset-0 ${config.bg} opacity-50 pointer-events-none transition-opacity group-hover:opacity-100`} />
                      <CardHeader className="relative z-10 pb-2">
                        <CardTitle className={`text-xs uppercase tracking-wider flex items-center gap-1.5 ${config.color}`}>
                          <Icon size={14} className="opacity-80" />
                          {config.label}
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="relative z-10">
                        <p className="text-3xl font-black text-foreground">{job[key]}</p>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>

              {/* Job Context Panel */}
              <Card className="border-border p-0 gap-0">
                <CardHeader className="p-4 pb-3 border-b border-border/50">
                  <CardTitle className="flex items-center gap-2 text-sm font-bold">
                    <Server size={16} className="text-info" />
                    Job Context
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 flex flex-col gap-5">
                  <div className="flex flex-col gap-1.5 px-2">
                    <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider">
                      Command
                    </div>
                    <div className="font-semibold font-mono text-xs break-all text-foreground/90" title={job.name}>
                      {job.name || "—"}
                    </div>
                  </div>

                  <div className="flex flex-col gap-1.5 px-2">
                    <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider">
                      Log Directory
                    </div>
                    <div className="font-semibold font-mono text-xs break-all text-foreground/90" title={job.log_directory}>
                      {job.log_directory || "—"}
                    </div>
                  </div>

                  <div className="h-px bg-border/40 mx-2" />

                  <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
                    <div className="flex flex-col gap-1.5 px-2">
                      <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider">
                        Priority
                      </div>
                      <div className="font-semibold">
                        <Badge variant="outline" className="rounded-md px-2 py-0.5 text-xs font-medium border-warning/30 bg-warning/5 text-warning">
                          {job.priority}
                        </Badge>
                      </div>
                    </div>

                    <div className="flex flex-col gap-1.5 px-2">
                      <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider">
                        Max Tasks
                      </div>
                      <div className="font-semibold text-sm text-foreground/90 flex items-center gap-1.5">
                        <span className="text-xl font-black">{job.max_tasks_per_worker}</span>
                      </div>
                    </div>

                    <div className="flex flex-col gap-1.5 px-2">
                      <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider">
                        Submit Time
                      </div>
                      <div className="font-semibold text-xs text-foreground/80">
                        {new Date(job.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </div>
                    </div>

                    <div className="flex flex-col gap-1.5 px-2">
                      <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider">
                        Runtime
                      </div>
                      <div className="font-semibold text-xs text-foreground/80">
                        {(() => {
                          if (!job.created_at) return "—";
                          const start = new Date(job.created_at).getTime();
                          const end = job.stopped_at ? new Date(job.stopped_at).getTime() : Date.now();
                          const diffMins = Math.floor((end - start) / 60000);
                          if (diffMins < 1) return "< 1m";
                          const hours = Math.floor(diffMins / 60);
                          const mins = diffMins % 60;
                          return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
                        })()}
                      </div>
                    </div>

                    <div className="flex flex-col gap-1.5 px-2">
                      <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider">
                        Target Pools
                      </div>
                      <div className="font-semibold text-xs flex flex-wrap gap-1">
                        {job.included_pools?.length > 0 ? (
                          job.included_pools.map((pool) => (
                            <Badge key={pool} variant="secondary" className="px-1.5 py-0 text-[10px]">
                              {pool}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-muted-foreground">Any</span>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Layers Table */}
              <Card className="border-border p-0 gap-0">
                <CardHeader className="p-4 pb-3 border-b border-border/50">
                  <CardTitle className="flex items-center gap-2 text-sm font-bold">
                    <Layers size={16} className="text-primary" />
                    Execution Layers
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader className="bg-muted/30">
                      <TableRow className="hover:bg-transparent">
                        <TableHead className="pl-6 font-semibold w-[25%]">Name</TableHead>
                        <TableHead className="font-semibold text-center w-[15%]">Type</TableHead>
                        <TableHead className="font-semibold text-center w-[15%]">State</TableHead>
                        <TableHead className="font-semibold text-center w-[20%]">Frame Range</TableHead>
                        <TableHead className="font-semibold text-right pr-6 w-[25%]">Progress</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {layers.map((layer) => (
                        <TableRow key={layer.id} className="hover:bg-muted/40 transition-colors group">
                          <TableCell className="pl-6">
                            <Link
                              href={`/jobs/${job.id}/layers/${layer.id}`}
                              className="font-bold text-primary hover:underline"
                            >
                              {layer.name}
                            </Link>
                          </TableCell>
                          <TableCell className="text-center">{layer.layer_type}</TableCell>
                          <TableCell className="text-center">
                            <StateBadge state={layer.state} />
                          </TableCell>
                          <TableCell className="text-center font-mono text-xs text-muted-foreground">
                            {layer.frame_range || "—"}
                          </TableCell>
                          <TableCell className="text-right pr-6">
                            <div className="flex items-center gap-3 justify-end">
                              <div className="w-24 h-1.5 rounded-full bg-muted overflow-hidden">
                                <div 
                                  className="h-full bg-primary transition-all duration-500" 
                                  style={{ width: `${Math.round(((layer.succeeded_tasks + layer.skipped_tasks) / Math.max(1, layer.total_tasks)) * 100)}%` }}
                                />
                              </div>
                              <span className="text-muted-foreground tabular-nums text-xs font-medium w-12 text-right">
                                {layer.succeeded_tasks + layer.skipped_tasks}/{layer.total_tasks}
                              </span>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              {/* Dependencies Panel (Full Width Expandable) */}
              <DependencyPanel jobId={job.id} isStaff={isStaff} />
            </>
          )}
        </div>

        <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
          <DialogContent className="border-border bg-surface">
            <DialogHeader>
              <DialogTitle>Edit Job Metadata</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Visible Name</Label>
                <Input value={draft.visible_name} onChange={handleDraftChange("visible_name")} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Priority</Label>
                  <Input type="number" value={draft.priority} onChange={handleDraftChange("priority")} />
                </div>
                <div className="space-y-2">
                  <Label>Max Tasks / Worker</Label>
                  <Input
                    type="number"
                    value={draft.max_tasks_per_worker}
                    onChange={handleDraftChange("max_tasks_per_worker")}
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setIsEditOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={() => void handleSave()}>Save changes</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
