import os
import sys
import io
import traceback
from compliance_chat.src.react_agent.agent import ReactAgent

# Force UTF-8 encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def test_run():
    try:
        agent = ReactAgent()
        query = "Generate obligation register for fintech personal loans"
        result = agent.run(query)
        print("RESULT ANSWER LENGTH:", len(result.get('answer', '')))
    except Exception as e:
        print("\nFATAL ERROR DETECTED:")
        traceback.print_exc()

if __name__ == "__main__":
    test_run()
