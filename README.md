# Lowprice Bot (최저가 검색 및 카카오톡 알림 봇)

다나와 실구매가 최저가 검색 및 카카오톡 '나에게 보내기' 알림 봇입니다.

## 기능
- **다나와 검색**: 광고 상품 필터링, 배송비 포함 실구매가 오름차순 정렬, TOP 3 출력
- **카카오톡 알림**: 1위 상품 실구매가가 목표가(20,000원) 이하일 때 카카오톡 메시지 전송
- **구매 링크**: 카카오톡 메시지에 '구매하러 가기' 버튼을 포함하여 원클릭 이동 지원

## 설치 및 실행

### 1. 환경변수 설정
`.env` 파일을 생성하고 카카오 API 인증 정보를 입력합니다:
```env
KAKAO_REST_API_KEY=your_kakao_rest_api_key
KAKAO_CLIENT_SECRET=your_kakao_client_secret
KAKAO_REFRESH_TOKEN=your_kakao_refresh_token
```

### 2. 실행
```bash
python lowprice_bot.py
```
