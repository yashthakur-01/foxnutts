import json
import os
import redis
from supabase_client.client import supabase

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    print(f"[Cache Warning] Could not connect to Redis: {e}")
    redis_client = None


# ==========================================
# 1. WORKSPACE CONFIGURATION CACHING
# ==========================================

def get_cached_workspace_config(workspace_id: str) -> dict:
    """
    Fetch workspace configuration from Redis cache.
    On cache miss, fetch from Supabase 'workspace' table and cache for 300s (5 minutes).
    """
    cache_key = f"workspace_config:{workspace_id}"

    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                print(f"[Workspace Cache] HIT for workspace: {workspace_id}")
                return json.loads(cached)
        except Exception as err:
            print(f"[Workspace Cache Warning] Redis get error: {err}")

    print(f"[Workspace Cache] MISS for workspace: {workspace_id}. Querying database...")
    res = supabase.table("workspace").select(
        "temperature, model_name, provider, system_prompt, search_enabled, chunk_size, chunk_overlap, similarity_threshold"
    ).eq("id", workspace_id).execute()

    if not res.data:
        raise Exception(f"Workspace with id {workspace_id} not found.")

    workspace_data = res.data[0]

    if redis_client:
        try:
            redis_client.setex(cache_key, 300, json.dumps(workspace_data))
            print(f"[Workspace Cache] SETEX successful for workspace: {workspace_id}")
        except Exception as err:
            print(f"[Workspace Cache Warning] Redis setex error: {err}")

    return workspace_data


def invalidate_workspace_cache(workspace_id: str) -> bool:
    """Purges cached workspace configuration from Redis."""
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


# ==========================================
# 2. CHAT HISTORY CACHING
# ==========================================

def get_cached_chat_history(session_id: str, limit: int = 8) -> list[dict]:
    """
    Fetches the last N chat history messages from Redis list 'chat_history:{session_id}'.
    On cache miss, queries Supabase 'messages' table, populates Redis, and sets 3600s (1-hour) TTL.
    """
    cache_key = f"chat_history:{session_id}"

    if redis_client:
        try:
            cached_messages = redis_client.lrange(cache_key, -limit, -1)
            if cached_messages:
                print(f"[Chat History Cache] HIT for session: {session_id}")
                return [json.loads(msg) for msg in cached_messages]
        except Exception as err:
            print(f"[Chat History Cache Warning] Redis lrange error: {err}")

    print(f"[Chat History Cache] MISS for session: {session_id}. Querying Supabase...")
    res = supabase.table("messages") \
        .select("sender_type, content") \
        .eq("session_id", session_id) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()

    formatted_messages = []
    if res.data:
        # Sort in chronological order (oldest to newest)
        raw_msgs = list(reversed(res.data))
        for msg in raw_msgs:
            formatted_messages.append({
                "sender_type": msg.get("sender_type"),
                "content": msg.get("content")
            })

        # Populate Redis list and set 1-hour TTL
        if redis_client and formatted_messages:
            try:
                pipe = redis_client.pipeline()
                pipe.delete(cache_key)
                for item in formatted_messages:
                    pipe.rpush(cache_key, json.dumps(item))
                pipe.expire(cache_key, 3600)
                pipe.execute()
                print(f"[Chat History Cache] Populated Redis list for session: {session_id}")
            except Exception as err:
                print(f"[Chat History Cache Warning] Redis pipeline error: {err}")

    return formatted_messages


def append_chat_message_to_cache(session_id: str, sender_type: str, content: str):
    """
    Pushes a new user or AI chat message to the Redis list 'chat_history:{session_id}'.
    """
    cache_key = f"chat_history:{session_id}"
    if redis_client:
        try:
            item_json = json.dumps({"sender_type": sender_type, "content": content})
            pipe = redis_client.pipeline()
            pipe.rpush(cache_key, item_json)
            pipe.ltrim(cache_key, -20, -1)  # Keep last 20 messages max
            pipe.expire(cache_key, 3600)
            pipe.execute()
            print(f"[Chat History Cache] Appended '{sender_type}' message to session: {session_id}")
        except Exception as err:
            print(f"[Chat History Cache Warning] Failed to append message to Redis: {err}")


# ==========================================
# 3. OBSERVABILITY CACHE INVALIDATION
# ==========================================

def invalidate_observability_cache(workspace_id: str) -> bool:
    """
    Invalidates cached observability metrics & traces for a given workspace using O(1) Set tracking.
    """
    if redis_client:
        try:
            tracker_set_key = f"workspace_trace_keys:{workspace_id}"
            metrics_key = f"observability_metrics:{workspace_id}"
            
            # Fetch registered page keys from the workspace Set tracker
            registered_keys = list(redis_client.smembers(tracker_set_key))
            
            keys_to_delete = [metrics_key, tracker_set_key]
            if registered_keys:
                keys_to_delete.extend(registered_keys)
                
            redis_client.delete(*keys_to_delete)
            print(f"[Observability Cache] INVALIDATED {len(keys_to_delete)} keys via Set tracker for workspace: {workspace_id}")
            return True
        except Exception as err:
            print(f"[Observability Cache Warning] Invalidation failed: {err}")
            return False
    return False
