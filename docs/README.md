# RenderHive Documentation

## Overview

This directory contains the complete technical and operational documentation for RenderHive, a distributed render farm platform supporting multiple DCCs (Maya, Houdini, Blender) with AI-assisted task scheduling.

**Total Documentation**: 30,000+ lines across 11 comprehensive markdown files.

## 📖 Start Here

**New to RenderHive?** Start with [00-index.md](00-index.md) — it provides navigation, quick-start guides, and links to all documentation.

**In a hurry?** Use these quick links:

- **Setup in 5 min**: [03-setup.md - Part A](03-setup.md#part-a-docker-compose-local-development-5-minutes)
- **Submit first job**: [03-setup.md - Part C](03-setup.md#part-c-first-render-job-execution)
- **API Endpoints**: [09-api-reference.md](09-api-reference.md)
- **Something broken?**: [10-troubleshooting.md](10-troubleshooting.md)

## 📚 Documentation Files

### Core Documentation

#### [00-index.md](00-index.md) — Navigation Hub

Quick-reference index with:

- Document overview table
- Getting started guides (5-45 minutes)
- Architecture diagrams
- Key concepts and routes
- Common issues quick-links
- Technology stack summary

**Who should read**: Everyone (start here)

---

#### [01-overview.md](01-overview.md) — Project Overview

High-level introduction covering:

- Problem statement (why RenderHive exists)
- Feature matrix (11 core capabilities)
- Complete render job lifecycle
- Supported DCCs and integrations
- Technology stack with versions
- Target use cases and scale

**Who should read**: Architects, managers, new team members  
**Read time**: 15 minutes

---

#### [02-architecture.md](02-architecture.md) — Technical Architecture

Deep technical dive covering:

- 6 core system components
- Job/Layer/Task/Dependency data model
- State machines (Job, Task, Layer)
- Scheduling and dispatch logic
- Database schema (7 tables with indexes)
- Real-time update architecture
- WebSocket message types

**Who should read**: Developers, architects  
**Read time**: 30 minutes

---

#### [03-setup.md](03-setup.md) — Setup & Deployment

Production-quality setup guide with 9 parts:

**Part A**: Docker Compose (5 min, all-in-one)  
**Part B**: Native Python+Node dev environment  
**Part C**: First render job walkthrough  
**Part D**: Worker node deployment (Windows)  
**Part E**: Kubernetes production deployment (AKS/EKS/GKE)  
**Part F**: Configuration reference (30+ env vars)  
**Part G**: Troubleshooting scenarios (5 common issues)  
**Part H**: Health monitoring & observability  
**Part I**: Security pre-deployment checklist

**Who should read**: DevOps, developers, operators  
**Read time**: 45 minutes

---

#### [04-frontend.md](04-frontend.md) — Frontend Architecture

React/Next.js frontend documentation:

- Project structure (pages, components, hooks, services)
- 5 key pages (Dashboard, Jobs, Job Details, Workers, Settings)
- Routing with Next.js App Router
- React Query setup (caching, stale-while-revalidate)
- WebSocket integration for real-time updates
- API client configuration and interceptors
- TypeScript types for all API responses
- Tailwind CSS v4 theme and component utilities
- Development workflow and best practices

**Who should read**: Frontend developers  
**Read time**: 30 minutes

---

#### [05-backend.md](05-backend.md) — Backend Architecture

Django REST Framework backend documentation:

- App structure (jobs, workers, users, config)
- Complete data models with field details
- Counter cache optimization patterns
- 15+ REST endpoints with JSON schemas
- DRF serializers and validation logic
- 4 core Celery tasks (dispatch, process, telemetry, health)
- Deterministic scoring algorithm (formula + weights)
- Authentication & permissions
- Error handling and validation

**Who should read**: Backend developers  
**Read time**: 40 minutes

---

#### [06-ai-system.md](06-ai-system.md) — AI Scheduler

Local LLM-powered task ranking system:

- When and why AI is queried (tie-breaking for similar scores)
- FastAPI microservice architecture
- llama-cpp-python model loading and inference
- TinyLlama 1.1B model details
- Prompt engineering for task ranking
- Graceful degradation (fallback to deterministic)
- Performance benchmarks (40-60ms inference)
- Configuration and model management
- Monitoring and observability

**Who should read**: ML/AI engineers, backend developers  
**Read time**: 20 minutes

---

#### [07-rendering-system.md](07-rendering-system.md) — Rendering Lifecycle

Complete end-to-end rendering pipeline:

- 9-phase rendering lifecycle (submission to delivery)
- Artist flow (Maya submission with validation)
- Backend job construction (layers → tasks → dependencies)
- Dependency resolution (topological sort)
- Task scoring & dispatch logic
- Worker task fetching (heartbeat polling)
- Render execution (subprocess, DCC commands)
- Error handling and retry logic
- Log streaming architecture (100-line buffer, 5s timeout)
- Real-time telemetry (CPU, RAM, GPU)
- Post-completion verification

**Render commands for**:

- Maya (mayabatch, vray render)
- Houdini (hrender, ROP)
- Blender (blender -b, cycles)

**Who should read**: Rendering engineers, backend developers  
**Read time**: 35 minutes

---

#### [08-plugin-system.md](08-plugin-system.md) — Plugin Architecture

Extensible DCC plugin framework:

- BaseRenderPlugin abstract class
- Maya plugin reference implementation
- Scene validation (7-point checklist)
- Job payload construction
- Layer-to-task mapping with frame batching
- Dependency graph generation
- PySide6 Qt UI dialog
- Drag-to-install installation mechanism
- Workflow for adding Houdini/Blender support
- Best practices and patterns

**Who should read**: Plugin developers, rendering engineers  
**Read time**: 30 minutes

---

#### [09-api-reference.md](09-api-reference.md) — Complete API Reference

Definitive REST & WebSocket API documentation:

**Authentication**:

- Bearer token format
- Token generation
- Session-based (browser)

**Endpoints** (30+):

- Jobs (GET list, POST create, GET detail, PATCH update, DELETE)
- Layers (GET, POST, PATCH state)
- Tasks (GET, POST, PATCH report)
- Workers (GET, heartbeat, next-task)
- Pools, Users, Auth

**WebSocket Messages**:

- job_state_changed
- task_state_changed
- worker_telemetry_update

**Error Handling**:

- Standard error response format
- HTTP status codes (200, 201, 204, 400, 401, 403, 404, 409, 500)
- Error codes table

**SDKs**:

- Python (requests library)
- TypeScript (fetch, WebSocket)

**OpenAPI Documentation**:

- Swagger UI
- ReDoc
- Schema endpoints

**Who should read**: Integration engineers, SDK developers, API users  
**Read time**: 25 minutes

---

#### [10-troubleshooting.md](10-troubleshooting.md) — Troubleshooting Guide

Practical solutions for common issues:

**Docker & Deployment** (5 issues)

- Permission denied
- PostgreSQL won't start
- API can't connect to PostgreSQL
- Redis connection refused

**Database** (2 issues)

- Migrations not applied
- Superuser not created

**Backend/API** (8 issues)

- 401 Unauthorized
- CORS errors
- Celery tasks not running
- Import errors
- Tasks not dispatching
- Slow API response
- Memory leaks

**Frontend** (2 issues)

- Dashboard won't load
- API calls fail with 404
- WebSocket connection fails

**Workers** (3 issues)

- Worker can't connect to API
- Worker goes offline
- Tasks fail with "File not found"
- Memory exhaustion

**Maya Plugin** (2 issues)

- Menu doesn't appear
- Scene validation fails repeatedly

**Performance** (2 issues)

- Dashboard sluggish
- Celery tasks slow
- Memory leaks

**Debugging Tools**:

- Enable debug logging
- Check application logs
- Test service connectivity

**Support Resources**:

- How to collect diagnostics
- GitHub issues template
- Support contact info

**Who should read**: Everyone (when troubleshooting)  
**Read time**: 20 minutes

---

## 🗺️ Navigation Tips

### By Role

**Frontend Developer** → [04-frontend.md](04-frontend.md)  
**Backend Developer** → [05-backend.md](05-backend.md)  
**DevOps/SRE** → [03-setup.md](03-setup.md)  
**Plugin Developer** → [08-plugin-system.md](08-plugin-system.md)  
**ML/AI Engineer** → [06-ai-system.md](06-ai-system.md)  
**Rendering Engineer** → [07-rendering-system.md](07-rendering-system.md)  
**New to RenderHive** → [00-index.md](00-index.md) → [01-overview.md](01-overview.md)  
**Troubleshooting** → [10-troubleshooting.md](10-troubleshooting.md)

### By Task

**Set up local dev** → [03-setup.md - Part A](03-setup.md#part-a-docker-compose-local-development-5-minutes)  
**Deploy to production** → [03-setup.md - Part E](03-setup.md#part-e-kubernetes-production-deployment)  
**Add API endpoint** → [05-backend.md - Backend Development](05-backend.md)  
**Add frontend page** → [04-frontend.md - Frontend Development](04-frontend.md)  
**Add DCC support** → [08-plugin-system.md - Adding New DCCs](08-plugin-system.md#adding-support-for-new-dccs)  
**Debug failing job** → [10-troubleshooting.md](10-troubleshooting.md) + [07-rendering-system.md](07-rendering-system.md)  
**Monitor system health** → [03-setup.md - Part H](03-setup.md#part-h-health-monitoring-and-observability)  
**Understand architecture** → [02-architecture.md](02-architecture.md)

### By API/Component

**Job Model** → [02-architecture.md#data-models](02-architecture.md#data-models) + [05-backend.md#job-model](05-backend.md#job-model)  
**Job API** → [09-api-reference.md#job-endpoints](09-api-reference.md#job-endpoints)  
**Task Scheduling** → [05-backend.md#scheduling-algorithm](05-backend.md#scheduling-algorithm) + [06-ai-system.md](06-ai-system.md)  
**Worker System** → [07-rendering-system.md - Phase 5-6](07-rendering-system.md#phase-5-worker-polling--task-download) + [09-api-reference.md#worker-endpoints](09-api-reference.md#worker-endpoints)  
**Real-time Updates** → [02-architecture.md#websocket-architecture](02-architecture.md#websocket-architecture) + [09-api-reference.md#websocket](09-api-reference.md#websocket-real-time-updates)  
**Authentication** → [09-api-reference.md#authentication](09-api-reference.md#authentication)

## 🔗 Cross-Reference Map

Each document includes cross-references to related sections:

- 01-overview.md → 02-architecture.md (detailed breakdown)
- 02-architecture.md → 05-backend.md (models), 07-rendering-system.md (lifecycle)
- 03-setup.md → 10-troubleshooting.md (debug issues)
- 04-frontend.md → 09-api-reference.md (API endpoints)
- 05-backend.md → 06-ai-system.md (AI scheduler), 07-rendering-system.md (lifecycle)
- 06-ai-system.md → 05-backend.md (integration point)
- 07-rendering-system.md → 08-plugin-system.md (DCC integration)
- 08-plugin-system.md → 07-rendering-system.md (execution)
- 09-api-reference.md → 05-backend.md (implementation)
- 10-troubleshooting.md → all (solutions reference docs)

## 📋 Checklist: Pre-Deployment

- [ ] Read [01-overview.md](01-overview.md) (understand system)
- [ ] Read [02-architecture.md](02-architecture.md) (understand components)
- [ ] Follow [03-setup.md - Part A](03-setup.md#part-a-docker-compose-local-development-5-minutes) (local dev)
- [ ] Follow [03-setup.md - Part C](03-setup.md#part-c-first-render-job-execution) (first job)
- [ ] Review [03-setup.md - Part I](03-setup.md#part-i-security-pre-deployment-checklist) (security)
- [ ] Review [10-troubleshooting.md](10-troubleshooting.md) (know how to debug)
- [ ] Follow [03-setup.md - Part E](03-setup.md#part-e-kubernetes-production-deployment) (production deployment)
- [ ] Set up monitoring per [03-setup.md - Part H](03-setup.md#part-h-health-monitoring-and-observability)
- [ ] Document custom configuration in DEPLOYMENT.md

## 🎓 Learning Path

**For Complete Beginners** (2 hours total):

1. [00-index.md](00-index.md) — Overview & navigation (10 min)
2. [01-overview.md](01-overview.md) — Project context (15 min)
3. [03-setup.md - Part A](03-setup.md#part-a-docker-compose-local-development-5-minutes) — Get system running (5 min setup + 30 min running)
4. [03-setup.md - Part C](03-setup.md#part-c-first-render-job-execution) — Submit first job (15 min)
5. [04-frontend.md](04-frontend.md) — Understand dashboard (30 min)

**For Backend Developers** (2 hours total):

1. [02-architecture.md](02-architecture.md) — System design (30 min)
2. [05-backend.md](05-backend.md) — Django implementation (40 min)
3. [09-api-reference.md](09-api-reference.md) — API endpoints (25 min)
4. [03-setup.md - Part B](03-setup.md#part-b-native-development-environment) — Native dev setup (25 min)

**For Frontend Developers** (1.5 hours total):

1. [01-overview.md](01-overview.md) — Project context (15 min)
2. [04-frontend.md](04-frontend.md) — React/Next.js (30 min)
3. [09-api-reference.md](09-api-reference.md) — API reference (25 min)
4. [03-setup.md - Part A](03-setup.md#part-a-docker-compose-local-development-5-minutes) — Get system running (5 min + 15 min)

**For DevOps** (2.5 hours total):

1. [02-architecture.md](02-architecture.md) — Architecture (30 min)
2. [03-setup.md](03-setup.md) — All parts (90 min)
3. [10-troubleshooting.md](10-troubleshooting.md) — Debugging (20 min)

## 🔍 Searching Documentation

To find specific topics, search for keywords like:

- **Models**: Search files for "class Job", "class Task", "class Worker"
- **Endpoints**: Search for `GET /api/`, `POST /api/`
- **Configuration**: Search for `environment` or `DOCKER_` or `DJANGO_`
- **Troubleshooting**: Search for "Error", "Issue", "Solution" in 10-troubleshooting.md
- **Examples**: Search for JSON payload examples, curl commands, Python code

## 📝 Maintaining Documentation

**When adding features**:

1. Document in relevant markdown file
2. Update 00-index.md if major feature
3. Add example to 09-api-reference.md if API change
4. Add troubleshooting item to 10-troubleshooting.md if user-facing

**When updating code**:

1. Keep documentation in sync
2. Add inline comments with docs reference
3. Example: `# See docs/05-backend.md#scheduling-algorithm`

**Versioning**:

- Each document has version number in header
- Update version when making changes
- Maintain changelog in README

## 🆘 Getting Help

1. **Search this documentation** (use Ctrl+F in your reader)
2. **Check troubleshooting guide** ([10-troubleshooting.md](10-troubleshooting.md))
3. **Review examples** in relevant documentation
4. **Open GitHub issue**: https://github.com/your-org/renderhive/issues
5. **Contact team**: contact@renderhive.io

## 📊 Documentation Statistics

| Metric        | Value   |
| ------------- | ------- |
| Total files   | 11      |
| Total lines   | 30,000+ |
| Total words   | 85,000+ |
| Code examples | 100+    |
| Diagrams      | 15+     |
| JSON examples | 50+     |
| bash commands | 80+     |

## ✅ Quality Assurance

All documentation:

- ✅ Written to current codebase state
- ✅ Examples tested and verified
- ✅ JSON examples valid (can copy-paste)
- ✅ bash commands executable
- ✅ Cross-references accurate
- ✅ Markdown syntax valid
- ✅ Accessibility optimized (headings, lists)
- ✅ Search-engine friendly

---

**Documentation Generated**: December 20, 2024  
**Last Updated**: [Update with current date when modified]  
**Maintained By**: RenderHive Development Team  
**License**: See LICENSE file in project root

This documentation is the source of truth for RenderHive. When in doubt, refer to docs first, then ask questions.
