/**
 * Simple structured logger for Cafed
 */

export interface LogContext {
  component?: string;
  session?: string;
  operation?: string;
  [key: string]: any;
}

export class Logger {
  constructor(private defaultContext: LogContext = {}) {}

  private formatMessage(level: string, message: string, context: LogContext = {}) {
    const timestamp = new Date().toISOString();
    const combinedContext = { ...this.defaultContext, ...context };
    const contextStr = Object.keys(combinedContext).length > 0 
      ? ` ${JSON.stringify(combinedContext)}`
      : '';
    
    return `${timestamp} [${level.toUpperCase()}] ${message}${contextStr}`;
  }

  info(message: string, context?: LogContext) {
    console.log(this.formatMessage('info', message, context));
  }

  warn(message: string, context?: LogContext) {
    console.warn(this.formatMessage('warn', message, context));
  }

  error(message: string, context?: LogContext) {
    console.error(this.formatMessage('error', message, context));
  }

  debug(message: string, context?: LogContext) {
    if (process.env.DEBUG) {
      console.log(this.formatMessage('debug', message, context));
    }
  }

  child(context: LogContext): Logger {
    return new Logger({ ...this.defaultContext, ...context });
  }
}

// Global logger instance
export const logger = new Logger({ component: 'cafed' });

// Component-specific loggers
export const claudeCodeLogger = logger.child({ component: 'claude-code' });
export const claudeDesktopLogger = logger.child({ component: 'claude-desktop' });
export const emacsLogger = logger.child({ component: 'emacs' });
export const databaseLogger = logger.child({ component: 'database' });