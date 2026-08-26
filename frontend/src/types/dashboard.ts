import type { ReactNode } from "react";
import type { components } from "./schema";

export type DashboardView =
  | "Dashboard"
  | "Job Queue"
  | "Worker Nodes"
  | "Worker Pools"
  | "User Management"
  | "Node Pool"
  | "Infrastructure"
  | "AI Scheduler"
  | "Settings";

export interface SidebarItem {
  icon: ReactNode;
  label: DashboardView;
  href: string;
}

export type JobPriority = number;
export type BackendJobState = components["schemas"]["State1dfEnum"];

export type JobStatus =
  | "Rendering"
  | "Queued"
  | "Completed"
  | "Failed"
  | "Paused";

export interface RenderJob {
  id: string;
  displayId: string;
  priority: JobPriority;
  user: string;
  status: JobStatus;
  backendState: BackendJobState;
  taskCounts: string;
  total_tasks: number;
  succeeded_tasks: number;
  failed_tasks: number;
  running_tasks: number;
  ready_tasks: number;
  waiting_tasks: number;
  skipped_tasks: number;
  depend_tasks: number;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  included_pools: string[];
  excluded_pools: string[];
  project: string;
  department: string;
}

export type LogType = "INFO" | "ROUTE" | "WARN";

export interface LogEntry {
  time: string;
  type: LogType;
  msg: string;
}

export type LogMessage = Omit<LogEntry, "time">;

export interface TelemetryPoint {
  x: number;
  vram: number;
  cpu: number;
  ram?: number;
  active_tasks?: number;
  timestamp?: string;
}

export interface TelemetryMetrics {
  cpuLoad: number;
  memoryUsage: number;
  vramUsage: number;
  ramUsage?: number;
  points: TelemetryPoint[];
}

export interface ClusterTelemetryHistory {
  range: string;
  cpu_load: number;
  vram_usage: number;
  ram_usage?: number;
  peak_cpu?: number;
  peak_vram?: number;
  peak_ram?: number;
  total_snapshots?: number;
  points: TelemetryPoint[];
}
export interface FarmEvent {
  readonly id: string;
  readonly event_type: string;
  readonly severity: "INFO" | "WARNING" | "ERROR" | "CRITICAL" | string;
  readonly actor_username?: string | null;
  readonly target_type?: string | null;
  readonly target_id?: string | null;
  readonly target_name?: string | null;
  readonly target_display?: string | null;
  readonly message: string;
  readonly payload?: unknown;
  readonly created_at: string;
}
export type DispatchTrace = components["schemas"]["DispatchTrace"];
export type TaskLogDetail = components["schemas"]["TaskLogDetail"];
export type TaskLogList = components["schemas"]["TaskLogList"];
export type RecentDispatchLog = components["schemas"]["RecentDispatchLog"];

