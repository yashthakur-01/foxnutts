import supabase from "../supabase/adminClient";

interface CacheEntry<T> {
  value: T;
  expiresAt: number;
}

class InMemoryTTLCache<T> {
  private cache = new Map<string, CacheEntry<T>>();
  private ttlMs: number;

  constructor(ttlMs: number = 60000) {
    this.ttlMs = ttlMs;
  }

  get(key: string): T | undefined {
    const entry = this.cache.get(key);
    if (!entry) return undefined;
    if (Date.now() > entry.expiresAt) {
      this.cache.delete(key);
      return undefined;
    }
    return entry.value;
  }

  set(key: string, value: T): void {
    this.cache.set(key, {
      value,
      expiresAt: Date.now() + this.ttlMs,
    });
  }

  delete(key: string): void {
    this.cache.delete(key);
  }

  clear(): void {
    this.cache.clear();
  }
}

// 60-second TTL cache for auth user tokens
const userSessionCache = new InMemoryTTLCache<any>(60000);

export async function getCachedUser(authHeader: string | null) {
  if (!authHeader) {
    return { user: null, error: { message: "Authorization header missing" } };
  }

  const token = authHeader.replace(/^Bearer\s+/i, "").trim();
  if (!token) {
    return { user: null, error: { message: "Invalid authorization token" } };
  }

  // 1. Check in-memory TTL cache
  const cachedUser = userSessionCache.get(token);
  if (cachedUser) {
    return { user: cachedUser, error: null };
  }

  // 2. Cache Miss: Query Supabase Auth
  const { data: customer, error: customerError } = await supabase.auth.getUser(authHeader);
  if (customerError || !customer?.user) {
    return { user: null, error: customerError };
  }

  // 3. Store in cache
  userSessionCache.set(token, customer.user);
  return { user: customer.user, error: null };
}

export function invalidateAuthUserCache(authHeader: string | null) {
  if (!authHeader) return;
  const token = authHeader.replace(/^Bearer\s+/i, "").trim();
  if (token) {
    userSessionCache.delete(token);
  }
}
