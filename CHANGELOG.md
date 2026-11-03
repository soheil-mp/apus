# Changelog

## 0.1.0 (2026-11-03)


### Features

* **core:** add coordinate frames and transformations ([990ffdf](https://github.com/soheil-mp/apus/commit/990ffdfc83aa1c60f42af104729773e301159b7c))
* **core:** add domain types for sites, frames, detections, tracks and advisories ([170c5a6](https://github.com/soheil-mp/apus/commit/170c5a6f9b7fd6247710d44808211e219730aa48))
* **core:** add the lidar packet wire format ([7274466](https://github.com/soheil-mp/apus/commit/72744663c182f361d211821b72ef04553d3f264e))
* **core:** add the time model and clock-skew policy ([d611507](https://github.com/soheil-mp/apus/commit/d6115075c07a4cd2886d8e51911c28bb2aa8360c))
* **edge:** add the minimal edge pipeline from datagrams to track updates ([251aef3](https://github.com/soheil-mp/apus/commit/251aef3e67dd998105d74b0081dfdeb982f5f63f))
* **proto:** add the TrackUpdate v1 message schema with Buf checks ([b492ee2](https://github.com/soheil-mp/apus/commit/b492ee2fc08df38bf404a47ac8e03415c8dddff9))
* **sim:** add the minimal straight-line simulator ([ea18f33](https://github.com/soheil-mp/apus/commit/ea18f337701780c33ca45d0d024e666ea69055c9))
* sync roadmap items to GitHub milestones and issues ([bec0555](https://github.com/soheil-mp/apus/commit/bec05552567751d6b9d54168d5c1c3c8968d27ef))


### Documentation

* add contributing guide, code of conduct, security policy and templates ([7f3bdf0](https://github.com/soheil-mp/apus/commit/7f3bdf040af076eecb139eebf76061b2034b0207))
* add contributor and assistant working rules ([97b60a4](https://github.com/soheil-mp/apus/commit/97b60a4751030d7a8700371dcf0ee854bc27b544))
* add README with purpose, audience, stack and setup ([ccf6bcf](https://github.com/soheil-mp/apus/commit/ccf6bcfd5fe015e9e7277b28a2c7c4946496097a))
* add roadmap with 21 milestones and 849 estimated hours ([26c26fd](https://github.com/soheil-mp/apus/commit/26c26fd5a79dcfd9807f35bc82d66593f3cdaf4d))
* add target architecture with context, edge, data-flow views ([5db2ce6](https://github.com/soheil-mp/apus/commit/5db2ce6c52c3ea919ab997b29282bd519fb25e22))
* **adr:** record the first ten architecture decisions ([467b7a9](https://github.com/soheil-mp/apus/commit/467b7a99a1c4067cdcc8f00497af14249016d8c9))
* describe the walking skeleton in the README and roadmap status ([03d157e](https://github.com/soheil-mp/apus/commit/03d157e1247e2922fb12d395bfdc5b503aa74b04))
* publish a Zensical documentation site to GitHub Pages ([628d8f0](https://github.com/soheil-mp/apus/commit/628d8f0050f7d7758d119a03dfb5fc0da582d55e))
* **research:** add domain research on lidar bird-flight monitoring ([f98acf5](https://github.com/soheil-mp/apus/commit/f98acf5eb746ddeaf87d6d3421f54147517f3f32))
* **research:** document data sources and technology selection ([1ced0ec](https://github.com/soheil-mp/apus/commit/1ced0ecb570ab7dba7c47c49307addb298dc9ebe))


### Build system

* add just task runner and a devcontainer ([3f55c76](https://github.com/soheil-mp/apus/commit/3f55c76206125f09d8ab90807b4161afc56c70cb))
* add Renovate and a dependency licence and scope check ([ffef1e1](https://github.com/soheil-mp/apus/commit/ffef1e1f2c28e379b9326935ecf566a20ea1fe39))
* **proto:** generate Python code for the schemas and add message conversions ([dbe3515](https://github.com/soheil-mp/apus/commit/dbe3515286c2e92eb0e0cd2f08a2e9bde5481de1))
* set up the uv workspace with six packages and quality tooling ([4f8d79b](https://github.com/soheil-mp/apus/commit/4f8d79ba1efa2973dc1432fa5f2a322b61c4d07a))


### Continuous integration

* add GitHub Actions workflow for lint, types, hooks and tests ([6e99b5f](https://github.com/soheil-mp/apus/commit/6e99b5fac8a9e708ec77ce1e92782a631d00be10))
* automate releases with release-please and add citation metadata ([23a2c8f](https://github.com/soheil-mp/apus/commit/23a2c8f401f470d9ccbe1d6b593fd3a67c5acef8))


### Tests

* enforce ground-truth isolation and edge layering with import contracts ([40f41e7](https://github.com/soheil-mp/apus/commit/40f41e78441ea9d31cf4732f0a740d5e07434d39))
