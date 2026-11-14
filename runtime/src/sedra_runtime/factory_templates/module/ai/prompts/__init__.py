"""Prompt Templates.

Reusable prompt templates for AI interactions.
"""
PROMPT_TEMPLATES = {
    "system": "You are a helpful assistant for MODULE_NAME.",
    "user_task": "Task: {task}\nContext: {context}\nProvide a clear, structured response.",
}

def get_prompt(name: str, **kwargs) -> str:
    """Get rendered prompt by name."""
    template = PROMPT_TEMPLATES.get(name, "")
    return template.format(**kwargs)