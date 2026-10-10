# M7 harbour porpoise engineering test set

This export contains 75 physically present and 75 explicitly target-removed images. Whole trajectories, all snapshots/GSDs and related runs stay in one split.

Class 0 labels only the bridge-owned harbour porpoise. Other demonstration animals remain unlabelled background; target removal does not mean all wildlife was absent. Boxes use direct evaluated mesh projection and are amodal. They are not exact visible or refracted underwater outlines. Rendered visibility remains unknown in metadata. The static-pose behavioural model and biology remain provisional for engineering use.

Visual review found brightness and texture-detail differences in some preserved background animals between target-present and removed rows. Their cause was not established. Matching physical scene and camera identities do not establish pixel-identical or photometrically equivalent RGB backgrounds.

The train/validation/test folders describe the declared grouping demonstration. No detector was trained or statistical generalization established. data.yaml records this export's absolute root and relative split directories. Update the root when moving the export. It is a dataset descriptor, not a training command.

manifest.json maps every copied PNG, label and annotation to its retained capture, actual GAMA source state, paired scene/camera identities and output hashes. visual_review.json retains descriptive contact-sheet observations for every image, including physically present targets that could not be separately distinguished. These observations do not replace unknown machine visibility or amodal labels.
