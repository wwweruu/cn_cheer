export interface AssetSnapshot<T> {
  status: "idle" | "loading" | "ready" | "failed";
  value?: T;
  error?: string;
  fallback?: boolean;
}

interface Entry<T> {
  snapshot: AssetSnapshot<T>;
  listeners: Set<() => void>;
  cleanup?: ReturnType<typeof setTimeout>;
  generation: number;
}

/** One request per shared asset, bounded concurrency, and independent failures. */
export class AssetCache<T> {
  private entries = new Map<string, Entry<T>>();
  private queue: Array<() => Promise<void>> = [];
  private running = 0;
  private listeners = new Set<() => void>();
  private revision = 0;

  constructor(
    private load: (key: string) => Promise<{ value: T; fallback?: boolean }>,
    private dispose: (value: T) => void,
    private concurrency = 3,
    private retentionMs = 15000,
  ) {}

  private entry(key: string) {
    let entry = this.entries.get(key);
    if (!entry) {
      entry = { snapshot: { status: "idle" }, listeners: new Set(), generation: 0 };
      this.entries.set(key, entry);
    }
    return entry;
  }

  snapshot = (key: string) => this.entry(key).snapshot;
  version = () => this.revision;
  resources = () => [...this.entries.values()].flatMap(entry=>entry.snapshot.value ? [entry.snapshot.value] : []);
  subscribeAll = (listener: () => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };
  stats = () => {
    const active = [...this.entries.values()].filter(entry => entry.listeners.size);
    return {
      total: active.length,
      loading: active.filter(e => e.snapshot.status === "loading" || e.snapshot.status === "idle").length,
      failed: active.filter(e => e.snapshot.status === "failed").length,
      fallback: active.filter(e => e.snapshot.fallback).length,
      ready: active.filter(e => e.snapshot.status === "ready").length,
    };
  };

  private emit(entry: Entry<T>) {
    this.revision++;
    entry.listeners.forEach(listener => listener());
    this.listeners.forEach(listener => listener());
  }

  subscribe = (key: string, listener: () => void) => {
    const entry = this.entry(key);
    clearTimeout(entry.cleanup);
    entry.listeners.add(listener);
    if (entry.snapshot.status === "idle") this.start(key, entry);
    return () => {
      entry.listeners.delete(listener);
      if (!entry.listeners.size) this.scheduleCleanup(key, entry);
    };
  };

  private scheduleCleanup(key: string, entry: Entry<T>) {
    clearTimeout(entry.cleanup);
    entry.cleanup = setTimeout(() => {
      if (entry.listeners.size || entry.snapshot.status === "loading") return;
      if (entry.snapshot.value) this.dispose(entry.snapshot.value);
      this.entries.delete(key);
      this.emit(entry);
    }, this.retentionMs);
  }

  private drain() {
    while (this.running < this.concurrency && this.queue.length) {
      this.running++;
      void this.queue.shift()!().finally(() => { this.running--; this.drain(); });
    }
  }

  private start(key: string, entry: Entry<T>) {
    const generation = ++entry.generation;
    entry.snapshot = { status: "loading" };
    this.emit(entry);
    this.queue.push(async () => {
      try {
        const result = await this.load(key);
        if (generation !== entry.generation) { this.dispose(result.value); return; }
        entry.snapshot = { status: "ready", ...result };
      } catch (error) {
        if (generation !== entry.generation) return;
        entry.snapshot = { status: "failed", error: error instanceof Error ? error.message : String(error) };
      }
      this.emit(entry);
      if (!entry.listeners.size) this.scheduleCleanup(key, entry);
    });
    this.drain();
  }

  retryFailures = () => {
    for (const [key, entry] of this.entries) {
      if (entry.listeners.size && entry.snapshot.status === "failed") this.start(key, entry);
    }
  };
}
