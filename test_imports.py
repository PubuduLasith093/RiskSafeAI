#!/usr/bin/env python3
"""Quick import test to find missing dependencies."""

print("Testing imports...")

try:
    print("1. Testing basic imports...")
    from dotenv import load_dotenv
    print("  OK dotenv")

    from compliance_chat.utils.config_loader import load_config
    print("  OK config_loader")

    from compliance_chat.utils.model_loader import ModelLoader
    print("  OK model_loader")

    print("\n2. Testing main.py imports...")
    from compliance_chat.src.document_ingestion.data_ingestion import ChatIngestor
    print("  OK ChatIngestor")

    from compliance_chat.src.document_chat.retrieval import ConversationalRAG
    print("  OK ConversationalRAG")

    print("\n3. Testing FastAPI...")
    from fastapi import FastAPI
    print("  OK FastAPI")

    print("\nSUCCESS: All imports successful!")

except Exception as e:
    print(f"\nERROR: Import failed: {e}")
    import traceback
    traceback.print_exc()
