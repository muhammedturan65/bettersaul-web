# BetterSaul Source Connector Service

Production-grade Python microservice for scraping 9M+ Turkish legal decisions,
generating real embeddings (multilingual-e5-large), and writing to PostgreSQL + pgvector.

## Mimari

```
┌─────────────────────────────────────────────────────────────────────┐
│ Next.js Web App (port 3000)                                        │
│  └─ /admin → Import Admin UI                                       │
│      └─ POST /api/import/real → calls Python service              │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP (internal network only)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Python Source Connector Service (port 8001)                         │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ FastAPI                                                     │    │
│  │  /health /sources /search /import /embed /search/semantic   │    │
│  └────────────────────┬───────────────────────────────────────┘    │
│                       │                                             │
│  ┌────────────────────┼───────────────────────────────────────┐    │
│  │ JobManager         │                                       │    │
│  │  ├─ ImportWorker (concurrent: 5-20)                        │    │
│  │  │   ├─ Connector.search(page)                             │    │
│  │  │   ├─ Connector.get_document()                           │    │
│  │  │   ├─ chunk_text()                                       │    │
│  │  │   ├─ embedder.embed_batch() ← sentence-transformers    │    │
│  │  │   └─ DatabaseWriter.upsert_decisions()                  │    │
│  │  └─ RateLimiter (Redis-backed)                             │    │
│  └────────────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
    ┌─────────────┐  ┌────────────┐  ┌──────────────┐
    │ 6 Hukuk     │  │ PostgreSQL │  │   Redis      │
    │ Portalları  │  │ +pgvector  │  │ (rate limit) │
    │ (HTTP scrape)│  │ (1024-dim) │  │              │
    └─────────────┘  └────────────┘  └──────────────┘
```

## Kaynaklar (6 portal)

| Kaynak | URL | Tahmini Karar | Rate Limit |
|---|---|---|---|
| Yargıtay | karararama.yargitay.gov.tr | ~4.5M | 20 RPM |
| Danıştay | danistaydergiler.adalet.gov.tr | ~1.2M | 20 RPM |
| Emsal (UYAP) | emsal.uyap.gov.tr | ~2.8M | 20 RPM |
| AYM | anayasa.gov.tr/api | ~65K | 60 RPM |
| Resmî Gazete | resmigazete.gov.tr | ~350K | 30 RPM |
| Mevzuat | mevzuat.gov.tr | ~28K | 60 RPM |
| **Toplam** | | **~9M** | |

## Embedding Backends

| Backend | Model | Dim | Kalite | Maliyet (9M karar) |
|---|---|---|---|---|
| `e5` (önerilen) | intfloat/multilingual-e5-large | 1024 | Yüksek | GPU: ~$50 (4 saat) |
| `openai` | text-embedding-3-large | 1536 | En yüksek | ~$1,170 API |
| `tfidf` (fallback) | TF-IDF + hashing | 256 | Düşük | $0 (CPU) |

## Kurulum

```bash
cd legacy/python-service

# 1. Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. sentence-transformers (önerilen, ~2.5GB model)
pip install sentence-transformers torch
# İlk çalıştırmada model otomatik indirilir

# 3. Environment
export DATABASE_URL="postgresql://bettersaul:bettersaul@localhost:5432/bettersaul"
export REDIS_URL="redis://localhost:6379"
export EMBEDDING_BACKEND="e5"  # auto | e5 | openai | tfidf

# 4. PostgreSQL + pgvector
docker-compose up -d postgres redis

# 5. Servisi başlat
python -m bettersaul_sources.api
# veya
uvicorn bettersaul_sources.api:app --host 0.0.0.0 --port 8001 --reload
```

## API Kullanımı

### Health check
```bash
curl http://localhost:8001/health
# {"status":"ok","service":"bettersaul-sources","version":"1.0.0"}
```

### Kaynak listesi
```bash
curl http://localhost:8001/sources
```

### Tek kaynak arama (DB'ye yazmadan)
```bash
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"source":"yargitay","query":"işe iade","page":1}'
```

### Import job başlat (9M karar)
```bash
curl -X POST http://localhost:8001/import \
  -H "Content-Type: application/json" \
  -d '{
    "source": "yargitay",
    "query": "*",
    "max_documents": 1000000,
    "concurrency": 10,
    "embedding_backend": "e5"
  }'
# {"job_id":"job_12345_abc","source":"yargitay","status":"queued"}
```

### Job durumu
```bash
curl http://localhost:8001/import/job_12345_abc
# {
#   "job_id": "job_12345_abc",
#   "source": "yargitay",
#   "status": "running",
#   "total": 1000000,
#   "processed": 15420,
#   "failed": 23,
#   "progress": 1.5,
#   "current_step": "Page 1542: 18 ok, 0 fail",
#   "log": [...]
# }
```

### Pause / Resume / Cancel
```bash
curl -X POST http://localhost:8001/import/job_12345_abc/pause
curl -X POST http://localhost:8001/import/job_12345_abc/resume
curl -X POST http://localhost:8001/import/job_12345_abc/cancel
```

### Semantic search
```bash
curl -X POST http://localhost:8001/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query":"işe iade feshin geçersizliği","top_k":20}'
```

## 9M Karar İçin Tahmini Süre

| Kaynak | Karar | Concurrency | Embedding | Süre |
|---|---|---|---|---|
| Yargıtay | 4.5M | 10 | e5 (GPU) | ~12 saat |
| Danıştay | 1.2M | 10 | e5 (GPU) | ~3 saat |
| Emsal | 2.8M | 10 | e5 (GPU) | ~7 saat |
| AYM | 65K | 5 | e5 (GPU) | ~10 dk |
| Resmî Gazete | 350K | 10 | e5 (GPU) | ~1 saat |
| Mevzuat | 28K | 5 | e5 (GPU) | ~5 dk |
| **Toplam** | **~9M** | | | **~24 saat** |

**CPU-only (e5, no GPU):** ~10x slower = ~10 gün

**Optimizasyonlar:**
- Rate limit (20 RPM) nedeniyle bazı kaynaklarda süre uzar
- GPU (RTX 4090) ile e5 batch=32 → ~200 docs/s
- CPU (8-core) ile e5 batch=32 → ~20 docs/s
- OpenAI API: 9M × 1000 tokens × $0.13/M = ~$1,170 (anlık, hızlı)

## Üretim Dağıtımı

### docker-compose.yml
```yaml
version: '3.8'
services:
  python-service:
    build: ./legacy/python-service
    ports: ["8001:8001"]
    environment:
      - DATABASE_URL=postgresql://bettersaul:bettersaul@postgres:5432/bettersaul
      - REDIS_URL=redis://redis:6379
      - EMBEDDING_BACKEND=e5
    depends_on: [postgres, redis]
    restart: unless-stopped
    # GPU için (e5 hızlandırma)
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: bettersaul
      POSTGRES_USER: bettersaul
      POSTGRES_PASSWORD: bettersaul
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  pgdata:
```

### Komutlar
```bash
# Tüm servisi başlat
docker-compose up -d

# Python service loglarını izle
docker-compose logs -f python-service

# Import job başlat (Next.js admin'den veya doğrudan)
curl -X POST http://localhost:8001/import \
  -H "Content-Type: application/json" \
  -d '{"source":"yargitay","max_documents":1000000,"concurrency":10}'

# PostgreSQL'e bağlan ve kontrol et
docker-compose exec postgres psql -U bettersaul -c "
  SELECT court, COUNT(*) FROM legal_decisions GROUP BY court;
"
```

## Next.js Admin ile Entegrasyon

Next.js admin panelinde "Real Source Import" bölümü:
1. Admin → Import Admin panel
2. "Python Service" toggle'ı aç
3. Kaynak seç (Yargıtay/Danıştay/...)
4. Max documents gir (test için 100, prod için 1M+)
5. "Gerçek Import Başlat" → `POST http://python-service:8001/import`
6. Job durumunu `GET /import/{job_id}` ile poll et
7. Progress bar + log real-time göster

## Güvenlik

- Python service **sadece internal network**'te (dışarıya açık değil)
- API key ile koruma (Next.js → Python service)
- Rate limit: Redis-backed (her kaynak için ayrı bucket)
- Proxy rotation: Her kaynak için ayrı User-Agent + proxy pool
- Audit log: Tüm import işlemleri `import_jobs` tablosuna kaydedilir

## Monitoring

- `/health` endpoint (uptime check)
- `/import` list (job status)
- PostgreSQL: `SELECT * FROM import_jobs ORDER BY created_at DESC LIMIT 10`
- Redis: `MONITOR` (rate limit buckets)
- Logs: `docker-compose logs -f python-service`
