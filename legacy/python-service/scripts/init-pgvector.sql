-- BetterSaul PostgreSQL init script
-- Runs on first container start (docker-entrypoint-initdb.d)

-- Required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- trigram (keyword search)
CREATE EXTENSION IF NOT EXISTS unaccent;      -- accent-insensitive search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- UUID generation

-- Verify pgvector
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    RAISE EXCEPTION 'pgvector extension not available. Use pgvector/pgvector:pg16 image.';
  END IF;
END $$;

-- Default permissions
GRANT ALL PRIVILEGES ON DATABASE bettersaul TO bettersaul;
