/**
 * Database Sync Transform - Converts database change events into sync actions
 * This bridges cafed database changes with Elia TUI database updates
 */

import { TransformFn } from '../core/wte.js';
import { DatabaseChangeEvent } from '../watchers/database-watcher.js';

export interface DatabaseSyncAction {
  type: 'trigger_session_sync' | 'trigger_project_sync' | 'trigger_full_discovery';
  priority: 'high' | 'medium' | 'low';
  data: {
    sessionUuids?: string[];
    projectPaths?: string[];
    reason: string;
    changeCount?: number;
  };
}

/**
 * Transform database change events into sync actions
 */
export const transformDatabaseChanges: TransformFn<DatabaseChangeEvent, DatabaseSyncAction> = (
  event: DatabaseChangeEvent
): DatabaseSyncAction | null => {
  
  switch (event.type) {
    case 'session_discovered':
      // New sessions detected in cafed database - sync them to Elia
      const sessionUuids = event.data.newSessions?.map(s => s.claude_session_uuid).filter(Boolean) || [];
      
      if (sessionUuids.length > 0) {
        console.log(`[TRANSFORM] Converting session discovery to sync action: ${sessionUuids.length} sessions`);
        
        return {
          type: 'trigger_session_sync',
          priority: 'high',
          data: {
            sessionUuids,
            reason: `${sessionUuids.length} new session(s) discovered in cafed database`,
            changeCount: sessionUuids.length
          }
        };
      }
      break;

    case 'project_added':
      // New projects detected - may have sessions that need syncing
      const projectPaths = event.data.newProjects?.map(p => p.path) || [];
      
      if (projectPaths.length > 0) {
        console.log(`[TRANSFORM] Converting project addition to discovery action: ${projectPaths.length} projects`);
        
        return {
          type: 'trigger_project_sync',
          priority: 'medium',
          data: {
            projectPaths,
            reason: `${projectPaths.length} new project(s) added to cafed database`,
            changeCount: projectPaths.length
          }
        };
      }
      break;

    case 'database_updated':
      // External discovery found new sessions - trigger full sync
      console.log('[TRANSFORM] Converting external discovery to full sync action');
      
      return {
        type: 'trigger_full_discovery',
        priority: 'high',
        data: {
          reason: 'External Claude Code sessions detected outside of cafed database',
          changeCount: event.data.sessionCount || 0
        }
      };

    default:
      console.log(`[TRANSFORM] Unknown event type: ${event.type}`);
      return null;
  }

  return null;
};

/**
 * Debounced transform that batches rapid changes
 */
export class DebouncedDatabaseTransform {
  private pendingActions: DatabaseSyncAction[] = [];
  private debounceMs: number;
  private timer: NodeJS.Timeout | null = null;

  constructor(debounceMs: number = 2000) {
    this.debounceMs = debounceMs;
  }

  async* transform(events: AsyncGenerator<DatabaseChangeEvent>): AsyncGenerator<DatabaseSyncAction> {
    for await (const event of events) {
      const action = transformDatabaseChanges(event);
      
      if (action) {
        this.pendingActions.push(action);
        
        // Clear existing timer
        if (this.timer) {
          clearTimeout(this.timer);
        }
        
        // Set new timer to flush actions
        this.timer = setTimeout(() => {
          this.flushActions();
        }, this.debounceMs);
      }
    }
  }

  private async flushActions() {
    if (this.pendingActions.length === 0) return;

    // Group actions by type and merge them
    const actionGroups = this.groupActions(this.pendingActions);
    
    for (const mergedAction of actionGroups) {
      console.log(`[DEBOUNCED_TRANSFORM] Yielding merged action: ${mergedAction.type}`);
      // In a real implementation, we'd yield this
      // For now, just log it
    }

    this.pendingActions = [];
  }

  private groupActions(actions: DatabaseSyncAction[]): DatabaseSyncAction[] {
    const groups = new Map<string, DatabaseSyncAction>();

    for (const action of actions) {
      const existing = groups.get(action.type);
      
      if (existing) {
        // Merge actions of the same type
        existing.data.sessionUuids = [
          ...(existing.data.sessionUuids || []),
          ...(action.data.sessionUuids || [])
        ];
        existing.data.projectPaths = [
          ...(existing.data.projectPaths || []),
          ...(action.data.projectPaths || [])
        ];
        existing.data.changeCount = (existing.data.changeCount || 0) + (action.data.changeCount || 0);
        existing.data.reason = `${existing.data.reason} + ${action.data.reason}`;
      } else {
        groups.set(action.type, { ...action });
      }
    }

    return Array.from(groups.values());
  }
}