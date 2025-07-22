import { getClaudeDiscovery, ClaudeProject, ClaudeSession } from './claude-discovery.js';

/**
 * Service for accessing Claude Code data through HTTP-friendly interface
 * Wraps claude-discovery.ts to provide formatted data for TUI consumption
 */
export class ClaudeCodeService {
  private discovery = getClaudeDiscovery();

  /**
   * Get all projects formatted for TUI display
   */
  async getProjects(): Promise<any[]> {
    const projects = await this.discovery.findAllProjects();
    return projects.map((project: ClaudeProject) => this.formatProjectForTUI(project));
  }

  /**
   * Get all sessions formatted for TUI display
   */
  async getSessions(): Promise<any[]> {
    const sessions = await this.discovery.findAllSessions();
    return sessions.map((session: ClaudeSession) => this.formatSessionForTUI(session));
  }

  /**
   * Get sessions for a specific project
   */
  async getSessionsForProject(projectPath: string): Promise<any[]> {
    const sessions = await this.discovery.findSessionsForProject(projectPath);
    return sessions.map((session: ClaudeSession) => this.formatSessionForTUI(session));
  }

  /**
   * Get session summary statistics
   */
  async getSessionSummary(): Promise<{
    totalSessions: number;
    activeSessions: number;
    totalProjects: number;
    totalCost: number;
  }> {
    return await this.discovery.getSessionSummary();
  }

  /**
   * Format ClaudeProject for TUI consumption
   */
  private formatProjectForTUI(project: ClaudeProject): any {
    return {
      name: project.name,
      path: project.path,
      status: project.sessionCount > 0 ? 'active' : 'inactive',
      sessions: project.sessions,
      activity_level: Math.min(project.sessionCount, 3) // 0-3 for emoji display
    };
  }

  /**
   * Format ClaudeSession for TUI consumption
   */
  private formatSessionForTUI(session: ClaudeSession): any {
    // Calculate duration from creation to last activity
    const duration = this.formatDuration(session.createdAt, session.lastActivity);
    
    // Calculate progress based on activity (simplified)
    const progress = session.conversationTurns > 0 ? Math.min(session.conversationTurns / 100, 1.0) : 0;
    
    return {
      id: session.sessionUuid,
      name: `${session.projectName} Session`,
      project: session.projectName,
      status: session.isActive ? 'active' : 'inactive',
      task: this.extractTaskFromSession(session),
      progress: progress,
      duration: duration,
      last_activity: session.lastActivity.toISOString(),
      files_context: session.fileOperations.map((file: string) => ({ path: file }))
    };
  }

  /**
   * Extract task description from session (simplified)
   */
  private extractTaskFromSession(session: ClaudeSession): string {
    if (session.fileOperations.length > 0) {
      return `Working on ${session.fileOperations.length} files`;
    }
    return `${session.conversationTurns} conversation turns`;
  }

  /**
   * Format duration between two dates
   */
  private formatDuration(start: Date, end: Date): string {
    const diffMs = end.getTime() - start.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    
    if (diffMins < 60) {
      return `${diffMins}m`;
    } else if (diffMins < 1440) {
      return `${Math.floor(diffMins / 60)}h`;
    } else {
      return `${Math.floor(diffMins / 1440)}d`;
    }
  }
}

// Global singleton instance
let _claudeCodeService: ClaudeCodeService | null = null;

export function getClaudeCodeService(): ClaudeCodeService {
  if (!_claudeCodeService) {
    _claudeCodeService = new ClaudeCodeService();
  }
  return _claudeCodeService;
}