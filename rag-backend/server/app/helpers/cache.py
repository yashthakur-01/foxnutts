import json
import os
import redis
from supabase_client.client import supabase

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    print(f"[Workspace Cache Warning] Could not connect to Redis: {e}")
    redis_client = None


def get_cached_workspace_config(workspace_id: str) -> dict:
    """
    Fetch workspace configuration from Redis cache.
    On cache miss, fetch from Supabase 'workspace' table and cache for 300s (5 minutes).
    """
    cache_key = f"workspace_config:{workspace_id}"

    # 1. Check Redis Cache
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                print(f"[Workspace Cache] HIT for workspace: {workspace_id}")
                return json.loads(cached)
        except Exception as err:
            print(f"[Workspace Cache Warning] Redis get error: {err}")

    # 2. Cache Miss: Query Supabase
    print(f"[Workspace Cache] MISS for workspace: {workspace_id}. Querying database...")
    res = supabase.table("workspace").select(
        "temperature, model_name, provider, system_prompt, search_enabled, chunk_size, chunk_overlap, similarity_threshold"
    ).eq("id", workspace_id).execute()

    if not res.data:
        raise Exception(f"Workspace with id {workspace_id} not found.")

    workspace_data = res.data[0]

    # 3. Write to Redis with 5-minute TTL
    if redis_client:
        try:
            redis_client.setex(cache_key, 300, json.dumps(workspace_data))
            print(f"[Workspace Cache] SETEX successful for workspace: {workspace_id}")
        except Exception as err:
            print(f"[Workspace Cache Warning] Redis setex error: {err}")

    return workspace_data


def invalidate_workspace_cache(workspace_id: str) -> bool:
    """
    Purges cached workspace configuration from Redis.
    """
    cache_key = f"workspace_config:{workspace_id}"
    if redis_client:
        try:
            redis_client.delete(cache_key)
            print(f"[Workspace Cache] INVALIDATED cache for workspace: {workspace_id}")
            return True
        except Exception as err:
            print(f"[Workspace Cache Warning] Redis delete error: {err}")
            return False
    return False
