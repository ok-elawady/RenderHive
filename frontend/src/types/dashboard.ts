import type { ReactNode } from "react";
import type { components } from "./schema";

export type DashboardView =
  | "Dashboard"
  | "Active Queue"
  | "Active Users"
  | "Node Pool"
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
  frameCounts: string;
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
