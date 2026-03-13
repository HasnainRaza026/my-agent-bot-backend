# backend/me_worker.py
import os
import json
from pypdf import PdfReader
from dotenv import load_dotenv
from openai import OpenAI  # same as your sample
import requests

load_dotenv(override=True)


# --- tools ---
def push(text, filename):
    """Append text to the specified file in the records directory."""
    filepath = os.path.join("records", filename)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(text + "\n")
    return {"recorded": "ok"}


def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"Recording {name} with email {email} and notes {notes}", "info.txt")
    return {"recorded": "ok"}


def record_unknown_question(question):
    push(f"Recording unknown question: {question}", "unknown.txt")
    return {"recorded": "ok"}


# Tool metadata used by the model
record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string"},
            "name": {"type": "string"},
            "notes": {"type": "string"},
        },
        "required": ["email"],
        "additionalProperties": False,
    },
}
record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Use this tool to record a question that the agent was not able to answer based on the provided context.",
    "parameters": {
        "type": "object",
        "properties": {"question": {"type": "string"}},
        "required": ["question"],
        "additionalProperties": False,
    },
}
tools = [
    {"type": "function", "function": record_user_details_json},
    {"type": "function", "function": record_unknown_question_json},
]


# --- helper: truncate text safely ---
def truncate_text(text, max_chars=4000):
    if len(text) <= max_chars:
        return text
    # keep head + tail for context
    head = text[: max_chars // 2]
    tail = text[-(max_chars // 2) :]
    return head + "\n\n...TRUNCATED...\n\n" + tail


class Me:
    def __init__(self):
        self.gemini = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        self.name = os.getenv("ME_NAME", "Me")
        # read summary
        summary_path = os.path.join("me", "summary.md")
        self.summary = ""
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                self.summary = f.read()
        # read linkedin pdf (concatenate pages)
        self.linkedin = ""
        linkedin_path = os.path.join("me", "linkedin.pdf")
        if os.path.exists(linkedin_path):
            reader = PdfReader(linkedin_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    self.linkedin += text + "\n\n"
        # combine and truncate to avoid huge prompts
        combined = f"## Summary:\n{self.summary}\n\n## LinkedIn:\n{self.linkedin}"
        self.context = truncate_text(combined, max_chars=5000)

    def system_prompt(self):
        system_prompt = (
            f"You are acting as {self.name}. Answer questions on {self.name}'s website "
            "about career, background, skills and experience. Use the facts in the context below; do not invent facts. "
            "IMPORTANT: Never share personal contact information such as phone numbers, home addresses, or any other private details. "
            "You may only share email addresses if asked for contact information, provide this email address if asked hasnainraz@gmail.com. "
            "If you don't know the answer, call the 'record_unknown_question' tool to record it and respond briefly that you don't have the information."
            f"\n\n{self.context}"
        )
        return system_prompt

    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name} with {args}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**args) if tool else {}
            results.append(
                {
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tool_call.id,
                }
            )
        return results

    def chat(self, message, history):
        messages = [{"role": "system", "content": self.system_prompt()}]
        # history: expected as [{"role":"user"/"assistant","content": "..."}]
        messages.extend(history[-8:])  # last 8 messages to control prompt size
        messages.append({"role": "user", "content": message})
        done = False
        while not done:
            response = self.gemini.chat.completions.create(
                model="gemini-3.1-flash-lite-preview", messages=messages, tools=tools
            )
            if response.choices[0].finish_reason == "tool_calls":
                message_obj = response.choices[0].message
                tool_calls = message_obj.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message_obj)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content
