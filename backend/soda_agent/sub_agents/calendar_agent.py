from google.adk.agents import Agent

from soda_agent.tools.calendar_tools import (
    create_event,
    get_free_slots,
    get_upcoming_events,
)

calendar_agent = Agent(
    name="calendar_agent",
    model="gemini-2.5-flash",
    description="Handles calendar queries, scheduling, and reminders. "
    "Use this agent for questions about meetings, events, schedule, and availability.",
    instruction="""You are the calendar specialist for Soda, a car voice assistant.
Use the calendar tools to answer questions about the user's schedule.
Always confirm before creating or modifying events.
Format times in a natural spoken way (e.g., 'three thirty PM' not '15:30').
Keep responses brief - the user is driving.""",
    tools=[get_upcoming_events, create_event, get_free_slots],
)
