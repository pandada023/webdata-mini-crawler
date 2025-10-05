# crawler_selenium.py
import sys, os, re, csv, time
from urllib.parse import quote_plus
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup, FeatureNotFound

BASE = "https://www.yes24.com/product/search?query={kw}&domain=BOOK&page={page}&size=24&viewMode=thumb"

def make_soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except FeatureNotFound:
        return BeautifulSoup(html, "html.parser")

def build_url(kw: str, page: int) -> str:
    return BASE.format(kw=quote_plus(kw), page=page)

def ensure_dirs():
    os.makedirs("data", exist_ok=True)
    os.makedirs("screenshots", exist_ok=True)

def make_driver():
    opts = Options()
    # 필요하면 주석 해제해서 창 안 띄우고 실행
    # opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    driver = webdriver.Chrome(options=opts)
    driver.set_window_size(1280, 960)
    return driver

def wait_for_list(driver, wait: WebDriverWait) -> str:
    """
    결과 리스트가 로드될 때까지 기다림.
    성공 시 어떤 CSS가 감지됐는지 문자열로 반환.
    """
    # 보기 모드에 따라 대표 셀렉터가 다를 수 있어 여러 개를 시도
    candidates = [
        "#yesSchList li a.gd_name",         # 썸네일 모드에서 자주 나오는 패턴
        "#yesSchList li .goods_name a",     # 리스트 모드 패턴
        "div.goods_info .goods_name a",     # 예전/다른 페이지 패턴
    ]
    last_err = None
    for css in candidates:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
            return css
        except TimeoutException as e:
            last_err = e
    # 전부 실패하면 마지막 에러를 그대로 던짐
    raise last_err

def parse_items(html: str):
    """
    다양한 마크업을 모두 커버하도록 안전하게 파싱
    """
    soup = make_soup(html)
    items = []

    # 1차: 가장 흔한 컨테이너
    cards = soup.select("#yesSchList li")
    # 2차: 다른 레이아웃
    if not cards:
        cards = soup.select("div.goods_list ul li")
    # 그래도 없으면 마지막 시도
    if not cards:
        cards = soup.select("div.goods_info")

    for li in cards:
        # 제목 후보
        title_el = (
            li.select_one("a.gd_name")
            or li.select_one(".goods_name a")
            or li.select_one("a")             # 최후의 보루
        )
        title = (title_el.get_text(strip=True) if title_el else "").strip()

        # 가격 후보(,와 원 제거해서 숫자만)
        price_el = (
            li.select_one("em.yes_b")
            or li.select_one(".goods_price em")
            or li.select_one(".price strong")
            or li.select_one(".price em")
        )
        price_txt = (price_el.get_text(strip=True) if price_el else "")
        m = re.search(r"\d[\d,]*", price_txt)
        price = int(m.group(0).replace(",", "")) if m else None

        if title:
            items.append((title, price))

    return items

def run(kw: str, pages: int):
    ensure_dirs()
    driver = make_driver()
    wait = WebDriverWait(driver, 12)

    rows, seen = [], set()
    try:
        for p in range(1, pages + 1):
            url = build_url(kw, p)
            driver.get(url)

            # 살짝 스크롤해서 지연로딩/광고 레이어 안정화
            try:
                driver.execute_script("window.scrollTo(0, 600);")
            except Exception:
                pass

            # 리스트 로드 대기 (여러 셀렉터 후보 중 하나)
            try:
                used_css = wait_for_list(driver, wait)
            except TimeoutException:
                print("[WARN] 리스트 컨테이너를 못 찾음 → 휴리스틱 파싱 시도")
                used_css = "(heuristic)"

            # 페이지 HTML → 파싱
            html = driver.page_source
            items = parse_items(html)

            # 디버그 로그
            print(f"[INFO] p{p} 탐지 CSS: {used_css} / 파싱결과 {len(items)}건")

            # CSV 누적 (제목+가격으로 중복 제거)
            for title, price in items:
                key = (title, price)
                if key in seen:
                    continue
                seen.add(key)
                rows.append([kw, title, price, p])

            # 각 페이지 스냅샷
            with open(f"screenshots/p{p}.html", "w", encoding="utf-8") as f:
                f.write(html)
            driver.save_screenshot(f"screenshots/p{p}.png")

            time.sleep(0.6)  # 서버 배려

        # 저장
        safe_kw = re.sub(r"[^\w가-힣]", "_", kw)
        out_path = f"data/yes24_{safe_kw}_p{pages}.csv"
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["검색어/URL", "제목", "가격", "페이지"])
            w.writerows(rows)

        # 마지막 페이지 HTML도 남김
        with open("screenshots/last_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        print("\n[RESULT]")
        print(f"URL  : {build_url(kw, pages)}")
        print(f"총 {len(rows)}건  → {out_path}")
        print("증빙(HTML): screenshots/last_page.html")
    finally:
        driver.quit()

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "자바"
    pages = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    run(kw, pages)
