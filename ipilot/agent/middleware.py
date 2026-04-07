from langchain.agents.middleware import dynamic_prompt

@dynamic_prompt
def build_system_prompt(request) -> str:
    ctx = request.runtime.context
    
    parts = [
        "You are iPilot.",
        f"Workspace: {ctx.workspace_path}",
        f"Provider: {ctx.provider}",
        f"Model: {ctx.model}",
    ]
    if ctx.channel:
        parts.append(f"Channel: {ctx.channel}")
    if ctx.chat_id:
        parts.append(f"Chat ID: {ctx.chat_id}")
    return "\n".join(parts)