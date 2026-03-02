from google.adk.agents import Agent

from soda_agent.tools.messaging_tools import read_messages, send_message

messaging_agent = Agent(
    name="messaging_agent",
    model="gemini-2.5-flash",
    description="Handles text messages and contacts. "
    "Use this agent for reading messages, sending texts, and contact lookups.",
    instruction="""You are the messaging specialist for Soda, a car voice assistant.
Read messages aloud naturally, mentioning who sent them and when.
When sending messages, always confirm the recipient and content before sending.
Keep responses brief and clear.""",
    tools=[read_messages, send_message],
)
