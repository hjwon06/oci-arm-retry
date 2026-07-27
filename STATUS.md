# 오라클 ARM 확보 — 상태 확인 가이드

> 새 세션에서 "오라클 됐나?" 확인할 때 이 문서부터 읽는다.
> 마지막 갱신: 2026-07-26 (미확보 상태)

## 가장 빠른 확인법 (순서대로)

**1. Issues 탭** — 성공하면 자동으로 Issue가 생긴다. 비어 있으면 아직 안 된 것.
https://github.com/hjwon06/oci-arm-retry/issues

**2. Actions 탭** — 워크플로가 **비활성화**돼 있으면 성공한 것 (성공 시 스스로 끈다).
https://github.com/hjwon06/oci-arm-retry/actions

**3. 로컬에서 직접 조회** (가장 확실)
```
python C:\Users\Jwon\.oci\check_status.py
```
`Total instances: 0` → 아직 미확보
인스턴스가 뜨면 `PUBLIC IP`까지 같이 출력된다.

## 지금 돌아가는 것

GitHub Actions가 24시간 자동 재시도 중. 제이 PC 꺼도 무관.

| 항목 | 값 |
|---|---|
| 스케줄 | 하루 4회 (0·6·12·18 UTC), 각 350분 루프 |
| 간격 | 60초 |
| 일일 시도 | 약 1,400회 |
| Fault Domain | FAULT-DOMAIN-1 → 2 → 3 순회 |
| 중복 실행 | `concurrency` 그룹으로 차단 |
| 비용 | 0원 (public repo = Actions 무제한) |

## 목표 스펙

- 이름 `crawl-server` / `VM.Standard.A1.Flex`
- 1 OCPU · 6GB RAM · 100GB Boot
- 리전 `ap-tokyo-1` / AD `CTnO:AP-TOKYO-1-AD-1`
- 이미지 Ubuntu 24.04 ARM

접속:
```
ssh ubuntu@<PUBLIC_IP> -i ~/.oci/crawl_server_key
```

## 성공하면 할 일

1. 서버 초기 세팅 — Python, Docker, cron
2. AI 컴퍼니 데몬 올리기 (슬랙 자율 발화·트리거 감지)
3. 크몽 크롤링 작업 서버로 연결

## 안 되고 있는 이유 (2026-07-26 기준)

도쿄 리전 ARM 용량 고갈. 30회 이상 전부 `Out of host capacity`.
Free Tier 계정은 용량 배정 우선순위가 구조적으로 최하위다.

**아직 안 쓴 카드:** Oracle PAYG 전환.
공식 문서상 무료 혜택은 그대로 유지되면서 인스턴스 실행 우선순위를 받는다.
제이가 "Free Tier 유지가 목적"이라 보류한 상태 — 오래 막히면 재검토 대상.

되돌릴 수 없다는 점(다운그레이드 불가)과, PAYG로도 용량 없으면 여전히 실패한다는 점은 감안해야 한다.

## 참고

- 재시도 로직: `retry.py`
- 워크플로: `.github/workflows/retry.yml`
- 시크릿: `OCI_PRIVATE_KEY` (등록 완료)
- 작업 회고: 볼트 `04-log/2026-07-26-oracle-arm-retry-github-actions.md`
