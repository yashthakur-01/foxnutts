import inspect
from datetime import datetime, timezone
from functools import wraps
import time
from langchain_core.messages import AIMessage


def observable_node(node_name):

    def decorator(func):
        is_async = inspect.iscoroutinefunction(func)
        
        def process_result(result, start, start_iso):
            duration = int((time.time() - start) * 1000)
            token_usage = None
            
            candidates = []
            if isinstance(result, dict):
                if "node_output" in result and result["node_output"]:
                    candidates.append(result["node_output"][-1])
                if "messages" in result and result["messages"]:
                    candidates.append(result["messages"][-1])
            
            for candidate in candidates:
                if hasattr(candidate, "usage_metadata") and candidate.usage_metadata:
                    token_usage = candidate.usage_metadata 
                    break
                elif hasattr(candidate, "response_metadata") and isinstance(candidate.response_metadata, dict):
                    token_usage = candidate.response_metadata.get("token_usage")
                    if token_usage:
                        break

            final_result = {k: v for k, v in result.items() if k != "trajectory"}

            trajectory_event = {
                "node": node_name,
                "start_time": start_iso,
                "end_time": datetime.now(timezone.utc).isoformat(),
                "duration_ms": duration,
                "tokens": token_usage,
                "node_output": final_result.get("node_output", [None])[0] if final_result.get("node_output") else None
            }

            return {
                **final_result,
                "trajectory": [trajectory_event],
                "error_messages": [{"node": node_name, "type": None, "message": None}]
            }
            
        def process_error(e, start, start_iso):
            duration = int((time.time() - start) * 1000)
            error_event = {
                "node": node_name,
                "start_time": start_iso,
                "end_time": datetime.now(timezone.utc).isoformat(),
                "duration_ms": duration,
                "error": str(e)
            }
            return {
                "trajectory": [error_event],
                "messages": [AIMessage(
                    content=f"SYSTEM OBSERVATION:\nPrevious node failed.\nNode: {node_name}\nError: {str(e)}\nChoose another strategy."
                )],
                "error_messages": [{
                    "node": node_name,
                    "type": type(e).__name__,
                    "message": str(e)
                }]
            }

        if is_async:
            @wraps(func)
            async def async_wrapper(state, config):
                start = time.time()
                start_iso = datetime.now(timezone.utc).isoformat()
                try:
                    result = await func(state, config)
                    return process_result(result, start, start_iso)
                except Exception as e:
                    return process_error(e, start, start_iso)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(state, config):
                start = time.time()
                start_iso = datetime.now(timezone.utc).isoformat()
                try:
                    result = func(state, config)
                    return process_result(result, start, start_iso)
                except Exception as e:
                    return process_error(e, start, start_iso)
            return sync_wrapper

    return decorator