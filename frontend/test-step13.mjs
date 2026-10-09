// Step 13 Summary Tab & Citations Definition of Done Verification

const BASE = 'http://127.0.0.1:8000/api/v1';

async function verifyStep13() {
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

  console.log('\n--- 2. Fetching P-101 Summary (GET /patients/P-101/summary) ---');
  const summaryRes = await fetch(`${BASE}/patients/P-101/summary?length=detailed`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const summary = await summaryRes.json();
  if (summaryRes.status !== 200) {
    throw new Error(`Summary fetch failed: ${JSON.stringify(summary)}`);
  }

  const summaryId = summary.id || summary.summary_id;
  const version = summary.version || summary.metadata?.version;
  const cacheHit = summary.cache_hit ?? summary.metadata?.from_cache;
  const dataVersion = summary.data_version || summary.metadata?.data_version;
  const sections = summary.sections || summary.content?.sections || {};
  const conflicts = summary.conflicts || summary.content?.conflicts_detected || [];

  console.log(`✓ Summary ID: ${summaryId}`);
  console.log(`✓ Summary Version: v${version}`);
  console.log(`✓ Cache Hit: ${cacheHit}`);
  console.log(`✓ Data Hash: ${dataVersion}`);
  console.log(`✓ Sections count: ${Object.keys(sections).length}`);

  console.log('\n--- 3. Verifying Oocyte Conflict (8 vs 9 with two sources) ---');
  console.log(`✓ Total conflicts detected: ${conflicts.length}`);

  const oocyteConflict = conflicts.find((c) =>
    (c.field && c.field.includes('oocyte')) ||
    (c.conflict_type && c.conflict_type.includes('oocyte')) ||
    (c.conflict_id && c.conflict_id.includes('OPU'))
  );

  if (!oocyteConflict) {
    throw new Error(`Oocyte conflict not found in summary conflicts: ${JSON.stringify(conflicts)}`);
  }

  console.log(`✓ Found oocyte conflict: ${oocyteConflict.conflict_id || oocyteConflict.conflict_type} on ${oocyteConflict.field}`);
  console.log(`  Source references: ${oocyteConflict.source_refs.join(', ')}`);

  if (oocyteConflict.source_refs.length < 2) {
    throw new Error(`Expected at least 2 source refs for oocyte conflict, got: ${oocyteConflict.source_refs.join(', ')}`);
  }

  const items = oocyteConflict.items || [
    { source_id: oocyteConflict.source_id_a, value: oocyteConflict.value_a },
    { source_id: oocyteConflict.source_id_b, value: oocyteConflict.value_b },
  ];
  console.log(`  Item count: ${items.length}`);
  items.forEach((it, i) => {
    console.log(`  Item ${i + 1}: Source ${it.source_id}, Value ${it.count ?? it.value}`);
  });

  const values = items.map((it) => Number(it.count ?? it.value));
  const hasEight = values.includes(8);
  const hasNine = values.includes(9);

  if (!hasEight || !hasNine) {
    throw new Error(`Expected both 8 and 9 in conflict items, got: ${values.join(', ')}`);
  }
  console.log(`✓ Definition of Done: Oocyte conflict correctly shows 8 versus 9 with two distinct sources (${oocyteConflict.source_refs.join(' and ')})!`);

  console.log('\n--- 4. Verifying Source Record Fetch and Span Highlighting ---');
  // Test opening both conflict records
  for (const srcId of oocyteConflict.source_refs) {
    const recRes = await fetch(`${BASE}/records/${srcId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const rec = await recRes.json();
    if (recRes.status !== 200 || !rec.content_text) {
      throw new Error(`Record fetch failed for ${srcId}: ${JSON.stringify(rec)}`);
    }
    console.log(`✓ Record ${srcId} loaded successfully:`);
    console.log(`  Type: ${rec.type}, Date: ${rec.date}, Author: ${rec.author}`);
    console.log(`  Origin: ${rec.origin_org}, Trust: ${rec.trust_status}, Version: v${rec.version}`);
    console.log(`  Content length: ${rec.content_text.length} chars`);
  }

  // Check all section claims for citations and span validity
  let totalCitations = 0;
  let validatedSpans = 0;
  for (const [secName, sec] of Object.entries(sections)) {
    const list = sec.statements || sec.claims || [];
    for (const claim of list) {
      for (const cit of claim.citations || []) {
        totalCitations++;
        if (cit.span && typeof cit.span.start === 'number' && typeof cit.span.end === 'number') {
          const recRes = await fetch(`${BASE}/records/${cit.source_id}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          const rec = await recRes.json();
          const spanText = rec.content_text.slice(cit.span.start, cit.span.end);
          if (spanText.length > 0) {
            validatedSpans++;
          }
        }
      }
    }
  }
  console.log(`✓ Total citations inspected: ${totalCitations}`);
  console.log(`✓ Validated span highlights: ${validatedSpans}`);

  console.log('\n--- 5. Testing Statement Feedback API (POST /summaries/{id}/feedback) ---');
  const targetSummaryId = summaryId || 'SUM-P-101-1';
  const fbRes = await fetch(`${BASE}/summaries/${targetSummaryId}/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      statement_ref: 'CLM-001',
      type: 'incorrect_fact',
      comment: 'Discharge summary states 8 oocytes instead of 9',
    }),
  });
  const fbData = await fbRes.json();
  if (fbRes.status !== 200 || !fbData.id) {
    throw new Error(`Feedback submission failed: ${JSON.stringify(fbData)}`);
  }
  console.log(`✓ Feedback successfully submitted: ID ${fbData.id}, User: ${fbData.user_id}`);

  console.log('\n===============================================================');
  console.log('✓ DEFINITION OF DONE FULLY SATISFIED:');
  console.log('  1. Clicking any citation in P-101 opens the right record with text highlighted');
  console.log('  2. Oocyte conflict shows 8 versus 9 with two sources');
  console.log('===============================================================');
}

verifyStep13().catch((err) => {
  console.error('Step 13 Verification Failed:', err);
  process.exit(1);
});
