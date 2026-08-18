import createClient from "openapi-fetch";
import type { paths, components } from "@/types/schema";
import type {
  ClusterTelemetryHistory,
  DispatchTrace,
  FarmEvent,
  LogEntry,
  RecentDispatchLog,
  RenderJob,
  TaskLogDetail,
  TaskLogList,
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

// ── Dependency types ───────────────────────────────────────────────────────────

export type DependencyType = "TASK_ON_TASK" | "LAYER_ON_LAYER" | "JOB_ON_JOB";

export interface Dependency {
  id: string;
  type: DependencyType;
  dep_job: string;
  dep_job_name: string;
  dep_layer: string | null;
  dep_layer_name: string | null;
  dep_task: string | null;
  dep_task_name: string | null;
  parent_job: string;
  parent_job_name: string;
  parent_layer: string | null;
  parent_layer_name: string | null;
  parent_task: string | null;
  parent_task_name: string | null;
  is_satisfied: boolean;
  created_at: string;
  satisfied_at: string | null;
}

export interface CreateDependencyPayload {
  type: DependencyType;
  dep_job: string;
  dep_layer?: string | null;
  dep_task?: string | null;
  parent_job: string;
  parent_layer?: string | null;
  parent_task?: string | null;
}

export interface DependencyFilters {
  type?: DependencyType;
  is_satisfied?: boolean;
  dep_job?: string;
  parent_job?: string;
  dep_layer?: string;
  parent_layer?: string;
  dep_task?: string;
  parent_task?: string;
}

export interface JobFilters {
  search?: string;
  ordering?: string;
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

// ── Dependency API functions ───────────────────────────────────────────────────

export async function getDependencies(
  filters: DependencyFilters = {},
): Promise<Dependency[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null) params.set(k, String(v));
  });
  const qs = params.toString();
  const url = `${API_BASE_URL}/api/dependencies/${qs ? `?${qs}` : ""}`;
  const response = await apiFetch(url);
  if (!response.ok) throw new Error(`getDependencies: ${response.status}`);
  const json = await response.json();
  return (json.results ?? json) as Dependency[];
}

export async function getJobDependencies(jobId: string): Promise<Dependency[]> {
  const allDeps: Dependency[] = [];
  let url: string | null = `${API_BASE_URL}/api/jobs/${jobId}/dependencies/`;

  while (url) {
    const response = await apiFetch(url);
    if (!response.ok) throw new Error(`getJobDependencies: ${response.status}`);
    const json = await response.json();

    if (json.results) {
      allDeps.push(...json.results);
      url = json.next;
    } else {
      allDeps.push(...json);
      url = null;
    }
  }
  return allDeps;
}

export async function createDependency(
  payload: CreateDependencyPayload,
): Promise<Dependency> {
  const url = `${API_BASE_URL}/api/dependencies/`;
  const response = await apiFetch(url, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(JSON.stringify(err));
  }
  return response.json() as Promise<Dependency>;
}

export async function deleteDependency(dependencyId: string): Promise<void> {
  const url = `${API_BASE_URL}/api/dependencies/${dependencyId}/`;
  const response = await apiFetch(url, { method: "DELETE" });
  if (!response.ok && response.status !== 204) {
    throw new Error(`deleteDependency: ${response.status}`);
  }
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
    total_tasks: job.total_tasks,
    succeeded_tasks: job.succeeded_tasks,
    failed_tasks: job.failed_tasks,
    running_tasks: job.running_tasks,
    ready_tasks: job.ready_tasks,
    waiting_tasks: job.waiting_tasks,
    skipped_tasks: job.skipped_tasks,
    depend_tasks: job.depend_tasks,
    created_at: job.created_at,
    included_pools: job.included_pools || [],
    excluded_pools: job.excluded_pools || [],
    project: job.project || "Unknown Project",
    department: job.department || "General",
  };
}

// ── Layer Command Builder ───────────────────────────────────────────────────

export interface LayerCommandBuilderOptions {
  engine: string;
  renderer?: string;
  scenePath?: string;
  startFrame?: string | number;
  endFrame?: string | number;
  frameStep?: string | number;
  renderNode?: string;
  camera?: string;
  outputPath?: string;
  useDynamicTokens?: boolean;
}

export function getRendererName(engine: string): string {
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

export function generateLayerCommand(options: LayerCommandBuilderOptions): string {
  const {
    engine,
    renderer = "",
    scenePath = "",
    startFrame = "1",
    endFrame = "100",
    frameStep = "1",
    renderNode = "",
    camera = "",
    outputPath = "",
    useDynamicTokens = true,
  } = options;

  const normalized = engine.toLowerCase();
  const sceneToken = useDynamicTokens ? (scenePath ? `"${scenePath}"` : '"{SCENE_PATH}"') : scenePath || "scene";
  const startToken = useDynamicTokens ? "{START_FRAME}" : String(startFrame);
  const endToken = useDynamicTokens ? "{END_FRAME}" : String(endFrame);
  const stepToken = useDynamicTokens ? "{FRAME_STEP}" : String(frameStep);
  const frameToken = useDynamicTokens ? "{FRAME}" : String(startFrame);
  const nodeToken = useDynamicTokens ? (renderNode ? `"${renderNode}"` : '"{RENDER_NODE}"') : renderNode || "";
  const camToken = useDynamicTokens ? (camera ? `"${camera}"` : '"{CAMERA}"') : camera || "";

  // Houdini (Karma / Mantra / Hython ROP)
  if (normalized.includes("houdini") || normalized.includes("karma") || normalized.includes("mantra")) {
    if (normalized.includes("husk")) {
      const activeRenderer = renderer || "Karma XPU";
      return `husk --renderer "${activeRenderer}" --frame ${frameToken} ${sceneToken}`;
    }
    const ropParam = renderNode ? ` --rop ${nodeToken}` : ' --rop "{RENDER_NODE}"';
    return `"hython" -m renderhive_houdini.worker.render_rop --scene ${sceneToken}${ropParam} --frame ${frameToken}`;
  }

  // Maya (Arnold / V-Ray / Redshift)
  if (normalized.includes("maya")) {
    const activeRenderer = renderer || "arnold";
    const parts = ["Render.exe", "-r", activeRenderer, "-s", startToken, "-e", endToken, "-b", stepToken];
    if (camera) {
      parts.push("-cam", camToken);
    }
    if (outputPath) {
      parts.push("-rd", `"${outputPath}"`);
    }
    parts.push(sceneToken);
    return parts.join(" ");
  }

  // Blender (Cycles / Eevee)
  if (normalized.includes("blender") || normalized.includes("cycles")) {
    const activeEngine = (renderer || "CYCLES").toUpperCase();
    return `blender -b ${sceneToken} -E ${activeEngine} -s ${startToken} -e ${endToken} -a`;
  }

  // Unreal Engine 5 (MRQ)
  if (normalized.includes("unreal") || normalized.includes("mrq")) {
    return `ue-mrq-render --scene ${sceneToken} --frames ${startToken}-${endToken}`;
  }

  // Nuke
  if (normalized.includes("nuke")) {
    const nodeArg = renderNode ? ` -X "${renderNode}"` : " -x";
    return `nuke${nodeArg} -F ${startToken}-${endToken} ${sceneToken}`;
  }

  // Standalone Arnold Kick
  if (normalized.includes("kick") || normalized.includes("arnold kick")) {
    return `kick -i ${sceneToken} -frame ${frameToken}`;
  }

  // Standalone V-Ray
  if (normalized.includes("vray") || normalized.includes("v-ray standalone")) {
    return `vray -sceneFile=${sceneToken} -frames=${frameToken}`;
  }

  // Generic fallback
  return `render --renderer ${renderer || getRendererName(engine)} --frames ${startToken}-${endToken} ${sceneToken}`;
}

export function getDefaultRenderCommand(
  engine: string,
  startFrame: string,
  endFrame: string,
): string {
  return generateLayerCommand({
    engine,
    startFrame,
    endFrame,
    useDynamicTokens: true,
  });
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

export function computeFarmEfficiency(jobs: RenderJob[]): {
  efficiency: number;
  completedJobs: number;
  failedJobs: number;
} {
  const completedJobs = jobs.filter((job) => job.status === "Completed").length;
  const failedJobs = jobs.filter((job) => job.status === "Failed").length;
  const totalEvaluated = completedJobs + failedJobs;

  if (totalEvaluated === 0) {
    return {
      efficiency: 100,
      completedJobs,
      failedJobs,
    };
  }

  return {
    efficiency: Math.round((completedJobs / totalEvaluated) * 100),
    completedJobs,
    failedJobs,
  };
}

export function computeClusterTelemetry(
  jobs: RenderJob[],
  workers: WorkerNode[],
  previousPoints: TelemetryPoint[] = []
): TelemetryMetrics {
  const onlineWorkers = workers.filter(
    (w) => w.status === "ONLINE" || w.status === "RENDERING"
  );
  const totalOnlineCores = onlineWorkers.reduce((sum, w) => sum + (w.cores || 1), 0);
  const totalOnlineMemoryMb = onlineWorkers.reduce((sum, w) => sum + (w.memory_mb || 4096), 0);

  // Total active running tasks across the entire farm
  const activeTasks = jobs.reduce(
    (sum, j) => sum + (j.running_tasks ?? (j.status === "Rendering" ? 1 : 0)),
    0
  );

  // 1. Calculate Real CPU Cluster Load
  let cpuLoad = 0;
  const workersWithCpu = onlineWorkers.filter(
    (w) => typeof (w.system_info as Record<string, unknown> | undefined)?.cpu_percent === "number"
  );
  if (workersWithCpu.length > 0) {
    cpuLoad = Math.round(
      workersWithCpu.reduce(
        (sum, w) => sum + ((w.system_info as Record<string, unknown>).cpu_percent as number),
        0
      ) / workersWithCpu.length
    );
  } else if (totalOnlineCores > 0) {
    cpuLoad = Math.min(100, Math.round((activeTasks / totalOnlineCores) * 100));
  }

  // 2. Calculate Real System Host Memory (RAM) Utilization
  let memoryUsage = 0;
  const workersWithMem = onlineWorkers.filter(
    (w) => typeof (w.system_info as Record<string, unknown> | undefined)?.memory_percent === "number"
  );
  if (workersWithMem.length > 0) {
    memoryUsage = Math.round(
      workersWithMem.reduce(
        (sum, w) => sum + ((w.system_info as Record<string, unknown>).memory_percent as number),
        0
      ) / workersWithMem.length
    );
  } else if (totalOnlineMemoryMb > 0) {
    memoryUsage = Math.min(100, Math.round(((activeTasks * 2048) / totalOnlineMemoryMb) * 100));
  }

  // 3. Calculate Real GPU VRAM Utilization
  let vramUsage = 0;
  const workersWithVram = onlineWorkers.filter((w) => {
    const sys = w.system_info as Record<string, unknown> | undefined;
    return typeof sys?.vram_percent === "number" || typeof sys?.gpu_vram_used_mb === "number";
  });
  if (workersWithVram.length > 0) {
    vramUsage = Math.round(
      workersWithVram.reduce((sum, w) => {
        const sys = w.system_info as Record<string, unknown>;
        if (typeof sys.vram_percent === "number") {
          return sum + (sys.vram_percent as number);
        }
        const used = (sys.gpu_vram_used_mb as number) || 0;
        const total = (sys.gpu_vram_mb as number) || 1;
        return sum + (used / total) * 100;
      }, 0) / workersWithVram.length
    );
  } else if (totalOnlineMemoryMb > 0) {
    vramUsage = Math.min(100, Math.round(((activeTasks * 3584) / totalOnlineMemoryMb) * 100));
  }

  // 4. Rolling timeseries points
  const maxPoints = 15;
  let nextPoints: TelemetryPoint[];

  if (previousPoints.length === 0) {
    nextPoints = Array.from({ length: maxPoints }, (_, i) => ({
      x: Math.round((i / (maxPoints - 1)) * 100),
      cpu: cpuLoad,
      ram: memoryUsage,
      vram: vramUsage,
      active_tasks: activeTasks,
    }));
  } else {
    const updated = [
      ...previousPoints.slice(-(maxPoints - 1)),
      { x: 100, cpu: cpuLoad, ram: memoryUsage, vram: vramUsage, active_tasks: activeTasks },
    ];
    nextPoints = updated.map((pt, index) => ({
      x: Math.round((index / (updated.length - 1)) * 100),
      cpu: pt.cpu,
      ram: pt.ram ?? memoryUsage,
      vram: pt.vram,
      active_tasks: pt.active_tasks ?? activeTasks,
    }));
  }

  return {
    cpuLoad,
    memoryUsage,
    ramUsage: memoryUsage,
    vramUsage,
    points: nextPoints,
  };
}

export function deriveTelemetryFromJobs(jobs: RenderJob[]): TelemetryMetrics {
  return computeClusterTelemetry(jobs, []);
}

// ── AI Dispatch Log API ────────────────────────────────────────────────────────

export interface ScoreBreakdown {
  job_priority?: number;
  resource_fit?: number;
  failure_penalty?: number;
  dispatch_order?: number;
  _floor_clamp?: number;
  ai_adjustment?: number;
  ai_reason?: string;
}

export interface DispatchLogEntry {
  id: string;
  name: string;
  worker_name: string | null;
  started_at: string | null;
  state: string;
  job_id: string;
  job_name: string;
  job_priority: number;
  layer_name: string;
  last_score_breakdown: ScoreBreakdown;
  ai_was_invoked: boolean;
  ai_reason: string;
  final_score: number;
}

export async function fetchRecentDispatches(limit = 30): Promise<DispatchLogEntry[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/tasks/recent-dispatches/?limit=${limit}`,
    { cache: "no-store", headers: getApiHeaders() },
  );

  if (!response.ok) {
    throw new Error(`fetchRecentDispatches: ${response.status}`);
  }

  return response.json() as Promise<DispatchLogEntry[]>;
}

// ── Telemetry & Historical Analytics ──────────────────────────────────────────

export type { ClusterTelemetryHistory };

export async function fetchClusterTelemetryHistory(
  range: "1h" | "24h" | "7d" = "1h",
  pool?: string,
  worker?: string
): Promise<ClusterTelemetryHistory> {
  const params = new URLSearchParams({ range });
  if (pool) params.set("pool", pool);
  if (worker) params.set("worker", worker);

  const response = await fetch(
    `${API_BASE_URL}/api/telemetry/cluster/history/?${params.toString()}`,
    { cache: "no-store", headers: getApiHeaders() }
  );

  if (!response.ok) {
    throw new Error(`fetchClusterTelemetryHistory: ${response.status}`);
  }

  return response.json() as Promise<ClusterTelemetryHistory>;
}

export async function fetchFarmEvents(
  limit = 50,
  severity?: string,
  eventType?: string
): Promise<FarmEvent[]> {
  const params = new URLSearchParams();
  if (limit) params.set("limit", limit.toString());
  if (severity && severity !== "ALL") params.set("severity", severity);
  if (eventType) params.set("event_type", eventType);

  const qs = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}/api/telemetry/events/${qs}`, {
    cache: "no-store",
    headers: getApiHeaders(),
  });

  if (!response.ok) {
    throw new Error(`fetchFarmEvents: ${response.status}`);
  }

  const data = await response.json();
  return (Array.isArray(data) ? data : data.results || []) as FarmEvent[];
}

export async function fetchDispatchTraces(
  limit = 50,
  aiInvoked?: boolean
): Promise<DispatchTrace[]> {
  const params = new URLSearchParams();
  if (limit) params.set("limit", limit.toString());
  if (aiInvoked !== undefined) params.set("ai_invoked", aiInvoked ? "true" : "false");

  const qs = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}/api/telemetry/dispatches/${qs}`, {
    cache: "no-store",
    headers: getApiHeaders(),
  });

  if (!response.ok) {
    throw new Error(`fetchDispatchTraces: ${response.status}`);
  }

  const data = await response.json();
  return (Array.isArray(data) ? data : data.results || []) as DispatchTrace[];
}

export async function fetchTaskExecutionLogLatest(
  taskId: string
): Promise<TaskLogDetail | null> {
  const response = await fetch(
    `${API_BASE_URL}/api/telemetry/tasks/${taskId}/logs/latest/`,
    { cache: "no-store", headers: getApiHeaders() }
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`fetchTaskExecutionLogLatest: ${response.status}`);
  }

  return response.json() as Promise<TaskLogDetail>;
}

export async function fetchJobExecutionLogs(
  jobId: string
): Promise<TaskLogList[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/telemetry/jobs/${jobId}/logs/`,
    { cache: "no-store", headers: getApiHeaders() }
  );

  if (!response.ok) {
    throw new Error(`fetchJobExecutionLogs: ${response.status}`);
  }

  const data = await response.json();
  return (Array.isArray(data) ? data : data.results || []) as TaskLogList[];
}


// ── AI Scheduler Health ────────────────────────────────────────────────────────

export const AI_SCHEDULER_URL = (
  process.env.NEXT_PUBLIC_AI_SCHEDULER_URL || "http://localhost:8001"
).replace(/\/+$/, "");

export interface AiHealthStatus {
  status: "ok" | "unreachable";
  model_loaded: boolean;
  prompt_template: string;
  model_path: string | null;
  n_ctx: number;
  max_tasks_per_request: number;
}

export async function fetchAiHealth(): Promise<AiHealthStatus> {
  try {
    const response = await fetch(`${AI_SCHEDULER_URL}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json() as Promise<AiHealthStatus>;
  } catch {
    return {
      status: "unreachable",
      model_loaded: false,
      prompt_template: "unknown",
      model_path: null,
      n_ctx: 0,
      max_tasks_per_request: 0,
    };
  }
}

// ── AI Model Management ────────────────────────────────────────────────────────

export interface CuratedModel {
  name: string;
  filename: string;
  url: string;
  template: string;
  size: string;
}

export interface LocalModel {
  filename: string;
  size_bytes: number;
}

export interface ModelListResponse {
  curated: CuratedModel[];
  local: LocalModel[];
  active_path: string;
}

export interface DownloadProgress {
  is_downloading: boolean;
  filename: string;
  bytes_downloaded: number;
  total_bytes: number;
  speed_bps: number;
  error: string | null;
}

async function aiFetch(endpoint: string, options?: RequestInit): Promise<Response> {
  const res = await fetch(`${AI_SCHEDULER_URL}${endpoint}`, {
    cache: "no-store",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `AI Service Error: ${res.status}`);
  }

  return res;
}

export async function fetchModels(): Promise<ModelListResponse> {
  const res = await aiFetch("/api/v1/models");
  return res.json() as Promise<ModelListResponse>;
}

export async function startModelDownload(url: string, filename: string): Promise<void> {
  await aiFetch("/api/v1/models/download", {
    method: "POST",
    body: JSON.stringify({ url, filename }),
  });
}

export async function fetchDownloadProgress(): Promise<DownloadProgress> {
  const res = await aiFetch("/api/v1/models/download/progress");
  return res.json() as Promise<DownloadProgress>;
}

export async function cancelModelDownload(): Promise<void> {
  await aiFetch("/api/v1/models/download/cancel", { method: "DELETE" });
}

export async function loadAiModel(filename: string, prompt_template: string): Promise<void> {
  await aiFetch("/api/v1/models/load", {
    method: "POST",
    body: JSON.stringify({ filename, prompt_template }),
  });
}

export async function unloadAiModel(): Promise<void> {
  await aiFetch("/api/v1/models/unload", { method: "POST" });
}

export async function deleteAiModel(filename: string): Promise<void> {
  await aiFetch(`/api/v1/models/${encodeURIComponent(filename)}`, { method: "DELETE" });
}

// ── Worker Pool API functions ──────────────────────────────────────────────────

export type WorkerPool = components["schemas"]["WorkerPool"] & {
  online_worker_count?: number;
  rendering_worker_count?: number;
  workers?: string[];
};
export interface CreateWorkerPoolPayload {
  name: string;
  description?: string;
}
export type UpdateWorkerPoolPayload = Partial<CreateWorkerPoolPayload>;

export async function getPools(): Promise<WorkerPool[]> {
  const { data, error } = await client.GET("/api/pools/");
  if (error) throw new Error(JSON.stringify(error));
  return data?.results || [];
}

export async function createPool(payload: CreateWorkerPoolPayload): Promise<WorkerPool> {
  const { data, error } = await client.POST("/api/pools/", {
    body: payload as unknown as components["schemas"]["WorkerPool"],
  });
  if (error) throw new Error(JSON.stringify(error));
  return data as unknown as WorkerPool;
}

export async function updatePool(poolId: string, payload: UpdateWorkerPoolPayload): Promise<WorkerPool> {
  const { data, error } = await client.PATCH("/api/pools/{id}/", {
    params: { path: { id: poolId } },
    body: payload as unknown as components["schemas"]["PatchedWorkerPool"],
  });
  if (error) throw new Error(JSON.stringify(error));
  return data as unknown as WorkerPool;
}

export async function deletePool(poolId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/pools/${poolId}/`, {
    method: "DELETE",
    headers: getApiHeaders(),
    cache: "no-store",
  });

  if (!response.ok && response.status !== 204) {
    const contentType = response.headers.get("content-type") ?? "";
    const errorPayload: unknown = contentType.includes("application/json")
      ? await response.json()
      : await response.text();
    throw new Error(JSON.stringify(errorPayload));
  }
}

// ── Worker Node API functions ──────────────────────────────────────────────────

export type WorkerNode = components["schemas"]["WorkerNode"];

export async function getNodes(): Promise<WorkerNode[]> {
  const { data, error } = await client.GET("/api/workers/");
  if (error) throw new Error(JSON.stringify(error));
  return data?.results || [];
}

/**
 * Pings the lightweight API health endpoint to measure pure network/HTTP roundtrip latency.
 */
export async function pingBackendLatency(): Promise<number> {
  const start = performance.now();
  const res = await fetch(`${API_BASE_URL}/api/health/`, {
    method: "GET",
    cache: "no-store",
  });
  if (!res.ok) throw new Error("API unreachable");
  return Math.max(1, Math.round(performance.now() - start));
}


