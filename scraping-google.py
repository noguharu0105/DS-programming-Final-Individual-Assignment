import requests
from bs4 import BeautifulSoup
import sqlite3
import time

DB_FILE = "google_repos_advanced.db"
BASE_URL = "https://github.com/orgs/google/repositories"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def convert_stars(stars_text):

    stars_text = stars_text.strip().lower()
    stars_text = stars_text.replace(",", "")

    try:
        if stars_text.endswith("k"):
            return int(float(stars_text[:-1]) * 1000)
        elif stars_text.endswith("m"):
            return int(float(stars_text[:-1]) * 1000000)
        else:
            return int(stars_text)
        
    except ValueError:
        return 0

def setup_database():

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                language TEXT,
                stars INTEGER
            )
        """)
        conn.commit()

def scrape_page(page_number):

    params = {
        "page": page_number,
        "type": "all"
    }

    print(f"\nScraping page {page_number} ...")

    try:
        response = requests.get(
            BASE_URL,
            headers=HEADERS,
            params=params,
            timeout=20
        )

        if response.status_code == 429:
            wait_time = int(
                response.headers.get("Retry-After", 300)
            )
            print(
                f"アクセス制限が発生しました。"
                f"{wait_time}秒待機します。"
            )
            time.sleep(wait_time)
            return None

        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        print(f"通信エラー: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    scraped_data = []

    links = soup.select('a[href^="/google/"]')

    for a in links:

        href = a.get("href", "")
        parts = href.strip("/").split("/")

        if len(parts) != 2 or parts[0] != "google":
            continue

        repo_name = parts[1]

        repo_block = None

        for parent in a.parents:

            star_tag = parent.select_one(
                'a[href$="/stargazers"]'
            )

            if star_tag:
                repo_block = parent
                break

        if repo_block is None:
            continue

        lang_tag = repo_block.find(
            "span",
            class_=lambda c: c and "PrimaryLanguageName" in c
        )

        language = (
            lang_tag.get_text(strip=True)
            if lang_tag else "None"
        )

        star_tag = repo_block.select_one(
            'a[href$="/stargazers"]'
        )

        stars_text = (
            star_tag.get_text(strip=True)
            if star_tag else "0"
        )

        stars = convert_stars(stars_text)

        scraped_data.append(
            (repo_name, language, stars)
        )

    scraped_data = list(dict.fromkeys(scraped_data))
    print(f"取得件数: {len(scraped_data)} 件")
    return scraped_data

def save_to_database(data):

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT OR REPLACE INTO repositories
            (name, language, stars)
            VALUES (?, ?, ?)
        """, data)

        conn.commit()

def show_database():

    with sqlite3.connect(DB_FILE) as conn:

        cursor = conn.cursor()
        print("\n===== Google GitHub Repositories =====")

        cursor.execute("""
            SELECT name, language, stars
            FROM repositories
            ORDER BY stars DESC
        """)

        rows = cursor.fetchall()

        for row in rows:
            repo_name, language, stars = row
            print(
                f"Name: {repo_name:<35} | "
                f"Language: {language:<15} | "
                f"Stars: {stars}"
            )

        print("\n======================================")

        print(f"保存件数: {len(rows)} 件")

def main():

    setup_database()
    page_number = 1
    total_count = 0

    while True:

        data = scrape_page(page_number)

        if data is None:
            print("取得を中断しました。")
            break

        if not data:
            print("\n最終ページに到達しました。")
            break

        save_to_database(data)
        total_count += len(data)
        print(f"現在までの取得件数: {total_count} 件")
        page_number += 1
        time.sleep(2)

    show_database()


if __name__ == "__main__":
    main()