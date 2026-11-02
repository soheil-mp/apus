# 0002. Deterministic, explainable perception

- Status: Accepted
- Date: 2026-11-02

## Context and problem statement

Apus must turn sparse lidar returns into bird detections, tracks and behaviour classes. Much
recent work on sparse lidar targets uses learned models (for example a 3D U-Net for bat
occupancy, [Klar et al., 2026](https://arxiv.org/abs/2609.20160)). Outputs of Apus are meant to
feed environmental assessments, such as collision-risk estimates for wind farms, where every
number may be questioned. Which family of methods should the perception pipeline use?

## Decision drivers

- **Auditability.** An ecologist or regulator must be able to see why a track was classed as a
  large bird, as a rule with thresholds, not a score.
- **Reproducibility.** The same input must give the same output on any machine.
- **No labelled data exists** for ground-based lidar of birds, and creating it is out of scope.
- **Edge hardware.** Processing must run on a low-power arm64 device without a GPU.
- **Physics is known.** Sensor geometry, target kinematics and clutter physics are well
  described, so model-based methods are a good fit.

## Considered options

1. Deterministic signal processing and estimation theory: background modelling, connected
   components, Kalman/IMM tracking, periodograms, explicit rules.
2. Learned detectors and classifiers.
3. A hybrid with learned components behind a flag.

## Decision outcome

Chosen: **option 1**. Apus contains no machine-learning models, no training or inference code,
no model APIs and no datasets for training or evaluating models. Behaviour classes come from a
versioned, human-readable rule set in which every decision carries its reasons.

### Consequences

- Good: every output can be traced to inputs, parameters and rules.
- Good: runs on modest hardware; no GPU, no model files.
- Good: the simulator's ground truth evaluates the algorithms directly.
- Bad: some discrimination power is given up, for example species identity, which lidar alone
  cannot reliably provide anyway.
- Bad: thresholds need careful calibration and documentation (M7).

## Confirmation

- The dependency licence and policy check in CI rejects machine-learning frameworks.
- Code review checks that new perception code is deterministic and seeded.
- Golden-scenario tests assert byte-identical outputs for fixed seeds.

## More information

- [Domain research](../research/01-domain.md)
- [Algorithms](../research/03-technology-landscape.md#3-algorithms)
