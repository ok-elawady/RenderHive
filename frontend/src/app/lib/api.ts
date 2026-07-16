import axios from "axios";
import type {
  BackendJobState,
  JobPriority,
  LogEntry,
  RenderJob,
  TelemetryMetrics,
  TelemetryPoint,
} from "../types/dashboard";

export const API_BASE_URL = "http://localhost:8000";
const JOBS_ENDPOINT = "/api/jobs/";
const renderHiveAuthToken = process.env.NEXT_PUBLIC_RENDERHIVE_AUTH_TOKEN;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    ...(renderHiveAuthToken
      ? { Authorization: `Token ${renderHiveAuthToken}` }
      : {}),
    "Content-Type": "application/json",
  },
});

export interface BackendJob {
  id: string;
  name: string;
  visible_name: string;
  project: string;
  department: string;
  user: string;
  state: BackendJobState;
  priority: number;
  is_paused: boolean;
  total_frames: number;
  waiting_frames: number;
  ready_frames: number;
  running_frames: number;
  succeeded_frames: number;
  failed_frames: number;
  skipped_frames: number;
  depend_frames: number;
  created_at: string;
  updated_at: string;
}

interface PaginatedResponse<T> {
  results: T[];
}

export interface JobFormValues {
  jobName: string;
  userId: number;
  engine: string;
  priority: JobPriority;
  startFrame: string;
  endFrame: string;
  logDirectory: string;
  renderCommand: string;
}

export interface CreateJobPayload {
  visible_name: string;
  project: "test";
  department: "td";
  priority: number;
  max_frames_per_worker: number;
  user: number;
  log_directory: string;
  layers: Array<{
    name: string;
    renderer: string;
    frame_range: string;
    chunk_size: number;
    command: string;
  }>;
}

function stringifyApiValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map(stringifyApiValue).filter(Boolean).join(", ");
  }
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, nestedValue]) => `${key}: ${stringifyApiValue(nestedValue)}`)
      .filter((entry) => !entry.endsWith(": "))
      .join(" | ");
  }

  return "";
}

function isPaginatedResponse<T>(
  value: T[] | PaginatedResponse<T>,
): value is PaginatedResponse<T> {
  return !Array.isArray(value) && Array.isArray(value.results);
}

function mapPriority(priority: number): JobPriority {
  if (priority >= 75) return "HIGH";
  if (priority >= 35) return "MED";
  return "LOW";
}

function mapStatus(state: BackendJobState): RenderJob["status"] {
  if (state === "RUNNING") return "Rendering";
  if (state === "PENDING" || state === "PAUSED") return "Queued";
  if (state === "FINISHED") return "Completed";
  return "Failed";
}

function getStatusColor(state: BackendJobState): string {
  if (state === "RUNNING") {
    return "text-[#5A1FA6] bg-[#5A1FA6]/10 border-[#5A1FA6]/30";
  }

  if (state === "PENDING" || state === "PAUSED") {
    return "text-[#4DA3FF] bg-[#4DA3FF]/10 border-[#4DA3FF]/30";
  }

  if (state === "FINISHED") {
    return "text-[#3DDC84] bg-[#3DDC84]/10 border-[#3DDC84]/30";
  }

  return "text-[#FF5D73] bg-[#FF5D73]/10 border-[#FF5D73]/30";
}

function getProgress(job: BackendJob): number {
  if (job.total_frames <= 0) return 0;

  return Math.round(
    ((job.succeeded_frames + job.skipped_frames) / job.total_frames) * 100,
  );
}

function getEta(job: BackendJob): string {
  if (job.state === "FINISHED") return "Done";
  if (job.state === "FAILED") return "Failed";
  if (job.state === "PAUSED") return "Paused";
  if (job.running_frames > 0) return "Rendering";
  if (job.ready_frames > 0) return "Ready";
  return "Waiting";
}

export function normalizeJobsResponse(
  data: BackendJob[] | PaginatedResponse<BackendJob>,
): BackendJob[] {
  return isPaginatedResponse(data) ? data.results : data;
}

export async function fetchJobs(): Promise<BackendJob[]> {
  const response = await apiClient.get<BackendJob[] | PaginatedResponse<BackendJob>>(
    JOBS_ENDPOINT,
  );

  return normalizeJobsResponse(response.data);
}

export function mapBackendJobToRenderJob(job: BackendJob): RenderJob {
  return {
    id: job.id,
    displayId: job.visible_name || job.name,
    priority: mapPriority(job.priority),
    node: job.running_frames > 0 ? "Render Worker Pool" : "Dispatcher Queue",
    status: mapStatus(job.state),
    backendState: job.state,
    progress: getProgress(job),
    eta: getEta(job),
    statusColor: getStatusColor(job.state),
  };
}

function getRendererName(engine: string): string {
  const normalizedEngine = engine.toLowerCase();

  if (normalizedEngine.includes("arnold")) return "arnold";
  if (normalizedEngine.includes("v-ray") || normalizedEngine.includes("vray")) {
    return "vray";
  }
  if (normalizedEngine.includes("karma")) return "karma";
  if (normalizedEngine.includes("mantra")) return "mantra";
  if (normalizedEngine.includes("mrq")) return "mrq";
  if (normalizedEngine.includes("unreal")) return "mrq";
  if (normalizedEngine.includes("cycles")) return "cycles";
  if (normalizedEngine.includes("blender")) return "cycles";

  return engine.trim().toLowerCase() || "default_renderer";
}

export function getDefaultRenderCommand(
  engine: string,
  startFrame: string,
  endFrame: string,
): string {
  const frameRange = `${startFrame}-${endFrame}`;
  const renderer = getRendererName(engine);

  if (renderer === "karma" || renderer === "mantra") {
    return `hython render.py --renderer ${renderer} --frames ${frameRange}`;
  }

  if (renderer === "arnold" || renderer === "vray") {
    return `render -renderer ${renderer} -f ${frameRange}`;
  }

  if (renderer === "mrq") {
    return `ue-mrq-render --frames ${frameRange}`;
  }

  if (renderer === "cycles") {
    return `blender -b scene.blend -E CYCLES -s ${startFrame} -e ${endFrame} -a`;
  }

  return `render --renderer ${renderer} --frames ${frameRange}`;
}

export function buildJobRequest(formData: JobFormValues): CreateJobPayload {
  const priorityMap: Record<JobPriority, number> = {
    HIGH: 80,
    MED: 50,
    LOW: 30,
  };

  const frameRange = `${formData.startFrame}-${formData.endFrame}`;
  const sanitizedName = formData.jobName.trim();

  return {
    visible_name: sanitizedName,
    project: "test",
    department: "td",
    priority: priorityMap[formData.priority],
    max_frames_per_worker: 0,
    user: formData.userId,
    log_directory: formData.logDirectory.trim(),
    layers: [
      {
        name: "default_layer",
        renderer: getRendererName(formData.engine),
        frame_range: frameRange,
        chunk_size: 1,
        command: formData.renderCommand.trim(),
      },
    ],
  };
}

export async function createJob(payload: CreateJobPayload): Promise<BackendJob> {
  const response = await apiClient.post<BackendJob>(JOBS_ENDPOINT, payload);

  return response.data;
}

export async function deleteJob(jobId: string): Promise<void> {
  await apiClient.delete(`${JOBS_ENDPOINT}${jobId}/`);
}

export function formatApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const responseMessage = stringifyApiValue(error.response?.data);

    if (responseMessage) return responseMessage;
    if (error.message) return error.message;
  }

  if (error instanceof Error) return error.message;

  return "Unable to submit this job to the backend API.";
}

export function deriveLogsFromJobs(jobs: RenderJob[]): LogEntry[] {
  return jobs.slice(0, 30).map((job) => ({
    time: job.eta,
    type:
      job.status === "Failed"
        ? "WARN"
        : job.status === "Completed"
          ? "INFO"
          : "ROUTE",
    msg: `${job.displayId} is ${job.backendState.toLowerCase()} at ${job.progress}% through ${job.node}.`,
    color:
      job.status === "Failed"
        ? "text-[#FF5D73]"
        : job.status === "Completed"
          ? "text-[#3DDC84]"
          : "text-[#5A1FA6]",
  }));
}

export function deriveTelemetryFromJobs(jobs: RenderJob[]): TelemetryMetrics {
  const totalJobs = jobs.length;
  const activeJobs = jobs.filter((job) => job.status === "Rendering").length;
  const averageProgress =
    totalJobs > 0
      ? Math.round(jobs.reduce((sum, job) => sum + job.progress, 0) / totalJobs)
      : 0;

  const vramUsage = Math.min(
    100,
    28 + activeJobs * 14 + Math.round(averageProgress * 0.25),
  );
  const cpuLoad = Math.min(
    100,
    18 + activeJobs * 18 + Math.round(averageProgress * 0.2),
  );

  const points: TelemetryPoint[] = Array.from({ length: 14 }, (_, index) => {
    const x = Math.round((index / 13) * 100);
    const taper = Math.abs(index - 10) * 2;

    return {
      x,
      vram: Math.max(0, Math.min(100, vramUsage - taper + (index % 3) * 4)),
      cpu: Math.max(0, Math.min(100, cpuLoad - taper + (index % 2) * 5)),
    };
  });

  return {
    vramUsage,
    cpuLoad,
    points,
  };
}
