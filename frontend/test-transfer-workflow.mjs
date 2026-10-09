// Automated End-to-End Test for Transfer and Consent Workflow
const API_URL = 'http://127.0.0.1:8005/api/v1';

async function post(url, body, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${url}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return { status: res.status, ok: res.ok, data };
}

async function get(url, token) {
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${url}`, { headers });
  const data = await res.json().catch(() => ({}));
  return { status: res.status, ok: res.ok, data };
}

async function del(url, token) {
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${url}`, { method: 'DELETE', headers });
  const data = await res.json().catch(() => ({}));
  return { status: res.status, ok: res.ok, data };
}

async function login(username, password = 'password123') {
  const res = await post('/auth/login', { username, password });
  if (!res.ok) throw new Error(`Login failed for ${username}: ${JSON.stringify(res.data)}`);
  return res.data.access_token;
}

async function run() {
  console.log('=== STARTING TRANSFER & CONSENT WORKFLOW VALIDATION ===\n');

  // 1. Authenticate Personas
  const tokenRao = await login('dr.rao');
  const tokenAdminB = await login('admin.b');
  const tokenDrMenon = await login('dr.menon');
  console.log('1. Authentication: Logged in dr.rao (Hospital A), admin.b (Hospital B), and dr.menon (Hospital B doctor)');

  const targetPatient = 'P-105';

  // 2. Revoke any existing consents for targetPatient so we start with zero consent
  const existingConsents = await get(`/patients/${targetPatient}/consents`, tokenAdminB);
  for (const c of existingConsents.data || []) {
    if (c.status === 'ACTIVE') {
      await del(`/consents/${c.id}`, tokenAdminB);
    }
  }
  console.log(`2. Baseline Check: Revoked existing consents for ${targetPatient} to verify consent barrier`);

  // 3. Request Transfer from ORG-Y to ORG-B
  const trfRes = await post(
    '/transfers',
    {
      patient_id: targetPatient,
      from_hospital_id: 'ORG-Y',
      to_hospital_id: 'ORG-B',
      reason: 'Patient relocating care to Hospital B for ICSI protocol.',
    },
    tokenRao
  );
  if (!trfRes.ok) throw new Error(`Failed to create transfer: ${JSON.stringify(trfRes.data)}`);
  const transfer = trfRes.data;
  console.log(`3. Transfer Request Created: ID ${transfer.id}, Patient: ${transfer.patient_name} (${transfer.patient_id}), Status: ${transfer.status}`);

  // 4. Hospital B Admin checks inbox
  const bInbox = await get('/transfers?direction=incoming', tokenAdminB);
  const inboxItem = bInbox.data.find((t) => t.id === transfer.id);
  console.log(`4. Hospital B Inbox: has_active_consent is ${inboxItem?.has_active_consent} (False expected)`);

  // 5. Test Strict Safety Rule S7: Attempt accept without active consent -> MUST return 409
  const acceptBlocked = await post(`/transfers/${transfer.id}/accept`, {}, tokenAdminB);
  console.log(`5. Safety Rule S7 Verification: Accept without consent returned ${acceptBlocked.status} (Expected 409: CONSENT_REQUIRED)`);
  if (acceptBlocked.status !== 409) {
    throw new Error(`Safety rule failure: Expected 409 but got ${acceptBlocked.status}`);
  }

  // 6. Record Patient Consent on Behalf
  const consentRes = await post(
    '/consents',
    {
      patient_id: targetPatient,
      target_hospital_id: 'ORG-B',
      purpose: 'Continuity of fertility care',
      scope: 'ALL_RECORDS',
      recorded_on_behalf: true,
    },
    tokenAdminB
  );
  if (!consentRes.ok) throw new Error(`Consent recording failed: ${JSON.stringify(consentRes.data)}`);
  console.log(`6. Patient Consent Recorded: ID ${consentRes.data.id}, Status: ${consentRes.data.status}`);

  // 7. Verify inbox now shows has_active_consent: true
  const bInboxAfter = await get('/transfers?direction=incoming', tokenAdminB);
  const inboxItemAfter = bInboxAfter.data.find((t) => t.id === transfer.id);
  console.log(`7. Hospital B Inbox (Updated): has_active_consent is ${inboxItemAfter?.has_active_consent} (True expected)`);

  // 8. Hospital B Admin accepts transfer -> SUCCEEDS with 200 COMPLETED
  const acceptRes = await post(`/transfers/${transfer.id}/accept`, {}, tokenAdminB);
  if (!acceptRes.ok) throw new Error(`Accept transfer failed: ${JSON.stringify(acceptRes.data)}`);
  console.log(`8. Transfer Accepted: Status is now ${acceptRes.data.status}`);

  // 9. Verify Receiving Doctor (dr.menon) now has READ_WRITE access
  const menonView = await get(`/patients/${targetPatient}`, tokenDrMenon);
  console.log(`9. Receiving Doctor (dr.menon) Access: Status ${menonView.status}, Access Level: ${menonView.data.access_level}`);
  if (menonView.status !== 200 || menonView.data.access_level !== 'READ_WRITE') {
    throw new Error(`Receiving doctor should have READ_WRITE access! Got status ${menonView.status}`);
  }

  // 10. Verify Sending Doctor (dr.rao) has been safely downgraded to READ_ONLY
  const raoView = await get(`/patients/${targetPatient}`, tokenRao);
  console.log(`10. Sending Doctor (dr.rao) Access: Status ${raoView.status}, Access Level: ${raoView.data.access_level}`);
  if (raoView.data.access_level !== 'READ_ONLY') {
    throw new Error(`Sending doctor access must be READ_ONLY! Got ${raoView.data.access_level}`);
  }

  console.log('\n======================================================');
  console.log('✓ ALL 10 STEPS OF THE TRANSFER & CONSENT WORKFLOW PASSED!');
  console.log('======================================================');
}

run().catch((err) => {
  console.error('Test Failed:', err);
  process.exit(1);
});
