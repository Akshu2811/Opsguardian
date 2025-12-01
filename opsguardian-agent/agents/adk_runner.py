# agents/adk_runner.py
import os
import asyncio
from dotenv import load_dotenv

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

# Import the minimal agent we just created
from agents.adk_agent import AdkLlmAgent

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing GOOGLE_API_KEY in .env")

# NOTE:
# We are *not* wiring model objects into Runner directly here.
# Instead we create a minimal ADK agent (AdkLlmAgent) which will call whichever
# model client you want. This keeps Runner happy (it needs app_name+agent).

session_service = InMemorySessionService()

# instantiate the agent and pass it to Runner
root_agent = AdkLlmAgent()

# Provide both app_name and agent — this satisfies Runner's validation.
runner = Runner(
    app_name="OpsGuardianAgentApp",
    agent=root_agent,
    session_service=session_service,
)

async def run_agent_async(agent_name: str, prompt: str) -> str:
    """
    Async wrapper that uses runner.run_debug to send a single prompt and
    return the final model text (best-effort).
    """
    # use run_debug helper — it creates/continues an in-memory session
    events = await runner.run_debug(prompt, quiet=True)
    # events is a list of Event objects; find last model authored event with text
    for ev in reversed(events):
        if ev.author == agent_name and ev.content:
            # try several shapes: content.parts[0].text or content.text or content.output_text
            parts = getattr(ev.content, "parts", None)
            if parts and len(parts) > 0:
                first = parts[0]
                txt = getattr(first, "text", None)
                if txt:
                    return txt
            # fallback fields
            txt = getattr(ev.content, "text", None) or getattr(ev.content, "output_text", None)
            if txt:
                return txt
    # if nothing found, stringify last event
    if events:
        return str(events[-1])
    return ""
