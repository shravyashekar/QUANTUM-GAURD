from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from nlp_filter import should_block
import datetime
from dotenv import load_dotenv
import os

app = FastAPI(title="Quantum Guard AI Gateway")

# ✅ CORS (VERY IMPORTANT)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Groq setup ──
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


# =========================================================
# ✅ 1. LOG ANALYSIS ROUTE (USED BY FRONTEND)
# =========================================================
@app.post("/analyze")
async def analyze_logs(request: Request):

    body = await request.json()
    text = body.get("text", "")

    # 🔒 Safety check
    if not text or not text.strip():
        return {"logs": []}

    lines = text.split("\n")
    processed_logs = []

    for line in lines:
        if not line.strip():
            continue

        try:
            blocked, analysis = should_block(line)
            score = analysis["score"]
        except Exception as e:
            print("⚠️ NLP ERROR:", e)

            processed_logs.append({
                "time": "",
                "level": "INFO",
                "source": "NLP",
                "message": f"{line} (NLP skipped)"
            })
            continue

        # ✅ Decide severity
        if score >= 70:
            level = "ERROR"
        elif score >= 31:
            level = "WARN"
        else:
            level = "INFO"

        processed_logs.append({
            "time": "",
            "level": level,
            "source": "NLP",
            "message": f"{line} (Score: {score})"
        })

    return {"logs": processed_logs}


# =========================================================
# ✅ 2. CHAT INTERCEPT ROUTE (YOUR ORIGINAL LOGIC)
# =========================================================
@app.post("/v1/chat/completions")
async def intercept_prompt(request: Request):

    body = await request.json()
    messages = body.get("messages", [])

    # Extract user prompt
    user_prompt = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_prompt = msg.get("content", "")
            break

    print(f"\n[{datetime.datetime.now()}] Prompt: {user_prompt[:80]}...")

    # NLP check
    try:
        blocked, analysis = should_block(user_prompt)
        score = analysis["score"]
    except Exception as e:
        print("⚠️ NLP ERROR:", e)
        score = 0
        analysis = {"score": 0, "reasons": ["NLP failed"]}

    # 🔴 BLOCK
    if score >= 70:
        return JSONResponse(
            status_code=403,
            content={
                "status":  "blocked",
                "score":   f"{score}/100",
                "reasons": analysis["reasons"],
                "message": "Blocked by Quantum Guard AI"
            }
        )

    # 🟡 WARNING
    elif score >= 31:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GROQ_URL,
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": messages
                },
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )

        groq_data = response.json()
        reply_text = (
            groq_data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "No response")
        )

        return {
            "status": "warning",
            "score": f"{score}/100",
            "response": reply_text
        }

    # ✅ SAFE
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GROQ_URL,
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages
            },
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=30
        )

    groq_data = response.json()
    reply_text = (
        groq_data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "No response")
    )

    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": reply_text
            }
        }],
        "guard_score": score
    }


# =========================================================
# ✅ HEALTH CHECK
# =========================================================
@app.get("/health")
def health_check():
    return {"status": "Quantum Guard AI is running ✓"}