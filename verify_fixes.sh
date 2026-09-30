#!/usr/bin/env bash
# Checks the dashboard fixes against the running stack (docker compose up).
set -euo pipefail
API=${API:-http://localhost:8000/api/v1}

token() {
  curl -sf "$API/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\",\"password\":\"$2\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])'
}
get() { curl -sf "$API/$2" -H "Authorization: Bearer $1"; }
check() { # name, actual, expected
  if [ "$2" = "$3" ]; then echo "PASS $1"; else echo "FAIL $1: got $2, want $3"; FAILED=1; fi
}
field() { python3 -c "import sys,json;print(json.load(sys.stdin)$1)"; }

FAILED=0
A=$(token sunset@propertyflow.com client_a_2024)
B=$(token ocean@propertyflow.com client_b_2024)

# Same property ID in both tenants must return each tenant's own data, in either order (cache isolation).
check "sunset prop-001 total"  "$(get "$A" 'dashboard/summary?property_id=prop-001' | field "['total_revenue']")" "2250.0"
check "ocean prop-001 total"   "$(get "$B" 'dashboard/summary?property_id=prop-001' | field "['total_revenue']")" "0.0"
check "sunset prop-001 again"  "$(get "$A" 'dashboard/summary?property_id=prop-001' | field "['total_revenue']")" "2250.0"
check "sunset cannot see prop-004" "$(get "$A" 'dashboard/summary?property_id=prop-004' | field "['reservations_count']")" "0"

# March in Paris local time includes res-tz-1 (2024-02-29 23:30 UTC = 2024-03-01 00:30 Paris).
check "sunset prop-001 March" "$(get "$A" 'dashboard/summary?property_id=prop-001&month=3&year=2024' | field "['total_revenue']")" "2250.0"
check "sunset prop-001 Feb"   "$(get "$A" 'dashboard/summary?property_id=prop-001&month=2&year=2024' | field "['total_revenue']")" "0.0"

# Property list is scoped to the tenant.
ids() { python3 -c 'import sys,json;print(",".join(p["id"] for p in json.load(sys.stdin)))'; }
check "sunset properties" "$(get "$A" 'dashboard/properties' | ids)" "prop-001,prop-002,prop-003"
check "ocean properties"  "$(get "$B" 'dashboard/properties' | ids)" "prop-001,prop-004,prop-005"

exit $FAILED
