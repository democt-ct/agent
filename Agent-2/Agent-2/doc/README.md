# Travel Agent Worker

## Installed Skills

The current Codex environment has these non-system skills installed under `C:\Users\democt\.codex\skills`:

- `planning-with-files`: persistent file-based planning workflow using `task_plan.md`, `findings.md`, and `progress.md`
- `impeccable`: high-quality frontend design/build skill with `craft`, `teach`, and `extract` modes
- `frontend-design`: frontend design guidance skill installed from `anthropics/claude-code`
- `skill-creator`: skill authoring workflow for creating new Codex skills
- `notebooklm-skill`: NotebookLM-oriented skill installed from `PleasePrompto/notebooklm-skill`

Related repositories tracked in project docs but not installed as Codex skills:

- `codex-plugin-cc`: plugin repository, not a standard Codex skill
- `superpowers`: plugin/extension repository, not a standard Codex skill

After installing new skills, restart Codex so they are picked up.

## Local setup

1. Copy `.dev.vars.example` to `.dev.vars`.
2. Fill in `OPENAI_API_KEY` or local `TEXT_*` variables.
3. Replace the `database_id` and `preview_database_id` placeholders in `wrangler.toml`.
4. Install dependencies:

```powershell
npm.cmd install
```

5. Create a local D1 database if needed:

```powershell
npx.cmd wrangler d1 create travel-agent-db
```

6. Run the migration:

```powershell
npx.cmd wrangler d1 migrations apply travel-agent-db --local
```

7. Start the worker:

```powershell
npx.cmd wrangler dev --local
```

## Example flow

Create a session:

```powershell
curl.exe -X POST http://127.0.0.1:8787/sessions ^
  -H "content-type: application/json" ^
  -d "{\"title\":\"浜斾竴鏉窞 4 澶‐"}"
```

Create a requirement:

```powershell
curl.exe -X POST http://127.0.0.1:8787/sessions/SESSION_ID/requirements ^
  -H "content-type: application/json" ^
  -d "{\"raw_input\":\"鎴戞兂浜斾竴鍘绘澀宸炵帺4澶╋紝棰勭畻4000鍏冿紝涓嶈澶疮锛岄€傚悎鎷嶇収銆俓",\"strategy\":\"llm\"}"
```

Generate an itinerary:

```powershell
curl.exe -X POST http://127.0.0.1:8787/sessions/SESSION_ID/itineraries ^
  -H "content-type: application/json" ^
  -d "{\"generator_type\":\"agent\"}"
```

Replan the itinerary:

```powershell
curl.exe -X POST http://127.0.0.1:8787/sessions/SESSION_ID/replan ^
  -H "content-type: application/json" ^
  -d "{\"instruction\":\"绗笁澶╀笅闆紝璇锋妸鎴峰娲诲姩鍑忓皯骞朵繚鎸佹暣浣撹妭濂忚交鏉俱€俓",\"generator_type\":\"agent\"}"
```

## FastAPI chat app with Ollama

If you want to run the local chat app before using Cloudflare Worker, use the FastAPI app under `fastapi/`.
The current default local model is `modelscope.cn/unsloth/DeepSeek-R1-Distill-Qwen-7B-GGUF:latest`.

1. Create a Python virtual environment and install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r fastapi\requirements.txt
```

2. Set the local model environment variables:

```powershell
$env:TEXT_API_KEY="ollama"
$env:TEXT_API_BASE="http://127.0.0.1:11434/v1/"
$env:TEXT_MODEL="modelscope.cn/unsloth/DeepSeek-R1-Distill-Qwen-7B-GGUF:latest"
```

3. Start the FastAPI server:

```powershell
uvicorn app:app --app-dir fastapi --host 127.0.0.1 --port 9000 --reload
```

4. Open the chat interface at `http://127.0.0.1:9000` and talk to the assistant directly.

5. If you want to test the HTTP API directly, use these endpoints:

```powershell
curl.exe -X POST http://127.0.0.1:9000/sessions -H "content-type: application/json" -d "{\"title\":\"鏉窞璋冭瘯浼氳瘽\"}"
```

```powershell
curl.exe -X POST http://127.0.0.1:9000/sessions/SESSION_ID/requirements -H "content-type: application/json" -d "{\"raw_input\":\"鎴戞兂浜斾竴鍘绘澀宸炵帺4澶╋紝棰勭畻4000鍏冿紝涓嶈澶疮锛岄€傚悎鎷嶇収銆俓"}"
```

```powershell
curl.exe -X POST http://127.0.0.1:9000/sessions/SESSION_ID/itineraries -H "content-type: application/json" -d "{\"generator_type\":\"agent\"}"
```

```powershell
curl.exe -X POST http://127.0.0.1:9000/sessions/SESSION_ID/replan -H "content-type: application/json" -d "{\"instruction\":\"绗笁澶╀笅闆紝璇峰噺灏戞埛澶栧畨鎺掑苟淇濇寔杞绘澗鑺傚銆俓"}"
```

