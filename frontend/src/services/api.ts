import createClient from "openapi-fetch";
import type { paths, components } from "@/types/schema";
import type { JobFormValues } from "@/types/api";
import type {
  JobPriority,
  LogEntry,
  RenderJob,
  TelemetryMetrics,
  TelemetryPoint,
} from "@/types/dashboard";

export const API_BASE_URL = "http://localhost:8000";
const renderHiveAuthToken = process.env.NEXT_PUBLIC_RENDERHIVE_AUTH_TOKEN;

// Initialize the openapi-fetch client
export const client = createClient<paths>({
  baseUrl: API_BASE_URL,
  headers: renderHiveAuthToken
    ? { Authorization: `Token ${renderHiveAuthToken}` }
    : {},
});

// Extract types from the generated schema
export type BackendJob = components["schemas"]["JobList"];
export type BackendJobState = components["schemas"]["State1dfEnum"];

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

export async function fetchJobs(): Promise<BackendJob[]> {
  const { data, error } = await client.GET("/api/jobs/");
  
  if (error) {
    throw new Error(JSON.stringify(error));
  }

  return data?.results || [];
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

export function buildJobRequest(
  formData: JobFormValues,
): components["schemas"]["JobCreate"] {
  const priorityMap: Record<JobPriority, number> = {
    HIGH: 80,
    MED: 50,
    LOW: 30,
  };

  const frameRange = `${formData.startFrame}-${formData.endFrame}`;
  const sanitizedName = formData.jobName.trim();
  const renderer = getRendererName(formData.engine);

  let layerType: components["schemas"]["LayerTypeEnum"] = "RENDER";
  if (renderer.includes("comp") || renderer.includes("nuke")) {
    layerType = "POST";
  }

  return {
    visible_name: sanitizedName,
    project: "test",
    department: "td",
    priority: priorityMap[formData.priority],
    max_frames_per_worker: 0,
    user: String(formData.userId),
    log_directory: formData.logDirectory.trim(),
    layers: [
      {
        name: "default_layer",
        layer_type: layerType,
        frame_range: frameRange,
        chunk_size: 1,
        command: formData.renderCommand.trim(),
      },
    ],
  };
}

export async function createJob(
  payload: components["schemas"]["JobCreate"],
): Promise<BackendJob> {
  const { data, error } = await client.POST("/api/jobs/", {
    body: payload,
  });

  if (error) {
    throw new Error(JSON.stringify(error));
  }

  // The backend returns the created Job object, we cast it to BackendJob
  return data as unknown as BackendJob;
}

export async function deleteJob(jobId: string): Promise<void> {
  const { error } = await client.DELETE("/api/jobs/{id}/", {
    params: { path: { id: jobId } },
  });

  if (error) {
    throw new Error(JSON.stringify(error));
  }
}

export function formatApiError(error: unknown): string {
  try {
    if (error instanceof Error) {
      try {
        // Attempt to parse stringified JSON error payloads
        const parsedError = JSON.parse(error.message);
        const responseMessage = stringifyApiValue(parsedError);
        if (responseMessage) return responseMessage;
      } catch {
        // Not a JSON string, fallback below
      }
      return error.message;
    }
  } catch {
    // Ultimate fallback
  }

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
