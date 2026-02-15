"""Database migration runner for semantic retrieval setup."""

import os
import logging
from pathlib import Path
from typing import List, Tuple
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

logger = logging.getLogger(__name__)


class MigrationRunner:
    """
    Manages database migrations for semantic retrieval.

    Tracks applied migrations in schema_migrations table and executes
    pending SQL migration files from the migrations directory.
    """

    def __init__(self, postgres_url: str):
        """
        Initialize migration runner.

        Args:
            postgres_url: PostgreSQL connection string
        """
        self.postgres_url = postgres_url
        self.migrations_dir = Path(__file__).parent / "migrations"

    def run_migrations(self) -> Tuple[bool, List[str]]:
        """
        Execute all pending migrations.

        Returns:
            Tuple of (success, applied_migrations)
        """
        try:
            conn = psycopg2.connect(self.postgres_url)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # Create migrations tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Get applied migrations
            cursor.execute("SELECT version FROM schema_migrations")
            applied_versions = {row[0] for row in cursor.fetchall()}

            logger.info(f"Found {len(applied_versions)} applied migrations")

            # Find migration files
            migration_files = sorted(self.migrations_dir.glob("*.sql"))
            logger.info(f"Found {len(migration_files)} migration files")

            applied_migrations = []

            for migration_file in migration_files:
                version = migration_file.stem  # e.g., "001_semantic_retrieval"

                if version in applied_versions:
                    logger.debug(f"Migration {version} already applied, skipping")
                    continue

                logger.info(f"Applying migration {version}")

                try:
                    # Read and execute SQL
                    sql = migration_file.read_text()
                    cursor.execute(sql)

                    # Record migration
                    cursor.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (version,)
                    )

                    logger.info(f"✓ Migration {version} applied successfully")
                    applied_migrations.append(version)

                except Exception as e:
                    logger.error(f"✗ Migration {version} failed: {e}")
                    cursor.close()
                    conn.close()
                    return False, applied_migrations

            cursor.close()
            conn.close()

            if applied_migrations:
                logger.info(f"Applied {len(applied_migrations)} new migrations")
            else:
                logger.info("No new migrations to apply")

            return True, applied_migrations

        except psycopg2.OperationalError as e:
            logger.error(f"Database connection failed: {e}")
            logger.warning("Semantic retrieval will not be available")
            return False, []

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False, []

    def rollback_migration(self, version: str) -> bool:
        """
        Rollback a specific migration (manual operation).

        Args:
            version: Migration version to rollback

        Returns:
            bool: Success status
        """
        try:
            conn = psycopg2.connect(self.postgres_url)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # Check if migration was applied
            cursor.execute(
                "SELECT version FROM schema_migrations WHERE version = %s",
                (version,)
            )

            if not cursor.fetchone():
                logger.warning(f"Migration {version} not found in applied migrations")
                cursor.close()
                conn.close()
                return False

            # Remove migration record
            cursor.execute(
                "DELETE FROM schema_migrations WHERE version = %s",
                (version,)
            )

            logger.info(f"Migration {version} rolled back")
            logger.warning("Note: Rollback only removes tracking record, not schema changes")

            cursor.close()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def get_migration_status(self) -> List[dict]:
        """
        Get status of all migrations.

        Returns:
            List of migration info dicts
        """
        try:
            conn = psycopg2.connect(self.postgres_url)
            cursor = conn.cursor()

            # Get applied migrations with timestamps
            cursor.execute("""
                SELECT version, applied_at
                FROM schema_migrations
                ORDER BY applied_at DESC
            """)

            applied = {
                row[0]: row[1].isoformat() if row[1] else None
                for row in cursor.fetchall()
            }

            cursor.close()
            conn.close()

            # Get all migration files
            migration_files = sorted(self.migrations_dir.glob("*.sql"))

            status = []
            for migration_file in migration_files:
                version = migration_file.stem
                status.append({
                    "version": version,
                    "file": migration_file.name,
                    "applied": version in applied,
                    "applied_at": applied.get(version)
                })

            return status

        except Exception as e:
            logger.error(f"Failed to get migration status: {e}")
            return []


def run_migrations_from_settings(settings) -> bool:
    """
    Run migrations using settings object.

    Args:
        settings: Application settings with semantic.postgres_url

    Returns:
        bool: Success status
    """
    if not settings.semantic.enabled:
        logger.debug("Semantic retrieval disabled, skipping migrations")
        return True

    if not settings.semantic.postgres_url:
        logger.warning("Postgres URL not configured, skipping migrations")
        return False

    runner = MigrationRunner(settings.semantic.postgres_url)
    success, applied = runner.run_migrations()

    if success:
        logger.info("Database migrations completed successfully")
    else:
        logger.error("Database migrations failed")

    return success
