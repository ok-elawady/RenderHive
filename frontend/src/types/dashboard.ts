import type { ReactNode } from "react";
import type { components } from "./schema";

export type DashboardView =
  | "Dashboard"
  | "Job Queue"
  | "User Management"
  | "Node Pool"
  | "Infrastructure"
  | "AI Rules"
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
  progress: number;
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
}

export interface TelemetryMetrics {
  vramUsage: number;
  cpuLoad: number;
  points: TelemetryPoint[];
}
