# History-data coverage and minimum usable inputs

The verified research records establish four distinct 36-hour PEGASE1354 dates: May 1, June 1, October 1 and December 1, 2017. Three labels are selected/materialized in the current history inventory; independently audited December seed-1/seed-2 labels can be recovered from previously verified archives. Thus there are four audited label dates in retained evidence, not just three. Extra seeds do not add dates. These four separated windows provide zero consecutive-daily transitions and zero unexposed test dates.

The compatible target has 1,354 buses, 260 generators, 1,991 lines and 1,288 source-listed single-line outages. Earlier base-network-only PEGASE1354 records and PEGASE89 records do not add compatible labels. Separate January 15, April 15 and July 15 public-input requests were recorded as HTTP 403 failures; no optimizer ran for those missing inputs, and this work did not retry or bypass access restrictions.

For a meaningful historical or learned policy, the smallest useful data package is:

- A chronological stream of neighboring input windows, with stable unit/bus/outage identities, exact model scope and original raw files
- Forecast issue/version times and features available at each decision cutoff: load, reserve, initial on/off age and power, current limits, ramps, startup/shutdown limits, minimum-up/down requirements, costs, fixed/must-run status, outages and availability
- Independently checked past schedules with complete u/y/z, dispatch, reserve and slacks; original model/source/security receipts; objective and bound kind/gap; and when solving and validation actually completed
- An explicit state-carry policy: after implementing 24 hours of a 36-hour plan, use the state after those 24 hours, not its terminal state
- A chronological train/validation/test separation fixed before tuning, with overlapping windows and correlation disclosed; no future realized values or later validation information may enter an earlier decision
- Complete cost records covering label acquisition, inference, failed repair, fallback and mandatory original/full-outage checks

A one-neighbor mechanism can operate with one eligible past label; a three-neighbor rule requires three. Those are interface minima, not statistically sufficient training sizes. Meaningful coverage must include changing initial states, residual up/down obligations, load/ramp conditions and availability regimes. No universal number of dates guarantees that coverage or reliable speedup.

A prior 36-hour optimized forecast schedule can be available before the physical horizon ends. Horizon overlap alone does not make using that already-computed plan a causal leak; input and label availability times govern that question. Evaluation still needs to account for overlapping observations and avoid future realized-data leakage.

The current four dates support correctness fixtures and retrospective diagnosis. They do not establish trained generalization, annual operation, a failure probability, or end-to-end savings from history. New legally available public windows or an explicitly provided dataset would be needed before a meaningful unseen-data study; no access to a user's machine is assumed.
