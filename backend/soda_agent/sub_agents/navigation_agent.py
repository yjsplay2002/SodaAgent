from google.adk.agents import Agent

from soda_agent.tools.maps_tools import (
    get_directions,
    get_eta,
    get_eta_from_query,
    search_places,
)

navigation_agent = Agent(
    name="navigation_agent",
    model="gemini-2.5-flash",
    description="Handles navigation, directions, ETA, and place search. "
    "Use this agent for driving directions, nearby places, traffic, and location queries.",
    instruction="""You are the navigation specialist for Soda, a car voice assistant.
Use the map tools to provide directions, find places, and estimate arrival times.
For travel-time questions like "서울에서 부산까지 얼마나 걸려?" or
"How long from Seoul to Busan?", call get_eta_from_query right away.
Do not answer travel times from memory when a map tool can be used.
Give clear, spoken turn-by-turn style summaries.
Mention traffic conditions when relevant.
Keep responses brief and driver-friendly.""",
    tools=[get_directions, get_eta, get_eta_from_query, search_places],
)
