# EIP-8025 readiness for Hegotá

This document is a single-page document that summarizes the current state of readiness for EIP-8025.

Last updated: 2026-09-27

## Summary

Counts are as of 2026-09-27, out of 7 EL clients, 6 CL clients, 6 guest programs, and 4 zkVMs.

| Workstream | Status | Remaining before Hegotá | Primary sources |
| --- | --- | --- | --- |
| EL specs and tests | Open upstream as draft `execution-specs#2268`; latest `tests-zkevm@v21.0.0`; first benchmark fixtures released | Split, review, and upstream ~17k lines; rebase onto `forks/amsterdam` | [`execution-specs#2268`](https://github.com/ethereum/execution-specs/pull/2268), [releases](https://github.com/ethereum/execution-specs/releases) |
| EL clients | Witness dashboard 4/7; `newPayloadWithWitness` 3/7 | Engine API witness endpoints; land `execution-apis#847` and `#885`; getPayload-with-witness spec | [Hive dashboard](https://eth-act.github.io/eest-execution-witness-dashboard/), [`execution-apis#847`](https://github.com/ethereum/execution-apis/pull/847), [`execution-apis#885`](https://github.com/ethereum/execution-apis/pull/885) |
| CL specs | Merged in master; 4 follow-up PRs open (3 consensus-specs, 1 beacon-APIs) | [`#5593`](https://github.com/ethereum/consensus-specs/pull/5593) and [`#5639`](https://github.com/ethereum/consensus-specs/pull/5639) | [`consensus-specs#5653`](https://github.com/ethereum/consensus-specs/issues/5653) |
| CL clients | Glamsterdam 1/6 done, 2/6 partial; Kurtosis 2/6 | Prysm with real proofs on Gloas; the other four clients | [Lighthouse](https://github.com/eth-act/lighthouse/tree/optional-proofs-gloas) and [Prysm](https://github.com/OffchainLabs/prysm/tree/eip8025-optional-proofs) branches, [`prysm#17490`](https://github.com/OffchainLabs/prysm/pull/17490) |
| Guest programs | 6 tracked; EEST across zkVMs 1/6; open-source CI 6/6 | EEST coverage, signed ELF and VK releases, licensing | [Guest program handbook](https://github.com/eth-act/zkevm-standards/blob/main/handbooks/guest-handbook.md), [Hive dashboard](https://eth-act.github.io/eest-execution-witness-dashboard/) |
| zkVMs | 4 tracked; RISC-V target 2/4; 6 standards proposed | Standards conformance, formal verification and real-time proving criteria, proof-size evidence | [zkVM handbook](https://github.com/eth-act/zkevm-standards/blob/main/handbooks/zkvm-handbook.md), [ISA monitor](https://eth-act.github.io/zkevm-test-monitor/), [`zkevm-standards`](https://github.com/eth-act/zkevm-standards) |
| Infrastructure and tooling | Implemented and in use on Glamsterdam devnets | Runbooks, metrics, ecosystem integration | [Section below](#infrastructure-and-tooling) |
| Benchmarks and repricing | Proving-time research done; benchmark fixtures released | Comparison tables, repricing, sub-block threshold, historical campaign | [Section below](#benchmarks-and-repricing) |

## ACD progress

EIP-8025 was [PFIed in ACD #178 (May 14, 2026)](https://www.youtube.com/watch?t=4147&v=tZIY3IybQh4); the case for CFI, and the open questions around it, are in [ACD.md](ACD.md).

## Blocked on CFI

These items are waiting only for EIP-8025 to be Considered for Inclusion (CFI):

- Move the [execution-witness dashboard](https://eth-act.github.io/eest-execution-witness-dashboard/) into official Hive.
- Switch witness-generation test runs to the SSZ Engine API.

## Execution layer: specifications and tests

- **Specifications:** Defined in [`execution-specs@projects/zkevm`](https://github.com/ethereum/execution-specs/tree/projects/zkevm), open upstream as [`execution-specs#2268`](https://github.com/ethereum/execution-specs/pull/2268) against `forks/amsterdam`.
  - Stateful execution layer (EL) specifications for guest program input generation.
  - End-to-end guest program specifications.
  - zkEVM test releases have been published and maintained since April 2025, initially in `execution-spec-tests` and now in `execution-specs`. The latest is [`tests-zkevm@v21.0.0`](https://github.com/ethereum/execution-specs/releases/tag/tests-zkevm%40v21.0.0) (September 24, 2026), based on [`tests@v21.0.0`](https://github.com/ethereum/execution-specs/releases/tag/tests%40v21.0.0) (Glamsterdam on Sepolia). Starting with this release, `tests-zkevm@` version numbers follow the upstream `tests@` release they are based on.

    <details>
    <summary>Release history (newest first)</summary>

    Current [`ethereum/execution-specs`](https://github.com/ethereum/execution-specs/releases) `tests-zkevm@` series:

    | Release | Based on |
    | --- | --- |
    | [`tests-zkevm@v21.0.0`](https://github.com/ethereum/execution-specs/releases/tag/tests-zkevm%40v21.0.0) | [`tests@v21.0.0`](https://github.com/ethereum/execution-specs/releases/tag/tests%40v21.0.0) (Glamsterdam on Sepolia) |
    | [`tests-zkevm@v0.8.4`](https://github.com/ethereum/execution-specs/releases/tag/tests-zkevm%40v0.8.4) | `glamsterdam-devnet-8` ([`tests-glamsterdam-devnet@v8.1.4`](https://github.com/ethereum/execution-specs/releases/tag/tests-glamsterdam-devnet%40v8.1.4)) |
    | [`tests-zkevm@v0.8.3`](https://github.com/ethereum/execution-specs/releases/tag/tests-zkevm%40v0.8.3) | `glamsterdam-devnet-8` ([`tests-glamsterdam-devnet@v8.1.3`](https://github.com/ethereum/execution-specs/releases/tag/tests-glamsterdam-devnet%40v8.1.3)) |
    | [`tests-zkevm@v0.8.2`](https://github.com/ethereum/execution-specs/releases/tag/tests-zkevm%40v0.8.2) | `glamsterdam-devnet-8` ([`tests-glamsterdam-devnet@v8.1.0`](https://github.com/ethereum/execution-specs/releases/tag/tests-glamsterdam-devnet%40v8.1.0)) |
    | [`tests-zkevm@v0.8.0`](https://github.com/ethereum/execution-specs/releases/tag/tests-zkevm%40v0.8.0) | `glamsterdam-devnet-8` ([`tests-glamsterdam-devnet@v8.1.0`](https://github.com/ethereum/execution-specs/releases/tag/tests-glamsterdam-devnet%40v8.1.0)) |
    | [`tests-zkevm@v0.6.2`](https://github.com/ethereum/execution-specs/releases/tag/tests-zkevm%40v0.6.2) | `glamsterdam-devnet-7` |
    | [`tests-zkevm@v0.6.1`](https://github.com/ethereum/execution-specs/releases/tag/tests-zkevm%40v0.6.1) | `glamsterdam-devnet-7` |
    | [`tests-zkevm@v0.6.0`](https://github.com/ethereum/execution-specs/releases/tag/tests-zkevm%40v0.6.0) | `glamsterdam-devnet-7` |
    | [`tests-zkevm@v0.5.0`](https://github.com/ethereum/execution-specs/releases/tag/tests-zkevm%40v0.5.0) | `glamsterdam-devnet-6` |
    | [`tests-zkevm@v0.4.1`](https://github.com/ethereum/execution-specs/releases/tag/tests-zkevm%40v0.4.1) | `bal-devnet-7` |

    Original [`ethereum/execution-spec-tests`](https://github.com/ethereum/execution-spec-tests/releases) `zkevm@` series:

    | Release | Based on |
    | --- | --- |
    | [`zkevm@v0.4.0`](https://github.com/ethereum/execution-spec-tests/releases/tag/zkevm%40v0.4.0) | `bal-devnet-7` |
    | [`zkevm@v0.3.4`](https://github.com/ethereum/execution-spec-tests/releases/tag/zkevm%40v0.3.4) | `bal-devnet-3` |
    | [`zkevm@v0.3.3`](https://github.com/ethereum/execution-spec-tests/releases/tag/zkevm%40v0.3.3) | `bal-devnet-3` |
    | [`zkevm@v0.3.2`](https://github.com/ethereum/execution-spec-tests/releases/tag/zkevm%40v0.3.2) | `bal-devnet-3` |
    | [`zkevm@v0.3.1`](https://github.com/ethereum/execution-spec-tests/releases/tag/zkevm%40v0.3.1) | `bal-devnet-3` |
    | [`zkevm@v0.3.0`](https://github.com/ethereum/execution-spec-tests/releases/tag/zkevm%40v0.3.0) | `bal-devnet-3` |
    | [`zkevm@v0.2.0`](https://github.com/ethereum/execution-spec-tests/releases/tag/zkevm%40v0.2.0) | — |
    | [`zkevm@v0.1.0`](https://github.com/ethereum/execution-spec-tests/releases/tag/zkevm%40v0.1.0) | — |
    | [`zkevm@v0.0.2`](https://github.com/ethereum/execution-spec-tests/releases/tag/zkevm%40v0.0.2) | — |
    | [`zkevm@v0.0.1`](https://github.com/ethereum/execution-spec-tests/releases/tag/zkevm%40v0.0.1) | — |

    </details>

- **Testing:** Integrated into the Ethereum Execution Spec Tests (EEST) framework (e.g. `t8n` changes, testing framework capabilities, and fixture format adjustments).

- **Benchmarks** (as of 2026-09-27):
  - Stateless benchmark releases: done. They started with [`tests-zkevm-benchmark@v0.8.2`](https://github.com/ethereum/execution-specs/releases/tag/tests-zkevm-benchmark%40v0.8.2) (August 18, 2026): Amsterdam compute benchmarks at 10M, 30M, and 60M gas, tagged on the same commit as `tests-zkevm@v0.8.2`.
  - Stateful benchmark releases: not started. The plan is to integrate them into STEEL's existing stateful filling infrastructure.

## Execution layer: clients

Counts are as of 2026-09-27, out of 7 EL clients: Besu, Erigon, Ethrex, Geth, Nethermind, Nimbus, and Reth.

- **Execution-witness dashboard:** 4/7 done, 2/7 partial. The [Hive dashboard](https://eth-act.github.io/eest-execution-witness-dashboard/) runs EEST fixtures (`tests-zkevm@v0.8.4` as of 2026-09-27) against each client's execution-witness generation.
- **`engine_newPayloadWithWitness{V4,V5}`:** 3/7 done, 3/7 partial.
- **`debug_executionWitness`:** 0/7 conformant with the proposed spec, 5/7 partial. Spec: open draft [`execution-apis#847`](https://github.com/ethereum/execution-apis/pull/847).
- **REST+SSZ `POST /engine/v1/payloads/witness`:** 1/7 partial. Spec: open [`execution-apis#885`](https://github.com/ethereum/execution-apis/pull/885).
- **Block building with witness** (getPayload, both JSON-RPC and REST+SSZ): waiting for a spec.

## Consensus layer: specifications

- **Specifications:** Merged in `consensus-specs` master, at [`ethereum/consensus-specs@master/specs/_features/eip8025`](https://github.com/ethereum/consensus-specs/tree/master/specs/_features/eip8025).
  - Proof-generating mode requests proofs and broadcasts them on the `execution_proof` gossip topic.
  - Proof-verifying mode consumes gossiped proofs and verifies them statelessly.
  - Includes the `ProofEngine` interface, proof gossip, request/response synchronization, and `eproof` Ethereum Node Record (ENR) discovery.
  - The spec tests stay in master: [`consensus-specs#5622`](https://github.com/ethereum/consensus-specs/pull/5622), which proposed removing them until CFI, was closed without merging on 2026-09-24.
- **Tracking issue:** [`consensus-specs#5653`](https://github.com/ethereum/consensus-specs/issues/5653).
- **Open follow-ups** (as of 2026-09-27):
  - [`consensus-specs#5593`](https://github.com/ethereum/consensus-specs/pull/5593): refine `ProofData` and gossip validation. Ready for review.
  - [`consensus-specs#5639`](https://github.com/ethereum/consensus-specs/pull/5639): make the `ProofEngine` validation-only and remove the proof-generation interfaces, leaving proof production to middleware outside the specification. Draft; depends on #5593.
  - [`consensus-specs#5534`](https://github.com/ethereum/consensus-specs/pull/5534): recursive execution proof guest. Draft.
  - [`beacon-APIs#569`](https://github.com/ethereum/beacon-APIs/pull/569): Beacon API endpoints for proof retrieval and submission.

## Consensus layer: clients

Counts are as of 2026-09-27, out of 6 CL clients: Grandine, Lighthouse, Lodestar, Nimbus, Prysm, and Teku.

- **Implementation on Glamsterdam:** 1/6 done, 2/6 partial.
  - Lighthouse: [`eth-act/lighthouse@optional-proofs-gloas`](https://github.com/eth-act/lighthouse/tree/optional-proofs-gloas).
  - Prysm: [`OffchainLabs/prysm@eip8025-optional-proofs`](https://github.com/OffchainLabs/prysm/tree/eip8025-optional-proofs), with work-in-progress draft [`prysm#17490`](https://github.com/OffchainLabs/prysm/pull/17490).
  - Grandine: [`eip8025-grandine/grandine@feature/eip8025`](https://github.com/eip8025-grandine/grandine/tree/feature/eip8025).
  - Prototypes in Teku ([`Consensys/teku@optional-proofs`](https://github.com/Consensys/teku/tree/optional-proofs)), Nimbus (draft [`nimbus-eth2#8004`](https://github.com/status-im/nimbus-eth2/pull/8004)), and Lodestar ([`ChainSafe/lodestar@optional-proofs`](https://github.com/ChainSafe/lodestar/tree/optional-proofs)).
- **[zkboost](https://github.com/eth-act/zkboost) integration:** 1/6 done, 1/6 partial.
- **Kurtosis integration:** 2/6, through the zkboost support in [`ethpandaops/ethereum-package`](https://github.com/ethpandaops/ethereum-package/tree/main/src/zkboost).
- **Testing:**
  - Fulu: Kurtosis devnet with mocked and real proofs working, using the earlier Fulu-based `optional-proofs` branches of Lighthouse and Prysm.
  - Glamsterdam: in progress. Prysm on Gloas still runs with mocked proofs and a zkboost fork.

## Guest programs

Counts are as of 2026-09-27, out of 6 guest programs: Ethrex, evm-asm, Nethermind, Nimbus, Reth, and Zesu. They are assessed against the [guest program handbook](https://github.com/eth-act/zkevm-standards/blob/main/handbooks/guest-handbook.md#guest-program-rubric) rubric.

- **ELF builds via public, fully open-source CI:** 6/6.
- **RISC-V target:** 5/6.
- **MIT + Apache 2.0 dual licensing:** 4/6.
- **Signed ELF and verification-key release assets:** 2/6 done, 3/6 partial.
- **EEST tests passing across zkVMs:** 1/6 done, 2/6 partial, on the [Hive dashboard](https://eth-act.github.io/eest-execution-witness-dashboard/) (`tests-zkevm@v0.8.4` as of 2026-09-27).
- **zkevm-standards interfaces** (I/O, accelerator C interface, memory operations, entry point and linking, ELF compliance, exit codes): mostly not yet assessed.
- **Formal verification of guest-program ELFs:** assessment criteria not yet defined.

## zkVMs

Counts are as of 2026-09-27, out of 4 zkVMs: lambda-vm, OpenVM, SP1, and ZisK. They are assessed against the [zkVM handbook](https://github.com/eth-act/zkevm-standards/blob/main/handbooks/zkvm-handbook.md#zkvm-rubric) rubric.

- **MIT + Apache 2.0 dual licensing:** 4/4.
- **Deterministic program verification-key generation:** 3/4.
- **RISC-V target:** 2/4 done, 1/4 partial. The [RISC-V Compliance Test Monitor](https://eth-act.github.io/zkevm-test-monitor/) publishes ISA compliance results for supported zkVMs ([source repository](https://github.com/eth-act/zkevm-test-monitor)).
- **ELF loading and validation, execution termination semantics:** partial on 4/4.
- **Cluster-mode support documented:** 2/4.
- **Final proof size ≤300 KiB:** not yet established on any.
- **EF cryptography review:** delayed.
- **Circuit formal verification, real-time proving on the EF reference cluster:** assessment criteria not yet defined.
- **Standards pipeline:** 6 proposals open in [`eth-act/zkevm-standards`](https://github.com/eth-act/zkevm-standards/pulls) and [9 open issues](https://github.com/eth-act/zkevm-standards/issues?q=is%3Aissue%20is%3Aopen), as of 2026-09-27. The proposals are host randomness ([#42](https://github.com/eth-act/zkevm-standards/pull/42)), proving cost estimation ([#36](https://github.com/eth-act/zkevm-standards/pull/36)), a logging function ([#27](https://github.com/eth-act/zkevm-standards/pull/27)), the Keccak-f[1600] permutation ([#26](https://github.com/eth-act/zkevm-standards/pull/26)), a U256 interface ([#22](https://github.com/eth-act/zkevm-standards/pull/22)), and minimum memory resources ([#20](https://github.com/eth-act/zkevm-standards/pull/20)).

## Infrastructure and tooling

- **Proving:**
  - [`eth-act/ere`](https://github.com/eth-act/ere) — Provides a unified interface and toolkit for compiling, executing, proving, and verifying programs across multiple zkVMs.
  - [`eth-act/ere-guests`](https://github.com/eth-act/ere-guests) — Maintains reusable libraries and compilation tooling for Ethereum guest programs across zkVMs with Ere.
  - [`eth-act/zkevm-benchmark-workload`](https://github.com/eth-act/zkevm-benchmark-workload) — Benchmarks Ethereum guest programs execution, proving, and verification across multiple zkVMs using EEST test and benchmark releases, and real mainnet/devnet blocks.
  - [`eth-act/zkboost`](https://github.com/eth-act/zkboost) — Implements an EIP-8025 proof node that serves consensus-client requests for execution-proof generation and verification through Ere-backed zkVMs.
  - [`ethpandaops/proofessoor`](https://ethpandaops.io/docs/tooling/proofessoor/) — Requests proofs of Ethereum execution blocks from zkboost and tracks each request through completion.
- **Devnets:**
  - Mocked and real proving support in the Kurtosis [`ethereum-package`](https://github.com/ethpandaops/ethereum-package).
  - Stateless-input artifacts allowing EIP-8025 proving on Glamsterdam devnets:
    - [R2 bucket for `glamsterdam-devnet-5` stateless inputs](https://pub-5345007fbd06486bbb7cbbe9f3112c45.r2.dev/devnets/glamsterdam-devnet-5/index.html)
    - [R2 bucket for `glamsterdam-devnet-7` stateless inputs](https://pub-df22334654034ebab51bc096137a59d8.r2.dev/devnets/glamsterdam-devnet-7/index.html)
    - [R2 bucket for `glamsterdam-devnet-8` stateless inputs](https://pub-760ad8b3dd9547539f829c1ea30f18b5.r2.dev/devnets/glamsterdam-devnet-8/index.html)

## Benchmarks and repricing

- **Done:**
  - Research on available proving time: [proving-time scenarios](https://jsign.github.io/proving-time-scenarios/).
  - Benchmark fixture releases: see [Execution layer: specifications and tests](#execution-layer-specifications-and-tests).
- **Pending** (as of 2026-09-27):
  - Comparison tables by zkVM and guest program, for mainnet blocks and for EEST worst cases, possibly using [zkevm-prof](https://han0110.github.io/zkevm-prof/) data.
  - Gas repricing analysis for the worst cases, using [`evm-gasfit`](https://github.com/jsign/evm-gasfit).
  - The gas limit at which serial execution uses up the available proving time for each zkVM, which is when sub-block proving becomes necessary.
  - A correctness campaign across historical mainnet blocks: generate witnesses for older forks and validate guest programs on a large historical block set.

## Coordination: zkEVM breakout calls

| Call | Date | Resources |
| ---: | --- | --- |
| 8 | September 9, 2026 | [Recording & notes](https://forkcast.org/calls/zkevm/008) · [Slides](breakout-calls/008/) |
| 7 | August 12, 2026 | [Recording & notes](https://forkcast.org/calls/zkevm/007) · [Slides](breakout-calls/007/) |
| 6 | July 8, 2026 | [Recording & notes](https://forkcast.org/calls/zkevm/006) · [Slides](breakout-calls/006/) |
| 5 | June 10, 2026 | [Recording & notes](https://forkcast.org/calls/zkevm/005) · [Slides](breakout-calls/005/) |
| 4 | May 13, 2026 | [Recording & notes](https://forkcast.org/calls/zkevm/004) · [Slides](breakout-calls/004/) |
| 3 | April 8, 2026 | [Recording & notes](https://forkcast.org/calls/zkevm/003) · [Slides](breakout-calls/003/) |
| 2 | March 11, 2026 | [Recording & notes](https://forkcast.org/calls/zkevm/002) · [Slides](breakout-calls/002/) |
| 1 | February 11, 2026 | [Recording & notes](https://forkcast.org/calls/zkevm/001) · [Slides](breakout-calls/001/) |

## Further reading

For technical deep dives on EIP-8025, zkVM performance, interoperability standards, and security, see the [zkEVM Team blog](https://zkevm.ethereum.foundation/blog).
