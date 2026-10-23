# Reel Match

A chat assistant that helps two people plan a movie date. It asks each person what genre they're in the mood for and where they are. It then searches the web for movies showing now at theaters near both of them and returns 3 picks as structured JSON: one in each person's genre, plus one that blends both. The browser renders them as cards.

Built with the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/), FastAPI and a vanilla JS frontend.

## Features

- **Guided two-person chat**: the assistant asks User 1 and then User 2 for a genre and a location, one question at a time. Replies stream into the chat as they're generated.
- **Live web search**: recommendations come from a web search for movies showing now near both locations. The current date is injected into the prompt, so results stay current.
- **Structured JSON output**: the final recommendations are validated against a Pydantic schema (`MovieRecommendations` in `app/agent.py`). The model is held to that schema, so the server receives typed data instead of free text to parse.
- **Recommendation cards**: the frontend renders each pick as a card with title, release date, genre, theater, address, showtimes and why it suits both people.
- **Agent handoff**: a conversational `Movie Date Agent` collects the answers, then hands off to a `Recommendation Agent` that searches and returns the structured result.
- **Event and tool panels**: the right-hand panes show the raw WebSocket events, web searches and agent handoffs as they happen.

## Structured output format

When the recommendations are ready, the server sends a single WebSocket message:

```json
{
  "type": "recommendations",
  "data": {
    "recommendations": [
      {
        "title": "Movie Title",
        "release_date": "Oct 10, 2026",
        "genre": "Comedy / Sci-fi",
        "theater_name": "AMC Example 12",
        "theater_address": "123 Main St, Brooklyn, NY",
        "showtimes": ["Fri 7:30 PM", "Sat 4:15 PM"],
        "reason": "Why it works for both of you"
      }
    ],
    "closing_message": "Enjoy your movie date!"
  }
}
```

Other messages the client receives:

| `type`                     | Meaning                                    |
| -------------------------- | ------------------------------------------ |
| `assistant_response_delta` | A streamed chunk of the assistant's reply  |
| `tool_start`               | The agent started a web search             |
| `handoff`                  | Control passed from one agent to another   |
| `response_complete`        | The assistant finished its turn            |

## Running locally

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and an `OPENAI_API_KEY` in your environment.

```bash
uv sync
```

```bash
cd app && uv run python server.py
```

Then open http://localhost:3000, click **Connect**, and answer the assistant's questions.

## Project layout

```
app/
  agent.py        # Agents, prompts and the MovieRecommendations schema
  server.py       # FastAPI app: WebSocket chat endpoint, /api/health, static files
  static/         # index.html + app.js frontend
k8s/              # EKS deployment (Deployment, Service, Ingress, cert-manager, AWS LB controller)
photos/           # UI wireframe
Dockerfile        # Production image (serves on port 3000)
```

## Deployment

The `Dockerfile` builds an image that runs `server.py` on port 3000. The manifests in `k8s/` deploy it to EKS behind an AWS Load Balancer with TLS from cert-manager. `/api/health` is used for readiness and liveness probes.
