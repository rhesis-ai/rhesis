#!/bin/bash

# SDK Endpoint Testing Script
# Tests various mapping scenarios and saves results for analysis

API_URL="http://localhost:8080"
API_KEY="rh-Qh_1EgeiKP2ek89CaojHINt81ZI5Ve3mD88HMFXqc1s"
OUTPUT_FILE="sdk_test_results.json"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Color codes for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "SDK Endpoint Testing Suite"
echo "Started: $TIMESTAMP"
echo "=========================================="
echo ""

# Initialize results file
echo "{" > "$OUTPUT_FILE"
echo "  \"test_run\": \"$TIMESTAMP\"," >> "$OUTPUT_FILE"
echo "  \"tests\": [" >> "$OUTPUT_FILE"

test_count=0

# Helper function to run a test
run_test() {
    local test_name="$1"
    local endpoint_id="$2"
    local request_data="$3"
    local description="$4"
    
    test_count=$((test_count + 1))
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Test $test_count: $test_name${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo "Description: $description"
    echo "Endpoint ID: $endpoint_id"
    echo ""
    echo "Request:"
    echo "$request_data" | jq '.' 2>/dev/null || echo "$request_data"
    echo ""
    
    # Add comma if not first test
    if [ $test_count -gt 1 ]; then
        echo "," >> "$OUTPUT_FILE"
    fi
    
    # Make the API call
    response=$(curl -s -X POST "$API_URL/endpoints/$endpoint_id/invoke" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $API_KEY" \
        -d "$request_data")
    
    # Check if response contains error
    if echo "$response" | jq -e '.detail' > /dev/null 2>&1; then
        echo -e "${RED}❌ ERROR${NC}"
        echo "$response" | jq '.'
        status="error"
    else
        echo -e "${GREEN}✅ SUCCESS${NC}"
        echo "$response" | jq '.'
        status="success"
    fi
    
    # Save to results file
    echo "    {" >> "$OUTPUT_FILE"
    echo "      \"test_number\": $test_count," >> "$OUTPUT_FILE"
    echo "      \"test_name\": \"$test_name\"," >> "$OUTPUT_FILE"
    echo "      \"description\": \"$description\"," >> "$OUTPUT_FILE"
    echo "      \"endpoint_id\": \"$endpoint_id\"," >> "$OUTPUT_FILE"
    echo "      \"request\": $request_data," >> "$OUTPUT_FILE"
    echo "      \"response\": $response," >> "$OUTPUT_FILE"
    echo "      \"status\": \"$status\"" >> "$OUTPUT_FILE"
    echo -n "    }" >> "$OUTPUT_FILE"
    
    echo ""
    sleep 0.5
}

# First, get all SDK endpoints to find their IDs
echo -e "${YELLOW}Fetching all SDK endpoints...${NC}"
echo ""

endpoints_response=$(curl -s -X GET "$API_URL/endpoints" \
    -H "Authorization: Bearer $API_KEY")

# Save endpoint list
echo "  \"available_endpoints\": " >> "$OUTPUT_FILE"
echo "$endpoints_response" | jq '[.data[] | select(.connection_type == "sdk") | {id, name, function: .endpoint_metadata.sdk_connection.function_name, status}]' >> "$OUTPUT_FILE"
echo "," >> "$OUTPUT_FILE"

echo "Available SDK Endpoints:"
echo "$endpoints_response" | jq '.data[] | select(.connection_type == "sdk") | {id, name, function: .endpoint_metadata.sdk_connection.function_name, status}'
echo ""
echo -e "${YELLOW}Press Enter to start tests...${NC}"
read

# Extract endpoint IDs (we'll use the known one and try to find others)
TEST_STANDARD_NAMING="5fa73ff4-6e19-4061-898b-f602f3c6de90"

# Test 1: Standard naming with auto-mapping
run_test \
    "test_standard_naming" \
    "$TEST_STANDARD_NAMING" \
    '{
        "input": "Hello, this is a test message",
        "session_id": "test_session_123"
    }' \
    "Auto-mapping with standard field names (input, session_id)"

# Test 2: Request/response field separation
run_test \
    "test_field_separation" \
    "$TEST_STANDARD_NAMING" \
    '{
        "input": "Testing field separation",
        "session_id": "session_456",
        "context": ["doc1", "doc2"],
        "metadata": {"priority": "high"},
        "tool_calls": [{"name": "search"}]
    }' \
    "Verify context/metadata/tool_calls in request are ignored (they are RESPONSE fields)"

# Test 3: Missing session_id (optional parameter)
run_test \
    "test_optional_session" \
    "$TEST_STANDARD_NAMING" \
    '{
        "input": "Testing without session_id"
    }' \
    "Test with only required field (input), session_id is optional"

# Test 4: Empty input
run_test \
    "test_empty_input" \
    "$TEST_STANDARD_NAMING" \
    '{
        "input": "",
        "session_id": "empty_test"
    }' \
    "Test with empty input string"

# Test 5: Long input
run_test \
    "test_long_input" \
    "$TEST_STANDARD_NAMING" \
    '{
        "input": "This is a much longer input message to test how the system handles more substantial text. It should still process correctly and return the appropriate response with all the standard fields populated as expected.",
        "session_id": "long_test_789"
    }' \
    "Test with longer input text"

# Test 6: Special characters
run_test \
    "test_special_chars" \
    "$TEST_STANDARD_NAMING" \
    '{
        "input": "Testing with special chars: @#$%^&*()_+-=[]{}|;:,.<>?",
        "session_id": "special_chars_test"
    }' \
    "Test with special characters in input"

# Test 7: Unicode characters
run_test \
    "test_unicode" \
    "$TEST_STANDARD_NAMING" \
    '{
        "input": "Testing Unicode: 你好世界 🎉 café",
        "session_id": "unicode_test"
    }' \
    "Test with Unicode and emoji characters"

# Test 8: Nested objects in input (should be stringified by Jinja2)
run_test \
    "test_complex_input" \
    "$TEST_STANDARD_NAMING" \
    '{
        "input": "What about complex data?",
        "session_id": "complex_test",
        "custom_field": {"nested": "value", "array": [1, 2, 3]}
    }' \
    "Test with custom nested field (demonstrates passthrough)"

# Close JSON array and object
echo "" >> "$OUTPUT_FILE"
echo "  ]," >> "$OUTPUT_FILE"
echo "  \"summary\": {" >> "$OUTPUT_FILE"
echo "    \"total_tests\": $test_count," >> "$OUTPUT_FILE"
echo "    \"completed_at\": \"$(date '+%Y-%m-%d %H:%M:%S')\"" >> "$OUTPUT_FILE"
echo "  }" >> "$OUTPUT_FILE"
echo "}" >> "$OUTPUT_FILE"

# Final summary
echo ""
echo "=========================================="
echo -e "${GREEN}Testing Complete!${NC}"
echo "=========================================="
echo "Total tests run: $test_count"
echo "Results saved to: $OUTPUT_FILE"
echo ""
echo "To view results:"
echo "  cat $OUTPUT_FILE | jq '.'"
echo ""
echo "To view summary:"
echo "  cat $OUTPUT_FILE | jq '.summary'"
echo ""
echo "To view specific test:"
echo "  cat $OUTPUT_FILE | jq '.tests[0]'  # First test"
echo ""

