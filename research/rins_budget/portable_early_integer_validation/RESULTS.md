# Portable early-only replay validation

The [portable package](../portable_early_integer_replay/README.md) has a validated tiny numerical path and corrected offline verification. This is a synthetic correctness check, with no production benchmark rerun or speedup claim. The [historical nine-pair result](../early_integer_results/RESULTS.md) remains separate.

The two-hour triangle passed both arms. Baseline used two proof solves; early used one discovery and one proof solve. Both finished with independently checked upper value 660 and adjusted solver lower bound 659.9999899995, a relative gap of about 1.52e-8. Every model readback field, original source constraint and listed tiny outage was checked. Discovery bounds remained excluded from proof.

The successful numerical tiny used 0.208417315 total solver-process seconds. Its two containing-arm intervals were 12.976275021 and 12.798994392 seconds; these tiny timings have no performance significance. The encompassing validation took 30.655552669 seconds and includes preparation, preflight and the initial offline-verifier failure. Cleanup was clean.

Two development failures are retained in the [complete validation record](result.json): v1 stopped after one 0.052365826-second solve when a benign keyword in a path-bearing CLI announcement matched the diagnostic scanner; v2 certified both arms, then its offline verifier failed because a local dictionary shadowed the source path. The final revision changes only that verifier variable name and required manifest metadata. Its numerical payload is byte-identical to the successfully exercised v2 payload. Corrected verification passed against the intact two-arm artifacts and rejected second-arm command tampering; no solve, API call or model generation was repeated for that correction.

The package also passed 18 pure tests and unchanged-output comparisons across 45 retained solver logs and 45 readback logs, including global keyword-path substitutions. Exact hashes and failure accounting are in the JSON record. The published package manifest is `62c97392d77cd0af2eb8056ea1167222ad969c82e9efa59c0196dcb5ebaa9743`.

Only Linux/glibc and the recorded runtime were exercised. New local runs bind their own runtime and measurements; this validation does not promise identical timing, broad platform support, or an independently proved exact dual certificate.
