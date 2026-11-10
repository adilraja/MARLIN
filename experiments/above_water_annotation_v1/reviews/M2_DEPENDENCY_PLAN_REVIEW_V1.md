# M2 dependency plan review v1

Date: 9 November 2026. Reviewer: **pending**. Decision: **pending**.
No installation has been authorized or performed by this record.

Please review [the dependency plan](../reports/M2_NATIVE_PROVIDER_DEPENDENCY_PLAN_V1.md),
its [eleven exact package variants and sizes](../diagnostics/m2_dependency_plan_v1/PACKAGE_TABLE.md),
[provider lock](../diagnostics/m2_dependency_plan_v1/provider_lock.json),
[proposed actions](../diagnostics/m2_dependency_plan_v1/planned_actions.json)
and the evidence manifest/verification in `diagnostics/m2_dependency_plan_v1/`.

The proposed candidate is Replicator core 1.13.27 with the Kit 110.2-specific
SyntheticData 0.6.15 backend. The exact future capture profile solved with 127
packages, reusing 116 and adding 11, with no existing package replacements.
Expected new storage is 282.61 MiB of archives and 590.98 MiB unpacked, before
filesystem/cache overhead; private-store and profile allowances are explicit.

The proposed decision concerns only the isolated download/verification/unpack
and provider feasibility stages described in the plan. It does not authorize a
main runtime upgrade, normal-app edits, broader package selection, changed
capture tolerances or any biological/optical/research use.

Retain these limitations when deciding:

- Compatibility passed vendor metadata filtering and dependency solving;
  provider activation and dry native annotation remain untested.
- Whole-archive SHA256 values must be recorded during the proposed quarantine
  verification before unpacking; the current packet pins official object
  identities and ZIP metadata hashes and does not invent absent vendor digests.
- Annotation AOV memory cost remains untested; existing resource guards apply.
- M2, its sixteen dry bundles, Gate B and the separate ocean-material M4 issue
  remain incomplete/open.

The pending JSON template is an aid for recording a future real named decision,
not an acceptance record. No acceptance has been inferred from Gate A or this
request to prepare a plan. Work stopped before dependency installation.
