# Naver SEO Toolkit — Codex Instructions

## Project Goal
Build an internal toolkit for delivering:
1. Naver carousel structured data
2. Technical SEO optimization
3. Image optimization

Support WordPress, Imweb, Cafe24, custom websites
and other web environments.

## Development Rules
- Use one coordinating Codex session and at most one explicitly delegated Codex CLI session, sequentially, as described below.
- Work on one implementation step at a time.
- Prefer existing libraries and standard APIs.
- Do not build SaaS, dashboards or payment systems.
- Do not implement unrequested features.
- Write small, testable modules.
- Run tests before reporting completion.
- Explain what changed, why, and how it was tested.

## Technical Requirements
- Detect CMS and web frameworks using observable evidence.
- Record the evidence and confidence of detections.
- Return UNKNOWN when technology cannot be identified.
- Separate common SEO logic from platform adapters.
- Keep analysis separate from deployment.
- Never assume access to server-side source code.
- Generate structured data from real page content.
- Validate against official search engine guidelines.
- Never guarantee search ranking or carousel display.

## Safety
- Default to read-only website analysis.
- Limit crawling to approved scope and rate.
- Block SSRF and unsafe network destinations by default.
- Access local/private hosts only when explicitly approved.
- Never modify production sites without approval.
- Do not store customer credentials in source control.
- Back up changes and provide rollback instructions.

## Task Execution Policy

- The current development step is defined by the latest explicit user task.
- Read AGENTS.md and inspect existing code before making changes.
- Preserve completed features, CLI compatibility, and JSON schemas unless changes are explicitly required.
- Reuse existing modules instead of rebuilding equivalent functionality.
- Do not expand the scope beyond the requested development step.
- Separate observed facts, inferred findings, and unverified information.
- Every finding must include reproducible evidence when applicable.
- Do not treat synthetic fixtures as real-world verification.
- Do not modify customer websites without explicit authorization.
- Run relevant tests and full regression tests before reporting completion.
- Report changed files, test results, limitations, and remaining issues.
- Stop after completing the requested step.

## Project Workflow

Customer Intake
-> Environment Detection
-> SEO Audit
-> Carousel and Image Optimization
-> Environment-Specific Implementation
-> Verification and Delivery

Each stage should reuse data and results from previous stages.
Do not implement future stages unless explicitly requested.

## Session Continuity

- 새 세션에서 작업을 시작할 때 `docs/PROJECT_STATE.md`를 읽고 현재 상태를 파악한다.
- 현재 작업과 관련된 코드 및 테스트를 확인한다.
- 문서와 실제 코드가 불일치하면 실제 코드와 테스트 증거를 우선하며 불일치를 보고한다.
- 작업이 끝나면 `docs/PROJECT_STATE.md`를 최신 상태로 갱신한다.
- 완료 기능, 변경 파일, 테스트 결과와 실행 시점, 결정사항, 미해결 문제와 다음 작업을 기록한다.
- 기존 결정사항을 변경한 경우 변경 이유를 남긴다.
- 작업 중단 시 미완료 항목과 다음에 이어야 할 지점을 기록한다.
- 상태 문서는 간결하게 유지하고 모든 대화·도구 출력을 저장하지 않는다. 고객 개인정보·인증정보·고객별 민감 자료는 추적 파일에 포함하지 않는다.
- Git으로 소스·문서 변경 이력을 관리하되, 사용자 승인 없이 Git 커밋을 자동 생성하지 않는다.
- 사용자 요청 없이 다음 개발 STEP을 자동으로 시작하지 않는다.

## Sequential Session Delegation

- 사용자 승인에 따라 조정 세션이 별도 Codex CLI 세션에 범위가 정해진 작업을 위임할 수 있다. 조정 세션 1개와 실행 세션 최대 1개만 사용한다.
- 이 프로젝트의 실행 세션은 사용자 지시에 따라 YOLO(`--dangerously-bypass-approvals-and-sandbox`)로 시작·재개한다. 실행 권한 설정이며 작업 범위·사이트 접근 동의·스테이징/커밋 승인 규칙은 그대로 적용한다.
- 동시에 파일을 수정하는 세션은 1개뿐이어야 한다. 실행 세션 작업 중 조정 세션은 읽기·진행 확인만 하고, 완료 후 결과를 검토한다.
- 실행 세션도 AGENTS.md와 docs/PROJECT_STATE.md를 읽는다. 위임 목표, 허용 변경 파일, 금지 사항, 검증 조건과 종료 지점을 명시한다.
- 실행 세션 ID와 인계 요약·검증 결과를 기록해 같은 ID로 후속 질문한다. 대화·도구 출력 전체를 프로젝트 기록에 복제하지 않는다.
- 실행 세션의 추가 세션·하위 에이전트 생성과 병렬 다중 에이전트 작업은 금지한다. 조정 세션이 최종 보고와 범위 준수를 책임진다.
- 위임은 다음 STEP, 사이트 요청·운영 수정, 스테이징·커밋의 포괄 승인이 아니다. 각각 기존 사용자 승인 범위를 유지한다.
