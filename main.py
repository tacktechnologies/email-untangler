#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 10 16:07:02 2025

@author: aaronbrace
"""

from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/inbound-email")
async def inbound_email(request: Request):
    data = await request.json()
    print("📨 Inbound email received")
    print(data)  # log full JSON payload
    return {"status": "received"}
