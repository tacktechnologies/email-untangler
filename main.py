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
    print("📨 Inbound email received")
    print(testKey)
    print(data)  # log full JSON payload
    return {"status": "received"}
