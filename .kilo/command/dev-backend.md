---
description: Start the FastAPI backend dev server
---
Start the backend dev server from the project root:

`cd api && python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000`

Use this for local API development; production uses `uvicorn wsgi:app`.
