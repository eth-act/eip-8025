# EIP-8025 and the Hegotá network upgrade

This document contains argument to justify EIP-8025's inclusion in Hegotá.  

TL;DR: EIP-8025 adds optional, non-attestation execution proofs: altruistic provers generate proofs of payload validity and gossip them, and opting-in nodes receive and verify only for metric collection and reporting. Every validator keeps re-executing payloads and attesting exactly as it does today.

We believe execution proofs are likely to become important as Ethereum scales: they could allow anyone to verify the chain's correct progression while avoiding proportional increases in storage, compute, and bandwidth requirements, even as throughput scales. EIP-8025 itself does not make proofs mandatory.

We believe five things make EIP-8025 worth doing in Hegotá:

- It front-runs the engineering that mandatory proofs would need while leaving the cryptography open: the parts that are reusable across proving systems get built and exercised now, and no zkVM or proving system is selected.
- Most of the work already exists, which bounds the cost. EL and CL specifications, two interoperating CL clients, witness construction upstreamed in most stateful ELs, and proving infrastructure in active use on Glamsterdam devnets.
- Nothing in EIP-8025 is consensus-critical, so it can be dropped at any point if it gets in the way of fork delivery. It cannot delay the fork.
- It would collect metrics and give pandaops and engineering teams operational experience on mainnet, supporting a smooth, de-risked transition to mandatory proofs.
- It would leave the protocol prepared integrating other big upcoming protocol changes i.e. new state tree in I*.
- It would allow ealier experimentation with other protocol features e.g. [validity-only partial statelessness (VOPS)](https://ethresear.ch/t/a-pragmatic-path-towards-validity-only-partial-statelessness-vops/22236).

It would **not**:

- change the canonical state-transition function, or let proofs influence payload acceptance, fork choice, or attestation in any way whatsoever
- change the behavior, bandwidth use, or attestation duties of operators who do not opt in
- select the final zkVM, proving system, guest program, or verification keys, or prejudge whether or when Ethereum should make execution proofs mandatory

A proposal for mandatory proofs would still have to resolve prover incentives, how large a gas-limit increase is safe, and the resulting state growth. EIP-8025 neither answers those questions nor needs to; Ethereum would have to resolve them before any transition away from re-execution (see [ACD Q&A](#acd-qa)).

## ACD progress

EIP-8025 was [PFIed in ACD #178 (May 14, 2026)](https://www.youtube.com/watch?t=4147&v=tZIY3IybQh4). See [`PFI/`](PFI/) for related assets.

The next step is proposing it for CFI.

## Case for CFI of EIP-8025

We believe the work completed so far justifies proposing EIP-8025 for CFI in Hegotá.

| EIP-7723 requirement | Where EIP-8025 stands |
| --- | --- |
| Proposed for Inclusion, and reviewed by client developers | Presented at ACDC #178 on May 14, 2026 |
| A Python implementation with tests in `execution-specs`, submitted as an open PR (`SHOULD`) | [`execution-specs#2268`](https://github.com/ethereum/execution-specs/pull/2268) is open, carrying the guest program, stateless interfaces, host-side witness construction, and ~163 conformance tests, with `tests-zkevm@` releases maintained since April 2025. It is a draft, based on `forks/amsterdam`. |
| Intent to attempt inclusion in devnets | Already rehearsed rather than intended: Kurtosis `ethereum-package` support, stateless-input artifacts for `glamsterdam-devnet-5` and `-7`, and Lighthouse and Prysm interoperating with a GPU prover. More details in the [readiness section](PROGRESS.md#summary). |
| Updates at this stage accompanied by updates to implementation and tests (`SHOULD`) | Already the working for at least six months of rebases across Glamsterdam devnets, owned by the zkEVM team |

The consensus-layer half went further than CFI asks: [`specs/_features/eip8025`](https://github.com/ethereum/consensus-specs/tree/master/specs/_features/eip8025) is merged in `consensus-specs` master. The work that remains is concentrated in `execution-specs`, mainly with the intention of upstreaming code.

## ACD Q&A

This section addresses questions we have received about EIP-8025 in Hegotá, along with others we expect ACD participants to raise.

### Why does EIP-8025 need to be scheduled in a fork?

EIP-8025 does not strictly _need_ a hard fork from the perspective of protocol changes. What it needs is a formal review, upstreaming, and integration capacity from specification, CL, and EL teams, along with support in ethPandaOps tooling.

Much of this upstream work is orthogonal to other EIPs in Hegotá. STEEL and ethPandaOps may be able to continue it in the background, but requesting capacity through ACD is more transparent and predictable. It is also fairer to work already scheduled for the fork, because EIP-8025 would no longer draw on unallocated resources.

We encourage core developers to ask the STEEL and ethPandaOps teams for their assessment. We have worked closely with both teams over the last six months, keeping them up to date while maintaining the forks and rebasing across Glamsterdam without requesting extra resources. With appropriate capacity from those teams, we believe the work is ready for a smooth upstreaming process.

### Why consider an EIP that only is essentially a request for resources?

The use of execution proofs to scale Ethereum has been under consideration [for more than eight years](https://ethresear.ch/t/delayed-state-execution-finality-and-cross-chain-operations/987). It seems reasonable to consider derisking steps, like EIP-8025, on a case-by-case basis so that we can properly gather data and maintain extremely high security standards. Apart from the Ethereum strategic arguments, refer to the next q&a regarding readiness.

### How ready is EIP-8025 to be included in Hegotá?

Beyond the specifications, tests, and devnet exercise covered in the [eligibility table](#case-for-cfi-of-eip-8025), multiple stateful ELs have upstreamed witness-construction changes and pass most of the execution-witness tests ([Hive dashboard](https://eth-act.github.io/eest-execution-witness-dashboard/#/group/tests-zkevm%20v0.6.2)).

Twelve months of work across multiple teams and devnet iterations produced this. Per-workstream detail is in the [readiness register](PROGRESS.md).

Work remains:

- upstream review and merging, highly concentrated in `execution-specs`
- client implementation, hardening, and interoperability testing beyond Lighthouse and Prysm
- upstreaming and wider integration into tools such as Hive and Dora
- benchmarking, optimizing, and formal verification of guest programs and zkVMs, to a higher bar than non-critical-path proofs strictly require

Receiving CFI from ACD would allow this work to proceed faster and more efficiently.

### What would be the practical "cost" for Hegotá?

Although we believe most of the work is in good shape, calling it cost-free would be misleading. Even non-attestation proofs need specification review, client integration, testing, and long-term maintenance, but we think this workload is small.

| Workstream | Existing work | Hegotá remaining work |
| --- | --- | --- |
| Execution specifications | EL specifications, conformance tests, and maintained zkEVM test releases, open as [`execution-specs#2268`](https://github.com/ethereum/execution-specs/pull/2268) | Prepare, review, split, and upstream ~16k existing lines; rebase from `forks/amsterdam` and keep them aligned with the fork |
| Consensus specifications | Feature specifications and tests merged in `consensus-specs` master | Maintain fork alignment, pin open parameters |
| EL clients | Witness-construction changes upstreamed in most stateful clients | Complete and harden witness-construction coverage; keep it aligned as the fork's STF settles |
| CL clients | Lighthouse and Prysm, with demonstrated interoperability | Upstream and harden both and remaining clients, and complete cross-client testing |
| Infrastructure and proving | Proving, Kurtosis support, observability, and testing infrastructure in active use | Production runbooks, metrics, and integration into existing ecosystem tools |
| Security, zkVMs, and documentation | zkVM standards, published ISA-compliance results, and cross-zkVM benchmarking of guest programs | Expand testing and formal verification coverage, refine security analysis, and add more documentation |

Most of the ~16k-line `execution-specs` diff does not modify the current state-transition function. It builds the architecture and testing support that stateless validation needs:

- new `t8n` parameters for stateless-execution artifacts (`executionWitness`, `statelessInputBytes`, `statelessOutputBytes`)
- testing-framework constructs such as execution-witness mutators and other coverage support
- adjacent data structures, such as a partial MPT for proof construction, which depend on internal repository APIs not promised as stable; a typical EIP does not reach into repository internals at all
- end-to-end modeling of the Engine API, because a guest program must prove a fully stateless `execution_newPayload` call, not only the STF
- SSZ support and dependencies not yet in the framework, expected to serve other shared needs

Depending on those internals is what makes rebasing expensive: every healthy refactor upstream lands on us. Six months of rebasing across Glamsterdam devnets is the evidence, and we have shared the specifics with STEEL as we hit them.

STEEL has offered to help upstream the work, and we meet with them regularly to plan it, but goodwill is not prioritization. CFI would allocate review, upstreaming, and integration capacity for work that already exists, not redesign or reimplementation.

We have also taken a reuse-first approach with forked tools such as Hive, extending established architectures only where necessary to keep both the upstreaming burden and the added surface area small.

### What are the risks and their blast radius?

It is worth clarifying again: EL re-execution remains the sole basis for payload acceptance, fork choice, and attestation. A proof-verification outcome is diagnostic: it may be recorded and reported, but never influences those decisions, and a missing, late, duplicated, or invalid proof can never delay an attestation. The metrics-gathering functionality is off by default.

Opting in does carry cost:

- Bandwidth: subscribing to the new proof gossip channels or reporting captured metrics will consume extra bandwidth, which can interfere indirectly with other network traffic.
- Storage and serving: proof-aware nodes must retain proofs for canonical blocks back to the finalized checkpoint and serve them to other opt-in nodes.
- CPU: logging and metrics capture consume CPU cycles, which are shared with everything else the node does.

Provers are new actors in the network that take on hardware cost, and that risk stays local: a prover that is slow, crashes, or misbehaves cannot affect network consensus.

### Why in Hegotá and not in later forks?

Waiting would:

- defer EL, CL, specification, and infrastructure work into the same fork where proof security, liveness, and performance first become consensus-critical
- increase the risk of a single "big bang" transition to mandatory proofs instead of incremental iteration; there will be always a more immediate thing to do in forks
- keep ethPandaOps and other infrastructure operators from learning how proof generation and distribution behave in their tooling
- spend engineering time rebasing the `execution-specs` branch instead of improving performance, security, and formal assurance; each rebase consumes resources that could otherwise be spent on more valuable protocol work
- make more difficult to asses zkVM impact of other upcoming EIP changes (e.g. state tree change) since more rebasing of parallel work is needed.

We think being optional is not itself a reason to keep EIP-8025 out of a fork. A more immediately user-visible proposal will almost always be competing for the same capacity; the tradeoff is against the risk this work removes from a transition Ethereum is likely to make anyway. We think of it as a strategic move with high long-term return on investment.

### What if a zkVM or proving system 100 times better than current systems appears later?

EIP-8025 standardizes what is reusable across proving technologies: stateless-execution semantics, the witness format, and the CL and tooling integration, for which a proof is opaque bytes. Innovation below that line reaches EIP-8025 only through proof formats and verification keys, which are easy to change.

### Who will generate proofs on mainnet without incentives?

Because EIP-8025 proofs are optional, the question of prover incentives does not require a definitive answer for this proposal. Prover incentives remain an open research problem for a potential mandatory proofs proposal.

The EF will dedicate its proving cluster to generating proofs and help other teams and entities take on the optional prover role. Making EIP-8025 part of a fork would give that role a clear place in the network and allow engineering and DevOps teams to build operational experience with it.

### How will proving performance keep up with increasing gas limits?

This is a fair question, and it is one reason we want to make EIP-8025 a first-class part of the protocol. Both guest programs and zkVMs will require optimization and evaluation as gas limits increase.

We also believe that introducing EIP-8025 would require protocol discussions to consider how changes could affect a future transition to mandatory proofs. This does not mean blocking protocol changes, but being careful not to create avoidable problems when small design variations would suffice.

### Given that these proofs are optional, how should we approach security?

Although EIP-8025 does not put Ethereum's security at risk after inclusion, we want both guest programs and zkVM security assessments to meet a high standard. In addition to following engineering best practices, we will establish and maintain robust test coverage, stress test the systems for liveness using fuzzing, and employ formal verification (FV) to establish spec compliance of both zkVMs and guest programs.

This work also accumulates progress, knowledge, and documentation for a smoother transition to mandatory proofs, and we believe it could make stateful ELs safer as well.

### What is the relationship between "prover killers" and EIP-8025?

Worst-case blocks are a blocker for mandatory proofs, not EIP-8025. EIP-8025 makes proofs optional partly because we cannot currently guarantee that every valid block can be proved in time.

Examples of why this guarantee is not currently possible include:

- [Bytecode chunkification](https://ethresear.ch/t/merkelizing-bytecode-options-tradeoffs/22255) does not exist today and probably will not until [Partitioned Binary Tree](https://eips.ethereum.org/EIPS/eip-8297) is implemented.
- Opcodes and precompiles require repricing, which might occur under the current unidimensional pricing model or a future multidimensional model.
