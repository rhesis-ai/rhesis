#!/bin/bash

# Rhesis Helm Chart Test Script
# This script validates the Helm chart before deployment

set -e

CHART_PATH="."
VALUES_FILE="values-local.yaml"

echo "🧪 Testing Rhesis Helm Chart..."

# Function to check if Helm is available
check_helm() {
    if ! command -v helm &> /dev/null; then
        echo "❌ Helm is not installed or not in PATH"
        echo "Please install Helm: https://helm.sh/docs/intro/install/"
        exit 1
    fi
    echo "✅ Helm found: $(helm version --short)"
}

# Function to lint the chart
lint_chart() {
    echo "🔍 Linting chart..."
    if helm lint $CHART_PATH; then
        echo "✅ Chart linting passed"
    else
        echo "❌ Chart linting failed"
        exit 1
    fi
}

# Function to test template rendering
test_templates() {
    echo "📝 Testing template rendering..."
    if helm template test-release $CHART_PATH --values $VALUES_FILE > /dev/null; then
        echo "✅ Template rendering successful"
    else
        echo "❌ Template rendering failed"
        exit 1
    fi
}

# Function to validate values
validate_values() {
    echo "✅ Validating values file..."
    if [ -f "$VALUES_FILE" ]; then
        echo "✅ Values file found: $VALUES_FILE"
    else
        echo "❌ Values file not found: $VALUES_FILE"
        exit 1
    fi
}

# Function to check chart structure
check_structure() {
    echo "📁 Checking chart structure..."
    
    required_files=("Chart.yaml" "values.yaml" "templates/")
    
    for file in "${required_files[@]}"; do
        if [ -e "$file" ]; then
            echo "✅ Found: $file"
        else
            echo "❌ Missing: $file"
            exit 1
        fi
    done
    
    echo "✅ Chart structure is valid"
}

# Function to show chart info
show_chart_info() {
    echo ""
    echo "📊 Chart Information:"
    helm show chart $CHART_PATH
    
    echo ""
    echo "📋 Chart Values:"
    helm show values $CHART_PATH
}

# Main test flow
main() {
    check_helm
    check_structure
    validate_values
    lint_chart
    test_templates
    show_chart_info
    
    echo ""
    echo "🎉 All tests passed! Your Helm chart is ready for deployment."
    echo ""
    echo "🚀 To deploy, run:"
    echo "   ./deploy-local.sh"
    echo ""
    echo "   Or manually:"
    echo "   helm install rhesis . --values $VALUES_FILE --namespace rhesis --create-namespace"
}

# Run main function
main
