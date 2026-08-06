import Redis from "ioredis";

const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379/0";

let redisClient: Redis | null = null;

try {
  redisClient = new Redis(REDIS_URL, {
    maxRetriesPerRequest: 1,
    lazyConnect: true,
  });
  redisClient.connect().catch((err) => {
    console.warn("[Next.js Redis Warning] Could not connect to Redis:", err.message);
  });
} catch (e) {
  console.warn("[Next.js Redis Warning] ioredis initialization error:", e);
}

export default redisClient;
