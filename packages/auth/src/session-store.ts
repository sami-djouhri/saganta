import type { PendingAuth, PendingStore, SessionRecord, SessionStore } from './types.js';

interface TimedEntry<T> {
  value: T;
  expiresAt: number;
}

/**
 * In-Memory-Store. Reicht für Single-Replica Dev und LAN-Phase.
 * Für Multi-Replica oder Restart-Persistenz: Redis-Backend (siehe createRedisSessionStore).
 */
export function createMemorySessionStore(): SessionStore {
  const map = new Map<string, TimedEntry<SessionRecord>>();
  return {
    async get(sid) {
      const e = map.get(sid);
      if (!e) return null;
      if (e.expiresAt < Date.now()) {
        map.delete(sid);
        return null;
      }
      return e.value;
    },
    async set(sid, record, ttlSeconds) {
      map.set(sid, { value: record, expiresAt: Date.now() + ttlSeconds * 1000 });
    },
    async destroy(sid) {
      map.delete(sid);
    },
  };
}

export function createMemoryPendingStore(): PendingStore {
  const map = new Map<string, TimedEntry<PendingAuth>>();
  return {
    async get(state) {
      const e = map.get(state);
      if (!e) return null;
      if (e.expiresAt < Date.now()) {
        map.delete(state);
        return null;
      }
      return e.value;
    },
    async set(state, pending, ttlSeconds) {
      map.set(state, { value: pending, expiresAt: Date.now() + ttlSeconds * 1000 });
    },
    async destroy(state) {
      map.delete(state);
    },
  };
}

/**
 * Redis-Backend für Prod. Erwartet ein ioredis-kompatibles Interface (get/set/del).
 * Wir injizieren den Client per Konstruktor, um die Library nicht hart zu koppeln.
 */
interface RedisLike {
  get(key: string): Promise<string | null>;
  set(key: string, value: string, mode: 'EX', ttl: number): Promise<unknown>;
  del(key: string): Promise<unknown>;
}

export function createRedisSessionStore(redis: RedisLike, prefix = 'saganta:sess:'): SessionStore {
  return {
    async get(sid) {
      const raw = await redis.get(prefix + sid);
      return raw ? (JSON.parse(raw) as SessionRecord) : null;
    },
    async set(sid, record, ttlSeconds) {
      await redis.set(prefix + sid, JSON.stringify(record), 'EX', ttlSeconds);
    },
    async destroy(sid) {
      await redis.del(prefix + sid);
    },
  };
}

export function createRedisPendingStore(redis: RedisLike, prefix = 'saganta:pending:'): PendingStore {
  return {
    async get(state) {
      const raw = await redis.get(prefix + state);
      return raw ? (JSON.parse(raw) as PendingAuth) : null;
    },
    async set(state, pending, ttlSeconds) {
      await redis.set(prefix + state, JSON.stringify(pending), 'EX', ttlSeconds);
    },
    async destroy(state) {
      await redis.del(prefix + state);
    },
  };
}
