Copyfrom flask import Flask, request
import anthropic
import time
import os

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

AGENT_ID = "agent_011CZrxQ99Bh7qLNBAng3JUm"
ENVIRONMENT_ID = "env_0115RJrQgSLY7GsNwuNNxDy7"

@app.route("/birds", methods=["POST"])
def birds():
    region = request.json.get("region")
    
    # Create session
    session = client.beta.sessions.create(
        agent=AGENT_ID,
        environment_id=ENVIRONMENT_ID,
        betas=["managed-agents-2026-04-01"]
    )
    
    # Send region code
    client.beta.sessions.events.send(
        session.id,
        events=[{"type": "user.message", "content": [{"type": "text", "text": region}]}],
        betas=["managed-agents-2026-04-01"]
    )
    
    # Poll for response
    while True:
        events = client.beta.sessions.events.list(session.id, betas=["managed-agents-2026-04-01"])
        for event in events.data:
            if event.type == "agent.message":
                return {"response": event.content[0].text}
        time.sleep(3)

if __name__ == "__main__":
    app.run(port=5000)
