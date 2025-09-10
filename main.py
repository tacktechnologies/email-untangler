from fastapi import FastAPI, Request
import openai
import os

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok"}


def chunk_text(text: str, max_tokens: int = 100_000) -> list[str]:
    """
    Split text into large chunks for GPT-4-1106-preview.
    1 token ≈ 4 characters, so 100k tokens ≈ 400k chars.
    Leaves buffer below the 128k max to allow prompt + response.
    """
    chunk_size = max_tokens * 4  # ~400k characters
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]


async def summarize_chunk(chunk: str, openapikey: str) -> str:
    """Summarize a single chunk of an email thread."""
    openai.api_key = openapikey
    try:
        completion = openai.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {
                    "role": "user",
                    "content": f"""
You are analyzing part of an email thread.
Summarize this section chronologically, highlighting:
- Dates and timeline
- Senders and recipients
- Key events, decisions, and outcomes
- Any outstanding action items

Text:
{chunk}
                    """,
                }
            ],
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Error summarizing chunk:", e)
        return ""


async def merge_summaries(summaries: list[str], openapikey: str) -> str:
    """Merge partial summaries into one coherent narrative."""
    openai.api_key = openapikey
    combined = "\n\n".join([f"Chunk {i+1}: {s}" for i, s in enumerate(summaries)])
    try:
        completion = openai.chat.completions.create(
            model="gpt-4-1106-preview",
            messages=[
                {
                    "role": "user",
                    "content": f"""
You are given multiple partial summaries of an email thread.
Merge them into one coherent, chronological narrative.
Make it clear and concise.
Highlight:
- Dates and timeline
- Who sent what to whom
- Decisions and agreements
- Outstanding action items

Partial summaries:
{combined}
                    """,
                }
            ],
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Error merging summaries:", e)
        return "Error merging summaries."


@app.post("/inbound-email")
async def inbound_email(request: Request):
    data = await request.json()

    # Config / env
    openapikey = os.getenv("openapi")
    sender_email = data.get("FromFull", {}).get("Email")
    text_body = data.get("TextBody") or ""

    print("📨 Inbound email received")
    print("Sender:", sender_email)

    # Split into max-sized chunks (~100k tokens / 400k chars each)
    chunks = chunk_text(text_body, max_tokens=100_000)

    # Summarize each chunk
    partial_summaries = []
    for idx, chunk in enumerate(chunks, 1):
        print(f"🔎 Summarizing chunk {idx}/{len(chunks)} ({len(chunk)} chars)...")
        summary = await summarize_chunk(chunk, openapikey)
        partial_summaries.append(summary)

    # If only one chunk → just return that summary
    if len(partial_summaries) == 1:
        final_summary = partial_summaries[0]
    else:
        final_summary = await merge_summaries(partial_summaries, openapikey)

    print("📝 Final summary:\n", final_summary)

    return {"status": "processed"}
