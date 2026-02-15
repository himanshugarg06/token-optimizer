#!/usr/bin/env python3
"""Standalone migration runner for manual testing."""

import sys
from app.settings import settings
from app.storage.migration_runner import run_migrations_from_settings

def main():
    """Run migrations."""
    print("=" * 80)
    print("Token Optimizer - Database Migration Runner")
    print("=" * 80)
    print()

    if not settings.semantic.enabled:
        print("❌ Semantic retrieval is disabled in settings")
        print("   Set SEMANTIC__ENABLED=true to enable")
        sys.exit(1)

    if not settings.semantic.postgres_url:
        print("❌ Postgres URL not configured")
        print("   Set SEMANTIC__POSTGRES_URL in environment")
        sys.exit(1)

    print(f"Postgres URL: {settings.semantic.postgres_url[:50]}...")
    print()
    print("Running migrations...")
    print()

    success = run_migrations_from_settings(settings)

    if success:
        print()
        print("✅ Migrations completed successfully!")
        sys.exit(0)
    else:
        print()
        print("❌ Migrations failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
