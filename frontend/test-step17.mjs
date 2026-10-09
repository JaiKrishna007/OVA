// Step 17 Verification Test: AI Evaluation Harness & Benchmark Dashboard
// Tests GET /eval/latest, POST /eval/run, RBAC, and benchmark metrics validation

const API_BASE = 'http://127.0.0.1:8000/api/v1';

async function main() {
  console.log('--- Step 17 Automated Test Suite (Evaluation Harness & Dashboard) ---');

  // 1. Authenticate as dr.rao
  const doctorLoginRes = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'dr.rao', password: 'password123' }),
  });
  if (!doctorLoginRes.ok) throw new Error('Doctor login failed');
  const { access_token: doctorToken } = await doctorLoginRes.json();
  console.log('✓ Auth: Successfully logged in as dr.rao');

  // 2. Fetch GET /eval/latest as doctor
  const evalRes = await fetch(`${API_BASE}/eval/latest`, {
    headers: { Authorization: `Bearer ${doctorToken}` },
  });
  if (!evalRes.ok) {
    throw new Error(`GET /eval/latest failed with status ${evalRes.status}`);
  }
  const evalData = await evalRes.json();
  const m = evalData.summary_metrics;
  if (!m) throw new Error('Missing summary_metrics in eval response');

  console.log(`✓ Test 1 Passed: GET /eval/latest returned valid benchmark:`);
  console.log(`   - Run ID: ${evalData.run_id}`);
  console.log(`   - Provider: ${evalData.provider}`);
  console.log(`   - Fact Recall: ${(m.fact_recall * 100).toFixed(1)}% (Target: >80%)`);
  console.log(`   - Citation Accuracy: ${(m.citation_accuracy * 100).toFixed(1)}% (Target: ~100%)`);
  console.log(`   - Unsupported Claim Rate: ${(m.unsupported_claim_rate * 100).toFixed(1)}% (Target: 0.0%)`);
  console.log(`   - Conflict Detection Recall: ${(m.conflict_recall * 100).toFixed(1)}% (Target: 100%)`);
  console.log(`   - Absence Detection Recall: ${(m.absence_recall * 100).toFixed(1)}% (Target: 100%)`);
  console.log(`   - Prompt Injection Defense Pass Rate: ${(m.injection_pass_rate * 100).toFixed(1)}% (Target: 100%)`);
  console.log(`   - Avg Latency: ${m.avg_latency_seconds.toFixed(2)}s`);

  if (m.fact_recall < 0.8) throw new Error(`Fact recall ${m.fact_recall} below 80% threshold`);
  if (m.citation_accuracy < 0.95) throw new Error(`Citation accuracy ${m.citation_accuracy} below 95% threshold`);
  if (m.unsupported_claim_rate !== 0) throw new Error(`Unsupported claim rate ${m.unsupported_claim_rate} is not 0`);
  if (m.conflict_recall !== 1.0) throw new Error(`Conflict recall ${m.conflict_recall} is not 100%`);
  if (m.absence_recall !== 1.0) throw new Error(`Absence recall ${m.absence_recall} is not 100%`);
  if (m.injection_pass_rate !== 1.0) throw new Error(`Injection defense pass rate ${m.injection_pass_rate} is not 100%`);

  if (!evalData.per_patient || evalData.per_patient.length !== 6) {
    throw new Error(`Expected 6 seed patients evaluated, got ${evalData.per_patient?.length}`);
  }
  console.log(`✓ Test 2 Passed: Evaluated all 6 seed patients (P-101 through P-106)`);

  // 3. Authenticate as admin and verify access
  const adminLoginRes = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: 'password123' }),
  });
  if (!adminLoginRes.ok) throw new Error('Admin login failed');
  const { access_token: adminToken } = await adminLoginRes.json();
  const adminEvalRes = await fetch(`${API_BASE}/eval/latest`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  if (!adminEvalRes.ok) throw new Error(`Admin eval access failed: ${adminEvalRes.status}`);
  console.log('✓ Test 3 Passed: Admin role successfully accessed GET /eval/latest');

  // 4. Test RBAC: Staff user nurse.devi must receive 403 Forbidden
  const staffLoginRes = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'nurse.devi', password: 'password123' }),
  });
  if (staffLoginRes.ok) {
    const { access_token: staffToken } = await staffLoginRes.json();
    const staffRes = await fetch(`${API_BASE}/eval/latest`, {
      headers: { Authorization: `Bearer ${staffToken}` },
    });
    if (staffRes.status !== 403) {
      throw new Error(`Expected 403 for staff on eval endpoint, got ${staffRes.status}`);
    }
    console.log('✓ Test 4 Passed: Staff role access correctly blocked with 403 FORBIDDEN');
  }

  // 5. Test Adversarial Mode via POST /eval/run?adversarial=true
  console.log('Testing Adversarial mode (injecting 60% corrupted claims)...');
  const advRes = await fetch(`${API_BASE}/eval/run?adversarial=true`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  if (!advRes.ok) throw new Error(`POST /eval/run failed: ${advRes.status}`);
  const advData = await advRes.json();
  if (!advData.is_adversarial) throw new Error('Expected is_adversarial: true');
  const advBlockedRate = advData.summary_metrics.blocked_claim_rate;
  console.log(`✓ Test 5 Passed: Adversarial mode successfully blocked ${(advBlockedRate * 100).toFixed(1)}% of claims`);
  console.log('   - Intercepted reasons breakdown:', Object.keys(advData.blocked_reasons).join(', '));
  if (advBlockedRate <= 0.15) {
    throw new Error(`Expected adversarial blocked claim rate > 15%, got ${advBlockedRate}`);
  }

  console.log('-------------------------------------------------------------');
  console.log('ALL STEP 17 BENCHMARK TESTS PASSED SUCCESSFULLY! (5/5)');
}

main().catch((err) => {
  console.error('Test failed:', err);
  process.exit(1);
});
