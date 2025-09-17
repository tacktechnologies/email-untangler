from fastapi import FastAPI, Request
import openai
import os
import re
import requests

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


def clean_summary_html(text: str) -> str:
    """Remove any accidental code fences or backticks from model output."""
    return re.sub(r"```html|```", "", text, flags=re.IGNORECASE).strip()


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

Return only valid HTML — **never wrap it in Markdown code fences** (no ```html).

Use this exact structure with emojis and color-bar-friendly headers:

<h2>📅 Dates and Timeline</h2>
<ul>
  <li>Use <strong>bold</strong> for key dates</li>
</ul>

<h2>👥 Senders and Recipients</h2>
<ul>
  <li>List each person and their role (sender, CC, etc.)</li>
</ul>

<h2>📝 Key Events, Decisions, and Outcomes</h2>
<ul>
  <li>Summarize what was discussed and decided</li>
</ul>

<h2>⚡ Outstanding Action Items</h2>
<ul>
  <li>Use <strong>bold names</strong> and <em>deadlines</em></li>
</ul>

Rules:
- Use semantic HTML (<h2>, <ul>, <li>, <strong>, <em>)
- Add relevant emojis to section headers only
- No Markdown (**text**, - lists)
- Be concise and scannable

Text to summarize:
{chunk}
"""
                }
            ],
        )
        return clean_summary_html(completion.choices[0].message.content.strip())
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
Merge them into one coherent, chronological narrative
using this exact structure — and return only raw HTML (no Markdown fences):

<h2>📅 Dates and Timeline</h2>
<ul>...</ul>

<h2>👥 Senders and Recipients</h2>
<ul>...</ul>

<h2>📝 Key Events, Decisions, and Outcomes</h2>
<ul>...</ul>

<h2>⚡ Outstanding Action Items</h2>
<ul>...</ul>

Rules:
- Use semantic HTML
- Include emojis in section headers
- Be concise, scannable, and visually consistent
- No Markdown or code fences

Partial summaries:
{combined}
"""
                }
            ],
        )
        return clean_summary_html(completion.choices[0].message.content.strip())
    except Exception as e:
        print("❌ Error merging summaries:", e)
        return "Error merging summaries."


@app.post("/inbound-email")
async def inbound_email(request: Request):
    data = await request.json()

    # Config / env
    openapikey = os.getenv("openapi")
    postmarkkey = os.getenv("POSTMARKKEY")
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

    # Clean again just in case
    final_summary = clean_summary_html(final_summary)

    print("📝 Final summary:\n", final_summary)

    url = "https://api.postmarkapp.com/email"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Postmark-Server-Token": postmarkkey
    }

    # Styled HTML email layout
    html_body = f"""
    <html>
      <body style="font-family:Segoe UI, Arial, sans-serif; background:#f4f6f9; padding:30px; color:#333;">
        <div style="max-width:650px; margin:0 auto; background:#ffffff; border-radius:12px; padding:40px; box-shadow:0 4px 14px rgba(0,0,0,0.06);">
          <h1 style="text-align:center; color:#4a90e2; margin-bottom:30px;">📨 Your Thread Has Been Untangled!</h1>
          <style>
            h2 {{
              border-left: 6px solid #4a90e2;
              padding-left: 10px;
              margin-top: 30px;
              color: #2c3e50;
            }}
            ul {{
              list-style: none;
              padding-left: 0;
            }}
            ul li::before {{
              content: '• ';
              color: #4a90e2;
            }}
          </style>
          {final_summary}
          <p style="margin-top:40px; font-size:13px; color:#999; text-align:center;">
            — Generated automatically by <strong>Untangle</strong>
          </p>
        </div>
      </body>
    </html>
    """

    data = {
        "From": "untangle@audienserve.com",
        "To": sender_email,
        "Subject": "Email Summary",
        "HtmlBody": html_body,
        "TextBody": "Your email client does not support HTML.",
        "MessageStream": "outbound"
    }

    response = requests.post(url, headers=headers, json=data, timeout=15)
    if response.status_code == 200:
        print("✅ Email sent via Postmark")
    else:
        print("❌ Postmark send failed:", response.status_code, response.text)
    print("Status:", response.status_code)
    print("Response:", response.text)
    return {"status": "processed"}
