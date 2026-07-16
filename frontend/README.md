# RenderHive Frontend

Distributed Rendering Management Platform.

## Tech Stack
- **Framework**: [Next.js 16 (App Router)](https://nextjs.org/)
- **Runtime**: [React 19](https://react.dev/)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/)
- **Icon Library**: [Lucide React](https://lucide-react.dev/)
- **Package Manager**: [pnpm](https://pnpm.io/)

## Directory Structure
- `src/app/layout.tsx` - Root layout, providers, and dashboard shell wiring
- `src/app/page.tsx` - Main RenderHive dashboard page
- `src/app/globals.css` - Global Tailwind CSS and theme styles
- `src/app/components/` - RenderHive dashboard UI components
- `src/app/lib/api.ts` - Axios client, auth header setup, API helpers, and payload builders
- `src/app/types/` - Shared TypeScript dashboard types
- `public/` - Brand assets used by the app shell

## Getting Started

### 1. Install Dependencies
```bash
pnpm install
```

### 2. Run Development Server
```bash
pnpm dev
```
Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

