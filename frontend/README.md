# RenderHive Frontend

Distributed Rendering Management Platform.

## Tech Stack
- **Framework**: [Next.js 16 (App Router)](https://nextjs.org/)
- **Runtime**: [React 19](https://react.dev/)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/)
- **UI Components**: [Shadcn UI](https://ui.shadcn.com/)
- **Icon Library**: [Lucide React](https://lucide-react.dev/)
- **Package Manager**: [pnpm](https://pnpm.io/)

## Directory Structure
- `src/app/` - Next.js App Router (pages, layouts, globals CSS)
- `src/components/` - React components
  - `ui/` - Shadcn UI generated components (e.g. `button.tsx`)
  - `common/` - Shared reusable components
  - `layout/` - Shell, header, navigation, and sidebar layouts
  - `dashboard/` - Features specific to dashboard views
- `src/hooks/` - Custom React hooks
- `src/lib/` - Helper modules and utility functions (e.g. `cn` in `utils.ts`)
- `src/services/` - API clients and services
- `src/styles/` - Additional styling configurations
- `src/types/` - Shared TypeScript interfaces and types
- `src/assets/` - Static assets (icons, images)

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

### 3. Adding New UI Components
This project is configured with Shadcn UI. To add new components:
```bash
pnpm dlx shadcn add [component-name]
```
Files will automatically be generated in `src/components/ui/` and styled with Tailwind CSS v4 variables.
