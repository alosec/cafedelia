/**
 * Core Watch-Transform-Execute interface
 * The fundamental pattern of cafedelic v2
 */

export interface WTE<T, A> {
  watch: () => AsyncGenerator<T>;
  transform: (event: T) => A | null;
  execute: (action: A) => Promise<void>;
}

export type WatcherFn<T> = () => AsyncGenerator<T>;
export type TransformFn<T, A> = (event: T) => A | null;
export type ExecutorFn<A> = (action: A) => Promise<void>;
