from datetime import datetime, timezone
from functools import wraps
import time
from langchain_core.messages import AIMessage


def observable_node(node_name):

    def decorator(func):

        @wraps(func)
        def wrapper(state, config):
            start = time.time()
            start_iso = datetime.now(timezone.utc).isoformat()

            try:
                result = func(state, config)
                duration = int((time.time() - start) * 1000)
                
                token_usage = None
                
                # Check for token usage in either node_output or messages
                candidates = []
                if isinstance(result, dict):
                    if "node_output" in result and result["node_output"]:
                        candidates.append(result["node_output"][-1])
                    if "messages" in result and result["messages"]:
                        candidates.append(result["messages"][-1])
                
                for candidate in candidates:
                    # 1. Check for LangChain's standard usage_metadata
                    if hasattr(candidate, "usage_metadata") and candidate.usage_metadata:
                        token_usage = candidate.usage_metadata 
                        break
                    # 2. Fallback to response_metadata for certain providers (like Groq/OpenAI)
                    elif hasattr(candidate, "response_metadata") and isinstance(candidate.response_metadata, dict):
                        token_usage = candidate.response_metadata.get("token_usage")
                        if token_usage:
                            break

                # Strip out any 'trajectory' manually appended by the node itself
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

            except Exception as e:
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
                        content=f"""
                        SYSTEM OBSERVATION:
                        Previous node failed.

                        Node: {node_name}
                        Error: {str(e)}

                        Choose another strategy.
                        """
                    )],
                    "error_messages": [{
                        "node": node_name,
                        "type": type(e).__name__,
                        "message": str(e)
                    }]
                }

        return wrapper

    return decorator