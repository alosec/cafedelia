/**
 * Reactive Database Sync Pipeline
 * Implements the complete WTE cycle for reactive TUI updates
 * 
 * Watch: Database changes in cafed SQLite
 * Transform: Change events into sync actions  
 * Execute: Sync actions to update Elia database
 */

import { WTE } from '../core/wte.js';
import { DatabaseChangeEvent, createDatabaseWatcher } from '../watchers/database-watcher.js';
import { DatabaseSyncAction, transformDatabaseChanges } from '../transforms/database-sync.js';
import { DatabaseSyncExecutor } from '../executors/database-sync.js';

/**
 * Complete WTE pipeline for reactive database synchronization
 */
export class ReactiveDatabaseSyncPipeline implements WTE<DatabaseChangeEvent, DatabaseSyncAction> {
  private databaseWatcher = createDatabaseWatcher(3000); // Check every 3 seconds
  private syncExecutor = new DatabaseSyncExecutor(3, 1000); // 3 retries, 1s delay

  /**
   * Watch for database changes
   */
  watch = (): AsyncGenerator<DatabaseChangeEvent> => {
    console.log('[REACTIVE_PIPELINE] Starting database watch...');
    return this.databaseWatcher.watch();
  };

  /**
   * Transform database changes into sync actions
   */
  transform = (event: DatabaseChangeEvent): DatabaseSyncAction | null => {
    console.log(`[REACTIVE_PIPELINE] Transforming event: ${event.type}`);
    return transformDatabaseChanges(event);
  };

  /**
   * Execute sync actions
   */
  execute = async (action: DatabaseSyncAction): Promise<void> => {
    console.log(`[REACTIVE_PIPELINE] Executing action: ${action.type}`);
    return this.syncExecutor.execute(action);
  };
}

/**
 * Create and configure the reactive database sync pipeline
 */
export function createReactiveDatabaseSyncPipeline(): ReactiveDatabaseSyncPipeline {
  return new ReactiveDatabaseSyncPipeline();
}

/**
 * Simple factory for the WTE interface
 */
export function createReactiveDatabaseWTE(): WTE<DatabaseChangeEvent, DatabaseSyncAction> {
  return createReactiveDatabaseSyncPipeline();
}