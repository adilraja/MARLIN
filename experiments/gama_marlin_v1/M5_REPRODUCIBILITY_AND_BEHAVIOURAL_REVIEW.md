# Milestone 5 — Reproducibility and behavioural review

Sprint: **GAMA–MARLIN Behavioural Integration and Validation**  
Milestone: **Validate reproducibility and review the behavioural model**  
Date: 8 October 2026

**Milestone 5 completed. Engineering reproducibility passed** for ten declared positive seeds and three repeated seeds, using the pinned installed GAMA runtime and unchanged `engineering_porpoise_v1`. **Biological suitability remained provisional**, with biological approval false. MAR completed the human review and found the material acceptable for now. The [human review record](qa/m5_human_review.json) governs that decision separately from the historical engineering analysis. Continued use remained limited to the explicitly labelled engineering proxy described in the review packet.

## Executed workload and reproducibility

The [positive execution plan](m5_positive_execution_plan.json) was declared before execution. The primary seeds were `1, 2, 42, 1729, 184729, 20261008, 314159, 8675309, 123456789, 2147483647`; seeds `1, 184729, 2147483647` were repeated. All **13 fresh recorder/GAMA launcher/JVM invocations** completed successfully, using distinct workspaces and output directories. Each yielded 41 states, for **533 accepted samples**. [Execution records](qa/m5_positive_execution.json) retained process IDs, commands, timestamps, log hashes and run outcomes; raw XML was preserved alongside every accepted trajectory.

The verifier reparsed the raw GAMA XML and compared canonical state **bytes**, excluding only the non-scientific `run_id` field. Wall-clock timestamps and machine paths belonged to execution metadata outside the state objects. Seeds and every scientific state field remained in the comparison. All three repeat pairs were exactly equal:

| Seed | Canonical SHA-256 for both runs |
| --- | --- |
| 1 | `f339088635608d611ef909ce39354e00b3eda29f801c488584d3166e43203b8d` |
| 184729 | `5c602f67e1c2bb7d551a23785b8bc1d355fc6fd17e84d8fc4c8257cd1ad82fb2` |
| 2147483647 | `a14011436d2ea0df1312212d6e3dfb09916bddbed3cd7f4ad406c40c6c969948` |

All ten primary seeds produced distinct initial phases and horizontal positions. Removing the declared phase rotation recovered the same geometry and headings within the declared tolerances: maximum position residual `8.38e-15 m`, heading residual `5.68e-14 degrees`. Clocks, state labels, depth evolution and horizontal speed stayed equal as intended. The variation test examined the actual output poses, rather than treating a changed seed field as proof of stochastic variation.

## Pinned execution scope

The accepted runs retained GAMA **2025.6.4**, commit `ab35ccb69a12b3e2ac9e0b902662f24a82367995`, JDK `21.0.7+6`. The model, configuration, launcher, installed runtime configuration, calibration and asset hashes matched the M3 pins. The [plan](m5_positive_execution_plan.json) contains their full hashes. Neither GAML nor model parameters were changed for M5.

The workload ran sequentially, with one model agent and no display aspect or asynchronous external input. Installed runtime preferences were pinned by configuration hash, rather than every parallelism preference being exported or explicitly forced. These results establish repeatability for this workload on this installed configuration; they do not establish universal repeatability across runtime updates or hosts. GAMA's [reproducibility guidance](https://gama-platform.org/wiki/Ensure-model-reproducibility) explains why execution conditions as well as the seed matter.

Two earlier attempts were retained as failures, separate from acceptance:

1. The [initial sandbox attempt](qa/m5_execution.json) could not write the installed GAMA headless configuration and produced no accepted trajectory. The subsequent installed-runtime execution used the approved escalation.
2. The [zero-seed attempt](qa/m5_retry_execution.json) completed GAMA but exported actual seed `0.0180602312789524` after seed `0` was requested. The existing strict recorder rejected the mismatch before accepting a trajectory. Raw XML and logs remained in `trajectories/m5_retry_seed_0_a/`. This was an observed counterexample for this model/runtime, not a claim about every GAMA zero-seed execution. A new positive-seed workload was declared before its execution; no remapping or simulated replacement data was used.

The accepted runner source was pinned in its execution plan. The two historical failed plans retain the older runner hash and are diagnostic history, rather than rerunnable plans for the current runner version.

## Measured behaviour against engineering constraints

Every accepted run passed the declared constraints. State exposure used intervals `[t_i, t_(i+1))`; the endpoint sample added no exposure. A 0–20 s sequence at 0.5 s spacing therefore contained 41 samples and 40 intervals.

| Episode | Time interval (s) | Observed exposure (s) |
| --- | --- | --- |
| surface | 0–2 | 2 |
| shallow_swim | 2–6 | 4 |
| descent | 6–10 | 4 |
| submerged_swim | 10–14 | 4 |
| ascent | 14–18 | 4 |
| surface | 18–20 | 2, right-censored |

The final surface state never exited within the observation window. Its 2 s exposure was not a measured natural dwell time. Aggregating both surface episodes gave 4 s per label, deliberately balanced for engineering coverage and unsuitable as a wild-state frequency estimate.

| Quantity | Result and interpretation |
| --- | --- |
| Motion-root depth | 0.2–3.0 m below fixed mean sea level, with declared cubic transitions |
| Instantaneous horizontal speed metadata | 0.5 m/s throughout |
| Measured horizontal chord speed | Approximately 0.4999796552 m/s; the small deficit was expected from chord sampling |
| Horizontal distance | Polyline 9.9995931039 m; declared continuous arc 10 m |
| Signed turning rate | Approximately +3.5809862196 degrees/s; differences wrapped across 360 degrees |
| Sampled depth rate | Peak descent +0.8078125 m/s, peak ascent −1.028125 m/s, positive down |
| Analytic cubic depth-rate peaks | Shallow transition +0.225, descent +0.825, ascent −1.05 m/s |
| Maximum measured 3D chord speed | Approximately 1.1432500476 m/s, including vertical movement |

The [analysis JSON](qa/m5_analysis.json) contains all per-run checks, tolerances, episodes, transition steps, interval measurements and residuals. Sampling-derived speed/rate tolerances were calculated from the declared position/depth tolerances and timestep. Numerical agreement with these equations did not validate them as animal behaviour.

## Parameter and rendered-pose review

The [register](M5_BEHAVIOURAL_PARAMETER_REGISTER.md) and [JSON register](m5_parameter_register.json) covered durations, speed, turning, depth and pose. Its 42 entries comprised **31 engineering assumptions and 11 unresolved items**. There were zero literature-supported or expert-specified behaviour values. The source asset's specimen length was retained as provenance, without promoting it to a general species parameter or resolving anatomical landmark uncertainty.

Four figure sets were produced as PNG and SVG: [ten trajectories](qa/m5_review_figures/m5_ten_seed_trajectories.png), [depth/state exposure](qa/m5_review_figures/m5_representative_depth_and_states.png), [speed/turning](qa/m5_review_figures/m5_representative_speed_and_turning.png), and [recorded poses](qa/m5_review_figures/m5_representative_recorded_poses.png). The [plot manifest](qa/m5_review_figures/plot_manifest.json) pinned their inputs and outputs. Two Codex agents visually inspected all four PNGs for legibility, clipping and consistency with source data; this quality check did not substitute for MAR's review.

The pose sheet reused six **actual M4 MARLIN renders**, at simulation times 0, 4, 8, 12, 16 and 20 s. M5 seed 184729 matched the original M3 sequence exactly, and all six recorded capture states, original image hashes, asset identity and sealed M4 evidence were verified before reuse. The sheet explicitly identified the older capture provenance. No new M5 capture, Kit restart, HTTP operation, or scene edit was performed.

The poses used a common upright static mesh with zero motion-root pitch/roll. Dive pitch, fluke/body animation, breathing and instantaneous wave clearance remained unvalidated. At a root depth of 0.2 m, the corrected mesh's upper bound of approximately 0.1607 m above the root remained nominally below the fixed plane; the `surface` label did not demonstrate breathing or emergence. The retained diagnostic camera followed the animal and used temporary underwater lighting; other scene animals remained visible.

MAR's [review packet](M5_MAR_REVIEW_PACKET.md) proposed continued use only as an explicitly labelled engineering proxy for state transfer and capture-pipeline development. After reviewing the material, the user stated: “Many thanks for this. I have reviewed the material and it looks good for now.” This completed the named human review required by the sprint. The response was conservatively recorded as **provisional; engineering use only**, rather than biological approval. That label was the recorded interpretation of the response in the packet's stated context, not a verbatim selection or a claim of biological expertise.

## Verification and milestone boundary

The verification completed **25 tests**: 14 behavioural-analysis tests and 11 existing recorder tests. These checked endpoint exposure/censoring, circular heading wrap, sampled versus instantaneous speeds, signed vertical rates, 3D movement, altered-data rejection, genuine phase variation and input isolation. Python syntax checks passed for the new tooling. Independent audits found no blocking defects in the metrics or execution provenance.

The original baseline (914 files), checkpoint records/archive, all 27 sealed M3 outputs and all 56 sealed M4 outputs remained unchanged; the separate audit also confirmed the 17 unchanged M2 outputs. No MARLIN service, ocean, behaviour controller, app, asset, model or configuration was modified.

The [engineering evidence manifest](qa/m5_engineering_manifest.json) sealed 172 outputs, including all accepted runs, failed attempts, tooling, parameter records, review packet and figures. The [final engineering QA record](qa/m5_final_engineering_qa.json) independently rechecked the prior evidence and plot pins. The 17 preserved M2 outputs excluded the extension source intentionally updated and resealed during M4. This summary and the human decision record were left outside the engineering seal so that the explicit human outcome could be recorded without rewriting experimental evidence.

Engineering deliverables and MAR's human review were complete. Overall **M5 acceptance completed**, with engineering reproducibility passed, biological suitability provisional and biological approval false. The [final milestone manifest](qa/milestone_5_manifest.json) sealed the engineering evidence together with the completed review record and this summary. Pending-review flags in the earlier engineering seal, analysis, register and review packet describe their preparation state; the final review record and milestone manifest contain the subsequent human outcome. No M6 frozen-state or paired-GSD capture work was started.
