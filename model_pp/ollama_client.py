"""Talk to a local Ollama server (no extra packages needed).

    chat = make_chat("paisaplan")                    # prose (explanations)
    chat = make_chat("paisaplan", force_json=True)   # JSON (extraction)
"""
import json
import urllib.error
import urllib.request


def make_chat(model="paisaplan", host="http://localhost:11434", temperature=0.0,
              timeout=180, force_json=False):
    url = host.rstrip("/") + "/api/chat"

    def chat(messages):
        payload = {"model": model, "messages": messages, "stream": False,
                   "options": {"temperature": temperature}}
        if force_json:
            payload["format"] = "json"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))["message"]["content"]
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")
            raise RuntimeError(f"Ollama error {e.code}: {detail[:200]} "
                               f"(is the model '{model}' created? run `ollama list`)") from e
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            raise RuntimeError(f"Could not reach Ollama at {host}. Is it running? ({e})") from e

    return chat