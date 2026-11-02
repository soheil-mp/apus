# Domain research: measuring bird flight with lidar

> Research notes written on 2026-11-02 to plan Apus. Claims link to their source. Numbers
> marked "≈" are planning approximations; the milestone that calibrates them is named in
> brackets, for example [M3].

## 1. Why measure bird flight in three dimensions

Three questions drive demand for continuous, three-dimensional bird-flight data:

1. **Collision risk with wind turbines.** Collision risk models (CRMs) need the passage rate of
   birds through a wind farm and the share of flights at rotor height. The Band model (Band,
   2012) is the standard deterministic CRM in European assessments. It has four options: options
   1–2 assume flights are spread uniformly over the rotor height band, while options 3–4 use a
   flight-height distribution, either generic (3) or site-specific (4)
   ([stochLAB `band_crm`][stochlab]). Site-specific height distributions are expensive to collect
   and are the input lidar can supply most directly.
2. **Migration ecology.** Operational weather radars measure bird density, speed and direction as
   a function of altitude ([Dokter et al., 2011][dokter2011]). These vertical profiles are
   published openly for Europe by Aloft (see [data sources](02-data-sources.md)). Weather radar
   is weakest near the ground, which is where turbines, buildings and airfields are.
3. **Behaviour near structures.** Avoidance, flight-height changes and flock behaviour near
   turbines, power lines, glass façades and runways. These need individual tracks, not
   aggregate densities.

## 2. Existing sensing methods and the gap

| Method | What it measures | Strengths | Limits for this problem |
| :-- | :-- | :-- | :-- |
| Weather radar (vol2bird profiles) | Density, ground speed and direction per 200 m height bin, every ≈ 5–15 min | Free, continental coverage, long archives | No individual tracks; lowest bins unreliable; km-scale volume ([Dokter et al., 2011][dokter2011]) |
| Dedicated avian radar | Individual tracks out to km | Long range, day and night | Costly; clutter; limited height accuracy; proprietary processing |
| Aircraft-mounted lidar | Seabird flight heights from survey aircraft | Accurate heights | Snapshot surveys, not continuous; noise from spray and moisture must be removed ([Scottish Government][govscot]; [APEM][apem]) |
| Entomological (Scheimpflug) lidar | Range-resolved echoes along one beam at kHz rates; wingbeat frequency | Resolves wingbeats; separates insects, bats and birds ([Malmqvist et al., 2018][malmqvist2018]) | One transect, not 3D tracks; research instruments |
| Ground-based 3D lidar for bats | Voxel occupancy in sensor-centric "raystacks" | Continuous 3D | Published approach is a learned 3D U-Net ([Klar et al., 2026][klar2026]) |
| Lidar drone detection (closest technical analogue) | Clusters and tracks of small aerial targets | Same sparsity problem | Uses DBSCAN clustering with Kalman or adaptive EKF tracking on Livox sensors ([Xiao et al., 2024][xiao2024]; [Khosravi et al., 2026][khosravi2026]) |
| Cameras and acoustics | Species identity | Identification | Need light (cameras) or vocal birds (audio); privacy issues; usually rely on learned models |

A raptor-monitoring review notes that lidar can track individual birds in its field of view but
cannot tell species apart ([OSTI 2335363][osti]).

**Gap.** A search of GitHub on 2026-11-02 for lidar bird detection returned two unrelated
repositories. No open-source, end-to-end, ground-based lidar pipeline exists that:

- turns raw lidar returns into bird tracks with deterministic, explainable methods,
- reports how detectable a bird of a given size is at a given range, so counts can become
  densities,
- puts those tracks into a reproducible data platform next to radar and weather data, and
- turns tracks into collision-risk inputs.

Apus fills that gap.

## 3. Detection physics

### 3.1 Sampling geometry

A scanning lidar samples directions on a grid. At range *R* the spacing between neighbouring
beams is *s = R·Δθ*. For a spinning sensor with 1024 columns over 360° (Δθ ≈ 0.352°) and 64 rows
over 45° (Δθ ≈ 0.714°):

| Range | Horizontal spacing | Vertical spacing |
| --: | --: | --: |
| 25 m | ≈ 0.15 m | ≈ 0.31 m |
| 50 m | ≈ 0.31 m | ≈ 0.62 m |
| 100 m | ≈ 0.61 m | ≈ 1.25 m |
| 200 m | ≈ 1.23 m | ≈ 2.49 m |

Birds are small against these numbers: a small passerine is about 0.1–0.15 m long with a
wingspan of about 0.2–0.3 m; gulls, buzzards and geese have wingspans of roughly 1.1–1.7 m.
When the target's projected area *A* is smaller than one beam cell (*s_h·s_v*), the expected
number of hits per frame is about *A / (s_h·s_v)* and the target is **intermittently
detected**. A gull-sized target (*A* ≈ 0.25 m², wings spread) at 100 m gives
0.25 / (0.61 × 1.25) ≈ 0.33: about one hit every three frames.

Consequences for the design:

- Detection must work on 1–5 points per frame, and tracking must bridge missed frames
  (M-of-N confirmation, coasting) [M5, M6].
- The probability of detecting a bird depends on its size, range and position in the scan
  pattern. Apus models this **detectability** explicitly and uses it to turn counts into
  densities [M5, M11].
- Non-repetitive (rosette) scanners fill gaps between beams over time, which trades
  per-frame density for coverage [M3].
- Real beams have a finite footprint (divergence of the order of mrad), which raises hit
  probability and lowers energy per hit. The simulator models footprint, not ideal rays [M3].

### 3.2 Link budget

For a target that fills the beam (an extended target), received power falls as 1/*R*². For a
target smaller than the beam footprint, the intercepted fraction of the beam also falls as
1/*R*², so received power falls as about 1/*R*⁴, as with radar point targets. Datasheet ranges
are quoted for extended Lambertian targets (typically 10 % and 80 % reflectivity), so the
maximum range for a small bird is much shorter than the headline figure. Feather reflectivity
at 850–950 nm is not well documented; Apus treats it as a calibrated parameter with a prior
range, not a constant [M3].

### 3.3 Clutter and false targets

| Source | Signature | Deterministic discriminant |
| :-- | :-- | :-- |
| Rain | Sparse single returns, falling at up to ≈ 9 m/s ([Gunn & Kinzer, 1949][gunn]) | No persistence across frames; vertical velocity; correlated with precipitation data |
| Fog, mist | Near-range returns, attenuation | Range distribution; visibility from weather data |
| Insects | Few returns, very close to the sensor | Range gate; size; erratic kinematics |
| Vegetation in wind | Returns near static background | Background model; distance to background surface |
| Sensor noise | Isolated returns | No spatial or temporal support |

Dual-band entomological lidar shows that frequency-domain modulation separates insects from
fog better than intensity alone ([Santos et al., 2023][santos2023]); Apus applies the same
idea through periodicity features of tracks [M7].

## 4. Bird flight parameters (simulation priors and plausibility checks)

- **Airspeed.** Tracking radar measurements of 138 species (0.01–10 kg) show cruising
  airspeed scales only weakly with mass (exponent ≈ 0.12), so most species cruise in a
  narrow band ([Alerstam et al., 2007][alerstam2007]). Apus uses ≈ 8–23 m/s airspeed as the
  plausible cruising range and wind-corrects ground speed with weather data [M7].
- **Wingbeat frequency.** Pennycuick's dimensionally correct formula predicts wingbeat
  frequency from body mass, gravity, wingspan, wing area and air density
  ([Pennycuick, 1996][pennycuick1996]). Observed frequencies of migrants at Falsterbo fell
  between 0.81 and 1.05 of the benchmark, except bounding passerines
  ([Pennycuick, 2001][pennycuick2001]). That study was limited to birds below 200 m, the
  same height band a ground lidar covers. As a rough guide, large birds flap at a few Hz and
  small passerines above 10 Hz.
- **Flight modes.** Continuous flapping, flap-gliding, bounding (wings folded between bursts,
  which modulates cross-section strongly), thermal soaring in circles, hovering, and flocks.
  Each mode has a distinct kinematic signature and is modelled in the simulator [M3].
- **Sampling limit.** At 10 Hz or 20 Hz frame rates the Nyquist frequency is 5 Hz or 10 Hz,
  so only slow wingbeats are resolved from frame-level measurements. Non-repetitive scanners
  stamp each point with its own time, which gives irregular sampling. The Lomb–Scargle
  periodogram handles irregular sampling and reduces aliasing, though the spectral window
  must be checked (VanderPlas, 2018). Apus reports wingbeat estimates with an explicit
  "resolvable / aliased / unknown" flag rather than a bare number [M7].

## 5. Radar aeroecology: what Apus compares against

Weather-radar profiles are produced by vol2bird and published as VPTS CSV (see
[data sources](02-data-sources.md)). Relevant fields, confirmed in a live file for the
Herwijnen radar (`nlhrw`):

- `height`: bottom of a 200 m bin; `dens`: bird density (birds/km³); `ff`: ground speed
  (m/s); `dd`: direction (°); `u`, `v`, `w`: velocity components; `eta`: reflectivity
  (cm²/km³); `rcs`: assumed radar cross-section per bird (11 cm² in the file).
- **Migration traffic rate (MTR)** in birds per km of front per hour:
  MTR = 3.6 × Σᵢ densᵢ × ffᵢ × Δhᵢ, with Δh in km.

The lidar observes a volume of a few hundred metres near the ground. Radar's lowest bins
are the least reliable. Comparing the two is an **indicative cross-check, not a
validation**, and the project's reports must say so [M11].

## 6. Collision risk modelling

- **Band (2012)** estimates the probability that a bird passing through a rotor is struck,
  from bird length, wingspan, speed and flight type, and rotor radius, rotation speed, blade
  chord, pitch and number of blades. Multiplied by the flux through the rotor-swept area and
  reduced by an avoidance rate, it gives expected collisions.
- **Avoidance rates** are close to 1 (for example 0.9923 for kittiwake and 0.9902 for Arctic
  tern in a Scottish offshore assessment, [Marine Scotland annex][marinescot]), so outputs are
  very sensitive to them. Stochastic CRMs resample uncertain parameters thousands of times
  ([stochLAB][stochlab]).
- **Turbine geometry matters**: a 2026 study compares collision probability across four
  reference turbines with the Band model ([Fritz et al., 2026][fritz2026]).
- **Apus** implements Band options 1–4 and a Monte Carlo wrapper from the published
  equations (no code is copied from other implementations), using lidar-derived site-specific
  height distributions in the lowest 200 m. It uses a virtual turbine with the IEA Wind
  3.4 MW reference geometry (130 m rotor, 110 m hub) [M11].

## 7. Privacy and safety by design

- Lidar measures geometry, not appearance: no images, faces or number plates.
- Returns close to the ground, where people walk, are dropped **on the device** before
  anything is stored or sent; only airborne detections above a height threshold leave the
  edge [M5].
- Apus has no cameras, no audio and no user accounts. All bundled data is synthetic or comes
  from public, non-personal sources (weather, radar profiles, elevation).
- Commercial automotive and industrial lidars are eye-safe Class 1 laser products under
  IEC 60825-1; field deployment notes cover this [M18].

## 8. Open research questions

These are tracked as research spikes in the roadmap:

1. How well does an analytic hit-probability model predict detection rates in the simulator,
   and later on real recordings? [M5, M18]
2. Can wingbeat frequency be recovered from 1–5 returns per frame with per-point timestamps,
   and how does the answer depend on scan pattern? [M7]
3. How should flocks be represented when individual birds merge into one cluster? [M6]
4. What detectability-corrected density does the lidar imply, and how does it relate to the
   lowest radar bins over the same hours? [M11]
5. How sensitive are Band CRM outputs to lidar-derived height distributions compared with
   generic ones? [M11]

## References

- Alerstam, T., Rosén, M., Bäckman, J., Ericson, P. G. P., & Hellgren, O. (2007). Flight
  speeds among bird species: allometric and phylogenetic effects. *PLoS Biology* 5(8): e197.
  [doi:10.1371/journal.pbio.0050197][alerstam2007]
- APEM. APEM pioneers the use of LiDAR to record bird flight heights. [apemltd.com][apem]
- Band, W. (2012). *Using a collision risk model to assess bird collision risks for offshore
  windfarms.* SOSS report for The Crown Estate.
- Dokter, A. M., Liechti, F., Stark, H., Delobbe, L., Tabary, P., & Holleman, I. (2011). Bird
  migration flight altitudes studied by a network of operational weather radars. *Journal of
  the Royal Society Interface* 8(54): 30–43. [doi:10.1098/rsif.2010.0116][dokter2011]
- Fritz et al. (2026). Avian collision risk with reference wind turbines: effects of geometry,
  operation and flight behaviour. *Applied Sciences* 16. [doi:10.3390/app16147354][fritz2026]
- Gunn, R., & Kinzer, G. D. (1949). The terminal velocity of fall for water droplets in
  stagnant air. *Journal of Meteorology* 6: 243–248. [doi:10.1175/1520-0469(1949)006<0243:TTVOFF>2.0.CO;2][gunn]
- Khosravi, N., Basiri, M., & Ventura, R. (2026). Lightweight 3D LiDAR-based UAV tracking: an
  adaptive extended Kalman filtering approach. [arXiv:2603.09783][khosravi2026]
- Klar, N., Rana, P., Gifary, N., Traub, J., & Ahmad, A. (2026). Needles in a Raystack:
  Ultra-sparse LiDAR occupancy detection for bat tracks. [arXiv:2609.20160][klar2026]
- Malmqvist, E., Jansson, S., Zhu, S., et al. (2018). The bat-bird-bug battle: daily flight
  activity of insects and their predators over a rice field revealed by high-resolution
  Scheimpflug Lidar. *Royal Society Open Science* 5: 172303. [doi:10.1098/rsos.172303][malmqvist2018]
- Marine Scotland. Annex 11.3b: deterministic CRM inputs and outputs. [PDF][marinescot]
- OSTI. Raptor monitoring and minimization technologies. [osti.gov/servlets/purl/2335363][osti]
- Pennycuick, C. J. (1996). Wingbeat frequency of birds in steady cruising flight: new data
  and improved predictions. *Journal of Experimental Biology* 199: 1613–1618.
  [doi:10.1242/jeb.199.7.1613][pennycuick1996]
- Pennycuick, C. J. (2001). Speeds and wingbeat frequencies of migrating birds compared with
  calculated benchmarks. *Journal of Experimental Biology* 204: 3283–3294.
  [doi:10.1242/jeb.204.19.3283][pennycuick2001]
- Santos, V., Costa-Vera, C., Rivera-Parra, P., et al. (2023). Dual-band infrared Scheimpflug
  lidar reveals insect activity in a tropical cloud forest. *Applied Spectroscopy* 77(6):
  593–602. [doi:10.1177/00037028231169302][santos2023]
- Scottish Government. Collection of seabird flight height data at an operational
  offshore wind farm using aircraft-mounted LiDAR: final report. [gov.scot][govscot]
- stochLAB R package, `band_crm` reference. [search.r-project.org][stochlab]
- VanderPlas, J. T. (2018). Understanding the Lomb–Scargle periodogram. *The Astrophysical
  Journal Supplement Series* 236(1): 16.
- Xiao, J., Pisutsin, P., Tsao, C. W., & Feroskhan, M. (2024). Clustering-based learning for
  UAV tracking and pose estimation. [arXiv:2405.16867][xiao2024]

Tracking and evaluation methods used later are referenced in
[03-technology-landscape.md](03-technology-landscape.md#algorithms).

[alerstam2007]: https://doi.org/10.1371/journal.pbio.0050197
[apem]: https://www.apemltd.com/apem-pioneers-the-use-of-lidar-to-record-bird-flight-heights/
[dokter2011]: https://doi.org/10.1098/rsif.2010.0116
[fritz2026]: https://doi.org/10.3390/app16147354
[govscot]: https://www.gov.scot/publications/collection-seabird-flight-height-data-operational-offshore-wind-farm-using-aircraft-mounted-lidar-final-report/pages/6/
[gunn]: https://doi.org/10.1175/1520-0469(1949)006%3C0243:TTVOFF%3E2.0.CO;2
[khosravi2026]: https://arxiv.org/abs/2603.09783
[klar2026]: https://arxiv.org/abs/2609.20160
[malmqvist2018]: https://doi.org/10.1098/rsos.172303
[marinescot]: https://marine.gov.scot/sites/default/files/annex_11.3b_deterministic_crm_inputs_and_outputs.pdf
[osti]: https://www.osti.gov/servlets/purl/2335363
[pennycuick1996]: https://doi.org/10.1242/jeb.199.7.1613
[pennycuick2001]: https://doi.org/10.1242/jeb.204.19.3283
[santos2023]: https://doi.org/10.1177/00037028231169302
[stochlab]: https://search.r-project.org/CRAN/refmans/stochLAB/html/band_crm.html
[xiao2024]: https://arxiv.org/abs/2405.16867
