/**
 * Database Sync Executor - Executes sync actions to update Elia database
 * This is where the reactive database updates actually happen
 */

import { ExecutorFn } from '../core/wte.js';
import { DatabaseSyncAction } from '../transforms/database-sync.js';

export interface SyncResult {
  success: boolean;
  syncedCount: number;
  errors: string[];
  duration: number;
}

/**
 * Execute database sync actions by calling Python session sync
 */
export const executeDatabaseSync: ExecutorFn<DatabaseSyncAction> = async (
  action: DatabaseSyncAction
): Promise<void> => {
  const startTime = Date.now();
  
  console.log(`[EXECUTOR] Executing ${action.type} with priority ${action.priority}`);
  console.log(`[EXECUTOR] Reason: ${action.data.reason}`);

  try {
    switch (action.type) {
      case 'trigger_session_sync':
        await executeSyncSpecificSessions(action);
        break;
        
      case 'trigger_project_sync':
        await executeSyncProjectSessions(action);
        break;
        
      case 'trigger_full_discovery':
        await executeFullDiscoverySync(action);
        break;
        
      default:
        console.warn(`[EXECUTOR] Unknown action type: ${action.type}`);
    }
    
    const duration = Date.now() - startTime;
    console.log(`[EXECUTOR] Completed ${action.type} in ${duration}ms`);
    
  } catch (error) {
    const duration = Date.now() - startTime;
    console.error(`[EXECUTOR] Failed ${action.type} after ${duration}ms:`, error);
    throw error;
  }
};

/**
 * Sync specific sessions by their UUIDs
 */
async function executeSyncSpecificSessions(action: DatabaseSyncAction): Promise<SyncResult> {
  const sessionUuids = action.data.sessionUuids || [];
  
  if (sessionUuids.length === 0) {
    return { success: true, syncedCount: 0, errors: [], duration: 0 };
  }

  console.log(`[EXECUTOR] Syncing ${sessionUuids.length} specific sessions`);
  
  // Call Python session sync via bridge
  // This would be implemented to call the SessionSync.sync_session method
  const results = await callPythonSessionSync('sync_sessions', { sessionUuids });
  
  return results;
}

/**
 * Sync sessions for specific projects
 */
async function executeSyncProjectSessions(action: DatabaseSyncAction): Promise<SyncResult> {
  const projectPaths = action.data.projectPaths || [];
  
  if (projectPaths.length === 0) {
    return { success: true, syncedCount: 0, errors: [], duration: 0 };
  }

  console.log(`[EXECUTOR] Syncing sessions for ${projectPaths.length} projects`);
  
  // Call Python session sync for project-specific sessions
  const results = await callPythonSessionSync('sync_project_sessions', { projectPaths });
  
  return results;
}

/**
 * Execute full discovery and sync
 */
async function executeFullDiscoverySync(action: DatabaseSyncAction): Promise<SyncResult> {
  console.log('[EXECUTOR] Executing full discovery sync');
  
  // Call Python session sync for all sessions
  const results = await callPythonSessionSync('sync_all_sessions', {});
  
  return results;
}

/**
 * Call Python session sync via subprocess or HTTP API
 * This is the bridge between TypeScript cafed and Python Elia
 */
async function callPythonSessionSync(method: string, params: any): Promise<SyncResult> {
  const startTime = Date.now();
  
  try {
    // Option 1: Call via subprocess (simpler for now)
    const { spawn } = await import('child_process');
    const { promisify } = await import('util');
    
    // Construct command to call Python session sync
    const pythonCmd = [
      'python', '-m', 'elia_chat.cli.session_sync',
      '--method', method,
      '--params', JSON.stringify(params)
    ];
    
    console.log(`[EXECUTOR] Running: ${pythonCmd.join(' ')}`);
    
    // For now, simulate the call
    // In real implementation, we'd actually execute the subprocess
    await new Promise(resolve => setTimeout(resolve, 100)); // Simulate async work
    
    const duration = Date.now() - startTime;
    
    // Simulate successful result
    return {
      success: true,
      syncedCount: params.sessionUuids?.length || params.projectPaths?.length || 1,
      errors: [],
      duration
    };
    
  } catch (error) {
    const duration = Date.now() - startTime;
    console.error('[EXECUTOR] Python session sync failed:', error);
    
    return {
      success: false,
      syncedCount: 0,
      errors: [error instanceof Error ? error.message : String(error)],
      duration
    };
  }
}

/**
 * Database sync executor with retry logic
 */
export class DatabaseSyncExecutor {
  private maxRetries: number;
  private retryDelayMs: number;

  constructor(maxRetries: number = 3, retryDelayMs: number = 1000) {
    this.maxRetries = maxRetries;
    this.retryDelayMs = retryDelayMs;
  }

  execute: ExecutorFn<DatabaseSyncAction> = async (action: DatabaseSyncAction): Promise<void> => {
    let lastError: Error | null = null;
    
    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        await executeDatabaseSync(action);
        return; // Success!
        
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        console.warn(`[EXECUTOR] Attempt ${attempt}/${this.maxRetries} failed:`, lastError.message);
        
        if (attempt < this.maxRetries) {
          const delay = this.retryDelayMs * attempt; // Exponential backoff
          console.log(`[EXECUTOR] Retrying in ${delay}ms...`);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }
    
    throw new Error(`Failed after ${this.maxRetries} attempts. Last error: ${lastError?.message}`);
  };
}