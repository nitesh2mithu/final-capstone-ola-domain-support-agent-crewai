# Deployment

## Vercel

Production URL: [https://final-capstone-ola-domain-support-a.vercel.app](https://final-capstone-ola-domain-support-a.vercel.app)

The repository is configured for Vercel's container runtime through the root `Dockerfile` and `vercel.json`. The production deployment of commit `1f3ebf1` passed root, health, policy, session, reset, and secure WebSocket smoke tests. The machine-readable [deployment evidence](../evidence/vercel_deployment_verification.json) records that scope.

1. Import `nitesh2mithu/final-capstone-ola-domain-support-agent-crewai` in Vercel.
2. Keep the root directory at the repository root and the framework preset as **Container**.
3. Deploy without environment variables. The image enables deterministic `MOCK_LLM` mode and downloads the pinned embedding model only during its build.
4. Confirm `GET /health` returns `{"status":"ok","mode":"MOCK_LLM","api_keys_required":false}` before testing support requests.

The service must run as one worker. Sessions, cache, logs, and generated indexes are instance-local and ephemeral; a cold start or scale-out can therefore end a multi-turn session. WebSocket clients should reconnect if an instance is retired.

## Local container check

```sh
docker build -t ola-domain-support-agent .
docker run --rm -p 8000:8000 ola-domain-support-agent
curl --noproxy '*' -s http://127.0.0.1:8000/health
```

The locally verified image was about 722 MB and used about 502 MiB after HTTP and WebSocket requests. A host should provide more than 512 MiB of memory; this rules out the smallest free Render and Koyeb instances for this build.

## API smoke test

```sh
curl -s -H 'Content-Type: application/json' \
  -d '{"query":"What is the refund policy for a duplicate charge?","session_id":"smoke-test"}' \
  https://final-capstone-ola-domain-support-a.vercel.app/ask
```

The public root lists the available routes. No API key or third-party model credential is required.
