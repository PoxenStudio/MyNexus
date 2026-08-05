"""Replay a captured LLM call for debugging, from the request file written
by util/debug_log.py when config.yaml's debug.llm_logging ("打开调试日志" in
the system settings page) is on:

    <tempdir>/mynexus-llm-debug/<timestamp>-<id>.request.json

Re-sends the exact same messages to the exact same provider/base_url/model
and streams the reply to stdout, so a bad or unexpected summarization/chat
response can be reproduced and iterated on outside a full task run. Not part
of the app — run standalone from worker/src (needs the same PYTHONPATH as
the worker process):

    cd worker/src
    python3 ../tests/replay_llm_debug.py /tmp/mynexus-llm-debug/20260805-153000-a1b2c3d4.request.json

Pass --api-key to override the key (the request file never contains one —
see debug_log.py's docstring), or set MYNEXUS_LLM_OPENAI_API_KEY. --base-url
and --model likewise override the captured values, e.g. to try the same
prompt against a different model.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nodes.llm.ollama_llm import OllamaLLM  # noqa: E402
from nodes.llm.openai_llm import OpenAILLM  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("request_file", help="path to a *.request.json written by util/debug_log.py")
    parser.add_argument("--api-key", default=os.getenv("MYNEXUS_LLM_OPENAI_API_KEY", ""))
    parser.add_argument("--base-url", default=None, help="override the captured base_url")
    parser.add_argument("--model", default=None, help="override the captured model")
    args = parser.parse_args()

    captured = json.loads(Path(args.request_file).read_text(encoding="utf-8"))
    provider = captured["provider"]
    base_url = args.base_url or captured["base_url"]
    model = args.model or captured["model"]
    messages = captured["messages"]

    print(f"# provider={provider} base_url={base_url} model={model}", file=sys.stderr)
    print(f"# {len(messages)} message(s), captured at {captured.get('timestamp', '?')}", file=sys.stderr)

    if provider == "ollama":
        llm = OllamaLLM(base_url, model)
    else:
        llm = OpenAILLM(args.api_key, base_url, model)

    for delta in llm.process(messages):
        print(delta, end="", flush=True)
    print()


if __name__ == "__main__":
    main()
