import hmac
import os
import time

import anthropic
from dotenv import load_dotenv
from flask import Flask, abort, request

load_dotenv()

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

AGENT_ID = os.environ["AGENT_ID"]
ENVIRONMENT_ID = os.environ["ENVIRONMENT_ID"]
API_TOKEN = os.environ["API_TOKEN"]


@app.route("/birds", methods=["POST"])
def birds():
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not hmac.compare_digest(token, API_TOKEN):
        abort(401)

    region = request.json.get("region")

    # Create session
    session = client.beta.sessions.create(
        agent=AGENT_ID,
        environment_id=ENVIRONMENT_ID,
        betas=["managed-agents-2026-04-01"],
    )

    # Send region code
    client.beta.sessions.events.send(
        session.id,
        events=[
            {"type": "user.message", "content": [{"type": "text", "text": region}]}
        ],
        betas=["managed-agents-2026-04-01"],
    )

    # Poll for response
    while True:
        events = client.beta.sessions.events.list(
            session.id, betas=["managed-agents-2026-04-01"]
        )
        for event in events.data:
            if event.type == "agent.message":
                return {"response": event.content[0].text}
        time.sleep(3)


if __name__ == "__main__":
    app.run(port=5000)
