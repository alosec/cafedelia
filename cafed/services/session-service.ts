import { getSQLiteService, Session } from './sqlite-service.js';
import { getClaudeDiscovery, ClaudeSession } from './claude-discovery.js';

/**
 * Session service for list/scan operations
 * Provides unified interface for database and file system session operations
 */

export interface SessionListOptions {
  projectId?: string;
  status?: string;
  since?: Date;
}

export interface SessionScanOptions {
  path?: string;
}

export interface FormattedOutput {
  format: 'table' | 'json' | 'csv';
  data: string;
}

export class SessionService {
  private sqliteService = getSQLiteService();
  private claudeDiscovery = getClaudeDiscovery();

  /**
   * List sessions from database with filtering
   */
  async listSessions(options: SessionListOptions = {}): Promise<Session[]> {
    // Ensure database is initialized
    if (!(await this.sqliteService.isInitialized())) {
      await this.sqliteService.initializeSchema();
    }

    return await this.sqliteService.getSessions({
      projectId: options.projectId,
      status: options.status,
      since: options.since
    });
  }

  /**
   * Scan Claude Code files for sessions
   */
  async scanSessions(options: SessionScanOptions = {}): Promise<ClaudeSession[]> {
    const claudeSessions = await this.claudeDiscovery.findAllSessions();

    if (options.path) {
      // Filter by path if specified
      return claudeSessions.filter(session => 
        session.projectPath.includes(options.path!)
      );
    }

    return claudeSessions;
  }

  /**
   * Format session output according to specified format
   */
  formatSessionList(sessions: Session[], format: 'table' | 'json' | 'csv' = 'table'): string {
    if (format === 'json') {
      return JSON.stringify(sessions.map(s => ({
        id: s.short_id,
        name: s.name,
        project: s.project_name,
        status: s.status,
        task: s.task_description,
        activity: s.last_activity,
        tmux: s.tmux_session_name,
        claude_uuid: s.claude_session_uuid
      })), null, 2);
    }

    if (format === 'csv') {
      if (sessions.length === 0) return '';
      
      const headers = ['id', 'name', 'project', 'status', 'task', 'activity'];
      const csvRows = [
        headers.join(','),
        ...sessions.map(s => [
          s.short_id,
          s.name,
          s.project_name,
          s.status,
          s.task_description || '',
          s.last_activity
        ].map(field => `"${field}"`).join(','))
      ];
      return csvRows.join('\n');
    }

    // Table format
    if (sessions.length === 0) {
      return 'No sessions found in database';
    }

    // Calculate column widths
    const maxId = Math.max(...sessions.map(s => s.short_id.length));
    const maxName = Math.max(...sessions.map(s => s.name.length));
    const maxProject = Math.max(...sessions.map(s => s.project_name?.length || 0));
    const maxStatus = Math.max(...sessions.map(s => s.status.length));

    // Headers
    const headers = [
      'ID'.padEnd(maxId),
      'NAME'.padEnd(maxName),
      'PROJECT'.padEnd(maxProject),
      'STATUS'.padEnd(maxStatus),
      'ACTIVITY'
    ].join(' ');
    
    const separator = '─'.repeat(headers.length);
    const lines = [
      'Sessions from database:',
      separator,
      headers,
      separator
    ];

    for (const session of sessions) {
      const activity = session.last_activity ? session.last_activity.substring(0, 16) : 'N/A';
      const line = [
        session.short_id.padEnd(maxId),
        session.name.padEnd(maxName),
        (session.project_name || '').padEnd(maxProject),
        session.status.padEnd(maxStatus),
        activity
      ].join(' ');
      lines.push(line);
    }

    return lines.join('\n');
  }

  /**
   * Format session scan output according to specified format
   */
  formatSessionScan(sessions: ClaudeSession[], format: 'table' | 'json' | 'csv' = 'table'): string {
    if (format === 'json') {
      return JSON.stringify(sessions.map(s => ({
        id: s.sessionUuid,
        name: `${s.projectName}-${s.conversationTurns}turns`,
        project: s.projectName,
        status: s.isActive ? 'active' : 'available',
        activity: s.lastActivity.toISOString(),
        turns: s.conversationTurns,
        cost: `$${s.totalCostUsd.toFixed(4)}`,
        path: s.projectPath,
        file: s.jsonlFilePath
      })), null, 2);
    }

    if (format === 'csv') {
      if (sessions.length === 0) return '';
      
      const headers = ['id', 'name', 'project', 'status', 'turns', 'cost', 'path'];
      const csvRows = [
        headers.join(','),
        ...sessions.map(s => [
          s.sessionUuid,
          `${s.projectName}-${s.conversationTurns}turns`,
          s.projectName,
          s.isActive ? 'active' : 'available',
          s.conversationTurns.toString(),
          `$${s.totalCostUsd.toFixed(4)}`,
          s.projectPath
        ].map(field => `"${field}"`).join(','))
      ];
      return csvRows.join('\n');
    }

    // Table format
    if (sessions.length === 0) {
      return 'No sessions found in Claude Code files';
    }

    const lines = [
      'Scanned sessions from Claude Code files:',
      '─'.repeat(60)
    ];

    for (const session of sessions) {
      lines.push(`ID: ${session.sessionUuid.substring(0, 8)}...`);
      lines.push(`Name: ${session.projectName}-${session.conversationTurns}turns`);
      lines.push(`Project: ${session.projectName}`);
      lines.push(`Status: ${session.isActive ? 'active' : 'available'}`);
      lines.push(`Turns: ${session.conversationTurns}, Cost: $${session.totalCostUsd.toFixed(4)}`);
      lines.push(`Path: ${session.projectPath}`);
      lines.push('');
    }

    return lines.join('\n');
  }

  /**
   * Parse time specification like "2 days ago", "1 hour ago"
   */
  private parseSince(sinceStr: string): Date {
    const since = sinceStr.toLowerCase();
    const now = new Date();

    if (since.includes('hour')) {
      const hours = parseInt(since.split(' ')[0]) || 1;
      return new Date(now.getTime() - hours * 60 * 60 * 1000);
    } else if (since.includes('day')) {
      const days = parseInt(since.split(' ')[0]) || 1;
      return new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
    } else if (since.includes('week')) {
      const weeks = parseInt(since.split(' ')[0]) || 1;
      return new Date(now.getTime() - weeks * 7 * 24 * 60 * 60 * 1000);
    } else {
      // Try to parse as ISO date
      try {
        return new Date(sinceStr);
      } catch {
        throw new Error(`Could not parse time specification: ${sinceStr}`);
      }
    }
  }

  /**
   * Complete session list operation with formatting
   */
  async listSessionsFormatted(options: {
    projectId?: string;
    status?: string;
    since?: string;
    format?: 'table' | 'json' | 'csv';
  }): Promise<string> {
    const listOptions: SessionListOptions = {
      projectId: options.projectId,
      status: options.status,
      since: options.since ? this.parseSince(options.since) : undefined
    };

    const sessions = await this.listSessions(listOptions);
    return this.formatSessionList(sessions, options.format || 'table');
  }

  /**
   * Complete session scan operation with formatting
   */
  async scanSessionsFormatted(options: {
    path?: string;
    format?: 'table' | 'json' | 'csv';
  }): Promise<string> {
    const scanOptions: SessionScanOptions = {
      path: options.path
    };

    const sessions = await this.scanSessions(scanOptions);
    return this.formatSessionScan(sessions, options.format || 'table');
  }

  /**
   * Load discovered sessions into database
   */
  async loadDiscoveredSessions(): Promise<{
    discovered: number;
    loaded: number;
    skipped: number;
    errors: number;
  }> {
    // Ensure database is initialized
    if (!(await this.sqliteService.isInitialized())) {
      await this.sqliteService.initializeSchema();
    }

    const claudeSessions = await this.claudeDiscovery.findAllSessions();
    const claudeProjects = await this.claudeDiscovery.findAllProjects();

    let loaded = 0;
    let skipped = 0;
    let errors = 0;

    // First, ensure projects exist in database
    for (const claudeProject of claudeProjects) {
      try {
        // Check if project already exists
        const existingProjects = await this.sqliteService.getProjects();
        const existingProject = existingProjects.find(p => p.path === claudeProject.path);

        if (!existingProject) {
          await this.sqliteService.createProject({
            name: claudeProject.name,
            path: claudeProject.path,
            description: `Discovered from Claude Code sessions`,
            hasGit: true, // Assume true for now
            discoveredFrom: 'claude_sessions'
          });
        }
      } catch (error) {
        console.error(`Error creating project ${claudeProject.name}: ${error}`);
        errors++;
      }
    }

    // Then, load sessions
    for (const claudeSession of claudeSessions) {
      try {
        // Find the project in database
        const projects = await this.sqliteService.getProjects();
        const project = projects.find(p => p.path === claudeSession.projectPath);

        if (!project) {
          console.warn(`Project not found for session ${claudeSession.sessionUuid}`);
          errors++;
          continue;
        }

        // Check if session already exists
        const existingSessions = await this.sqliteService.getSessions();
        const existingSession = existingSessions.find(s => s.claude_session_uuid === claudeSession.sessionUuid);

        if (existingSession) {
          skipped++;
          continue;
        }

        // Create session
        await this.sqliteService.createSession({
          projectId: project.short_id,
          name: `${claudeSession.projectName}-${claudeSession.conversationTurns}turns`,
          claudeSessionUuid: claudeSession.sessionUuid,
          taskDescription: `Discovered Claude session with ${claudeSession.conversationTurns} turns`,
          conversationTurns: claudeSession.conversationTurns,
          totalCostUsd: claudeSession.totalCostUsd,
          jsonlFilePath: claudeSession.jsonlFilePath
        });

        loaded++;
      } catch (error) {
        console.error(`Error loading session ${claudeSession.sessionUuid}: ${error}`);
        errors++;
      }
    }

    return {
      discovered: claudeSessions.length,
      loaded,
      skipped,
      errors
    };
  }
}

// Global singleton instance
let _sessionService: SessionService | null = null;

export function getSessionService(): SessionService {
  if (!_sessionService) {
    _sessionService = new SessionService();
  }
  return _sessionService;
}