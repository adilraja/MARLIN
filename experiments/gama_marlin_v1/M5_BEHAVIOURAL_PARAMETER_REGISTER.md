# M5 behavioural parameter register

This register records the assumptions in the unchanged `engineering_porpoise_v1`
model and `static_pose_proxy_v1` mapping. It separates executable constraints from
biological evidence. **Every numerical behaviour setting remains an engineering
assumption.** No behavioural row is literature-supported or expert-specified.
Unsupported biological interpretations are recorded as unresolved.

The machine-readable companion is [m5_parameter_register.json](m5_parameter_register.json).
Measured values from the declared M5 workload belong in
[qa/m5_analysis.json](qa/m5_analysis.json); design-derived values below are not
presented as new GAMA execution results. The named human reviewer is **MAR**.
The review is pending, and this register awards no biological approval. The
separate review record will contain MAR's actual decision and stated scope.

## Evidence and classification

The numeric configuration is
[porpoise_model_config.json](porpoise_model_config.json), JSON pointer
`/parameters`. The implemented rules are in
[porpoise_behaviour.gaml](../../integrations/gama/porpoise_behaviour.gaml).
The retained [Pilot calibration](../gsd_pilot_v1/wildlife/harbour_porpoise.json)
was read in full, including its uncertainty, static-state restriction and explicit
absence of biological or optical validation. Its publisher metadata is retained
in [sources.json](../gsd_pilot_v1/wildlife/sources.json), source ID
`digitallife_model75a`. Publisher-reported length is asset provenance; it supplies
no swimming, dive, timing or turning parameters.

Each machine-readable row contains an ID, domain, value or rule, units, one of the
four required evidence categories, precise source fields or code symbols, the
measurement/constraint, uncertainty or interpretation, and review status. Source
files are pinned by SHA-256 in that companion. Categories are:

- `literature-supported`: a behavioural value justified by an identified primary
  source. There are currently no such rows.
- `expert-specified`: a behavioural value explicitly supplied by an identified
  expert. There are currently no such rows; assignment of a reviewer is not such
  evidence.
- `engineering assumption`: a configuration, derived design constraint or proxy
  choice used to exercise the software.
- `unresolved`: a biological requirement or interpretation without sufficient
  support or a completed review.

## State timing and horizontal movement

The following configured values are all **engineering assumption**. Source fields
are the exact keys under `porpoise_model_config.json#/parameters`; GAML uses the
same names.

| Parameter | Value | Implementation and declared interpretation |
|---|---:|---|
| `step` | 0.5 s | `update_clock`; samples at `cycle * step`. |
| `initial_surface_s` | 2 s | Initial `surface` body; next state starts at t=2. |
| `shallow_swim_s` | 4 s | `shallow_swim`; t=2 to t=6. |
| `descent_s` | 4 s | `descent`; t=6 to t=10. |
| `submerged_swim_s` | 4 s | `submerged_swim`; t=10 to t=14. |
| `ascent_s` | 4 s | `ascent`; t=14 to t=18. |
| `final_surface_s` | 2 s | Run-horizon contribution; final surface is observed to t=20, without an observed exit. |
| `path_radius_m` | 8 m | `horizontal_sample`; circular XZ path about the origin. |
| `horizontal_speed_mps` | 0.5 m/s | Instantaneous horizontal speed; exported as `speed_mps` in every state. |

The state sequence is `surface → shallow_swim → descent → submerged_swim →
ascent → surface`. Initial and final surface are different internal FSM bodies
but share one exported label. At a transition time the newly executed body owns
that sample. All states share the horizontal path; no state is a stationary
breathing or resting model.

Let R=8 m, v=0.5 m/s and φ be the one initial GAMA draw `rnd(360.0)` after
explicit seed assignment. The GAML `horizontal_sample` action implements:

```text
θ(t) = φ + (v/R) t                    [angles converted to degrees in GAML]
x(t) = R sin θ(t)
z(t) = R cos θ(t)
heading(t) = wrap360(θ(t) + 90°)
turning rate = v/R = 0.0625 rad/s = 3.580986219567645°/s
```

These derived turning and path rules are also engineering assumptions. The seed
changes **only initial phase**, and thus initial position and heading. Durations,
speed, curvature, depth history and pose are not stochastic in this model.
Different seeds are not independent samples of wild behavioural diversity.

## Depth evolution and measurement conventions

The configured `surface_depth_m=0.2`, `shallow_depth_m=0.8` and
`submerged_depth_m=3.0` are **engineering assumption**. The depth datum is the
unchanged motion-root origin below the fixed mean-sea-level plane Y=0. It is not
anatomical depth, water clearance or instantaneous wave-relative depth. The
bridge's `exchange_v2.preview_transforms` resolves metres as `[x, -depth, z]`,
then divides by the inspected, explicitly authored positive `metersPerUnit` on a
Y-up stage. MARLIN does not separately integrate exported speed.

The GAML `shallow_swim`, `descent` and `ascent` bodies use the engineering curve
`depth = d0 + (d1-d0) u²(3-2u)`, with `u=(t-t0)/T`. Its derivative is
`(d1-d0) 6u(1-u)/T`: depth rate is positive downward and world-Y velocity has the
opposite sign. Endpoint derivatives are zero. Design-derived extrema are:

| Phase | Endpoints | Analytic peak depth rate | Maximum-magnitude 0.5 s secant |
|---|---|---:|---:|
| Shallow swim | 0.2 → 0.8 m in 4 s | +0.225 m/s | +0.2203125 m/s |
| Descent | 0.8 → 3.0 m in 4 s | +0.825 m/s | +0.8078125 m/s |
| Ascent | 3.0 → 0.2 m in 4 s | −1.05 m/s | −1.028125 m/s |

These are consequences of the declared curve, not literature limits for a
porpoise. Sampled finite differences must be compared with the corresponding
secants, rather than asserted to equal the continuous peak. Record each
derivative interval `[t_i,t_(i+1)]` with its left sample's state label.

Other acceptance measurements need the same care:

- Duration/coverage uses intervals `[t_i,t_(i+1))`, with no extra interval after
  t=20. The final surface segment is right-censored by the run stop; 2 s is the
  observed duration, not proof of its full natural or FSM lifetime.
- There are 41 samples. Initial/final surface have 4 and 5 samples, respectively;
  the four intervening phases have 8 each. Elapsed label coverage is deliberately
  4 s each over 20 s. Neither count nor coverage estimates wild state frequencies.
- The expected horizontal chord speed is
  `2R sin(v Δt/(2R))/Δt = 0.4999796551962679 m/s` at Δt=0.5 s. The exported
  instantaneous value is 0.5 m/s. Their difference is geometric, not an error.
- Heading differences use `((h_next-h_prev+180) mod 360)-180` before division by
  Δt, so crossing 360° cannot create a spurious turn. Positive turns follow the
  declared MARLIN heading convention, 0°=+Z and 90°=+X.
- A 3D displacement-derived speed includes vertical motion; exported `speed_mps`
  is horizontal. It must not be interpreted as total swimming speed.

## Asset and pose constraints

The mapping is implemented by
[`PorpoiseActor`](../../source/extensions/cris.madil.gama_bridge/cris/madil/gama_bridge/actor_v2.py),
particularly `_calibrate` and `apply`. All five labels use the same static asset,
zero root pitch/roll, GAMA root heading and GAMA root depth. Existing correction
`[-90,0,0]` is the **model-child** rotation; it is separate from root yaw. The
retained conversion is 1 metre per native unit, with reference scale
`1 / metersPerUnit` (100 on the M4 0.01 m/unit stage). The original asset origin
was retained. These are engineering reuse choices, not newly verified biological
calibration. No source asset, rig or animation was changed.

The calibration's precise field
`/geometry/corrected_metric_bounds_relative_to_root/maximum/1` is
`0.16072557866573337` m. Under the unchanged zero-pitch/roll mapping, at the
configured surface root depth of 0.2 m its nominal upper bound is:

```text
world upper Y = -0.2 + 0.16072557866573337
              = -0.03927442133426663 m
```

Thus the retained static geometry is nominally entirely at least **0.0392744 m
below the fixed mean plane** in the `surface` label. This calculation uses the
existing bounds; it is neither a new live vertex measurement nor a claim about
animated wave clearance. It cannot certify breathing, blowhole exposure,
surfacing anatomy or visibility. Existing Pilot support was a visually reviewed
static shallow proxy under flat water, explicitly not validated behaviour.

The publisher-reported 1.555 m specimen length and candidate landmark distance
are retained provenance. The same calibration explicitly leaves equivalence to
the publisher's total-length protocol unverified, provides no numerical
measurement uncertainty and records `biological_calibration_verified=false`.
Taxonomic identity remains a publisher description without independent
verification. These limitations remain unresolved; they were not converted to
literature-supported behaviour rows.

## Reproducibility scope and pending review

GAMA's primary [reproducibility guidance](https://gama-platform.org/wiki/Ensure-model-reproducibility)
describes execution/randomness conditions relevant to repeatability. This model
uses one agent, no display aspects, one seeded random draw and no external input
during simulation. The M5 workload uses sequential fresh GAMA processes, not
parallel model runs, an asynchronous live interaction, or display-side random
behaviour. The declared ten seeds and repeated-seed comparisons must be judged
from their retained raw outputs and canonical state comparisons under pinned
model, configuration and runtime. This is an empirical result for that bounded
execution setup; a seed alone does not prove reproducibility in other setups.

The final acceptance scope is the ten positive seeds declared before their runs
in [m5_positive_execution_plan.json](m5_positive_execution_plan.json), with three
declared repeated seeds. A retained earlier execution,
[`m5_retry_seed_0_a`](trajectories/m5_retry_seed_0_a/execution.json), requested
seed 0 but exported `actual_seed=0.0180602312789524` in its original raw XML.
Although its launcher exited successfully, the unchanged recorder rejected that
seed mismatch. Those files remain failed evidence. Support for requested seed 0
is **unresolved and excluded from the accepted scope**; no seed was remapped or
raw value repaired. This is one observed runtime/model edge case, not a claim
that every GAMA zero-seed execution behaves the same way. The positive-seed
workload must stand on its own comparisons, without presenting the original
zero-seed attempt as a pass.

The following remain **unresolved** pending evidence or MAR's recorded review:

- Species-specific durations, speeds, turning distributions, depth distributions
  and their dependence on behaviour or context.
- Physiological interpretation of the deliberately balanced label schedule.
- Breathing/waterline correspondence and anatomical root-depth interpretation.
- Dive/ascent pitch, body deformation, stroke/fin motion and animation phase.
- Anatomical and optical suitability beyond the existing static proxy.
- Specimen measurement uncertainty, landmark protocol and independent identity.
- Approval for a stated biological or research use.

MAR is assigned as the human reviewer, with review **pending**. Assignment does
not establish expertise, approval or that the existing plots/poses were already
reviewed. Engineering reproducibility and biological suitability must be
reported separately in the M5 results and review record.
