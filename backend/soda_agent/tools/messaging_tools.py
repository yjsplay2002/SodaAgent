def read_messages(count: int = 5) -> dict:
    """Reads recent unread messages.

    Args:
        count: Number of recent messages to retrieve. Default is 5.

    Returns:
        A dictionary with recent messages.
    """
    return {
        "status": "success",
        "messages": [
            {
                "from": "Mom",
                "time": "10 minutes ago",
                "text": "Don't forget to pick up groceries on the way home!",
            },
            {
                "from": "Alex",
                "time": "30 minutes ago",
                "text": "Are we still meeting for dinner tonight?",
            },
        ],
        "unread_count": 2,
    }


def send_message(contact: str, message: str) -> dict:
    """Sends a text message to a contact.

    Args:
        contact: Name of the contact to send the message to.
        message: The message text to send.

    Returns:
        A dictionary confirming the message was sent.
    """
    return {
        "status": "success",
        "to": contact,
        "message": message,
        "confirmation": f"Message sent to {contact}: '{message}'",
    }
