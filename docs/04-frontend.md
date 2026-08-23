# Frontend Architecture & Development

## Directory Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── layout.tsx          # Root layout + auth wrapper
│   │   ├── page.tsx            # Dashboard home
│   │   ├── jobs/
│   │   │   ├── page.tsx        # Job list + filters
│   │   │   └── [id]/
│   │   │       └── page.tsx    # Job detail view
│   │   ├── workers/
│   │   ├── settings/
│   │   └── logs/
│   ├── components/
│   │   ├── auth/               # Login, OAuth flows
│   │   ├── dashboard/          # Dashboard widgets
│   │   ├── jobs/               # Job-related components
│   │   ├── workers/            # Worker status components
│   │   ├── layout/             # Navigation, sidebar
│   │   └── ui/                 # Shadcn UI primitives (button, dialog, etc.)
│   ├── hooks/
│   │   ├── use-mobile.ts       # Responsive breakpoint detection
│   │   └── use-api.ts          # API query hook (React Query)
│   ├── services/
│   │   ├── api.ts              # API client configuration
│   │   └── utils.ts            # Helper functions
│   ├── types/
│   │   ├── api.ts              # TypeScript types for API responses
│   │   ├── dashboard.ts        # UI component prop types
│   │   └── schema.d.ts         # Generated from OpenAPI (optional)
│   └── styles/
│       └── globals.css         # Tailwind CSS + theme
├── next.config.ts             # Next.js configuration
├── tsconfig.json              # TypeScript configuration
├── eslint.config.mjs          # ESLint rules
├── postcss.config.mjs         # PostCSS + Tailwind setup
├── package.json
└── pnpm-lock.yaml            # Dependency lock (pnpm monorepo)
```

---

## Tech Stack

| Technology       | Version | Purpose                                             |
| ---------------- | ------- | --------------------------------------------------- |
| **Next.js**      | 16      | App Router, SSR, static generation                  |
| **React**        | 19      | UI components, hooks                                |
| **TypeScript**   | 5.x     | Static typing                                       |
| **Tailwind CSS** | v4      | Utility-first styling                               |
| **Shadcn UI**    | Latest  | Pre-styled components (Button, Dialog, Table, etc.) |
| **React Query**  | 5.x     | Server-state management, caching                    |
| **Axios**        | 1.x     | HTTP client                                         |
| **Zod**          | 3.x     | Runtime schema validation                           |

---

## Key Pages & Routes

### 1. Dashboard (`/`)

**Component**: `src/app/page.tsx`

**Purpose**: High-level overview of farm status

**Features**:

- Total jobs (queued, running, completed)
- Worker count (online, offline, disabled)
- Farm-wide metrics (CPU %, GPU VRAM, memory)
- Recent activity feed
- Quick links to job submission and management

**API Calls**:

```typescript
GET /api/jobs/?limit=5&ordering=-created_at  // Recent jobs
GET /api/workers/                             // Worker status
GET /api/metrics/                             // Farm-wide stats
GET /api/activity/                            // Activity feed
```

**WebSocket Events**:

- `job_state_changed` — Update job count
- `worker_telemetry_update` — Refresh metrics
- `task_state_changed` — Update activity feed

---

### 2. Job Queue (`/jobs`)

**Component**: `src/app/jobs/page.tsx`

**Purpose**: Browse, filter, and manage jobs

**Features**:

- Paginated table of all jobs
- Filters: project, department, priority, state
- Search by job name or visible_name
- Bulk operations (pause, resume, retry failed)
- Sort by: created_at, priority, state, progress

**API Calls**:

```typescript
GET /api/jobs/?page=1&limit=20&search=query&state=RUNNING&ordering=-priority

// Response:
{
  "count": 156,
  "next": "http://localhost:8000/api/jobs/?page=2",
  "results": [
    {
      "id": "uuid",
      "name": "ProjectName_ShotName_20250115",
      "visible_name": "ProjectName / ShotName",
      "state": "RUNNING",
      "priority": 75,
      "total_tasks": 100,
      "succeeded_tasks": 45,
      "failed_tasks": 3,
      "running_tasks": 2,
      "created_at": "2025-01-15T09:00:00Z"
    }
  ]
}
```

**Table Columns**:

- Job Name (linked to detail page)
- Project
- State (badge: PENDING, RUNNING, FINISHED, FAILED)
- Priority (numeric)
- Progress (progress bar: % complete)
- Tasks (succeeded/failed/running)
- Created At (relative time)
- Actions (pause, resume, delete)

---

### 3. Job Details (`/jobs/[id]`)

**Component**: `src/app/jobs/[id]/page.tsx`

**Purpose**: Detailed view of a single job

**Features**:

- Job metadata (project, department, user, submitted_at)
- State machine visualization (PENDING → RUNNING → FINISHED/FAILED)
- Layer breakdown (table of render passes)
- Task list with real-time progress
- Dependency graph (if dependencies exist)
- Log viewer (tail last 1000 lines)
- Render output gallery (images, EXR sequences)
- Manual retry interface

**Layout**:

```
┌─ Job Header ─────────────────────────┐
│ Title, State, Priority, Progress     │
└─────────────────────────────────────┘

┌─ Tabs ──────────────────────────────┐
│ [Overview] [Layers] [Tasks] [Logs]  │
└─────────────────────────────────────┘

┌─ Overview Tab ──────────────────────┐
│ Metadata:                           │
│  Project: Project X                 │
│  Department: Lighting               │
│  User: john.doe                     │
│  Submitted: 2025-01-15 09:00 UTC    │
│  Duration: 2h 34m                   │
│                                     │
│ Counters:                           │
│  Total: 100  Succeeded: 87          │
│  Waiting: 0  Running: 2             │
│  Retrying: 3  Failed: 1             │
│                                     │
│ Dependencies:                       │
│  [None] or [DAG visualization]      │
└─────────────────────────────────────┘

┌─ Layers Tab ────────────────────────┐
│ Layer | Type   | Tasks | Status     │
├───────┼────────┼───────┼────────────┤
│ beauty| RENDER |  50   | RUNNING    │
│ shadow| RENDER |  50   | READY      │
└─────────────────────────────────────┘

┌─ Tasks Tab ─────────────────────────┐
│ Frame | State  | Worker      | Time │
├───────┼────────┼─────────────┼──────┤
│ 1-10  | SUCCESS| node-01     | 45s  │
│ 11-20 | RUNNING| node-02     | 25s  │
│ 21-30 | READY  | —           | —    │
└─────────────────────────────────────┘

┌─ Logs Tab ──────────────────────────┐
│ [Tail] [Download] [Filter]          │
│                                     │
│ 2025-01-15 09:30:42 | beauty       │
│ V-Ray: Rendering frame 1…           │
│ V-Ray: GI Compute 45% complete…     │
│ V-Ray: Frame 1 rendered in 45.2 sec │
└─────────────────────────────────────┘
```

**API Calls**:

```typescript
GET /api/jobs/{id}/                    // Job metadata
GET /api/jobs/{id}/layers/             // Layers in job
GET /api/jobs/{id}/layers/{lid}/tasks/ // Tasks in layer
GET /api/jobs/{id}/dependencies/       // Dependency DAG
GET /api/jobs/{id}/logs/               // Logs (with pagination)
GET /api/jobs/{id}/outputs/            // Render outputs
```

---

### 4. Workers (`/workers`)

**Component**: `src/app/workers/page.tsx`

**Purpose**: Monitor and manage worker pool

**Features**:

- Worker grid (status, utilization, capabilities)
- Worker pool filtering
- Real-time telemetry (CPU, RAM, GPU)
- Disable/enable worker
- View worker logs
- Task assignment details

**Worker Card**:

```
┌──────────────────────────────┐
│ render-node-01       [ONLINE]│  ← Status badge
├──────────────────────────────┤
│ Pool: STUDIO_A               │
│ CPU: 12/16 cores (75%)  ▓▓▓▓ │  ← Progress bar
│ RAM: 24/32 GB (75%)     ▓▓▓▓ │
│ GPU: 2/2 online               │
│   └─ GPU 0: 85% VRAM, 92% use │
│   └─ GPU 1: 45% VRAM, 23% use │
│                              │
│ Tasks Running: 2             │
│ Maya 2024 | Arnold 7 | V-Ray │  ← Capabilities
└──────────────────────────────┘
```

---

### 5. Settings (`/settings`)

**Component**: `src/app/settings/page.tsx`

**Purpose**: User preferences and API token management

**Sections**:

- Profile (display name, email, department)
- API Tokens (generate, revoke, view usage)
- Preferences (theme, refresh rate, notification frequency)
- Connected DCCs (registered Maya installs, Houdini versions)

---

## State Management

### Server State (API Cache)

**Using React Query**:

```typescript
// src/hooks/use-api.ts
export function useJobs(filters?: JobFilters) {
  return useQuery({
    queryKey: ["jobs", filters],
    queryFn: async () => {
      const res = await api.get("/jobs/", { params: filters });
      return res.data;
    },
    staleTime: 5000, // 5 seconds
    gcTime: 1000 * 60 * 5, // 5 minute garbage collection
  });
}

export function useJob(jobId: string) {
  return useQuery({
    queryKey: ["jobs", jobId],
    queryFn: () => api.get(`/jobs/${jobId}/`),
    enabled: !!jobId, // Only fetch if jobId exists
  });
}
```

**Usage in Component**:

```typescript
export function JobList() {
  const [filters, setFilters] = useState({ state: 'RUNNING' });
  const { data: jobs, isLoading, error } = useJobs(filters);

  if (isLoading) return <Skeleton />;
  if (error) return <Error message={error.message} />;

  return (
    <table>
      {jobs.results.map(job => (
        <JobRow key={job.id} job={job} />
      ))}
    </table>
  );
}
```

### Client State (UI)

**Using React Context or URL State**:

```typescript
// For filters, pagination, modals: store in URL query params
// Reason: survives page refresh, shareable URLs

export function JobFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const state = searchParams.get('state') || '';
  const page = searchParams.get('page') || '1';

  const handleStateChange = (newState: string) => {
    const params = new URLSearchParams(searchParams);
    params.set('state', newState);
    params.set('page', '1');  // Reset pagination
    router.push(`/jobs?${params.toString()}`);
  };

  return (
    <Select value={state} onValueChange={handleStateChange}>
      <Option value="RUNNING">Running</Option>
      <Option value="FINISHED">Finished</Option>
    </Select>
  );
}
```

---

## Real-Time Updates via WebSocket

**Connection & Authentication**:

```typescript
// src/services/websocket.ts
export class JobWebSocket {
  private ws: WebSocket | null = null;

  connect(token: string) {
    const url = `${process.env.NEXT_PUBLIC_WS_URL}/api/ws/?token=${token}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log("WebSocket connected");
      // Optionally send subscription request
      this.ws?.send(
        JSON.stringify({
          type: "subscribe",
          channels: ["jobs", "workers", "tasks"],
        }),
      );
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      // Dispatch events to React Query or store
      if (message.type === "job_state_changed") {
        queryClient.setQueryData(["jobs", message.job_id], (old: any) => ({
          ...old,
          state: message.new_state,
        }));
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      // Fallback to polling
    };
  }

  disconnect() {
    this.ws?.close();
  }
}
```

**Usage**:

```typescript
export function useRealtimeJobs() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  useEffect(() => {
    if (!user) return;

    const ws = new JobWebSocket();
    ws.connect(user.token);

    return () => ws.disconnect();
  }, [user, queryClient]);
}
```

---

## API Client Configuration

**Axios instance** (`src/services/api.ts`):

```typescript
import axios from "axios";
import { useAuth } from "@/hooks/use-auth";

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor: add auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("authToken");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired, redirect to login
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export default api;
```

---

## Type Definitions

**API Response Types** (`src/types/api.ts`):

```typescript
export interface Job {
  id: string;
  name: string;
  visible_name: string;
  project: string;
  department: string;
  user: string;
  submitted_by: User | null;
  state: JobState;
  priority: number;
  total_tasks: number;
  waiting_tasks: number;
  ready_tasks: number;
  running_tasks: number;
  succeeded_tasks: number;
  failed_tasks: number;
  skipped_tasks: number;
  created_at: string;
  updated_at: string;
  stopped_at: string | null;
}

export type JobState = "PENDING" | "RUNNING" | "FINISHED" | "FAILED" | "PAUSED";

export interface Layer {
  id: string;
  job_id: string;
  name: string;
  type: "RENDER" | "UTIL" | "POST";
  order: number;
  state: LayerState;
}

export type LayerState =
  | "WAITING"
  | "READY"
  | "RUNNING"
  | "FINISHED"
  | "FAILED";

export interface Task {
  id: string;
  layer_id: string;
  frame_start: number;
  frame_end: number;
  state: TaskState;
  retry_count: number;
  max_retries: number;
  worker_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  exit_code: number | null;
}

export type TaskState =
  | "WAITING"
  | "READY"
  | "RUNNING"
  | "CHECKPOINT"
  | "SUCCEEDED"
  | "FAILED"
  | "SKIPPED";

export interface Worker {
  id: string;
  name: string;
  pool: string;
  state: "ONLINE" | "OFFLINE" | "DISABLED";
  telemetry: WorkerTelemetry;
  capabilities: WorkerCapabilities;
  last_heartbeat: string;
}

export interface WorkerTelemetry {
  cpu_usage_percent: number;
  memory_usage_gb: number;
  memory_total_gb: number;
  gpu_count: number;
  gpu_memory_gb: number[];
  gpu_usage_percent: number[];
}

export interface WorkerCapabilities {
  cpu_cores: number;
  memory_gb: number;
  gpu_count: number;
  software: string[];
}
```

---

## Styling with Tailwind CSS v4

**Theme Variables** (`src/styles/globals.css`):

```css
@theme {
  --color-primary: #2563eb;
  --color-primary-dark: #1e40af;
  --color-success: #10b981;
  --color-danger: #ef4444;
  --color-warning: #f59e0b;
  --spacing-xs: 0.25rem;
  --spacing-sm: 0.5rem;
  --spacing-md: 1rem;
  --spacing-lg: 1.5rem;
  --spacing-xl: 2rem;
}

@layer components {
  .badge-success {
    @apply inline-flex px-3 py-1 text-xs font-semibold text-white bg-green-600 rounded-full;
  }

  .badge-danger {
    @apply inline-flex px-3 py-1 text-xs font-semibold text-white bg-red-600 rounded-full;
  }

  .card {
    @apply p-6 bg-white border border-gray-200 rounded-lg shadow-sm;
  }
}
```

---

## Development Workflow

### Local Development with Hot Reload

```bash
cd frontend
pnpm install
pnpm dev

# Runs on http://localhost:3000
# Changes hot-reload automatically
```

### Building for Production

```bash
pnpm build  # Builds optimized production bundle
pnpm start  # Runs production server
```

### Linting & Type Checking

```bash
pnpm lint      # ESLint check
pnpm typecheck # TypeScript check
pnpm format    # Prettier formatting
```

---

## Performance Optimizations

1. **Image Optimization**: Next.js `<Image>` component with automatic resizing
2. **Code Splitting**: Route-based splitting via App Router
3. **Caching**: React Query with 5s stale time for fast UI updates
4. **Lazy Loading**: Components loaded on-demand
5. **WebSocket over Polling**: Real-time updates without excessive HTTP calls

---

## Accessibility

- ARIA labels on interactive elements
- Keyboard navigation support (Tab, Enter, Esc)
- High contrast mode support
- Screen reader friendly
- Semantic HTML structure

---

This frontend provides a modern, responsive dashboard for orchestrating and monitoring distributed rendering jobs.
