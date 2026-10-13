"""Prompt-to-video via fal's queue API. Python 3.10+, no pip packages required."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MODEL = "fal-ai/wan/v2.2-a14b/text-to-video"


def api(url, key, payload=None, method=None):
    if urlparse(url).scheme != "https" or urlparse(url).netloc != "queue.fal.run":
        raise ValueError("Unexpected queue URL")
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=data, method=method, headers={
        "Authorization": f"Key {key}", "Content-Type": "application/json"
    })
    try:
        with urlopen(request, timeout=60) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"fal HTTP {error.code}; check credentials, credits, and model access") from None
    except URLError:
        raise RuntimeError("fal network error; check connectivity. Submission is not automatically retried.") from None


def generate(prompt, output, aspect_ratio="16:9", timeout=1200):
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty")
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        raise ValueError("Set FAL_KEY in your environment or GitHub Actions secrets")
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; use a new directory for each run")
    output.mkdir(parents=True, exist_ok=True)
    inputs = {"prompt": prompt, "aspect_ratio": aspect_ratio, "resolution": "480p",
              "num_frames": 81, "frames_per_second": 16,
              "enable_safety_checker": True, "enable_output_safety_checker": True}
    queued = api(f"https://queue.fal.run/{MODEL}", key, inputs)
    metadata = {"model": MODEL, "input": inputs, "queue": queued}
    manifest = output / "request.json"
    manifest.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Submitted request {queued['request_id']}", flush=True)
    deadline = time.monotonic() + timeout
    previous = None
    while time.monotonic() < deadline:
        status = api(queued["status_url"], key)
        state = status.get("status")
        if state != previous:
            print(f"Status: {state}", flush=True)
            previous = state
        if status.get("error"):
            raise RuntimeError("Provider reported generation failure; inspect request in fal dashboard")
        if state == "COMPLETED":
            break
        if state not in ("IN_QUEUE", "IN_PROGRESS"):
            raise RuntimeError(f"Unexpected queue status: {state}")
        time.sleep(5)
    else:
        try:
            api(queued["cancel_url"], key, method="PUT")
        except (RuntimeError, ValueError):
            pass
        raise TimeoutError("Generation timed out; cancellation attempted. Check fal dashboard before rerunning.")
    result = api(queued["response_url"], key)
    metadata["result"] = result
    manifest.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    video_url = result.get("video", {}).get("url", "")
    if urlparse(video_url).scheme != "https":
        raise RuntimeError("Provider did not return an HTTPS video URL")
    temporary = output / "video.mp4.part"
    try:
        # No API key is sent to the media host.
        with urlopen(video_url, timeout=120) as response, temporary.open("wb") as target:
            shutil.copyfileobj(response, target)
        with temporary.open("rb") as video:
            header = video.read(12)
        if len(header) < 12 or header[4:8] != b"ftyp":
            raise RuntimeError("Downloaded file is not an MP4")
        temporary.replace(output / "video.mp4")
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Saved {output / 'video.mp4'}", flush=True)
    return output / "video.mp4"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", default="outputs/clip")
    parser.add_argument("--aspect-ratio", choices=["16:9", "9:16", "1:1"], default="16:9")
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        generate(args.prompt, args.output, args.aspect_ratio, args.timeout)
    except (ValueError, RuntimeError, TimeoutError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
