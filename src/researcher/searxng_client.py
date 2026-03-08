import requests
from typing import Any, Dict, Iterable, List


class SearXNGClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def test_connection(self) -> bool:
        """SearXNG が利用可能か確認（HTML パース対応）"""
        try:
            response = requests.get(
                f"{self.base_url}/search",
                params={"q": "test"},  # HTML形式で取得
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=5,
            )
            if response.status_code == 200:
                # HTML に <article> タグが含まれていれば、結果があると判定
                if '<article' in response.text or '<div' in response.text:
                    return True
            elif response.status_code == 403:
                # 403でも、HTML パース方式で動作するため成功とみなす
                return True
        except requests.exceptions.RequestException:
            pass
        
        return False

    def search(self, query: str, **kwargs: Any) -> Dict[str, Any]:
        """検索実行（SearXNG JSON、失敗時はHTML パース）"""
        
        # SearXNG JSON API で試す
        params: Dict[str, Any] = {"q": query, "format": "json"}
        allowed = ["categories", "engines", "language", "pageno", "time_range", "safesearch"]
        invalid = [key for key in kwargs if key not in allowed]
        if invalid:
            raise ValueError(
                f"未サポートの検索パラメータが含まれています: {invalid}. 対応しているキーは {allowed} です。"
            )
        _safesearch_map = {"off": 0, "moderate": 1, "strict": 2}
        for key in allowed:
            if key in kwargs and kwargs[key] is not None:
                value = kwargs[key]
                if key == "safesearch" and isinstance(value, str):
                    value = _safesearch_map.get(value.lower(), 0)
                params[key] = value
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/search",
                params=params,
                headers=headers,
                timeout=10,
            )
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(f"SearXNGサーバーへの接続に失敗しました: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(f"SearXNGとの通信がタイムアウトしました: {exc}") from exc

        try:
            # JSON API が 403 返した場合、HTML パース方式にフォールバック
            if response.status_code == 403:
                return self._search_html(query)
            
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            status = response.status_code
            reason = getattr(response, "reason", "")
            text = (response.text[:200] + "...") if len(response.text) > 200 else response.text
            raise RuntimeError(
                f"SearXNG検索エラー: HTTP {status} {reason} - {text}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"SearXNG応答の解析に失敗しました: {exc}") from exc
        parsed = self._parse_results(payload)
        return {"raw": payload, "results": parsed}

    def _search_html(self, query: str) -> Dict[str, Any]:
        """SearXNG HTML ページから結果をスクレイピング"""
        try:
            # HTML形式で検索
            response = requests.get(
                f"{self.base_url}/search",
                params={"q": query},  # format指定なし = HTML
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=10,
            )
            response.raise_for_status()
            
            results = self._parse_searxng_html(response.text)
            
            if not results:
                raise RuntimeError(f"SearXNG HTML パースで '{query}' の結果が見つかりません")
            
            return {
                "raw": {"source": "searxng-html", "query": query},
                "results": results
            }
        except Exception as exc:
            raise RuntimeError(f"SearXNG HTML スクレイピングエラー: {exc}") from exc

    def _parse_searxng_html(self, html: str) -> List[Dict[str, Any]]:
        """SearXNG HTML ページから検索結果をパース"""
        import re
        from html import unescape
        
        results = []
        
        # SearXNG の検索結果は複数の構造があるため、複数パターンで試す
        
        # パターン1: <article> タグ
        article_pattern = r'<article[^>]*>(.*?)</article>'
        for article_match in re.finditer(article_pattern, html, re.DOTALL):
            article_html = article_match.group(1)
            
            # URL を抽出
            url_match = re.search(r'href="([^"]+)"', article_html)
            if not url_match:
                continue
            url = unescape(url_match.group(1))
            
            # タイトルを抽出
            # リンクテキストまたは h3/h2 タグから
            title_candidates = [
                re.search(r'href="[^"]+">([^<]+)</a>', article_html),
                re.search(r'<h[23]>([^<]+)</h[23]>', article_html),
            ]
            title = ""
            for match in title_candidates:
                if match:
                    title = unescape(match.group(1))
                    break
            
            # スニペット（p タグ）を抽出
            snippet_match = re.search(r'<p[^>]*>([^<]+)</p>', article_html)
            snippet = unescape(snippet_match.group(1)) if snippet_match else ""
            
            if url.startswith('http'):
                results.append({
                    "title": title[:100] if title else url.split('/')[2],
                    "url": url,
                    "snippet": snippet[:200],
                    "published_date": None,
                    "score": 0.5,
                })
                
                if len(results) >= 10:
                    break
        
        # パターン2: 結果がない場合、<div class="result"> パターンを試す
        if not results:
            result_pattern = r'<div[^>]*class="result[^"]*"[^>]*>(.*?)</div>\s*</div>'
            for match in re.finditer(result_pattern, html, re.DOTALL):
                result_html = match.group(1)
                
                url_match = re.search(r'href="([^"]+)"', result_html)
                if not url_match:
                    continue
                
                url = unescape(url_match.group(1))
                title_match = re.search(r'href="[^"]+">([^<]+)</a>', result_html)
                title = unescape(title_match.group(1)) if title_match else ""
                
                snippet_match = re.search(r'<p>([^<]+)</p>', result_html)
                snippet = unescape(snippet_match.group(1)) if snippet_match else ""
                
                if url.startswith('http'):
                    results.append({
                        "title": title[:100] if title else url.split('/')[2],
                        "url": url,
                        "snippet": snippet[:200],
                        "published_date": None,
                        "score": 0.5,
                    })
                    
                    if len(results) >= 10:
                        break
        
        return results[:10]

    def _parse_google_html(self, html: str) -> List[Dict[str, Any]]:
        """Google HTML から検索結果をパース"""
        import re
        
        results = []
        
        # Google の検索結果 div を抽出
        # パターン: <div data-sokoban-container...> の中に <a href="...">タイトル</a> と <span>説明</span>
        
        # より単純なパターンマッチ
        # href="([^"]+)" から URL を抽出
        link_pattern = r'href="(/url\?q=([^&"]+)|([^"]+))"[^>]*>([^<]+)</a>'
        
        for match in re.finditer(link_pattern, html):
            try:
                # URL をデコード
                url = match.group(2) or match.group(3)
                if not url:
                    continue
                
                # Google結果からのURL抽出の場合
                if url.startswith('/'):
                    continue
                
                # タイトルを取得
                title = match.group(4)
                
                # パラメータをデコード
                import urllib.parse
                try:
                    url = urllib.parse.unquote(url)
                except:
                    pass
                
                # 有効な URL かチェック
                if url.startswith('http'):
                    results.append({
                        "title": title[:100],
                        "url": url,
                        "snippet": "",  # HTMLパースは複雑なので省略
                        "date": None,
                    })
                    
                    if len(results) >= 10:
                        break
            except:
                continue
        
        # 結果が少なければ、別のパターンを試す
        if len(results) < 3:
            # Markdown リンク形式を試す（Jina Reader の場合）
            url_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
            for match in re.finditer(url_pattern, html):
                title, url = match.groups()
                if url.startswith('http') and not any(x in url for x in ['.css', '.js', '.png']):
                    results.append({
                        "title": title[:100],
                        "url": url,
                        "snippet": "",
                        "date": None,
                    })
                    if len(results) >= 10:
                        break
        
        return results[:10]


    def _parse_results(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        for item in response.get("results", []):
            results.append(
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "snippet": item.get("snippet"),
                    "published_date": item.get("published_date") or item.get("date"),
                    "score": item.get("score", 0.5),
                }
            )
        return results
