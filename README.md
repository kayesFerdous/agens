
**To start:**
```
env PYTHONPATH=src uv run -m src.main
```
or
```
uv run src/main.py
```

**To start the server:**
```
env PYTHONPATH=src uv run uvicorn interfaces.api.app:app --reload --log-level info
```

**For migration:**
```
env PYTHONPATH=src uv run -m db.init
```



