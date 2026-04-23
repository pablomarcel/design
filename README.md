# Design

**Design as an API for mechanical engineering.**

Design is a Python-based collection of engineering packages that treats mechanical design problems as structured computational workflows instead of page-flipping exercises.

The core idea is simple:

> Define the problem in a JSON file, run the solver, and get structured results back.

Instead of manually bouncing between equations, tables, charts, correction factors, and textbook pages, this project aims to move mechanical design toward a more modern workflow: **design inputs in, engineering outputs out**.

This repository is a modest but serious attempt at **jump-starting the idea of Design as an API**.

---

## Why this project exists

Mechanical design is powerful, but the traditional workflow is tedious.

A typical calculation often looks like this:

- read the statement of the problem
- find the governing equation
- jump to a table for a factor
- jump to a figure for another factor
- go back to the equation
- switch chapters for a material property or design assumption
- repeat until the calculation is done

That process is slow, error-prone, and hostile to automation.

This project was built from the belief that many machine design calculations can be expressed in a better way:

- **inputs** should be explicit
- **solver paths** should be repeatable
- **lookup data** should be machine-readable
- **outputs** should be structured
- **engineering workflows** should be scriptable

In other words: **mechanical design should not live only inside heavy textbooks and scattered hand calculations.**

---

## The main idea: Design as an API

Each package in this repository corresponds to a major topic typically studied in a **mechanical design** or **machine elements** course.

Within each package:

- the user defines a problem in an **input JSON file**
- the package routes the request through a **solve path**
- the solver performs the calculations, including factor lookup logic where applicable
- results are returned in **JSON output** format

That means the project behaves less like a single monolithic app and more like a **library of domain-specific engineering APIs**.

The current implementation is not an internet-scale cloud platform. It is a local, Python-first foundation for that idea.

But the direction is intentional:

**today:** local JSON-driven mechanical design workflows  
**future:** richer data services, cloud-backed lookup systems, visualization, and AI-assisted engineering workflows

---

## What makes this useful

This repository is especially useful for people who want to:

- automate textbook-style mechanical design calculations
- avoid repeated manual lookup of tables and figures
- build engineering workflows around JSON inputs and reproducible outputs
- prototype CLI-based design tools in Python
- explore how classical machine design can be turned into programmable infrastructure

The repo is also opinionated:

- it favors **Python** over closed educational workflows
- it favors **structured inputs** over opaque spreadsheets
- it favors **reproducible computation** over calculator gymnastics
- it favors **open, extensible engineering tooling** over proprietary lock-in

---

## Repository philosophy

This project is based on a broader conviction:

- engineering knowledge should be computationally accessible
- textbooks should not be dead static objects forever
- modern technical education should include richer visual content, animation, and interactive exploration
- students should not be forced into proprietary tools just to learn core engineering subjects

If industry wants commercial tools, industry can pay for them.

But for education, experimentation, and open technical work, **Python is the right default**.

This repository reflects that mindset.

---

## How the workflow works

At a high level, the workflow looks like this:

1. Choose the package for the engineering topic.
2. Create or modify an input JSON file.
3. Select the appropriate `solve_path`.
4. Run the package from the CLI or app wrapper.
5. Review the JSON results.

This approach makes the calculations:

- easier to repeat
- easier to validate
- easier to compare across cases
- easier to scale into larger engineering pipelines

---

## Package map

Each major chapter/topic is implemented as its own Python package.

### `load_stress` — Load and Stress Analysis

Capabilities include:

- 2D and general 3D **stress Mohr circles**
- 2D and general 3D **strain Mohr circles**
- **strain gauge** calculations
  - equiangular rosettes `(0, 120, 240)`
  - arbitrary-angle rosettes
  - rectangular rosettes `(0, 45, 90)`
  - arbitrary single strain gauges in biaxial plane stress
- **generalized Hooke’s law** for isotropic materials

### `deflection_stiffness` — Deflection and Stiffness

Capabilities include:

- general beam analysis
- stepped shafts
- indeterminate beams
- reaction force calculations
- shear, moment, and deflection diagrams

Notes:

- uses **anastruct** for beam calculations

### `static_failure` — Failures Resulting from Static Loading

Capabilities include:

- ductile failure theories
  - distortion energy (DE)
  - maximum shear stress (MSS)
- Coulomb-Mohr approaches for ductile materials
- brittle failure theories
  - Coulomb-Mohr
  - modified Mohr
- transverse crack calculations
- edge crack calculations

### `fatigue_failure` — Fatigue Failure Resulting from Variable Loading

Capabilities include:

- strength calculations
- surface factors
- size factors
- temperature factors
- stress concentration and notch sensitivity
- cycles to failure
- endurance limit
- part life calculations
- fatigue factor of safety
- Gerber and Langer criteria
- multiple-criterion failure analysis
  - Goodman
  - Gerber
  - ASME elliptic
  - Langer
- brittle material axial fatigue
- combined loading modes
- variable stress block damage

### `shafts` — Shafts and Shaft Components

Capabilities include:

- multi-criterion fatigue checks
  - Goodman
  - Gerber
  - Soderberg
  - ASME elliptic
- vector combination of slopes and deflections across multiple planes
- bearing and gear station analysis using beam-derived shaft responses

Notes:

- uses **anastruct-derived inputs** for shaft analysis workflows

### `screws_fasteners` — Screws, Fasteners, and Nonpermanent Joints

Capabilities include:

- power screw calculations
- fastener member stiffness for single-material joints
- fastener mixed-member stiffness for multi-material joints
- bolt strength
- statically loaded tension joints with preload
- tension joints in fatigue service
- bolted joints in shear
- joints with eccentric shear

### `welding_bonding` — Welding, Bonding, and Permanent Joints

Capabilities include:

- weld groups in torsion
- parallel welds in static loading
- design of welds in static loading
- welded joints in bending
- welds in fatigue service
- adhesive double-lap joints

### `mechanical_springs` — Mechanical Springs

Capabilities include:

- helical compression spring analysis
- selection of statically loaded compression springs
- iterative design of compression springs
- fatigue analysis of helical compression springs
- fatigue design of compression springs
- extension spring analysis for static service
- extension spring analysis for dynamic service
- torsional spring calculations

### `rolling_contact_bearings` — Rolling-Contact Bearings

Capabilities include:

- L10 life calculations
- selection of ball bearings
- selection of cylindrical roller bearings
- selection of tapered roller bearings
- tapered roller bearings in pure axial loading

Notes:

- includes **iterative bearing selection workflows**

### `journal_bearings` — Lubrication and Journal Bearings

Capabilities include:

- parameters obtained from numerical Reynolds-equation-based workflows
  - coefficient of friction
  - maximum film pressure
  - minimum film thickness
  - temperature rise
  - volumetric flow rate
- steady-state conditions in self-contained bearings
- pressure-fed journal bearing calculations
- boundary-lubricated bearing analysis
- selection of boundary-lubricated bearings from availability charts

Notes:

- includes **iterative journal bearing calculations**

### `gears` — Gears, General Force Analysis

Capabilities include:

- spur gear forces
- bevel gear forces
- helical gear forces
- worm gear forces

### `spur_helical_gears` — Spur and Helical Gears

Capabilities include:

- spur gear analysis using **AGMA-based** methods
- helical gear analysis using **AGMA-based** methods
- gear mesh design workflows

Why it matters:

This is one of the most tedious parts of classical machine design because it usually requires repeated factor extraction from tables and figures. This package aims to automate that lookup burden.

### `bevel_worm_gears` — Bevel and Worm Gears

Capabilities include:

- straight bevel gear analysis
- straight bevel gear design
- worm gear analysis
- worm gear design

Notes:

- uses **AGMA-style approaches**

### `clutches_brakes_flywheels` — Clutches, Brakes, Couplings, and Flywheels

Capabilities include:

- rim brake calculations
- annular pad caliper calculations
- button pad caliper calculations
- caliper temperature-rise calculations
- flywheel calculations

Notes:

- includes **iterative approaches** for thermal calculations

### `flexible_elements` — Flexible Mechanical Elements

Capabilities include:

- flat belt analysis
- flat belt design
- flat metal belt calculations
- V-belt analysis
- roller chain selection
- wire rope analysis

Why it matters:

Like gears and bearings, this topic often depends on repeated data lookup from charts and tables. This package moves that effort into code.

---

## What “Design as an API” means in practice

This project does **not** claim to solve every possible design problem.

Instead, it provides a growing set of **typical solve paths** for well-defined classes of machine design problems.

That means:

- the package capabilities are bounded by implemented solve paths
- the workflows are still highly useful because the JSON files are editable
- users can adapt inputs to their own cases instead of being locked to one canned example

So the value proposition is not “universal intelligence.”

The value proposition is:

**programmable engineering workflows for recurring design problems**

---

## Why JSON matters here

Using JSON inputs and outputs is not just a coding choice. It is part of the architecture.

JSON makes it easier to:

- document assumptions
- preserve complete problem statements
- compare cases side by side
- version-control engineering scenarios
- reuse inputs across solver runs
- integrate with future GUIs, dashboards, or cloud services
- support AI-assisted workflows in the future

A hand calculation can be insightful.

A hand calculation that can also become a machine-readable artifact is far more powerful.

---

## Future direction

This repository is intentionally forward-looking.

Some future directions include:

- cloud-backed engineering data lookup
- richer factor libraries and material/property services
- improved plotting and visualization
- embedded animations and interactive engineering explanations
- stronger GUI layers on top of the solver packages
- AI-assisted setup, checking, and interpretation of engineering problems

The long-term vision is larger than a single repo:

**engineering knowledge should become queryable, automatable, and composable**.

That is the deeper meaning of Design as an API.

---

## Current state of the project

This project is best understood as:

- a serious engineering codebase
- a collection of chapter-oriented design packages
- a programmable alternative to repetitive textbook workflows
- an open Python-first experiment in rethinking machine design infrastructure

It is not pretending that the future has fully arrived.

It is a practical step toward it.

---

## Who this may interest

This repository may be useful to:

- mechanical engineering students
- machine design learners
- practicing engineers who want to automate recurring calculations
- developers building engineering software in Python
- anyone interested in computationalizing traditional design workflows

---

## Closing thought

The old workflow says:

> open the textbook, find the chapter, find the table, find the figure, copy the factor, go back to the equation, and hope nothing was missed

This project asks a different question:

> what if design knowledge were structured well enough that engineers could call it like an API?

That is the spirit of this repository.

---

## Repository

GitHub repository: `pablomarcel/design`

Public repo link: <https://github.com/pablomarcel/design>

