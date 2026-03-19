"""Gemini API adapter for Vertex AI with function calling support."""

import json
import time
import traceback
from typing import Optional

from google import genai
from google.genai import types
from rich.console import Console

from ..core.code_reader import CodeReader
from ..core.cost_tracker import CostTracker

console = Console()

# Maximum function calls per single generation request
MAX_FUNCTION_CALLS = 15

# Retry config
MAX_RETRIES = 5
RETRY_BACKOFF_BASE = 2  # seconds


def _build_function_tools() -> list[types.FunctionDeclaration]:
    """Build the function calling tool declarations for code access."""
    return [
        types.FunctionDeclaration(
            name="read_file",
            description=(
                "Read a source file from the codebase to verify a design detail. "
                "Use paths relative to the analysis scope (e.g., 'src/main.py'). "
                "To read files outside the scope (shared libraries, root configs), "
                "prefix with ~/ (e.g., '~/shared/auth/jwt.py')."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(type="STRING", description="File path"),
                },
                required=["path"],
            ),
        ),
        types.FunctionDeclaration(
            name="search_code",
            description=(
                "Search the codebase for a pattern (regex supported). "
                "Set scope_only=false to search the entire repo including shared code."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "pattern": types.Schema(type="STRING", description="Search pattern"),
                    "file_glob": types.Schema(type="STRING", description="e.g., '*.py'"),
                    "scope_only": types.Schema(type="BOOLEAN", description="true=scope only"),
                },
                required=["pattern"],
            ),
        ),
        types.FunctionDeclaration(
            name="read_file_full",
            description=(
                "Read the complete content of a large file. "
                "Use only when read_file returned a truncated summary."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(type="STRING", description="File path"),
                },
                required=["path"],
            ),
        ),
    ]


def _execute_function_call(
    function_name: str, function_args: dict, code_reader: CodeReader
) -> str:
    """Execute a function call from the LLM and return the result."""
    try:
        if function_name == "read_file":
            return code_reader.read_file(function_args["path"])
        elif function_name == "search_code":
            return code_reader.search_to_string(
                pattern=function_args["pattern"],
                file_glob=function_args.get("file_glob", "*"),
                scope_only=function_args.get("scope_only", True),
            )
        elif function_name == "read_file_full":
            return code_reader.read_file_full(function_args["path"])
        else:
            return f"Unknown function: {function_name}"
    except Exception as e:
        return f"Error executing {function_name}: {e}"


class GeminiAdapter:
    """Wrapper around Google GenAI SDK for Vertex AI Gemini."""

    def __init__(
        self,
        model: str = "gemini-2.5-pro",
        cost_tracker: Optional[CostTracker] = None,
        verbose: bool = False,
    ):
        self.model = model
        self.cost_tracker = cost_tracker
        self.verbose = verbose
        self.client = genai.Client()

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        code_reader: Optional[CodeReader] = None,
        enable_function_calling: bool = False,
        phase: str = "phase1",
    ) -> str:
        """
        Generate a response from Gemini.

        If enable_function_calling=True and code_reader is provided,
        the LLM can call read_file/search_code/read_file_full to access code.
        Function calls are executed locally and results fed back automatically.
        """
        # Build config
        tools = None
        if enable_function_calling and code_reader:
            tools = [types.Tool(function_declarations=_build_function_tools())]

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,  # Low temperature for factual/analytical tasks
            tools=tools,
        )

        # Initial message
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=user_message)])]

        # Agentic function-calling loop (separate from retry logic)
        function_call_count = 0

        while function_call_count <= MAX_FUNCTION_CALLS:
            # Inner retry loop for transient API errors only
            response = None
            for attempt in range(MAX_RETRIES):
                try:
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=contents,
                        config=config,
                    )
                    break  # Success — exit retry loop

                except Exception as e:
                    error_str = str(e)

                    # Rate limit
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        wait = RETRY_BACKOFF_BASE ** (attempt + 1)
                        console.print(f"[yellow]Rate limited. Waiting {wait}s...[/yellow]")
                        time.sleep(wait)
                        continue

                    # Server overloaded
                    if "503" in error_str or "UNAVAILABLE" in error_str:
                        console.print("[yellow]Model overloaded. Waiting 60s...[/yellow]")
                        time.sleep(60)
                        continue

                    # Other transient errors
                    if attempt < MAX_RETRIES - 1:
                        console.print(f"[yellow]API error (attempt {attempt + 1}): {error_str[:200]}[/yellow]")
                        time.sleep(RETRY_BACKOFF_BASE ** attempt)
                        continue

                    # Final attempt failed
                    console.print(f"[red]API error after {MAX_RETRIES} attempts: {error_str[:500]}[/red]")
                    if self.verbose:
                        traceback.print_exc()
                    raise

            if response is None:
                raise RuntimeError("Max retries exceeded")

            # Track tokens
            if self.cost_tracker and response.usage_metadata:
                self.cost_tracker.record_call(
                    phase=phase,
                    input_tokens=response.usage_metadata.prompt_token_count or 0,
                    output_tokens=response.usage_metadata.candidates_token_count or 0,
                )
                self.cost_tracker.check_limits()
                self.cost_tracker.warn_if_approaching()

            # Check for function calls in the response
            if response.candidates and response.candidates[0].content:
                parts = response.candidates[0].content.parts

                # Collect all function calls from the response
                function_calls = [p for p in parts if p.function_call]

                if function_calls and code_reader and function_call_count < MAX_FUNCTION_CALLS:
                    # Add assistant's response to conversation
                    contents.append(response.candidates[0].content)

                    # Execute each function call and build response
                    function_response_parts = []
                    for fc_part in function_calls:
                        fc = fc_part.function_call
                        function_call_count += 1

                        if self.verbose:
                            console.print(f"  [dim]→ {fc.name}({json.dumps(dict(fc.args), ensure_ascii=False)[:100]})[/dim]")

                        result = _execute_function_call(fc.name, dict(fc.args), code_reader)

                        function_response_parts.append(
                            types.Part.from_function_response(
                                name=fc.name,
                                response={"result": result},
                            )
                        )

                    # Add function results and continue the agentic loop
                    contents.append(
                        types.Content(role="user", parts=function_response_parts)
                    )
                    continue  # Continue while loop for next LLM turn

            # No function calls (or limit reached) — extract text response
            return self._extract_text(response)

        raise RuntimeError("Max function calls exceeded")

    def generate_json(
        self,
        system_prompt: str,
        user_message: str,
        code_reader: Optional[CodeReader] = None,
        enable_function_calling: bool = False,
        phase: str = "phase1",
    ) -> dict:
        """Generate and parse JSON response. Retries if JSON is invalid."""
        for attempt in range(3):
            raw = self.generate(
                system_prompt=system_prompt,
                user_message=user_message,
                code_reader=code_reader,
                enable_function_calling=enable_function_calling,
                phase=phase,
            )

            # Try to extract JSON from the response
            parsed = self._try_parse_json(raw)
            if parsed is not None:
                return parsed

            if attempt < 2:
                console.print("[yellow]Invalid JSON response, retrying with stricter instructions...[/yellow]")
                user_message = (
                    user_message + "\n\nIMPORTANT: Your previous response was not valid JSON. "
                    "Please respond with ONLY a JSON object, no markdown fences, no preamble."
                )

        # Return raw text wrapped in a basic structure
        console.print("[yellow]Could not parse JSON after 3 attempts. Using raw text.[/yellow]")
        return {"raw_text": raw}

    def _extract_text(self, response) -> str:
        """Extract text content from a Gemini response."""
        if not response.candidates:
            return ""

        parts = response.candidates[0].content.parts
        text_parts = [p.text for p in parts if hasattr(p, "text") and p.text]
        return "\n".join(text_parts)

    def _try_parse_json(self, text: str) -> Optional[dict]:
        """Try to parse JSON from LLM response, handling common issues."""
        text = text.strip()

        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (fences)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in the text
        start = text.find("{")
        if start == -1:
            return None

        # Find matching closing brace
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        return None

        return None
