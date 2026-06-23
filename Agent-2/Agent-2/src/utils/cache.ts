interface CacheEntry<T> {
  value: T;
  expiresAt: number;
}

export class SimpleCache<T = unknown> {
  private store = new Map<string, CacheEntry<T>>();
  private readonly defaultTtlMs: number;

  constructor(defaultTtlMs: number = 5 * 60 * 1000) {
    this.defaultTtlMs = defaultTtlMs;
  }

  get(key: string): T | undefined {
    const entry = this.store.get(key);
    if (!entry) return undefined;
    if (Date.now() > entry.expiresAt) {
      this.store.delete(key);
      return undefined;
    }
    return entry.value;
  }

  set(key: string, value: T, ttlMs?: number): void {
    this.store.set(key, {
      value,
      expiresAt: Date.now() + (ttlMs ?? this.defaultTtlMs)
    });
  }

  has(key: string): boolean {
    return this.get(key) !== undefined;
  }

  clear(): void {
    this.store.clear();
  }

  get size(): number {
    return this.store.size;
  }
}

export const poiSearchCache = new SimpleCache<any>(10 * 60 * 1000);
export const routeSegmentCache = new SimpleCache<any>(15 * 60 * 1000);
export const webSearchCache = new SimpleCache<any>(5 * 60 * 1000);

export function buildPoiCacheKey(city: string | undefined, keyword: string, category?: string): string {
  return `poi:${city ?? ""}:${keyword}:${category ?? ""}`;
}

export function buildRouteCacheKey(from: string, to: string, mode: string): string {
  return `route:${from}:${to}:${mode}`;
}

export function buildWebCacheKey(query: string, city?: string): string {
  return `web:${city ?? ""}:${query}`;
}
