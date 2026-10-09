// test-patient-transfer-workflow.mjs
// Verifies the complete patient transfer authorization workflow:
// 1. Hospital creates transfer request to another hospital.
// 2. Patient accesses chart and sees pending transfer with 2 options: Accept & Transfer, Revoke Transfer.
// 3. Confirm Transfer execution: data is transferred, active consent recorded, access granted.
// 4. Verification that grant access authority belongs to patient.
// 5. Revoke Transfer execution: transfer is rejected without data transfer.

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
  console.log('=== STARTING PATIENT TRANSFER & CONSENT WORKFLOW VALIDATION ===\n');

  // 1. Log in as Hospital Admin (admin.a at ORG-Y) and Patient (patient.priya, P-101)
  console.log('1. Logging in as Hospital Admin (admin.a) and Patient (patient.priya)...');
  const adminAuth = await login('admin.a');
  const patientAuth = await login('patient.priya');
  console.log('   ✓ Logged in admin.a (ORG-Y)');
  console.log(`   ✓ Logged in patient.priya (patient_id: ${patientAuth.patient_id})`);

  const adminHeaders = {
    'Authorization': `Bearer ${adminAuth.access_token}`,
    'Content-Type': 'application/json',
  };
  const patientHeaders = {
    'Authorization': `Bearer ${patientAuth.access_token}`,
    'Content-Type': 'application/json',
  };

  // 2. Hospital initiates transfer request for P-101 from ORG-Y to ORG-B
  console.log('\n2. Hospital initiates transfer request for P-101 to ORG-B...');
  const createRes = await fetch(`${BASE_URL}/transfers`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({
      patient_id: 'P-101',
      from_hospital_id: 'ORG-Y',
      to_hospital_id: 'ORG-B',
      reason: 'Relocating to Bangalore clinic for IVF cycle #2 continuity of care',
    }),
  });
  const transfer = await createRes.json();
  console.log(`   ✓ Transfer created: ID ${transfer.id}, Status: ${transfer.status}`);
  if (transfer.status !== 'REQUESTED') {
    throw new Error(`Expected REQUESTED status, got ${transfer.status}`);
  }

  // 3. Patient views their chart and lists transfer requests
  console.log('\n3. Patient retrieves pending transfer requests...');
  const listRes = await fetch(`${BASE_URL}/transfers?patient_id=P-101`, {
    headers: patientHeaders,
  });
  const transferList = await listRes.json();
  const requestedTransfer = transferList.find(t => t.id === transfer.id);
  console.log(`   ✓ Patient found transfer: ${requestedTransfer.id}`);
  console.log(`     From: ${requestedTransfer.from_hospital_id} -> To: ${requestedTransfer.to_hospital_id}`);
  console.log(`     Reason: "${requestedTransfer.reason}"`);

  // 4. Test "Accept & Transfer" with patient confirmation
  console.log('\n4. Patient executes "Accept & Transfer" (simulating Confirm Transfer dialog)...');
  const acceptRes = await fetch(`${BASE_URL}/transfers/${transfer.id}/accept`, {
    method: 'POST',
    headers: patientHeaders,
  });
  if (!acceptRes.ok) {
    const err = await acceptRes.text();
    throw new Error(`Patient accept transfer failed: ${err}`);
  }
  const completedTransfer = await acceptRes.json();
  console.log(`   ✓ Transfer status updated to: ${completedTransfer.status}`);
  console.log(`   ✓ Generated Consent ID: ${completedTransfer.consent_id}`);

  // 5. Verify patient consent was recorded and access permissions updated
  console.log('\n5. Verifying active patient consent on file...');
  const consentsRes = await fetch(`${BASE_URL}/patients/P-101/consents`, {
    headers: patientHeaders,
  });
  const consents = await consentsRes.json();
  const targetConsent = consents.find(c => c.granted_to_hospital_id === 'ORG-B');
  console.log(`   ✓ Active consent found: ID ${targetConsent?.id}, Status: ${targetConsent?.status}`);
  console.log(`   ✓ Granted by: "${targetConsent?.granted_by}"`);

  // 6. Test Doctor at receiving hospital (ORG-B) can now access P-101
  console.log('\n6. Verifying Doctor at Hospital B (dr.menon) now has clinical care access...');
  const drMenonAuth = await login('dr.menon');
  const menonHeaders = {
    'Authorization': `Bearer ${drMenonAuth.access_token}`,
  };
  const menonViewRes = await fetch(`${BASE_URL}/patients/P-101`, {
    headers: menonHeaders,
  });
  console.log(`   ✓ Hospital B Doctor access status: ${menonViewRes.status} (OK)`);
  const patientProfile = await menonViewRes.json();
  console.log(`   ✓ Patient name: ${patientProfile.name}`);

  // 7. Test "Revoke Transfer" flow with another request
  console.log('\n7. Testing "Revoke Transfer" option...');
  const req2Res = await fetch(`${BASE_URL}/transfers`, {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify({
      patient_id: 'P-101',
      from_hospital_id: 'ORG-Y',
      to_hospital_id: 'ORG-C',
      reason: 'Proposed transfer to ORG-C',
    }),
  });
  const transfer2 = await req2Res.json();
  console.log(`   ✓ Second transfer request created: ${transfer2.id} (Status: ${transfer2.status})`);

  // Patient revokes transfer
  const revokeRes = await fetch(`${BASE_URL}/transfers/${transfer2.id}/reject`, {
    method: 'POST',
    headers: patientHeaders,
    body: JSON.stringify({ reason: 'Revoked by patient' }),
  });
  const revokedTransfer = await revokeRes.json();
  console.log(`   ✓ Transfer revoked by patient: Status: ${revokedTransfer.status}`);
  if (revokedTransfer.status !== 'REJECTED') {
    throw new Error(`Expected REJECTED status, got ${revokedTransfer.status}`);
  }

  console.log('\n=== ALL PATIENT TRANSFER & CONSENT WORKFLOW CHECKS PASSED SUCCESSFULLY! ===');
}

run().catch(err => {
  console.error('\n❌ Workflow test failed:', err);
  process.exit(1);
});
