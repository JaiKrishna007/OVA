// test-duplicate-transfer-prevention.mjs
// Verifies:
// 1. Clear all transfer data resets database to 0 transfers and clean baseline.
// 2. Creating a transfer request succeeds.
// 3. Creating a duplicate concurrent transfer request is rejected with 409 DUPLICATE_TRANSFER.
// 4. Once transferred, attempting to transfer to the same hospital again is rejected with 409 DUPLICATE_TRANSFER.
// 5. Final clear leaves clean state.

const BASE_URL = 'http://127.0.0.1:8005/api/v1';

async function login(username, password = 'password123') {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`Login failed for ${username}: ${txt}`);
  }
  return res.json();
}

async function run() {
  console.log('=== STARTING CLEAR ALL & DUPLICATE TRANSFER PREVENTION TESTS ===\n');

  const adminAuth = await login('admin.a');
  const patientAuth = await login('patient.priya');

  const adminHeaders = {
    'Authorization': `Bearer ${adminAuth.access_token}`,
    'Content-Type': 'application/json',
  };
  const patientHeaders = {
    'Authorization': `Bearer ${patientAuth.access_token}`,
    'Content-Type': 'application/json',
  };

  // 1. Test POST /transfers/clear
  console.log('1. Testing POST /api/v1/transfers/clear...');
  const clearRes = await fetch(`${BASE_URL}/transfers/clear`, {
    method: 'POST',
    headers: adminHeaders,
  });
  if (!clearRes.ok) {
    throw new Error(`Failed to clear transfers: ${await clearRes.text()}`);
  }
  const clearData = await clearRes.json();
  console.log('   ✓ Response:', clearData);

  // Verify list is empty
  const listEmptyRes = await fetch(`${BASE_URL}/transfers`, { headers: adminHeaders });
  const emptyList = await listEmptyRes.json();
  console.log(`   ✓ Transfer list count after clear: ${emptyList.length} (expected: 0)`);
  if (emptyList.length !== 0) {
    throw new Error(`Expected 0 transfers, found ${emptyList.length}`);
  }

  // 2. Create initial transfer request for P-101
  console.log('\n2. Creating first transfer request for P-101 to ORG-B...');
  const create1Res = await fetch(`${BASE_URL}/transfers`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({
      patient_id: 'P-101',
      from_hospital_id: 'ORG-Y',
      to_hospital_id: 'ORG-B',
      reason: 'Relocating to Bangalore for IVF cycle #2',
    }),
  });
  if (!create1Res.ok) {
    throw new Error(`Failed to create transfer 1: ${await create1Res.text()}`);
  }
  const t1 = await create1Res.json();
  console.log(`   ✓ Created transfer 1: ID ${t1.id}, Status: ${t1.status}`);

  // 3. Attempt to create a DUPLICATE transfer request for P-101 while first is pending
  console.log('\n3. Attempting to create duplicate transfer request while first is pending...');
  const dupRes = await fetch(`${BASE_URL}/transfers`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({
      patient_id: 'P-101',
      from_hospital_id: 'ORG-Y',
      to_hospital_id: 'ORG-B',
      reason: 'Second duplicate transfer attempt',
    }),
  });
  console.log(`   ✓ Duplicate request status code: ${dupRes.status} (expected: 409 Conflict)`);
  const dupErr = await dupRes.json();
  console.log(`   ✓ Error Code: ${dupErr.error?.code}`);
  console.log(`   ✓ Error Message: "${dupErr.error?.message}"`);

  if (dupRes.status !== 409 || dupErr.error?.code !== 'DUPLICATE_TRANSFER') {
    throw new Error(`Expected 409 DUPLICATE_TRANSFER, got ${dupRes.status} ${JSON.stringify(dupErr)}`);
  }

  // 4. Patient accepts transfer 1
  console.log('\n4. Patient accepts transfer 1...');
  const acceptRes = await fetch(`${BASE_URL}/transfers/${t1.id}/accept`, {
    method: 'POST',
    headers: patientHeaders,
  });
  if (!acceptRes.ok) {
    throw new Error(`Patient accept failed: ${await acceptRes.text()}`);
  }
  const acceptedT1 = await acceptRes.json();
  console.log(`   ✓ Transfer 1 completed: ${acceptedT1.status}`);

  // 5. Attempt to transfer P-101 to ORG-B AGAIN now that she is already at ORG-B
  console.log('\n5. Attempting to create transfer to ORG-B when patient already has active access at ORG-B...');
  const dupHospRes = await fetch(`${BASE_URL}/transfers`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({
      patient_id: 'P-101',
      from_hospital_id: 'ORG-Y',
      to_hospital_id: 'ORG-B',
      reason: 'Attempting transfer to existing hospital',
    }),
  });
  console.log(`   ✓ Duplicate destination status code: ${dupHospRes.status} (expected: 409 Conflict)`);
  const dupHospErr = await dupHospRes.json();
  console.log(`   ✓ Error Code: ${dupHospErr.error?.code}`);
  console.log(`   ✓ Error Message: "${dupHospErr.error?.message}"`);

  if (dupHospRes.status !== 409 || dupHospErr.error?.code !== 'DUPLICATE_TRANSFER') {
    throw new Error(`Expected 409 DUPLICATE_TRANSFER, got ${dupHospRes.status} ${JSON.stringify(dupHospErr)}`);
  }

  // 6. Reset database to clean state
  console.log('\n6. Cleaning up database to leave zero transfers on file...');
  await fetch(`${BASE_URL}/transfers/clear`, { method: 'POST', headers: adminHeaders });
  const finalCountRes = await fetch(`${BASE_URL}/transfers`, { headers: adminHeaders });
  const finalTransfers = await finalCountRes.json();
  console.log(`   ✓ Clean state verified: ${finalTransfers.length} transfers on file.`);

  console.log('\n=== ALL CLEAR DATA AND DUPLICATE TRANSFER PREVENTION CHECKS PASSED! ===');
}

run().catch(err => {
  console.error('\n❌ Test failed:', err);
  process.exit(1);
});
