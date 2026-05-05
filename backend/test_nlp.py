from nlp_filter import should_block

# Test 1 — Should be BLOCKED
prompt1 = "Here is our internal source code for RVCEBank login system: def login(): pass"
blocked, analysis = should_block(prompt1)
print(f"\nTest 1 — Blocked: {blocked}")
print(f"Score: {analysis['score']}/100")
print(f"Reasons: {analysis['reasons']}")

# Test 2 — Should PASS
prompt2 = "Can you explain how binary search works?"
blocked, analysis = should_block(prompt2)
print(f"\nTest 2 — Blocked: {blocked}")
print(f"Score: {analysis['score']}/100")
print(f"Reasons: {analysis['reasons']}")