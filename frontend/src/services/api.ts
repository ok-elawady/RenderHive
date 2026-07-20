import createClient from "openapi-fetch";
import type { paths, components } from "@/types/schema";
import type { JobFormValues } from "@/types/api";
import type {
  LogEntry,
  RenderJob,
  TelemetryMetrics,
  TelemetryPoint,
} from "@/types/dashboard";

export const API_BASE_URL = "http://localhost:8000";
const renderHiveAuthToken = process.env.NEXT_PUBLIC_RENDERHIVE_AUTH_TOKEN;
const renderHiveAdminAuthToken =
  process.env.NEXT_PUBLIC_RENDERHIVE_ADMIN_AUTH_TOKEN;

function getApiHeaders(): HeadersInit {
  const token = renderHiveAdminAuthToken || renderHiveAuthToken;

  return {
    Accept: "application/json",
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Token ${token}` } : {}),
  };
}

// Initialize the openapi-fetch client
export const client = createClient<paths>({
  baseUrl: API_BASE_URL,
  headers: getApiHeaders(),
});

// Extract types from the generated schema
export type BackendJob = components["schemas"]["JobList"];
export type BackendJobState = components["schemas"]["State1dfEnum"];
export type JobDetail = components["schemas"]["JobDetail"];
export type JobPatch = components["schemas"]["PatchedJobPatch"];
export type LayerList = components["schemas"]["LayerList"];
export type LayerDetail = components["schemas"]["LayerDetail"];
export type FrameList = components["schemas"]["FrameList"];
export type FrameDetail = components["schemas"]["FrameDetail"];
export type JobStateFilter = NonNullable<
  NonNullable<paths["/api/jobs/"]["get"]["parameters"]["query"]>["state"]
>;
export type FrameStateFilter = NonNullable<
  NonNullable<
    paths["/api/jobs/{job_pk}/layers/{layer_pk}/frames/"]["get"]["parameters"]["query"]
  >["state"]
>;

export interface JobFilters {
  project?: string;
  department?: string;
  state?: JobStateFilter;
  user?: string;
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



export async function fetchJobs(): Promise<BackendJob[]> {
  const { data, error } = await client.GET("/api/jobs/");
  
  if (error) {
    throw new Error(JSON.stringify(error));
  }

  return data?.results || [];
}

export async function getJobs(filters: JobFilters = {}): Promise<BackendJob[]> {
  const { data, error } = await client.GET("/api/jobs/", {
    params: { query: filters },
  });

  if (error) {
    throw new Error(JSON.stringify(error));
  }

  return data?.results || [];
}

export async function getJob(jobId: string): Promise<JobDetail> {
  const { data, error } = await client.GET("/api/jobs/{id}/", {
    params: { path: { id: jobId } },
  });

  if (error) {
    throw new Error(JSON.stringify(error));
  }

  return data;
}

export async function updateJob(
  jobId: string,
  payload: JobPatch,
): Promise<components["schemas"]["JobPatch"]> {
  const { data, error } = await client.PATCH("/api/jobs/{id}/", {
    params: { path: { id: jobId } },
    body: payload,
  });

  if (error) {
    throw new Error(JSON.stringify(error));
  }

  return data;
}

export async function abortJob(jobId: string): Promise<void> {
  await deleteJob(jobId);
}

export async function pauseJob(jobId: string): Promise<JobDetail> {
  const { data, error } = await client.POST("/api/jobs/{id}/pause/", {
    params: { path: { id: jobId } },
  });

  if (error) {
    throw new Error(JSON.stringify(error));
  }

  return data;
}

export async function resumeJob(jobId: string): Promise<JobDetail> {
  const { data, error } = await client.POST("/api/jobs/{id}/resume/", {
    params: { path: { id: jobId } },
  });

  if (error) {
    throw new Error(JSON.stringify(error));
  }

  return data;
}

export async function getJobLayers(jobId: string): Promise<LayerList[]> {
  const { data, error } = await client.GET("/api/jobs/{job_pk}/layers/", {
    params: { path: { job_pk: jobId } },
  });

  if (error) {
    throw new Error(JSON.stringify(error));
  }

  return data?.results || [];
}

export async function getLayer(
  jobId: string,
  layerId: string,
): Promise<LayerDetail> {
  const { data, error } = await client.GET("/api/jobs/{job_pk}/layers/{id}/", {
    params: { path: { job_pk: jobId, id: layerId } },
  });

  if (error) {
    throw new Error(JSON.stringify(error));
  }

  return data;
}

export async function getLayerFrames(
  jobId: string,
  layerId: string,
  state?: FrameStateFilter,
): Promise<FrameList[]> {
  const { data, error } = await client.GET(
    "/api/jobs/{job_pk}/layers/{layer_pk}/frames/",
    {
      params: {
        path: { job_pk: jobId, layer_pk: layerId },
        query: state ? { state } : undefined,
      },
    },
  );

  if (error) {
    throw new Error(JSON.stringify(error));
  }

  return data?.results || [];
}

export async function skipFrame(frameId: string): Promise<FrameDetail> {
  const { data, error } = await client.POST("/api/frames/{id}/skip/", {
    params: { path: { id: frameId } },
  });

  if (error) {
    throw new Error(JSON.stringify(error));
  }

  return data;
}

export function mapBackendJobToRenderJob(job: BackendJob): RenderJob {
  return {
    id: job.id,
    displayId: job.visible_name || job.name,
    priority: job.priority,
    user: job.user || "System",
    status: mapStatus(job.state),
    backendState: job.state,
    progress: getProgress(job),
    frameCounts: `${job.succeeded_frames + job.skipped_frames}/${job.total_frames}`,
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
    priority: formData.priority,
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
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/`, {
    method: "DELETE",
    headers: getApiHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    const errorPayload: unknown = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    throw new Error(JSON.stringify(errorPayload));
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
    time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    type:
      job.status === "Failed"
        ? "WARN"
        : job.status === "Completed"
          ? "INFO"
          : "ROUTE",
    msg: `${job.displayId} is ${job.backendState.toLowerCase()} at ${job.progress}% for ${job.user}.`,
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
