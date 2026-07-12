from storage.templates import save_template, delete_template, list_templates

SAVE_TEMPLATE_TOOL = {
    "name": "save_template",
    "description": (
        "Save (or overwrite) a reusable email template by name. Use {placeholders} in "
        "the subject or body for parts that change per recipient, e.g. {name} or "
        "{company}. Call this when the user gives you a template to remember."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Short unique template name, e.g. 'networking'."},
            "subject": {"type": "string", "description": "Subject line, may contain {placeholders}."},
            "body": {"type": "string", "description": "Body text, may contain {placeholders}."},
        },
        "required": ["name", "subject", "body"],
    },
}

DELETE_TEMPLATE_TOOL = {
    "name": "delete_template",
    "description": "Delete a saved email template by its exact name.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Exact name of the template to delete."},
        },
        "required": ["name"],
    },
}


def handle_save_template(name: str, subject: str, body: str) -> str:
    save_template(name, subject, body)
    return f'Template "{name}" saved.'


def handle_delete_template(name: str) -> str:
    if delete_template(name):
        return f'Template "{name}" deleted.'
    return f'No template named "{name}" found.'
