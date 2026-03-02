"""Session management service."""

from google.adk.sessions import InMemorySessionService


def get_session_service():
    """Get the session service instance.

    MVP: InMemorySessionService for local development.
    Production: Switch to DatabaseSessionService with Firestore.
    """
    # TODO: Switch to Firestore for production
    # from google.adk.sessions import DatabaseSessionService
    # return DatabaseSessionService(db_url="firestore://soda-agent-sessions")
    return InMemorySessionService()


session_service = get_session_service()
