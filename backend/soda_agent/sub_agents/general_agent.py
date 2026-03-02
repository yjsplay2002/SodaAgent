from google.adk.agents import Agent
from google.adk.tools import google_search

from soda_agent.tools.vehicle_tools import get_vehicle_status

general_agent = Agent(
    name="general_agent",
    model="gemini-2.5-flash",
    description="Handles general knowledge questions, vehicle status, and miscellaneous requests. "
    "Use this agent for anything not covered by other specialists.",
    instruction="""You are the general assistant for Soda, a car voice assistant.
Answer general knowledge questions concisely.
Use Google Search when you need current information.
Provide vehicle status when asked about the car.
Keep all responses brief - the user is driving.""",
    tools=[google_search, get_vehicle_status],
)
