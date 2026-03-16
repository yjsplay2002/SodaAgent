from google.adk.agents import Agent

from soda_agent.tools.todo_tools import (
    add_todo,
    get_todo,
    get_todo_history,
    list_todos,
    search_todos,
    update_todo_status,
)

todo_agent = Agent(
    name="todo_agent",
    model="gemini-2.5-flash",
    description="Handles todo planning, classification, lookup, progress tracking, and history.",
    instruction="""You are the todo specialist for Soda.
Manage the user's todos and keep your answers concise.
When the user wants to add a todo, classify it with a sensible priority and category.
Use add_todo to save the todo.
Use list_todos or search_todos when the user asks about existing tasks.
Use get_todo for one task's current details.
Use get_todo_history when the user asks what happened with a specific todo over time.
Use update_todo_status when the user says a task moved to todo, in_progress, review, or done.
The allowed statuses are exactly: todo, in_progress, review, done.
If the user refers to a task vaguely, search before answering.
Keep responses brief and spoken-language friendly.""",
    tools=[
        add_todo,
        list_todos,
        search_todos,
        get_todo,
        update_todo_status,
        get_todo_history,
    ],
)
