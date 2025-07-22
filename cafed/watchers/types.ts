/**
 * Common types for watchers
 */

export interface LogEntry {
  timestamp: string;
  component: string;
  type: string;
  content: Record<string, any>;
  raw: string;
}