from google.adk.agents import Agent

from soda_agent.tools.weather_tools import get_current_weather, get_forecast

weather_agent = Agent(
    name="weather_agent",
    model="gemini-2.5-flash",
    description="Handles weather information and forecasts. "
    "Use this agent for current weather, forecasts, and weather alerts.",
    instruction="""You are the weather specialist for Soda, a car voice assistant.
Provide weather information in a conversational, easy-to-understand way.
Mention driving-relevant conditions (rain, ice, fog, wind) proactively.
Keep responses brief.""",
    tools=[get_current_weather, get_forecast],
)
