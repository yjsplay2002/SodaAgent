from google.adk.agents import Agent

from soda_agent.tools.maps_tools import get_directions, get_eta, search_places

navigation_agent = Agent(
    name="navigation_agent",
    model="gemini-2.5-flash",
    description="Handles navigation, directions, ETA, and place search. "
    "Use this agent for driving directions, nearby places, traffic, and location queries.",
    instruction="""You are the navigation specialist for Soda, a car voice assistant.
Use the map tools to provide directions, find places, and estimate arrival times.
Give clear, spoken turn-by-turn style summaries.
Mention traffic conditions when relevant.
Keep responses brief and driver-friendly.""",
    tools=[get_directions, get_eta, search_places],
)
