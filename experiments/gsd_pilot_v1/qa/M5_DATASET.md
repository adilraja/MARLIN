# Milestone 5: provisional pilot dataset

The dataset used the frozen Milestone 3 scene proposals and the validated
Milestone 4 generic Kit capture path. It included 25 scene groups for each
provisional target, the European storm petrel and harbour porpoise. Each group
had five positive views at 0.5, 1, 2, 3 and 4 cm/px. Five parent groups per
species, with predefined indices 0, 6, 12, 18 and 24, also had a target-absent
view at every GSD. The accepted set contained 250 positive images, 50
negatives and 300 images total, with zero QA rejections. Ten scene-0 images were reused
byte-for-byte from the Milestone 4 method check. The chosen negative parents
were fixed before rendering and retained their parent scene identities;
Milestone 6 will assign splits with the required 3/1/1 negative-parent counts.

The M3 sampler validated the original 1.2.0 specification schema. Its 50
saved manifests therefore were validated against the byte-preserved M3
specification, not regenerated from the later 1.3.0 reporting revision. The
sampling code and M3 manifest bytes remained unchanged. New scene snapshots
were reconstructed from those manifests and the frozen environment. Large
materialized USD checkpoints were kept under ignored `artifacts/` storage;
the tracked variant index recorded their SHA-256 hashes, base-scene hashes,
biological identity hashes, and camera positions. `m5_prepare.py` could
rematerialize missing local checkpoints from the preserved inputs.

For each new image, the capture script stopped live controllers, restored the
frozen stage, checked controller status, captured repeated frames until the
full-image mean absolute RGB change fell below 1/255, and saved the accepted
1024 × 768 image. It recorded probe hashes and settling differences without
adding every intermediate probe to the dataset. The M4 scene-0 images retained
their original, independently validated capture records. Actual Kit viewport
camera, resolution, renderer settings and zero time-sampled attributes were
checked against the frozen environment for all accepted images.

The 250 positive labels projected all evaluated animal mesh vertices through
the authored capture camera, including parent transforms and the frozen pose.
The COCO boxes described direct amodal geometry. Their `area` field meant
bounding-box area for detection; it was not substituted for unknown projected
silhouette or visible target area. The porpoise labels did not invert water
refraction. Image-local contrast against a 12-pixel surround established
target presence for each positive frame; the 50 target-absent counterparts
provided stronger paired differences for their parent groups. Visibility
thresholds and all per-frame outcomes were retained in
`qa/m5_dataset_validation.json`.

The M5 deliverable remained a provisional synthetic dataset. It did not claim
biological distribution realism, exact underwater visible outlines, measured
RTX sample counts, bitwise RGB replay identity, survey-hardware calibration,
or detector performance. Split assignment, model-input transforms and model
training belonged to later milestones.

Key files were `renders/milestone_5/variant_index.json`,
`renders/milestone_5/capture_progress.json`,
`annotations/milestone_5_geometry.json`,
`annotations/milestone_5_frames.json`, and
`annotations/milestone_5_coco.json`. The scene preparation and capture scripts
resumed completed work; they did not regenerate accepted RGB images unless
their progress records were deliberately removed.
