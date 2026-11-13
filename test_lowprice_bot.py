"""
test_lowprice_bot.py

lowprice_bot.py 동작 검증 테스트
- 실제 다나와에 요청하지 않고 가상 데이터만 사용
- 4개 항목 PASS/FAIL 판정 출력
"""

import sys
import io
import json
import unittest
from unittest.mock import patch

# lowprice_bot 모듈 임포트 (main() 자동 실행 방지)
sys.path.insert(0, r"c:\agapp_project\lowprice")
import lowprice_bot

# ─── 가상 데이터 ──────────────────────────────────────────────────────────────

# prodType=1 : 정식 가격비교 상품 (유효)
# prodType=3 : 광고성 단일 쇼핑몰 상품 (필터링 대상)

RAW_CHEAP = [  # 최저가 19,000원 → 목표가 이하
    {"prodType": 1, "productName": "베베앙 오리지널 100매 20팩", "productSeq": "001",
     "minPriceNumber": 19000, "postPriceNumber": 0, "shopCount": 10,
     "writeCount": 50, "commentCount": 5, "linkUrl": ""},
    {"prodType": 3, "productName": "[광고]베베앙 프리미엄 70매 20팩", "productSeq": "AD1",
     "minPriceNumber": 15000, "postPriceNumber": 0, "shopCount": 1,
     "writeCount": 0, "commentCount": 0, "linkUrl": ""},
    {"prodType": 1, "productName": "베베앙 시그니처 100매 20팩", "productSeq": "002",
     "minPriceNumber": 25000, "postPriceNumber": 0, "shopCount": 8,
     "writeCount": 30, "commentCount": 2, "linkUrl": ""},
]

RAW_EXPENSIVE = [  # 최저가 25,000원 → 목표가 초과
    {"prodType": 1, "productName": "베베앙 프리미엄 골드 70매 20팩", "productSeq": "003",
     "minPriceNumber": 25000, "postPriceNumber": 2500, "shopCount": 5,
     "writeCount": 20, "commentCount": 3, "linkUrl": ""},
    {"prodType": 1, "productName": "베베앙 시그니처 100매 20팩", "productSeq": "004",
     "minPriceNumber": 27000, "postPriceNumber": 0, "shopCount": 12,
     "writeCount": 46, "commentCount": 1, "linkUrl": ""},
]

RAW_WITH_ADS = [  # 광고(prodType=3) 2개 + 정상 2개
    {"prodType": 3, "productName": "[쿠팡광고]베베앙 100매 20팩", "productSeq": "AD2",
     "minPriceNumber": 18000, "postPriceNumber": 0, "shopCount": 1,
     "writeCount": 0, "commentCount": 0, "linkUrl": ""},
    {"prodType": 3, "productName": "[광고]베베앙 프리미엄 70매", "productSeq": "AD3",
     "minPriceNumber": 16000, "postPriceNumber": 0, "shopCount": 1,
     "writeCount": 0, "commentCount": 0, "linkUrl": ""},
    {"prodType": 1, "productName": "베베앙 오리지널 100매 20팩", "productSeq": "005",
     "minPriceNumber": 23000, "postPriceNumber": 0, "shopCount": 35,
     "writeCount": 25, "commentCount": 0, "linkUrl": ""},
    {"prodType": 1, "productName": "베베앙 시그니처 100매 20팩", "productSeq": "006",
     "minPriceNumber": 27000, "postPriceNumber": 0, "shopCount": 8,
     "writeCount": 46, "commentCount": 2, "linkUrl": ""},
]

# 빈 HTML (상품 데이터 없음 → 오류 처리 테스트용)
HTML_EMPTY = "<html><body><p>검색 결과 없음</p></body></html>"

# ─── 테스트 케이스 ────────────────────────────────────────────────────────────

class TestLowPriceBot(unittest.TestCase):

    def _capture_display(self, products, target_price):
        """display_results 출력을 문자열로 캡처"""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            lowprice_bot.display_results(products, "테스트키워드", target_price, 3)
        return buf.getvalue()

    # ── 검사 1: 2만원 이하일 때 특가 메시지 출력 ──────────────────────────────
    def test_1_sale_message_when_below_target(self):
        """최저가 ≤ 목표가 → '[특가 발견]' 메시지 출력 여부"""
        products = lowprice_bot.process_products(RAW_CHEAP)
        # 최저가 상품이 19,000원임을 먼저 확인
        self.assertLessEqual(products[0]["total_price"], 20000,
            "테스트 데이터 오류: 첫 번째 상품 가격이 20,000원 이하여야 합니다.")
        output = self._capture_display(products, 20000)
        self.assertIn("[특가 발견]", output,
            "2만원 이하 상품인데 '[특가 발견]' 메시지가 출력되지 않았습니다.")
        self.assertNotIn("[유지]", output,
            "2만원 이하 상품인데 '[유지]' 메시지가 함께 출력되었습니다.")

    # ── 검사 2: 2만원 초과일 때 유지 메시지 출력 ──────────────────────────────
    def test_2_hold_message_when_above_target(self):
        """최저가 > 목표가 → '[유지]' 메시지 출력 여부"""
        products = lowprice_bot.process_products(RAW_EXPENSIVE)
        # 최저가 상품이 20,000원 초과임을 먼저 확인
        self.assertGreater(products[0]["total_price"], 20000,
            "테스트 데이터 오류: 첫 번째 상품 가격이 20,000원 초과여야 합니다.")
        output = self._capture_display(products, 20000)
        self.assertIn("[유지]", output,
            "2만원 초과 상품인데 '[유지]' 메시지가 출력되지 않았습니다.")
        self.assertNotIn("[특가 발견]", output,
            "2만원 초과 상품인데 '[특가 발견]' 메시지가 함께 출력되었습니다.")

    # ── 검사 3: 광고 상품 필터링 ───────────────────────────────────────────────
    def test_3_ad_products_filtered_out(self):
        """prodType=3(광고) 상품이 결과에서 완전히 제거되는가"""
        products = lowprice_bot.process_products(RAW_WITH_ADS)

        # 결과에 광고 상품명이 포함되면 안 됨
        names = [p["name"] for p in products]
        for name in names:
            self.assertNotIn("광고", name,
                f"광고 상품이 필터링되지 않고 결과에 포함되었습니다: '{name}'")

        # 정상 상품(prodType=1)만 남아야 함 → 2개
        self.assertEqual(len(products), 2,
            f"광고 제거 후 정상 상품은 2개여야 하는데 {len(products)}개가 반환되었습니다.")

        # 가격 오름차순 정렬 확인
        prices = [p["total_price"] for p in products]
        self.assertEqual(prices, sorted(prices),
            f"상품이 가격 오름차순으로 정렬되지 않았습니다: {prices}")

    # ── 검사 4: 잘못된 데이터 → 멈추지 않고 오류 메시지 출력 ─────────────────
    def test_4_error_message_on_bad_data(self):
        """상품 데이터가 없는 HTML → sys.exit 호출 + 오류 메시지 출력 (프로세스 종료 없음)"""
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            with self.assertRaises(SystemExit) as ctx:
                lowprice_bot.extract_products_from_html(HTML_EMPTY)

        # sys.exit(1) 이 호출되어야 함 (종료 코드 1)
        self.assertEqual(ctx.exception.code, 1,
            "오류 상황에서 sys.exit(1)이 호출되지 않았습니다.")

        # 오류 메시지(❌)가 출력되어야 함
        output = buf.getvalue()
        self.assertIn("❌", output,
            "오류 발생 시 ❌ 오류 메시지가 출력되지 않았습니다.")


# ─── 결과 출력 러너 ───────────────────────────────────────────────────────────

TESTS = [
    ("검사 1", "test_1_sale_message_when_below_target", "2만원 이하일 때 특가 메시지가 출력되는가"),
    ("검사 2", "test_2_hold_message_when_above_target", "2만원 초과일 때 유지 메시지가 출력되는가"),
    ("검사 3", "test_3_ad_products_filtered_out",       "광고 상품이 섞여 있을 때 걸러낼 수 있는가"),
    ("검사 4", "test_4_error_message_on_bad_data",       "값을 가져오지 못했을 경우 오류를 알려주는가"),
]

def run_tests():
    sep = "─" * 60
    print()
    print("=" * 60)
    print("  lowprice_bot.py 검사 결과")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for _, method, _ in TESTS:
        suite.addTest(TestLowPriceBot(method))

    # 각 테스트를 개별 실행하여 결과 수집
    results = {}
    for label, method, desc in TESTS:
        single = unittest.TestSuite([TestLowPriceBot(method)])
        # stderr / stdout 모두 억제
        buf_err = io.StringIO()
        runner = unittest.TextTestRunner(stream=buf_err, verbosity=0)
        result = runner.run(single)
        passed = result.wasSuccessful()
        results[label] = (passed, desc, result)

    # 결과 출력
    print()
    all_pass = True
    for label, method, desc in TESTS:
        passed, desc_text, result = results[label]
        status = "✅ PASS" if passed else "❌ FAIL"
        if not passed:
            all_pass = False
        print(f"  {status}  [{label}] {desc_text}")
        if not passed:
            for failure in result.failures + result.errors:
                # 실패 원인 한 줄 요약
                reason = failure[1].strip().split("\n")[-1]
                print(f"           └ {reason}")

    print()
    print(sep)
    if all_pass:
        print("  🎉 전체 검사 통과! lowprice_bot.py가 정상 동작합니다.")
    else:
        fail_count = sum(1 for l, m, d in TESTS if not results[l][0])
        print(f"  ⚠️  {fail_count}개 항목 실패. 위 FAIL 항목을 확인하세요.")
    print(sep)
    print()

    return all_pass


if __name__ == "__main__":
    run_tests()
