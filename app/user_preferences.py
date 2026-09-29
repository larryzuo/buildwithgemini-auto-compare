# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""User car preferences management with Vertex AI Memory Bank."""

import logging
from typing import Any, Optional

from google.adk.memory.memory_entry import MemoryEntry
from google.adk.tools.tool_context import ToolContext
from google.genai import types

logger = logging.getLogger(__name__)


async def remember_car_preference(
    preference: str,
    category: Optional[str] = None,
    tool_context: Optional[ToolContext] = None,
) -> dict[str, Any]:
    """Persists a user vehicle preference to Vertex AI long-term Memory Bank.

    Call this tool whenever the user mentions a preference about vehicles, such as:
    - Powertrain or fuel type (EV, plug-in hybrid, hybrid, gas)
    - Budget limits or price range (e.g. under $60k, luxury tier)
    - Vehicle category or body style (SUV, sports sedan, coupe, truck)
    - Brand/manufacturer preferences or dislikes (e.g. loves BMW, dislikes Tesla)
    - Practical requirements (cargo space, trunk capacity, seating, towing)
    - Performance desires (horsepower, 0-60 acceleration, sporty handling)
    - Daily commute or charging setup (e.g. 40 miles daily commute, has home L2 charger)

    Args:
        preference: A clear, concise statement of the user's car preference.
        category: Optional category such as 'powertrain', 'budget', 'body_style', 'brand', 'practicality', or 'performance'.
        tool_context: ADK ToolContext injected automatically at runtime.

    Returns:
        A dictionary confirming the preference was recorded in long-term memory.
    """
    clean_pref = preference.strip()
    formatted = f"User car preference ({category}): {clean_pref}" if category else f"User car preference: {clean_pref}"

    entry = MemoryEntry(
        content=types.Content(
            parts=[types.Part.from_text(text=formatted)]
        ),
        custom_metadata={"category": category or "general", "type": "car_preference"},
    )

    if tool_context and hasattr(tool_context, "add_memory"):
        try:
            await tool_context.add_memory(memories=[entry])
            return {
                "status": "success",
                "message": f"Remembered user preference: {clean_pref}",
                "category": category,
            }
        except Exception as e:
            logger.warning(f"Could not save memory via tool_context: {e}")

    # Fallback directly via process-wide memory service
    try:
        from app.app_utils.services import get_memory_service

        svc = get_memory_service()
        await svc.add_memory(app_name="app", user_id="default_user", memories=[entry])
        return {
            "status": "success",
            "message": f"Remembered user preference: {clean_pref}",
            "category": category,
        }
    except Exception as e:
        logger.error(f"Error persisting memory entry: {e}")
        return {
            "status": "error",
            "message": f"Failed to save preference to Memory Bank: {e}",
        }


async def get_remembered_car_preferences(
    query: str = "car vehicle preferences budget powertrain",
    tool_context: Optional[ToolContext] = None,
) -> dict[str, Any]:
    """Retrieves remembered user vehicle preferences from Vertex AI Memory Bank.

    Use this tool when recommending cars or when the user asks what preferences
    are currently remembered.

    Args:
        query: Search query for relevant preferences (defaults to general car preferences).
        tool_context: ADK ToolContext injected automatically at runtime.

    Returns:
        A dictionary containing the list of remembered car preferences.
    """
    memories_found = []

    if tool_context and hasattr(tool_context, "search_memory"):
        try:
            res = await tool_context.search_memory(query=query)
            if res and res.memories:
                for m in res.memories:
                    if m.content and m.content.parts:
                        text = " ".join(p.text for p in m.content.parts if p.text)
                        if text:
                            memories_found.append(text)
        except Exception as e:
            logger.warning(f"Search memory via tool_context failed: {e}")

    if not memories_found:
        try:
            from app.app_utils.services import get_memory_service

            svc = get_memory_service()
            res = await svc.search_memory(app_name="app", user_id="default_user", query=query)
            if res and res.memories:
                for m in res.memories:
                    if m.content and m.content.parts:
                        text = " ".join(p.text for p in m.content.parts if p.text)
                        if text:
                            memories_found.append(text)
        except Exception as e:
            logger.error(f"Search memory via service failed: {e}")

    return {
        "status": "success",
        "preferences_count": len(memories_found),
        "preferences": memories_found,
    }
