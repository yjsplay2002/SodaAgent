from google.adk.agents import Agent

from soda_agent.tools.music_tools import pause_music, play_song, skip_track

music_agent = Agent(
    name="music_agent",
    model="gemini-2.5-flash",
    description="Controls music playback and discovery. "
    "Use this agent for playing songs, pausing, skipping, and music recommendations.",
    instruction="""You are the music specialist for Soda, a car voice assistant.
Handle music playback requests naturally.
Confirm what you're playing after starting music.
Keep responses very brief for music controls (pause, skip, etc.).""",
    tools=[play_song, pause_music, skip_track],
)
