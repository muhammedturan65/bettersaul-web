# BetterSaul Web — Legal Intelligence Platform

AI-powered Turkish legal research and petition generation platform.

🌐 **Live**: [bettersaul-web.vercel.app](https://bettersaul-web.vercel.app)
🐍 **Python Service**: [bettersaul-python-service](https://github.com/muhammedturan65/bettersaul-python-service)

## ✨ Features

- 🔐 **Auth** — NextAuth + JWT + RBAC (admin/lawyer/user/org_admin)
- 🔍 **Hybrid Search** — Semantic (TF-IDF/pgvector) + keyword + metadata filter + AI query expansion
- 📝 **Petition AI Generation** — 4-stage pipeline (extract → generate → check → repair) via Z.ai SDK
- 💬 **AI Chat** — Source-cited legal assistant with tool transparency
- 🌿 **Research Trace** — AI reasoning steps visualization
- 📁 **Document Upload** — User private document embeddings
- ⚙️ **Admin Panel** — Import pipeline (mock + real Python service) + embedding reindex
- 🎨 **Premium UI** — Editorial legal-tech design (warm parchment + brass accent)

## 🛠️ Tech Stack

- **Framework**: Next.js 16 (App Router) + TypeScript 5
- **Styling**: Tailwind CSS 4 + shadcn/ui (New York)
- **Database**: Prisma ORM (SQLite for demo, PostgreSQL+pgvector for production)
- **Auth**: NextAuth.js v4 + bcryptjs
- **AI**: Z.ai SDK (z-ai-web-dev-sdk) — chat completions
- **Fonts**: Inter (sans) + IBM Plex Mono (mono)

## 🚀 Quick Start

```bash
# 1. Install
bun install

# 2. Set environment
cp .env.example .env
# Edit .env with your secrets

# 3. Database
bun run db:push
bun run db:generate

# 4. Seed demo data
node scripts/seed.js

# 5. Run
bun run dev
```

Open [http://localhost:3000](http://localhost:3000)

**Demo login**: `demo@bettersaul.legal` / `demo1234` (admin role)

## 📦 Environment Variables

```env
DATABASE_URL=file:./db/custom.db     # SQLite (demo) or postgresql://... (prod)
NEXTAUTH_SECRET=your-secret-here     # openssl rand -base64 32
NEXTAUTH_URL=http://localhost:3000   # or https://your-domain.vercel.app
PYTHON_SERVICE_URL=http://localhost:8001  # Railway python service URL (optional)
```

## 📁 Project Structure

```
src/
├── app/
│   ├── (auth)/login, register/
│   ├── api/                    # Next.js API routes
│   │   ├── auth/[...nextauth]/
│   │   ├── dashboard/
│   │   ├── legal/search/
│   │   ├── petitions/ + generate/
│   │   ├── chat/
│   │   ├── research/
│   │   ├── documents/
│   │   ├── import/ + real/     # Mock + Python service
│   │   └── embeddings/reindex/
│   ├── login/, register/
│   ├── admin/
│   ├── globals.css             # Premium editorial theme
│   ├── layout.tsx
│   └── page.tsx                # Main app (view router)
├── components/
│   ├── bettersaul/             # 8 view components
│   │   ├── sidebar, topbar
│   │   ├── dashboard, search-view
│   │   ├── petitions-view, petition-editor
│   │   ├── chat-view, research-view
│   │   ├── documents-view, import-admin
│   │   └── providers
│   └── ui/                     # shadcn/ui (47 components)
├── lib/
│   ├── auth.ts                 # NextAuth config
│   ├── db.ts                   # Prisma client
│   ├── import-queue.ts         # In-memory job queue (demo)
│   └── legal-engine/           # engine.py TypeScript port
│       ├── embeddings.ts       # 256-dim TF-IDF + hashing
│       ├── tracks.ts           # 10 legal track detector
│       ├── quality.ts          # 17-dimension quality check
│       ├── mcp-tools.ts        # 21 MCP tools
│       └── petition-pipeline.ts # 4-stage AI generation
└── middleware.ts               # RBAC route protection
prisma/
└── schema.prisma               # 19 models
```

## 🎨 Design

- **Palette**: Warm parchment background + deep ink + brass accent (no indigo/blue)
- **Typography**: Inter (display + body) + IBM Plex Mono (code/data)
- **Layout**: Sticky sidebar (dark theme) + topbar + responsive main
- **Mobile**: Drawer sidebar, stacked layout, touch-friendly

## 🔌 Python Service Integration

Web app calls Python service for real-source imports (9M+ decisions):

```typescript
// src/app/api/import/real/route.ts
const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL
const res = await fetch(`${PYTHON_SERVICE_URL}/import`, {...})
```

Python service repo: [bettersaul-python-service](https://github.com/muhammedturan65/bettersaul-python-service)

## 📜 License

MIT — BetterSaul Legal Intelligence Platform
