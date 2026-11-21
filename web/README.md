# cigala web

Alexia's lazy decision tree, issue #2. React + Vite; financial numbers come exclusively from the API. Requires Node 22.12+ or 24 and the backend from this repository.

From the repo root, start the API:

```sh
python -m pip install -r api/requirements.txt
python -m uvicorn api.main:app --port 8000
```

In another terminal:

```sh
cd web
npm ci
npm run dev
```

Open the Vite URL (normally http://127.0.0.1:5173). The dev proxy maps `/api/*` to port 8000. For a separately hosted API, set `VITE_API_BASE_URL` in `web/.env.local` **before building**. For a same-origin production deployment, reverse-proxy `/api/*` to the backend with the `/api` prefix removed. No keys belong in Vite variables.

```sh
npm test
npm run build
```

## Demo check

1. Start at Today: three child options, metrics on every visible node.
2. Pick Master's, then part-time work: each click requests `/tree/expand`; only the returned chosen path, current siblings and children render.
3. Switch a grey sibling: replaces the current decision rather than appending to it.
4. Back one step and return to Today. Earlier siblings disappear once more than one level away.
5. Stop the backend and choose an option: an error and retry appear; the last valid tree stays visible.

Mock results are explicitly labelled. Negative balances show financing needs. No local financial fixture, paid API calls, or persisted user data. Profile details are loaded from `/profiles/demo`; if unavailable, the tree can still load independently. Leaf detail, editable assumptions, roots intake and chat/voice are separate issues #3/#4.
