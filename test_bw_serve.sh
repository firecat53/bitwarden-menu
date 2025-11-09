#!/bin/bash

# Test script for bw serve API

echo "Starting bw serve on port 8087..."
bw serve --hostname localhost:8087 &
BW_PID=$!
sleep 2

echo -e "\n=== 1. Check status ==="
curl -s http://localhost:8087/status | jq '.'

echo -e "\n=== 2. Unlock vault ==="
echo "Enter your master password:"
read -s PASSWORD
UNLOCK_RESPONSE=$(curl -s -X POST http://localhost:8087/unlock \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"$PASSWORD\"}")
echo "$UNLOCK_RESPONSE" | jq '.'

# Extract session token
SESSION=$(echo "$UNLOCK_RESPONSE" | jq -r '.data.raw')
echo "Session token (first 20 chars): ${SESSION:0:20}..."

echo -e "\n=== 3. List all items ==="
curl -s "http://localhost:8087/list/object/items?session=$SESSION" | jq '.data.data[] | {id, name, organizationId}'

echo -e "\n=== 4. Find 'test 3' item ==="
ITEM_ID=$(curl -s "http://localhost:8087/list/object/items?session=$SESSION" | jq -r '.data.data[] | select(.name=="test 3") | .id')
echo "Item ID: $ITEM_ID"

if [ -n "$ITEM_ID" ]; then
    echo -e "\n=== 5. Get full item details ==="
    ITEM=$(curl -s "http://localhost:8087/object/item/$ITEM_ID?session=$SESSION")
    echo "$ITEM" | jq '.'

    echo -e "\n=== 6. Try DELETE without body ==="
    curl -s -X DELETE "http://localhost:8087/object/item/$ITEM_ID?session=$SESSION" | jq '.'

    echo -e "\n=== 7. Try DELETE with item in body ==="
    curl -s -X DELETE "http://localhost:8087/object/item/$ITEM_ID?session=$SESSION" \
      -H "Content-Type: application/json" \
      -d "$ITEM" | jq '.'
fi

echo -e "\n=== Stopping bw serve ==="
kill $BW_PID
