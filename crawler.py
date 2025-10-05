import requests
from bs4 import BeautifulSoup

# 1. 가져올 웹사이트 주소
url = "https://www.yes24.com/Product/Search?domain=BOOK&query=파이썬"

# 2. 웹사이트에 요청 보내기 (User-Agent 꼭 넣기!)
headers = {"User-Agent": "Mozilla/5.0"}
response = requests.get(url, headers=headers)

# 3. 받은 데이터를 파싱하기
soup = BeautifulSoup(response.text, "html.parser")

# 4. 책 제목과 가격 찾기
books = soup.select(".gd_name a")          # 책 제목
prices = soup.select(".price .yes_b")      # 가격

print("책 개수:", len(books))
print("가격 개수:", len(prices))

# 5. 출력하기
for title, price in zip(books, prices):
    print("책 제목:", title.text.strip())
    print("가격:", price.text.strip())
    print("-" * 30)
