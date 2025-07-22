import { readFile, stat, readdir } from 'fs/promises';
import { join } from 'path';
import { homedir } from 'os';
import { existsSync } from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

/**
 * TypeScript port of Claude Code Discovery Module
 * Scans ~/.claude/projects/ and parses JSONL session files to extract real session data.
 */

export interface ClaudeSession {
  sessionUuid: string;
  projectPath: string;
  projectName: string;
  title: string;
  createdAt: Date;
  lastActivity: Date;
  conversationTurns: number;
  totalCostUsd: number;
  fileOperations: string[];
  isActive: boolean;
  jsonlFilePath: string;
}

export interface ClaudeProject {
  path: string;
  name: string;
  sessionCount: number;
  lastActivity: Date;
  sessions: string[]; // UUIDs
}

export interface PathMappings {
  mappings: Record<string, string>;
}

export class ClaudeDiscovery {
  private claudeDir: string;
  private pathMappings: Record<string, string> = {};

  constructor() {
    this.claudeDir = join(homedir(), '.claude', 'projects');
    this.loadPathMappings();
  }

  /**
   * Load path mappings from JSON file
   */
  private async loadPathMappings(): Promise<void> {
    try {
      const mappingsFile = join(process.cwd(), 'cafed', 'database', 'path_mappings.json');
      if (existsSync(mappingsFile)) {
        const data = await readFile(mappingsFile, 'utf-8');
        const parsed: PathMappings = JSON.parse(data);
        this.pathMappings = parsed.mappings || {};
      }
    } catch (error) {
      console.warn(`Warning: Could not load path mappings: ${error}`);
    }
  }

  /**
   * Decode Claude's directory encoding back to filesystem path
   */
  decodeProjectPath(encodedName: string): string {
    // First check if we have a manual mapping for this encoded name
    if (this.pathMappings[encodedName]) {
      return this.pathMappings[encodedName];
    }

    // Fallback to algorithmic decoding
    // Claude encodes paths like: /home/alex/code/cafedelic -> -home-alex-code-cafedelic
    if (encodedName.startsWith('-')) {
      // Remove leading dash and replace remaining dashes with slashes
      const decoded = encodedName.substring(1).replace(/-/g, '/');
      return `/${decoded}`;
    }
    return encodedName;
  }

  /**
   * Validate if string is a proper UUID
   */
  private isValidUuid(uuid: string): boolean {
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return uuidRegex.test(uuid);
  }

  /**
   * Scan ~/.claude/projects/ and discover all projects
   */
  async findAllProjects(): Promise<ClaudeProject[]> {
    if (!existsSync(this.claudeDir)) {
      return [];
    }

    const projects: ClaudeProject[] = [];

    try {
      const projectDirs = await readdir(this.claudeDir, { withFileTypes: true });

      for (const dirent of projectDirs) {
        if (!dirent.isDirectory()) {
          continue;
        }

        // Decode project path from directory name
        const projectPath = this.decodeProjectPath(dirent.name);
        const projectName = projectPath !== dirent.name 
          ? projectPath.split('/').pop() || dirent.name
          : dirent.name;

        // Find all session files in this project
        const projectDir = join(this.claudeDir, dirent.name);
        const sessionFiles = await readdir(projectDir);
        const jsonlFiles = sessionFiles.filter(file => file.endsWith('.jsonl'));

        const sessionUuids: string[] = [];
        let lastActivity: Date | null = null;

        for (const sessionFile of jsonlFiles) {
          // Extract UUID from filename
          const sessionUuid = sessionFile.replace('.jsonl', '');

          // Validate it's a proper UUID
          if (this.isValidUuid(sessionUuid)) {
            sessionUuids.push(sessionUuid);

            // Get file modification time for last activity
            try {
              const filePath = join(projectDir, sessionFile);
              const fileStat = await stat(filePath);
              const fileMtime = new Date(fileStat.mtime);
              
              if (!lastActivity || fileMtime > lastActivity) {
                lastActivity = fileMtime;
              }
            } catch (error) {
              // Skip if can't read file stats
              continue;
            }
          }
        }

        if (sessionUuids.length > 0) { // Only add projects that have valid sessions
          projects.push({
            path: projectPath,
            name: projectName,
            sessionCount: sessionUuids.length,
            lastActivity: lastActivity || new Date(),
            sessions: sessionUuids
          });
        }
      }
    } catch (error) {
      console.error(`Error reading Claude projects directory: ${error}`);
      return [];
    }

    return projects.sort((a, b) => b.lastActivity.getTime() - a.lastActivity.getTime());
  }

  /**
   * Parse a JSONL session file to extract metadata
   */
  async parseSessionFile(sessionFilePath: string): Promise<ClaudeSession | null> {
    if (!existsSync(sessionFilePath)) {
      return null;
    }

    try {
      const sessionUuid = sessionFilePath.split('/').pop()?.replace('.jsonl', '') || '';

      // Validate UUID
      if (!this.isValidUuid(sessionUuid)) {
        return null;
      }

      // Decode project path from parent directory
      const parentDir = sessionFilePath.split('/').slice(-2, -1)[0];
      const projectPath = this.decodeProjectPath(parentDir);
      const projectName = projectPath !== parentDir 
        ? projectPath.split('/').pop() || parentDir
        : parentDir;

      // Parse JSONL file for metadata
      let conversationTurns = 0;
      let totalCost = 0.0;
      const fileOperations: string[] = [];
      let createdAt: Date | null = null;
      let lastActivity: Date | null = null;
      let sessionTitle: string | null = null;

      const content = await readFile(sessionFilePath, 'utf-8');
      const lines = content.split('\n');

      for (const [lineNum, line] of lines.entries()) {
        const trimmedLine = line.trim();
        if (!trimmedLine) {
          continue;
        }

        try {
          const entry = JSON.parse(trimmedLine);
          conversationTurns++;

          // Extract title from summary entry
          if (entry.type === "summary" && entry.summary && !sessionTitle) {
            sessionTitle = entry.summary;
          }

          // Extract timestamp
          if (entry.timestamp) {
            const timestamp = new Date(entry.timestamp);
            if (!createdAt) {
              createdAt = timestamp;
            }
            lastActivity = timestamp;
          }

          // Extract cost
          if (entry.total_cost_usd) {
            totalCost += parseFloat(entry.total_cost_usd) || 0;
          }

          // Extract file operations from tool calls
          if (entry.tool_calls && Array.isArray(entry.tool_calls)) {
            for (const toolCall of entry.tool_calls) {
              if (toolCall && typeof toolCall === 'object' && toolCall.tool_input) {
                const toolInput = toolCall.tool_input;
                if (toolInput.file_path && !fileOperations.includes(toolInput.file_path)) {
                  fileOperations.push(toolInput.file_path);
                }
              }
            }
          }
        } catch (error) {
          // Skip malformed lines
          continue;
        }
      }

      // Use file modification time if no timestamps in content
      const fileStat = await stat(sessionFilePath);
      if (!lastActivity) {
        lastActivity = new Date(fileStat.mtime);
      }
      if (!createdAt) {
        createdAt = new Date(fileStat.birthtime || fileStat.ctime);
      }

      // Check if session is currently active (basic process check)
      const isActive = await this.isSessionActive(sessionUuid);

      return {
        sessionUuid,
        projectPath,
        projectName,
        title: sessionTitle || `Claude Code Session (${sessionUuid.substring(0, 8)})`,
        createdAt,
        lastActivity,
        conversationTurns,
        totalCostUsd: totalCost,
        fileOperations,
        isActive,
        jsonlFilePath: sessionFilePath
      };

    } catch (error) {
      console.error(`Error parsing session file ${sessionFilePath}: ${error}`);
      return null;
    }
  }

  /**
   * Find and parse all Claude Code sessions
   */
  async findAllSessions(): Promise<ClaudeSession[]> {
    const sessions: ClaudeSession[] = [];

    if (!existsSync(this.claudeDir)) {
      return sessions;
    }

    try {
      // Find all JSONL files in all project directories
      const projectDirs = await readdir(this.claudeDir, { withFileTypes: true });

      for (const dirent of projectDirs) {
        if (!dirent.isDirectory()) {
          continue;
        }

        const projectDir = join(this.claudeDir, dirent.name);
        const files = await readdir(projectDir);
        const jsonlFiles = files.filter(file => file.endsWith('.jsonl'));

        for (const jsonlFile of jsonlFiles) {
          const sessionFilePath = join(projectDir, jsonlFile);
          const sessionData = await this.parseSessionFile(sessionFilePath);
          if (sessionData) {
            sessions.push(sessionData);
          }
        }
      }
    } catch (error) {
      console.error(`Error finding Claude sessions: ${error}`);
    }

    return sessions.sort((a, b) => b.lastActivity.getTime() - a.lastActivity.getTime());
  }

  /**
   * Find all sessions for a specific project path
   */
  async findSessionsForProject(projectPath: string): Promise<ClaudeSession[]> {
    const allSessions = await this.findAllSessions();
    return allSessions.filter(s => s.projectPath === projectPath);
  }

  /**
   * Check if a session is currently active (basic process detection)
   */
  private async isSessionActive(sessionUuid: string): Promise<boolean> {
    try {
      // Look for claude processes that might be running this session
      const { stdout } = await execAsync('ps aux');
      
      // Look for claude processes
      const claudeProcesses = stdout
        .split('\n')
        .filter(line => line.includes('claude') && !line.includes('grep'));
      
      // This is a basic check - more sophisticated process detection could be added
      return claudeProcesses.length > 0;
    } catch (error) {
      return false;
    }
  }

  /**
   * Get summary statistics about Claude Code sessions
   */
  async getSessionSummary(): Promise<{
    totalSessions: number;
    activeSessions: number;
    totalProjects: number;
    totalCost: number;
  }> {
    const sessions = await this.findAllSessions();
    const projects = await this.findAllProjects();

    const activeSessions = sessions.filter(s => s.isActive).length;
    const totalCost = sessions.reduce((sum, s) => sum + s.totalCostUsd, 0);

    return {
      totalSessions: sessions.length,
      activeSessions,
      totalProjects: projects.length,
      totalCost
    };
  }
}

// Global singleton instance
let _claudeDiscovery: ClaudeDiscovery | null = null;

export function getClaudeDiscovery(): ClaudeDiscovery {
  if (!_claudeDiscovery) {
    _claudeDiscovery = new ClaudeDiscovery();
  }
  return _claudeDiscovery;
}
