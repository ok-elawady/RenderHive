import createClient from "openapi-fetch";
import type { paths, components } from "@/types/schema";
import type {
  LogEntry,
  RenderJob,
  TelemetryMetrics,
  TelemetryPoint,
} from "@/types/dashboard";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");
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
  firstName?: string;
  lastName?: string;
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
  display_name?: string;
  email?: string;
  first_name?: string;
  firstName?: string;
  last_name?: string;
  lastName?: string;
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

export interface CurrentUserProfile {
  id: number | string;
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  role: string;
  isStaff: boolean;
  isSuperuser: boolean;
}

export interface ChangePasswordPayload {
  currentPassword: string;
  newPassword: string;
}

export const USER_TITLE_ROLES = [
  "Technical Director",
  "Animator",
  "Pipeline Engineer",
  "FX Artist",
  "Lighting Lead",
  "Render User",
] as const;

export const USER_ACCESS_LEVELS = ["Superuser", "Staff", "Client"] as const;

export type UserTitleRole = (typeof USER_TITLE_ROLES)[number];
export type UserAccessLevel = (typeof USER_ACCESS_LEVELS)[number];

export interface User {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  username: string;
  email: string;
  title_role: string;
  access_level: UserAccessLevel;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  date_joined: string;
  last_login: string | null;
}

export interface CreateUserPayload {
  first_name: string;
  last_name: string;
  username: string;
  email: string;
  title_role: UserTitleRole;
  access_level: UserAccessLevel;
  password: string;
}

export interface UpdateUserPayload {
  first_name?: string;
  last_name?: string;
  email?: string;
  title_role?: UserTitleRole;
  access_level?: UserAccessLevel;
}

export interface ResetPasswordPayload {
  password?: string;
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

function getRawUser(payload: RawLoginResponse): RawLoginUser | undefined {
  return payload.user ?? payload.data?.user;
}

function getNameParts(
  rawUser: RawLoginUser | undefined,
  fallbackUser?: AuthUser | null,
): { firstName: string; lastName: string } {
  const displayName =
    rawUser?.display_name?.trim() ||
    rawUser?.display?.trim() ||
    fallbackUser?.displayName.trim() ||
    "";
  const displayParts = displayName.split(/\s+/).filter(Boolean);
  const displayFirstName = displayParts.at(0) ?? "";
  const displayLastName = displayParts.slice(1).join(" ");

  return {
    firstName:
      rawUser?.first_name?.trim() ||
      rawUser?.firstName?.trim() ||
      fallbackUser?.firstName?.trim() ||
      displayFirstName,
    lastName:
      rawUser?.last_name?.trim() ||
      rawUser?.lastName?.trim() ||
      fallbackUser?.lastName?.trim() ||
      displayLastName,
  };
}

function normalizeUser(rawUser: RawLoginUser | undefined, username: string): AuthUser {
  const { firstName, lastName } = getNameParts(rawUser);
  const displayName =
    rawUser?.display_name ||
    rawUser?.display ||
    [firstName, lastName].filter(Boolean).join(" ") ||
    rawUser?.username ||
    username;
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
    firstName,
    lastName,
  };
}

function normalizeProfile(rawUser: RawLoginUser | undefined, fallbackUser: AuthUser | null): CurrentUserProfile {
  const { firstName, lastName } = getNameParts(rawUser, fallbackUser);
  const isStaff = Boolean(rawUser?.is_staff ?? rawUser?.isStaff ?? fallbackUser?.isStaff);
  const isSuperuser = Boolean(rawUser?.is_superuser ?? rawUser?.isSuperuser ?? fallbackUser?.isSuperuser);
  const username = rawUser?.username || fallbackUser?.username || "";

  return {
    id: rawUser?.id ?? fallbackUser?.id ?? username,
    username,
    email: rawUser?.email || fallbackUser?.email || "",
    firstName,
    lastName,
    role: isSuperuser ? "Superuser" : isStaff ? "TD Admin" : "Render User",
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

async function parseApiResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  return undefined as T;
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
export type TaskList = components["schemas"]["TaskList"];
export type TaskDetail = components["schemas"]["TaskDetail"];
export type JobStateFilter = NonNullable<
  NonNullable<paths["/api/jobs/"]["get"]["parameters"]["query"]>["state"]
>;
export type TaskStateFilter = NonNullable<
  NonNullable<
    paths["/api/jobs/{job_pk}/layers/{layer_pk}/tasks/"]["get"]["parameters"]["query"]
  >["state"]
>;

export interface JobFilters {
  project?: string;
  department?: string;
  state?: JobStateFilter;
  user?: string;
}



function mapStatus(state: BackendJobState): RenderJob["status"] {
  if (state === "RUNNING") return "Rendering";
  if (state === "PAUSED") return "Paused";
  if (state === "PENDING") return "Queued";
  if (state === "FINISHED") return "Completed";
  return "Failed";
}

function getProgress(job: BackendJob): number {
  if (job.total_tasks <= 0) return 0;

  return Math.round(
    ((job.succeeded_tasks + job.skipped_tasks) / job.total_tasks) * 100,
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

export async function getLayerTasks(
  jobId: string,
  layerId: string,
  state?: TaskStateFilter,
): Promise<TaskList[]> {
  const { data, error } = await client.GET(
    "/api/jobs/{job_pk}/layers/{layer_pk}/tasks/",
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

export async function skipTask(taskId: string): Promise<TaskDetail> {
  const { data, error } = await client.POST("/api/tasks/{id}/skip/", {
    params: { path: { id: taskId } },
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
    taskCounts: `${job.succeeded_tasks + job.skipped_tasks}/${job.total_tasks}`,
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

export async function getUsers(ordering?: string): Promise<User[]> {
  const query = ordering ? `?ordering=${encodeURIComponent(ordering)}` : "";
  const response = await apiFetch(`${API_BASE_URL}/api/users/${query}`, {
    method: "GET",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(JSON.stringify(await parseApiResponse<unknown>(response)));
  }

  return parseApiResponse<User[]>(response);
}

export async function createUser(
  payload: CreateUserPayload,
): Promise<User> {
  const response = await apiFetch(`${API_BASE_URL}/api/users/`, {
    method: "POST",
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(JSON.stringify(await parseApiResponse<unknown>(response)));
  }

  return parseApiResponse<User>(response);
}

export async function updateUser(
  userId: number,
  payload: UpdateUserPayload,
): Promise<User> {
  const response = await apiFetch(`${API_BASE_URL}/api/users/${userId}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(JSON.stringify(await parseApiResponse<unknown>(response)));
  }

  return parseApiResponse<User>(response);
}

export async function resetUserPassword(
  userId: number,
  payload: ResetPasswordPayload,
): Promise<User> {
  const response = await apiFetch(`${API_BASE_URL}/api/users/${userId}/password/`, {
    method: "PUT",
    body: JSON.stringify(payload),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(JSON.stringify(await parseApiResponse<unknown>(response)));
  }

  return parseApiResponse<User>(response);
}

export async function deleteUser(userId: number): Promise<void> {
  const response = await apiFetch(`${API_BASE_URL}/api/users/${userId}/`, {
    method: "DELETE",
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(JSON.stringify(await parseApiResponse<unknown>(response)));
  }
}

export async function fetchCurrentUserProfile(): Promise<CurrentUserProfile> {
  const fallbackSession = readAuthSession();
  const response = await fetch(`${API_BASE_URL}/_allauth/app/v1/auth/session`, {
    method: "GET",
    headers: getApiHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    if (fallbackSession?.user) {
      return normalizeProfile(undefined, fallbackSession.user);
    }

    throw new Error(JSON.stringify(await parseApiResponse<unknown>(response)));
  }

  const payload = await parseApiResponse<RawLoginResponse>(response);
  return normalizeProfile(getRawUser(payload), fallbackSession?.user ?? null);
}

export async function changePassword(payload: ChangePasswordPayload): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/_allauth/app/v1/account/password/change`, {
    method: "POST",
    headers: getApiHeaders(),
    body: JSON.stringify({
      current_password: payload.currentPassword,
      new_password: payload.newPassword,
    }),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(JSON.stringify(await parseApiResponse<unknown>(response)));
  }

  try {
    const headerSessionToken = response.headers.get("x-session-token");
    const responseBody = await parseApiResponse<RawLoginResponse>(response);
    const newSessionToken =
      headerSessionToken ||
      responseBody.session_token ||
      responseBody.sessionToken ||
      responseBody.meta?.session_token ||
      responseBody.meta?.sessionToken;

    if (newSessionToken) {
      const currentSession = getStoredAuthSession();
      if (currentSession) {
        persistAuthSession({
          ...currentSession,
          xSessionToken: newSessionToken,
        });
      }
    }
  } catch {
    // Ignore JSON parsing if allauth returned an empty 200/204 response
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
    user: normalizeUser(getRawUser(rawPayload), credentials.username),
  };

  persistAuthSession(session);
  return session;
}

export function formatApiError(error: unknown): string {
  if (!error) return "An unexpected error occurred.";

  try {
    let payload: unknown = error;
    if (error instanceof Error) {
      try {
        payload = JSON.parse(error.message);
      } catch {
        return error.message;
      }
    }

    if (isRecord(payload)) {
      // 1. Allauth 410 Gone (Session Expired / Invalid Session Token)
      if (payload.status === 410) {
        return "Your session has expired. Please log in again.";
      }

      // 2. Allauth errors array: [{ message: "...", param: "..." }]
      if (Array.isArray(payload.errors) && payload.errors.length > 0) {
        const messages = payload.errors
          .map((err) => (isRecord(err) && typeof err.message === "string" ? err.message : null))
          .filter(Boolean);
        if (messages.length > 0) return messages.join(" ");
      }

      // 3. Simple detail string
      if (typeof payload.detail === "string") {
        return payload.detail;
      }

      // 4. Object dictionary of field errors
      const fieldMessages: string[] = [];
      for (const [key, value] of Object.entries(payload)) {
        if (key === "status" || key === "meta") continue;
        if (typeof value === "string") {
          fieldMessages.push(value);
        } else if (Array.isArray(value)) {
          const strValues = value.filter((v): v is string => typeof v === "string");
          if (strValues.length > 0) fieldMessages.push(strValues.join(" "));
        }
      }
      if (fieldMessages.length > 0) return fieldMessages.join(" ");
    }
  } catch {
    // Fallback
  }

  if (error instanceof Error) return error.message;
  return "An error occurred while processing your request.";
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
