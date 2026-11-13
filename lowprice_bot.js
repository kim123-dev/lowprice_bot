/**
 * lowprice_bot.js
 * 
 * 베베앙 물티슈 20개 최저가 검색 봇 (다나와 가격비교 기반)
 * - danawa-price-search 스킬 방식으로 다나와 공개 검색 인터페이스 활용
 * - 광고 상품 필터링, 최저가 TOP 3 출력, 목표가 비교
 * 
 * 사용법: node lowprice_bot.js
 */

const KEYWORD = '베베앙 20개';
const TARGET_PRICE = 20000; // 목표가 (원)
const SHOW_COUNT = 3;       // 출력할 상품 수

// ─── 유틸 ───────────────────────────────────────────────────────────────────

function stripHtml(str) {
  return (str || '').replace(/<[^>]+>/g, '').trim();
}

function formatPrice(n) {
  return Number(n).toLocaleString('ko-KR') + '원';
}

function printSeparator(char = '─', len = 60) {
  console.log(char.repeat(len));
}

// ─── 다나와 HTML 파싱 ────────────────────────────────────────────────────────

function extractProductsFromHtml(html) {
  // 다나와는 Next.js App Router + RSC 방식으로 상품 데이터를
  // self.__next_f.push([1, "..."]) 형태의 스크립트 안에 JSON으로 포함
  const scriptRegex = /<script[^>]*>([\s\S]*?)<\/script>/g;
  let m;
  let rscContent = '';

  while ((m = scriptRegex.exec(html)) !== null) {
    if (m[1].includes('productSeq') || m[1].includes('productName')) {
      rscContent = m[1];
      break;
    }
  }

  if (!rscContent) {
    return { error: '다나와 응답에서 상품 데이터를 찾을 수 없습니다. 사이트 구조가 변경되었을 수 있습니다.' };
  }

  // self.__next_f.push([1,"..."]) 의 내부 문자열 추출
  const startMarker = 'self.__next_f.push([1,"';
  const startIdx = rscContent.indexOf(startMarker);
  if (startIdx === -1) {
    return { error: 'RSC 데이터 블록을 찾을 수 없습니다.' };
  }

  const after = rscContent.slice(startIdx + startMarker.length);
  let raw = '';
  let i = 0;
  while (i < after.length) {
    if (after[i] === '\\') {
      raw += after[i] + after[i + 1];
      i += 2;
    } else if (after[i] === '"' && after[i + 1] === ']' && after[i + 2] === ')') {
      break;
    } else {
      raw += after[i];
      i++;
    }
  }

  // JS 문자열 이스케이프 해제
  const unescaped = raw
    .replace(/\\"/g, '"')
    .replace(/\\n/g, '\n')
    .replace(/\\r/g, '\r')
    .replace(/\\t/g, '\t')
    .replace(/\\\\/g, '\\')
    .replace(/\\u003c/gi, '<')
    .replace(/\\u003e/gi, '>')
    .replace(/\\u0026/gi, '&');

  // products 배열 위치 찾기
  const productsKey = '"products":[';
  const pIdx = unescaped.indexOf(productsKey);
  if (pIdx === -1) {
    return { error: 'products 배열을 파싱하지 못했습니다. 검색 결과가 없거나 사이트 구조가 변경되었을 수 있습니다.' };
  }

  const arrStart = pIdx + '"products":'.length;
  let depth = 0;
  let end = arrStart;
  for (let j = arrStart; j < unescaped.length; j++) {
    if (unescaped[j] === '[') depth++;
    else if (unescaped[j] === ']') {
      depth--;
      if (depth === 0) { end = j + 1; break; }
    }
  }

  let products;
  try {
    products = JSON.parse(unescaped.slice(arrStart, end));
  } catch (e) {
    return { error: `상품 JSON 파싱 실패: ${e.message}` };
  }

  if (!Array.isArray(products) || products.length === 0) {
    return { error: '검색 결과가 없습니다. 키워드를 확인해주세요.' };
  }

  return { products };
}

// ─── 상품 필터링 & 정렬 ──────────────────────────────────────────────────────

function processProducts(rawProducts) {
  const results = [];

  for (const p of rawProducts) {
    const name = stripHtml(p.productName || '');
    if (!name) continue;

    // prodType=1 : 다나와 정식 가격비교 상품 (신뢰도 높음)
    // prodType=3 : 개별 쇼핑몰 상품 (광고성 포함 가능)
    // prodType이 없거나 다른 경우 → 건너뜀
    const prodType = p.prodType;
    if (prodType !== 1 && prodType !== 3) continue;

    // 광고 필터링: prodType=3 중 linkUrl이 외부 쇼핑몰 직링크가 아닌 경우 등
    // 다나와에서 광고 상품은 별도 adType 대신 prodType=3 + 개별 쇼핑몰 pcode(EE*, TH*, ED* prefix)로 구분
    // prodType=3 은 단일 쇼핑몰 광고성 노출이므로 제거 (가격비교 대상 아님)
    if (prodType === 3) continue;

    // 가격 정보
    const minPrice = p.minPriceNumber || p.minPrice || 0;
    const shippingFee = p.postPriceNumber || p.postPrice || 0;
    const totalPrice = minPrice + shippingFee;

    if (minPrice === 0) continue; // 가격 정보 없는 상품 제외

    // 리뷰 / 의견 수
    const reviewCount = (p.writeCount || 0) + (p.commentCount || 0);

    // 상품 URL
    const link = p.linkUrl
      ? (p.linkUrl.startsWith('http') ? p.linkUrl : 'https://prod.danawa.com' + p.linkUrl)
      : `https://prod.danawa.com/info/?pcode=${p.productSeq}`;

    // 최저가 쇼핑몰 정보 (다나와 가격비교 기반)
    const shopCount = p.shopCount || 1;
    const mall = shopCount > 1 ? `다나와 가격비교 (${shopCount}개 쇼핑몰)` : '단독 판매';

    results.push({
      name,
      minPrice,
      shippingFee,
      totalPrice,
      reviewCount,
      mall,
      link,
      pcode: p.productSeq,
    });
  }

  if (results.length === 0) {
    return { error: '광고 상품 필터링 후 유효한 가격비교 상품이 없습니다. 검색 결과가 광고성 단일 쇼핑몰 상품만 있을 수 있습니다.' };
  }

  // 실구매가(배송비 포함) 오름차순 정렬
  results.sort((a, b) => a.totalPrice - b.totalPrice);

  return { products: results };
}

// ─── 출력 ────────────────────────────────────────────────────────────────────

function displayResults(products, keyword, targetPrice, showCount) {
  const top = products.slice(0, showCount);
  const best = top[0];

  console.log('');
  printSeparator('═');
  console.log(`🔍  다나와 최저가 검색 결과`);
  console.log(`    키워드 : "${keyword}"`);
  console.log(`    기준   : 광고 제거 · 배송비 포함 실구매가 · 가격 오름차순`);
  printSeparator('═');

  top.forEach((p, idx) => {
    const rank = ['🥇', '🥈', '🥉'][idx] || `${idx + 1}.`;
    console.log('');
    console.log(`${rank}  ${p.name}`);
    printSeparator('─', 55);
    console.log(`    💰 최저가     : ${formatPrice(p.minPrice)}`);
    if (p.shippingFee > 0) {
      console.log(`    🚚 배송비     : ${formatPrice(p.shippingFee)}`);
      console.log(`    💳 실구매가   : ${formatPrice(p.totalPrice)}`);
    } else {
      console.log(`    🚚 배송비     : 무료`);
      console.log(`    💳 실구매가   : ${formatPrice(p.totalPrice)}`);
    }
    console.log(`    🏪 쇼핑몰     : ${p.mall}`);
    console.log(`    ⭐ 리뷰 수    : ${p.reviewCount.toLocaleString()}개`);
    console.log(`    🔗 링크       : ${p.link}`);
  });

  console.log('');
  printSeparator('═');

  // 목표가 판정
  if (best.totalPrice <= targetPrice) {
    console.log(`🎉 [특가 발견] 목표 가격 이하입니다!!`);
    console.log(`    실구매가 ${formatPrice(best.totalPrice)} ≤ 목표가 ${formatPrice(targetPrice)}`);
  } else {
    console.log(`📌 [유지] 아직 목표 가격보다 비싸요!!`);
    console.log(`    실구매가 ${formatPrice(best.totalPrice)} > 목표가 ${formatPrice(targetPrice)}`);
    console.log(`    목표가까지 ${formatPrice(best.totalPrice - targetPrice)} 더 내려야 합니다.`);
  }

  printSeparator('═');
  console.log(`    조회 시각 : ${new Date().toLocaleString('ko-KR')}`);
  printSeparator('═');
  console.log('');
}

// ─── 메인 ────────────────────────────────────────────────────────────────────

async function main() {
  console.log(`\n⏳ 다나와에서 "${KEYWORD}" 검색 중...`);

  // 1) 다나와 검색 HTML 가져오기
  const url = 'https://search.danawa.com/dsearch.php?query=' +
    encodeURIComponent(KEYWORD) + '&sort=priceASC';

  let html;
  try {
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' +
          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Referer': 'https://www.danawa.com/',
      },
    });

    if (!res.ok) {
      console.error(`❌ 오류: 다나와 서버 응답 실패 (HTTP ${res.status})`);
      console.error('   네트워크 연결 또는 다나와 서버 상태를 확인해주세요.');
      process.exit(1);
    }

    html = await res.text();
  } catch (err) {
    console.error(`❌ 오류: 네트워크 요청 실패 - ${err.message}`);
    console.error('   인터넷 연결을 확인하고 다시 시도해주세요.');
    process.exit(1);
  }

  // 2) HTML에서 상품 데이터 추출
  const extractResult = extractProductsFromHtml(html);
  if (extractResult.error) {
    console.error(`❌ 파싱 오류: ${extractResult.error}`);
    process.exit(1);
  }

  // 3) 광고 필터링 + 정렬
  const processResult = processProducts(extractResult.products);
  if (processResult.error) {
    console.error(`❌ 필터링 오류: ${processResult.error}`);
    process.exit(1);
  }

  // 4) 결과 출력
  displayResults(processResult.products, KEYWORD, TARGET_PRICE, SHOW_COUNT);
}

main();
