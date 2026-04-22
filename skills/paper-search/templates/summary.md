# 논문 Summary 템플릿

> 이 파일은 `summary.md` 로 복사해 채워 넣는 placeholder.
>
> **목적**: PDF 를 다시 열지 않고도 논문의 **사실 기반** 정보를 전부 복기. 앞으로의 Q&A / 논의는 이 파일을 1 차 소스로 본다.
>
> **무엇을 쓰고 무엇을 쓰지 않는가**:
> - ✅ 사실 그대로 서술 — 수식, 수치, Table, Figure, 저자가 실제로 한 주장.
> - ❌ 개인 해석, 호불호 평가 → **여기에 쓰지 않는다**.
> - ✅ 예외: **§ 왜 이 프로젝트와 관련 있는가** — paper-search 고유 섹션. 프로젝트 컨텍스트 (`.project_analysis.json`) 와 논문을 잇는 2-4 문장.
>
> 이 템플릿은 wj926/paper-summary (MIT) 의 `summary.md` 를 차용하고, 마지막 § "왜 이 프로젝트와 관련" 을 추가.

---

## 메타데이터

- **제목**:
- **저자**:
- **소속**:
- **학회/저널**:
- **연도**:
- **arXiv/DOI**:
- **BibTeX key**: `author연도short`
- **Confidence**: high | medium | low  <!-- venue 분류 / 관련성 신뢰도 -->
- **PDF**: `<paper_title>.pdf` (같은 폴더)

```bibtex
@inproceedings{...}
```

## Abstract

- **원문 (영어)**:
  > (논문 abstract 통째로)
- **한글 번역** (필수):
  > (의역 OK, 단 수치·모델명·약어·기호 보존)

## TL;DR (3줄)

1.
2.
3.

### TL;DR 에 등장한 고유 용어

> TL;DR 에서 쓰인 용어 중 이 논문이 특수하게 정의·사용하는 것만. 일반 ML 용어 제외.

- **(용어명)**: 한 줄 정의. (자세: § X.X)

## 핵심 기여 (Contributions)

-

## 논문 고유 용어 / Glossary

> 이 논문이 **새로 정의하거나 특별한 의미로 사용하는** 용어·개념·기호. 일반 ML 용어 제외.

- **(용어명)**: 한 줄 정의. (출처: § X.X / Eq. N / Fig. M)
- **(기호 예시: $g_{t,i}$)**: 정의. (출처: Eq. 4)

## Section별 상세

> 각 Section 서술 중 **본문에 등장하는 figure 는 여기서 embed**.

### 1. Introduction / Motivation

- 풀려는 문제:
- 기존 접근의 한계:
- 이 논문의 관점/질문:

![Fig 1 — 제목](figures/fig1.png)

- **저자 주장**:
- **직관적 해석**: (figure 를 읽는 순서·왜 이 배치인지 — 논문 주장 기반으로만)
- **본문 언급**:
  - § X.X: "원문 인용" — 주장 요약.

### 2. Preliminaries / Setup

- 표기법:
- 주요 정의:

$$\text{긴 수식은 여기에 display math 로}$$

> 한 줄 한국어 주석.

### 3. 이론 (있다면)

- Proposition / Theorem / Lemma 각각 한 블록:
  - 형식 statement (수식)
  - **무엇을 증명하려는가 (직관)**: 한 줄
  - **증거 / 핵심 아이디어**: 한두 줄 (full proof: appendix 참조)

### 4. 방법론

- **알고리즘**:
  ```
  (pseudocode)
  ```
- **핵심 수식**:

$$\mathcal{L} = ...$$

> 주석.

### 5. 실험 세팅

- **데이터셋**:
- **모델/아키텍처**:
- **베이스라인**:
- **평가지표**:
- **하이퍼파라미터/학습 세팅**:

### 6. 주요 결과

> 표/그림 **수치 그대로** 기록. "무엇이 보이는가" 까지만.

#### Table N

| col1 | col2 |
|------|------|
|      |      |

![Fig N — 제목](figures/figN.png)

- **저자 주장**:
- **직관적 해석**:
- **본문 언급**:
  - § X.X: "원문 인용" — 주장 요약.

### 7. Ablation / 분석

-

### 8. 저자 스스로 밝힌 한계

-

### Appendix 주요 내용

- **A / B / C ...**: 섹션별 한 줄 요약.

![Fig A1 — 제목](figures/figA1.png)

- **저자 주장**:
- **직관적 해석**:
- **본문 언급**:
  - § X.X: "원문 인용" — 주장 요약.

## Figure 인덱스

### Main

| 파일 | 한 줄 설명 | 원문 번호 |
|------|-----------|---------|
| `figures/fig1.png` |  | Fig 1 (p. N) |

### Appendix

| 파일 | 한 줄 설명 | 원문 번호 |
|------|-----------|---------|
| `figures/figA1.png` |  | Fig X (p. N) |

## 인용된 주요 선행 연구

> 이 논문이 본문에서 자주 참조하는 문헌.

- **(저자, 연도)**: 이 논문 안에서의 역할.

---

## 왜 이 프로젝트와 관련 있는가  ⭐ paper-search 고유

> 이 섹션만 "해석" 이 허용된다. 프로젝트의 `.project_analysis.json` 신호 (domain/problem/method_keywords/benchmarks/baselines) 를 기준으로 2-4 문장.
> 위의 Section별 상세처럼 수치·인용을 지어내지 말 것. 불명확하면 "abstract/raw.md 에 명시 없음" 표기.
