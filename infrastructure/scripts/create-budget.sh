#!/bin/bash

# Gemini API Budget Setup Script
# Creates a monthly 1000 EUR budget with email alerts

set -e

echo "🚀 Setting up Gemini API budget..."

# Configuration
BUDGET_AMOUNT="1000"
CURRENCY="EUR"
EMAIL1="harry@rhesis.ai"
EMAIL2="nicolai@rhesis.ai"
BUDGET_NAME="Gemini API Monthly Budget - ${BUDGET_AMOUNT} ${CURRENCY}"

# Get billing account
echo "📋 Getting billing account..."
BILLING_ACCOUNT=$(gcloud billing accounts list --format="value(name)" --limit=1)
if [ -z "$BILLING_ACCOUNT" ]; then
    echo "❌ Error: No billing account found"
    exit 1
fi
echo "✅ Using billing account: $BILLING_ACCOUNT"

# Create notification channels
echo "📧 Creating email notification channels..."

# Create first notification channel
CHANNEL1_ID=$(gcloud alpha monitoring channels create \
    --display-name="Budget Alert - Harry" \
    --type=email \
    --channel-labels=email_address=$EMAIL1 \
    --format="value(name)")

if [ -z "$CHANNEL1_ID" ]; then
    echo "❌ Error: Failed to create notification channel for $EMAIL1"
    exit 1
fi
echo "✅ Created notification channel for $EMAIL1: $CHANNEL1_ID"

# Create second notification channel
CHANNEL2_ID=$(gcloud alpha monitoring channels create \
    --display-name="Budget Alert - Nicolai" \
    --type=email \
    --channel-labels=email_address=$EMAIL2 \
    --format="value(name)")

if [ -z "$CHANNEL2_ID" ]; then
    echo "❌ Error: Failed to create notification channel for $EMAIL2"
    exit 1
fi
echo "✅ Created notification channel for $EMAIL2: $CHANNEL2_ID"

# Create the budget
echo "💰 Creating monthly budget..."
BUDGET_ID=$(gcloud billing budgets create \
    --billing-account=$BILLING_ACCOUNT \
    --display-name="$BUDGET_NAME" \
    --budget-amount=${BUDGET_AMOUNT}${CURRENCY} \
    --threshold-rule=percent=50,basis=CURRENT_SPEND \
    --threshold-rule=percent=90,basis=CURRENT_SPEND \
    --threshold-rule=percent=100,basis=CURRENT_SPEND \
    --notifications-rule-monitoring-notification-channels="$CHANNEL1_ID,$CHANNEL2_ID" \
    --filter-services="services/aiplatform.googleapis.com" \
    --format="value(name)")

if [ -z "$BUDGET_ID" ]; then
    echo "❌ Error: Failed to create budget"
    exit 1
fi

echo "✅ Budget created successfully!"
echo ""
echo "📊 Budget Summary:"
echo "   Name: $BUDGET_NAME"
echo "   Amount: $BUDGET_AMOUNT $CURRENCY (monthly)"
echo "   Service: AI Platform API (includes Gemini API)"
echo "   Alerts: 50%, 90%, 100% of budget"
echo "   Email notifications: $EMAIL1, $EMAIL2"
echo "   Budget ID: $BUDGET_ID"
echo ""
echo "🎉 Setup complete! You'll receive email alerts when spending reaches the configured thresholds."