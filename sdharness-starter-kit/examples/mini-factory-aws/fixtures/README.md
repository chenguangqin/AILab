# Cloud-run event fixture

`events.jsonl` is a **real, green `sdharness` run captured from a Lambda MicroVM** (us-west-2) — the
NDJSON the MicroVM worker streamed out its HTTPS endpoint, end to end (`run_start` → RESEARCH → PLAN →
BUILD → VERIFY → `complete` with a passing `integration_report`).

It's a small smoke intake (a trivial Python module) — the point is a **genuine cloud-run event stream**
to replay in VERIFY, so the control plane's launch → stream → result seam can be proven **without
provisioning a live MicroVM** (fast, free, no MicroVM-enabled account needed). Your build's own VERIFY
should replay this (or a fixture it records) rather than calling AWS.
