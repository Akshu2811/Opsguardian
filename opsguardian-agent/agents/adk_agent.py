# agents/adk_agent.py
import os
import logging
from dotenv import load_dotenv

from google.adk.agents.base_agent import BaseAgent
from google.adk.events.event import Event
from google.genai import types as gen_types
from google.genai import Client as GenAIClient

# helpers from your runtime (avoid circular imports here)
from agents.adk_runtime import run_agent_async, create_runner_with_agent

load_dotenv()
LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Default model to use — change this to any model name from your list if desired
DEFAULT_GENAI_MODEL = os.getenv("GENAI_MODEL", "models/gemini-2.5-pro")
API_KEY = os.getenv("GOOGLE_API_KEY")


class AdkLlmAgent(BaseAgent):
    # Keep this annotated so Pydantic/base class rules are happy
    name: str = "adk_llm_agent"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure a Runner is created for this agent (idempotent)
        create_runner_with_agent(self, app_name="OpsGuardianAgentApp")

        # Lazy initialize GenAI client (so import/time-of-init doesn't explode)
        if not API_KEY:
            LOG.warning("GOOGLE_API_KEY not found in environment; GenAI calls will fail.")
        self._genai_client = None

    def _get_genai_client(self):
        if self._genai_client is None:
            if not API_KEY:
                raise RuntimeError("Missing GOOGLE_API_KEY in environment.")
            self._genai_client = GenAIClient(api_key=API_KEY)
        return self._genai_client

    async def run_async(self, ctx):
        """
        ctx.user_content is an ADK Content object; extract the first part text.
        Call the GenAI models.generate_content and yield an Event with the model text.
        """
        # extract incoming user text safely
        user_text = ""
        try:
            if ctx.user_content and getattr(ctx.user_content, "parts", None):
                p0 = ctx.user_content.parts[0]
                user_text = getattr(p0, "text", "") or ""
        except Exception:
            user_text = ""

        # If empty, nothing to do — return a helpful message
        if not user_text:
            out_text = "No input text provided."
            ev = Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=gen_types.Content(parts=[gen_types.Part(text=out_text)]),
            )
            yield ev
            return

        # Model name (can be overridden via env var GENAI_MODEL)
        model_name = DEFAULT_GENAI_MODEL

        try:
            client = self._get_genai_client()

            # Call models.generate_content — wrap user_text in list for 'contents'
            # (the shape expected by this client)
            resp = client.models.generate_content(model=model_name, contents=[user_text])

            # resp might be a complex object (Pager/candidate/outputs). Extract text robustly:
            output_text = None

            # Option 1: resp has 'candidates' attribute (older shapes)
            if hasattr(resp, "candidates") and resp.candidates:
                # candidate could be an object with 'content' or 'output' etc.
                cand = resp.candidates[0]
                # try common attributes
                output_text = getattr(cand, "content", None) or getattr(cand, "output", None) or None
                if isinstance(output_text, list):
                    # join parts if it's a list of content pieces
                    try:
                        output_text = "\n".join(str(p) for p in output_text)
                    except Exception:
                        output_text = str(output_text)

            # Option 2: resp has 'outputs' (newer shapes)
            if not output_text and hasattr(resp, "outputs") and resp.outputs:
                # outputs often contain items with a 'content' field (string or list)
                first_out = resp.outputs[0]
                output_text = getattr(first_out, "content", None) or getattr(first_out, "text", None)

                # If content is list/dict, try to extract text fields
                if isinstance(output_text, list):
                    # concatenate text-like entries
                    pieces = []
                    for item in output_text:
                        # item might be a dict-like with 'text' key
                        txt = None
                        if hasattr(item, "text"):
                            txt = getattr(item, "text")
                        elif isinstance(item, dict):
                            txt = item.get("text") or item.get("content")
                        else:
                            txt = str(item)
                        if txt:
                            pieces.append(str(txt))
                    output_text = "\n".join(pieces)

            # Option 3: resp has a top-level 'content' or 'output' attribute
            if not output_text and hasattr(resp, "content"):
                output_text = getattr(resp, "content")
                if isinstance(output_text, list):
                    output_text = "\n".join(str(x) for x in output_text)

            # Option 4: fallback to stringifying the response
            if not output_text:
                try:
                    output_text = str(resp)
                except Exception:
                    output_text = "GenAI response received but could not extract text."

            # final ensure it's a plain string
            if not isinstance(output_text, str):
                output_text = str(output_text)

            out_text = output_text.strip()

        except Exception as e:
            LOG.error("GenAI client call failed", exc_info=True)
            out_text = f"Error calling GenAI model: {e}"

        # Build ADK Event with gen_types.Content -> Part(text=str)
        try:
            content = gen_types.Content(parts=[gen_types.Part(text=out_text)])
        except Exception as e:
            # if constructing types fails for any reason, fall back to string content
            LOG.warning("ModelContent construction failed, falling back to plain str: %s", e)
            # some ADK versions expect ModelContent or Content with a different shape;
            # we'll ensure at least we return a Content with a string part.
            try:
                content = gen_types.Content(parts=[gen_types.Part(text=str(out_text))])
            except Exception:
                # ultimate fallback: send the raw string as Event.content (may or may not work)
                content = out_text

        ev = Event(invocation_id=ctx.invocation_id, author=self.name, content=content)
        yield ev
