/**
 * Emacs Executor
 * Uses property-based pane discovery for intelligent routing
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import { join } from 'path';
import { FileAction } from '../transforms/types.js';

const execAsync = promisify(exec);

// Path to scripts directory - use process.cwd() to get project root
const SCRIPTS_DIR = join(process.cwd(), 'scripts');

/**
 * Find best pane for a role with optional source preference
 */
async function findBestPane(role: string, preferredSource?: string): Promise<string | null> {
  try {
    const scriptPath = join(SCRIPTS_DIR, 'pane-properties/find-best-pane-for-role.sh');
    const args = [role];
    if (preferredSource) args.push(preferredSource);
    
    const command = `"${scriptPath}" ${args.map(arg => `"${arg}"`).join(' ')}`;
    const { stdout } = await execAsync(command);
    
    return stdout.trim() || null;
  } catch (error) {
    console.error(`Failed to find pane for role=${role}:`, error);
    return null;
  }
}

export interface EmacsOptions {
  readOnly?: boolean;
  source?: string;  // Which assistant/context owns this operation
  role?: string;    // What type of pane to use
}

/**
 * Open file or directory in Emacs using property-based pane discovery
 */
export async function openInEmacs(
  action: FileAction, 
  options: EmacsOptions = {}
): Promise<void> {
  // Set defaults
  const source = options.source || 'claude-desktop';
  const role = options.role || 'editor';
  
  // Find best pane based on role and source
  const paneId = await findBestPane(role, source);
  
  if (!paneId) {
    console.error(`No pane found with role='${role}' (preferred source='${source}')`);
    console.error(`To assign a pane: assign_pane_properties session:X window:Y pane:Z role:'${role}' source:'${source}'`);
    return;
  }
  
  console.log(`[EXECUTE] ${action.type} ${action.path} -> ${paneId} (role=${role}, source=${source})${options.readOnly ? ' [read-only]' : ''}`);
  
  const scriptBase = join(SCRIPTS_DIR, 'emacs/pane-server');
  
  switch (action.type) {
    case 'read':
    case 'write': {
      const script = `${scriptBase}/open-file-in-pane.sh`;
      const readOnlyFlag = options.readOnly ? 'READ_ONLY=1' : '';
      await execAsync(`${readOnlyFlag} bash "${script}" "${action.path}" "${paneId}"`);
      break;
    }
    
    case 'list': {
      const script = `${scriptBase}/open-directory-in-pane.sh`;
      await execAsync(`bash "${script}" "${action.path}" "${paneId}"`);
      break;
    }
    
    default:
      console.warn(`Unknown action type: ${action.type}`);
  }
}

/**
 * Convenience exports for common configurations
 */
export const claudeDesktopEmacs = (action: FileAction) => 
  openInEmacs(action, { source: 'claude-desktop', role: 'editor' });

export const claudeCodeEmacs = (action: FileAction) => 
  openInEmacs(action, { source: 'claude-code', role: 'editor' });

export const userEmacs = (action: FileAction) => 
  openInEmacs(action, { source: 'user', role: 'editor' });