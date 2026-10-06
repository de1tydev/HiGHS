# V2 direct refresh, after rejected V1

V1 completed all 21 pairs with matching solution bytes and checked primals,
but failed its predeclared speed gate: median +0.4749% wall among 6 >=0.5s
pairs, worst +29.4556%. Do not enable V1 or select only its dcmulti seed-1 win.

New implementation hypothesis: V1 paid a key/validity branch and 40-byte cache
entry for every integer term in every trial. Static review of
flipComplementation confirms that only vals[index] (plus the corresponding
solution/complement flag and common rhs) changes. Replace lazy per-term lookup
with 16-byte (floor,fraction) entries, initialize only at the first admissible
trial, then explicitly refresh the one trial coordinate. After a rejected trial
refresh that coordinate after restoration; before rhs/f0 rejection the cache
has not changed, so no refresh is needed. No omitted trial or reassociation.
This is an implementation iteration on exposed development data, not validation
on an unseen panel or a post-hoc rescue of V1.

Predeclared V2 execution: sanitizer/reference test including accepted/rejected
flip sequences; one logged gesa2/seed1 mechanism run; default-off official pairs
on dcmulti/gesa2 seed1; same full 7-model x 3-seed panel with reversed order rule,
60s native/75s outer, same original matrix checker and >=5% median / <=20% worst
practical gate. No data/seed replacement. A failure remains a failure.
Retain V1 patch, binary, results and source before V2. Build V2 in a separate
build directory, with no overlapping numerical experiment. If V2 also fails,
stop cache optimization; next prioritize separator attribution, not a third
threshold tuned on these results.
