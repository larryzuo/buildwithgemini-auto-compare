# ruff: noqa
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

import datetime
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools.load_memory_tool import LoadMemoryTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from app.a2ui_utils import a2ui_callback
from app.car_images import fetch_and_store_car_images, generate_open_trunk_images, visualize_trunk_luggage
from app.cars_db import add_car, compare_cars, compare_running_costs, get_car_specs, search_cars
from app.nhtsa_api import decode_vin, lookup_manufacturer_models
from app.user_preferences import get_remembered_car_preferences, remember_car_preference

MODEL = "gemini-3.6-flash"


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


AGENT_INSTRUCTION = (
    "You are AutoCompare, an expert automotive comparison and research assistant. "
    "You help car buyers and enthusiasts research vehicle specifications, compare performance "
    "metrics (horsepower, torque, 0-60 mph, top speed, price, fuel economy), and discover "
    "cars in your catalog using your Firestore tools and public automotive data.\n\n"
    "Available capabilities:\n"
    "- search_cars: Search the internal Firestore vehicle catalog by keywords, price ceiling, body style, or fuel type.\n"
    "- get_car_specs: Retrieve in-depth specifications for any specific car in the catalog.\n"
    "- compare_cars: Provide side-by-side comparative analysis of multiple cars.\n"
    "- compare_running_costs: Compare annual and 5-year fuel/energy operating costs between vehicles.\n"
    "- add_car: Add a new vehicle to the Firestore catalog when the user provides specs.\n"
    "- decode_vin: Decode any 17-character VIN using the US NHTSA government API to get factory specs and build details.\n"
    "- lookup_manufacturer_models: Look up official vehicle models produced by any manufacturer from the NHTSA database.\n"
    "- fetch_and_store_car_images: Fetch studio photos (front-angled ¾, rear-angled ¾, and cargo/trunk views) for a car from carimagesapi.com and store them in Cloud Storage.\n"
    "- generate_open_trunk_images: Generate open trunk/cargo photos (both empty and packed with luggage) with watermarks removed, saving to artifacts and Cloud Storage.\n"
    "- visualize_trunk_luggage: Generate an example luggage visualization image for a vehicle's trunk space using the vehicle's rear photo and gemini-3.1-flash-lite-image, saving it to artifacts and uploading to public Cloud Storage.\n"
    "- remember_car_preference: Explicitly save a user vehicle preference (powertrain, budget, body style, brand affinity, cargo needs, performance) to long-term Vertex AI Memory Bank.\n"
    "- get_remembered_car_preferences: Query and inspect remembered vehicle preferences stored for the user.\n"
    "- load_memory: Search the user's long-term memory bank on demand.\n\n"
    "MEMORY & USER PREFERENCES:\n"
    "- You have long-term cross-session memory powered by Vertex AI Memory Bank.\n"
    "- Proactively remember the user's car preferences across conversations, including:\n"
    "  * Preferred vehicle types / body styles (SUV, sports sedan, coupe, truck, hatchback).\n"
    "  * Powertrain / fuel preferences (EV, plug-in hybrid, hybrid, gas).\n"
    "  * Budget limits, maximum price, and running cost priorities.\n"
    "  * Brand / manufacturer affinities and dislikes.\n"
    "  * Performance priorities (horsepower, 0-60 acceleration, sporty handling).\n"
    "  * Practical needs (cargo space, trunk capacity, seating capacity, towing).\n"
    "- Whenever the user expresses or updates a car preference, invoke remember_car_preference to persist it.\n"
    "- Always check and honor remembered user preferences when searching, comparing, or recommending vehicles.\n"
    "Ground your vehicle specifications and comparisons in your Firestore catalog or NHTSA data."
)


_schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

A2UI_INSTRUCTION = _schema_manager.generate_system_prompt(
    role_description=AGENT_INSTRUCTION,
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property (\'h1\', \'h2\', \'body\') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or \'kind\'/\'data\'/\'metadata\' objects."
    ),
    include_schema=True,
    include_examples=True,
)


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    inv_ctx = getattr(callback_context, "_invocation_context", None)
    if inv_ctx is not None and getattr(inv_ctx, "memory_service", None) is None:
        return None
    try:
        await callback_context.add_session_to_memory()
    except ValueError as e:
        if "memory service is not available" not in str(e):
            raise
    return None


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=A2UI_INSTRUCTION,
    tools=[
        PreloadMemoryTool(),
        LoadMemoryTool(),
        search_cars,
        get_car_specs,
        compare_cars,
        compare_running_costs,
        add_car,
        decode_vin,
        lookup_manufacturer_models,
        fetch_and_store_car_images,
        generate_open_trunk_images,
        visualize_trunk_luggage,
        remember_car_preference,
        get_remembered_car_preferences,
        get_weather,
        get_current_time,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
