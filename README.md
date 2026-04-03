# fin_tools

## XLSX build endpoint

`POST /xlsx/build`

Builds a multi-sheet `.xlsx` file in memory from JSON payload and returns it as a binary response.

Request example:

```json
{
  "file_name": "Balances_03.04.2026_11-00.xlsx",
  "sheets": [
    {
      "name": "Operator Alert",
      "rows": [
        { "merchant": "A", "currency": "INR", "balance": 1000 },
        { "merchant": "B", "currency": "USD", "balance": 2000 }
      ]
    },
    {
      "name": "Merchant Alert",
      "rows": [
        { "merchant": "X", "currency": "INR", "amount": 500 },
        { "merchant": "Y", "currency": "USD", "amount": 700 }
      ]
    }
  ]
}
```

curl example:

```bash
curl -X POST "https://fin-tools-app.onrender.com/xlsx/build" \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "Balances_03.04.2026_11-00.xlsx",
    "sheets": [
      {
        "name": "Operator Alert",
        "rows": [
          { "merchant": "A", "currency": "INR", "balance": 1000 },
          { "merchant": "B", "currency": "USD", "balance": 2000 }
        ]
      },
      {
        "name": "Merchant Alert",
        "rows": [
          { "merchant": "X", "currency": "INR", "amount": 500 },
          { "merchant": "Y", "currency": "USD", "amount": 700 }
        ]
      }
    ]
  }' \
  --output Balances_03.04.2026_11-00.xlsx
```

Notes:
- each item in `sheets` becomes a worksheet
- column headers are built as the union of keys across all rows
- empty sheets are still created
- response content type is XLSX and works with n8n binary download flow
