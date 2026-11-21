# Tree imagery pipeline

Photoreal stills of one oak at dawn, generated with OpenRouter `google/gemini-3.1-flash-image` (`OPENROUTER_API_KEY` from `.env.local`; every call is logged in `costs.log`, USD 2.30 so far).

1. `gen.py MODEL OUT PROMPT [INPUT_IMAGE] [ASPECT]`: one image call (`IMG_SIZE=2K` for 2752x1536).
2. Master: `p_master.txt` (text to image), then re-rendered at 2K from itself with `p_up.txt`.
3. `hd.py WORKDIR`: every other still, level by level, from an exact crop of its parent's 2K still (`chain.json`: parent + normalised crop box), colour-matched to that crop. Prompt: `p_zoom.txt`.
4. `build.py WORKDIR ../public/tree`: AVIF encoding, label maps (limb skeletons + sub-branch hotspots in `hot.json`), and `stills.json` with a node slot down to level 4.

To add a deeper close-up: add `{"cK_I_J": {"parent": "cK_I", "box": [x, y, 0.5, 0.5]}}` to `chain.json`, run `hd.py` and `build.py`, and point the node's slot in `build.py` at it.
