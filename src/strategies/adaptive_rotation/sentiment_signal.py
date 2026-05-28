"""
Sentiment Signal Module
========================

Integrates news sentiment into the adaptive rotation strategy.

Data Sources:
- FMP news (already cached in SQLite via data_fetcher)
- Finnhub news (free tier: 60 calls/min)

Produces:
- Per-ticker sentiment score (-1.0 to +1.0)
- Per-group aggregated sentiment score
- Market-wide sentiment score (for regime overlay)

Integration Points:
- Group strength: sentiment-adjusted Information Ratio
- Intra-group ranking: sentiment boost/penalty on Z-scores
- Market regime: extreme negative sentiment as additional risk signal

Author: Sentiment Integration
Version: 1.0.0
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SENTIMENT_MAP = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}


@dataclass
class TickerSentiment:
    symbol: str
    score: float  # -1.0 to +1.0 weighted average
    article_count: int
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    avg_confidence: float
    freshness_hours: float  # hours since most recent article


@dataclass
class GroupSentiment:
    group_name: str
    score: float  # average of constituent ticker scores
    ticker_scores: Dict[str, float]
    article_count: int
    coverage: float  # fraction of group tickers with news


@dataclass
class SentimentResult:
    ticker_sentiments: Dict[str, TickerSentiment]
    group_sentiments: Dict[str, GroupSentiment]
    market_sentiment: float  # overall market mood
    as_of_date: pd.Timestamp
    total_articles: int
    scorer_backend: str = "keyword"

    def get_ticker_score(self, symbol: str, default: float = 0.0) -> float:
        ts = self.ticker_sentiments.get(symbol)
        return ts.score if ts else default

    def get_group_score(self, group_name: str, default: float = 0.0) -> float:
        gs = self.group_sentiments.get(group_name)
        return gs.score if gs else default

    def to_audit_dict(self) -> Dict[str, Any]:
        return {
            "scorer_backend": self.scorer_backend,
            "market_sentiment": round(self.market_sentiment, 4),
            "total_articles": self.total_articles,
            "group_sentiments": {
                name: {"score": round(gs.score, 4), "articles": gs.article_count, "coverage": round(gs.coverage, 2)}
                for name, gs in self.group_sentiments.items()
            },
            "ticker_sentiments": {
                sym: {"score": round(ts.score, 4), "articles": ts.article_count}
                for sym, ts in self.ticker_sentiments.items()
                if ts.article_count > 0
            },
        }


class SentimentScorer:
    """
    Pluggable sentiment scoring backends.
    Priority: finbert (free, local) > gemini > openai > keyword (fallback)
    """

    def __init__(self, backend: str = "auto"):
        self._backend = backend
        self._finbert_pipeline = None
        self._gemini_client = None
        self._resolved_backend = None

    def _resolve_backend(self) -> str:
        if self._resolved_backend:
            return self._resolved_backend

        if self._backend != "auto":
            self._resolved_backend = self._backend
            return self._backend

        # Auto-detect best available backend
        # 1. FinBERT local (free, best for finance — needs torch>=2.6 / Python 3.10+)
        try:
            from transformers import pipeline
            self._finbert_pipeline = pipeline(
                "sentiment-analysis",
                model="ProsusAI/finbert",
                tokenizer="ProsusAI/finbert",
                top_k=None,
            )
            self._resolved_backend = "finbert"
            logger.info("Sentiment backend: FinBERT (local, free)")
            return "finbert"
        except Exception as e:
            logger.debug(f"FinBERT local not available: {e}")

        # 1b. FinBERT via Hugging Face Inference API (free, no local torch needed)
        hf_token = os.environ.get("HF_API_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
        if hf_token and "your_" not in hf_token:
            self._resolved_backend = "finbert_api"
            logger.info("Sentiment backend: FinBERT via HuggingFace API (free)")
            return "finbert_api"

        # 2. Gemini
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key and "your_" not in gemini_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=gemini_key)
                self._resolved_backend = "gemini"
                logger.info("Sentiment backend: Gemini API")
                return "gemini"
            except Exception as e:
                logger.debug(f"Gemini not available: {e}")

        # 3. OpenAI (existing in the repo)
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key and "your_" not in openai_key:
            self._resolved_backend = "openai"
            logger.info("Sentiment backend: OpenAI API")
            return "openai"

        # 4. Keyword fallback
        self._resolved_backend = "keyword"
        logger.info("Sentiment backend: keyword fallback (no API keys found)")
        return "keyword"

    def score(self, title: str, text: str = "") -> Dict[str, Any]:
        """
        Score a single article. Returns {"sentiment": str, "confidence": float}.
        """
        backend = self._resolve_backend()

        if backend == "finbert":
            return self._score_finbert(title, text)
        elif backend == "finbert_api":
            return self._score_finbert_api(title, text)
        elif backend == "gemini":
            return self._score_gemini(title, text)
        elif backend == "openai":
            return self._score_openai(title, text)
        else:
            label = SentimentAnalyzer._keyword_sentiment(title, text)
            return {"sentiment": label, "confidence": 0.3}

    def _score_finbert(self, title: str, text: str) -> Dict[str, Any]:
        if not self._finbert_pipeline:
            try:
                from transformers import pipeline
                self._finbert_pipeline = pipeline(
                    "sentiment-analysis",
                    model="ProsusAI/finbert",
                    tokenizer="ProsusAI/finbert",
                    top_k=None,
                )
            except Exception:
                label = SentimentAnalyzer._keyword_sentiment(title, text)
                return {"sentiment": label, "confidence": 0.3}

        input_text = f"{title}. {text}"[:512]
        try:
            results = self._finbert_pipeline(input_text)
            if isinstance(results, list) and isinstance(results[0], list):
                results = results[0]
            best = max(results, key=lambda x: x["score"])
            return {"sentiment": best["label"].lower(), "confidence": round(best["score"], 4)}
        except Exception as e:
            logger.debug(f"FinBERT scoring failed: {e}")
            label = SentimentAnalyzer._keyword_sentiment(title, text)
            return {"sentiment": label, "confidence": 0.3}

    def _score_finbert_api(self, title: str, text: str) -> Dict[str, Any]:
        """Score via Hugging Face Inference API (free, no local model needed)."""
        import requests as _requests
        hf_token = os.environ.get("HF_API_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
        if not hf_token:
            label = SentimentAnalyzer._keyword_sentiment(title, text)
            return {"sentiment": label, "confidence": 0.3}

        input_text = f"{title}. {text}"[:512]
        try:
            resp = _requests.post(
                "https://api-inference.huggingface.co/models/ProsusAI/finbert",
                headers={"Authorization": f"Bearer {hf_token}"},
                json={"inputs": input_text},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and isinstance(data[0], list):
                data = data[0]
            best = max(data, key=lambda x: x["score"])
            return {"sentiment": best["label"].lower(), "confidence": round(best["score"], 4)}
        except Exception as e:
            logger.debug(f"FinBERT API scoring failed: {e}")
            label = SentimentAnalyzer._keyword_sentiment(title, text)
            return {"sentiment": label, "confidence": 0.3}

    def _ensure_gemini_client(self):
        if not self._gemini_client:
            gemini_key = os.environ.get("GEMINI_API_KEY")
            if not gemini_key:
                return False
            from google import genai
            self._gemini_client = genai.Client(api_key=gemini_key)
        return True

    def _score_gemini(self, title: str, text: str) -> Dict[str, Any]:
        if not self._ensure_gemini_client():
            return {"sentiment": "neutral", "confidence": 0.3}

        snippet = text[:800] if text else ""
        prompt = (
            f"Classify this financial news as positive, neutral, or negative. "
            f"Reply with ONLY a JSON object: {{\"sentiment\": \"...\", \"confidence\": 0.XX}}\n\n"
            f"Title: {title}\nContent: {snippet}"
        )
        try:
            response = self._gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            import json
            parsed = json.loads(response.text.strip().strip("`").replace("json\n", ""))
            if parsed.get("sentiment") in ("positive", "neutral", "negative"):
                return {"sentiment": parsed["sentiment"], "confidence": float(parsed.get("confidence", 0.5))}
        except Exception as e:
            logger.debug(f"Gemini scoring failed: {e}")

        label = SentimentAnalyzer._keyword_sentiment(title, text)
        return {"sentiment": label, "confidence": 0.3}

    def score_batch(self, articles: List[Dict[str, str]], batch_size: int = 20) -> List[Dict[str, Any]]:
        """Score multiple articles in batched Gemini calls (1 API call per batch_size articles)."""
        backend = self._resolve_backend()
        if backend != "gemini" or not self._ensure_gemini_client():
            return [self.score(a.get("title", ""), a.get("text", "")) for a in articles]

        import json
        results = []
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            numbered = "\n".join(
                f"{j+1}. {a.get('title', '')[:200]}"
                for j, a in enumerate(batch)
            )
            prompt = (
                f"Classify each financial news headline as positive, neutral, or negative.\n"
                f"Reply with ONLY a JSON array of objects: "
                f'[{{"sentiment": "...", "confidence": 0.XX}}, ...]\n'
                f"One object per headline, in order.\n\n{numbered}"
            )
            try:
                response = self._gemini_client.models.generate_content(
                    model="gemini-2.5-flash", contents=prompt,
                )
                raw = response.text.strip().strip("`").replace("json\n", "")
                parsed = json.loads(raw)
                if isinstance(parsed, list) and len(parsed) == len(batch):
                    for item in parsed:
                        if item.get("sentiment") in ("positive", "neutral", "negative"):
                            results.append({"sentiment": item["sentiment"], "confidence": float(item.get("confidence", 0.5))})
                        else:
                            results.append({"sentiment": "neutral", "confidence": 0.3})
                    continue
            except Exception as e:
                logger.debug(f"Gemini batch scoring failed: {e}")
            for a in batch:
                label = SentimentAnalyzer._keyword_sentiment(a.get("title", ""), a.get("text", ""))
                results.append({"sentiment": label, "confidence": 0.3})
        return results

    def _score_openai(self, title: str, text: str) -> Dict[str, Any]:
        try:
            from openai import OpenAI
            client = OpenAI()
            snippet = text[:800] if text else ""
            response = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": "You classify financial news sentiment. Reply with JSON only: {\"sentiment\": \"positive|neutral|negative\", \"confidence\": 0.XX}"},
                    {"role": "user", "content": f"Title: {title}\nContent: {snippet}"},
                ],
                temperature=0.1,
                max_tokens=60,
            )
            import json
            parsed = json.loads(response.choices[0].message.content.strip())
            if parsed.get("sentiment") in ("positive", "neutral", "negative"):
                return {"sentiment": parsed["sentiment"], "confidence": float(parsed.get("confidence", 0.5))}
        except Exception as e:
            logger.debug(f"OpenAI scoring failed: {e}")

        label = SentimentAnalyzer._keyword_sentiment(title, text)
        return {"sentiment": label, "confidence": 0.3}

    @property
    def backend_name(self) -> str:
        return self._resolve_backend()


class SentimentAnalyzer:
    """Reads news sentiment from the database and computes trading signals."""

    def __init__(
        self,
        data_store=None,
        data_fetcher=None,
        lookback_days: int = 7,
        decay_half_life_days: float = 2.0,
        min_articles: int = 2,
        finnhub_api_key: Optional[str] = None,
        sentiment_backend: str = "auto",
    ):
        self.data_store = data_store
        self.data_fetcher = data_fetcher
        self.lookback_days = lookback_days
        self.decay_half_life_days = decay_half_life_days
        self.min_articles = min_articles
        key = finnhub_api_key or os.environ.get("FINNHUB_API_KEY")
        self.finnhub_api_key = key if key and "your_" not in key else None
        self._finnhub_client = None
        self.scorer = SentimentScorer(backend=sentiment_backend)

    def _get_finnhub_client(self):
        if self._finnhub_client is not None:
            return self._finnhub_client
        if not self.finnhub_api_key:
            return None
        try:
            import finnhub
            self._finnhub_client = finnhub.Client(api_key=self.finnhub_api_key)
            return self._finnhub_client
        except (ImportError, Exception) as e:
            logger.debug(f"Finnhub client init failed: {e}")
            return None

    def fetch_finnhub_news(self, symbol: str, from_date: str, to_date: str) -> List[Dict[str, Any]]:
        """Fetch news from Finnhub and return in a normalized format."""
        client = self._get_finnhub_client()
        if not client:
            return []
        try:
            news = client.company_news(symbol, _from=from_date, to=to_date)
            articles = []
            for item in (news or []):
                articles.append({
                    "symbol": symbol,
                    "title": item.get("headline", ""),
                    "text": item.get("summary", ""),
                    "url": item.get("url", ""),
                    "source": item.get("source", "finnhub"),
                    "publishedDate": datetime.fromtimestamp(item.get("datetime", 0)).strftime("%Y-%m-%d %H:%M:%S"),
                })
            return articles
        except Exception as e:
            logger.warning(f"Finnhub news fetch failed for {symbol}: {e}")
            return []

    @staticmethod
    def _keyword_sentiment(title: str, text: str = "") -> str:
        """Fast keyword-based sentiment when GPT annotation is unavailable."""
        blob = (title + " " + text).lower()
        pos = ("surge", "soar", "rally", "beat", "upgrade", "record high",
               "outperform", "bullish", "profit", "gain", "boost", "strong")
        neg = ("crash", "plunge", "drop", "miss", "downgrade", "bearish",
               "loss", "decline", "risk", "warn", "cut", "layoff", "sell-off",
               "selloff", "lawsuit", "fraud", "bankruptcy", "default")
        p = sum(1 for w in pos if w in blob)
        n = sum(1 for w in neg if w in blob)
        if p > n:
            return "positive"
        if n > p:
            return "negative"
        return "neutral"

    def _compute_ticker_sentiment(
        self, symbol: str, articles_df: pd.DataFrame, as_of: pd.Timestamp
    ) -> TickerSentiment:
        """Compute time-decayed sentiment score for a single ticker."""
        if articles_df.empty:
            return TickerSentiment(
                symbol=symbol, score=0.0, article_count=0,
                positive_pct=0.0, negative_pct=0.0, neutral_pct=0.0,
                avg_confidence=0.0, freshness_hours=float("inf"),
            )

        df = articles_df.copy()

        # Fill missing sentiment using the pluggable scorer (FinBERT / Gemini / OpenAI / keyword)
        if "sentiment" not in df.columns:
            df["sentiment"] = None
        if "sentiment_confidence" not in df.columns:
            df["sentiment_confidence"] = None
        mask = df["sentiment"].isna() | ~df["sentiment"].isin(["positive", "neutral", "negative"])
        if mask.any():
            to_score = [
                {"title": str(r.get("title", "")), "text": str(r.get("text", r.get("body", "")))}
                for _, r in df.loc[mask].iterrows()
            ]
            scored = self.scorer.score_batch(to_score)
            df.loc[mask, "sentiment"] = [s["sentiment"] for s in scored]
            df.loc[mask, "sentiment_confidence"] = [s["confidence"] for s in scored]

        df = df[df["sentiment"].isin(["positive", "neutral", "negative"])]

        if df.empty:
            return TickerSentiment(
                symbol=symbol, score=0.0, article_count=0,
                positive_pct=0.0, negative_pct=0.0, neutral_pct=0.0,
                avg_confidence=0.0, freshness_hours=float("inf"),
            )

        df["numeric_sentiment"] = df["sentiment"].map(SENTIMENT_MAP)

        # Coalesce multiple date columns (FMP uses published_datetime, Finnhub uses publishedDate)
        df["pub_dt"] = pd.NaT
        for col in ("published_datetime", "publishedDate"):
            if col in df.columns:
                parsed = pd.to_datetime(df[col], errors="coerce")
                df["pub_dt"] = df["pub_dt"].fillna(parsed)
        df["pub_dt"] = df["pub_dt"].fillna(as_of)

        hours_ago = (as_of - df["pub_dt"]).dt.total_seconds() / 3600.0
        hours_ago = hours_ago.clip(lower=0)
        half_life_hours = self.decay_half_life_days * 24.0
        weights = np.exp(-0.693 * hours_ago / half_life_hours)

        conf = df.get("sentiment_confidence")
        if conf is not None:
            conf = pd.to_numeric(conf, errors="coerce").fillna(0.5)
            weights = weights * conf

        total_w = weights.sum()
        if total_w == 0:
            score = 0.0
        else:
            score = float((df["numeric_sentiment"] * weights).sum() / total_w)

        n = len(df)
        counts = df["sentiment"].value_counts()
        freshness = float(hours_ago.min()) if len(hours_ago) > 0 else float("inf")
        avg_conf = float(conf.mean()) if conf is not None and len(conf) > 0 else 0.0

        return TickerSentiment(
            symbol=symbol,
            score=np.clip(score, -1.0, 1.0),
            article_count=n,
            positive_pct=counts.get("positive", 0) / n,
            negative_pct=counts.get("negative", 0) / n,
            neutral_pct=counts.get("neutral", 0) / n,
            avg_confidence=avg_conf,
            freshness_hours=freshness,
        )

    def analyze(
        self,
        symbols: List[str],
        group_map: Dict[str, List[str]],
        as_of_date: pd.Timestamp,
        fetch_new: bool = True,
        analyze_sentiment: bool = True,
    ) -> SentimentResult:
        """
        Run full sentiment analysis for all symbols.

        Args:
            symbols: all ticker symbols to analyze
            group_map: {group_name: [symbols]} mapping
            as_of_date: decision date
            fetch_new: whether to fetch fresh news (False for backtest)
            analyze_sentiment: whether to run GPT annotation on missing sentiment
        """
        from_date = (as_of_date - timedelta(days=self.lookback_days)).strftime("%Y-%m-%d")
        to_date = as_of_date.strftime("%Y-%m-%d")

        ticker_sentiments: Dict[str, TickerSentiment] = {}
        total_articles = 0

        for symbol in symbols:
            if symbol.startswith("^"):
                continue

            articles_df = pd.DataFrame()

            # 1) Try existing DB data
            if self.data_store:
                try:
                    articles_df = self.data_store.get_news_articles(symbol, from_date, to_date)
                except Exception as e:
                    logger.debug(f"DB news read failed for {symbol}: {e}")

            # 2) Fetch new data if enabled
            if fetch_new and self.data_fetcher:
                try:
                    articles_df = self.data_fetcher.get_news(
                        symbol, from_date, to_date,
                        analyze_sentiment=analyze_sentiment,
                    )
                except Exception as e:
                    logger.warning(f"News fetch failed for {symbol}: {e}")

            # 3) Supplement with Finnhub if we have few articles
            if len(articles_df) < self.min_articles and self.finnhub_api_key:
                fh_articles = self.fetch_finnhub_news(symbol, from_date, to_date)
                if fh_articles:
                    if self.data_fetcher and analyze_sentiment:
                        self.data_fetcher._annotate_sentiment(fh_articles)
                    fh_df = pd.DataFrame(fh_articles)
                    if not fh_df.empty:
                        articles_df = pd.concat([articles_df, fh_df], ignore_index=True)

            ts = self._compute_ticker_sentiment(symbol, articles_df, as_of_date)
            ticker_sentiments[symbol] = ts
            total_articles += ts.article_count

        # Aggregate per group
        group_sentiments: Dict[str, GroupSentiment] = {}
        for group_name, group_symbols in group_map.items():
            scores = {}
            group_articles = 0
            tickers_with_news = 0
            for sym in group_symbols:
                ts = ticker_sentiments.get(sym)
                if ts and ts.article_count >= self.min_articles:
                    scores[sym] = ts.score
                    group_articles += ts.article_count
                    tickers_with_news += 1

            n_group = len(group_symbols)
            coverage = tickers_with_news / n_group if n_group > 0 else 0.0
            avg_score = float(np.mean(list(scores.values()))) if scores else 0.0

            group_sentiments[group_name] = GroupSentiment(
                group_name=group_name,
                score=avg_score,
                ticker_scores=scores,
                article_count=group_articles,
                coverage=coverage,
            )

        # Market-wide sentiment (average of all ticker scores with news)
        scored_tickers = [ts.score for ts in ticker_sentiments.values() if ts.article_count >= self.min_articles]
        market_sentiment = float(np.mean(scored_tickers)) if scored_tickers else 0.0

        return SentimentResult(
            ticker_sentiments=ticker_sentiments,
            group_sentiments=group_sentiments,
            market_sentiment=market_sentiment,
            as_of_date=as_of_date,
            total_articles=total_articles,
            scorer_backend=self.scorer.backend_name,
        )


def apply_sentiment_to_group_strength(
    group_strength_result,
    sentiment_result: SentimentResult,
    sentiment_weight: float = 0.15,
):
    """
    Adjust group Information Ratios by blending in sentiment.

    IR_adjusted = IR * (1 + sentiment_weight * group_sentiment_score)

    A group with strong positive sentiment gets a boost;
    a group with negative sentiment gets penalized.
    This only adjusts the ranking metric, not the raw data.
    """
    for group_name, metrics in group_strength_result.groups.items():
        if not metrics.is_valid:
            continue
        sent_score = sentiment_result.get_group_score(group_name, 0.0)
        adjustment = 1.0 + sentiment_weight * sent_score
        metrics.information_ratio = metrics.information_ratio * adjustment

    # Re-rank after adjustment
    from .group_strength import rank_groups_by_strength, select_active_groups
    ranked = rank_groups_by_strength(group_strength_result.groups, "information_ratio")
    group_strength_result.ranked_groups = ranked

    max_active = len(group_strength_result.active_groups)
    group_strength_result.active_groups = select_active_groups(
        ranked, max_active, group_strength_result.groups, trend_filter=True
    )

    return group_strength_result


def apply_sentiment_to_rankings(
    group_rankings: Dict[str, Any],
    sentiment_result: SentimentResult,
    sentiment_weight: float = 0.20,
):
    """
    Adjust intra-group asset Z-scores by blending in per-ticker sentiment.

    z_adjusted = z + sentiment_weight * ticker_sentiment_score

    Positive sentiment nudges a stock up in the ranking;
    negative sentiment pushes it down.
    """
    for group_name, ranking in group_rankings.items():
        for symbol, score in ranking.asset_scores.items():
            if not score.is_valid:
                continue
            sent_score = sentiment_result.get_ticker_score(symbol, 0.0)
            score.zscore = score.zscore + sentiment_weight * sent_score

        # Re-sort
        valid_scores = {
            sym: s for sym, s in ranking.asset_scores.items() if s.is_valid
        }
        sorted_assets = sorted(valid_scores.keys(), key=lambda s: valid_scores[s].zscore, reverse=True)
        ranking.ranked_assets = sorted_assets
        for rank, sym in enumerate(sorted_assets, 1):
            ranking.asset_scores[sym].rank = rank
        if hasattr(ranking, "top_n_assets"):
            n = len(ranking.top_n_assets)
            ranking.top_n_assets = sorted_assets[:n]

    return group_rankings


def sentiment_regime_overlay(
    sentiment_result: SentimentResult,
    negative_threshold: float = -0.4,
    article_threshold: int = 10,
) -> Dict[str, Any]:
    """
    Check if sentiment is extremely negative across the market,
    which can serve as an additional risk-off signal.

    Returns a dict with:
        - is_bearish: bool — True if market sentiment is very negative
        - market_score: float
        - recommendation: str — "tighten" or "normal"
    """
    ms = sentiment_result.market_sentiment
    total = sentiment_result.total_articles

    is_bearish = ms <= negative_threshold and total >= article_threshold

    return {
        "is_bearish": is_bearish,
        "market_score": round(ms, 4),
        "total_articles": total,
        "recommendation": "tighten" if is_bearish else "normal",
    }
