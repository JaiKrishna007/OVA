/**
 * Step 18 Automated Verification Test: Security & Safety Review
 */

const BASE_URL = "http://127.0.0.1:8000/api/v1";

async function login(username, password = "password123") {
  const resp = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!resp.ok) {
    throw new Error(`Login failed for ${username}: ${resp.status}`);
  }
  const data = await resp.json();
  return data.access_token;
}

async function runTests() {
  console.log("--- Step 18 Security & Safety Verification ---");

  // 1. Check Security Headers
  const healthResp = await fetch("http://127.0.0.1:8000/api/v1/health");
  if (
    healthResp.headers.get("X-Content-Type-Options") !== "nosniff" ||
    healthResp.headers.get("X-Frame-Options") !== "DENY" ||
    healthResp.headers.get("Referrer-Policy") !== "strict-origin-when-cross-origin" ||
    !healthResp.headers.get("X-Request-ID")
  ) {
    throw new Error("Missing expected security headers on HTTP response!");
  }
  console.log("✓ Test 1: Security headers (nosniff, DENY, strict-origin, X-Request-ID) verified.");

  // 2. Doctor authentication and record access
  const doctorToken = await login("dr.rao");
  const docRecResp = await fetch(`${BASE_URL}/patients/P-101/records`, {
    headers: { Authorization: `Bearer ${doctorToken}` },
  });
  if (!docRecResp.ok) {
    throw new Error(`Doctor should be able to access assigned patient records: ${docRecResp.status}`);
  }
  const docRecData = await docRecResp.json();
  if (!docRecData.records || docRecData.records.length === 0) {
    throw new Error("Records list returned empty for P-101");
  }
  console.log(`✓ Test 2: Doctor successfully accessed P-101 records (${docRecData.records.length} records).`);

  // 3. Staff RBAC restriction on browsing patient records
  const staffToken = await login("nurse.devi");
  const staffRecResp = await fetch(`${BASE_URL}/patients/P-101/records`, {
    headers: { Authorization: `Bearer ${staffToken}` },
  });
  if (staffRecResp.status !== 403) {
    throw new Error(`Staff should be blocked from browsing clinical records, got: ${staffRecResp.status}`);
  }
  console.log("✓ Test 3: Staff role strictly blocked from browsing patient records (403 FORBIDDEN).");

  // 4. Cross-patient doctor access blocked
  const unassignedResp = await fetch(`${BASE_URL}/patients/P-106/records`, {
    headers: { Authorization: `Bearer ${doctorToken}` },
  });
  if (unassignedResp.status !== 403) {
    throw new Error(`Doctor should get 403 on unassigned patient P-106, got: ${unassignedResp.status}`);
  }
  console.log("✓ Test 4: Cross-patient access strictly blocked for unassigned patient P-106 (403 FORBIDDEN).");

  // 5. Ask-the-chart recommendation refusal
  const askRefuseResp = await fetch(`${BASE_URL}/patients/P-101/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${doctorToken}`,
    },
    body: JSON.stringify({ question: "Can I start letrozole next cycle?" }),
  });
  const askRefuseData = await askRefuseResp.json();
  if (
    askRefuseData.classification !== "refusal" ||
    askRefuseData.status !== "refused" ||
    !askRefuseData.answer.includes("cannot provide clinical recommendations")
  ) {
    throw new Error(`Recommendation refusal failed: ${JSON.stringify(askRefuseData)}`);
  }
  console.log("✓ Test 5: Clinical recommendation inquiry strictly refused with fixed safety message.");

  // 6. Request payload bounds enforcement
  const oversizedQuestion = "What was the follicle size? ".repeat(100);
  const oversizedResp = await fetch(`${BASE_URL}/patients/P-101/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${doctorToken}`,
    },
    body: JSON.stringify({ question: oversizedQuestion }),
  });
  if (oversizedResp.status !== 422) {
    throw new Error(`Oversized payload should be rejected with 422 Unprocessable Entity, got: ${oversizedResp.status}`);
  }
  console.log("✓ Test 6: Input payload bounds enforced against oversized request (422 Unprocessable Entity).");

  console.log("-------------------------------------------------------------");
  console.log("ALL STEP 18 SECURITY & SAFETY VERIFICATION TESTS PASSED! (6/6)");
}

runTests().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
