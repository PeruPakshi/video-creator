# Prompt-to-video setup

This adds real generated motion clips using Wan 2.2 through fal. The original
offline narrated image-video pipeline remains available through main.py.
The new path needs Python 3.10+ only; do not install requirements.txt for it.
No local GPU, Node, or downloaded models are needed. Clips use 81 frames at
16 FPS and 480p (approximately 5 seconds before optional interpolation).
Audio generation is not included.

## GitHub

1. Fork https://github.com/prakashdk/video-creator into your GitHub account.
2. Add generate_clip.py, test_generate_clip.py, CLIP_SETUP.md and
   .github/workflows/generate-clip.yml from this package to your fork.
3. Create a fal account, add credits, and create an API key at
   https://fal.ai/dashboard/keys. Check the model's current price before running:
   https://fal.ai/models/fal-ai/wan/v2.2-a14b/text-to-video.
4. In your fork open Settings > Secrets and variables > Actions > New repository
   secret. Set its name to FAL_KEY and its value to your fal key.
5. Enable Actions if GitHub asks, then open Actions > Generate AI clip > Run
   workflow. Enter a prompt, for example: "A cinematic tracking shot of ocean
   waves breaking on a rocky shore at sunrise, natural motion, warm light."
6. Download the ai-clip artifact from the completed run. It contains video.mp4,
   request.json, and media-info.json. Artifacts expire after seven days.

The workflow runs only when manually triggered and each run makes a paid
generation request. No GitHub token needs to be stored as a secret for this job.
GitHub Actions usage may also count against your account limits.

## Local PowerShell

Set FAL_KEY in your environment through your preferred secure secret mechanism;
the script does not load .env files. Never commit your key.

    python -m unittest test_generate_clip -v
    python generate_clip.py --prompt "Ocean waves at sunrise" --output outputs/my-first-clip
    ffmpeg -v error -i outputs/my-first-clip/video.mp4 -f null -

Use --aspect-ratio 9:16 for vertical clips. Each output directory must be empty.
On failure, request.json retains the request ID if submission succeeded. Check
that request in the fal dashboard before rerunning to avoid duplicate charges.
Submission is deliberately not retried automatically. After a 20-minute timeout,
cancellation is attempted; already-running generations may still finish and bill.

## Verification status

Local automated tests use mocked provider responses and a synthetic file header.
They verify missing-key handling, queue polling, downloading without forwarding
credentials, manifest storage, and timeout cancellation. They do not prove AI
generation or video decodability. A funded FAL_KEY and a successful real run are
still needed for end-to-end verification. The GitHub job validates downloaded
video by decoding it with FFmpeg.

API references:
https://fal.ai/models/fal-ai/wan/v2.2-a14b/text-to-video/api
https://fal.ai/docs/documentation/model-apis/inference/queue
