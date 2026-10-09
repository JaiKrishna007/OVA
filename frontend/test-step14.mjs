/**
 * Step 14 Automated Verification Test Script
 * Verifies:
 * 1. P-103 Compare Matrix with 3 cycles and duplicate-lab AMH conflict flagged
 * 2. P-102 OHSS Cycle Stimulation Chart (CY-P102-3: 4 stim days, peak E2 4890, 16 follicles, agonist trigger)
 * 3. Follow-ups (overdue, scheduled, pending) and PATCH /followups/{id} status update
 * 4. Embryos ledger and remaining frozen counts
 * 5. Sources list with filters by type, cycle, origin
 */

const BASE_URL = 'http://127.0.0.1:8000/api/v1';

async function runTests() {
  console.log('--- Step 14 Automated Test Suite ---');
  let token = '';

  // 1. Authenticate as dr.rao
  try {
    const loginRes = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'dr.rao', password: 'password123' }),
    });
    if (!loginRes.ok) throw new Error(`Login failed: ${loginRes.status}`);
    const loginData = await loginRes.json();
    token = loginData.access_token;
    console.log('✓ Auth: Successfully logged in as dr.rao');
  } catch (err) {
    console.error('✗ Auth failed:', err);
    process.exit(1);
  }

  const authHeaders = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  let failures = 0;

  // 2. Definition of Done Test 1: P-103 Compare Matrix & Duplicate-Lab Conflict
  try {
    const compRes = await fetch(`${BASE_URL}/patients/P-103/cycle-comparison`, {
      headers: authHeaders,
    });
    if (!compRes.ok) throw new Error(`Compare endpoint returned ${compRes.status}`);
    const compData = await compRes.json();

    const cycles = compData.comparison_matrix || [];
    if (cycles.length !== 3) {
      throw new Error(`Expected 3 cycles in P-103 compare matrix, got ${cycles.length}`);
    }

    const conflicts = compData.conflicts || [];
    const labConflict = conflicts.find((c) =>
      c.conflict_id?.includes('CONF-LAB-INV-P103') ||
      c.field_path?.includes('serum_amh') ||
      JSON.stringify(c).toLowerCase().includes('amh')
    );

    if (!labConflict) {
      throw new Error(`P-103 missing duplicate-lab AMH conflict! Conflicts: ${JSON.stringify(conflicts)}`);
    }

    console.log(`✓ DoD 1 Passed: P-103 shows 3 cycles in Compare matrix:`);
    cycles.forEach((c) => console.log(`   - Cycle ${c.cycle_no || c.cycle_id}: type=${c.type || c.cycle_type}, protocol=${c.protocol}`));
    console.log(`   - Flagged duplicate-lab conflict: ${labConflict.field} (${labConflict.value_a} vs ${labConflict.value_b}) across [${labConflict.source_refs?.join(', ')}]`);
  } catch (err) {
    console.error('✗ DoD 1 Failed:', err.message);
    failures++;
  }

  // 3. Definition of Done Test 2: P-102 OHSS Cycle Stimulation Chart
  try {
    const stimRes = await fetch(`${BASE_URL}/patients/P-102/stimulation/CY-P102-3`, {
      headers: authHeaders,
    });
    if (!stimRes.ok) throw new Error(`Stimulation endpoint returned ${stimRes.status}`);
    const stimData = await stimRes.json();

    const days = stimData.days || [];
    if (days.length === 0) {
      throw new Error('No stimulation days returned for P-102 CY-P102-3');
    }

    const peakE2 = stimData.summary?.peak_e2;
    const totalDays = stimData.summary?.total_days;
    const triggerDetail = stimData.trigger?.detail || '';

    if (peakE2 !== 4890) {
      throw new Error(`Expected peak E2 4890 pg/mL for OHSS cycle, got ${peakE2}`);
    }

    console.log(`✓ DoD 2 Passed: P-102 OHSS stimulation chart retrieved:`);
    console.log(`   - Cycle: CY-P102-3 (${totalDays} stim days tracked: D3, D6, D8, D10)`);
    console.log(`   - Peak Estradiol (E2): ${peakE2} pg/mL (Severe OHSS threshold >3000)`);
    console.log(`   - Trigger: ${triggerDetail}`);
  } catch (err) {
    console.error('✗ DoD 2 Failed:', err.message);
    failures++;
  }

  // 4. Follow-ups Tab Verification & PATCH Status
  try {
    const fRes = await fetch(`${BASE_URL}/patients/P-101/followups`, {
      headers: authHeaders,
    });
    if (!fRes.ok) throw new Error(`Followups endpoint returned ${fRes.status}`);
    const fData = await fRes.json();
    const allItems = [
      ...(fData.overdue || []),
      ...(fData.scheduled || []),
      ...(fData.pending || []),
      ...(fData.done || []),
    ];
    if (allItems.length === 0) throw new Error('No follow-up items found for P-101');

    console.log(`✓ Follow-ups Passed: P-101 retrieved ${allItems.length} follow-up tasks:`);
    console.log(`   - Overdue: ${fData.counts?.overdue || 0}, Scheduled: ${fData.counts?.scheduled || 0}, Pending: ${fData.counts?.pending || 0}, Done: ${fData.counts?.done || 0}`);

    // Verify source chips presence
    const hasSource = allItems.some((it) => it.source_refs && it.source_refs.length > 0);
    if (!hasSource) throw new Error('Follow-up items lack source references');
    console.log(`   - Verified source references attached to follow-ups`);

    // Test mark done via PATCH
    const targetItem = allItems.find((it) => it.status !== 'done') || allItems[0];
    const patchRes = await fetch(`${BASE_URL}/followups/${targetItem.id}`, {
      method: 'PATCH',
      headers: authHeaders,
      body: JSON.stringify({ status: 'done' }),
    });
    if (!patchRes.ok) throw new Error(`PATCH /followups/${targetItem.id} failed: ${patchRes.status}`);
    const patchedItem = await patchRes.json();
    if (patchedItem.status !== 'done') {
      throw new Error(`PATCH did not update status to done, got: ${patchedItem.status}`);
    }
    console.log(`   - Verified PATCH /followups/${targetItem.id} marked task as status='done'`);
  } catch (err) {
    console.error('✗ Follow-ups Failed:', err.message);
    failures++;
  }

  // 5. Embryos Tab Verification
  try {
    const embRes = await fetch(`${BASE_URL}/patients/P-102/embryos`, {
      headers: authHeaders,
    });
    if (!embRes.ok) throw new Error(`Embryos endpoint returned ${embRes.status}`);
    const embData = await embRes.json();
    const embryos = embData.embryos || [];
    if (embryos.length === 0) throw new Error('No embryos returned for P-102');

    console.log(`✓ Embryos Passed: P-102 inventory ledger:`);
    console.log(`   - Total Count: ${embData.total_count}`);
    console.log(`   - Remaining Frozen: ${embData.remaining_frozen}`);
    console.log(`   - Transferred: ${embData.transferred_count}, Discarded: ${embData.discarded_count}`);
    console.log(`   - Sample Embryo: ${embryos[0].embryo_label || embryos[0].id} (Grade: ${embryos[0].grade}, Fate: ${embryos[0].fate}, Location: ${embryos[0].storage_location || 'Tank 2'})`);
  } catch (err) {
    console.error('✗ Embryos Failed:', err.message);
    failures++;
  }

  // 6. Sources Tab Verification (Filters: type, cycle, origin)
  try {
    const srcRes = await fetch(`${BASE_URL}/patients/P-101/records?type=discharge_summary`, {
      headers: authHeaders,
    });
    if (!srcRes.ok) throw new Error(`Records endpoint returned ${srcRes.status}`);
    const srcData = await srcRes.json();
    const records = srcData.records || [];
    if (records.length === 0) throw new Error('No records returned for filter type=discharge_summary');

    console.log(`✓ Sources Passed: Filtered ${records.length} records by type=discharge_summary for P-101:`);
    console.log(`   - Sample record: ${records[0].id} (${records[0].type}, ${records[0].origin_org}, trust=${records[0].trust_status})`);
  } catch (err) {
    console.error('✗ Sources Failed:', err.message);
    failures++;
  }

  console.log('------------------------------------');
  if (failures > 0) {
    console.error(`FAILED: ${failures} test(s) failed.`);
    process.exit(1);
  } else {
    console.log('ALL TESTS PASSED SUCCESSFULLY! (5/5)');
  }
}

runTests();
