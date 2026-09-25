# Frontend

Product semantics are defined in
[PRODUCT_SEMANTICS.md](../../docs/PRODUCT_SEMANTICS.md).
[DESIGN.md](DESIGN.md) defines presentation only.

```sh
npm install
npm run dev -- --host 127.0.0.1
npm test
npm run build
```

Set `VITE_API_BASE_URL` in `apps/web/.env.local` to the backend origin (no `/api`
suffix). The file is ignored. Vite proxies `/api` and `/health` to that origin
during development; absent a configured origin it uses `http://localhost:8000`.
This preserves the `X-Valtide-Source` response header for verification and allows
both local hostnames. Reads do not publish attestations.

Production builds call `VITE_API_BASE_URL` directly (or use same-origin routes
when it is set to an empty string). A cross-origin API must allow the deployed
frontend origin and expose `X-Valtide-Source` through CORS. Alternatively, configure
a same-origin API proxy on the frontend host. The Vite development proxy is not
part of a static production build. Historical replay fails closed when its
`historical_panel` source header cannot be verified; it never substitutes Demo.

Operational is the default context. Historical and Demo require explicit
selection. Offline fixture fallback exists only within Demo, retaining the six
unaltered scenario observations. Animation changes only the playhead position.
