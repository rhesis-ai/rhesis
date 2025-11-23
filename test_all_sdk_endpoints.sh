#!/bin/bash

# Comprehensive SDK Endpoint Testing Script
# Tests all test functions across different mapping scenarios

API_URL="http://localhost:8080"
API_KEY="rh-Qh_1EgeiKP2ek89CaojHINt81ZI5Ve3mD88HMFXqc1s"
OUTPUT_FILE="sdk_comprehensive_test_results.json"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "=========================================="
echo "SDK Comprehensive Testing Suite"
echo "Started: $TIMESTAMP"
echo "=========================================="
echo ""

# Initialize results file
echo "{" > "$OUTPUT_FILE"
echo "  \"test_run\": \"$TIMESTAMP\"," >> "$OUTPUT_FILE"

# Step 1: Fetch all SDK endpoints
echo -e "${YELLOW}Step 1: Fetching all SDK endpoints...${NC}"
echo ""

endpoints_response=$(curl -s -X GET "$API_URL/endpoints/?limit=100" \
    -H "Authorization: Bearer $API_KEY")

# Parse and display endpoints  
echo "$endpoints_response" | jq -r '.[] | select(.connection_type == "SDK") | "\(.endpoint_metadata.sdk_connection.function_name // "unknown") | \(.id) | \(.status)"' | while IFS='|' read -r func_name endpoint_id status; do
    echo "  - $func_name (${endpoint_id// /}) [${status// /}]"
done

# Save endpoint list
echo "  \"available_endpoints\": " >> "$OUTPUT_FILE"
echo "$endpoints_response" | jq '[.[] | select(.connection_type == "SDK") | {id, name, function: .endpoint_metadata.sdk_connection.function_name, status, request_mapping: .request_mapping, response_mapping: .response_mapping}]' >> "$OUTPUT_FILE"
echo "," >> "$OUTPUT_FILE"

echo ""
echo "  \"tests\": [" >> "$OUTPUT_FILE"

test_count=0

# Helper function to run a test
run_test() {
    local category="$1"
    local test_name="$2"
    local function_name="$3"
    local request_data="$4"
    local description="$5"
    
    # Find endpoint ID for this function
    local endpoint_id=$(echo "$endpoints_response" | jq -r ".[] | select(.endpoint_metadata.sdk_connection.function_name == \"$function_name\") | .id")
    
    if [ -z "$endpoint_id" ] || [ "$endpoint_id" == "null" ]; then
        echo -e "${RED}⚠️  Function '$function_name' not found - SKIPPED${NC}"
        return
    fi
    
    test_count=$((test_count + 1))
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}[$category] Test $test_count: $test_name${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo "Function: $function_name"
    echo "Endpoint ID: $endpoint_id"
    echo "Description: $description"
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
    cat >> "$OUTPUT_FILE" << EOF
    {
      "test_number": $test_count,
      "category": "$category",
      "test_name": "$test_name",
      "function_name": "$function_name",
      "description": "$description",
      "endpoint_id": "$endpoint_id",
      "request": $request_data,
      "response": $response,
      "status": "$status"
    }
EOF
    
    echo ""
    sleep 0.5
}

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}CATEGORY 1: AUTO-MAPPING (HIGH CONFIDENCE)${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

run_test "AUTO-MAPPING" \
    "Standard Naming" \
    "test_standard_naming" \
    '{
        "input": "Test with all standard fields",
        "session_id": "test_123"
    }' \
    "Exact match on input & session_id (confidence: 0.7)"

run_test "AUTO-MAPPING" \
    "Partial Standard" \
    "test_partial_standard" \
    '{
        "input": "Test with partial standard naming",
        "session_id": "partial_456"
    }' \
    "Only input & session_id, missing context/metadata/tool_calls"

run_test "AUTO-MAPPING" \
    "Input Only" \
    "test_input_only" \
    '{
        "input": "Test with only input parameter"
    }' \
    "Only input field (confidence: 0.5, should still auto-map)"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}CATEGORY 2: PATTERN VARIATIONS${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

run_test "PATTERN-VARIATIONS" \
    "Input Variations" \
    "test_input_variations" \
    '{
        "input": "Testing message parameter",
        "session_id": "conv_789"
    }' \
    "message→input, conversation_id→session_id mapping"

run_test "PATTERN-VARIATIONS" \
    "Compound Patterns" \
    "test_compound_patterns" \
    '{
        "input": "Testing compound names",
        "session_id": "compound_123"
    }' \
    "user_message→input, conv_id→session_id, context_docs→context"

run_test "PATTERN-VARIATIONS" \
    "Suffix Patterns" \
    "test_suffix_patterns" \
    '{
        "input": "Testing _id suffixes",
        "session_id": "suffix_456"
    }' \
    "query→input, session_id/thread_id→session_id"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}CATEGORY 3: LLM FALLBACK (LOW CONFIDENCE)${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

run_test "LLM-FALLBACK" \
    "Custom Naming No Hints" \
    "test_custom_naming_no_hints" \
    '{
        "input": "Testing completely custom parameters",
        "session_id": "custom_789"
    }' \
    "xyz/abc/qwerty params, LLM should infer mappings"

run_test "LLM-FALLBACK" \
    "Domain Specific Naming" \
    "test_domain_specific_naming" \
    '{
        "input": "What is covered in my policy?",
        "session_id": "POL-123456"
    }' \
    "insurance_question→input, policy_number→session_id"

run_test "LLM-FALLBACK" \
    "Abbreviated Names" \
    "test_abbreviated_names" \
    '{
        "input": "Testing abbreviations",
        "session_id": "abbr_999"
    }' \
    "q→input, sid→session_id, ctx→context"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}CATEGORY 4: MANUAL MAPPINGS${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

run_test "MANUAL-MAPPING" \
    "Manual Request Mapping" \
    "test_manual_request_mapping" \
    '{
        "input": "Testing manual request mapping",
        "session_id": "manual_req_123",
        "context": ["doc1", "doc2", "doc3"]
    }' \
    "Custom request_mapping via @collaborate decorator"

run_test "MANUAL-MAPPING" \
    "Manual Response Mapping" \
    "test_manual_response_mapping" \
    '{
        "input": "Testing manual response mapping",
        "session_id": "manual_resp_456"
    }' \
    "Custom response_mapping extracting nested fields"

run_test "MANUAL-MAPPING" \
    "Full Manual Mapping" \
    "test_full_manual_mapping" \
    '{
        "input": "I need support with my ticket",
        "session_id": "TKT-789",
        "context": ["ticket_history"],
        "metadata": {"urgency": "high"}
    }' \
    "Both request & response manually mapped"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}CATEGORY 5: CUSTOM FIELD PASSTHROUGH${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

run_test "CUSTOM-FIELDS" \
    "Custom Field Passthrough" \
    "test_custom_field_passthrough" \
    '{
        "input": "What is my coverage?",
        "policy_number": "POL-987654",
        "customer_tier": "gold",
        "language": "fr"
    }' \
    "Custom fields (policy_number, customer_tier, language) passed through"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}CATEGORY 6: COMPLEX OUTPUT STRUCTURES${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

run_test "COMPLEX-OUTPUT" \
    "Nested Output" \
    "test_nested_output" \
    '{
        "input": "Testing deeply nested response"
    }' \
    "Response with deeply nested output structure"

run_test "COMPLEX-OUTPUT" \
    "List Output" \
    "test_list_output" \
    '{
        "input": "Testing list output"
    }' \
    "Response with list/array outputs"

run_test "COMPLEX-OUTPUT" \
    "Mixed Output Types" \
    "test_mixed_output_types" \
    '{
        "input": "Testing mixed data types"
    }' \
    "Response with string, float, int, bool, list, dict"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}CATEGORY 7: FIELD SEPARATION VALIDATION${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

run_test "FIELD-SEPARATION" \
    "Response Fields in Request Ignored" \
    "test_standard_naming" \
    '{
        "input": "Validate field separation",
        "session_id": "sep_test",
        "context": ["should", "be", "ignored"],
        "metadata": {"should": "be_ignored"},
        "tool_calls": [{"should": "be_ignored"}]
    }' \
    "CRITICAL: context/metadata/tool_calls in request should be IGNORED"

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}CATEGORY 8: EDGE CASES${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

run_test "EDGE-CASES" \
    "Empty Input" \
    "test_standard_naming" \
    '{
        "input": "",
        "session_id": "empty_test"
    }' \
    "Empty string input"

run_test "EDGE-CASES" \
    "Very Long Input" \
    "test_standard_naming" \
    '{
        "input": "'"$(python3 -c 'print("A" * 1000)')"'",
        "session_id": "long_test"
    }' \
    "1000 character input"

run_test "EDGE-CASES" \
    "Unicode and Emoji" \
    "test_standard_naming" \
    '{
        "input": "Testing: 你好 🎉 مرحبا שלום",
        "session_id": "unicode_test"
    }' \
    "Unicode characters from multiple languages + emoji"

run_test "EDGE-CASES" \
    "JSON Special Characters" \
    "test_standard_naming" \
    '{
        "input": "Testing: \"quotes\" and \\backslash\\ and \ttab",
        "session_id": "json_escape_test"
    }' \
    "JSON special characters requiring escaping"

# Close JSON
echo "" >> "$OUTPUT_FILE"
echo "  ]," >> "$OUTPUT_FILE"

# Generate summary
success_count=$(grep -c '"status": "success"' "$OUTPUT_FILE")
error_count=$(grep -c '"status": "error"' "$OUTPUT_FILE")

echo "  \"summary\": {" >> "$OUTPUT_FILE"
echo "    \"total_tests\": $test_count," >> "$OUTPUT_FILE"
echo "    \"success_count\": $success_count," >> "$OUTPUT_FILE"
echo "    \"error_count\": $error_count," >> "$OUTPUT_FILE"
echo "    \"success_rate\": \"$(echo "scale=1; $success_count * 100 / $test_count" | bc)%\"," >> "$OUTPUT_FILE"
echo "    \"completed_at\": \"$(date '+%Y-%m-%d %H:%M:%S')\"" >> "$OUTPUT_FILE"
echo "  }" >> "$OUTPUT_FILE"
echo "}" >> "$OUTPUT_FILE"

# Final summary
echo ""
echo "=========================================="
echo -e "${GREEN}COMPREHENSIVE TESTING COMPLETE!${NC}"
echo "=========================================="
echo ""
echo "📊 Test Summary:"
echo "  Total Tests:   $test_count"
echo "  ✅ Success:    $success_count"
echo "  ❌ Errors:     $error_count"
echo "  Success Rate:  $(echo "scale=1; $success_count * 100 / $test_count" | bc)%"
echo ""
echo "📁 Results saved to: $OUTPUT_FILE"
echo ""
echo "🔍 Analysis commands:"
echo "  View all results:      cat $OUTPUT_FILE | jq '.'"
echo "  View summary:          cat $OUTPUT_FILE | jq '.summary'"
echo "  View by category:      cat $OUTPUT_FILE | jq '.tests[] | select(.category == \"AUTO-MAPPING\")'"
echo "  View errors only:      cat $OUTPUT_FILE | jq '.tests[] | select(.status == \"error\")'"
echo "  View specific test:    cat $OUTPUT_FILE | jq '.tests[0]'"
echo ""

