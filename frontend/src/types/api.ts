import type { JobPriority } from "./dashboard";

export interface JobFormValues {
  jobName: string;
  user: string;
  engine: string;
  priority: JobPriority;
  startFrame: string;
  endFrame: string;
  logDirectory: string;
  renderCommand: string;
}
