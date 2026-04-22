# Summary 작성 규칙

> Phase 7 (raw.md → `summary.md` + `abstract.md` 작성) 시 Claude 가 따를 규칙.
> 이 파일은 wj926/paper-summary (MIT) 의 `summary_rules.md` 를 차용하고,
> paper-search 고유인 **§ 왜 이 프로젝트와 관련 있는가** 섹션에 대한 예외 조항만 추가.

## 0. 폴더명 · venue 결정

### 0.1 폴더명 규칙

`<N>_<firstauthor><year><METHOD>(<venue><year>)` — 이미 §6 `build_paper_folder.py` 가 생성. Claude 는 수정하지 말 것.

- `<N>`: 해당 `/paper-search` 실행의 ranking 순서 (01부터).
- `<firstauthor>`: 제1저자 성 (소문자). 예: `zhu`, `kim`, `qi`.
- `<year>`: 논문 연도 (4자리).
- `<METHOD>`: 논문 title/abstract 에서 추출한 대문자 acronym 우선. 예: `DPO`, `LoRA`, `TRANSFORMER`. 적절한 것이 없으면 생략 (build_paper_folder 가 `--method` 없이 호출되면 자동 생략).
- `<venue><year>`: 학회 약어 + 연도. 예: `ICML2025`, `NeurIPS2025`, `ICLR2026`.

### 0.2 venue 결정

paper-search §4.5 (`resolve_venues.py`) 가 PDF 헤더로 확인함. Claude 는 결과를 신뢰. preprint 인 경우 `preprint` 로 기록.

## 0.3 Phase 7 출력물 두 개

- **`abstract.md`**: 메타데이터 + Abstract 원문 + **한글 번역 (필수)** + 관련성 한 줄. 급히 검색/판단용.
- **`summary.md`**: 전체 사실 요약 (수식 / figure / Table / Glossary / Section 상세) + **§ 왜 이 프로젝트와 관련 있는가** (paper-search 고유).

두 파일 간 메타·번역은 반드시 **동일 문구** — 한 쪽 수정하면 다른 쪽도 동기화.

## 1. 내용 원칙

### 1.1 사실만 쓴다 (hallucination 금지) ★★

- **수치 / 인용 / 수식 / 저자명 / 연도는 raw.md 원문 그대로.** 기억·감으로 변형 금지.
- 확신 없으면 `"raw.md 에 명시 없음"` 이라고 쓰고 넘어간다. **짐작·지어내기 금지.**
- 주장·해석할 때 **출처 명시**: `"raw.md p. 5"`, `"Eq. 7"`, `"Fig 3 caption"` 식으로.

### 1.2 해석/연결은 지정 섹션에서만 ⭐ paper-search 추가 조항

summary.md 본문 대부분은 논문 **내부 사실** 만. 해석/주관은 다음 위치에서만 허용:

- **Figure 의 "직관적 해석"** — 논문 주장 범위 내에서 "왜 이 배치인지" 해설.
- **§ 왜 이 프로젝트와 관련 있는가** (마지막 섹션) — 프로젝트 컨텍스트 연결. **2-4 문장, 새 수치 지어내기 금지**.

그 외 모든 섹션은 사실 기반. "이걸 우리 연구에 어떻게 쓸까" 를 중간 섹션에 넣지 말 것.

### 1.3 Claude 조어 금지 ★

- 논문에 없는 **새 용어를 만들어 쓰지 않는다**. 따옴표/볼드로 새 명사처럼 보이게 하는 것도 금지.
- 대신:
  - 논문 용어 (Glossary) 를 그대로 쓴다
  - 확립된 일반 ML 용어 (probing, ablation, embedding 등) 단독 사용
  - 기능적 평서문으로 푼다 ("X 는 Y 를 Z 한다" 식)

## 2. 수식 포맷

### 2.1 Display vs Inline

- **짧은 기호·변수** ($x$, $\alpha_t$, $|M|$) 만 인라인 허용.
- **한 줄 이상**, 분자/분모/적분/합/기댓값 포함이면 **무조건 display math** (`$$...$$`).
- 각 display 수식 아래에 **한국어 한 줄 주석**.

### 2.2 본문 수식은 빠짐없이 포함

논문 본문 (main sections) 의 수식은 **누락 없이** summary.md 에 옮긴다. Appendix-only 수식은 선택.

포맷:

```
#### (수식 제목, h4)

$$\text{수식}$$

> 한 줄 한국어 주석.

> **Notation**
> - 기호: 정의
>
> **Per-term**
> - factor: 역할
```

Proposition / Theorem / Lemma 은 동일 구조이되, 추가:

```
> **무엇을 증명하려는가 (직관)**: 한 줄.
>
> **증거 / 핵심 아이디어**: 한두 줄 (full proof: Appendix X.X).
```

## 3. Figure 규칙

### 3.1 Embed 위치

- 본문에 등장하는 figure 는 **해당 Section 안에 embed**.
- 경로: `![Fig N — 한 줄 제목](figures/figN.png)` (main) / `figures/figAN.png` (appendix).
- Main / Appendix 모두 embed. figure 를 "Figure 인덱스" 표에만 넣고 본문에서 누락 금지.
- `figures/_pages/p-NN.png` 는 자동 추출이 실패했을 때 수동 재크롭용 — summary.md 에서 직접 참조하지 말 것.

### 3.2 Figure 주석 (3줄)

각 figure embed 바로 밑에:

- **저자 주장**: 저자가 이 figure 로 보이려는 본문 § X.X 의 주장 (사실 기반).
- **직관적 해석**: 왜 이 figure 가 여기 있어야 하는지 — 짧게, **논문 주장 범위 내에서만**.
- **본문 언급**: 본문에서 이 figure 를 인용한 모든 위치 + 그때 저자가 한 주장. raw.md 에서 `"Fig N"` / `"Figure N"` 으로 grep. `- § X.X: "원문 인용" — 주장 요약` 포맷.

### 3.3 raw.md 의 Figure index 활용

`raw.md` 첫 부분에 `[M]` / `[A]` 마킹 + `src: image/drawing/mixed/text-bound/page-top` + ⚠ 경고가 있음. Claude 는 이 정보를 보고:
- `src: page-top` 또는 ⚠ 있는 figure 는 품질 낮을 수 있음 → summary.md 에서 "figure 품질 주의" 명시 가능
- 원문 번호와 순차 번호 (fig1, fig2 …) 매핑 정확히 기록

## 4. Glossary 운용

- 이 논문이 **새로 정의하거나 특별한 의미로 사용하는** 용어·기호만. 일반 ML 용어 제외.
- 각 항목: **용어 → 한 줄 정의 → 출처 (§ / Eq. / Fig.)**.
- 본문 곳곳에서 그 용어가 나올 때마다 정의 반복 금지.

## 5. 금지 표현

- "통찰", "영감", "시사점", "가능성 있는", "의미 있는", "흥미로운", "중요한" 등 평가·수사.
- "우리는", "본 연구는" — 논문 화자인지 독자인지 헷갈리게 함. "저자는", "논문은" 으로.
- 볼드·따옴표로 새 용어 꾸미기.

## 6. 체크리스트 (작성 종료 시)

- [ ] 메타데이터 + BibTeX 모두 채움
- [ ] Abstract 원문 + 한글 번역 (**한글번역 누락 금지**)
- [ ] TL;DR 3줄
- [ ] Glossary 에 이 논문 고유 용어 전부
- [ ] 본문 수식 누락 없이 모두 포함 (h4 + display + Notation/Per-term)
- [ ] 모든 figure 가 Section 내부에 embed + 3줄 주석
- [ ] 모든 figure 가 Figure 인덱스 표에 등재
- [ ] `.project_analysis.json` 기반 § 왜 이 프로젝트와 관련 섹션 채움 (2-4 문장)
- [ ] `"raw.md 에 없음"` 대신 지어낸 수치 0건
- [ ] `abstract.md` 의 메타·원문·한글번역이 summary.md 와 일치
