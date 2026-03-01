# 한국어 번역 프로젝트 가이드라인

## 프로젝트 컨텍스트

이 레포지토리는 Larry Cermak의 "How Crypto Actually Works: The Missing Manual"의 한국어 번역본입니다.

- **Upstream**: https://github.com/lawmaster10/howcryptoworksbook
- **원본 언어**: 영어
- **번역 언어**: 한국어

## 번역 규칙

### 문체

- 격식체(합쇼체) 사용: "~합니다", "~입니다"
- 기존 번역의 톤과 일관성을 유지할 것
- 원문의 뉘앙스를 최대한 살릴 것

### 파일 헤더

모든 챕터 파일은 다음 헤더로 시작합니다. 새 파일 번역 시 반드시 포함할 것:

```markdown
> 이 문서는 [How Crypto Actually Works](https://github.com/lawmaster10/howcryptoworksbook)의 한국어 번역본입니다.
> 원저자: Larry Cermak | 공동 저자: Igor Igamberdiev, Bohdan Pavlov (Wintermute)
```

### 챕터 제목 형식

한국어 제목 뒤에 괄호로 영어 원문을 병기합니다:

```markdown
# 제1장: 비트코인에 대한 포괄적 입문 (A Comprehensive Introduction to Bitcoin)
## 섹션 I: 비트코인 핵심 개념 (Bitcoin Core Concepts)
```

### 기술 용어 처리

- 첫 등장 시: 한국어(영어) 또는 **영어**(한국어) 형태로 병기
  - 예: "작업 증명(Proof of Work)", **genesis block**(블록체인의 첫 번째 블록)
- 이후 등장: 한국어 또는 영어 단독 사용 가능
- 기존 번역에서 영어를 유지한 용어는 그대로 영어 유지
  - 예: mining, hash rate, nonce, block, transaction 등은 영어 그대로 사용하는 패턴이 있음
- 아래 용어 사전을 반드시 참고하되, 기존 번역의 패턴을 우선 따를 것

### 마크다운

- 원본의 마크다운 구조(제목 레벨, 링크, 코드블록, 볼드/이탤릭)를 그대로 유지
- 내부 링크 경로는 변경하지 않음
- 이미지 경로는 변경하지 않음

### 번역하지 않는 것

- 코드 블록 내용
- URL 및 링크
- 파일 경로
- 수학 공식
- 고유명사 (Satoshi Nakamoto, Vitalik Buterin 등)

## 동기화 대상 파일

### 자동 번역 대상

- `Chapters/*.md` — 모든 챕터 파일
- `table_of_contents.md` — 목차

### 자동 번역 제외 (수동 관리)

- `readme.md` — 한국어판 전용 커스텀 README
- `CONTRIBUTING.md` — 한국어판 전용 기여 가이드
- `assets/` — 이미지 등 바이너리 파일

## 용어 사전

| English | 한국어 | 비고 |
|---------|--------|------|
| UTXO | UTXO | 영어 그대로 |
| Bitcoin | 비트코인 / Bitcoin | 문맥에 따라 |
| Ethereum | 이더리움 / Ethereum | 문맥에 따라 |
| Solana | 솔라나 / Solana | 문맥에 따라 |
| blockchain | 블록체인 | |
| smart contract | 스마트 컨트랙트 | |
| DeFi | 탈중앙화 금융(DeFi) | 첫 등장 시 풀네임 |
| MEV | 최대 추출 가능 가치(MEV) | 첫 등장 시 풀네임 |
| NFT | 대체 불가능 토큰(NFT) | 첫 등장 시 풀네임 |
| stablecoin | 스테이블코인 | |
| custody | 커스터디 | |
| governance | 거버넌스 | |
| tokenomics | 토큰 이코노믹스 | |
| DePIN | 탈중앙화 물리 인프라 네트워크(DePIN) | 첫 등장 시 풀네임 |
| RWA | 실물자산(RWA) | 첫 등장 시 풀네임 |
| liquidity pool | 유동성 풀 | |
| consensus mechanism | 합의 메커니즘 / 합의(consensus) | |
| proof of work (PoW) | 작업 증명(PoW) | |
| proof of stake (PoS) | 지분 증명(PoS) | |
| validator | 검증자 | |
| block reward | 블록 보상 | |
| gas fee | 가스 수수료 | |
| oracle | 오라클 | |
| bridge | 브릿지 | |
| rollup | 롤업 | |
| layer 1 (L1) | 레이어 1(L1) | |
| layer 2 (L2) | 레이어 2(L2) | |
| mempool | 멤풀 | |
| slippage | 슬리피지 | |
| impermanent loss | 비영구적 손실 | |
| yield farming | 이자 농사 | |
| airdrop | 에어드롭 | |
| wallet | 지갑 | |
| private key | 개인 키 | |
| public key | 공개 키 | |
| hash / hash function | 해시 / 해시 함수 | |
| nonce | 논스 / nonce | 기존 번역에서 영어 유지 |
| Merkle tree | 머클 트리 | |
| quantum resistance | 양자 내성 | |
| prediction market | 예측 시장 | |
| Hyperliquid | 하이퍼리퀴드 | |
| mining | 채굴 / mining | 기존 번역에서 영어 유지하는 경우 있음 |
| block | 블록 / block | 문맥에 따라 |
| transaction | 트랜잭션 / transaction | 기존 번역에서 영어 유지하는 경우 있음 |
| hash rate | hash rate | 기존 번역에서 영어 그대로 사용 |
| coinbase transaction | coinbase transaction | 영어 그대로 |
| genesis block | genesis block | 영어 그대로 |
| peer-to-peer | peer-to-peer | 영어 그대로 |
| cypherpunk | 사이퍼펑크(cypherpunk) | |
