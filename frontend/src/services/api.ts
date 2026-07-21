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
const AUTH_STORAGE_KEY = "renderhive-auth-session";

export interface AuthUser {
  id: number | string;
  username: string;
  displayName: string;
  email: string;
  role: string;
  initials: string;
  isStaff: boolean;
  isSuperuser: boolean;
}

export interface AuthSession {
  token?: string;
  xSessionToken?: string;
  user: AuthUser;
}

interface RawLoginUser {
  id?: number | string;
  username?: string;
  display?: string;
  email?: string;
  is_staff?: boolean;
  isStaff?: boolean;
  is_superuser?: boolean;
  isSuperuser?: boolean;
}

interface RawLoginResponse {
  token?: string;
  key?: string;
  session_token?: string;
  sessionToken?: string;
  user?: RawLoginUser;
  data?: {
    user?: RawLoginUser;
    session_token?: string;
    sessionToken?: string;
  };
  meta?: {
    session_token?: string;
    sessionToken?: string;
  };
}

export interface LoginCredentials {
  username: string;
  password: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getInitials(name: string): string {
  const parts = name
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (parts.length === 0) return "RH";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();

  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

function normalizeUser(rawUser: RawLoginUser | undefined, username: string): AuthUser {
  const displayName = rawUser?.display || rawUser?.username || username;
  const isStaff = Boolean(rawUser?.is_staff ?? rawUser?.isStaff);
  const isSuperuser = Boolean(rawUser?.is_superuser ?? rawUser?.isSuperuser);

  return {
    id: rawUser?.id ?? username,
    username: rawUser?.username ?? username,
    displayName,
    email: rawUser?.email ?? "",
    role: isSuperuser ? "Superuser" : isStaff ? "TD Admin" : "Render User",
    initials: getInitials(displayName),
    isStaff,
    isSuperuser,
  };
}

function getStoredAuthSession(): AuthSession | null {
  if (typeof window === "undefined") return null;

  try {
    const rawSession = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!rawSession) return null;

    const parsedSession: unknown = JSON.parse(rawSession);
    if (!isRecord(parsedSession) || !isRecord(parsedSession.user)) return null;

    return parsedSession as unknown as AuthSession;
  } catch {
    return null;
  }
}

export function readAuthSession(): AuthSession | null {
  return getStoredAuthSession();
}

export function persistAuthSession(session: AuthSession): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

export function clearAuthSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

function getApiHeaders(): HeadersInit {
  const session = getStoredAuthSession();

  return {
    Accept: "application/json",
    "Content-Type": "application/json",
    ...(session?.token ? { Authorization: `Token ${session.token}` } : {}),
    ...(session?.xSessionToken ? { "X-Session-Token": session.xSessionToken } : {}),
  };
}

function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return fetch(input, {
    ...init,
    headers: {
      ...getApiHeaders(),
      ...init?.headers,
    },
  });
}

// Initialize the openapi-fetch client
export const client = createClient<paths>({
  baseUrl: API_BASE_URL,
  fetch: apiFetch,
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
    user: formData.user,
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

export async function login(credentials: LoginCredentials): Promise<AuthSession> {
  const response = await fetch(`${API_BASE_URL}/_allauth/app/v1/auth/login`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(credentials),
    cache: "no-store",
  });
  const payload: unknown = await response.json();

  if (!response.ok) {
    throw new Error(JSON.stringify(payload));
  }

  const rawPayload = payload as RawLoginResponse;
  const token = rawPayload.token || rawPayload.key;
  const headerSessionToken = response.headers.get("x-session-token");
  const xSessionToken =
    headerSessionToken ||
    rawPayload.session_token ||
    rawPayload.sessionToken ||
    rawPayload.data?.session_token ||
    rawPayload.data?.sessionToken ||
    rawPayload.meta?.session_token ||
    rawPayload.meta?.sessionToken;

  if (!token && !xSessionToken) {
    throw new Error(
      JSON.stringify({
        detail: "Login succeeded, but the backend did not return an auth token.",
      }),
    );
  }

  const session: AuthSession = {
    token,
    xSessionToken,
    user: normalizeUser(rawPayload.user || rawPayload.data?.user, credentials.username),
  };

  persistAuthSession(session);
  return session;
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
