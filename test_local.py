#!/usr/bin/env python3
from lambda_function import lambda_handler

# Test event (simulate API Gateway or direct invoke)
test_event = {
    "httpMethod": "GET",
    "path": "/test"
}

# Mock context
class MockContext:
    def __init__(self):
        self.function_name = "PeerSupportTesting"
        self.aws_request_id = "test-request-id"

if __name__ == "__main__":
    context = MockContext()
    result = lambda_handler(test_event, context)
    print("Response:", result)