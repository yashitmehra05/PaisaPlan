"""Talk to a local Ollama server (no extra packages needed).

    chat = make_chat("paisaplan")          # the fine-tuned model
    chat = make_chat("llama3.2:3b")        # the untouched base model (for the baseline)
    reply_text = chat([{"role": "system", "content": "..."}, {"role": "user", "content": "..."}])

Ollama must be running (open the Ollama app, or run `ollama serve`).
"""
import json
import urllib.error
import urllib.request


def make_chat(model="paisaplan", host="http://localhost:11434", temperature=0.0, timeout=180):
    url = host.rstrip("/") + "/api/chat"

    def chat(messages):
        body = json.dumps({"model": model, "messages": messages, "stream": False,
                           "options": {"temperature": temperature}}).encode("utf-8")
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
