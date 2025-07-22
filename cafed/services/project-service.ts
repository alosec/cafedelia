import { getSQLiteService, Project } from './sqlite-service.js';
import { getClaudeDiscovery, ClaudeProject } from './claude-discovery.js';
import { readdir, stat } from 'fs/promises';
import { join } from 'path';
import { existsSync } from 'fs';

/**
 * Project service for list/scan operations
 * Provides unified interface for database and file system project operations
 */

export interface ProjectListOptions {
  status?: string;
  hasSessionsOnly?: boolean;
}

export interface ProjectScanOptions {
  path?: string;
  recursive?: boolean;
}

export interface ScannedProject {
  name: string;
  path: string;
  type: string;
  git: boolean;
  sessions: number;
  activeSessions: number;
  lastActivity: string;
}

export class ProjectService {
  private sqliteService = getSQLiteService();
  private claudeDiscovery = getClaudeDiscovery();

  /**
   * List projects from database with filtering
   */
  async listProjects(options: ProjectListOptions = {}): Promise<Project[]> {
    // Ensure database is initialized
    if (!(await this.sqliteService.isInitialized())) {
      await this.sqliteService.initializeSchema();
    }

    return await this.sqliteService.getProjects({
      status: options.status,
      hasSessionsOnly: options.hasSessionsOnly
    });
  }

  /**
   * Scan filesystem for projects
   */
  async scanProjects(options: ProjectScanOptions = {}): Promise<ScannedProject[]> {
    const scanPath = options.path || process.cwd();
    
    if (!existsSync(scanPath)) {
      throw new Error(`Path does not exist: ${scanPath}`);
    }

    const projects: ScannedProject[] = [];
    const claudeSessions = await this.claudeDiscovery.findAllSessions();

    // Collect paths to scan
    const pathsToScan: string[] = [scanPath];
    
    if (options.recursive) {
      // Add subdirectories recursively
      const subdirs = await this.findSubdirectories(scanPath);
      pathsToScan.push(...subdirs);
    } else {
      // Add immediate subdirectories only
      try {
        const entries = await readdir(scanPath, { withFileTypes: true });
        for (const entry of entries) {
          if (entry.isDirectory()) {
            pathsToScan.push(join(scanPath, entry.name));
          }
        }
      } catch (error) {
        // Skip if can't read directory
      }
    }

    // Check each path for project indicators
    for (const projectPath of pathsToScan) {
      if (await this.isProjectDirectory(projectPath)) {
        // Check if it's associated with Claude Code sessions
        const associatedSessions = claudeSessions.filter(s => s.projectPath === projectPath);
        
        const projectName = projectPath.split('/').pop() || 'unknown';
        
        projects.push({
          name: projectName,
          path: projectPath,
          type: await this.detectProjectType(projectPath),
          git: existsSync(join(projectPath, '.git')),
          sessions: associatedSessions.length,
          activeSessions: associatedSessions.filter(s => s.isActive).length,
          lastActivity: associatedSessions.length > 0 
            ? new Date(Math.max(...associatedSessions.map(s => s.lastActivity.getTime()))).toISOString()
            : new Date().toISOString()
        });
      }
    }

    return projects.sort((a, b) => new Date(b.lastActivity).getTime() - new Date(a.lastActivity).getTime());
  }

  /**
   * Find subdirectories recursively
   */
  private async findSubdirectories(rootPath: string): Promise<string[]> {
    const subdirs: string[] = [];
    
    try {
      const entries = await readdir(rootPath, { withFileTypes: true });
      
      for (const entry of entries) {
        if (entry.isDirectory() && !entry.name.startsWith('.')) {
          const fullPath = join(rootPath, entry.name);
          subdirs.push(fullPath);
          
          // Recurse into subdirectory
          const nestedDirs = await this.findSubdirectories(fullPath);
          subdirs.push(...nestedDirs);
        }
      }
    } catch (error) {
      // Skip directories we can't read
    }
    
    return subdirs;
  }

  /**
   * Check if directory looks like a project
   */
  private async isProjectDirectory(path: string): Promise<boolean> {
    const indicators = [
      '.git',
      'package.json',
      'requirements.txt',
      'Cargo.toml',
      'pom.xml',
      'build.gradle',
      'Makefile',
      'pyproject.toml',
      'composer.json'
    ];

    for (const indicator of indicators) {
      if (existsSync(join(path, indicator))) {
        return true;
      }
    }

    return false;
  }

  /**
   * Detect project type based on files
   */
  private async detectProjectType(path: string): Promise<string> {
    if (existsSync(join(path, 'package.json'))) {
      return 'Node.js';
    } else if (existsSync(join(path, 'requirements.txt')) || existsSync(join(path, 'pyproject.toml'))) {
      return 'Python';
    } else if (existsSync(join(path, 'Cargo.toml'))) {
      return 'Rust';
    } else if (existsSync(join(path, 'pom.xml'))) {
      return 'Java/Maven';
    } else if (existsSync(join(path, 'build.gradle'))) {
      return 'Java/Gradle';
    } else if (existsSync(join(path, '.git'))) {
      return 'Git';
    } else {
      return 'Unknown';
    }
  }

  /**
   * Format project list output according to specified format
   */
  formatProjectList(projects: Project[], format: 'table' | 'json' | 'csv' = 'table'): string {
    if (format === 'json') {
      return JSON.stringify(projects.map(p => ({
        id: p.short_id,
        name: p.name,
        path: p.path,
        status: p.status,
        sessions: p.session_count,
        active_sessions: p.active_sessions,
        activity: p.last_activity
      })), null, 2);
    }

    if (format === 'csv') {
      if (projects.length === 0) return '';
      
      const headers = ['id', 'name', 'path', 'status', 'sessions', 'activity'];
      const csvRows = [
        headers.join(','),
        ...projects.map(p => [
          p.short_id,
          p.name,
          p.path,
          p.status,
          p.session_count?.toString() || '0',
          p.last_activity || 'N/A'
        ].map(field => `"${field}"`).join(','))
      ];
      return csvRows.join('\n');
    }

    // Table format
    if (projects.length === 0) {
      return 'No projects found in database';
    }

    // Calculate column widths
    const maxId = Math.max(...projects.map(p => p.short_id.length));
    const maxName = Math.max(...projects.map(p => p.name.length));
    const maxPath = Math.min(Math.max(...projects.map(p => p.path.length)), 40); // Limit path width
    const maxStatus = Math.max(...projects.map(p => p.status.length));

    // Headers
    const headers = [
      'ID'.padEnd(maxId),
      'NAME'.padEnd(maxName),
      'PATH'.padEnd(maxPath),
      'STATUS'.padEnd(maxStatus),
      'SESSIONS',
      'ACTIVITY'
    ].join(' ');
    
    const separator = '─'.repeat(headers.length);
    const lines = [
      'Projects from database:',
      separator,
      headers,
      separator
    ];

    for (const project of projects) {
      const pathDisplay = project.path.length <= maxPath 
        ? project.path 
        : '...' + project.path.substring(project.path.length - maxPath + 3);
      const activity = project.last_activity ? project.last_activity.substring(0, 16) : 'N/A';
      
      const line = [
        project.short_id.padEnd(maxId),
        project.name.padEnd(maxName),
        pathDisplay.padEnd(maxPath),
        project.status.padEnd(maxStatus),
        (project.session_count || 0).toString().padStart(7),
        activity
      ].join(' ');
      lines.push(line);
    }

    return lines.join('\n');
  }

  /**
   * Format project scan output according to specified format
   */
  formatProjectScan(projects: ScannedProject[], format: 'table' | 'json' | 'csv' = 'table'): string {
    if (format === 'json') {
      return JSON.stringify(projects, null, 2);
    }

    if (format === 'csv') {
      if (projects.length === 0) return '';
      
      const headers = ['name', 'path', 'type', 'git', 'sessions', 'active_sessions', 'last_activity'];
      const csvRows = [
        headers.join(','),
        ...projects.map(p => [
          p.name,
          p.path,
          p.type,
          p.git.toString(),
          p.sessions.toString(),
          p.activeSessions.toString(),
          p.lastActivity
        ].map(field => `"${field}"`).join(','))
      ];
      return csvRows.join('\n');
    }

    // Table format
    if (projects.length === 0) {
      return 'No projects found in scan';
    }

    const lines = [
      'Scanned projects from filesystem:',
      '─'.repeat(60)
    ];

    for (const project of projects) {
      lines.push(`Name: ${project.name}`);
      lines.push(`Path: ${project.path}`);
      lines.push(`Type: ${project.type}, Git: ${project.git ? 'Yes' : 'No'}`);
      lines.push(`Sessions: ${project.sessions} total, ${project.activeSessions} active`);
      lines.push(`Activity: ${new Date(project.lastActivity).toISOString()}`);
      lines.push('');
    }

    return lines.join('\n');
  }

  /**
   * Complete project list operation with formatting
   */
  async listProjectsFormatted(options: {
    status?: string;
    hasSessionsOnly?: boolean;
    format?: 'table' | 'json' | 'csv';
  }): Promise<string> {
    const listOptions: ProjectListOptions = {
      status: options.status,
      hasSessionsOnly: options.hasSessionsOnly
    };

    const projects = await this.listProjects(listOptions);
    return this.formatProjectList(projects, options.format || 'table');
  }

  /**
   * Complete project scan operation with formatting
   */
  async scanProjectsFormatted(options: {
    path?: string;
    recursive?: boolean;
    format?: 'table' | 'json' | 'csv';
  }): Promise<string> {
    const scanOptions: ProjectScanOptions = {
      path: options.path,
      recursive: options.recursive
    };

    const projects = await this.scanProjects(scanOptions);
    return this.formatProjectScan(projects, options.format || 'table');
  }

  /**
   * Load discovered projects into database
   */
  async loadDiscoveredProjects(): Promise<{
    discovered: number;
    loaded: number;
    skipped: number;
    errors: number;
  }> {
    // Ensure database is initialized
    if (!(await this.sqliteService.isInitialized())) {
      await this.sqliteService.initializeSchema();
    }

    const claudeProjects = await this.claudeDiscovery.findAllProjects();
    
    let loaded = 0;
    let skipped = 0;
    let errors = 0;

    for (const claudeProject of claudeProjects) {
      try {
        // Check if project already exists
        const existingProjects = await this.sqliteService.getProjects();
        const existingProject = existingProjects.find(p => p.path === claudeProject.path);

        if (existingProject) {
          skipped++;
          continue;
        }

        // Create project
        await this.sqliteService.createProject({
          name: claudeProject.name,
          path: claudeProject.path,
          description: `Discovered from Claude Code sessions (${claudeProject.sessionCount} sessions)`,
          hasGit: true, // Assume true for discovered projects
          discoveredFrom: 'claude_sessions'
        });

        loaded++;
      } catch (error) {
        console.error(`Error loading project ${claudeProject.name}: ${error}`);
        errors++;
      }
    }

    return {
      discovered: claudeProjects.length,
      loaded,
      skipped,
      errors
    };
  }
}

// Global singleton instance
let _projectService: ProjectService | null = null;

export function getProjectService(): ProjectService {
  if (!_projectService) {
    _projectService = new ProjectService();
  }
  return _projectService;
}