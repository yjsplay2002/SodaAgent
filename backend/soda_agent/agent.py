from google.adk.agents import Agent
from google.adk.tools import google_search

from soda_agent.prompts import ROOT_INSTRUCTION
from soda_agent.sub_agents.calendar_agent import calendar_agent
from soda_agent.sub_agents.general_agent import general_agent
from soda_agent.sub_agents.messaging_agent import messaging_agent
from soda_agent.sub_agents.music_agent import music_agent
from soda_agent.sub_agents.navigation_agent import navigation_agent
from soda_agent.sub_agents.weather_agent import weather_agent

from soda_agent.tools.calendar_tools import get_upcoming_events, create_event, get_free_slots
from soda_agent.tools.maps_tools import (
    get_directions,
    get_eta,
    get_eta_from_query,
    search_places,
)
from soda_agent.tools.weather_tools import get_current_weather, get_forecast
from soda_agent.tools.music_tools import play_song, pause_music, skip_track
from soda_agent.tools.messaging_tools import read_messages, send_message
from soda_agent.tools.vehicle_tools import get_vehicle_status

# Text mode (adk web, Runner.run_async): gemini-2.5-pro with sub-agents
# Live audio mode (ws_mobile.py): native-audio-preview with flat tools (no sub-agents)

LIVE_MODEL = "gemini-live-2.5-flash-native-audio"
TEXT_MODEL = "gemini-2.5-pro"

# Text mode: multi-agent with delegation
root_agent = Agent(
    name="soda_agent",
    model=TEXT_MODEL,
    description="Soda - your all-in-one car voice assistant",
    instruction=ROOT_INSTRUCTION,
    sub_agents=[
        calendar_agent,
        navigation_agent,
        weather_agent,
        music_agent,
        messaging_agent,
        general_agent,
    ],
)

LIVE_INSTRUCTION = """You are Soda, a friendly and efficient car voice assistant.
You help drivers stay safe, informed, and entertained while driving.

PERSONALITY:
- Warm, conversational, but concise (driver is focused on the road)
- Proactive when safety-relevant (weather warnings, traffic changes)
- Never ask more than one question at a time
- Keep responses under 2 sentences unless the user asks for detail
- Use natural spoken language, not written format
- ALWAYS respond in the same language the user spoke. If they speak Korean, reply in Korean. If English, reply in English. Never repeat the same response in a different language.
- Use the user's current location for weather when available; otherwise ask for the city before calling weather tools.
- For weather, report temperatures in Celsius only.
- For travel-time questions like "서울에서 부산까지 얼마나 걸려?" or "How long from Seoul to Busan?", call `get_eta_from_query` immediately instead of answering from memory.
- If the user gives both origin and destination, do not ask a follow-up question before using a navigation tool.

YOU HAVE THESE TOOLS - use them when the user asks about:
- Calendar/scheduling: get_upcoming_events, create_event, get_free_slots
- Navigation/directions: get_directions, get_eta, get_eta_from_query, search_places
- Weather: get_current_weather, get_forecast
- Music: play_song, pause_music, skip_track
- Messages: read_messages, send_message
- Vehicle: get_vehicle_status
- General knowledge: google_search

SAFETY:
- Prioritize urgent information (traffic, weather alerts)
- If user seems distracted or stressed, keep responses ultra-brief
- Never provide content that requires reading while driving
"""

# Live mode: flat agent with all tools (no sub-agents, no transfer_to_agent)
live_agent = Agent(
    name="soda_live_agent",
    model=LIVE_MODEL,
    description="Soda live voice agent with all tools",
    instruction=LIVE_INSTRUCTION,
    tools=[
        get_upcoming_events, create_event, get_free_slots,
        get_directions, get_eta, get_eta_from_query, search_places,
        get_current_weather, get_forecast,
        play_song, pause_music, skip_track,
        read_messages, send_message,
        get_vehicle_status,
        google_search,
    ],
)
