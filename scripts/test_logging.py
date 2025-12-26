from app.core.sandbox import Sandbox
import logging

# Configure logging to stdout
logging.basicConfig(level=logging.INFO)

def test_sandbox():
    print("Testing Sandbox...")
    # This should trigger INFO logs
    sandbox = Sandbox()
    try:
        res = sandbox.run_code("print('logging test')")
        print(f"Result: {res['output'].strip()}")
    finally:
        sandbox.cleanup()

if __name__ == "__main__":
    test_sandbox()
