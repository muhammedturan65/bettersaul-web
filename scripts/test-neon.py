"""Test Neon PostgreSQL connection + check pgvector availability."""
import psycopg2
import sys

NEON_URL = "postgresql://neondb_owner:npg_Nct1aqdKL9hp@ep-delicate-frost-b29rat94-pooler.c-6.eu-central-1.aws.neon.tech/neondb?sslmode=require"

def main():
    print("=== Connecting to Neon ===")
    try:
        conn = psycopg2.connect(NEON_URL)
        conn.autocommit = True
        cur = conn.cursor()
        print("✓ Connected")
        
        # Check PostgreSQL version
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        print(f"PostgreSQL version: {version[:60]}")
        
        # Check available extensions
        print("\n=== Available extensions ===")
        cur.execute("""
            SELECT name, default_version, installed_version 
            FROM pg_available_extensions 
            WHERE name IN ('vector', 'pg_trgm', 'unaccent', 'uuid-ossp')
            ORDER BY name
        """)
        for name, default_v, installed_v in cur.fetchall():
            status = "✓ installed" if installed_v else "○ available"
            print(f"  {status} {name} (v{default_v})")
        
        # Check if vector already installed
        cur.execute("SELECT 1 FROM pg_extension WHERE extname='vector'")
        has_vector = cur.fetchone() is not None
        print(f"\npgvector installed: {'✓' if has_vector else '✗'}")
        
        if not has_vector:
            print("\n=== Installing pgvector ===")
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                conn.commit()
                print("✓ pgvector installed")
            except Exception as e:
                print(f"✗ Cannot install pgvector: {e}")
                print("Note: Neon requires pgvector-enabled compute. Try creating it via Neon dashboard.")
        
        # Check other useful extensions
        print("\n=== Installing useful extensions ===")
        for ext in ["pg_trgm", "unaccent", "uuid-ossp"]:
            try:
                cur.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")
                conn.commit()
                print(f"✓ {ext}")
            except Exception as e:
                print(f"✗ {ext}: {e}")
        
        # List current tables
        print("\n=== Current tables ===")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        if tables:
            for t in tables:
                print(f"  - {t[0]}")
        else:
            print("  (none)")
        
        cur.close()
        conn.close()
        print("\n✓ Done")
        return True
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
