# Data layout

`data/generated/` contains local diagnostic and replay-panel outputs generated
by scripts. `data/runtime/` contains the local SQLite runtime state. Both are
ignored and are never deployment or source-of-truth artifacts.

The canonical quant model and feature artifacts live in
`valtide-quant-service-p1ac/`. The backend consumes those package artifacts and
does not silently fall back to a checked-in sample panel.
