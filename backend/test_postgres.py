#!/usr/bin/env python3
"""Test Postgres connection and pgvector availability."""

import sys
import os

def test_connection():
    """Test Postgres connection."""
    print("=" * 80)
    print("Postgres Connection Test")
    print("=" * 80)
    print()

    # Get connection string from environment
    postgres_url = os.environ.get('SEMANTIC__POSTGRES_URL') or os.environ.get('POSTGRES_URL')

    if not postgres_url:
        print("❌ No Postgres URL found in environment")
        print()
        print("Please set one of these environment variables:")
        print("  export SEMANTIC__POSTGRES_URL='postgresql://user:pass@host:port/db'")
        print("  export POSTGRES_URL='postgresql://user:pass@host:port/db'")
        sys.exit(1)

    # Mask password for display
    masked_url = postgres_url.split('@')[0].split(':')[:-1]
    masked_url = ':'.join(masked_url) + ':****@' + postgres_url.split('@')[1]
    print(f"Connection URL: {masked_url}")
    print()

    try:
        import psycopg2
        print("✓ psycopg2 installed")
    except ImportError:
        print("❌ psycopg2 not installed")
        print("   Run: pip install psycopg2-binary")
        sys.exit(1)

    # Test connection
    print()
    print("Testing connection...")
    try:
        conn = psycopg2.connect(postgres_url)
        print("✅ Connection successful!")

        cursor = conn.cursor()

        # Check PostgreSQL version
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✓ PostgreSQL version: {version.split(',')[0]}")

        # Check if pgvector is installed
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'vector'
            );
        """)
        has_pgvector = cursor.fetchone()[0]

        if has_pgvector:
            print("✅ pgvector extension is installed!")

            # Get pgvector version
            cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
            pgvector_version = cursor.fetchone()[0]
            print(f"✓ pgvector version: {pgvector_version}")
        else:
            print("❌ pgvector extension NOT installed")
            print()
            print("To install, run this SQL:")
            print("  CREATE EXTENSION IF NOT EXISTS vector;")
            print()
            print("You can run it using:")
            print(f"  psql '{postgres_url}' -c 'CREATE EXTENSION IF NOT EXISTS vector;'")
            cursor.close()
            conn.close()
            sys.exit(1)

        # Check if migrations table exists
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'schema_migrations'
            );
        """)
        has_migrations = cursor.fetchone()[0]

        if has_migrations:
            cursor.execute("SELECT version, applied_at FROM schema_migrations ORDER BY applied_at;")
            migrations = cursor.fetchall()
            print(f"✓ Found {len(migrations)} applied migration(s)")
            for version, applied_at in migrations:
                print(f"  - {version} (applied: {applied_at})")
        else:
            print("⚠ No migrations table found (will be created on first run)")

        # Check if blocks table exists
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'blocks'
            );
        """)
        has_blocks = cursor.fetchone()[0]

        if has_blocks:
            cursor.execute("SELECT COUNT(*) FROM blocks;")
            count = cursor.fetchone()[0]
            print(f"✓ blocks table exists ({count} rows)")
        else:
            print("⚠ blocks table not found (will be created by migration)")

        cursor.close()
        conn.close()

        print()
        print("=" * 80)
        print("✅ All checks passed! Database is ready.")
        print("=" * 80)
        print()
        print("Next steps:")
        if not has_migrations:
            print("  1. Run migrations: python run_migrations.py")
        print("  2. Start backend: docker-compose up -d")
        print("  3. Test: curl http://localhost:8000/v1/health | jq")

    except psycopg2.OperationalError as e:
        print(f"❌ Connection failed: {e}")
        print()
        print("Troubleshooting:")
        print("  - Check that the host and port are correct")
        print("  - Verify username and password")
        print("  - Ensure database exists")
        print("  - Check firewall/security group allows your IP")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
