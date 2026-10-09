// Step 12 Patient Page & Timeline Definition of Done Verification

const BASE = 'http://127.0.0.1:8000/api/v1';

async function verifyStep12() {
  console.log('--- 1. Authenticating as dr.rao ---');
  const loginRes = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'dr.rao', password: 'password123' }),
  });
  const loginData = await loginRes.json();
  if (loginRes.status !== 200 || !loginData.access_token) {
    throw new Error(`Login failed: ${JSON.stringify(loginData)}`);
  }
  const token = loginData.access_token;
  console.log('✓ Successfully authenticated as dr.rao');

  console.log('\n--- 2. Fetching P-101 Patient Detail (Header verification) ---');
  const patientRes = await fetch(`${BASE}/patients/P-101`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const patient = await patientRes.json();
  if (patientRes.status !== 200) {
    throw new Error(`Patient fetch failed: ${JSON.stringify(patient)}`);
  }

  console.log(`✓ Name: ${patient.name} (${patient.id})`);
  console.log(`  DOB: ${patient.dob}, Sex: ${patient.sex}`);
  console.log(`  Diagnosis: ${JSON.stringify(patient.diagnosis)}`);
  console.log(`  Partner: ${patient.partner_id}`);
  console.log(`  Blood group: ${patient.blood_group}`);
  console.log(`  BMI: ${patient.bmi}`);
  console.log(`  Current Stage: ${patient.current_stage}`);
  console.log(`  Masked Phone: ${patient.phone_masked}`);

  if (!patient.partner_id || !patient.blood_group || !patient.bmi) {
    throw new Error('Header baseline fields missing');
  }

  console.log('\n--- 3. Fetching P-101 Timeline (Cycle verification) ---');
  const timelineRes = await fetch(`${BASE}/patients/P-101/timeline`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const timeline = await timelineRes.json();
  if (timelineRes.status !== 200) {
    throw new Error(`Timeline fetch failed: ${JSON.stringify(timeline)}`);
  }

  console.log(`✓ Timeline stage: ${timeline.stage}`);
  console.log(`✓ Total cycles: ${timeline.total_cycles}`);

  if (timeline.cycles.length !== 3) {
    throw new Error(`Expected 3 cycles for P-101, got ${timeline.cycles.length}`);
  }

  const [c1, c2, c3] = timeline.cycles;

  // Cycle 1: External IUI
  console.log(`\nCycle 1: ${c1.cycle_id} (#${c1.cycle_no})`);
  console.log(`  Type: ${c1.type}`);
  console.log(`  Origin: ${c1.origin_org}`);
  console.log(`  Trust: ${c1.trust_status}`);
  console.log(`  Outcome: ${c1.outcome_badge}`);

  if (c1.type !== 'IUI') {
    throw new Error(`Cycle 1 type expected IUI, got ${c1.type}`);
  }
  if (!c1.origin_org.includes('Hospital X') || c1.trust_status !== 'external_unverified') {
    throw new Error(`Cycle 1 expected external origin 'Hospital X', got ${c1.origin_org} (${c1.trust_status})`);
  }
  console.log('✓ Definition of Done: External IUI is correctly identified and badged as external.');

  // Cycle 2: IVF
  console.log(`\nCycle 2: ${c2.cycle_id} (#${c2.cycle_no})`);
  console.log(`  Type: ${c2.type}`);
  console.log(`  Outcome: ${c2.outcome_badge}`);

  // Cycle 3: IVF In Progress
  console.log(`\nCycle 3: ${c3.cycle_id} (#${c3.cycle_no})`);
  console.log(`  Type: ${c3.type}`);
  console.log(`  Start date: ${c3.start_date}`);
  console.log(`  End date: ${c3.end_date}`);
  console.log(`  Outcome: ${c3.outcome}`);
  console.log(`  Outcome Badge: ${c3.outcome_badge}`);

  const isCycle3InProgress = !c3.end_date && (!c3.outcome || c3.outcome_badge === 'In Progress');
  if (!isCycle3InProgress) {
    throw new Error(`Cycle 3 expected to be in progress, got end_date: ${c3.end_date}, outcome: ${c3.outcome}`);
  }
  console.log('✓ Definition of Done: Cycle 3 is correctly marked as in progress.');

  console.log('\n--- 4. Testing Cycle Drill-Down API (/cycles/CY-P101-2) ---');
  const cycleDetailRes = await fetch(`${BASE}/patients/P-101/cycles/CY-P101-2`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const cycleDetail = await cycleDetailRes.json();
  if (cycleDetailRes.status !== 200) {
    throw new Error(`Cycle detail fetch failed: ${JSON.stringify(cycleDetail)}`);
  }
  console.log(`✓ Cycle 2 Drill-Down loaded: ${cycleDetail.type} (${cycleDetail.outcome_badge})`);
  console.log(`  OPU retrieved: ${cycleDetail.opu ? cycleDetail.opu.oocytes_retrieved : 'N/A'}`);
  console.log(`  Embryos count: ${cycleDetail.embryos.length}`);
  console.log(`  Transfers count: ${cycleDetail.transfers.length}`);
  console.log(`  Pregnancy Outcome: ${cycleDetail.pregnancy_outcome ? cycleDetail.pregnancy_outcome.result : 'N/A'}`);

  console.log('\n===============================================================');
  console.log('✓ DEFINITION OF DONE FULLY SATISFIED:');
  console.log('  P-101 shows 3 cycles with the external IUI badged');
  console.log('  and cycle 3 marked as in progress.');
  console.log('===============================================================');
}

verifyStep12().catch((err) => {
  console.error('Step 12 Verification Failed:', err);
  process.exit(1);
});
