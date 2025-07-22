/**
 * Common types for transforms
 */

export interface FileAction {
  type: 'read' | 'write' | 'list';
  path: string;
  timestamp: string;
}