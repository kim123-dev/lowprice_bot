"""
lowprice_bot.py

베베앙 물티슈 20개 최저가 검색 봇 (다나와 가격비교 기반)
- danawa-price-search 스킬 방식으로 다나와 공개 검색 인터페이스 활용
- 광고 상품 필터링, 최저가 TOP 3 출력, 목표가 비교
- 목표가(2만원) 이하 특가 발견 시 카카오톡 '나에게 보내기' 알림 전송

사용법: python lowprice_bot.py
"""

import urllib.request
import urllib.parse
import json
import re
import sys
import os
from datetime import datetime

# ─── 설정 ───────────────────────────────────────────────────────────────────

KEYWORD = "베베앙 20개"
TARGET_PRICE = 20000   # 목표가 (원)
SHOW_COUNT = 3         # 출력할 상품 수
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

# ─── .env 파싱 ──────────────────────────────────────────────────────────────

def load_env(env_path=ENV_PATH) -> dict:
    """
    .env 파일에서 카카오 인증 정보를 읽어옴.
    코드에 직접 키 값을 작성하지 않고 .env 파일에서 동적으로 파싱합니다.
    """
    env_vars = {}
    target_files = [env_path]

    # 기본 .env가 없을 경우 (2).env 도 탐색
    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_files.append(os.path.join(base_dir, "(2).env"))
    target_files.append(os.path.join(base_dir, " (2).env"))

    for fpath in target_files:
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k not in env_vars:
                        env_vars[k] = v
            # 필요한 필수 키가 모두 채워졌으면 중단
            if "KAKAO_REST_API_KEY" in env_vars and "KAKAO_REFRESH_TOKEN" in env_vars:
                break

    return env_vars

# ─── 유틸 ────────────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()

def format_price(price: int) -> str:
    return f"{price:,}원"

def print_separator(char="─", length=60):
    print(char * length)

# ─── 다나와 HTML 파싱 ─────────────────────────────────────────────────────────

def fetch_html(keyword: str) -> str:
    query = urllib.parse.urlencode({"query": keyword, "sort": "priceASC"})
    url = f"https://search.danawa.com/dsearch.php?{query}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://www.danawa.com/",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            if res.status != 200:
                print(f"❌ 오류: 다나와 서버 응답 실패 (HTTP {res.status})")
                print("   네트워크 연결 또는 다나와 서버 상태를 확인해주세요.")
                sys.exit(1)
            return res.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"❌ 오류: 네트워크 요청 실패 - {e}")
        print("   인터넷 연결을 확인하고 다시 시도해주세요.")
        sys.exit(1)


def extract_products_from_html(html: str) -> list:
    """다나와 Next.js RSC 플라이트 데이터에서 상품 목록 추출"""
    script_blocks = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html)

    rsc_content = ""
    for block in script_blocks:
        if "productSeq" in block or "productName" in block:
            rsc_content = block
            break

    if not rsc_content:
        print("❌ 파싱 오류: 다나와 응답에서 상품 데이터를 찾을 수 없습니다.")
        print("   사이트 구조가 변경되었거나 차단되었을 수 있습니다.")
        sys.exit(1)

    start_marker = 'self.__next_f.push([1,"'
    start_idx = rsc_content.find(start_marker)
    if start_idx == -1:
        print("❌ 파싱 오류: RSC 데이터 블록을 찾을 수 없습니다.")
        sys.exit(1)

    after = rsc_content[start_idx + len(start_marker):]

    raw_chars = []
    i = 0
    while i < len(after):
        if after[i] == "\\" and i + 1 < len(after):
            raw_chars.append(after[i])
            raw_chars.append(after[i + 1])
            i += 2
        elif after[i] == '"' and after[i+1:i+3] == "])":
            break
        else:
            raw_chars.append(after[i])
            i += 1
    raw = "".join(raw_chars)

    unescaped = (
        raw
        .replace('\\"', '"')
        .replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\\t", "\t")
        .replace("\\\\", "\\")
        .replace("\\u003c", "<")
        .replace("\\u003e", ">")
        .replace("\\u0026", "&")
    )

    p_idx = unescaped.find('"products":[')
    if p_idx == -1:
        print("❌ 파싱 오류: products 배열을 찾지 못했습니다.")
        print("   검색 결과가 없거나 사이트 구조가 변경되었을 수 있습니다.")
        sys.exit(1)

    arr_start = p_idx + len('"products":')
    depth = 0
    end = arr_start
    for j in range(arr_start, len(unescaped)):
        if unescaped[j] == "[":
            depth += 1
        elif unescaped[j] == "]":
            depth -= 1
            if depth == 0:
                end = j + 1
                break

    try:
        products = json.loads(unescaped[arr_start:end])
    except json.JSONDecodeError as e:
        print(f"❌ 파싱 오류: 상품 JSON 파싱 실패 - {e}")
        sys.exit(1)

    if not products:
        print("❌ 오류: 검색 결과가 없습니다. 키워드를 확인해주세요.")
        sys.exit(1)

    return products

# ─── 상품 필터링 & 정렬 ───────────────────────────────────────────────────────

def process_products(raw_products: list) -> list:
    """광고 제거 + 가격 정보 정리 + 실구매가 오름차순 정렬"""
    results = []

    for p in raw_products:
        name = strip_html(p.get("productName", ""))
        if not name:
            continue

        # prodType=1 : 다나와 정식 가격비교 상품 (신뢰도 높음)
        # prodType=3 : 개별 쇼핑몰 광고성 단일 노출 → 광고로 판단해 제거
        prod_type = p.get("prodType")
        if prod_type != 1:
            continue

        min_price = p.get("minPriceNumber") or p.get("minPrice") or 0
        shipping_fee = p.get("postPriceNumber") or p.get("postPrice") or 0
        total_price = min_price + shipping_fee

        if min_price == 0:
            continue

        review_count = (p.get("writeCount") or 0) + (p.get("commentCount") or 0)
        shop_count = p.get("shopCount") or 1
        mall = f"다나와 가격비교 ({shop_count}개 쇼핑몰)" if shop_count > 1 else "단독 판매"
        pcode = p.get("productSeq", "")
        link = p.get("linkUrl") or f"https://prod.danawa.com/info/?pcode={pcode}"
        if link and not link.startswith("http"):
            link = "https://prod.danawa.com" + link

        results.append({
            "name": name,
            "min_price": min_price,
            "shipping_fee": shipping_fee,
            "total_price": total_price,
            "review_count": review_count,
            "mall": mall,
            "link": link,
        })

    if not results:
        print("❌ 필터링 오류: 광고 제거 후 유효한 가격비교 상품이 없습니다.")
        print("   검색 결과가 광고성 단일 쇼핑몰 상품만 있을 수 있습니다.")
        sys.exit(1)

    results.sort(key=lambda x: x["total_price"])
    return results

# ─── 카카오톡 나에게 메시지 보내기 ──────────────────────────────────────────

def get_kakao_access_token(env: dict) -> str:
    """리프레시 토큰을 이용해 유효한 액세스 토큰을 발급받음"""
    rest_api_key = env.get("KAKAO_REST_API_KEY")
    client_secret = env.get("KAKAO_CLIENT_SECRET")
    refresh_token = env.get("KAKAO_REFRESH_TOKEN")

    if not rest_api_key:
        raise ValueError(".env에 KAKAO_REST_API_KEY 항목이 없습니다.")
    if not refresh_token:
        raise ValueError(".env에 KAKAO_REFRESH_TOKEN 항목이 없습니다.")

    token_data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token,
    }
    if client_secret:
        token_data["client_secret"] = client_secret

    encoded_data = urllib.parse.urlencode(token_data).encode("utf-8")
    req = urllib.request.Request(
        "https://kauth.kakao.com/oauth/token",
        data=encoded_data,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            res_json = json.loads(res.read().decode("utf-8"))
            access_token = res_json.get("access_token")
            new_refresh = res_json.get("refresh_token")

            # 리프레시 토큰이 갱신되어 새로 온 경우 .env 업데이트
            if new_refresh and new_refresh != refresh_token:
                update_env_refresh_token(new_refresh)

            return access_token
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"카카오 액세스 토큰 갱신 실패 (HTTP {e.code}): {err_msg}")
    except Exception as e:
        raise RuntimeError(f"카카오 인증 서버 연결 실패: {e}")


def update_env_refresh_token(new_refresh_token: str):
    """갱신된 리프레시 토큰을 .env 파일에 저장"""
    try:
        content = ""
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                content = f.read()

        lines = content.splitlines()
        found = False
        new_lines = []
        for line in lines:
            if line.startswith("KAKAO_REFRESH_TOKEN="):
                new_lines.append(f"KAKAO_REFRESH_TOKEN={new_refresh_token}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"KAKAO_REFRESH_TOKEN={new_refresh_token}")

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
    except Exception as e:
        print(f"⚠️  주의: .env 리프레시 토큰 갱신 저장 실패: {e}")


def send_kakao_alert(product: dict) -> bool:
    """1위 특가 상품 정보를 카카오톡 '나에게 보내기'로 전송"""
    print("\n💬 카카오톡 알림 전송을 시도합니다...")

    env = load_env()
    if not env:
        print("❌ 카카오톡 전송 실패: .env 파일을 찾을 수 없습니다.")
        return False

    # 1. 액세스 토큰 획득
    try:
        access_token = get_kakao_access_token(env)
    except Exception as e:
        print(f"❌ 카카오톡 전송 실패 (토큰 오류): {e}")
        return False

    # 2. 메시지 템플릿 구성 (상품명, 가격, 쇼핑몰 이름, 리뷰 수 + '구매하러 가기' 버튼)
    shipping_str = "무료배송" if product["shipping_fee"] == 0 else f"배송비 {format_price(product['shipping_fee'])}"
    message_text = (
        f"🎉 [특가 발견] 목표 가격 이하입니다!!\n\n"
        f"📦 상품명: {product['name']}\n"
        f"💰 실구매가: {format_price(product['total_price'])} ({shipping_str})\n"
        f"🏪 쇼핑몰: {product['mall']}\n"
        f"⭐ 리뷰 수: {product['review_count']:,}개"
    )

    template = {
        "object_type": "text",
        "text": message_text,
        "link": {
            "web_url": product["link"],
            "mobile_web_url": product["link"],
        },
        "button_title": "구매하러 가기",
    }

    send_data = urllib.parse.urlencode({
        "template_object": json.dumps(template, ensure_ascii=False)
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        data=send_data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        },
    )

    # 3. 메시지 전송 API 호출
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            res_json = json.loads(res.read().decode("utf-8"))
            if res_json.get("result_code") == 0:
                print("✅ [카카오톡 알림 전송 완료] 내 카카오톡으로 특가 메시지를 성공적으로 보냈습니다!")
                return True
            else:
                print(f"❌ [카카오톡 전송 실패] 알림 전송에 실패했습니다. (API 응답: {res_json})")
                return False
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_msg)
            kakao_msg = err_json.get("msg", err_msg)
            kakao_code = err_json.get("code", "")
            print(f"❌ [카카오톡 전송 실패] HTTP {e.code} 에러가 발생했습니다.")
            print(f"   - 카카오 오류 코드: {kakao_code}")
            print(f"   - 상세 내용: {kakao_msg}")
        except Exception:
            print(f"❌ [카카오톡 전송 실패] HTTP {e.code} 에러: {err_msg}")
        return False
    except Exception as e:
        print(f"❌ [카카오톡 전송 실패] 네트워크 또는 알 수 없는 오류로 전송하지 못했습니다: {e}")
        return False

# ─── 화면 출력 ───────────────────────────────────────────────────────────────

def display_results(products: list, keyword: str, target_price: int, show_count: int):
    top = products[:show_count]
    best = top[0]

    print()
    print_separator("═")
    print("🔍  다나와 최저가 검색 결과")
    print(f'    키워드 : "{keyword}"')
    print("    기준   : 광고 제거 · 배송비 포함 실구매가 · 가격 오름차순")
    print_separator("═")

    medals = ["🥇", "🥈", "🥉"]
    for idx, p in enumerate(top):
        medal = medals[idx] if idx < len(medals) else f"{idx+1}."
        print()
        print(f"{medal}  {p['name']}")
        print_separator("─", 55)
        print(f"    💰 최저가     : {format_price(p['min_price'])}")
        if p["shipping_fee"] > 0:
            print(f"    🚚 배송비     : {format_price(p['shipping_fee'])}")
        else:
            print(f"    🚚 배송비     : 무료")
        print(f"    💳 실구매가   : {format_price(p['total_price'])}")
        print(f"    🏪 쇼핑몰     : {p['mall']}")
        print(f"    ⭐ 리뷰 수    : {p['review_count']:,}개")
        print(f"    🔗 링크       : {p['link']}")

    print()
    print_separator("═")

    if best["total_price"] <= target_price:
        print("🎉 [특가 발견] 목표 가격 이하입니다!!")
        print(f"    실구매가 {format_price(best['total_price'])} ≤ 목표가 {format_price(target_price)}")
    else:
        print("📌 [유지] 아직 목표 가격보다 비싸요!!")
        print(f"    실구매가 {format_price(best['total_price'])} > 목표가 {format_price(target_price)}")
        diff = best["total_price"] - target_price
        print(f"    목표가까지 {format_price(diff)} 더 내려야 합니다.")

    print_separator("═")
    now = datetime.now().strftime("%Y년 %m월 %d일 %H:%M:%S")
    print(f"    조회 시각 : {now}")
    print_separator("═")
    print()

# ─── 메인 ────────────────────────────────────────────────────────────────────

def main():
    print(f'\n⏳ 다나와에서 "{KEYWORD}" 검색 중...')

    html = fetch_html(KEYWORD)
    raw_products = extract_products_from_html(html)
    products = process_products(raw_products)
    display_results(products, KEYWORD, TARGET_PRICE, SHOW_COUNT)

    # 1위 가격이 목표가 이하일 때만 카카오톡 알림 전송 (초과 시 전송하지 않음)
    best = products[0]
    if best["total_price"] <= TARGET_PRICE:
        send_kakao_alert(best)
    else:
        print(f"ℹ️  1위 상품 가격이 목표가({format_price(TARGET_PRICE)})를 초과하여 카카오톡 알림은 전송하지 않습니다.")


if __name__ == "__main__":
    main()
