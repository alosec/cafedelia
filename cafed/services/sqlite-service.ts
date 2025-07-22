import sqlite3 from 'sqlite3';
import { promisify } from 'util';
import { readFile } from 'fs/promises';
import { join } from 'path';
import { homedir } from 'os';

/**
 * TypeScript SQLite service for Cafed database operations
 * Provides async/await interface over sqlite3 callbacks
 */

export interface Project {
  id: number;
  short_id: string;
  name: string;
  path: string;
  description?: string;
  status: 'active' | 'archived' | 'paused';
  has_git: boolean;
  git_remote_url?: string;
  discovered_from: 'manual' | 'claude_sessions' | 'filesystem_scan';
  created_at: string;
  updated_at: string;
  session_count?: number;
  active_sessions?: number;
  last_activity?: string;
}

export interface Session {
  id: number;
  short_id: string;
  project_id: number;
  name: string;
  claude_session_uuid?: string;
  tmux_session_name?: string;
  tmux_window_id?: string;
  tmux_pane_id?: string;
  status: 'active' | 'available' | 'detached' | 'stuck' | 'inactive';
  task_description?: string;
  conversation_turns: number;
  total_cost_usd: number;
  jsonl_file_path?: string;
  created_at: string;
  updated_at: string;
  last_activity: string;
  project_name?: string;
  project_short_id?: string;
  recent_activity_count?: number;
}

export interface Activity {
  id: number;
  session_id: number;
  activity_type: string;
  description: string;
  file_path?: string;
  created_at: string;
}

export class SQLiteService {
  private db: sqlite3.Database | null = null;
  private dbPath: string;

  constructor(dbPath?: string) {
    this.dbPath = dbPath || join(homedir(), '.cafed', 'intelligence.db');
  }

  /**
   * Initialize database connection and schema
   */
  async initialize(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.db = new sqlite3.Database(this.dbPath, (err) => {
        if (err) {
          reject(new Error(`Failed to open database: ${err.message}`));
          return;
        }
        resolve();
      });
    });
  }

  /**
   * Check if database is initialized with tables
   */
  async isInitialized(): Promise<boolean> {
    if (!this.db) await this.initialize();
    
    return new Promise((resolve, reject) => {
      this.db!.get(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'",
        (err, row) => {
          if (err) {
            reject(err);
            return;
          }
          resolve(!!row);
        }
      );
    });
  }

  /**
   * Initialize database schema
   */
  async initializeSchema(): Promise<void> {
    if (!this.db) await this.initialize();

    const createTablesSQL = `
    CREATE TABLE IF NOT EXISTS projects (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      short_id TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL,
      path TEXT UNIQUE NOT NULL,
      description TEXT,
      status TEXT DEFAULT 'active',
      has_git BOOLEAN DEFAULT 0,
      git_remote_url TEXT,
      discovered_from TEXT DEFAULT 'manual',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      short_id TEXT UNIQUE NOT NULL,
      project_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      claude_session_uuid TEXT,
      tmux_session_name TEXT,
      tmux_window_id TEXT,
      tmux_pane_id TEXT,
      status TEXT DEFAULT 'available',
      task_description TEXT,
      conversation_turns INTEGER DEFAULT 0,
      total_cost_usd REAL DEFAULT 0.0,
      jsonl_file_path TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (project_id) REFERENCES projects (id)
    );

    CREATE TABLE IF NOT EXISTS activities (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id INTEGER NOT NULL,
      activity_type TEXT NOT NULL,
      description TEXT NOT NULL,
      file_path TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (session_id) REFERENCES sessions (id)
    );

    CREATE VIEW IF NOT EXISTS project_summary AS
    SELECT 
      p.id,
      p.short_id,
      p.name,
      p.path,
      p.description,
      p.status,
      p.has_git,
      p.git_remote_url,
      p.discovered_from,
      p.created_at,
      p.updated_at,
      COUNT(s.id) as session_count,
      COUNT(CASE WHEN s.status = 'active' THEN 1 END) as active_sessions,
      MAX(s.last_activity) as last_activity
    FROM projects p
    LEFT JOIN sessions s ON p.id = s.project_id
    GROUP BY p.id;

    CREATE VIEW IF NOT EXISTS active_sessions AS
    SELECT 
      s.id,
      s.short_id,
      s.project_id,
      s.name,
      s.claude_session_uuid,
      s.tmux_session_name,
      s.tmux_window_id,
      s.tmux_pane_id,
      s.status,
      s.task_description,
      s.conversation_turns,
      s.total_cost_usd,
      s.jsonl_file_path,
      s.created_at,
      s.updated_at,
      s.last_activity,
      p.name as project_name,
      p.short_id as project_short_id,
      COUNT(a.id) as recent_activity_count
    FROM sessions s
    JOIN projects p ON s.project_id = p.id
    LEFT JOIN activities a ON s.id = a.session_id
    GROUP BY s.id;
    `;

    return new Promise((resolve, reject) => {
      this.db!.exec(createTablesSQL, (err) => {
        if (err) {
          reject(new Error(`Failed to initialize schema: ${err.message}`));
          return;
        }
        resolve();
      });
    });
  }

  /**
   * Get all projects with summary information
   */
  async getProjects(options?: {
    status?: string;
    hasSessionsOnly?: boolean;
  }): Promise<Project[]> {
    if (!this.db) await this.initialize();

    let query = 'SELECT * FROM project_summary';
    const params: any[] = [];

    if (options?.status) {
      query += ' WHERE status = ?';
      params.push(options.status);
    }

    if (options?.hasSessionsOnly) {
      query += options.status ? ' AND' : ' WHERE';
      query += ' session_count > 0';
    }

    query += ' ORDER BY last_activity DESC';

    return new Promise((resolve, reject) => {
      this.db!.all(query, params, (err, rows: any[]) => {
        if (err) {
          reject(err);
          return;
        }
        resolve(rows.map(row => ({
          ...row,
          has_git: !!row.has_git,
          session_count: row.session_count || 0,
          active_sessions: row.active_sessions || 0
        })));
      });
    });
  }

  /**
   * Get sessions with optional filtering
   */
  async getSessions(options?: {
    projectId?: string;
    status?: string;
    since?: Date;
  }): Promise<Session[]> {
    if (!this.db) await this.initialize();

    let query = 'SELECT * FROM active_sessions';
    const params: any[] = [];
    const conditions: string[] = [];

    if (options?.projectId) {
      conditions.push('project_short_id = ?');
      params.push(options.projectId);
    }

    if (options?.status) {
      conditions.push('status = ?');
      params.push(options.status);
    }

    if (options?.since) {
      conditions.push('last_activity >= ?');
      params.push(options.since.toISOString());
    }

    if (conditions.length > 0) {
      query += ' WHERE ' + conditions.join(' AND ');
    }

    query += ' ORDER BY last_activity DESC';

    return new Promise((resolve, reject) => {
      this.db!.all(query, params, (err, rows: any[]) => {
        if (err) {
          reject(err);
          return;
        }
        resolve(rows.map(row => ({
          ...row,
          recent_activity_count: row.recent_activity_count || 0
        })));
      });
    });
  }

  /**
   * Create a new project with retry mechanism for concurrent operations
   */
  async createProject(project: {
    name: string;
    path: string;
    description?: string;
    hasGit?: boolean;
    gitRemoteUrl?: string;
    discoveredFrom?: 'manual' | 'claude_sessions' | 'filesystem_scan';
  }): Promise<string> {
    if (!this.db) await this.initialize();

    // Retry up to 5 times for concurrent operations
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        // Find next available short_id within a transaction
        const lastProject = await new Promise<{ short_id: string } | undefined>((resolve, reject) => {
          this.db!.get(
            "SELECT short_id FROM projects WHERE short_id LIKE 'p%' ORDER BY short_id DESC LIMIT 1",
            (err, row: any) => {
              if (err) reject(err);
              else resolve(row);
            }
          );
        });

        let nextNum = 1;
        if (lastProject) {
          nextNum = parseInt(lastProject.short_id.substring(1)) + 1;
        }

        const shortId = `p${nextNum}`;

        return await new Promise<string>((resolve, reject) => {
          this.db!.run(
            `INSERT INTO projects (short_id, name, path, description, has_git, git_remote_url, discovered_from)
             VALUES (?, ?, ?, ?, ?, ?, ?)`,
            [
              shortId,
              project.name,
              project.path,
              project.description || '',
              project.hasGit ? 1 : 0,
              project.gitRemoteUrl || null,
              project.discoveredFrom || 'manual'
            ],
            function(err) {
              if (err) {
                reject(err);
                return;
              }
              resolve(shortId);
            }
          );
        });
      } catch (error: any) {
        // If it's a UNIQUE constraint error, retry with a delay
        if (error.message.includes('UNIQUE constraint failed') && attempt < 4) {
          await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 10));
          continue;
        }
        throw error;
      }
    }
    throw new Error('Failed to create project after multiple attempts');
  }

  /**
   * Create a new session with retry mechanism for concurrent operations
   */
  async createSession(session: {
    projectId: string;
    name: string;
    claudeSessionUuid?: string;
    taskDescription?: string;
    conversationTurns?: number;
    totalCostUsd?: number;
    jsonlFilePath?: string;
  }): Promise<string> {
    if (!this.db) await this.initialize();

    // Get project's actual ID
    const project = await new Promise<{ id: number } | undefined>((resolve, reject) => {
      this.db!.get(
        'SELECT id FROM projects WHERE short_id = ?',
        [session.projectId],
        (err, row: any) => {
          if (err) reject(err);
          else resolve(row);
        }
      );
    });

    if (!project) {
      throw new Error(`Project ${session.projectId} not found`);
    }

    // Retry up to 5 times for concurrent operations
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        // Find next available short_id
        const lastSession = await new Promise<{ short_id: string } | undefined>((resolve, reject) => {
          this.db!.get(
            "SELECT short_id FROM sessions WHERE short_id LIKE 's%' ORDER BY short_id DESC LIMIT 1",
            (err, row: any) => {
              if (err) reject(err);
              else resolve(row);
            }
          );
        });

        let nextNum = 1;
        if (lastSession) {
          nextNum = parseInt(lastSession.short_id.substring(1)) + 1;
        }

        const shortId = `s${nextNum}`;

        return await new Promise<string>((resolve, reject) => {
          this.db!.run(
            `INSERT INTO sessions (short_id, project_id, name, claude_session_uuid, task_description, conversation_turns, total_cost_usd, jsonl_file_path)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
            [
              shortId,
              project.id,
              session.name,
              session.claudeSessionUuid || null,
              session.taskDescription || '',
              session.conversationTurns || 0,
              session.totalCostUsd || 0.0,
              session.jsonlFilePath || null
            ],
            function(err) {
              if (err) {
                reject(err);
                return;
              }
              resolve(shortId);
            }
          );
        });
      } catch (error: any) {
        // If it's a UNIQUE constraint error, retry with a delay
        if (error.message.includes('UNIQUE constraint failed') && attempt < 4) {
          await new Promise(resolve => setTimeout(resolve, Math.random() * 100 + 10));
          continue;
        }
        throw error;
      }
    }
    throw new Error('Failed to create session after multiple attempts');
  }

  /**
   * Close database connection
   */
  async close(): Promise<void> {
    if (!this.db) return;

    return new Promise((resolve, reject) => {
      this.db!.close((err) => {
        if (err) {
          reject(err);
          return;
        }
        this.db = null;
        resolve();
      });
    });
  }
}

// Global singleton instance
let _sqliteService: SQLiteService | null = null;

export function getSQLiteService(): SQLiteService {
  if (!_sqliteService) {
    _sqliteService = new SQLiteService();
  }
  return _sqliteService;
}