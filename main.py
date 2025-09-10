#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 10 16:07:02 2025

@author: aaronbrace
"""

from fastapi import FastAPI, Request
import openai
import os
app = FastAPI()



@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/inbound-email")
async def inbound_email(request: Request):
    data = await request.json()
    testKey = os.getenv('TESTER')
    openapikey = os.getenv('TESTER')
    sender_email = data.get("FromFull", {}).get("Email")  # clean email
    print("Sender:", sender_email)
    openai.api_key = openapikey
    print("📨 Inbound email received")
    print(testKey)
    print(data)  # log full JSON payload
    mod = True
    while mod:
        try:
            completion = openai.chat.completions.create(
              model="gpt-4-1106-preview",
              messages=[
                {"role": "user", "content": f"""your job is to summarise email threads and show dates, senders and receipients and outcomes. here is the thread, return the summaries: {data}"""
                 }
              ]
            )
            mod = False
        except Exception as e:
            print(e)

    b = completion.dict()['choices'][0]['message']['content']
    print(b)
    return {"status": "received"}
