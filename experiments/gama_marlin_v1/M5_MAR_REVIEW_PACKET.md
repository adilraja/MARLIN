# Milestone 5 — MAR review packet

Sprint: **GAMA–MARLIN Behavioural Integration and Validation**  
Milestone: **Validate reproducibility and review the behavioural model**  
Named human reviewer: **MAR**, assigned by the user on 8 October 2026.  
Review status: **Pending an explicit human decision.** Assignment did not constitute approval.

Engineering reproducibility passed for the declared positive-seed workload. Biological suitability remained **provisional**, with no biological approval. The proposed limited use was an **engineering proxy for deterministic GAMA-to-MARLIN state transfer and capture-pipeline development**. The evidence did not establish realistic harbour-porpoise behaviour, natural state occupancy, breathing, or validated survey imagery.

## Material to review

1. [Ten actual GAMA trajectories](qa/m5_review_figures/m5_ten_seed_trajectories.png): ten starting angles, the same 8 m circular path, and 20 s per record.
2. [Depth and state exposure](qa/m5_review_figures/m5_representative_depth_and_states.png): representative seed 184729, five deliberately balanced labels and a censored final surface episode.
3. [Speed and turning](qa/m5_review_figures/m5_representative_speed_and_turning.png): horizontal metadata, measured horizontal chord speed, 3D chord speed, and circular heading differences.
4. [Six actual MARLIN rendered poses](qa/m5_review_figures/m5_representative_recorded_poses.png): retained M4 captures whose source states matched the new M5 seed-184729 sequence exactly. These were existing renders, with no new M5 Kit captures.
5. [Behavioural parameter register](M5_BEHAVIOURAL_PARAMETER_REGISTER.md): 42 entries, comprising 31 engineering assumptions and 11 unresolved items. No behaviour value was promoted to literature-supported or expert-specified.

The figures also have SVG exports in the same directory. [Detailed results](M5_REPRODUCIBILITY_AND_BEHAVIOURAL_REVIEW.md), [machine-readable analysis](qa/m5_analysis.json), and the [original M4 demonstration](qa/m4_live_03/porpoise_replay_demo.gif) provide the supporting evidence. The GIF is a six-keyframe diagnostic demonstration, not continuous body animation.

## Interpretation and limits

- All 13 fresh GAMA executions succeeded: ten declared positive seeds and three repeats. Each repeated pair had identical canonical state bytes. Different seeds varied the initial phase and horizontal pose; duration, depth, speed, and turning were fixed.
- The 41 samples at 0.5 s spacing covered **20 s**, not 20.5 s. Each label accumulated 4 s by design. That balance did not estimate wild-animal occupancy. The final surface episode was observed for 2 s before recording ended; its eventual duration was unknown.
- Motion-root depth ranged from 0.2 to 3 m below the fixed mean sea-level plane. It was not an anatomical depth or instantaneous wave clearance. The corrected static mesh's upper bound was approximately 0.1607 m above the root; a root 0.2 m below the plane therefore did not demonstrate breathing or body emergence.
- Every state used the same upright static pose. Dive pitch, roll, fluke motion, breathing and anatomical clearance remained unvalidated. The camera followed the animal; similar screen positions did not mean the animal was stationary. Temporary underwater diagnostic lighting and other demonstration animals were visible in the retained images.
- A retained negative test requested seed 0 but exported actual seed 0.0180602312789524 on this installed model/runtime. The recorder rejected it. Seed 0 was excluded from the newly declared positive-seed acceptance workload; no seed remapping or model change was made.

## Human decision to record

MAR should review both the trajectories and the rendered pose sheet, then state one of the following outcomes with any required corrections:

- **Provisional; engineering use only:** retain the above limitations and permit continued development using this explicitly labelled proxy. This does not grant biological approval.
- **Approved for a stated limited biological use:** identify the exact use, the supporting expertise/evidence, and any constraints. Software success alone is insufficient.
- **Changes requested or blocked:** identify the unacceptable trajectories, poses, parameters, or missing evidence and the required remedy.

The authoritative human response will be recorded in [the review record](qa/m5_human_review.json). Until then, Milestone 5 remains pending human review. Milestone 6 has not started.
