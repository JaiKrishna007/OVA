const BASE = 'http://127.0.0.1:8000/api/v1';

async function testDefinitionOfDone() {
  console.log('--- 1. Testing Login as dr.rao ---');
  const loginRes = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'dr.rao', password: 'password123' }),
  });
  const loginData = await loginRes.json();
  if (loginRes.status !== 200 || !loginData.access_token) {
    throw new Error(`Login failed: ${JSON.stringify(loginData)}`);
  }
  console.log('✓ Successfully logged in as dr.rao. Token received.');
  console.log(`  User: ${loginData.user.username}, Role: ${loginData.user.role}, Org: ${loginData.user.org_id}`);
  const token = loginData.access_token;

  console.log('\n--- 2. Testing Login Failure Handling ---');
  const failRes = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'dr.rao', password: 'wrongpassword' }),
  });
  const failData = await failRes.json();
  if (failRes.status !== 401 || !failData.error || failData.error.code !== 'INVALID_CREDENTIALS') {
    throw new Error(`Expected 401 with INVALID_CREDENTIALS, got: ${failRes.status} ${JSON.stringify(failData)}`);
  }
  console.log(`✓ Login failure correctly handled: ${failData.error.code} - "${failData.error.message}"`);

  console.log('\n--- 3. Testing Patient Search "priya" ---');
  const searchRes = await fetch(`${BASE}/patients?q=priya`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const searchResults = await searchRes.json();
  if (!Array.isArray(searchResults) || searchResults.length === 0) {
    throw new Error(`Search for "priya" returned no results: ${JSON.stringify(searchResults)}`);
  }
  const priya = searchResults.find(p => p.id === 'P-101');
  if (!priya) {
    throw new Error(`P-101 not found in search results: ${JSON.stringify(searchResults)}`);
  }
  console.log(`✓ Found patient: ${priya.name} (${priya.id})`);
  console.log(`  Stage: ${priya.current_stage}`);
  console.log(`  Phone (masked): ${priya.phone_masked}`);
  console.log(`  Source Refs: ${priya.source_refs.join(', ')}`);

  console.log('\n--- 4. Testing Open Patient Route (P-101 Detail) ---');
  const detailRes = await fetch(`${BASE}/patients/P-101`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const detailData = await detailRes.json();
  if (detailRes.status !== 200 || detailData.id !== 'P-101') {
    throw new Error(`Patient detail fetch failed: ${detailRes.status} ${JSON.stringify(detailData)}`);
  }
  console.log(`✓ Successfully opened patient route for P-101: ${detailData.name}`);

  console.log('\n--- 5. Testing 403 Forbidden Handling on Unassigned P-106 ---');
  const forbiddenRes = await fetch(`${BASE}/patients/P-106`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const forbiddenData = await forbiddenRes.json();
  if (forbiddenRes.status !== 403 || !forbiddenData.error || forbiddenData.error.code !== 'FORBIDDEN') {
    throw new Error(`Expected 403 FORBIDDEN on P-106, got: ${forbiddenRes.status} ${JSON.stringify(forbiddenData)}`);
  }
  console.log(`✓ 403 Forbidden correctly returned for P-106: ${forbiddenData.error.code} - "${forbiddenData.error.message}"`);

  console.log('\n=============================================');
  console.log('✓ ALL DEFINITION OF DONE REQUIREMENTS PASSED!');
  console.log('=============================================');
}

testDefinitionOfDone().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
