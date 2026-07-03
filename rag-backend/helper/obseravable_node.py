from datetime import datetime, timezone
from functools import wraps
import time
from langchain_core.messages import AIMessage


def observable_node(node_name):

    def decorator(func):

        @wraps(func)
        def wrapper(state, config):

            start = time.time()

            start_event = {
                "node": node_name,
                "event": "started",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            try:
                result = func(state, config)

                duration = int((time.time() - start) * 1000)

                end_event = {
                    "node": node_name,
                    "event": "finished",
                    "duration_ms": duration,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

                node_trajectory = result.get("trajectory", [])
                final_result = {k: v for k, v in result.items() if k != "trajectory"}

                return {
                    **final_result,
                    "trajectory": [
                        start_event,
                        *node_trajectory,
                        end_event
                    ],
                    "error_messages": [{"node": node_name, "type": None, "message": None}]
                }

            except Exception as e:

                duration = int((time.time() - start) * 1000)

                error_event = {
                    "node": node_name,
                    "event": "failed",
                    "duration_ms": duration,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

                return {
                    "trajectory": [
                        start_event,
                        error_event
                    ],

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