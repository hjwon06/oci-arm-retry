# OCI ARM Instance Auto-Retry

GitHub Actions로 5분마다 Oracle Cloud ARM 인스턴스 생성을 시도합니다.

## Setup

1. Repository Secret에 `OCI_PRIVATE_KEY` 추가 (OCI API 프라이빗 키 PEM 내용 전체)
2. Actions 탭에서 workflow enable
3. 인스턴스 생성 성공 시 자동으로 Issue 생성 + workflow 비활성화
