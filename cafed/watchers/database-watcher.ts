/**
 * Database Watcher - Watches cafed SQLite database for session changes
 * This enables reactive TUI updates when new Claude Code sessions are discovered
 */

import { WatcherFn } from '../core/wte.js';
import { SQLiteService } from '../services/sqlite-service.js';
import { ClaudeDiscovery } from '../services/claude-discovery.js';

export interface DatabaseChangeEvent {
  type: 'session_discovered' | 'project_added' | 'database_updated';
  timestamp: string;
  data: {
    sessionCount?: number;
    projectCount?: number;
    newSessions?: any[];
    newProjects?: any[];
  };
}

export class DatabaseWatcher {
  private sqliteService: SQLiteService;
  private claudeDiscovery: ClaudeDiscovery;
  private lastSessionCount = 0;
  private lastProjectCount = 0;
  private intervalMs: number;

  constructor(
    sqliteService: SQLiteService,
    claudeDiscovery: ClaudeDiscovery,
    intervalMs: number = 5000 // Check every 5 seconds
  ) {
    this.sqliteService = sqliteService;
    this.claudeDiscovery = claudeDiscovery;
    this.intervalMs = intervalMs;
  }

  /**
   * Watch for database changes - implements WTE watch pattern
   */
  async* watch(): AsyncGenerator<DatabaseChangeEvent> {
    console.log('[DATABASE_WATCHER] Starting database watch...');
    
    while (true) {
      try {
        // Initialize if needed
        if (!await this.sqliteService.isInitialized()) {
          await this.sqliteService.initialize();
          await this.sqliteService.initializeSchema();
        }

        // Check current session and project counts
        const currentSessions = await this.sqliteService.getSessions();
        const currentProjects = await this.sqliteService.getProjects();
        
        const currentSessionCount = currentSessions.length;
        const currentProjectCount = currentProjects.length;

        // Detect changes
        if (currentSessionCount > this.lastSessionCount) {
          const newSessionsCount = currentSessionCount - this.lastSessionCount;
          console.log(`[DATABASE_WATCHER] Detected ${newSessionsCount} new session(s)`);
          
          yield {
            type: 'session_discovered' as const,
            timestamp: new Date().toISOString(),
            data: {
              sessionCount: currentSessionCount,
              newSessions: currentSessions.slice(-newSessionsCount)
            }
          };
        }

        if (currentProjectCount > this.lastProjectCount) {
          const newProjectsCount = currentProjectCount - this.lastProjectCount;
          console.log(`[DATABASE_WATCHER] Detected ${newProjectsCount} new project(s)`);
          
          yield {
            type: 'project_added' as const,
            timestamp: new Date().toISOString(),
            data: {
              projectCount: currentProjectCount,
              newProjects: currentProjects.slice(-newProjectsCount)
            }
          };
        }

        // Update counters
        this.lastSessionCount = currentSessionCount;
        this.lastProjectCount = currentProjectCount;

        // Periodically run discovery to check for new external sessions
        const discoveryResult = await this.claudeDiscovery.getSessionSummary();
        if (discoveryResult.totalSessions > currentSessionCount) {
          console.log('[DATABASE_WATCHER] External sessions detected, triggering discovery sync');
          
          yield {
            type: 'database_updated' as const,
            timestamp: new Date().toISOString(),
            data: {
              sessionCount: discoveryResult.totalSessions,
              projectCount: discoveryResult.totalProjects
            }
          };
        }

      } catch (error) {
        console.error('[DATABASE_WATCHER] Watch error:', error);
        // Continue watching even if there's an error
      }

      // Wait before next check
      await new Promise(resolve => setTimeout(resolve, this.intervalMs));
    }
  }
}

/**
 * Create database watcher with default configuration
 */
export function createDatabaseWatcher(intervalMs?: number): DatabaseWatcher {
  const sqliteService = new SQLiteService();
  const claudeDiscovery = new ClaudeDiscovery();
  
  return new DatabaseWatcher(sqliteService, claudeDiscovery, intervalMs);
}