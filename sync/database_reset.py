"""
Database reset functionality for Cafedelia.

Provides safe database recreation with optional backup and full schema reset.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from elia_chat.database.database import db_path
from elia_chat.database.models import metadata
from sqlmodel import create_engine

logger = logging.getLogger(__name__)


class DatabaseResetManager:
    """Manages database reset operations safely."""
    
    def __init__(self):
        self.db_path = Path(db_path)
        self.backup_dir = self.db_path.parent / "backups"
    
    async def reset_database(self, backup: bool = True) -> bool:
        """
        Reset the database to a clean state.
        
        Args:
            backup: Whether to create a backup before reset
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create backup if requested
            if backup and self.db_path.exists():
                backup_path = await self._create_backup()
                logger.info(f"Created database backup at: {backup_path}")
            
            # Close any existing connections
            from elia_chat.database.database import get_session
            # Force close all sessions
            await get_session.aclose()
            
            # Remove existing database
            if self.db_path.exists():
                self.db_path.unlink()
                logger.info(f"Removed existing database: {self.db_path}")
            
            # Recreate database with schema
            await self._create_schema()
            
            # Reset sync positions
            from sync.incremental_sync import incremental_sync_engine
            sync_positions_file = incremental_sync_engine.sync_metadata_file
            if sync_positions_file.exists():
                sync_positions_file.unlink()
                logger.info("Reset incremental sync positions")
            
            logger.info("Database reset complete")
            return True
            
        except Exception as e:
            logger.error(f"Database reset failed: {e}")
            return False
    
    async def _create_backup(self) -> Path:
        """Create a timestamped backup of the database."""
        self.backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"cafedelia_backup_{timestamp}.sqlite"
        
        shutil.copy2(self.db_path, backup_path)
        
        # Keep only last 5 backups
        await self._cleanup_old_backups()
        
        return backup_path
    
    async def _cleanup_old_backups(self) -> None:
        """Remove old backups, keeping only the most recent ones."""
        backups = sorted(self.backup_dir.glob("cafedelia_backup_*.sqlite"))
        
        if len(backups) > 5:
            for old_backup in backups[:-5]:
                old_backup.unlink()
                logger.debug(f"Removed old backup: {old_backup}")
    
    async def _create_schema(self) -> None:
        """Create fresh database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create engine and tables
        engine = create_engine(f"sqlite:///{self.db_path}")
        metadata.create_all(engine)
        
        logger.info("Created fresh database schema")
    
    async def restore_backup(self, backup_name: str) -> bool:
        """
        Restore database from a backup.
        
        Args:
            backup_name: Name of the backup file
            
        Returns:
            True if successful, False otherwise
        """
        backup_path = self.backup_dir / backup_name
        
        if not backup_path.exists():
            logger.error(f"Backup not found: {backup_path}")
            return False
        
        try:
            # Create backup of current database
            if self.db_path.exists():
                await self._create_backup()
            
            # Replace with backup
            shutil.copy2(backup_path, self.db_path)
            logger.info(f"Restored database from: {backup_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
    
    def list_backups(self) -> list[dict]:
        """List available backups with metadata."""
        backups = []
        
        if not self.backup_dir.exists():
            return backups
        
        for backup_file in sorted(self.backup_dir.glob("cafedelia_backup_*.sqlite"), reverse=True):
            stat = backup_file.stat()
            backups.append({
                "name": backup_file.name,
                "path": str(backup_file),
                "size_mb": stat.st_size / (1024 * 1024),
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        
        return backups


# Global instance
db_reset_manager = DatabaseResetManager()